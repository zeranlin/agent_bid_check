from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .schemas import BusinessDomain, ClauseRole, EvidenceStrength, SourceKind


@dataclass
class Evidence:
    evidence_id: str
    excerpt: str
    location: str
    source_kind: SourceKind = "unknown"
    business_domain: BusinessDomain = "unknown"
    clause_role: ClauseRole = "unknown"
    evidence_strength: EvidenceStrength = "medium"
    hard_evidence: bool = False
    topic_hints: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TopicEvidenceInput:
    topic_key: str
    sections: list[dict[str, Any]] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    coverage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceLayerArtifact:
    document_name: str
    evidences: list[Evidence] = field(default_factory=list)
    topic_inputs: dict[str, TopicEvidenceInput] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    content: str = ""
    raw_output: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_name": self.document_name,
            "evidences": [item.to_dict() for item in self.evidences],
            "topic_inputs": {key: value.to_dict() for key, value in self.topic_inputs.items()},
            "metadata": dict(self.metadata),
        }
