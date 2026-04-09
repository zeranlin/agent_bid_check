from __future__ import annotations

import hashlib
import re

from .rules import infer_family
from .schemas import GovernanceClusterEnvelope, RiskFamily, RiskIdentity


def _slug(text: str) -> str:
    compact = re.sub(r"[^\w\u4e00-\u9fff]+", "-", str(text or "").strip().lower())
    compact = compact.strip("-")
    return compact or "unclassified-risk"


def _anchor_hash(text: str) -> str:
    normalized = re.sub(r"\s+", "", str(text or "").strip())
    if not normalized:
        return ""
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()[:12]


def build_risk_family(envelope: GovernanceClusterEnvelope) -> RiskFamily:
    family_key, canonical_title = infer_family(
        envelope.title,
        envelope.review_type,
        *envelope.source_excerpts,
        *envelope.risk_judgment,
        *envelope.source_locations,
    )
    return RiskFamily(
        family_key=_slug(family_key),
        canonical_title=canonical_title,
        source_topics=list(dict.fromkeys(envelope.source_topics)),
    )


def build_risk_identity(envelope: GovernanceClusterEnvelope, family: RiskFamily) -> RiskIdentity:
    rule_candidates = [item for item in envelope.source_rules if str(item).strip()]
    compare_rule_codes = [item.split(":", 1)[1] for item in rule_candidates if item.startswith("compare_rule:")]
    if compare_rule_codes:
        rule_id = compare_rule_codes[0]
    elif "compare_rule" in rule_candidates:
        rule_id = f"compare::{family.family_key}"
    else:
        rule_id = f"topic::{family.family_key}"

    evidence_anchors = list(dict.fromkeys(filter(None, [_anchor_hash(item) for item in envelope.source_excerpts])))
    document_span = list(dict.fromkeys(str(item).strip() for item in envelope.source_locations if str(item).strip()))
    return RiskIdentity(
        rule_id=rule_id,
        risk_family=family.family_key,
        source_topics=list(dict.fromkeys(envelope.source_topics)),
        evidence_anchors=evidence_anchors,
        document_span=document_span,
    )
