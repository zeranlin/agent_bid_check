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


def _build_w014_governance_comparison() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="w014-standard",
                title="技术参数引用错误标准及标准号存疑",
                severity="高风险",
                review_type="技术参数倾向性/错误",
                source_locations=["技术参数第8点"],
                source_excerpts=[
                    "符合GB 48001-2026《汽车车门把手安全技术要求》标准中的要求；并提供福建省检测机构出具的检测报告。"
                ],
                risk_judgment=[
                    "家具采购中引用汽车车门把手标准，属于明显错误或异常标准引用。",
                    "限定福建省检测机构出具检测报告，构成检测机构地域限制。",
                ],
                legal_basis=["技术标准应准确且不得设置地域限制。"],
                rectification=["分别修正标准引用并删除检测机构地域限定。"],
                topics=["technical"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="w014-sample-main",
                title="样品制作要求具有排他性及泄露信息风险",
                severity="高风险",
                review_type="技术参数倾向性/限制竞争",
                source_locations=["样品要求第3、4点"],
                source_excerpts=[
                    "不得出现样品图样，标识等可能泄露投标人样品的任何信息，否则按无效投标处理；样品需提前组装并一次性送达。"
                ],
                risk_judgment=["样品要求过细，且匿名/复核规则失衡。"],
                legal_basis=["样品要求不得形成不合理门槛。"],
                rectification=["压缩样品要求并补充复核机制。"],
                topics=["samples_demo"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="w014-sample-support",
                title="样品隐去信息要求与评审需求存在逻辑矛盾",
                severity="中风险",
                review_type="样品要求合理性审查",
                source_locations=["样品要求第3点"],
                source_excerpts=["不得出现样品图样，标识等可能泄露投标人样品的任何信息，否则按无效投标处理。"],
                risk_judgment=["样品匿名要求与评审识别存在冲突。"],
                legal_basis=["样品评审规则应明确。"],
                rectification=["明确匿名评审与图样对照方式。"],
                topics=["samples_demo"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="w014-sample-wrong-title",
                title="商务条款中关于“无犯罪证明”的提交时限及无效投标处理存在法律风险",
                severity="高风险",
                review_type="技术参数倾向性/限制竞争",
                source_locations=["样品要求第3、4点"],
                source_excerpts=[
                    "不得出现样品图样，标识等可能泄露投标人样品的任何信息，否则按无效投标处理。"
                ],
                risk_judgment=["这条其实来自样品条款，不应继续保留无犯罪证明标题。"],
                legal_basis=["误映射标题应回归样品风险簇。"],
                rectification=["回归样品门槛风险表达。"],
                topics=["samples_demo"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="w014-tech-main",
                title="技术参数中尺寸公差及工艺要求过于具体，存在指向性嫌疑",
                severity="中风险",
                review_type="技术参数倾向性",
                source_locations=["技术参数A"],
                source_excerpts=["尺寸公差±5mm，拉手规格123*28*22mm。"],
                risk_judgment=["参数过细。"],
                legal_basis=["不得以过细参数指向特定产品。"],
                rectification=["放宽非关键参数。"],
                topics=["technical"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="w014-tech-support",
                title="技术参数存在特定工艺和连接件描述，具有排他性倾向",
                severity="高风险",
                review_type="技术参数倾向性审查",
                source_locations=["技术参数B"],
                source_excerpts=["采用三合一连接件固定，不能使用焊接和螺丝固定。"],
                risk_judgment=["特定工艺和连接件要求指向性强。"],
                legal_basis=["不得限定特定工艺。"],
                rectification=["改为性能结果导向。"],
                topics=["technical"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="w014-contract-up",
                title="商务条款中采购人单方调整权过大且结算方式不明",
                severity="中风险",
                review_type="商务条款失衡",
                source_locations=["商务要求8.3、13.3"],
                source_excerpts=["采购人有权细微调整且中标价不变，偏离超过5%按面积比例换算。"],
                risk_judgment=["采购人单方变更权过大，结算口径不清。"],
                legal_basis=["不得背离合同实质性内容。"],
                rectification=["补充双方协商和价格调整机制。"],
                topics=["contract"],
                source_rules=["baseline"],
            ),
            MergedRiskCluster(
                cluster_id="w014-acceptance-up",
                title="验收标准引用‘厂家验收标准’导致依据模糊",
                severity="中风险",
                review_type="验收标准明确性审查",
                source_locations=["验收条款"],
                source_excerpts=["按厂家验收标准、招标文件、投标文件及中标人在投标文件中所提供的样品要求等有关内容进行验收。"],
                risk_judgment=["厂家验收标准+样品要求共同作为验收依据，裁量过宽。"],
                legal_basis=["验收标准应统一明确。"],
                rectification=["删除厂家标准并固化验收标准。"],
                topics=["acceptance"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="w014-supervision",
                title="验收条款中“驻厂检查”及“终止合同”条件过于严苛",
                severity="中风险",
                review_type="商务条款失衡/验收条款",
                source_locations=["验收条款10.4"],
                source_excerpts=["采购人可对生产全过程驻厂检查，发现未按工艺生产可终止合同。"],
                risk_judgment=["监督与解除条件失衡。"],
                legal_basis=["违约处理应与过错程度相当。"],
                rectification=["压缩监督范围并增加整改程序。"],
                topics=["acceptance"],
                source_rules=["topic"],
            ),
        ],
        metadata={},
    )


def test_output_governance_objects_can_be_constructed() -> None:
    envelope = GovernanceClusterEnvelope(
        compare_source_bucket="formal_risks",
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
    assert len(governed.governed_candidates) == 3

    formal = next(item for item in governed.governed_candidates if item.decision.canonical_title == "将项目验收方案纳入评审因素，违反评审规则合规性要求")
    assert formal.identity.rule_id.startswith("compare::")
    assert formal.decision.canonical_title == "将项目验收方案纳入评审因素，违反评审规则合规性要求"
    assert not hasattr(formal.decision, "target_layer")

    pending = next(item for item in governed.governed_candidates if item.decision.canonical_title == "节能环保产品政策条款缺失")
    assert pending.extras["compare_source_bucket"] == "pending_review_items"

    excluded = next(item for item in governed.governed_candidates if item.decision.canonical_title == "验收时点约定缺失，导致验收流程不可操作")
    assert excluded.identity.rule_id

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
    assert final_output["governance"]["governed_candidates"][0]["identity"]["rule_id"].startswith("compare::")


def test_output_governance_rejects_topic_free_text_as_governed_object() -> None:
    try:
        _coerce_pending_or_excluded("仅凭 topic summary 直接冒充治理结果", "pending_review_items")
    except TypeError as exc:
        assert "structured dict items" in str(exc)
    else:
        raise AssertionError("expected TypeError for free-text governance input")


def test_output_governance_merges_duplicate_risk_families_without_deciding_layers() -> None:
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
    candidate_titles = [item.decision.canonical_title for item in governed.governed_candidates]

    assert candidate_titles.count("业绩评分限定特定行政区域，存在地域排斥风险") == 1
    assert candidate_titles.count("履约保证金比例严重超标") == 1
    assert "残疾人福利性单位及监狱企业政策表述不完整" in candidate_titles
    assert "社保缴纳证明要求存在例外情形，需关注执行一致性" in candidate_titles


def test_output_governance_real_file_replay_matches_og2_target_matrix() -> None:
    ns = runpy.run_path("tests/test_w002_real_file.py")
    saved_file, structure, baseline, topics = ns["_build_0330_result_topics"]()
    comparison = ns["compare_review_artifacts"](saved_file.name, baseline, topics)
    governed = govern_comparison_artifact(saved_file.name, comparison)

    candidate_titles = [item.decision.canonical_title for item in governed.governed_candidates]

    assert candidate_titles.count("业绩评分限定特定行政区域，存在地域排斥风险") == 1
    assert candidate_titles.count("验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险") == 1
    assert candidate_titles.count("履约保证金比例严重超标") == 1
    assert candidate_titles.count("项目负责人评分项设置过高且累计分值不合理，存在重复评价和倾向性风险") == 1
    assert candidate_titles.count("以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险") == 1
    assert "以特定认证证书作为高分条件，存在限定特定供应商和倾向性评分风险" not in candidate_titles
    assert "指定特定认证机构，具有排他性" not in candidate_titles
    assert "残疾人福利性单位及监狱企业政策表述不完整" in candidate_titles
    assert "节能环保产品政策条款缺失" in candidate_titles
    assert "社保缴纳证明要求存在例外情形，需关注执行一致性" in candidate_titles
    assert "采购文件澄清截止时间未明确填写" in candidate_titles
    assert "验收主体及流程描述不完整，缺乏不合格处理机制" in candidate_titles


def test_w014_output_governance_rewrites_titles_splits_standard_and_merges_clusters() -> None:
    comparison = _build_w014_governance_comparison()
    governed = govern_comparison_artifact("fuzhou-school-dorm.docx", comparison)

    candidate_titles = [item.decision.canonical_title for item in governed.governed_candidates]

    assert "商务条款中关于“无犯罪证明”的提交时限及无效投标处理存在法律风险" not in candidate_titles
    assert candidate_titles.count("样品要求过细且评审规则失衡，存在样品门槛风险") == 1
    assert candidate_titles.count("技术参数过细且特征化，存在指向性风险") == 1
    assert "技术参数存在错误或异常标准引用，可能导致技术要求失真" in candidate_titles
    assert "检测报告限定福建省检测机构，存在检测机构地域限制风险" in candidate_titles
    assert "履约监督与解除条件失衡" in candidate_titles
    assert "验收标准引用“厂家验收标准”及“样品”，存在模糊表述和单方裁量风险" in candidate_titles
    assert "技术参数引用错误标准及标准号存疑" not in candidate_titles


def test_output_governance_emits_single_candidate_stream_without_layer_semantics() -> None:
    governed = govern_comparison_artifact("sample.docx", _build_sample_comparison())
    payload = governed.to_dict()

    assert "governed_candidates" in payload
    assert "formal_risks" not in payload
    assert "pending_review_items" not in payload
    assert "excluded_risks" not in payload
    assert all("target_layer" not in item["decision"] for item in payload["governed_candidates"])
 

def test_output_governance_merges_same_family_candidates_without_layer_winner_selection() -> None:
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
    candidate_titles = [item.decision.canonical_title for item in governed.governed_candidates]
    candidate = governed.governed_candidates[0]
    assert candidate_titles == ["将项目验收方案纳入评审因素，违反评审规则合规性要求"]
    assert set(candidate.extras["compare_source_buckets"]) == {"formal_risks", "pending_review_items"}


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
    family_keys = [item["family"]["family_key"] for item in final_output["governance"]["governed_candidates"]]
    assert len(family_keys) == len(set(family_keys))


def test_build_v2_final_output_rejects_cross_layer_family_conflicts() -> None:
    comparison = _build_sample_comparison()
    governed = govern_comparison_artifact("sample.docx", comparison)
    duplicated = governed.governed_candidates[1]
    duplicated.family.family_key = governed.governed_candidates[0].family.family_key
    duplicated.family.canonical_title = governed.governed_candidates[0].family.canonical_title

    try:
        validate_governed_result(governed)
    except ValueError as exc:
        assert "duplicate governed families remain after governance" in str(exc)
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

    assert [item.decision.canonical_title for item in governed.governed_candidates] == ["缺失检测报告及认证资质要求"]


def test_output_governance_normalizes_missing_detection_report_blurry_title() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="missing-detection-blurry",
                title="检测报告及认证资质要求缺失或表述模糊",
                severity="中风险",
                review_type="检测认证要求审查",
                source_locations=["技术条款：设备验收"],
                source_excerpts=["未见关于第三方检测报告、CMA/CNAS 资质或 CCC 认证的具体条款。"],
                risk_judgment=["需人工确认验收章节是否补充了相关检测要求。"],
                topics=["technical_standard"],
                source_rules=["topic"],
            )
        ],
        metadata={},
    )

    governed = govern_comparison_artifact("diesel.docx", comparison)

    assert [item.decision.canonical_title for item in governed.governed_candidates] == [
        "检测报告及认证资质要求缺失或表述不明"
    ]


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

    blocked = next(item for item in governed.governed_candidates if item.decision.canonical_title == "缺失检测报告及认证资质要求")
    assert blocked.identity.rule_id == "topic::缺失检测报告及认证资质要求"


def test_output_governance_absorbs_certification_scoring_supporting_risks_into_single_main_risk() -> None:
    governed = govern_comparison_artifact("diesel.docx", _build_w012_cert_scoring_comparison())

    formal_titles = [item.decision.canonical_title for item in governed.governed_candidates]

    assert formal_titles.count("以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险") == 1
    assert "以特定认证证书作为高分条件，存在限定特定供应商和倾向性评分风险" not in formal_titles
    assert "评分标准中要求特定非强制性认证证书，具有倾向性" not in formal_titles
    assert "综合实力评分中三项体系认证要求过于刚性，可能排斥中小企业" not in formal_titles
    assert "指定特定认证机构，具有排他性" not in formal_titles


def test_output_governance_records_absorption_trace_for_certification_supporting_items() -> None:
    governed = govern_comparison_artifact("diesel.docx", _build_w012_cert_scoring_comparison())

    main = next(
        item
        for item in governed.governed_candidates
        if item.decision.canonical_title == "以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险"
    )
    absorbed = main.extras.get("absorbed_risks", [])
    absorbed_titles = {item["absorbed_title"] for item in absorbed}

    assert {
        "以特定认证证书作为高分条件，存在限定特定供应商和倾向性评分风险",
        "评分标准中要求特定非强制性认证证书，具有倾向性",
        "综合实力评分中三项体系认证要求过于刚性，可能排斥中小企业",
        "指定特定认证机构，具有排他性",
    } <= absorbed_titles
    assert all(item["blocked_from_formal"] is True for item in absorbed)
    assert all(item["absorbed_by_title"] == main.decision.canonical_title for item in absorbed)


def test_output_governance_records_absorption_trace_for_sample_cluster() -> None:
    governed = govern_comparison_artifact("fuzhou-school-dorm.docx", _build_w014_governance_comparison())

    sample = next(
        item
        for item in governed.governed_candidates
        if item.decision.canonical_title == "样品要求过细且评审规则失衡，存在样品门槛风险"
    )
    absorbed = sample.extras.get("absorbed_risks", [])
    absorbed_titles = {item["absorbed_title"] for item in absorbed}

    assert "样品隐去信息要求与评审需求存在逻辑矛盾" in absorbed_titles
    assert "商务条款中关于“无犯罪证明”的提交时限及无效投标处理存在法律风险" in absorbed_titles
    assert all(item["blocked_from_formal"] is True for item in absorbed)


def test_output_governance_normalizes_fuzhou_contract_and_technical_variant_titles() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="variant-contract",
                title="商务条款赋予采购人单方面变更权且结算方式不明",
                severity="中风险",
                review_type="商务条款失衡",
                source_locations=["商务条款 8.3、13.3"],
                source_excerpts=["采购人可单方面调整款式、尺寸、颜色，中标价不变。"],
                risk_judgment=["采购人单方面变更权过大，结算口径不清。"],
                legal_basis=["合同权利义务应保持公平。"],
                rectification=["补充价格调整和协商机制。"],
                topics=["baseline"],
                source_rules=["baseline"],
            ),
            MergedRiskCluster(
                cluster_id="variant-technical",
                title="技术参数中尺寸公差及材料要求过于具体，存在指向性嫌疑",
                severity="中风险",
                review_type="技术参数倾向性",
                source_locations=["技术参数 1-3"],
                source_excerpts=["尺寸、公差、材料厚度和连接件形态要求过细。"],
                risk_judgment=["尺寸公差和材料要求过于具体，容易指向特定产品。"],
                legal_basis=["技术参数不得指向特定供应商或产品。"],
                rectification=["改成功能性、通用性指标。"],
                topics=["baseline"],
                source_rules=["baseline"],
            ),
        ],
        metadata={},
    )

    governed = govern_comparison_artifact("fuzhou-school-dorm.docx", comparison)
    titles = {item.decision.canonical_title for item in governed.governed_candidates}

    assert "商务条款中采购人单方变更权过大且结算方式不明" in titles
    assert "技术参数过细且特征化，存在指向性风险" in titles
