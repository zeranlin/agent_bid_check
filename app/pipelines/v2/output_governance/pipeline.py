from __future__ import annotations

from copy import deepcopy

from .identity import build_risk_family, build_risk_identity
from .rules import apply_family_severity_floor, infer_absorption_kind, merge_reason_for_family, pick_higher_severity
from .schemas import GovernedResult, GovernedRisk, GovernanceClusterEnvelope, GovernanceDecision, GovernanceInput


def _build_absorption_trace(
    *,
    absorbed_title: str,
    absorbed_rule_id: str,
    absorber: GovernedRisk,
    reason: str,
    kind: str,
) -> dict:
    return {
        "absorbed_title": absorbed_title,
        "absorbed_rule_id": absorbed_rule_id,
        "absorbed_by_title": absorber.decision.canonical_title,
        "absorbed_by_rule_id": absorber.identity.rule_id,
        "absorption_reason": reason,
        "absorption_kind": kind,
        "blocked_from_formal": True,
    }


def _append_absorption_trace(target: GovernedRisk, trace: dict) -> None:
    traces = list(target.extras.get("absorbed_risks", []))
    key = (trace.get("absorbed_title"), trace.get("absorbed_rule_id"), trace.get("absorbed_by_title"))
    existing_keys = {
        (item.get("absorbed_title"), item.get("absorbed_rule_id"), item.get("absorbed_by_title"))
        for item in traces
        if isinstance(item, dict)
    }
    if key not in existing_keys:
        traces.append(trace)
    target.extras["absorbed_risks"] = traces


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
        compare_source_bucket=layer,  # type: ignore[arg-type]
        title=title,
        review_type=review_type,
        severity=str(item.get("severity", "需人工复核")).strip() or "需人工复核",
        source_locations=[str(item.get("source_location", "")).strip()] if str(item.get("source_location", "")).strip() else [],
        source_excerpts=[str(item.get("source_excerpt", "")).strip()] if str(item.get("source_excerpt", "")).strip() else [],
        source_topics=[str(item.get("topic", "")).strip()] if str(item.get("topic", "")).strip() else [],
        governance_reason=str(item.get("reason", "")).strip() or "由 compare 元数据进入输出治理层。",
        extras={
            **{k: v for k, v in item.items() if k not in {"title", "review_type", "severity", "source_location", "source_excerpt", "topic", "reason"}},
            "compare_source_bucket": layer,
        },
    )


def _expand_cluster_envelopes(cluster) -> list[GovernanceClusterEnvelope]:
    envelope = GovernanceClusterEnvelope.from_cluster(cluster)
    source_blob = "\n".join([envelope.title, *envelope.source_excerpts, *envelope.risk_judgment])

    if "技术参数引用错误标准及标准号存疑" not in source_blob:
        return [envelope]

    expanded: list[GovernanceClusterEnvelope] = []
    if any(token in source_blob for token in ["错误标准", "异常标准", "汽车车门把手标准", "标准号存疑"]):
        abnormal = deepcopy(envelope)
        abnormal.title = "技术参数存在错误或异常标准引用，可能导致技术要求失真"
        abnormal.risk_judgment = [
            item
            for item in abnormal.risk_judgment
            if any(token in item for token in ["错误", "异常标准", "汽车车门把手标准", "标准号"])
        ] or list(envelope.risk_judgment)
        abnormal.extras["absorbed_risks"] = [
            {
                "absorbed_title": envelope.title,
                "absorbed_rule_id": "",
                "absorbed_by_title": abnormal.title,
                "absorbed_by_rule_id": "",
                "absorption_reason": "旧混合标题已拆分为更具体的标准错误风险输出，避免与拆分后的正式风险并列重复。",
                "absorption_kind": "legacy_mixed_title",
                "blocked_from_formal": True,
            }
        ]
        expanded.append(abnormal)
    if any(token in source_blob for token in ["福建省检测机构", "地域限制"]):
        regional = deepcopy(envelope)
        regional.title = "检测报告限定福建省检测机构，存在检测机构地域限制风险"
        regional.risk_judgment = [
            item for item in regional.risk_judgment if any(token in item for token in ["福建省检测机构", "地域限制"])
        ] or list(envelope.risk_judgment)
        regional.extras["absorbed_risks"] = [
            {
                "absorbed_title": envelope.title,
                "absorbed_rule_id": "",
                "absorbed_by_title": regional.title,
                "absorbed_by_rule_id": "",
                "absorption_reason": "旧混合标题已拆分为更具体的检测机构地域限制风险输出，避免与拆分后的正式风险并列重复。",
                "absorption_kind": "legacy_mixed_title",
                "blocked_from_formal": True,
            }
        ]
        expanded.append(regional)
    return expanded or [envelope]


def _govern_envelope(envelope: GovernanceClusterEnvelope) -> GovernedRisk:
    family = build_risk_family(envelope)
    identity = build_risk_identity(envelope, family)
    normalized_severity = apply_family_severity_floor(family.family_key, envelope.severity)
    governance_reason = envelope.governance_reason or "输出治理层已完成标题规范、规则归属与候选对象标准化。"
    decision = GovernanceDecision(
        governance_reason=governance_reason,
        proposed_title=envelope.title,
        canonical_title=family.canonical_title,
    )
    extras = dict(envelope.extras)
    extras.setdefault("compare_source_bucket", envelope.compare_source_bucket)
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
        extras=extras,
    )


def _merge_into_existing(existing: GovernedRisk, item: GovernedRisk) -> GovernedRisk:
    absorption_reason = merge_reason_for_family(existing.family.family_key)
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
    existing.decision.governance_reason = absorption_reason

    _append_absorption_trace(
        existing,
        _build_absorption_trace(
            absorbed_title=item.decision.proposed_title,
            absorbed_rule_id=item.identity.rule_id,
            absorber=existing,
            reason=absorption_reason,
            kind=infer_absorption_kind(existing.family.family_key, item.decision.proposed_title, existing.decision.canonical_title),
        ),
    )
    for trace in item.extras.get("absorbed_risks", []):
        if isinstance(trace, dict):
            _append_absorption_trace(existing, trace)

    compare_buckets = [
        *existing.extras.get("compare_source_buckets", [existing.extras.get("compare_source_bucket", "formal_risks")]),
        *item.extras.get("compare_source_buckets", [item.extras.get("compare_source_bucket", "formal_risks")]),
    ]
    existing.extras["compare_source_buckets"] = list(dict.fromkeys(str(bucket) for bucket in compare_buckets if str(bucket).strip()))
    existing.extras["compare_source_bucket"] = existing.extras["compare_source_buckets"][0]
    return existing


def _merge_governed_risks(items: list[GovernedRisk]) -> list[GovernedRisk]:
    merged: dict[str, GovernedRisk] = {}
    for item in items:
        key = item.family.family_key
        if key not in merged:
            item.decision.canonical_title = item.family.canonical_title
            item.extras["compare_source_buckets"] = [
                item.extras.get("compare_source_bucket", "formal_risks"),
            ]
            merged[key] = item
            continue
        merged[key] = _merge_into_existing(merged[key], item)
    return list(merged.values())


def validate_governed_result(result: GovernedResult) -> None:
    family_keys = [item.family.family_key for item in result.iter_all()]
    duplicates = sorted({family for family in family_keys if family_keys.count(family) > 1})
    if duplicates:
        raise ValueError(f"duplicate governed families remain after governance: {duplicates}")


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
    governed_clusters = []
    for cluster in comparison.clusters:
        for envelope in _expand_cluster_envelopes(cluster):
            envelope.governance_reason = "由 compare 候选风险进入输出治理层。"
            governed_clusters.append(_govern_envelope(envelope))
    pending_items = comparison.metadata.get("pending_review_items", []) if isinstance(comparison.metadata, dict) else []
    excluded_items = comparison.metadata.get("excluded_risks", []) if isinstance(comparison.metadata, dict) else []
    governed_pending = [_govern_envelope(_coerce_pending_or_excluded(item, "pending_review_items")) for item in pending_items]
    governed_excluded = [_govern_envelope(_coerce_pending_or_excluded(item, "excluded_risks")) for item in excluded_items]
    result.governed_candidates = _merge_governed_risks([*governed_clusters, *governed_pending, *governed_excluded])
    result.input_summary["governance_input"] = governance_input.to_dict()
    validate_governed_result(result)
    return result
