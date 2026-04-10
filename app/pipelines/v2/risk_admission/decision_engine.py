from __future__ import annotations

from app.pipelines.v2.output_governance.schemas import GovernedRisk
from app.pipelines.v2.problem_layer.models import Problem

from .evidence_classifier import infer_evidence_kind
from .rules import build_admission_decision
from .schemas import AdmissionCandidate
from .source_classifier import infer_source_type


LAYER_PRIORITY = {"formal_risks": 3, "pending_review_items": 2, "excluded_risks": 1}


def _pick_winner_input_bucket(problem: Problem) -> str:
    buckets = [
        str(item.get("source_bucket", "")).strip()
        for item in problem.layer_conflict_inputs
        if isinstance(item, dict) and str(item.get("source_bucket", "")).strip()
    ]
    if not buckets:
        return str(problem.primary_candidate.extras.get("compare_source_bucket", "formal_risks"))
    return sorted(set(buckets), key=lambda item: (-LAYER_PRIORITY.get(item, 0), item))[0]


def admit_governed_risk(governed_risk: GovernedRisk) -> tuple[AdmissionCandidate, object]:
    compare_source_bucket = str(governed_risk.extras.get("compare_source_bucket", "formal_risks"))
    evidence_kind = infer_evidence_kind(
        review_type=governed_risk.review_type,
        title=governed_risk.decision.canonical_title,
        source_locations=governed_risk.source_locations,
        source_excerpts=governed_risk.source_excerpts,
    )
    source_type = infer_source_type(governed_risk.source_rules)
    if source_type == "warning_only" and compare_source_bucket == "formal_risks":
        source_type = "candidate_rule"
    decision = build_admission_decision(
        rule_id=governed_risk.identity.rule_id,
        family_key=governed_risk.family.family_key,
        title=governed_risk.decision.canonical_title,
        proposed_title=governed_risk.decision.proposed_title,
        governance_reason=governed_risk.decision.governance_reason,
        evidence_kind=evidence_kind,
        source_type=source_type,
        compare_source_bucket=compare_source_bucket,
        compare_source_buckets=[str(item) for item in governed_risk.extras.get("compare_source_buckets", [])],
        severity=governed_risk.severity,
        need_manual_review=governed_risk.need_manual_review,
        source_locations=governed_risk.source_locations,
        source_excerpts=governed_risk.source_excerpts,
        risk_judgment=governed_risk.risk_judgment,
    )
    candidate = AdmissionCandidate.from_governed_risk(
        governed_risk,
        evidence_kind=evidence_kind,
        source_type=source_type,
    )
    return candidate, decision


def admit_problem(problem: Problem) -> tuple[AdmissionCandidate, object]:
    primary = problem.primary_candidate
    compare_source_bucket = _pick_winner_input_bucket(problem)
    merged_locations = list(dict.fromkeys(location for item in [primary, *problem.supporting_candidates] for location in item.source_locations))
    merged_excerpts = list(dict.fromkeys(excerpt for item in [primary, *problem.supporting_candidates] for excerpt in item.source_excerpts))
    merged_judgment = list(dict.fromkeys(judgment for item in [primary, *problem.supporting_candidates] for judgment in item.risk_judgment))
    evidence_kind = infer_evidence_kind(
        review_type=primary.review_type,
        title=problem.canonical_title,
        source_locations=merged_locations,
        source_excerpts=merged_excerpts,
    )
    source_type = infer_source_type(list(dict.fromkeys(rule for item in [primary, *problem.supporting_candidates] for rule in item.source_rules)))
    if source_type == "warning_only" and compare_source_bucket == "formal_risks":
        source_type = "candidate_rule"
    decision = build_admission_decision(
        rule_id=primary.identity.rule_id,
        family_key=problem.family_key,
        title=problem.canonical_title,
        proposed_title=primary.decision.proposed_title,
        governance_reason=primary.decision.governance_reason,
        evidence_kind=evidence_kind,
        source_type=source_type,
        compare_source_bucket=compare_source_bucket,
        compare_source_buckets=list(dict.fromkeys(str(item.get("source_bucket", "")).strip() for item in problem.layer_conflict_inputs if str(item.get("source_bucket", "")).strip())),
        severity=primary.severity,
        need_manual_review=primary.need_manual_review,
        source_locations=merged_locations,
        source_excerpts=merged_excerpts,
        risk_judgment=merged_judgment,
    )
    final_resolution = {
        "target_layer": decision.target_layer,
        "winner_input_bucket": compare_source_bucket,
        "winner_rule_id": primary.identity.rule_id,
        "winner_basis": "problem_conflict_resolution_priority",
        "conflict_reason": "同一问题的多来源输入已在 admission 前按 formal > pending > excluded 的优先顺序统一选择输入层，并再由 admission 规则完成最终裁决。",
        "admission_reason": decision.admission_reason,
    }
    problem.final_problem_resolution = dict(final_resolution)
    problem.trace["final_problem_resolution"] = dict(final_resolution)
    candidate = AdmissionCandidate.from_problem(
        problem,
        evidence_kind=evidence_kind,
        source_type=source_type,
    )
    return candidate, decision
