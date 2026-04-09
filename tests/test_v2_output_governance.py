from __future__ import annotations

import json
import runpy
from pathlib import Path

from app.common.schemas import RiskPoint
from app.pipelines.v2.assembler import build_v2_final_output
from app.web.v2_app import build_review_view_from_final_output
from app.pipelines.v2.output_governance import govern_comparison_artifact, validate_governed_result
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


def _build_w012_cert_scoring_comparison() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="cert-main",
                title="以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险",
                severity="高风险",
                review_type="评分因素合规性 / 限定特定认证或发证机构",
                source_locations=["评分内容A"],
                source_excerpts=["省级标准协会颁发的采用国际标准产品确认证书和采用国际标准产品标志证书，每项40分。"],
                risk_judgment=["主风险应保留。"],
                legal_basis=["不得限定或者指定特定供应商。"],
                rectification=["删除特定发证机构限定。"],
                topics=["cross_topic", "baseline"],
                source_rules=["compare_rule", "baseline"],
            ),
            MergedRiskCluster(
                cluster_id="cert-support-1",
                title="以特定认证证书作为高分条件，存在限定特定供应商和倾向性评分风险",
                severity="高风险",
                review_type="评分项合规性审查",
                source_locations=["评分内容B"],
                source_excerpts=["CNAS中国认可产品标志证书得20分，本小项最高100分。"],
                risk_judgment=["这是同一组评分证据中的证书侧佐证。"],
                legal_basis=["非强制认证不宜作为高分门槛。"],
                rectification=["删除特定证书高分条件。"],
                topics=["scoring"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="cert-support-2",
                title="评分标准中要求特定非强制性认证证书，具有倾向性",
                severity="中风险",
                review_type="技术参数倾向性/评分因素不相关",
                source_locations=["评分内容C"],
                source_excerpts=["省级标准协会颁发的证书效力不一。"],
                risk_judgment=["这是同一组评分证据中的非强制认证佐证。"],
                legal_basis=["不得以非强制认证限制竞争。"],
                rectification=["删除非强制性认证要求。"],
                topics=["baseline"],
                source_rules=["baseline"],
            ),
            MergedRiskCluster(
                cluster_id="cert-support-3",
                title="综合实力评分中三项体系认证要求过于刚性，可能排斥中小企业",
                severity="中风险",
                review_type="证书奖项审查",
                source_locations=["评分内容D"],
                source_excerpts=["每具备一项证书得35分，两项70分，三项100分。"],
                risk_judgment=["这是同一组认证组合门槛/权重佐证。"],
                legal_basis=["认证项权重不宜畸高。"],
                rectification=["压缩认证项分值。"],
                topics=["performance_staff"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="cert-support-4",
                title="指定特定认证机构，具有排他性",
                severity="中风险",
                review_type="评分项合规性审查",
                source_locations=["评分内容E"],
                source_excerpts=["要求由特定协会或认证机构出具相关认证证明。"],
                risk_judgment=["这是同一组评分证据中的发证机构侧佐证。"],
                legal_basis=["不得限定特定认证机构。"],
                rectification=["删除特定机构限定。"],
                topics=["scoring"],
                source_rules=["topic"],
            ),
        ],
        metadata={},
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

    assert len(formal_titles) == 17
    assert formal_titles.count("业绩评分限定特定行政区域，存在地域排斥风险") == 1
    assert formal_titles.count("验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险") == 1
    assert formal_titles.count("履约保证金比例严重超标") == 1
    assert formal_titles.count("项目负责人评分项设置过高且累计分值不合理，存在重复评价和倾向性风险") == 1
    assert formal_titles.count("以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险") == 1
    assert "以特定认证证书作为高分条件，存在限定特定供应商和倾向性评分风险" not in formal_titles
    assert "指定特定认证机构，具有排他性" not in formal_titles
    assert "残疾人福利性单位及监狱企业政策表述不完整" in pending_titles
    assert "节能环保产品政策条款缺失" in pending_titles
    assert "社保缴纳证明要求存在例外情形，需关注执行一致性" in excluded_titles


def test_output_governance_can_promote_pending_candidate_to_formal() -> None:
    comparison = ComparisonArtifact(
        clusters=[],
        metadata={
            "pending_review_items": [
                {
                    "title": "将项目验收方案纳入评审因素，违反评审规则合规性要求",
                    "severity": "中高风险",
                    "review_type": "评分因素合规性 / 评审规则设置合法性",
                    "topic": "评分办法",
                    "source_location": "评分条款",
                    "source_excerpt": "验收方案优的得满分。",
                    "reason": "compare 初步判成待补证。",
                }
            ]
        },
    )
    governed = govern_comparison_artifact("sample.docx", comparison)
    assert [item.decision.canonical_title for item in governed.formal_risks] == ["将项目验收方案纳入评审因素，违反评审规则合规性要求"]
    assert governed.pending_review_items == []


def test_output_governance_can_promote_excluded_candidate_to_pending() -> None:
    comparison = ComparisonArtifact(
        clusters=[],
        metadata={
            "excluded_risks": [
                {
                    "title": "节能环保产品政策条款缺失",
                    "severity": "中风险",
                    "review_type": "政策条款审查",
                    "source_location": "政策章节",
                    "source_excerpt": "当前仅见政策章节召回不足。",
                    "reason": "compare 初步排除了该项。",
                }
            ]
        },
    )
    governed = govern_comparison_artifact("sample.docx", comparison)
    assert [item.decision.canonical_title for item in governed.pending_review_items] == ["节能环保产品政策条款缺失"]
    assert governed.excluded_risks == []


def test_output_governance_can_demote_formal_candidate_to_excluded() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="formal-1",
                title="社保缴纳证明要求存在例外情形，需关注执行一致性",
                severity="中风险",
                review_type="资格条件审查",
                source_locations=["资格条款"],
                source_excerpts=["退休返聘人员可免提供社保，若供应商成立不足三个月也可说明替代。"],
                topics=["qualification"],
            )
        ],
        metadata={},
    )
    governed = govern_comparison_artifact("sample.docx", comparison)
    assert [item.decision.canonical_title for item in governed.excluded_risks] == ["社保缴纳证明要求存在例外情形，需关注执行一致性"]
    assert governed.formal_risks == []


def test_output_governance_resolves_same_family_conflict_between_formal_and_pending() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="formal-acceptance",
                title="将项目验收方案纳入评审因素，违反评审规则合规性要求",
                severity="高风险",
                review_type="评分因素合规性审查",
                source_locations=["评分条款A"],
                source_excerpts=["验收方案优的得满分。"],
                topics=["scoring"],
                source_rules=["compare_rule:R-003"],
            )
        ],
        metadata={
            "pending_review_items": [
                {
                    "title": "将项目验收方案纳入评审因素，违反评审规则合规性要求",
                    "severity": "需人工复核",
                    "review_type": "评分因素合规性审查",
                    "topic": "评分办法",
                    "source_location": "评分条款B",
                    "source_excerpt": "验收方案作为评分依据。",
                    "reason": "另一来源仍给了待补证。",
                }
            ]
        },
    )
    governed = govern_comparison_artifact("sample.docx", comparison)
    assert [item.decision.canonical_title for item in governed.formal_risks] == ["将项目验收方案纳入评审因素，违反评审规则合规性要求"]
    assert governed.pending_review_items == []


def test_output_governance_resolves_same_family_conflict_between_pending_and_excluded() -> None:
    comparison = ComparisonArtifact(
        clusters=[],
        metadata={
            "pending_review_items": [
                {
                    "title": "节能环保产品政策条款缺失",
                    "severity": "需人工复核",
                    "review_type": "政策条款审查",
                    "topic": "政策条款",
                    "source_location": "政策条款A",
                    "source_excerpt": "政策条款未完整召回。",
                    "reason": "当前仅能确认政策章节召回不足。",
                }
            ],
            "excluded_risks": [
                {
                    "title": "节能环保产品政策落实条款缺失",
                    "severity": "中风险",
                    "review_type": "政策条款审查",
                    "source_location": "政策条款B",
                    "source_excerpt": "该表述其实是公告承接字段，暂不作为正式风险。",
                    "reason": "边界提示项，建议排除。",
                }
            ],
        },
    )
    governed = govern_comparison_artifact("sample.docx", comparison)
    assert governed.formal_risks == []
    assert [item.decision.canonical_title for item in governed.pending_review_items] == ["节能环保产品政策条款缺失"]
    assert governed.excluded_risks == []


def test_output_governance_resolves_same_family_conflict_across_all_three_layers() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="formal-template",
                title="验收时点约定缺失，导致验收流程不可操作",
                severity="中风险",
                review_type="合同模板边界审查",
                source_locations=["合同模板A"],
                source_excerpts=["到货后的 ____ 个工作日内组织验收。"],
                topics=["acceptance"],
            )
        ],
        metadata={
            "pending_review_items": [
                {
                    "title": "验收流程关键时点留白",
                    "severity": "需人工复核",
                    "review_type": "合同模板边界审查",
                    "topic": "验收条款",
                    "source_location": "合同模板B",
                    "source_excerpt": "安装调试完毕后的 ____ 个工作日内组织验收。",
                    "reason": "compare 另一来源给了待补证。",
                }
            ],
            "excluded_risks": [
                {
                    "title": "验收时点约定缺失，导致验收流程不可操作",
                    "severity": "中风险",
                    "review_type": "合同模板边界审查",
                    "source_location": "合同模板C",
                    "source_excerpt": "检测通过后___个工作日内。",
                    "reason": "模板占位符，建议排除。",
                }
            ],
        },
    )
    governed = govern_comparison_artifact("sample.docx", comparison)
    assert governed.formal_risks == []
    assert governed.pending_review_items == []
    assert [item.decision.canonical_title for item in governed.excluded_risks] == ["验收时点约定缺失，导致验收流程不可操作"]


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
    family_layers: dict[str, set[str]] = {}
    for layer in ("formal_risks", "pending_review_items", "excluded_risks"):
        for item in final_output["governance"][layer]:
            family_key = item["family"]["family_key"]
            family_layers.setdefault(family_key, set()).add(layer)
    assert all(len(layers) == 1 for layers in family_layers.values())


def test_build_v2_final_output_rejects_cross_layer_family_conflicts() -> None:
    comparison = _build_sample_comparison()
    governed = govern_comparison_artifact("sample.docx", comparison)
    duplicated = governed.pending_review_items[0]
    duplicated.family.family_key = governed.formal_risks[0].family.family_key
    duplicated.family.canonical_title = governed.formal_risks[0].family.canonical_title

    try:
        validate_governed_result(governed)
    except ValueError as exc:
        assert "cross-layer family conflicts remain after governance" in str(exc)
    else:
        raise AssertionError("expected cross-layer family conflict gate to reject invalid governed result")


def test_output_governance_blocks_topic_pseudo_rule_missing_detection_report_from_formal() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="pseudo-topic-1",
                title="缺失检测报告及认证资质要求",
                severity="高风险",
                review_type="检测认证要求审查",
                source_locations=["证据1、证据2、证据3"],
                source_excerpts=["全文未提及检测报告、CMA、CNAS、认证证书等要求。"],
                risk_judgment=[
                    "技术参数中引用了多项标准，但未要求供应商提供具备CMA/CNAS资质的第三方检测机构出具的检测报告。",
                    "未明确是否要求产品通过CCC认证或其他强制性认证。",
                ],
                topics=["technical_standard"],
                source_rules=["topic"],
            )
        ],
        metadata={},
    )

    governed = govern_comparison_artifact("sample.docx", comparison)

    assert [item.decision.canonical_title for item in governed.formal_risks] == []
    assert [item.decision.canonical_title for item in governed.excluded_risks] == ["缺失检测报告及认证资质要求"]


def test_output_governance_real_replay_blocks_topic_pseudo_rule_for_diesel_case() -> None:
    comparison_payload = json.loads(
        Path("data/results/v2/20260408-162750-07e8e4d3/comparison.json").read_text(encoding="utf-8")
    )
    target_cluster = next(
        cluster for cluster in comparison_payload["clusters"] if cluster["title"] == "缺失检测报告及认证资质要求"
    )
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id=target_cluster["cluster_id"],
                title=target_cluster["title"],
                severity=target_cluster["severity"],
                review_type=target_cluster["review_type"],
                source_locations=target_cluster["source_locations"],
                source_excerpts=target_cluster["source_excerpts"],
                risk_judgment=target_cluster["risk_judgment"],
                legal_basis=target_cluster["legal_basis"],
                rectification=target_cluster["rectification"],
                topics=target_cluster["topics"],
                source_rules=target_cluster["source_rules"],
                need_manual_review=target_cluster["need_manual_review"],
            )
        ],
        metadata={},
    )

    governed = govern_comparison_artifact("SZDL2025000495-A-0330.docx", comparison)

    assert not any(item.decision.canonical_title == "缺失检测报告及认证资质要求" for item in governed.formal_risks)
    blocked = next(item for item in governed.excluded_risks if item.decision.canonical_title == "缺失检测报告及认证资质要求")
    assert blocked.identity.rule_id == "topic::缺失检测报告及认证资质要求"


def test_output_governance_absorbs_certification_scoring_supporting_risks_into_single_main_risk() -> None:
    governed = govern_comparison_artifact("diesel.docx", _build_w012_cert_scoring_comparison())

    formal_titles = [item.decision.canonical_title for item in governed.formal_risks]

    assert formal_titles.count("以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险") == 1
    assert "以特定认证证书作为高分条件，存在限定特定供应商和倾向性评分风险" not in formal_titles
    assert "评分标准中要求特定非强制性认证证书，具有倾向性" not in formal_titles
    assert "综合实力评分中三项体系认证要求过于刚性，可能排斥中小企业" not in formal_titles
    assert "指定特定认证机构，具有排他性" not in formal_titles
