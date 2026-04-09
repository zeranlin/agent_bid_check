from __future__ import annotations

import re

from .schemas import AdmissionDecision, AdmissionLayer, AdmissionSourceType, EvidenceKind


TEMPLATE_EVIDENCE_KINDS: set[EvidenceKind] = {
    "contract_template",
    "declaration_template",
    "joint_venture_template",
    "subcontract_template",
}
BOUNDARY_EVIDENCE_KINDS: set[EvidenceKind] = {
    "optional_form",
    "attachment_instruction",
    "unknown",
}
WEAK_SOURCE_TYPES: set[AdmissionSourceType] = {
    "topic_inference",
    "completeness_hint",
    "warning_only",
}
REMINDER_TITLE_RE = re.compile(
    r"(需确认|需警惕|建议评估|需进一步核实|适用性需进一步核实|需结合项目规模评估|评审细节需确认|"
    r"表述不清|描述不完整|不够明确|缺乏可操作性|可能引发争议|倾向性隐患)"
)
REMINDER_JUDGMENT_RE = re.compile(
    r"(需确认|需警惕|建议评估|需进一步核实|建议人工复核|需结合.+评估|可能需进一步|"
    r"容易引发争议|缺乏明确标准|缺少可操作性|仍需结合.+判断)"
)
EVIDENCE_INSUFFICIENT_RE = re.compile(
    r"(关键条款缺失|证据缺失|证据片段未覆盖|内容缺失|适用性需进一步核实|需人工复核|待补证|无法判断|需结合项目规模评估)"
)
MISSING_TYPE_RE = re.compile(
    r"(未见|缺失|未明确|表述不明|待确认|需确认|需人工确认|是否补充|可能补充|未发现条款|另有章节补充)"
)
PROTECTED_FORMAL_TITLE_RE = re.compile(
    r"(评分标准中“信息化软件服务能力”要求著作权人为投标人，可能限制竞争|商务条款中关于“无犯罪证明”的提交时限及无效投标处理存在法律风险)"
)


def default_target_layer(governed_target_layer: AdmissionLayer) -> AdmissionLayer:
    return governed_target_layer


def _template_gate_decision(
    *,
    evidence_kind: EvidenceKind,
    source_type: AdmissionSourceType,
) -> tuple[AdmissionLayer, str]:
    if evidence_kind in TEMPLATE_EVIDENCE_KINDS:
        if source_type == "topic_inference":
            return (
                "excluded_risks",
                "检测到模板/协议/声明函类证据，且当前仅有专题推断支撑，不得直接作为正式风险主证据。",
            )
        return (
            "pending_review_items",
            "检测到模板/协议/声明函类证据，缺少正文硬证据交叉支撑，先降为待补证复核项。",
        )
    return (
        "pending_review_items",
        "检测到可选表单或边界型证据，当前不足以直接支撑正式风险，先保留为待补证复核项。",
    )


def _build_text_blob(title: str, governance_reason: str, *extra_parts: str) -> str:
    return "\n".join(item for item in [title, governance_reason, *extra_parts] if item)


def _should_downgrade_reminder(
    *,
    governed_target_layer: AdmissionLayer,
    title: str,
    governance_reason: str,
    source_type: AdmissionSourceType,
    source_excerpts: list[str],
    risk_judgment: list[str],
) -> bool:
    if governed_target_layer != "formal_risks":
        return False
    if source_type not in WEAK_SOURCE_TYPES:
        return False
    text_blob = _build_text_blob(title, governance_reason, *source_excerpts, *risk_judgment)
    return bool(REMINDER_TITLE_RE.search(text_blob) or REMINDER_JUDGMENT_RE.search(text_blob))


def _should_downgrade_evidence_insufficient(
    *,
    governed_target_layer: AdmissionLayer,
    title: str,
    governance_reason: str,
    source_type: AdmissionSourceType,
    source_excerpts: list[str],
    risk_judgment: list[str],
) -> bool:
    if governed_target_layer != "formal_risks":
        return False
    if source_type not in WEAK_SOURCE_TYPES:
        return False
    text_blob = _build_text_blob(title, governance_reason, *source_excerpts, *risk_judgment)
    return bool(EVIDENCE_INSUFFICIENT_RE.search(text_blob))


def _should_downgrade_missing_type(
    *,
    governed_target_layer: AdmissionLayer,
    title: str,
    governance_reason: str,
    source_type: AdmissionSourceType,
    source_excerpts: list[str],
    risk_judgment: list[str],
) -> bool:
    if governed_target_layer != "formal_risks":
        return False
    if source_type not in WEAK_SOURCE_TYPES:
        return False
    text_blob = _build_text_blob(title, governance_reason, *source_excerpts, *risk_judgment)
    return bool(MISSING_TYPE_RE.search(text_blob))


def build_admission_decision(
    *,
    governed_target_layer: AdmissionLayer,
    title: str,
    governance_reason: str,
    evidence_kind: EvidenceKind,
    source_type: AdmissionSourceType,
    source_excerpts: list[str],
    risk_judgment: list[str],
) -> AdmissionDecision:
    target_layer = default_target_layer(governed_target_layer)
    admission_reason = governance_reason or "risk_admission 已接管最终分层裁决。"
    is_protected_formal = governed_target_layer == "formal_risks" and bool(PROTECTED_FORMAL_TITLE_RE.search(title))

    if governed_target_layer == "formal_risks" and (evidence_kind in TEMPLATE_EVIDENCE_KINDS or evidence_kind in BOUNDARY_EVIDENCE_KINDS):
        target_layer, admission_reason = _template_gate_decision(
            evidence_kind=evidence_kind,
            source_type=source_type,
        )
    elif not is_protected_formal and _should_downgrade_reminder(
        governed_target_layer=governed_target_layer,
        title=title,
        governance_reason=governance_reason,
        source_type=source_type,
        source_excerpts=source_excerpts,
        risk_judgment=risk_judgment,
    ):
        target_layer = "pending_review_items"
        admission_reason = "检测到提醒项或边界提示表达，且当前缺少标准规则级硬支撑，已下沉为待补证复核项。"
    elif not is_protected_formal and _should_downgrade_evidence_insufficient(
        governed_target_layer=governed_target_layer,
        title=title,
        governance_reason=governance_reason,
        source_type=source_type,
        source_excerpts=source_excerpts,
        risk_judgment=risk_judgment,
    ):
        target_layer = "pending_review_items"
        admission_reason = "检测到证据不足或适用性待核实表达，当前不足以直接进入正式风险，已下沉为待补证复核项。"
    elif not is_protected_formal and _should_downgrade_missing_type(
        governed_target_layer=governed_target_layer,
        title=title,
        governance_reason=governance_reason,
        source_type=source_type,
        source_excerpts=source_excerpts,
        risk_judgment=risk_judgment,
    ):
        target_layer = "pending_review_items"
        admission_reason = "检测到缺失型或未见型判断表达，当前核心结论依赖未覆盖证据或待确认章节，已下沉为待补证复核项。"
    return AdmissionDecision(
        target_layer=target_layer,
        admission_reason=admission_reason,
        evidence_kind=evidence_kind,
        source_type=source_type,
    )
