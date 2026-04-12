from __future__ import annotations

from .downgrade_rules import apply_downgrade_rules
from .formal_gate import evaluate_formal_gate
from .formal_registry import resolve_formal_registry_resolution
from .historical_block import match_historical_hard_block
from .pending_gate import evaluate_pending_gate
from .schemas import AdmissionDecision, AdmissionSourceType, EvidenceKind
from .user_visible_gate import evaluate_user_visible_gate


def _build_source_blob(title: str, governance_reason: str, *parts: str) -> str:
    return "\n".join(item for item in [title, governance_reason, *parts] if item)


def build_admission_decision(
    *,
    rule_id: str,
    family_key: str,
    title: str,
    proposed_title: str,
    governance_reason: str,
    evidence_kind: EvidenceKind,
    source_type: AdmissionSourceType,
    compare_source_bucket: str,
    compare_source_buckets: list[str],
    severity: str,
    need_manual_review: bool,
    source_locations: list[str],
    source_excerpts: list[str],
    risk_judgment: list[str],
) -> AdmissionDecision:
    del compare_source_buckets
    del severity
    del need_manual_review

    source_blob = _build_source_blob(title, governance_reason, *source_excerpts, *risk_judgment)
    historical_block = match_historical_hard_block(title, proposed_title, source_blob)
    if historical_block is not None:
        _, reason = historical_block
        technical_layer = "excluded_risks"
        user_gate = evaluate_user_visible_gate(
            technical_layer=technical_layer,
            rule_id=rule_id,
            family_key=family_key,
            title=title,
            source_type=source_type,
            source_locations=source_locations,
            source_excerpts=source_excerpts,
            formal_gate_rule="historical_hard_block",
            formal_gate_registry_resolution="missing",
            pending_gate_reason_code="",
        )
        return AdmissionDecision(
            target_layer=user_gate.target_layer,
            admission_reason=reason,
            evidence_kind=evidence_kind,
            source_type=source_type,
            technical_layer_decision=technical_layer,
            gate_passed=user_gate.passed,
            gate_reason=user_gate.reason,
            gate_rule=user_gate.rule,
            user_visible_gate_passed=user_gate.passed,
            user_visible_gate_reason=user_gate.reason,
            user_visible_gate_rule=user_gate.rule,
            stable_pending_config_id=user_gate.stable_pending_config_id,
            evidence_sufficiency=user_gate.evidence_sufficiency,
            user_visible_decision_basis=user_gate.decision_basis,
            pending_gate_reason_code="",
            pending_gate_reason="",
            formal_gate_passed=False,
            formal_gate_reason=reason,
            formal_gate_rule="historical_hard_block",
            formal_gate_exception_whitelist_hit=False,
            formal_gate_family_allowed=False,
            formal_gate_evidence_passed=False,
            formal_gate_registry_rule_id="",
            formal_gate_registry_status="",
            formal_gate_registry_source="",
            formal_gate_registry_resolution="missing",
        )

    registry_resolution = resolve_formal_registry_resolution(rule_id=rule_id, family_key=family_key, title=title)
    downgrade = apply_downgrade_rules(
        title=title,
        governance_reason=governance_reason,
        evidence_kind=evidence_kind,
        source_type=source_type,
        source_excerpts=source_excerpts,
        risk_judgment=risk_judgment,
        registry_family_allowed=bool(registry_resolution.entry and registry_resolution.entry.allow_formal),
    )
    if downgrade is not None:
        layer, reason, rule_name = downgrade
        decision = AdmissionDecision(
            target_layer=layer,
            admission_reason=reason,
            evidence_kind=evidence_kind,
            source_type=source_type,
            technical_layer_decision=layer,
            pending_gate_reason_code="",
            pending_gate_reason="",
            formal_gate_passed=False,
            formal_gate_reason=reason,
            formal_gate_rule=rule_name,
            formal_gate_exception_whitelist_hit=False,
            formal_gate_family_allowed=False,
            formal_gate_evidence_passed=False,
            formal_gate_registry_rule_id="",
            formal_gate_registry_status="",
            formal_gate_registry_source="",
            formal_gate_registry_resolution="missing",
        )
        technical_layer = decision.target_layer
        pending_gate = evaluate_pending_gate(
            current_layer=technical_layer,
            title=title,
            governance_reason=governance_reason,
            source_type=source_type,
            source_locations=source_locations,
            source_excerpts=source_excerpts,
            risk_judgment=risk_judgment,
        )
        if pending_gate is not None:
            decision.pending_gate_reason_code = pending_gate.reason_code
            decision.pending_gate_reason = pending_gate.reason
        user_gate = evaluate_user_visible_gate(
            technical_layer=technical_layer,
            rule_id=rule_id,
            family_key=family_key,
            title=title,
            source_type=source_type,
            source_locations=source_locations,
            source_excerpts=source_excerpts,
            formal_gate_rule=decision.formal_gate_rule,
            formal_gate_registry_resolution=decision.formal_gate_registry_resolution,
            pending_gate_reason_code=decision.pending_gate_reason_code,
        )
        decision.technical_layer_decision = technical_layer
        decision.target_layer = user_gate.target_layer
        decision.gate_passed = user_gate.passed
        decision.gate_reason = user_gate.reason
        decision.gate_rule = user_gate.rule
        decision.user_visible_gate_passed = user_gate.passed
        decision.user_visible_gate_reason = user_gate.reason
        decision.user_visible_gate_rule = user_gate.rule
        decision.stable_pending_config_id = user_gate.stable_pending_config_id
        decision.evidence_sufficiency = user_gate.evidence_sufficiency
        decision.user_visible_decision_basis = user_gate.decision_basis
        return decision

    gate_result = evaluate_formal_gate(
        rule_id=rule_id,
        family_key=family_key,
        title=title,
        proposed_title=proposed_title,
        governance_reason=governance_reason,
        evidence_kind=evidence_kind,
        source_type=source_type,
        compare_source_bucket=compare_source_bucket,
        source_locations=source_locations,
        source_excerpts=source_excerpts,
        risk_judgment=risk_judgment,
    )
    decision = AdmissionDecision(
        target_layer=gate_result.target_layer,
        admission_reason=gate_result.reason,
        evidence_kind=evidence_kind,
        source_type=source_type,
        technical_layer_decision=gate_result.target_layer,
        pending_gate_reason_code="",
        pending_gate_reason="",
        formal_gate_passed=gate_result.passed,
        formal_gate_reason=gate_result.reason,
        formal_gate_rule=gate_result.rule,
        formal_gate_exception_whitelist_hit=gate_result.whitelist_hit,
        formal_gate_family_allowed=gate_result.family_allowed,
        formal_gate_evidence_passed=gate_result.evidence_passed,
        formal_gate_registry_rule_id=gate_result.registry_rule_id,
        formal_gate_registry_status=gate_result.registry_status,
        formal_gate_registry_source=gate_result.registry_source,
        formal_gate_registry_resolution=gate_result.registry_resolution,
    )
    technical_layer = decision.target_layer
    pending_gate = evaluate_pending_gate(
        current_layer=technical_layer,
        title=title,
        governance_reason=governance_reason,
        source_type=source_type,
        source_locations=source_locations,
        source_excerpts=source_excerpts,
        risk_judgment=risk_judgment,
    )
    if pending_gate is not None:
        decision.pending_gate_reason_code = pending_gate.reason_code
        decision.pending_gate_reason = pending_gate.reason
    user_gate = evaluate_user_visible_gate(
        technical_layer=technical_layer,
        rule_id=rule_id,
        family_key=family_key,
        title=title,
        source_type=source_type,
        source_locations=source_locations,
        source_excerpts=source_excerpts,
        formal_gate_rule=decision.formal_gate_rule,
        formal_gate_registry_resolution=decision.formal_gate_registry_resolution,
        pending_gate_reason_code=decision.pending_gate_reason_code,
    )
    decision.technical_layer_decision = technical_layer
    decision.target_layer = user_gate.target_layer
    decision.gate_passed = user_gate.passed
    decision.gate_reason = user_gate.reason
    decision.gate_rule = user_gate.rule
    decision.user_visible_gate_passed = user_gate.passed
    decision.user_visible_gate_reason = user_gate.reason
    decision.user_visible_gate_rule = user_gate.rule
    decision.stable_pending_config_id = user_gate.stable_pending_config_id
    decision.evidence_sufficiency = user_gate.evidence_sufficiency
    decision.user_visible_decision_basis = user_gate.decision_basis
    return decision
