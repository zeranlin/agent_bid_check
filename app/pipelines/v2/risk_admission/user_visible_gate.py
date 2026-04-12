from __future__ import annotations

import re
from dataclasses import dataclass

from .pending_gate import PLACEHOLDER_EXCERPT_RE, PLACEHOLDER_LOCATION_RE
from .schemas import AdmissionLayer, AdmissionSourceType


STABLE_PENDING_FAMILIES: set[str] = {
    "missing_detection_or_cert_requirement",
    "scoring_clarity",
    "energy_policy_missing",
    "software_copyright_competition",
    "no_crime_submission_timing",
    "brand_bias",
    "sample_acceptance_gate",
}

STABLE_PENDING_TITLE_RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "pending_material_issue_allowed",
        re.compile(r"(缺乏预付款安排|资金压力较大)"),
        "当前问题虽未达 formal 条件，但具备明确商务影响和原文证据，保留为用户可见待补证项。",
    ),
    (
        "pending_material_issue_allowed",
        re.compile(r"(远程开标解密时限及后果条款的合理性审查|远程开标逾期解密后果表述需进一步确认)"),
        "当前问题涉及投标有效性或程序后果，具备明确复核价值，保留为用户可见待补证项。",
    ),
    (
        "pending_material_issue_allowed",
        re.compile(r"(验收流程与考核机制表述笼统|验收流程、组织方式及不合格复验程序约定不明)"),
        "当前问题涉及履约执行和验收争议风险，具备明确复核价值，保留为用户可见待补证项。",
    ),
    (
        "pending_material_issue_allowed",
        re.compile(r"(专门面向中小企业采购的评审细节需确认|专门面向中小企业采购的证明材料要求表述需核实)"),
        "当前问题涉及采购政策适用边界，具备明确复核价值，保留为用户可见待补证项。",
    ),
    (
        "pending_material_issue_allowed",
        re.compile(r"(评分标准中设置特定品牌倾向性条款|设备品牌指定风险|疑似限定或倾向特定品牌/供应商)"),
        "当前问题涉及潜在品牌倾向或品牌指定，具备明确复核价值，保留为用户可见待补证项。",
    ),
    (
        "pending_material_issue_allowed",
        re.compile(r"(人员配置数量及证书要求需结合项目规模评估|要求现场技术人员必须为制造商原厂工程师)"),
        "当前问题涉及资格条件与竞争边界，具备明确复核价值，保留为用户可见待补证项。",
    ),
    (
        "pending_material_issue_allowed",
        re.compile(r"(信息化软件服务能力.*著作权人为投标人|无犯罪证明.*提交时限|远程开标解密时限及后果条款显失公平)"),
        "当前问题具备明确竞争或程序后果，虽未进入 formal，但应保留为用户可见待补证项。",
    ),
]


@dataclass(frozen=True)
class UserVisibleGateResult:
    target_layer: AdmissionLayer
    passed: bool
    reason: str
    rule: str
    evidence_sufficiency: str
    decision_basis: str


def _has_user_visible_evidence(source_locations: list[str], source_excerpts: list[str]) -> tuple[bool, str]:
    normalized_locations = [str(item).strip() for item in source_locations if str(item).strip()]
    normalized_excerpts = [str(item).strip() for item in source_excerpts if str(item).strip()]
    if not normalized_locations or not normalized_excerpts:
        return False, "missing_user_visible_evidence"
    if all(PLACEHOLDER_LOCATION_RE.fullmatch(item) for item in normalized_locations) or all(
        PLACEHOLDER_EXCERPT_RE.fullmatch(item) for item in normalized_excerpts
    ):
        return False, "missing_user_visible_evidence"
    return True, "sufficient"


def _is_stable_pending_issue(*, family_key: str, title: str) -> tuple[bool, str]:
    if family_key in STABLE_PENDING_FAMILIES:
        return True, "当前问题属于稳定的待补证家族，具备持续对外复核价值。"
    for _, pattern, reason in STABLE_PENDING_TITLE_RULES:
        if pattern.search(title):
            return True, reason
    return False, ""


def evaluate_user_visible_gate(
    *,
    technical_layer: AdmissionLayer,
    rule_id: str,
    family_key: str,
    title: str,
    source_type: AdmissionSourceType,
    source_locations: list[str],
    source_excerpts: list[str],
    formal_gate_rule: str,
    formal_gate_registry_resolution: str,
    pending_gate_reason_code: str,
) -> UserVisibleGateResult:
    has_visible_evidence, evidence_sufficiency = _has_user_visible_evidence(source_locations, source_excerpts)
    if not has_visible_evidence:
        return UserVisibleGateResult(
            target_layer="excluded_risks",
            passed=False,
            reason="当前问题缺少用户可见的原文位置或摘录，仅保留内部 trace，不进入用户可见结果层。",
            rule="missing_user_visible_evidence",
            evidence_sufficiency=evidence_sufficiency,
            decision_basis="location_excerpt_required_for_user_visible_output",
        )

    if technical_layer == "formal_risks":
        return UserVisibleGateResult(
            target_layer="formal_risks",
            passed=True,
            reason="当前问题已通过技术层 formal 准入，且具备稳定证据，可进入用户可见正式风险层。",
            rule="formal_output_allowed",
            evidence_sufficiency=evidence_sufficiency,
            decision_basis="technical_formal_and_user_visible_gate_aligned",
        )

    if technical_layer == "excluded_risks":
        return UserVisibleGateResult(
            target_layer="excluded_risks",
            passed=False,
            reason="当前问题已在技术层被排除，仅保留内部 trace 供排障复核。",
            rule="technical_layer_excluded",
            evidence_sufficiency=evidence_sufficiency,
            decision_basis="technical_layer_excluded",
        )

    if pending_gate_reason_code in {
        "weak_signal_no_rule_support",
        "weak_signal_no_material_consequence",
        "missing_user_visible_evidence",
    }:
        return UserVisibleGateResult(
            target_layer="excluded_risks",
            passed=False,
            reason="当前问题仅形成弱提示或证据不足提示，不再进入用户可见待补证层。",
            rule=pending_gate_reason_code,
            evidence_sufficiency="insufficient" if pending_gate_reason_code != "missing_user_visible_evidence" else evidence_sufficiency,
            decision_basis="pending_gate_blocked_before_user_visible_output",
        )

    stable_pending, stable_reason = _is_stable_pending_issue(family_key=family_key, title=title)
    if stable_pending:
        return UserVisibleGateResult(
            target_layer="pending_review_items",
            passed=True,
            reason=stable_reason,
            rule="pending_material_issue_allowed",
            evidence_sufficiency=evidence_sufficiency,
            decision_basis="stable_pending_family_or_title_with_material_review_value",
        )

    if formal_gate_rule in {"registry_mapping_missing_block", "registry_mapping_mismatch_block"} and source_type != "topic_inference":
        return UserVisibleGateResult(
            target_layer="excluded_risks",
            passed=False,
            reason="当前仅命中内部治理信号，未形成可直接对外展示的用户结果。",
            rule="internal_governance_signal",
            evidence_sufficiency=evidence_sufficiency,
            decision_basis="unstable_registry_identity_should_not_be_user_visible",
        )

    if formal_gate_registry_resolution == "missing" and source_type in {"topic_inference", "warning_only", "completeness_hint"}:
        return UserVisibleGateResult(
            target_layer="excluded_risks",
            passed=False,
            reason="当前问题尚未形成稳定规则归属或用户可理解的待补证价值，先收回内部治理层。",
            rule="unstable_pending_identity_block",
            evidence_sufficiency=evidence_sufficiency,
            decision_basis="topic_only_pending_without_stable_registry_or_allowlist",
        )

    if not rule_id.strip() or not family_key.strip():
        return UserVisibleGateResult(
            target_layer="excluded_risks",
            passed=False,
            reason="当前问题缺少稳定家族或规则标识，仅保留内部 trace。",
            rule="missing_stable_identity",
            evidence_sufficiency=evidence_sufficiency,
            decision_basis="stable_identity_required_for_user_visible_output",
        )

    return UserVisibleGateResult(
        target_layer="pending_review_items",
        passed=True,
        reason="当前问题虽未进入 formal，但具备可定位证据与明确复核价值，保留为用户可见待补证项。",
        rule="pending_material_issue_allowed",
        evidence_sufficiency=evidence_sufficiency,
        decision_basis="default_pending_user_visible_allow_with_sufficient_evidence",
    )
