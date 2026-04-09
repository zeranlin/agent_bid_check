from __future__ import annotations

from .identity import build_risk_family, build_risk_identity
from .rules import apply_family_severity_floor, decide_target_layer, merge_reason_for_family, pick_higher_severity
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
    normalized_severity = apply_family_severity_floor(family.family_key, envelope.severity)
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
        severity=normalized_severity,
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


def _is_preserved_input_layer(item: GovernedRisk) -> bool:
    return item.decision.governance_reason.startswith("未触发治理层纠偏规则，暂保留 compare 初始层级。")


def _merge_into_winner(winner: GovernedRisk, covered: GovernedRisk) -> GovernedRisk:
    winner.severity = pick_higher_severity(winner.severity, covered.severity)
    winner.source_locations = list(dict.fromkeys([*winner.source_locations, *covered.source_locations]))
    winner.source_excerpts = list(dict.fromkeys([*winner.source_excerpts, *covered.source_excerpts]))
    winner.risk_judgment = list(dict.fromkeys([*winner.risk_judgment, *covered.risk_judgment]))
    winner.legal_basis = list(dict.fromkeys([*winner.legal_basis, *covered.legal_basis]))
    winner.rectification = list(dict.fromkeys([*winner.rectification, *covered.rectification]))
    winner.source_rules = list(dict.fromkeys([*winner.source_rules, *covered.source_rules]))
    winner.identity.source_topics = list(dict.fromkeys([*winner.identity.source_topics, *covered.identity.source_topics]))
    winner.identity.evidence_anchors = list(
        dict.fromkeys([*winner.identity.evidence_anchors, *covered.identity.evidence_anchors])
    )
    winner.identity.document_span = list(dict.fromkeys([*winner.identity.document_span, *covered.identity.document_span]))
    winner.family.source_topics = list(dict.fromkeys([*winner.family.source_topics, *covered.family.source_topics]))
    winner.need_manual_review = winner.need_manual_review or covered.need_manual_review
    return winner


def _pick_family_winner(items: list[GovernedRisk]) -> GovernedRisk:
    formal_items = [item for item in items if item.decision.target_layer == "formal_risks"]
    pending_items = [item for item in items if item.decision.target_layer == "pending_review_items"]
    excluded_items = [item for item in items if item.decision.target_layer == "excluded_risks"]

    deterministic_formal = [
        item for item in formal_items if not item.need_manual_review and item.severity != "需人工复核"
    ]
    explicit_excluded = [item for item in excluded_items if not _is_preserved_input_layer(item)]

    if deterministic_formal:
        return sorted(deterministic_formal, key=lambda item: -len(item.source_rules))[0]
    if explicit_excluded:
        return sorted(explicit_excluded, key=lambda item: -len(item.source_locations))[0]
    if pending_items:
        return sorted(pending_items, key=lambda item: -len(item.source_locations))[0]
    if formal_items:
        return sorted(formal_items, key=lambda item: -len(item.source_locations))[0]
    return sorted(excluded_items, key=lambda item: -len(item.source_locations))[0]


def _resolve_cross_layer_conflicts(items: list[GovernedRisk]) -> list[GovernedRisk]:
    by_family: dict[str, list[GovernedRisk]] = {}
    for item in items:
        by_family.setdefault(item.family.family_key, []).append(item)

    resolved: list[GovernedRisk] = []
    for family_items in by_family.values():
        if len(family_items) == 1:
            resolved.append(family_items[0])
            continue
        winner = _pick_family_winner(family_items)
        covered_layers = sorted({item.decision.target_layer for item in family_items if item is not winner})
        covered_titles = [item.decision.canonical_title for item in family_items if item is not winner]
        for item in family_items:
            if item is winner:
                continue
            winner = _merge_into_winner(winner, item)
        covered_text = "、".join(covered_layers) if covered_layers else "无"
        covered_titles_text = "；".join(dict.fromkeys(covered_titles)) if covered_titles else "无"
        winner.decision.governance_reason = (
            f"同一风险家族跨层冲突已仲裁，最终保留为 {winner.decision.target_layer}，"
            f"覆盖层级：{covered_text}，吸收标题：{covered_titles_text}。"
        )
        resolved.append(winner)
    return resolved


def validate_governed_result(result: GovernedResult) -> None:
    family_layers: dict[str, set[str]] = {}
    for item in result.iter_all():
        family_layers.setdefault(item.family.family_key, set()).add(item.decision.target_layer)
    conflicts = {family: sorted(layers) for family, layers in family_layers.items() if len(layers) > 1}
    if conflicts:
        raise ValueError(f"cross-layer family conflicts remain after governance: {conflicts}")


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
    governed_formal = []
    for cluster in comparison.clusters:
        envelope = GovernanceClusterEnvelope.from_cluster(cluster)
        envelope.governance_reason = "由 compare formal 候选进入输出治理层。"
        governed_formal.append(_govern_envelope(envelope))
    pending_items = comparison.metadata.get("pending_review_items", []) if isinstance(comparison.metadata, dict) else []
    excluded_items = comparison.metadata.get("excluded_risks", []) if isinstance(comparison.metadata, dict) else []
    governed_pending = [_govern_envelope(_coerce_pending_or_excluded(item, "pending_review_items")) for item in pending_items]
    governed_excluded = [_govern_envelope(_coerce_pending_or_excluded(item, "excluded_risks")) for item in excluded_items]
    all_items = _resolve_cross_layer_conflicts(
        _merge_governed_risks([*governed_formal, *governed_pending, *governed_excluded])
    )
    result.formal_risks = [item for item in all_items if item.decision.target_layer == "formal_risks"]
    result.pending_review_items = [item for item in all_items if item.decision.target_layer == "pending_review_items"]
    result.excluded_risks = [item for item in all_items if item.decision.target_layer == "excluded_risks"]
    result.input_summary["governance_input"] = governance_input.to_dict()
    validate_governed_result(result)
    return result
