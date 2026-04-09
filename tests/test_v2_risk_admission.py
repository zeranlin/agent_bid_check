from __future__ import annotations

import json
from pathlib import Path

from app.common.schemas import RiskPoint
from app.pipelines.v2.assembler import build_v2_final_output
from app.pipelines.v2.output_governance import govern_comparison_artifact
from app.pipelines.v2.risk_admission.evidence_classifier import infer_evidence_kind
from app.pipelines.v2.risk_admission import admit_governance_result, validate_admitted_result
from app.pipelines.v2.risk_admission.schemas import AdmissionCandidate, AdmissionDecision, AdmissionResult
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
                source_rules=["compare_rule:R-003"],
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
            ]
        },
    )


def _build_template_gate_comparison() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="cluster-template",
                title="验收标准模糊且依赖后续合同确定，存在需求条款合规风险",
                severity="高风险",
                review_type="条款明确性审查",
                source_locations=["证据 1（第 2621-2624 行）、证据 3（第 3111-3133 行）"],
                source_excerpts=[
                    "1、期次 1，说明：按招标文件及合同约定的服务要求执行验收... 分包合同标的... 质量要求和标准，验收... 待甲方中标（成交）后，根据甲方与采购人签订的总包合同确定具体的内容。"
                ],
                risk_judgment=["模板中的分包合同约定被直接抬成正式风险。"],
                legal_basis=["需进一步核实正文是否有独立验收依据。"],
                rectification=["模板类证据不得直接转正式风险。"],
                topics=["acceptance"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="cluster-body",
                title="评分标准中设置特定品牌倾向性条款",
                severity="高风险",
                review_type="评分因素合规性审查",
                source_locations=["评分条款：第三章 评分办法"],
                source_excerpts=["设备配置如果有华为小米等相关国产品牌优先。"],
                risk_judgment=["评分条款直接点名品牌。"],
                legal_basis=["评分因素不得限定特定品牌。"],
                rectification=["删除品牌倾向性表述。"],
                topics=["scoring"],
                source_rules=["topic"],
            ),
        ]
    )


def _build_reminder_gate_comparison() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="cluster-reminder-1",
                title="专门面向中小企业采购的评审细节需确认",
                severity="高风险",
                review_type="政策条款审查",
                source_locations=["评分条款：政策评分项"],
                source_excerpts=["针对专门面向中小企业采购的具体评审细节，需结合项目设置进一步确认。"],
                risk_judgment=["当前仅提示需确认评审细节，尚未形成稳定硬风险结论。"],
                legal_basis=["需结合项目实际设置进一步核实。"],
                rectification=["补充明确评审细则。"],
                topics=["policy"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="cluster-reminder-2",
                title="人员配置数量及证书要求需结合项目规模评估",
                severity="高风险",
                review_type="资格条件审查",
                source_locations=["资格条款：人员配置要求"],
                source_excerpts=["现有证据仅能看出人员配置要求偏强，需结合项目规模评估其必要性。"],
                risk_judgment=["当前证据不足以直接认定为正式风险。"],
                legal_basis=["建议结合项目规模和履约需求继续核实。"],
                rectification=["补充项目规模与人员需求说明。"],
                topics=["qualification"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="cluster-hard-1",
                title="评分标准中设置特定品牌倾向性条款",
                severity="高风险",
                review_type="评分因素合规性审查",
                source_locations=["评分条款：第三章 评分办法"],
                source_excerpts=["设备配置如果有华为小米等相关国产品牌优先。"],
                risk_judgment=["评分条款直接点名品牌。"],
                legal_basis=["评分因素不得限定特定品牌。"],
                rectification=["删除品牌倾向性表述。"],
                topics=["scoring"],
                source_rules=["topic"],
            ),
        ]
    )


def _build_w011_absorption_comparison() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="cluster-main",
                title="拒绝进口 vs 外标/国外部件引用矛盾风险",
                severity="中风险",
                review_type="采购政策/技术标准/验收口径一致性审查",
                source_locations=["技术条款：1.规格及技术参数"],
                source_excerpts=["外标引用：符合 BS EN 61000 GB/T 17626 及 EN55011 标准。"],
                risk_judgment=["主风险已经成立。"],
                legal_basis=["已结合规则库交叉校验与原文条款综合判断。"],
                rectification=["补充说明等效标准。"],
                topics=["technical_standard"],
                source_rules=["compare_rule:R-001"],
            ),
            MergedRiskCluster(
                cluster_id="cluster-support",
                title="电磁兼容标准引用格式混乱且编号不完整",
                severity="中风险",
                review_type="标准规范性审查",
                source_locations=["技术条款：1.规格及技术参数"],
                source_excerpts=["1.14 电磁影响：符合 BS EN 61000 GB/T 17626 及 EN55011 标准。"],
                risk_judgment=["该条更多是主风险的标准编号和格式佐证。"],
                legal_basis=["标准应明确具体。"],
                rectification=["修正标准编号。"],
                topics=["technical_standard"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="cluster-missing",
                title="检测报告及认证资质要求缺失或表述不明",
                severity="中风险",
                review_type="检测认证要求审查",
                source_locations=["技术条款：设备验收"],
                source_excerpts=["未见关于第三方检测报告、CMA/CNAS 资质或 CCC 认证的具体条款。"],
                risk_judgment=[
                    "文件仅要求符合相关标准，但未明确检测报告要求。",
                    "需人工确认验收章节是否补充了相关检测要求。",
                ],
                legal_basis=["需进一步核实。"],
                rectification=["补充明确检测要求。"],
                topics=["technical_standard"],
                source_rules=["topic"],
            ),
        ]
    )


def _build_w011_fujian_stability_comparison() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="cluster-info",
                title="评分标准中设置“信息化软件服务能力”要求，存在倾向性",
                severity="低风险",
                review_type="评分因素合规性审查",
                source_locations=["商务项 -> 信息化软件服务能力"],
                source_excerpts=["投标人须提供承诺函和著作权人为投标人的《计算机软件著作权登记证书》。"],
                risk_judgment=["当前标题过宽。"],
                legal_basis=["评分因素不得不当限制竞争。"],
                rectification=["调整评分条件。"],
                topics=["scoring"],
                source_rules=["baseline"],
            ),
            MergedRiskCluster(
                cluster_id="cluster-crime",
                title="评分标准中设置“无犯罪证明”作为中标后承诺，存在法律风险",
                severity="低风险",
                review_type="商务条款审查",
                source_locations=["商务项 -> 无犯罪证明承诺"],
                source_excerpts=["承诺在合同签订后的三个月内提供无犯罪证明，未提供的按无效投标处理。"],
                risk_judgment=["当前标题过宽。"],
                legal_basis=["法律风险已形成。"],
                rectification=["删除违法处置规则。"],
                topics=["contract_payment"],
                source_rules=["baseline"],
            ),
        ]
    )


def test_risk_admission_objects_can_be_constructed() -> None:
    decision = AdmissionDecision(
        target_layer="formal_risks",
        admission_reason="具备稳定规则来源和正文证据，可进入正式风险。",
        evidence_kind="scoring_clause",
        source_type="compare_rule",
    )
    candidate = AdmissionCandidate(
        rule_id="compare::R-003",
        title="将项目验收方案纳入评审因素，违反评审规则合规性要求",
        review_type="评分因素合规性审查",
        severity="高风险",
        evidence_kind="scoring_clause",
        source_type="compare_rule",
        source_locations=["评分条款：第二章 评审标准"],
        source_excerpts=["验收方案优的得满分。"],
        source_rules=["compare_rule:R-003"],
    )
    result = AdmissionResult(document_name="sample.docx", formal_risks=[candidate], decisions={"compare::R-003": decision})

    assert result.document_name == "sample.docx"
    assert result.formal_risks[0].evidence_kind == "scoring_clause"
    assert result.decisions["compare::R-003"].source_type == "compare_rule"


def test_infer_evidence_kind_recognizes_subcontract_template() -> None:
    evidence_kind = infer_evidence_kind(
        review_type="条款明确性审查",
        title="验收标准模糊且依赖后续合同确定，存在需求条款合规风险",
        source_locations=["证据 3（第 3111-3133 行）"],
        source_excerpts=["分包合同标的的质量要求和标准待甲方中标（成交）后，根据总包合同确定具体内容。"],
    )

    assert evidence_kind == "subcontract_template"


def test_risk_admission_is_unique_three_layer_exit() -> None:
    comparison = _build_sample_comparison()
    governance = govern_comparison_artifact("sample.docx", comparison)
    admission = admit_governance_result("sample.docx", comparison, governance)

    validate_admitted_result(admission)

    assert len(admission.formal_risks) == 1
    assert len(admission.pending_review_items) == 1
    assert admission.excluded_risks == []
    assert admission.decisions
    assert all(
        key in {"formal_risks", "pending_review_items", "excluded_risks"}
        for key in [decision.target_layer for decision in admission.decisions.values()]
    )


def test_subcontract_template_cannot_directly_support_formal_risk() -> None:
    comparison = _build_template_gate_comparison()
    governance = govern_comparison_artifact("fujian.docx", comparison)
    admission = admit_governance_result("fujian.docx", comparison, governance)

    template_titles = {item.title for item in admission.excluded_risks}
    formal_titles = {item.title for item in admission.formal_risks}

    assert "验收标准模糊且依赖后续合同确定，存在需求条款合规风险" in template_titles
    assert "验收标准模糊且依赖后续合同确定，存在需求条款合规风险" not in formal_titles
    assert (
        admission.decisions["topic::验收标准模糊且依赖后续合同确定-存在需求条款合规风险"].admission_reason
        == "检测到模板/协议/声明函类证据，且当前仅有专题推断支撑，不得直接作为正式风险主证据。"
    )


def test_body_clause_hard_risk_is_not_misclassified_as_template() -> None:
    comparison = _build_template_gate_comparison()
    governance = govern_comparison_artifact("fujian.docx", comparison)
    admission = admit_governance_result("fujian.docx", comparison, governance)

    formal_titles = {item.title for item in admission.formal_risks}
    body_item = next(item for item in admission.formal_risks if item.title == "评分标准中设置特定品牌倾向性条款")

    assert "评分标准中设置特定品牌倾向性条款" in formal_titles
    assert body_item.evidence_kind == "scoring_clause"


def test_reminder_items_are_downgraded_to_pending_review() -> None:
    comparison = _build_reminder_gate_comparison()
    governance = govern_comparison_artifact("sample.docx", comparison)
    admission = admit_governance_result("sample.docx", comparison, governance)

    pending_titles = {item.title for item in admission.pending_review_items}
    formal_titles = {item.title for item in admission.formal_risks}

    assert "专门面向中小企业采购的评审细节需确认" in pending_titles
    assert "人员配置数量及证书要求需结合项目规模评估" in pending_titles
    assert "评分标准中设置特定品牌倾向性条款" in formal_titles


def test_fujian_template_misreport_is_blocked_by_current_admission_rules() -> None:
    source = Path("data/results/v2/20260408-fujian-review-173153/comparison.json")
    payload = json.loads(source.read_text(encoding="utf-8"))
    comparison = ComparisonArtifact(
        clusters=[MergedRiskCluster(**cluster) for cluster in payload.get("clusters", [])],
        metadata=payload.get("metadata", {}),
    )

    governance = govern_comparison_artifact("fujian.docx", comparison)
    admission = admit_governance_result("fujian.docx", comparison, governance)

    formal_titles = {item.title for item in admission.formal_risks}
    excluded_titles = {item.title for item in admission.excluded_risks}

    assert "验收标准模糊且依赖后续合同确定，存在需求条款合规风险" in excluded_titles
    assert "验收标准模糊且依赖后续合同确定，存在需求条款合规风险" not in formal_titles
    assert "评分标准中设置特定品牌倾向性条款" in formal_titles
    assert "评分标准中“信息化软件服务能力”要求著作权人为投标人，可能限制竞争" in formal_titles
    assert "商务条款中关于“无犯罪证明”的提交时限及无效投标处理存在法律风险" in formal_titles


def test_missing_type_risk_is_downgraded_from_formal() -> None:
    comparison = _build_w011_absorption_comparison()
    governance = govern_comparison_artifact("diesel.docx", comparison)
    admission = admit_governance_result("diesel.docx", comparison, governance)

    assert "检测报告及认证资质要求缺失或表述不明" in {item.title for item in admission.pending_review_items}
    assert "检测报告及认证资质要求缺失或表述不明" not in {item.title for item in admission.formal_risks}


def test_supporting_standard_format_risk_is_absorbed_by_main_import_conflict() -> None:
    comparison = _build_w011_absorption_comparison()
    governance = govern_comparison_artifact("diesel.docx", comparison)
    admission = admit_governance_result("diesel.docx", comparison, governance)

    formal_titles = [item.title for item in admission.formal_risks]

    assert formal_titles.count("拒绝进口 vs 外标/国外部件引用矛盾风险") == 1
    assert "电磁兼容标准引用格式混乱且编号不完整" not in formal_titles


def test_fujian_titles_and_severity_are_stabilized() -> None:
    comparison = _build_w011_fujian_stability_comparison()
    governance = govern_comparison_artifact("fujian.docx", comparison)
    admission = admit_governance_result("fujian.docx", comparison, governance)
    final_output = build_v2_final_output(
        "fujian.docx",
        V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`fujian.docx`\n"),
        V2StageArtifact(name="structure", metadata={}),
        [],
        comparison=comparison,
        governance=governance,
        admission=admission,
    )

    formal_by_title = {item["title"]: item for item in final_output["formal_risks"]}

    assert "评分标准中“信息化软件服务能力”要求著作权人为投标人，可能限制竞争" in formal_by_title
    assert formal_by_title["评分标准中“信息化软件服务能力”要求著作权人为投标人，可能限制竞争"]["severity"] == "中风险"
    assert "商务条款中关于“无犯罪证明”的提交时限及无效投标处理存在法律风险" in formal_by_title
    assert formal_by_title["商务条款中关于“无犯罪证明”的提交时限及无效投标处理存在法律风险"]["severity"] == "中风险"


def test_assembler_consumes_risk_admission_output_only() -> None:
    comparison = _build_sample_comparison()
    governance = govern_comparison_artifact("sample.docx", comparison)
    admission = admit_governance_result("sample.docx", comparison, governance)

    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    structure = V2StageArtifact(name="structure", metadata={})
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题",
            risk_points=[
                RiskPoint(
                    title="旧专题自由文案",
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
    ]

    final_output = build_v2_final_output(
        "sample.docx",
        baseline,
        structure,
        topics,
        comparison=comparison,
        governance=governance,
        admission=admission,
    )

    assert final_output["formal_risks"][0]["title"] == "将项目验收方案纳入评审因素，违反评审规则合规性要求"
    assert final_output["pending_review_items"][0]["title"] == "节能环保产品政策条款缺失"
    assert final_output["risk_admission"]["formal_risks"][0]["title"] == "将项目验收方案纳入评审因素，违反评审规则合规性要求"
