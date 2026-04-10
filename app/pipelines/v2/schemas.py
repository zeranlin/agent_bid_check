from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.common.schemas import RiskPoint


@dataclass
class SectionCandidate:
    title: str
    start_line: int
    end_line: int
    body: str = ""
    excerpt: str = ""
    module: str = "procedure"
    module_scores: dict[str, int] = field(default_factory=dict)
    confidence: int = 0
    keywords: list[str] = field(default_factory=list)
    heading_level: int = 0
    source: str = "rule_split"

    @property
    def line_span(self) -> int:
        return max(self.end_line - self.start_line + 1, 0)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ModuleHit:
    module: str
    score: float
    source: str = "rule"
    reason: str = ""
    evidence_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceBundle:
    topic: str
    sections: list[SectionCandidate] = field(default_factory=list)
    primary_section_ids: list[str] = field(default_factory=list)
    secondary_section_ids: list[str] = field(default_factory=list)
    missing_hints: list[str] = field(default_factory=list)
    recall_query: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["sections"] = [section.to_dict() for section in self.sections]
        return payload


@dataclass
class TopicCoverage:
    topic: str
    covered_modules: list[str] = field(default_factory=list)
    covered_section_ids: list[str] = field(default_factory=list)
    missing_modules: list[str] = field(default_factory=list)
    missing_hints: list[str] = field(default_factory=list)
    need_manual_review: bool = False
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RiskSignature:
    topic: str
    title: str
    review_type: str
    source_locations: list[str] = field(default_factory=list)
    source_excerpt_hash: str = ""
    severity: str = "需人工复核"
    source_rule: str = "topic"
    source_excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MergedRiskCluster:
    cluster_id: str
    title: str
    severity: str
    review_type: str
    source_locations: list[str] = field(default_factory=list)
    source_excerpts: list[str] = field(default_factory=list)
    risk_judgment: list[str] = field(default_factory=list)
    legal_basis: list[str] = field(default_factory=list)
    rectification: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    source_rules: list[str] = field(default_factory=list)
    conflict_notes: list[str] = field(default_factory=list)
    need_manual_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ComparisonArtifact:
    signatures: list[RiskSignature] = field(default_factory=list)
    clusters: list[MergedRiskCluster] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    coverage_summary: dict[str, Any] = field(default_factory=dict)
    comparison_summary: dict[str, Any] = field(default_factory=dict)
    baseline_only_risks: list[dict[str, Any]] = field(default_factory=list)
    topic_only_risks: list[dict[str, Any]] = field(default_factory=list)
    missing_topic_coverage: list[str] = field(default_factory=list)
    manual_review_items: list[str] = field(default_factory=list)
    coverage_gaps: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signatures": [item.to_dict() for item in self.signatures],
            "clusters": [item.to_dict() for item in self.clusters],
            "conflicts": self.conflicts,
            "coverage_summary": self.coverage_summary,
            "comparison_summary": self.comparison_summary,
            "baseline_only_risks": self.baseline_only_risks,
            "topic_only_risks": self.topic_only_risks,
            "missing_topic_coverage": self.missing_topic_coverage,
            "manual_review_items": self.manual_review_items,
            "coverage_gaps": self.coverage_gaps,
            "metadata": self.metadata,
        }


@dataclass
class V2StageArtifact:
    name: str
    content: str = ""
    raw_output: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TopicReviewArtifact:
    topic: str
    summary: str
    risk_points: list[RiskPoint] = field(default_factory=list)
    need_manual_review: bool = False
    coverage_note: str = ""
    raw_output: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class V2ReviewArtifacts:
    extracted_text: str
    baseline: V2StageArtifact
    structure: V2StageArtifact
    topics: list[TopicReviewArtifact]
    final_markdown: str
    evidence: V2StageArtifact | None = None
    comparison: ComparisonArtifact | None = None
    governance: Any | None = None
    admission: Any | None = None
