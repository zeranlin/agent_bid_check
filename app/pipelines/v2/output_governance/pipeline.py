from __future__ import annotations

from .identity import build_risk_family, build_risk_identity
from .rules import decide_target_layer, merge_reason_for_family, pick_higher_severity
from .schemas import GovernedResult, GovernedRisk, GovernanceClusterEnvelope, GovernanceDecision, GovernanceInput


def _coerce_pending_or_excluded(item: dict, layer: str) -> GovernanceClusterEnvelope:
    if not isinstance(item, dict):
        raise TypeError("output governance only accepts structured dict items for pending/excluded layers")
    title = str(item.get("title", "")).strip()
    review_type = str(item.get("review_type", "")).strip()
    if not title:
        raise ValueError("governance item must contain structured title")
    if not review_type:
        review_type = "待补证复核" if layer == "pending_review_items" else "已剔除误报"
    return GovernanceClusterEnvelope(
        layer=layer,  # type: ignore[arg-type]
        title=title,
        review_type=review_type,
        severity=str(item.get("severity", "需人工复核")).strip() or "需人工复核",
        source_locations=[str(item.get("source_location", "")).strip()] if str(item.get("source_location", "")).strip() else [],
        source_excerpts=[str(item.get("source_excerpt", "")).strip()] if str(item.get("source_excerpt", "")).strip() else [],
        source_topics=[str(item.get("topic", "")).strip()] if str(item.get("topic", "")).strip() else [],
        governance_reason=str(item.get("reason", "")).strip() or "由 compare 元数据进入输出治理层。",
        extras={k: v for k, v in item.items() if k not in {"title", "review_type", "severity", "source_location", "source_excerpt", "topic", "reason"}},
    )


def _govern_envelope(envelope: GovernanceClusterEnvelope) -> GovernedRisk:
    family = build_risk_family(envelope)
    identity = build_risk_identity(envelope, family)
    target_layer, governance_reason = decide_target_layer(envelope)
    decision = GovernanceDecision(
        target_layer=target_layer,
        governance_reason=governance_reason,
        proposed_title=envelope.title,
        canonical_title=family.canonical_title,
    )
    return GovernedRisk(
        identity=identity,
        family=family,
        decision=decision,
        review_type=envelope.review_type,
        severity=envelope.severity,
        source_locations=list(envelope.source_locations),
        source_excerpts=list(envelope.source_excerpts),
        risk_judgment=list(envelope.risk_judgment),
        legal_basis=list(envelope.legal_basis),
        rectification=list(envelope.rectification),
        source_rules=list(envelope.source_rules),
        need_manual_review=envelope.need_manual_review,
        extras=dict(envelope.extras),
    )


def _merge_governed_risks(items: list[GovernedRisk]) -> list[GovernedRisk]:
    merged: dict[tuple[str, str], GovernedRisk] = {}
    for item in items:
        key = (item.decision.target_layer, item.family.family_key)
        if key not in merged:
            item.decision.canonical_title = item.family.canonical_title
            merged[key] = item
            continue
        existing = merged[key]
        existing.severity = pick_higher_severity(existing.severity, item.severity)
        existing.source_locations = list(dict.fromkeys([*existing.source_locations, *item.source_locations]))
        existing.source_excerpts = list(dict.fromkeys([*existing.source_excerpts, *item.source_excerpts]))
        existing.risk_judgment = list(dict.fromkeys([*existing.risk_judgment, *item.risk_judgment]))
        existing.legal_basis = list(dict.fromkeys([*existing.legal_basis, *item.legal_basis]))
        existing.rectification = list(dict.fromkeys([*existing.rectification, *item.rectification]))
        existing.source_rules = list(dict.fromkeys([*existing.source_rules, *item.source_rules]))
        existing.identity.source_topics = list(dict.fromkeys([*existing.identity.source_topics, *item.identity.source_topics]))
        existing.identity.evidence_anchors = list(dict.fromkeys([*existing.identity.evidence_anchors, *item.identity.evidence_anchors]))
        existing.identity.document_span = list(dict.fromkeys([*existing.identity.document_span, *item.identity.document_span]))
        existing.family.source_topics = list(dict.fromkeys([*existing.family.source_topics, *item.family.source_topics]))
        existing.need_manual_review = existing.need_manual_review or item.need_manual_review
        existing.decision.governance_reason = merge_reason_for_family(existing.family.family_key)
    return list(merged.values())


def govern_comparison_artifact(document_name: str, comparison) -> GovernedResult:
    governance_input = GovernanceInput(document_name=document_name, comparison=comparison)
    result = GovernedResult(
        document_name=document_name,
        input_summary={
            "cluster_count": len(comparison.clusters),
            "pending_count": len(comparison.metadata.get("pending_review_items", [])) if isinstance(comparison.metadata, dict) else 0,
            "excluded_count": len(comparison.metadata.get("excluded_risks", [])) if isinstance(comparison.metadata, dict) else 0,
        },
    )
    governed_formal = [_govern_envelope(GovernanceClusterEnvelope.from_cluster(cluster)) for cluster in comparison.clusters]
    pending_items = comparison.metadata.get("pending_review_items", []) if isinstance(comparison.metadata, dict) else []
    excluded_items = comparison.metadata.get("excluded_risks", []) if isinstance(comparison.metadata, dict) else []
    governed_pending = [_govern_envelope(_coerce_pending_or_excluded(item, "pending_review_items")) for item in pending_items]
    governed_excluded = [_govern_envelope(_coerce_pending_or_excluded(item, "excluded_risks")) for item in excluded_items]
    all_items = _merge_governed_risks([*governed_formal, *governed_pending, *governed_excluded])
    result.formal_risks = [item for item in all_items if item.decision.target_layer == "formal_risks"]
    result.pending_review_items = [item for item in all_items if item.decision.target_layer == "pending_review_items"]
    result.excluded_risks = [item for item in all_items if item.decision.target_layer == "excluded_risks"]
    result.input_summary["governance_input"] = governance_input.to_dict()
    return result
