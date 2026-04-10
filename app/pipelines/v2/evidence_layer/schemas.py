from __future__ import annotations

from typing import Literal


SourceKind = Literal[
    "unknown",
    "body_clause",
    "template_clause",
    "placeholder_clause",
    "contract_template",
    "attachment_clause",
    "reminder_clause",
    "form_clause",
    "sample_clause",
]
BusinessDomain = Literal[
    "unknown",
    "qualification",
    "scoring",
    "technical",
    "technical_standard",
    "commercial",
    "acceptance",
    "policy",
    "procedure",
    "sample",
    "performance_staff",
]
ClauseRole = Literal[
    "unknown",
    "gate",
    "scoring_factor",
    "technical_requirement",
    "acceptance_basis",
    "commercial_obligation",
    "supporting_material",
    "reminder",
]
EvidenceStrength = Literal["weak", "medium", "strong"]
