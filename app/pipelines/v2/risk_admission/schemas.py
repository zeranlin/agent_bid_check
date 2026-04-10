from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from app.pipelines.v2.output_governance.schemas import GovernedRisk
from app.pipelines.v2.problem_layer.models import Problem


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
    pending_gate_reason_code: str = ""
    pending_gate_reason: str = ""
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

    @classmethod
    def from_problem(
        cls,
        problem: Problem,
        *,
        evidence_kind: EvidenceKind,
        source_type: AdmissionSourceType,
    ) -> "AdmissionCandidate":
        primary = problem.primary_candidate
        merged_locations = list(
            dict.fromkeys(
                location
                for item in [primary, *problem.supporting_candidates]
                for location in item.source_locations
            )
        )
        merged_excerpts = list(
            dict.fromkeys(
                excerpt
                for item in [primary, *problem.supporting_candidates]
                for excerpt in item.source_excerpts
            )
        )
        merged_source_rules = list(
            dict.fromkeys(
                rule
                for item in [primary, *problem.supporting_candidates]
                for rule in item.source_rules
            )
        )
        return cls(
            rule_id=primary.identity.rule_id,
            risk_family=problem.family_key,
            title=problem.canonical_title,
            review_type=primary.review_type,
            severity=primary.severity,
            evidence_kind=evidence_kind,
            source_type=source_type,
            governance_reason=primary.decision.governance_reason,
            source_locations=merged_locations,
            source_excerpts=merged_excerpts,
            source_rules=merged_source_rules,
            extras={
                **dict(primary.extras),
                "problem_id": problem.problem_id,
                "problem_rule_ids": list(problem.rule_ids),
                "problem_source_rules": list(merged_source_rules),
                "problem_evidence_ids": list(problem.evidence_ids),
                "problem_topic_sources": list(problem.topic_sources),
                "problem_supporting_candidate_rule_ids": [item.identity.rule_id for item in problem.supporting_candidates],
                "problem_supporting_candidate_titles": [item.decision.canonical_title for item in problem.supporting_candidates],
                "merged_topic_sources": list(problem.merged_topic_sources),
                "merged_family_keys": list(problem.merged_family_keys),
                "cross_topic_merge_reason": problem.cross_topic_merge_reason,
                "layer_conflict_inputs": list(problem.layer_conflict_inputs),
                "final_problem_resolution": dict(problem.final_problem_resolution),
                "problem_kind": problem.problem_kind,
                "conflict_type": problem.conflict_type,
                "left_side": dict(problem.left_side),
                "right_side": dict(problem.right_side),
                "conflict_reason": dict(problem.conflict_reason),
                "conflict_evidence_links": list(problem.conflict_evidence_links),
                "problem_trace": dict(problem.trace),
                "governance_proposed_title": primary.decision.proposed_title,
                "governance_canonical_title": primary.decision.canonical_title,
            },
        )


@dataclass
class AdmissionInput:
    document_name: str
    comparison_summary: dict[str, Any] = field(default_factory=dict)
    governance_summary: dict[str, Any] = field(default_factory=dict)
    problem_summary: dict[str, Any] = field(default_factory=dict)

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
