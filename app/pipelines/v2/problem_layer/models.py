from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.pipelines.v2.output_governance.schemas import GovernedRisk


@dataclass
class Problem:
    problem_id: str
    canonical_title: str
    family_key: str
    primary_candidate: GovernedRisk
    problem_kind: str = "standard"
    supporting_candidates: list[GovernedRisk] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    topic_sources: list[str] = field(default_factory=list)
    rule_ids: list[str] = field(default_factory=list)
    merged_topic_sources: list[str] = field(default_factory=list)
    merged_family_keys: list[str] = field(default_factory=list)
    cross_topic_merge_reason: str = ""
    layer_conflict_inputs: list[dict[str, Any]] = field(default_factory=list)
    final_problem_resolution: dict[str, Any] = field(default_factory=dict)
    conflict_type: str = ""
    left_side: dict[str, Any] = field(default_factory=dict)
    right_side: dict[str, Any] = field(default_factory=dict)
    conflict_reason: dict[str, Any] = field(default_factory=dict)
    conflict_evidence_links: list[dict[str, Any]] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "problem_id": self.problem_id,
            "canonical_title": self.canonical_title,
            "family_key": self.family_key,
            "problem_kind": self.problem_kind,
            "primary_candidate": self.primary_candidate.to_dict(),
            "supporting_candidates": [item.to_dict() for item in self.supporting_candidates],
            "evidence_ids": list(self.evidence_ids),
            "topic_sources": list(self.topic_sources),
            "rule_ids": list(self.rule_ids),
            "merged_topic_sources": list(self.merged_topic_sources),
            "merged_family_keys": list(self.merged_family_keys),
            "cross_topic_merge_reason": self.cross_topic_merge_reason,
            "layer_conflict_inputs": list(self.layer_conflict_inputs),
            "final_problem_resolution": dict(self.final_problem_resolution),
            "conflict_type": self.conflict_type,
            "left_side": dict(self.left_side),
            "right_side": dict(self.right_side),
            "conflict_reason": dict(self.conflict_reason),
            "conflict_evidence_links": list(self.conflict_evidence_links),
            "trace": dict(self.trace),
        }


@dataclass
class ProblemLayerResult:
    document_name: str
    input_summary: dict[str, Any] = field(default_factory=dict)
    problems: list[Problem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_name": self.document_name,
            "input_summary": dict(self.input_summary),
            "problems": [item.to_dict() for item in self.problems],
        }
