from __future__ import annotations

import runpy

from app.common.schemas import RiskPoint
from app.pipelines.v2.assembler import build_v2_final_output
from app.web.v2_app import build_review_view_from_final_output
from app.pipelines.v2.output_governance import govern_comparison_artifact
from app.pipelines.v2.output_governance.identity import build_risk_family, build_risk_identity
from app.pipelines.v2.output_governance.pipeline import _coerce_pending_or_excluded
from app.pipelines.v2.output_governance.schemas import GovernanceClusterEnvelope
from app.pipelines.v2.schemas import ComparisonArtifact, MergedRiskCluster, TopicReviewArtifact, V2StageArtifact


def _build_sample_comparison() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="cluster-1",
                title="将项目验收方案纳入评审因素，违反评审规则合规性要求",
                severity="高风险",
                review_type="评分因素合规性审查",
                source_locations=["评分条款：第二章 评审标准"],
                source_excerpts=["验收方案优的得满分。"],
                risk_judgment=["验收方案被直接作为评分条件。"],
                legal_basis=["评审因素应与采购需求和合同履约相关。"],
                rectification=["删除与验收方案直接挂钩的评分条件。"],
                topics=["scoring"],
                source_rules=["compare_rule"],
            )
        ],
        metadata={
            "pending_review_items": [
                {
                    "title": "节能环保产品政策条款缺失",
                    "severity": "需人工复核",
                    "review_type": "政策条款复核",
                    "topic": "政策条款",
                    "source_location": "政策章节",
                    "source_excerpt": "未见明确节能环保政策落实条款。",
                    "reason": "当前仅能确认政策章节召回不足，先转待补证。",
                }
            ],
            "excluded_risks": [
                {
                    "title": "验收时点约定缺失，导致验收流程不可操作",
                    "severity": "中风险",
                    "review_type": "合同模板边界审查",
                    "source_location": "合同模板区",
                    "source_excerpt": "到货后的 ____ 个工作日内组织验收。",
                    "reason": "检测到模板占位，按边界规则排除。",
                }
            ],
        },
    )


def test_output_governance_objects_can_be_constructed() -> None:
    envelope = GovernanceClusterEnvelope(
        layer="formal_risks",
        title="履约保证金比例严重超标",
        review_type="合规性审查",
        severity="高风险",
        source_locations=["商务条款：履约保证金"],
        source_excerpts=["履约保证金为合同金额的12%。"],
        source_topics=["contract_payment"],
        source_rules=["compare_rule"],
        governance_reason="由 compare 候选正式风险进入治理层。",
    )
    family = build_risk_family(envelope)
    identity = build_risk_identity(envelope, family)

    assert family.family_key
    assert family.canonical_title == "履约保证金比例严重超标"
    assert identity.rule_id.startswith("compare::")
    assert identity.risk_family == family.family_key
    assert identity.evidence_anchors
    assert identity.document_span == ["商务条款：履约保证金"]


def test_output_governance_minimal_pipeline_converts_compare_result() -> None:
    comparison = _build_sample_comparison()
    governed = govern_comparison_artifact("sample.docx", comparison)

    assert governed.input_summary["cluster_count"] == 1
    assert len(governed.formal_risks) == 1
    assert len(governed.pending_review_items) == 1
    assert len(governed.excluded_risks) == 1

    formal = governed.formal_risks[0]
    assert formal.identity.rule_id.startswith("compare::")
    assert formal.decision.target_layer == "formal_risks"
    assert formal.decision.canonical_title == "将项目验收方案纳入评审因素，违反评审规则合规性要求"

    pending = governed.pending_review_items[0]
    assert pending.decision.target_layer == "pending_review_items"
    assert pending.extras == {}

    final_output = build_v2_final_output(
        "sample.docx",
        V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n"),
        V2StageArtifact(name="structure", metadata={}),
        [
            TopicReviewArtifact(
                topic="scoring",
                summary="评分专题",
                risk_points=[
                    RiskPoint(
                        title="自由文本旧标题",
                        severity="高风险",
                        review_type="旧专题输出",
                        source_location="旧位置",
                        source_excerpt="旧摘录",
                        risk_judgment=["旧判断"],
                        legal_basis=["旧依据"],
                        rectification=["旧建议"],
                    )
                ],
            )
        ],
        comparison=comparison,
        governance=governed,
    )
    assert final_output["formal_risks"][0]["title"] == "将项目验收方案纳入评审因素，违反评审规则合规性要求"
    assert final_output["pending_review_items"][0]["title"] == "节能环保产品政策条款缺失"
    assert final_output["excluded_risks"][0]["title"] == "验收时点约定缺失，导致验收流程不可操作"
    assert final_output["governance"]["formal_risks"][0]["identity"]["rule_id"].startswith("compare::")


def test_output_governance_rejects_topic_free_text_as_governed_object() -> None:
    try:
        _coerce_pending_or_excluded("仅凭 topic summary 直接冒充治理结果", "pending_review_items")
    except TypeError as exc:
        assert "structured dict items" in str(exc)
    else:
        raise AssertionError("expected TypeError for free-text governance input")


def test_output_governance_merges_duplicate_risk_families_and_decides_layers() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="r6",
                title="业绩评分限定特定行政区域，存在地域排斥风险",
                severity="高风险",
                review_type="评分项合规性审查",
                source_locations=["评分条款A"],
                source_excerpts=["仅对深圳市政府机关同类业绩计分。"],
                topics=["performance_staff"],
            ),
            MergedRiskCluster(
                cluster_id="r7",
                title="业绩评分限定特定行政区域，存在地域歧视和排斥潜在投标人风险",
                severity="中风险",
                review_type="评分项合规性审查",
                source_locations=["评分条款B"],
                source_excerpts=["限定深圳市政府机关业绩。"],
                topics=["performance_staff"],
            ),
            MergedRiskCluster(
                cluster_id="r15",
                title="履约保证金比例过高，加重供应商负担",
                severity="中风险",
                review_type="合规性审查",
                source_locations=["商务条款A"],
                source_excerpts=["履约保证金为合同金额的12%。"],
                topics=["contract_payment"],
            ),
            MergedRiskCluster(
                cluster_id="r25",
                title="履约保证金比例严重超标",
                severity="高风险",
                review_type="合规性审查",
                source_locations=["商务条款B"],
                source_excerpts=["履约保证金12%，超过法定上限。"],
                topics=["contract_payment"],
            ),
            MergedRiskCluster(
                cluster_id="r16",
                title="残疾人福利性单位及监狱企业政策表述不完整",
                severity="中风险",
                review_type="政策条款审查",
                source_locations=["政策条款A"],
                source_excerpts=["残疾人福利性单位及监狱企业表述较简。"],
                topics=["policy"],
            ),
            MergedRiskCluster(
                cluster_id="r26",
                title="社保缴纳证明要求存在例外情形，需关注执行一致性",
                severity="中风险",
                review_type="资格条件审查",
                source_locations=["资格条款A"],
                source_excerpts=["退休返聘人员可免提供社保。"],
                topics=["qualification"],
            ),
        ],
        metadata={},
    )

    governed = govern_comparison_artifact("sample.docx", comparison)
    formal_titles = [item.decision.canonical_title for item in governed.formal_risks]
    pending_titles = [item.decision.canonical_title for item in governed.pending_review_items]
    excluded_titles = [item.decision.canonical_title for item in governed.excluded_risks]

    assert formal_titles.count("业绩评分限定特定行政区域，存在地域排斥风险") == 1
    assert formal_titles.count("履约保证金比例严重超标") == 1
    assert "残疾人福利性单位及监狱企业政策表述不完整" in pending_titles
    assert "社保缴纳证明要求存在例外情形，需关注执行一致性" in excluded_titles


def test_output_governance_real_file_replay_matches_og2_target_matrix() -> None:
    ns = runpy.run_path("tests/test_w002_real_file.py")
    saved_file, structure, baseline, topics = ns["_build_0330_result_topics"]()
    comparison = ns["compare_review_artifacts"](saved_file.name, baseline, topics)
    governed = govern_comparison_artifact(saved_file.name, comparison)

    formal_titles = [item.decision.canonical_title for item in governed.formal_risks]
    pending_titles = [item.decision.canonical_title for item in governed.pending_review_items]
    excluded_titles = [item.decision.canonical_title for item in governed.excluded_risks]

    assert len(formal_titles) == 18
    assert formal_titles.count("业绩评分限定特定行政区域，存在地域排斥风险") == 1
    assert formal_titles.count("验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险") == 1
    assert formal_titles.count("履约保证金比例严重超标") == 1
    assert formal_titles.count("项目负责人评分项设置过高且累计分值不合理，存在重复评价和倾向性风险") == 1
    assert "残疾人福利性单位及监狱企业政策表述不完整" in pending_titles
    assert "节能环保产品政策条款缺失" in pending_titles
    assert "社保缴纳证明要求存在例外情形，需关注执行一致性" in excluded_titles


def test_output_governance_real_file_gate_keeps_final_output_and_web_cards_consistent() -> None:
    ns = runpy.run_path("tests/test_w002_real_file.py")
    saved_file, structure, baseline, topics = ns["_build_0330_result_topics"]()
    comparison = ns["compare_review_artifacts"](saved_file.name, baseline, topics)
    governed = govern_comparison_artifact(saved_file.name, comparison)
    final_output = build_v2_final_output(
        saved_file.name,
        baseline,
        structure,
        topics,
        comparison=comparison,
        governance=governed,
    )
    review_view = build_review_view_from_final_output(final_output, comparison.to_dict())

    formal_titles = [item["title"] for item in final_output["formal_risks"]]
    card_titles = [item["title"] for item in review_view["all_cards"]]
    assert set(formal_titles) == set(card_titles)
    assert len(formal_titles) == len(card_titles)
    assert final_output["summary"]["high_risk_titles"] == [
        item["title"] for item in final_output["formal_risks"] if item["severity"] == "高风险"
    ]
    assert final_output["summary"]["manual_review_titles"] == [item["title"] for item in final_output["pending_review_items"]]
    assert all(item["title"] not in formal_titles for item in final_output["excluded_risks"])
