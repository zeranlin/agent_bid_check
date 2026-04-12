from __future__ import annotations

import json
from pathlib import Path

from app.common.schemas import RiskPoint
from app.pipelines.v2.assembler import build_v2_final_output
from app.pipelines.v2.output_governance import govern_comparison_artifact
from app.pipelines.v2.problem_layer import build_problem_layer
from app.pipelines.v2.risk_admission.evidence_classifier import infer_evidence_kind
from app.pipelines.v2.risk_admission.formal_registry import (
    FormalRegistryEntry,
    FormalRegistryResolution,
    clear_formal_registry_cache,
    load_formal_registry_index,
)
from app.pipelines.v2.risk_admission import admit_governance_result, admit_problem_result, validate_admitted_result
from app.pipelines.v2.risk_admission.schemas import AdmissionCandidate, AdmissionDecision, AdmissionResult
from app.pipelines.v2.schemas import ComparisonArtifact, MergedRiskCluster, TopicReviewArtifact, V2StageArtifact


def _load_comparison_artifact(path: str | Path) -> ComparisonArtifact:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return ComparisonArtifact(
        signatures=[],
        clusters=[MergedRiskCluster(**item) for item in payload.get("clusters", [])],
        conflicts=list(payload.get("conflicts", [])),
        coverage_summary=dict(payload.get("coverage_summary", {})),
        comparison_summary=dict(payload.get("comparison_summary", {})),
        baseline_only_risks=list(payload.get("baseline_only_risks", [])),
        topic_only_risks=list(payload.get("topic_only_risks", [])),
        missing_topic_coverage=list(payload.get("missing_topic_coverage", [])),
        manual_review_items=list(payload.get("manual_review_items", [])),
        coverage_gaps=list(payload.get("coverage_gaps", [])),
        metadata=dict(payload.get("metadata", {})),
    )


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


def test_admission_consumes_problem_objects_instead_of_raw_governed_candidates() -> None:
    comparison = _build_sample_comparison()
    governance = govern_comparison_artifact("sample.docx", comparison)
    problems = build_problem_layer("sample.docx", governance)

    admission = admit_problem_result("sample.docx", comparison, problems, governance)

    assert admission.input_summary["problem_summary"]["problem_count"] == len(problems.problems)
    assert admission.input_summary["governance_summary"]["candidate_count"] == len(governance.governed_candidates)


def test_admission_preserves_conflict_problem_trace_and_absorbs_source_problems() -> None:
    comparison = _build_pb4_acceptance_conflict_for_admission()
    governance = govern_comparison_artifact("sample.docx", comparison)
    problems = build_problem_layer("sample.docx", governance)

    assert len(problems.problems) == 1
    assert problems.problems[0].problem_kind == "conflict"

    admission = admit_problem_result("sample.docx", comparison, problems, governance)

    assert len(admission.formal_risks) == 1
    assert admission.pending_review_items == []
    formal = admission.formal_risks[0]
    assert formal.extras["problem_kind"] == "conflict"
    assert formal.extras["conflict_type"] == "acceptance_plan_scoring_conflict"
    assert formal.extras["left_side"]["topic"] == "policy"
    assert formal.extras["right_side"]["topic"] == "scoring"
    assert formal.extras["final_problem_resolution"]["target_layer"] == "formal_risks"


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


def _build_w014_admission_comparison() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="prepayment",
                title="缺乏预付款安排，资金压力较大",
                severity="中风险",
                review_type="商务条款审查",
                source_locations=["商务条款 5.1"],
                source_excerpts=["本项目货到验收合格后一次性付款，未设置预付款。"],
                risk_judgment=["仅能看出未设预付款，不足以直接定性为正式合规风险。"],
                legal_basis=["预付款安排通常属交易结构选择。"],
                rectification=["可结合项目情况评估是否设置预付款。"],
                topics=["contract_payment"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="sign-default",
                title="开标记录签字确认的默认认可条款",
                severity="中风险",
                review_type="开标程序审查",
                source_locations=["开标须知"],
                source_excerpts=["投标人未签字确认开标记录的，视为认可开标结果。"],
                risk_judgment=["当前仅见默认认可表述，尚不足以构成正式风险。"],
                legal_basis=["需结合异议救济机制综合判断。"],
                rectification=["补充异议保留路径。"],
                topics=["opening"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="remote-opening-default",
                title="远程开标解密时限及后果条款的合理性审查",
                severity="中风险",
                review_type="开标程序审查",
                source_locations=["远程开标须知"],
                source_excerpts=["投标人应在30分钟内完成解密，未完成的视为撤销投标文件。"],
                risk_judgment=["当前仅见一般性解密时限及后果表述，仍需结合异常时长或异常后果判断。"],
                legal_basis=["需结合电子招投标通常安排进一步核实。"],
                rectification=["核查时限是否异常偏短、后果是否过重。"],
                topics=["opening"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="remote-opening-abnormal",
                title="远程开标解密时限及后果条款显失公平",
                severity="高风险",
                review_type="开标程序审查",
                source_locations=["远程开标须知"],
                source_excerpts=["投标人须在5分钟内完成解密，超时即按无效投标处理且不得提出异议。"],
                risk_judgment=["解密时限异常偏短，且直接按无效投标处理，后果明显过重。"],
                legal_basis=["开标程序安排不得设置明显失衡门槛。"],
                rectification=["合理延长解密时限并调整后果。"],
                topics=["opening"],
                source_rules=["compare_rule:R-OPEN"],
            ),
            MergedRiskCluster(
                cluster_id="contract-up",
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
                cluster_id="acceptance-up",
                title="验收标准引用“厂家验收标准”及“样品”，存在模糊表述和单方裁量风险",
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
                cluster_id="template-blank",
                title="验收时间条款留白，导致验收安排不明确",
                severity="中风险",
                review_type="合同模板边界审查",
                source_locations=["专用条款 12.1"],
                source_excerpts=["采购人应在货到后_______日内组织验收，具体时间按【专用条款】约定。"],
                risk_judgment=["明显属于模板留白。"],
                legal_basis=["模板占位不宜直接抬正式风险。"],
                rectification=["排除模板占位后再核查正文。"],
                topics=["acceptance"],
                source_rules=["topic"],
            ),
        ]
    )


def _build_pb4_acceptance_conflict_for_admission() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="pb4-acceptance-policy",
                title="评分规则明确不得将验收方案作为评审因素",
                severity="中风险",
                review_type="评分规则一致性审查",
                source_locations=["评分规则总则"],
                source_excerpts=["评审因素不得包含验收方案、付款方式等与评审无关内容。"],
                risk_judgment=["评分规则已明确禁止。"],
                legal_basis=["评审因素应与采购需求和履约相关。"],
                rectification=["保持评分规则与评分细则一致。"],
                topics=["policy"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="pb4-acceptance-scoring",
                title="将项目验收方案纳入评审因素，违反评审规则合规性要求",
                severity="高风险",
                review_type="评分因素合规性审查",
                source_locations=["评分细则：验收方案评分"],
                source_excerpts=["验收方案优的得满分。"],
                risk_judgment=["评分细则实际按验收方案打分。"],
                legal_basis=["评审因素应与采购需求和履约相关。"],
                rectification=["删除与验收方案直接挂钩的评分条件。"],
                topics=["scoring"],
                source_rules=["compare_rule:R-003"],
            ),
        ]
    )


def test_risk_admission_objects_can_be_constructed() -> None:
    decision = AdmissionDecision(
        target_layer="formal_risks",
        admission_reason="具备稳定规则来源和正文证据，可进入正式风险。",
        evidence_kind="scoring_clause",
        source_type="compare_rule",
        formal_gate_passed=True,
        formal_gate_reason="命中 formal 白名单，且存在正文硬证据。",
        formal_gate_rule="formal_whitelist",
        formal_gate_exception_whitelist_hit=True,
        formal_gate_family_allowed=True,
        formal_gate_evidence_passed=True,
    )
    candidate = AdmissionCandidate(
        rule_id="compare::R-003",
        risk_family="acceptance_scheme_scoring",
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
    assert result.decisions["compare::R-003"].formal_gate_passed is True
    assert result.decisions["compare::R-003"].formal_gate_family_allowed is True
    assert result.decisions["compare::R-003"].formal_gate_evidence_passed is True


def test_formal_gate_trace_fields_exist_for_formal_output() -> None:
    comparison = _build_sample_comparison()
    governance = govern_comparison_artifact("sample.docx", comparison)
    admission = admit_governance_result("sample.docx", comparison, governance)

    decision = admission.decisions["R-003"]

    assert decision.target_layer == "formal_risks"
    assert decision.formal_gate_passed is True
    assert decision.formal_gate_reason
    assert decision.formal_gate_rule
    assert decision.formal_gate_exception_whitelist_hit in {True, False}
    assert decision.formal_gate_family_allowed in {True, False}
    assert decision.formal_gate_evidence_passed in {True, False}
    assert decision.formal_gate_registry_resolution in {"matched", "missing", "mismatch"}
    assert decision.technical_layer_decision in {"formal_risks", "pending_review_items", "excluded_risks"}
    assert decision.user_visible_gate_passed in {True, False}
    assert decision.user_visible_gate_reason
    assert decision.user_visible_gate_rule
    assert decision.evidence_sufficiency in {"sufficient", "insufficient", "missing_user_visible_evidence"}
    assert decision.user_visible_decision_basis


def test_formal_registry_index_after_q7_uses_registry_as_runtime_single_source() -> None:
    clear_formal_registry_cache()
    index = load_formal_registry_index()

    import_entry = index.by_family_key["import_consistency"]
    regional_entry = index.by_family_key["regional_performance"]

    assert import_entry.rule_id == "R-001"
    assert import_entry.source == "registry"
    assert import_entry.allow_formal is True
    assert regional_entry.rule_id == "GOV-regional_performance"
    assert regional_entry.source == "registry"
    assert regional_entry.allow_formal is True
    assert "R-001" in index.by_rule_id
    assert "GOV-software_copyright_competition" not in index.by_rule_id


def test_formal_registry_index_uses_registry_as_primary_source_for_formal_rules() -> None:
    clear_formal_registry_cache()
    index = load_formal_registry_index()

    assert index.by_rule_id["R-001"].family_key == "import_consistency"
    assert index.by_rule_id["R-001"].canonical_title == "拒绝进口 vs 外标/国外部件引用矛盾风险"
    assert index.by_rule_id["R-001"].source == "registry"
    assert "GOV-regional_performance" in index.by_rule_id


def test_formal_registry_index_prefers_registry_for_migrated_governance_formal_items() -> None:
    clear_formal_registry_cache()
    index = load_formal_registry_index()

    sample_entry = index.by_rule_id["GOV-sample_gate"]
    tech_entry = index.by_rule_id["GOV-technical_over_specific"]

    assert sample_entry.source == "registry"
    assert sample_entry.family_key == "sample_gate"
    assert tech_entry.source == "registry"
    assert tech_entry.canonical_title == "技术参数过细且特征化，存在指向性风险"


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
    assert governance.governed_candidates
    assert len(governance.governed_candidates) == (
        len(admission.formal_risks) + len(admission.pending_review_items) + len(admission.excluded_risks)
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
    assert (
        admission.decisions["topic::验收标准模糊且依赖后续合同确定-存在需求条款合规风险"].formal_gate_rule
        == "downgrade_template_or_boundary"
    )


def test_body_clause_hard_risk_is_not_misclassified_as_template() -> None:
    comparison = _build_template_gate_comparison()
    governance = govern_comparison_artifact("fujian.docx", comparison)
    admission = admit_governance_result("fujian.docx", comparison, governance)

    formal_titles = {item.title for item in admission.formal_risks}
    pending_titles = {item.title for item in admission.pending_review_items}
    body_item = next(item for item in admission.pending_review_items if item.title == "评分标准中设置特定品牌倾向性条款")
    body_decision = admission.decisions[body_item.rule_id]

    assert "评分标准中设置特定品牌倾向性条款" not in formal_titles
    assert "评分标准中设置特定品牌倾向性条款" in pending_titles
    assert body_item.evidence_kind == "scoring_clause"
    assert body_decision.formal_gate_rule == "registry_mapping_missing_block"


def test_reminder_items_are_downgraded_to_pending_review() -> None:
    comparison = _build_reminder_gate_comparison()
    governance = govern_comparison_artifact("sample.docx", comparison)
    admission = admit_governance_result("sample.docx", comparison, governance)

    pending_titles = {item.title for item in admission.pending_review_items}
    formal_titles = {item.title for item in admission.formal_risks}

    assert "专门面向中小企业采购的评审细节需确认" in pending_titles
    assert "人员配置数量及证书要求需结合项目规模评估" in pending_titles
    assert "评分标准中设置特定品牌倾向性条款" not in formal_titles
    assert "评分标准中设置特定品牌倾向性条款" in pending_titles


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
    pending_titles = {item.title for item in admission.pending_review_items}

    assert "验收标准模糊且依赖后续合同确定，存在需求条款合规风险" in excluded_titles
    assert "验收标准模糊且依赖后续合同确定，存在需求条款合规风险" not in formal_titles
    assert "评分标准中设置特定品牌倾向性条款" in pending_titles
    assert "评分标准中“信息化软件服务能力”要求著作权人为投标人，可能限制竞争" not in formal_titles
    assert (
        "评分标准中“信息化软件服务能力”要求著作权人为投标人，可能限制竞争" in pending_titles
        or "评分标准中“信息化软件服务能力”要求著作权人为投标人，可能限制竞争" in excluded_titles
    )
    assert "商务条款中关于“无犯罪证明”的提交时限及无效投标处理存在法律风险" not in formal_titles
    assert (
        "商务条款中关于“无犯罪证明”的提交时限及无效投标处理存在法律风险" in pending_titles
        or "商务条款中关于“无犯罪证明”的提交时限及无效投标处理存在法律风险" in excluded_titles
    )


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


def test_formal_gate_order_blocks_history_before_whitelist() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="blocked-1",
                title="缺失检测报告及认证资质要求",
                severity="高风险",
                review_type="检测认证要求审查",
                source_locations=["技术条款：设备验收"],
                source_excerpts=["技术参数引用了多项标准，但未说明检测报告。"],
                risk_judgment=["仅由专题推断抬起。"],
                topics=["technical_standard"],
                source_rules=["compare_rule:R-FAKE"],
            )
        ],
        metadata={},
    )

    governance = govern_comparison_artifact("diesel.docx", comparison)
    admission = admit_governance_result("diesel.docx", comparison, governance)
    decision = next(iter(admission.decisions.values()))

    assert admission.formal_risks == []
    assert [item.title for item in admission.excluded_risks] == ["缺失检测报告及认证资质要求"]
    assert decision.formal_gate_passed is False
    assert decision.formal_gate_rule == "historical_hard_block"


def test_formal_gate_order_applies_downgrade_before_whitelist() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="template-whitelist",
                title="评分标准中“信息化软件服务能力”要求著作权人为投标人，可能限制竞争",
                severity="中风险",
                review_type="条款明确性审查",
                source_locations=["证据 3（第 3111-3133 行）"],
                source_excerpts=["分包合同标的的质量要求和标准待甲方中标（成交）后，根据总包合同确定具体内容。"],
                risk_judgment=["当前仅见模板中的信息化能力要求。"],
                topics=["scoring"],
                source_rules=["topic"],
            )
        ],
        metadata={},
    )

    governance = govern_comparison_artifact("fujian.docx", comparison)
    admission = admit_governance_result("fujian.docx", comparison, governance)
    decision = next(iter(admission.decisions.values()))

    assert admission.formal_risks == []
    assert [item.title for item in admission.excluded_risks] == ["评分标准中“信息化软件服务能力”要求著作权人为投标人，可能限制竞争"]
    assert decision.formal_gate_passed is False
    assert decision.formal_gate_rule == "downgrade_template_or_boundary"
    assert decision.formal_gate_exception_whitelist_hit is False


def test_formal_gate_no_longer_uses_whitelist_as_runtime_source_for_software_copyright_case() -> None:
    comparison = _build_w011_fujian_stability_comparison()
    governance = govern_comparison_artifact("fujian.docx", comparison)
    admission = admit_governance_result("fujian.docx", comparison, governance)

    decision = admission.decisions["topic::software_copyright_competition"]

    assert "评分标准中“信息化软件服务能力”要求著作权人为投标人，可能限制竞争" not in {
        item.title for item in admission.formal_risks
    }
    assert "评分标准中“信息化软件服务能力”要求著作权人为投标人，可能限制竞争" in {
        item.title for item in admission.pending_review_items
    }
    assert decision.formal_gate_passed is False
    assert decision.formal_gate_rule == "registry_mapping_missing_block"
    assert decision.formal_gate_exception_whitelist_hit is False


def test_formal_gate_blocks_absorbed_supporting_item_before_formal_admission() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="support-only",
                title="电磁兼容标准引用格式混乱且编号不完整",
                severity="中风险",
                review_type="标准规范性审查",
                source_locations=["技术条款：1.规格及技术参数"],
                source_excerpts=["1.14 电磁影响：符合 BS EN 61000 GB/T 17626 及 EN55011 标准。"],
                risk_judgment=["该条更多是主风险的标准编号和格式佐证。"],
                topics=["technical_standard"],
                source_rules=["topic"],
            )
        ],
        metadata={},
    )

    governance = govern_comparison_artifact("diesel.docx", comparison)
    admission = admit_governance_result("diesel.docx", comparison, governance)
    decision = next(iter(admission.decisions.values()))

    assert admission.formal_risks == []
    assert [item.title for item in admission.excluded_risks] == ["拒绝进口 vs 外标/国外部件引用矛盾风险"]
    assert decision.formal_gate_passed is False
    assert decision.formal_gate_rule == "absorbed_supporting_item_block"


def test_formal_gate_demotes_unstable_family_even_with_body_evidence() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="unstable-family-hard-evidence",
                title="要求现场技术人员必须为制造商原厂工程师，存在排斥代理商风险",
                severity="中风险",
                review_type="资格条件审查",
                source_locations=["资格条款：技术服务团队"],
                source_excerpts=["投标人须承诺派驻至少2名制造商原厂工程师常驻现场。"],
                risk_judgment=["条款正文明确，但当前规则家族尚未纳入稳定 formal 范围。"],
                legal_basis=["需结合规则纳管状态继续复核。"],
                rectification=["补充履约必要性说明。"],
                topics=["qualification"],
                source_rules=["topic"],
            )
        ],
        metadata={},
    )

    governance = govern_comparison_artifact("diesel.docx", comparison)
    admission = admit_governance_result("diesel.docx", comparison, governance)
    decision = next(iter(admission.decisions.values()))

    assert admission.formal_risks == []
    assert [item.title for item in admission.pending_review_items] == ["要求现场技术人员必须为制造商原厂工程师，存在排斥代理商风险"]
    assert decision.formal_gate_passed is False
    assert decision.formal_gate_family_allowed is False
    assert decision.formal_gate_evidence_passed is True
    assert decision.formal_gate_rule == "registry_mapping_missing_block"
    assert decision.formal_gate_registry_resolution == "missing"


def test_formal_gate_allows_stable_family_with_body_evidence() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="stable-family-hard-evidence",
                title="验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险",
                severity="高风险",
                review_type="商务条款审查",
                source_locations=["商务条款：报价要求"],
                source_excerpts=["投标总价应包含项目验收、检测及相关部门验收等全部费用。"],
                risk_judgment=["费用边界与转嫁风险已在正文明确出现。"],
                legal_basis=["不得将本应由采购人承担的法定职责费用转嫁供应商。"],
                rectification=["明确费用承担边界。"],
                topics=["contract_payment"],
                source_rules=["compare_rule:R-COST"],
            )
        ],
        metadata={},
    )

    governance = govern_comparison_artifact("diesel.docx", comparison)
    admission = admit_governance_result("diesel.docx", comparison, governance)
    decision = next(iter(admission.decisions.values()))

    assert [item.title for item in admission.formal_risks] == ["验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险"]
    assert decision.formal_gate_passed is True
    assert decision.formal_gate_family_allowed is True
    assert decision.formal_gate_evidence_passed is True
    assert decision.formal_gate_rule == "registry_family_hard_evidence_gate"
    assert decision.formal_gate_registry_rule_id == "R-007"
    assert decision.formal_gate_registry_status == "active"
    assert decision.formal_gate_registry_source == "registry"
    assert decision.formal_gate_registry_resolution == "matched"


def test_formal_gate_blocks_when_registry_mapping_missing_even_with_body_evidence(monkeypatch) -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="registry-missing-hard-evidence",
                title="验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险",
                severity="高风险",
                review_type="商务条款审查",
                source_locations=["商务条款：报价要求"],
                source_excerpts=["投标总价应包含项目验收、检测及相关部门验收等全部费用。"],
                risk_judgment=["费用边界与转嫁风险已在正文明确出现。"],
                legal_basis=["不得将本应由采购人承担的法定职责费用转嫁供应商。"],
                rectification=["明确费用承担边界。"],
                topics=["contract_payment"],
                source_rules=["compare_rule:R-COST"],
            )
        ],
        metadata={},
    )

    def _fake_missing_resolution(**_: object) -> FormalRegistryResolution:
        return FormalRegistryResolution(
            outcome="missing",
            reason="未找到 family_key / rule_id 对应的 formal registry 配置。",
            entry=None,
        )

    monkeypatch.setattr(
        "app.pipelines.v2.risk_admission.formal_gate.resolve_formal_registry_resolution",
        _fake_missing_resolution,
    )

    governance = govern_comparison_artifact("diesel.docx", comparison)
    admission = admit_governance_result("diesel.docx", comparison, governance)
    decision = next(iter(admission.decisions.values()))

    assert admission.formal_risks == []
    assert admission.pending_review_items == []
    assert [item.title for item in admission.excluded_risks] == ["验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险"]
    assert decision.formal_gate_passed is False
    assert decision.formal_gate_rule == "registry_mapping_missing_block"
    assert decision.formal_gate_registry_resolution == "missing"
    assert decision.formal_gate_registry_rule_id == ""
    assert decision.formal_gate_family_allowed is False
    assert decision.formal_gate_evidence_passed is True
    assert decision.technical_layer_decision == "pending_review_items"
    assert decision.user_visible_gate_passed is False
    assert decision.user_visible_gate_rule == "internal_governance_signal"
    assert decision.user_visible_gate_reason == "当前仅命中内部治理信号，未形成可直接对外展示的用户结果。"


def test_formal_gate_blocks_inactive_registry_rule_even_with_body_evidence(monkeypatch) -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="registry-inactive-hard-evidence",
                title="验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险",
                severity="高风险",
                review_type="商务条款审查",
                source_locations=["商务条款：报价要求"],
                source_excerpts=["投标总价应包含项目验收、检测及相关部门验收等全部费用。"],
                risk_judgment=["费用边界与转嫁风险已在正文明确出现。"],
                legal_basis=["不得将本应由采购人承担的法定职责费用转嫁供应商。"],
                rectification=["明确费用承担边界。"],
                topics=["contract_payment"],
                source_rules=["compare_rule:R-COST"],
            )
        ],
        metadata={},
    )

    def _fake_inactive_resolution(**_: object) -> FormalRegistryResolution:
        return FormalRegistryResolution(
            outcome="matched",
            reason="命中 formal registry，但对应规则当前未正式纳管。",
            entry=FormalRegistryEntry(
                rule_id="R-007",
                family_key="acceptance_testing_cost",
                canonical_title="验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险",
                status="review",
                source="registry",
                allow_formal=False,
                requires_hard_evidence=True,
            ),
        )

    monkeypatch.setattr(
        "app.pipelines.v2.risk_admission.formal_gate.resolve_formal_registry_resolution",
        _fake_inactive_resolution,
    )

    governance = govern_comparison_artifact("diesel.docx", comparison)
    admission = admit_governance_result("diesel.docx", comparison, governance)
    decision = next(iter(admission.decisions.values()))

    assert admission.formal_risks == []
    assert [item.title for item in admission.pending_review_items] == ["验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险"]
    assert decision.formal_gate_passed is False
    assert decision.formal_gate_rule == "registry_inactive_block"
    assert decision.formal_gate_registry_rule_id == "R-007"
    assert decision.formal_gate_registry_status == "review"
    assert decision.formal_gate_registry_source == "registry"
    assert decision.formal_gate_registry_resolution == "matched"


def test_pending_gate_absorbs_same_family_pending_when_formal_primary_exists() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="acceptance-cost-formal",
                title="验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险",
                severity="高风险",
                review_type="商务条款审查",
                source_locations=["商务条款：报价要求"],
                source_excerpts=["投标总价应包含项目验收、检测及相关部门验收等全部费用。"],
                risk_judgment=["正文已明确出现费用承担安排。"],
                legal_basis=["不得将应由采购人承担的费用不当转嫁供应商。"],
                rectification=["明确费用边界。"],
                topics=["contract_payment"],
                source_rules=["compare_rule:R-COST"],
            ),
            MergedRiskCluster(
                cluster_id="acceptance-cost-pending",
                title="将验收产生的检测费用计入投标人承担范围，存在需求条款合规风险",
                severity="中风险",
                review_type="需求条款审查",
                source_locations=["采购需求：验收要求"],
                source_excerpts=["验收、检测等费用由中标人承担。"],
                risk_judgment=["同一家族中的附属说明不应再并列对外展示。"],
                legal_basis=["采购需求不得转嫁不合理费用负担。"],
                rectification=["删除转嫁费用表述。"],
                topics=["acceptance"],
                source_rules=["topic"],
            ),
        ],
        metadata={
            "pending_review_items": [
                {
                    "title": "将验收产生的检测费用计入投标人承担范围，存在需求条款合规风险",
                    "severity": "需人工复核",
                    "review_type": "需求条款审查",
                    "topic": "验收条款",
                    "source_location": "采购需求：验收要求",
                    "source_excerpt": "验收、检测等费用由中标人承担。",
                    "reason": "当前为待补证复核输出。",
                }
            ]
        },
    )
    governance = govern_comparison_artifact("fuzhou-school-dorm.docx", comparison)
    problems = build_problem_layer("fuzhou-school-dorm.docx", governance)

    admission = admit_problem_result("fuzhou-school-dorm.docx", comparison, problems, governance)

    assert [item.title for item in admission.formal_risks] == ["验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险"]
    assert admission.pending_review_items == []
    formal = admission.formal_risks[0]
    assert formal.extras["problem_trace"]["absorbed_user_visible_items"][0]["title"] == "将验收产生的检测费用计入投标人承担范围，存在需求条款合规风险"
    assert formal.extras["problem_trace"]["absorbed_user_visible_items"][0]["hidden_reason"] == "same_family_absorbed_by_formal_primary"


def test_pending_gate_drops_weak_signal_without_rule_support_from_user_visible_pending() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="weak-pending-no-rule",
                title="政策依据引用不完整，存在表述截断风险",
                severity="中风险",
                review_type="政策条款审查",
                source_locations=["政策章节"],
                source_excerpts=["上述政策依据后续内容未完整展示，需进一步确认。"],
                risk_judgment=["当前仅提示政策依据可能不完整。"],
                legal_basis=["需结合完整政策条文进一步核实。"],
                rectification=["补充完整政策依据。"],
                topics=["policy"],
                source_rules=["topic"],
            )
        ],
        metadata={},
    )
    governance = govern_comparison_artifact("fuzhou-school-dorm.docx", comparison)
    problems = build_problem_layer("fuzhou-school-dorm.docx", governance)

    admission = admit_problem_result("fuzhou-school-dorm.docx", comparison, problems, governance)

    assert admission.pending_review_items == []
    assert [item.title for item in admission.excluded_risks] == ["政策依据引用不完整，存在表述截断风险"]
    decision = next(iter(admission.decisions.values()))
    assert decision.pending_gate_reason_code == "weak_signal_no_rule_support"
    assert decision.technical_layer_decision == "pending_review_items"
    assert decision.user_visible_gate_passed is False
    assert decision.user_visible_gate_rule == "weak_signal_no_rule_support"
    assert decision.evidence_sufficiency == "insufficient"


def test_pending_gate_drops_weak_signal_without_material_consequence_from_user_visible_pending() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="weak-pending-no-consequence",
                title="节能环保政策具体适用要求缺失",
                severity="中风险",
                review_type="政策条款审查",
                source_locations=["政策章节"],
                source_excerpts=["节能环保政策条款未写明具体适用要求，建议结合项目进一步确认。"],
                risk_judgment=["当前仅提示存在适用要求缺口，未见明确合规后果。"],
                legal_basis=["需结合采购标的与适用政策进一步核实。"],
                rectification=["补充适用要求说明。"],
                topics=["policy"],
                source_rules=["topic"],
            )
        ],
        metadata={},
    )
    governance = govern_comparison_artifact("fuzhou-school-dorm.docx", comparison)
    problems = build_problem_layer("fuzhou-school-dorm.docx", governance)

    admission = admit_problem_result("fuzhou-school-dorm.docx", comparison, problems, governance)

    assert admission.pending_review_items == []
    assert [item.title for item in admission.excluded_risks] == ["节能环保政策具体适用要求缺失"]
    decision = next(iter(admission.decisions.values()))
    assert decision.pending_gate_reason_code == "weak_signal_no_material_consequence"
    assert decision.technical_layer_decision == "pending_review_items"
    assert decision.user_visible_gate_passed is False
    assert decision.user_visible_gate_rule == "weak_signal_no_material_consequence"


def test_pending_gate_drops_fuzhou_energy_policy_hint_from_user_visible_pending() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="fuzhou-energy-policy-hint",
                title="节能环保政策具体适用要求缺失",
                severity="中风险",
                review_type="政策条款审查",
                source_locations=["证据2，第 473 - 505 行，八、政府采购政策，17.2 条款"],
                source_excerpts=["政府采购节能产品、环境标志产品实施品目清单管理...依据品目清单和认证证书实施政府优先采购或强制采购。"],
                risk_judgment=["当前仅提示节能环保政策适用要求缺口，未形成明确合规后果。"],
                legal_basis=["需结合采购标的与适用政策进一步核实。"],
                rectification=["补充适用要求说明。"],
                topics=["policy"],
                source_rules=["baseline"],
            )
        ],
        metadata={},
    )
    governance = govern_comparison_artifact("fuzhou-school-dorm.docx", comparison)
    problems = build_problem_layer("fuzhou-school-dorm.docx", governance)

    admission = admit_problem_result("fuzhou-school-dorm.docx", comparison, problems, governance)

    assert admission.pending_review_items == []
    assert [item.title for item in admission.excluded_risks] == ["节能环保政策具体适用要求缺失"]
    decision = next(iter(admission.decisions.values()))
    assert decision.pending_gate_reason_code == "weak_signal_no_material_consequence"


def test_pending_gate_blocks_missing_user_visible_evidence() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="missing-visible-evidence",
                title="违约责任及质保期条款缺失",
                severity="中风险",
                review_type="商务条款审查",
                source_locations=["未在当前证据片段中找到"],
                source_excerpts=["无"],
                risk_judgment=["当前仅能推测章节可能缺失。"],
                legal_basis=["需结合完整合同条款继续核实。"],
                rectification=["补充违约责任及质保期条款。"],
                topics=["contract_payment"],
                source_rules=["topic"],
            )
        ],
        metadata={},
    )
    governance = govern_comparison_artifact("fuzhou-school-dorm.docx", comparison)
    problems = build_problem_layer("fuzhou-school-dorm.docx", governance)

    admission = admit_problem_result("fuzhou-school-dorm.docx", comparison, problems, governance)

    assert admission.pending_review_items == []
    assert [item.title for item in admission.excluded_risks] == ["违约责任及质保期条款缺失"]
    decision = next(iter(admission.decisions.values()))
    assert decision.pending_gate_reason_code == "missing_user_visible_evidence"
    assert decision.technical_layer_decision == "pending_review_items"
    assert decision.user_visible_gate_passed is False
    assert decision.user_visible_gate_rule == "missing_user_visible_evidence"
    assert decision.evidence_sufficiency == "missing_user_visible_evidence"


def test_user_visible_gate_keeps_material_pending_with_trace() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="material-pending",
                title="检测报告及认证资质要求缺失或表述不明",
                severity="中风险",
                review_type="检测认证要求审查",
                source_locations=["技术条款：设备验收"],
                source_excerpts=["未见关于第三方检测报告、CMA/CNAS 资质或 CCC 认证的具体条款。"],
                risk_judgment=["文件仅要求符合相关标准，但未明确检测报告要求。", "需人工确认验收章节是否补充了相关检测要求。"],
                legal_basis=["需进一步核实。"],
                rectification=["补充明确检测要求。"],
                topics=["technical_standard"],
                source_rules=["topic"],
            )
        ],
        metadata={},
    )
    governance = govern_comparison_artifact("diesel.docx", comparison)
    problems = build_problem_layer("diesel.docx", governance)

    admission = admit_problem_result("diesel.docx", comparison, problems, governance)

    assert [item.title for item in admission.pending_review_items] == ["检测报告及认证资质要求缺失或表述不明"]
    decision = next(iter(admission.decisions.values()))
    assert decision.technical_layer_decision == "pending_review_items"
    assert decision.user_visible_gate_passed is True
    assert decision.user_visible_gate_rule == "pending_material_issue_allowed"
    assert decision.evidence_sufficiency == "sufficient"
    assert decision.user_visible_decision_basis


def test_formal_gate_whitelist_can_survive_weak_source_downgrade_rules() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="whitelist-acceptance-hard-risk",
                title="验收标准引用‘厂家验收标准’导致依据模糊",
                severity="中风险",
                review_type="验收标准明确性审查",
                source_locations=["验收条款"],
                source_excerpts=["按厂家验收标准、招标文件、投标文件及中标人在投标文件中所提供的样品要求等有关内容进行验收。"],
                risk_judgment=["厂家验收标准与样品共同作为验收依据，裁量空间过大。"],
                legal_basis=["验收标准应统一明确。"],
                rectification=["删除厂家标准并固化验收标准。"],
                topics=["acceptance"],
                source_rules=["topic"],
            )
        ],
        metadata={},
    )

    governance = govern_comparison_artifact("fuzhou-school-dorm.docx", comparison)
    admission = admit_governance_result("fuzhou-school-dorm.docx", comparison, governance)
    decision = next(iter(admission.decisions.values()))

    assert [item.title for item in admission.formal_risks] == ["验收标准引用“厂家验收标准”及“样品”，存在模糊表述和单方裁量风险"]
    assert decision.formal_gate_passed is True
    assert decision.formal_gate_exception_whitelist_hit is True
    assert decision.formal_gate_rule == "formal_whitelist"


def test_formal_gate_whitelist_accepts_fuzhou_contract_variant_title() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="whitelist-contract-variant",
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
            )
        ],
        metadata={},
    )

    governance = govern_comparison_artifact("fuzhou-school-dorm.docx", comparison)
    admission = admit_governance_result("fuzhou-school-dorm.docx", comparison, governance)
    decision = next(iter(admission.decisions.values()))

    assert [item.title for item in admission.formal_risks] == ["商务条款中采购人单方变更权过大且结算方式不明"]
    assert decision.formal_gate_passed is True
    assert decision.formal_gate_exception_whitelist_hit is True
    assert decision.formal_gate_rule == "formal_whitelist"


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

    assert "评分标准中“信息化软件服务能力”要求著作权人为投标人，可能限制竞争" not in formal_by_title
    assert "商务条款中关于“无犯罪证明”的提交时限及无效投标处理存在法律风险" not in formal_by_title
    pending_titles = {item["title"] for item in final_output["pending_review_items"]}
    assert "评分标准中“信息化软件服务能力”要求著作权人为投标人，可能限制竞争" in pending_titles
    assert "商务条款中关于“无犯罪证明”的提交时限及无效投标处理存在法律风险" in pending_titles


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
    assert "governed_candidates" in final_output["governance"]
    assert "formal_risks" not in final_output["governance"]


def test_w014_risk_admission_demotes_wrong_layer_items_and_promotes_real_hard_risks() -> None:
    comparison = _build_w014_admission_comparison()
    governance = govern_comparison_artifact("fuzhou-school-dorm.docx", comparison)
    admission = admit_governance_result("fuzhou-school-dorm.docx", comparison, governance)

    formal_titles = {item.title for item in admission.formal_risks}
    pending_titles = {item.title for item in admission.pending_review_items}
    excluded_titles = {item.title for item in admission.excluded_risks}

    assert "商务条款中采购人单方变更权过大且结算方式不明" in formal_titles
    assert "验收标准引用“厂家验收标准”及“样品”，存在模糊表述和单方裁量风险" in formal_titles
    assert "缺乏预付款安排，资金压力较大" not in formal_titles
    assert "开标记录签字确认的默认认可条款" not in formal_titles
    assert "远程开标解密时限及后果条款的合理性审查" not in formal_titles
    assert "缺乏预付款安排，资金压力较大" in pending_titles or "缺乏预付款安排，资金压力较大" in excluded_titles
    assert "开标记录签字确认的默认认可条款" in excluded_titles
    assert "远程开标解密时限及后果条款的合理性审查" in pending_titles
    assert "远程开标解密时限及后果条款显失公平" not in formal_titles
    assert "远程开标解密时限及后果条款显失公平" in pending_titles
    assert "验收时间条款留白，导致验收安排不明确" in excluded_titles


def test_risk_admission_can_promote_candidate_without_governance_layer_hint() -> None:
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

    governance = govern_comparison_artifact("sample.docx", comparison)
    admission = admit_governance_result("sample.docx", comparison, governance)

    assert [item.title for item in admission.formal_risks] == ["将项目验收方案纳入评审因素，违反评审规则合规性要求"]
    assert admission.pending_review_items == []


def test_risk_admission_can_demote_candidate_without_governance_layer_hint() -> None:
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

    governance = govern_comparison_artifact("sample.docx", comparison)
    admission = admit_governance_result("sample.docx", comparison, governance)

    assert [item.title for item in admission.excluded_risks] == ["社保缴纳证明要求存在例外情形，需关注执行一致性"]
    assert admission.formal_risks == []


def test_risk_admission_handles_cross_candidate_conflict_without_governance_layer_bucket() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="same-family-formal",
                title="履约保证金比例过高，加重供应商负担",
                severity="高风险",
                review_type="合规性审查",
                source_locations=["商务条款A"],
                source_excerpts=["履约保证金为合同金额的12%。"],
                topics=["contract_payment"],
                source_rules=["compare_rule:R-005"],
            ),
            MergedRiskCluster(
                cluster_id="same-family-reminder",
                title="履约保证金比例严重超标，需结合项目情况进一步核实",
                severity="中风险",
                review_type="合规性审查",
                source_locations=["商务条款B"],
                source_excerpts=["履约保证金12%，但仍建议结合项目情况核实。"],
                risk_judgment=["当前表述带有需进一步核实提示。"],
                topics=["contract_payment"],
                source_rules=["topic"],
            ),
        ],
        metadata={},
    )

    governance = govern_comparison_artifact("sample.docx", comparison)
    admission = admit_governance_result("sample.docx", comparison, governance)

    assert [item.title for item in admission.formal_risks] == ["履约保证金比例严重超标"]
    assert admission.pending_review_items == []
    assert admission.excluded_risks == []
    assert admission.decisions[next(iter(admission.decisions))].target_layer == "formal_risks"


def test_domain_classifier_assigns_expected_domains_for_real_replay_documents() -> None:
    cases = [
        (
            "quanzhou.docx",
            Path("data/results/v2/20260412-092839-quanzhou-runreview/comparison.json"),
            "engineering_maintenance_construction",
        ),
        (
            "fuzhou.docx",
            Path("data/results/v2/gr1-fuzhou-baseline/comparison.json"),
            "goods_procurement",
        ),
        (
            "fujian.docx",
            Path("data/results/v2/gr1-fujian-baseline/comparison.json"),
            "service_procurement",
        ),
        (
            "diesel.docx",
            Path("data/results/v2/gr1-diesel-baseline/comparison.json"),
            "goods_procurement",
        ),
    ]

    for document_name, comparison_path, expected_domain in cases:
        comparison = _load_comparison_artifact(comparison_path)
        governance = govern_comparison_artifact(document_name, comparison)
        problems = build_problem_layer(document_name, governance)
        admission = admit_problem_result(document_name, comparison, problems, governance)

        domains = {decision.document_domain for decision in admission.decisions.values()}
        assert domains == {expected_domain}
        assert all(decision.domain_confidence > 0 for decision in admission.decisions.values())
        assert all(decision.domain_policy_id for decision in admission.decisions.values())
        assert all(decision.domain_evidence for decision in admission.decisions.values())
        assert admission.input_summary["domain_context"]["document_domain"] == expected_domain


def test_domain_budget_compresses_quanzhou_pending_and_preserves_trace() -> None:
    comparison = _load_comparison_artifact("data/results/v2/20260412-092839-quanzhou-runreview/comparison.json")
    governance = govern_comparison_artifact("quanzhou.docx", comparison)
    problems = build_problem_layer("quanzhou.docx", governance)
    admission = admit_problem_result("quanzhou.docx", comparison, problems, governance)

    pending_titles = {item.title for item in admission.pending_review_items}
    hidden_titles = {
        candidate.title
        for candidate in admission.iter_all()
        if admission.decisions[candidate.rule_id].budget_hit
    }

    assert admission.input_summary["domain_context"]["document_domain"] == "engineering_maintenance_construction"
    assert len(admission.pending_review_items) <= 4
    assert "疑似限定或倾向特定品牌/供应商" in pending_titles
    assert "将样品要求/验收方案不当作为评审或履约门槛" in pending_titles
    assert "专门面向中小企业采购的证明材料要求表述需核实" not in pending_titles
    assert any(
        title in hidden_titles
        for title in {
            "专门面向中小企业采购的证明材料要求表述需核实",
            "验收流程、组织方式及不合格复验程序约定不明，存在执行风险",
        }
    )
    assert admission.input_summary["budget_summary"]["hidden_count"] >= 1
    assert any(
        decision.budget_hit
        and decision.budget_rule
        and decision.budget_reason
        and decision.absorbed_or_hidden_items
        for decision in admission.decisions.values()
    )


def test_domain_budget_marks_hidden_pending_items_as_internal_trace_only() -> None:
    comparison = _load_comparison_artifact("data/results/v2/20260412-092839-quanzhou-runreview/comparison.json")
    governance = govern_comparison_artifact("quanzhou.docx", comparison)
    problems = build_problem_layer("quanzhou.docx", governance)
    admission = admit_problem_result("quanzhou.docx", comparison, problems, governance)

    hidden_decisions = [decision for decision in admission.decisions.values() if decision.budget_hit]

    assert hidden_decisions
    assert all(decision.gate_passed is False for decision in hidden_decisions)
    assert all(decision.user_visible_gate_passed is False for decision in hidden_decisions)
    assert all(decision.budget_rule for decision in hidden_decisions)
    assert all(decision.budget_reason for decision in hidden_decisions)
