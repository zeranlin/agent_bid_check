from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from app.pipelines.v2.schemas import ComparisonArtifact, MergedRiskCluster


CompareSourceBucket = Literal["formal_risks", "pending_review_items", "excluded_risks"]


@dataclass
class RiskIdentity:
    rule_id: str
    risk_family: str
    source_topics: list[str] = field(default_factory=list)
    evidence_anchors: list[str] = field(default_factory=list)
    document_span: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RiskFamily:
    family_key: str
    canonical_title: str
    source_topics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GovernanceDecision:
    governance_reason: str
    proposed_title: str
    canonical_title: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GovernedRisk:
    identity: RiskIdentity
    family: RiskFamily
    decision: GovernanceDecision
    review_type: str
    severity: str
    source_locations: list[str] = field(default_factory=list)
    source_excerpts: list[str] = field(default_factory=list)
    risk_judgment: list[str] = field(default_factory=list)
    legal_basis: list[str] = field(default_factory=list)
    rectification: list[str] = field(default_factory=list)
    source_rules: list[str] = field(default_factory=list)
    need_manual_review: bool = False
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["identity"] = self.identity.to_dict()
        payload["family"] = self.family.to_dict()
        payload["decision"] = self.decision.to_dict()
        return payload


@dataclass
class GovernanceInput:
    document_name: str
    comparison: ComparisonArtifact

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_name": self.document_name,
            "comparison": self.comparison.to_dict(),
        }


@dataclass
class GovernedResult:
    document_name: str
    input_summary: dict[str, Any] = field(default_factory=dict)
    governed_candidates: list[GovernedRisk] = field(default_factory=list)

    def iter_all(self) -> list[GovernedRisk]:
        return list(self.governed_candidates)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_name": self.document_name,
            "input_summary": dict(self.input_summary),
            "governed_candidates": [item.to_dict() for item in self.governed_candidates],
        }


@dataclass
class GovernanceClusterEnvelope:
    compare_source_bucket: CompareSourceBucket
    title: str
    review_type: str
    severity: str
    source_locations: list[str] = field(default_factory=list)
    source_excerpts: list[str] = field(default_factory=list)
    risk_judgment: list[str] = field(default_factory=list)
    legal_basis: list[str] = field(default_factory=list)
    rectification: list[str] = field(default_factory=list)
    source_topics: list[str] = field(default_factory=list)
    source_rules: list[str] = field(default_factory=list)
    need_manual_review: bool = False
    governance_reason: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_cluster(cls, cluster: MergedRiskCluster) -> "GovernanceClusterEnvelope":
        return cls(
            compare_source_bucket="formal_risks",
            title=cluster.title,
            review_type=cluster.review_type,
            severity=cluster.severity,
            source_locations=list(cluster.source_locations),
            source_excerpts=list(cluster.source_excerpts),
            risk_judgment=list(cluster.risk_judgment),
            legal_basis=list(cluster.legal_basis),
            rectification=list(cluster.rectification),
            source_topics=list(cluster.topics),
            source_rules=list(cluster.source_rules),
            need_manual_review=cluster.need_manual_review,
            governance_reason="由 compare 层候选正式风险进入输出治理层，等待统一治理裁决。",
        )
