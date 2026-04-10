from __future__ import annotations

from app.pipelines.v2.output_governance.schemas import GovernedRisk

from .evidence_classifier import infer_evidence_kind
from .rules import build_admission_decision
from .schemas import AdmissionCandidate
from .source_classifier import infer_source_type


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
