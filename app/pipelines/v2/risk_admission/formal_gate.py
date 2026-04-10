from __future__ import annotations

import re
from dataclasses import dataclass

from .formal_registry import resolve_formal_registry_resolution
from .schemas import AdmissionLayer, AdmissionSourceType, EvidenceKind
from .whitelist import match_formal_exception_whitelist


HARD_EVIDENCE_KINDS: set[EvidenceKind] = {
    "body_clause",
    "scoring_clause",
    "qualification_clause",
    "acceptance_clause",
}
ABSORBED_SUPPORTING_ITEM_RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "absorbed_supporting_item_block",
        re.compile(r"(电磁兼容标准引用格式混乱且编号不完整|标准编号与名称引用混乱且缺失版本信息)"),
        "该条属于主风险的补充佐证，已被主风险吸收，不再单独进入正式风险。",
    ),
]


@dataclass
class FormalGateResult:
    target_layer: AdmissionLayer
    passed: bool
    reason: str
    rule: str
    whitelist_hit: bool
    family_allowed: bool
    evidence_passed: bool
    registry_rule_id: str
    registry_status: str
    registry_source: str
    registry_resolution: str


def _build_source_blob(title: str, governance_reason: str, *parts: str) -> str:
    return "\n".join(item for item in [title, governance_reason, *parts] if item)


def _has_explicit_body_evidence(
    *,
    evidence_kind: EvidenceKind,
    source_type: AdmissionSourceType,
    source_excerpts: list[str],
    source_locations: list[str],
    allow_weak_source: bool = False,
) -> bool:
    return (
        evidence_kind in HARD_EVIDENCE_KINDS
        and (allow_weak_source or source_type != "warning_only")
        and any(str(item).strip() for item in source_excerpts)
        and any(str(item).strip() for item in source_locations)
    )


def evaluate_formal_gate(
    *,
    rule_id: str,
    family_key: str,
    title: str,
    proposed_title: str,
    governance_reason: str,
    evidence_kind: EvidenceKind,
    source_type: AdmissionSourceType,
    compare_source_bucket: str,
    source_locations: list[str],
    source_excerpts: list[str],
    risk_judgment: list[str],
) -> FormalGateResult | None:
    source_blob = _build_source_blob(title, proposed_title, governance_reason, *source_excerpts, *risk_judgment)
    evidence_passed = _has_explicit_body_evidence(
        evidence_kind=evidence_kind,
        source_type=source_type,
        source_excerpts=source_excerpts,
        source_locations=source_locations,
    )
    registry_resolution = resolve_formal_registry_resolution(rule_id=rule_id, family_key=family_key, title=title)
    registry_entry = registry_resolution.entry
    family_allowed = bool(registry_entry and registry_entry.allow_formal)
    requires_hard_evidence = True if registry_entry is None else registry_entry.requires_hard_evidence
    if not evidence_passed and registry_resolution.outcome == "matched" and compare_source_bucket in {
        "formal_risks",
        "pending_review_items",
    }:
        evidence_passed = _has_explicit_body_evidence(
            evidence_kind=evidence_kind,
            source_type=source_type,
            source_excerpts=source_excerpts,
            source_locations=source_locations,
            allow_weak_source=True,
        )
    registry_rule_id = registry_entry.rule_id if registry_entry is not None else ""
    registry_status = registry_entry.status if registry_entry is not None else ""
    registry_source = registry_entry.source if registry_entry is not None else ""

    for rule_name, pattern, reason in ABSORBED_SUPPORTING_ITEM_RULES:
        if pattern.search(source_blob):
            return FormalGateResult(
                "excluded_risks",
                False,
                reason,
                rule_name,
                False,
                family_allowed,
                evidence_passed,
                registry_rule_id,
                registry_status,
                registry_source,
                registry_resolution.outcome,
            )

    whitelist = match_formal_exception_whitelist(title, source_blob)
    if whitelist is not None:
        rule_name, reason = whitelist
        return FormalGateResult(
            "formal_risks",
            True,
            reason,
            "formal_whitelist",
            True,
            family_allowed,
            evidence_passed,
            registry_rule_id,
            registry_status,
            registry_source,
            registry_resolution.outcome,
        )

    if registry_resolution.outcome == "mismatch":
        return FormalGateResult(
            "pending_review_items",
            False,
            registry_resolution.reason,
            "registry_mapping_mismatch_block",
            False,
            False,
            evidence_passed,
            registry_rule_id,
            registry_status,
            registry_source,
            registry_resolution.outcome,
        )

    if compare_source_bucket == "excluded_risks":
        return FormalGateResult(
            "excluded_risks",
            False,
            "compare 来源曾标注为已剔除项，当前 admission 未发现足以升格的正文硬证据，暂保留为排除层。",
            "compare_bucket_fallback",
            False,
            family_allowed,
            evidence_passed,
            registry_rule_id,
            registry_status,
            registry_source,
            registry_resolution.outcome,
        )

    if registry_resolution.outcome == "missing":
        return FormalGateResult(
            "pending_review_items",
            False,
            registry_resolution.reason,
            "registry_mapping_missing_block",
            False,
            False,
            evidence_passed,
            "",
            "",
            "",
            registry_resolution.outcome,
        )

    if registry_entry is not None and not registry_entry.allow_formal:
        return FormalGateResult(
            "pending_review_items",
            False,
            "当前已命中 formal registry，但对应规则尚未正式纳管或未开放 formal 准入，先转待补证复核项。",
            "registry_inactive_block",
            False,
            False,
            evidence_passed,
            registry_rule_id,
            registry_status,
            registry_source,
            registry_resolution.outcome,
        )

    if family_allowed and (evidence_passed or not requires_hard_evidence):
        return FormalGateResult(
            "formal_risks",
            True,
            "命中 formal registry/治理单源配置，且具备正文硬证据，可进入正式风险。",
            "registry_family_hard_evidence_gate",
            False,
            True,
            evidence_passed,
            registry_rule_id,
            registry_status,
            registry_source,
            registry_resolution.outcome,
        )

    if evidence_passed and not family_allowed:
        return FormalGateResult(
            "pending_review_items",
            False,
            "当前虽具备正文硬证据，但 formal registry 未放行该规则/家族进入正式风险，先转待补证复核项。",
            "registry_family_gate_block",
            False,
            False,
            True,
            registry_rule_id,
            registry_status,
            registry_source,
            registry_resolution.outcome,
        )

    if family_allowed and not evidence_passed:
        return FormalGateResult(
            "pending_review_items",
            False,
            "当前规则/家族已被 formal registry 放行，但正文硬证据不足，先转待补证复核项。",
            "registry_family_evidence_block",
            False,
            True,
            False,
            registry_rule_id,
            registry_status,
            registry_source,
            registry_resolution.outcome,
        )

    return FormalGateResult(
        "pending_review_items",
        False,
        "当前未满足 formal 准入门槛，且无例外白名单命中，先保留为待补证复核项。",
        "formal_gate_default_pending",
        False,
        family_allowed,
        evidence_passed,
        registry_rule_id,
        registry_status,
        registry_source,
        registry_resolution.outcome,
    )
