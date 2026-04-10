from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from app.pipelines.v2.output_governance.schemas import GovernedRisk


EvidenceKind = Literal[
    "body_clause",
    "scoring_clause",
    "qualification_clause",
    "acceptance_clause",
    "contract_template",
    "declaration_template",
    "joint_venture_template",
    "subcontract_template",
    "attachment_instruction",
    "optional_form",
    "unknown",
]

AdmissionSourceType = Literal[
    "formal_rule",
    "candidate_rule",
    "compare_rule",
    "topic_inference",
    "completeness_hint",
    "warning_only",
]

AdmissionLayer = Literal["formal_risks", "pending_review_items", "excluded_risks"]


@dataclass
class AdmissionDecision:
    target_layer: AdmissionLayer
    admission_reason: str
    evidence_kind: EvidenceKind
    source_type: AdmissionSourceType
    formal_gate_passed: bool = False
    formal_gate_reason: str = ""
    formal_gate_rule: str = ""
    formal_gate_exception_whitelist_hit: bool = False
    formal_gate_family_allowed: bool = False
    formal_gate_evidence_passed: bool = False
    formal_gate_registry_rule_id: str = ""
    formal_gate_registry_status: str = ""
    formal_gate_registry_source: str = ""
    formal_gate_registry_resolution: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AdmissionCandidate:
    rule_id: str
    risk_family: str
    title: str
    review_type: str
    severity: str
    evidence_kind: EvidenceKind
    source_type: AdmissionSourceType
    governance_reason: str = ""
    source_locations: list[str] = field(default_factory=list)
    source_excerpts: list[str] = field(default_factory=list)
    source_rules: list[str] = field(default_factory=list)
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_governed_risk(
        cls,
        governed_risk: GovernedRisk,
        *,
        evidence_kind: EvidenceKind,
        source_type: AdmissionSourceType,
    ) -> "AdmissionCandidate":
        return cls(
            rule_id=governed_risk.identity.rule_id,
            risk_family=governed_risk.family.family_key,
            title=governed_risk.decision.canonical_title,
            review_type=governed_risk.review_type,
            severity=governed_risk.severity,
            evidence_kind=evidence_kind,
            source_type=source_type,
            governance_reason=governed_risk.decision.governance_reason,
            source_locations=list(governed_risk.source_locations),
            source_excerpts=list(governed_risk.source_excerpts),
            source_rules=list(governed_risk.source_rules),
            extras={
                **dict(governed_risk.extras),
                "governance_proposed_title": governed_risk.decision.proposed_title,
                "governance_canonical_title": governed_risk.decision.canonical_title,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AdmissionInput:
    document_name: str
    comparison_summary: dict[str, Any] = field(default_factory=dict)
    governance_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AdmissionResult:
    document_name: str
    input_summary: dict[str, Any] = field(default_factory=dict)
    formal_risks: list[AdmissionCandidate] = field(default_factory=list)
    pending_review_items: list[AdmissionCandidate] = field(default_factory=list)
    excluded_risks: list[AdmissionCandidate] = field(default_factory=list)
    decisions: dict[str, AdmissionDecision] = field(default_factory=dict)

    def iter_all(self) -> list[AdmissionCandidate]:
        return [*self.formal_risks, *self.pending_review_items, *self.excluded_risks]

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_name": self.document_name,
            "input_summary": dict(self.input_summary),
            "formal_risks": [item.to_dict() for item in self.formal_risks],
            "pending_review_items": [item.to_dict() for item in self.pending_review_items],
            "excluded_risks": [item.to_dict() for item in self.excluded_risks],
            "decisions": {rule_id: decision.to_dict() for rule_id, decision in self.decisions.items()},
        }
