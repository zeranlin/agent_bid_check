from __future__ import annotations

from app.pipelines.v2.output_governance.schemas import GovernedRisk

from .evidence_classifier import infer_evidence_kind
from .rules import build_admission_decision
from .schemas import AdmissionCandidate
from .source_classifier import infer_source_type


def admit_governed_risk(governed_risk: GovernedRisk) -> tuple[AdmissionCandidate, object]:
    evidence_kind = infer_evidence_kind(
        review_type=governed_risk.review_type,
        title=governed_risk.decision.canonical_title,
        source_locations=governed_risk.source_locations,
        source_excerpts=governed_risk.source_excerpts,
    )
    source_type = infer_source_type(governed_risk.source_rules)
    decision = build_admission_decision(
        governed_target_layer=governed_risk.decision.target_layer,
        title=governed_risk.decision.canonical_title,
        governance_reason=governed_risk.decision.governance_reason,
        evidence_kind=evidence_kind,
        source_type=source_type,
        source_excerpts=governed_risk.source_excerpts,
        risk_judgment=governed_risk.risk_judgment,
    )
    candidate = AdmissionCandidate.from_governed_risk(
        governed_risk,
        evidence_kind=evidence_kind,
        source_type=source_type,
    )
    return candidate, decision
