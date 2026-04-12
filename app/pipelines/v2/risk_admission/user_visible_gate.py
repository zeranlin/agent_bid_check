from __future__ import annotations

import re
from dataclasses import dataclass

from app.governance.ax_governance import load_ax_governance_index

from .pending_gate import PLACEHOLDER_EXCERPT_RE, PLACEHOLDER_LOCATION_RE
from .schemas import AdmissionLayer, AdmissionSourceType


@dataclass(frozen=True)
class UserVisibleGateResult:
    target_layer: AdmissionLayer
    passed: bool
    reason: str
    rule: str
    evidence_sufficiency: str
    decision_basis: str
    stable_pending_config_id: str = ""


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


def _match_stable_pending_config(*, family_key: str, title: str) -> tuple[str, str, str]:
    index = load_ax_governance_index()
    family = index.stable_pending_families.get(family_key)
    if family is not None:
        return family.config_id, family.reason, family.gate_rule
    for item in index.stable_pending_patterns:
        if re.search(item.pattern, title):
            return item.config_id, item.reason, item.gate_rule
    return "", "", ""


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

    stable_config_id, stable_reason, stable_rule = _match_stable_pending_config(family_key=family_key, title=title)
    if stable_config_id:
        return UserVisibleGateResult(
            target_layer="pending_review_items",
            passed=True,
            reason=stable_reason,
            rule=stable_rule,
            evidence_sufficiency=evidence_sufficiency,
            decision_basis="stable_pending_family_or_title_with_material_review_value",
            stable_pending_config_id=stable_config_id,
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
