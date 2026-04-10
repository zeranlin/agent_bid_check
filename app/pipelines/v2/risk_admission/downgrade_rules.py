from __future__ import annotations

import re

from .schemas import AdmissionLayer, AdmissionSourceType, EvidenceKind
from .whitelist import match_formal_exception_whitelist


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
PENDING_RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "policy_completeness_pending",
        re.compile(r"(残疾人福利性单位及监狱企业政策表述不完整)"),
        "当前更像政策配套表述是否完整的问题，证据不足以直接作为正式风险定性，先转为待补证复核项。",
    ),
    (
        "energy_policy_completeness_pending",
        re.compile(r"(节能环保产品政策条款缺失|节能环保产品政策落实条款缺失)"),
        "当前仅能确认节能环保政策章节召回不足，尚不足以直接认定为正式风险，先转为待补证复核项。",
    ),
    (
        "sme_policy_completeness_pending",
        re.compile(r"(中小企业扶持政策落实条款缺失（价格扣除比例未明确）|中小企业扶持政策价格扣除比例缺失)"),
        "当前属于政策执行参数是否完整的问题，仍需后续结合正文证据判断，先转为待补证复核项。",
    ),
    (
        "payment_chain_pending",
        re.compile(r"(付款节点设置导致质保金比例较高且支付周期较长|付款节点明显偏后|尾款支付节点滞后)"),
        "当前更多体现为付款链路合理性待核查，需结合预付款、中间款、尾款整体结构判断，先转为待补证复核项。",
    ),
    (
        "acceptance_clarity_pending",
        re.compile(r"(验收主体及流程描述不完整，缺乏不合格处理机制|验收标准来源表述不清，容易引发验收依据理解歧义)"),
        "当前更适合作为验收条款明确性复核项，需结合完整验收机制继续核实，先转为待补证复核项。",
    ),
]
EXCLUDED_RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "qualification_exception_excluded",
        re.compile(r"(社保缴纳证明要求存在例外情形，需关注执行一致性|人员社保要求存在特殊豁免)"),
        "当前属于合理例外说明场景，未见明显失衡或异常豁免，不作为正式风险。",
    ),
    (
        "template_placeholder_excluded",
        re.compile(r"(验收流程关键时点留白|验收时点约定缺失，导致验收流程不可操作)"),
        "检测到合同/协议模板中的时限占位符，属于模板留白，不直接作为正式风险输出。",
    ),
    (
        "clarification_placeholder_excluded",
        re.compile(r"(采购文件澄清截止时间未明确填写|澄清/修改事项截止时间未明确填写)"),
        "当前更像模板留白或程序承接字段缺失，不直接作为正式风险输出。",
    ),
    (
        "electronic_capacity_excluded",
        re.compile(r"(电子投标文件容量限制可能增加投标负担|电子投标文件容量限制需关注)"),
        "当前属于电子化平台参数边界提示，不直接作为正式风险输出。",
    ),
    (
        "integrity_scoring_excluded",
        re.compile(r"(评分标准中“诚信情况”查询渠道及扣分标准表述不清)"),
        "当前更多属于诚信评分细则优化事项，未达到正式风险输出阈值。",
    ),
]
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
PREPAYMENT_ONLY_RE = re.compile(r"(缺乏预付款安排|未设置预付款|未设预付款)")
SIGN_DEFAULT_RE = re.compile(r"(开标记录签字确认的默认认可条款|未签字确认开标记录的[，,]?[视即]?为认可开标结果)")
REMOTE_DECRYPT_RE = re.compile(r"(远程开标|解密)")
REMOTE_DECRYPT_ABNORMAL_RE = re.compile(
    r"(5分钟内|10分钟内|超时即按无效投标处理|不得提出异议|不得异议|直接按无效投标)"
)
TEMPLATE_BLANK_RE = re.compile(
    r"(验收时间条款留白|履约验收时点不明确|_{3,}|【专用条款】|专用条款约定|_______日内)"
)


def _build_text_blob(title: str, *extra_parts: str) -> str:
    return "\n".join(item for item in [title, *extra_parts] if item)


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


def apply_downgrade_rules(
    *,
    title: str,
    governance_reason: str,
    evidence_kind: EvidenceKind,
    source_type: AdmissionSourceType,
    source_excerpts: list[str],
    risk_judgment: list[str],
    registry_family_allowed: bool = False,
) -> tuple[AdmissionLayer, str, str] | None:
    source_blob = _build_text_blob(title, *source_excerpts, *risk_judgment)

    if evidence_kind in TEMPLATE_EVIDENCE_KINDS or evidence_kind in BOUNDARY_EVIDENCE_KINDS:
        layer, reason = _template_gate_decision(evidence_kind=evidence_kind, source_type=source_type)
        return layer, reason, "downgrade_template_or_boundary"

    if TEMPLATE_BLANK_RE.search(source_blob):
        return (
            "excluded_risks",
            "检测到模板留白或专用条款占位表达，当前属于模板边界内容，不作为正式风险输出。",
            "downgrade_template_blank",
        )

    for rule_name, pattern, reason in EXCLUDED_RULES:
        if pattern.search(source_blob):
            return "excluded_risks", reason, rule_name

    for rule_name, pattern, reason in PENDING_RULES:
        if pattern.search(source_blob):
            return "pending_review_items", reason, rule_name

    if PREPAYMENT_ONLY_RE.search(source_blob):
        return (
            "pending_review_items",
            "当前仅体现未设预付款安排，尚不足以直接认定为正式合规风险，先转待补证复核。",
            "downgrade_prepayment_only",
        )
    if SIGN_DEFAULT_RE.search(source_blob):
        return (
            "excluded_risks",
            "当前仅见开标记录签字默认认可表述，未见足以支撑正式风险的异常程序失衡证据，先排除输出。",
            "downgrade_sign_default",
        )
    if (
        REMOTE_DECRYPT_RE.search(source_blob)
        and not REMOTE_DECRYPT_ABNORMAL_RE.search(source_blob)
        and "显失公平" not in title
    ):
        return (
            "pending_review_items",
            "当前仅见一般性远程开标解密时限及后果安排，未出现异常偏短时长或明显过重后果，先转待补证复核。",
            "downgrade_remote_decrypt_routine",
        )

    if source_type in WEAK_SOURCE_TYPES:
        whitelist_hit = match_formal_exception_whitelist(title, source_blob)
        if whitelist_hit is not None:
            return None
        if registry_family_allowed:
            return None
        if REMINDER_TITLE_RE.search(source_blob) or REMINDER_JUDGMENT_RE.search(source_blob):
            return (
                "pending_review_items",
                "检测到提醒项或边界提示表达，且当前缺少标准规则级硬支撑，已下沉为待补证复核项。",
                "downgrade_reminder",
            )
        if EVIDENCE_INSUFFICIENT_RE.search(source_blob):
            return (
                "pending_review_items",
                "检测到证据不足或适用性待核实表达，当前不足以直接进入正式风险，已下沉为待补证复核项。",
                "downgrade_evidence_insufficient",
            )
        if MISSING_TYPE_RE.search(source_blob):
            return (
                "pending_review_items",
                "检测到缺失型或未见型判断表达，当前核心结论依赖未覆盖证据或待确认章节，已下沉为待补证复核项。",
                "downgrade_missing_type",
            )

    return None
