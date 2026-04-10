from __future__ import annotations

import re
from dataclasses import dataclass

from .schemas import AdmissionLayer, AdmissionSourceType


WEAK_SOURCE_TYPES: set[AdmissionSourceType] = {
    "topic_inference",
    "completeness_hint",
    "warning_only",
}

PLACEHOLDER_LOCATION_RE = re.compile(r"^(未在当前证据片段中找到|未发现|无)$")
PLACEHOLDER_EXCERPT_RE = re.compile(r"^(无|未发现|未在当前证据片段中找到)$")
WEAK_RULE_SUPPORT_RE = re.compile(
    r"(政策依据引用不完整|表述截断风险|质疑投诉章节内容不完整|执行标准引用不明确|使用[“\"]?国家标准[”\"]?泛称|"
    r"强制性产品认证（CCC）要求表述模糊|未明确证书或报告要求)"
)
WEAK_CONSEQUENCE_RE = re.compile(
    r"(节能环保政策具体适用要求缺失|节能环保政策条款未写明具体适用要求|未见明确合规后果)"
)
MATERIAL_CONSEQUENCE_RE = re.compile(
    r"(无效投标|限制竞争|排斥|转嫁|失衡|矛盾|加分|扣分|废标|单方裁量|强制|必须|不满足)"
)


@dataclass(frozen=True)
class PendingGateDecision:
    target_layer: AdmissionLayer
    reason_code: str
    reason: str


def _text_blob(title: str, governance_reason: str, source_locations: list[str], source_excerpts: list[str], risk_judgment: list[str]) -> str:
    return "\n".join(
        part
        for part in [title, governance_reason, *source_locations, *source_excerpts, *risk_judgment]
        if str(part).strip()
    )


def evaluate_pending_gate(
    *,
    current_layer: AdmissionLayer,
    title: str,
    governance_reason: str,
    source_type: AdmissionSourceType,
    source_locations: list[str],
    source_excerpts: list[str],
    risk_judgment: list[str],
) -> PendingGateDecision | None:
    if current_layer != "pending_review_items":
        return None

    normalized_locations = [str(item).strip() for item in source_locations if str(item).strip()]
    normalized_excerpts = [str(item).strip() for item in source_excerpts if str(item).strip()]
    if not normalized_locations or not normalized_excerpts:
        return PendingGateDecision(
            target_layer="excluded_risks",
            reason_code="missing_user_visible_evidence",
            reason="当前问题缺少用户可见的原文位置或摘录，仅保留内部 trace，不再作为对外待补证项展示。",
        )
    if all(PLACEHOLDER_LOCATION_RE.fullmatch(item) for item in normalized_locations) or all(
        PLACEHOLDER_EXCERPT_RE.fullmatch(item) for item in normalized_excerpts
    ):
        return PendingGateDecision(
            target_layer="excluded_risks",
            reason_code="missing_user_visible_evidence",
            reason="当前问题缺少有效原文位置或摘录，仅保留内部 trace，不再作为对外待补证项展示。",
        )

    if source_type not in WEAK_SOURCE_TYPES:
        return None

    source_blob = _text_blob(title, governance_reason, normalized_locations, normalized_excerpts, risk_judgment)
    if WEAK_RULE_SUPPORT_RE.search(source_blob):
        return PendingGateDecision(
            target_layer="excluded_risks",
            reason_code="weak_signal_no_rule_support",
            reason="当前仅体现标题或表述层面的弱提示，缺少稳定规则支撑，已阻断用户可见 pending 输出。",
        )
    if WEAK_CONSEQUENCE_RE.search(source_blob):
        return PendingGateDecision(
            target_layer="excluded_risks",
            reason_code="weak_signal_no_material_consequence",
            reason="当前仅体现提醒性或适用性缺口，尚未形成明确合规后果，已阻断用户可见 pending 输出。",
        )
    if not MATERIAL_CONSEQUENCE_RE.search(source_blob):
        return None
    return None
