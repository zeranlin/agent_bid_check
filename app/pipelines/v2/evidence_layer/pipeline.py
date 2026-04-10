from __future__ import annotations

import json
from hashlib import md5

from app.pipelines.v2.schemas import V2StageArtifact

from .classifier import (
    classify_business_domain,
    classify_clause_role,
    classify_evidence_strength,
    classify_hard_evidence,
    classify_source_kind,
)
from .models import Evidence, EvidenceLayerArtifact, TopicEvidenceInput


def _section_key(section: dict[str, object]) -> str:
    return f"{section.get('start_line', 0)}-{section.get('end_line', 0)}-{section.get('title', '')}"


def _location_text(section: dict[str, object]) -> str:
    title = str(section.get("title", "")).strip() or "未命名章节"
    start_line = int(section.get("start_line", 0) or 0)
    end_line = int(section.get("end_line", 0) or 0)
    if start_line and end_line:
        return f"{title}（第 {start_line}-{end_line} 行）"
    return title


def _excerpt_text(section: dict[str, object]) -> str:
    excerpt = str(section.get("excerpt", "")).strip()
    if excerpt:
        return excerpt
    body = str(section.get("body", "")).strip()
    return body[:180] if body else "未发现"


def _evidence_id(section: dict[str, object]) -> str:
    digest = md5(_section_key(section).encode("utf-8")).hexdigest()[:10]
    return f"evidence-{digest}"


def build_evidence_layer(
    document_name: str,
    structure: V2StageArtifact,
    evidence_map: V2StageArtifact,
) -> EvidenceLayerArtifact:
    bundle_map = evidence_map.metadata.get("topic_evidence_bundles", {}) if evidence_map.metadata else {}
    coverage_map = evidence_map.metadata.get("topic_coverages", {}) if evidence_map.metadata else {}

    evidence_by_key: dict[str, Evidence] = {}
    section_payload_by_key: dict[str, dict[str, object]] = {}
    topic_inputs: dict[str, TopicEvidenceInput] = {}

    for topic_key, bundle in bundle_map.items():
        if not isinstance(bundle, dict):
            continue
        sections = bundle.get("sections", []) if isinstance(bundle.get("sections", []), list) else []
        topic_sections: list[dict[str, object]] = []
        topic_evidence_ids: list[str] = []
        for raw_section in sections:
            if not isinstance(raw_section, dict):
                continue
            section = dict(raw_section)
            key = _section_key(section)
            evidence = evidence_by_key.get(key)
            if evidence is None:
                source_trace = classify_source_kind(section)
                business_trace = classify_business_domain(section)
                role_trace = classify_clause_role(section)
                strength_trace = classify_evidence_strength(section)
                hard_evidence_trace = classify_hard_evidence(section)
                evidence = Evidence(
                    evidence_id=_evidence_id(section),
                    excerpt=_excerpt_text(section),
                    location=_location_text(section),
                    source_kind=source_trace["source_kind"],
                    business_domain=business_trace["business_domain"],
                    clause_role=role_trace["clause_role"],
                    evidence_strength=strength_trace["evidence_strength"],
                    hard_evidence=hard_evidence_trace["hard_evidence"],
                    topic_hints=[str(topic_key).strip()],
                    metadata={
                        "section_title": str(section.get("title", "")).strip(),
                        "start_line": int(section.get("start_line", 0) or 0),
                        "end_line": int(section.get("end_line", 0) or 0),
                        "module": str(section.get("module", "")).strip(),
                        "source_kind_trace": source_trace,
                        "business_domain_trace": business_trace,
                        "clause_role_trace": role_trace,
                        "evidence_strength_trace": strength_trace,
                        "hard_evidence_trace": hard_evidence_trace,
                    },
                )
                evidence_by_key[key] = evidence
                section_payload_by_key[key] = {
                    **section,
                    "evidence_id": evidence.evidence_id,
                    "location": evidence.location,
                    "excerpt": evidence.excerpt,
                    "source_kind": evidence.source_kind,
                    "source_kind_trace": source_trace,
                    "business_domain": evidence.business_domain,
                    "business_domain_trace": business_trace,
                    "clause_role": evidence.clause_role,
                    "clause_role_trace": role_trace,
                    "evidence_strength": evidence.evidence_strength,
                    "evidence_strength_trace": strength_trace,
                    "hard_evidence": evidence.hard_evidence,
                    "hard_evidence_trace": hard_evidence_trace,
                }
            elif topic_key not in evidence.topic_hints:
                evidence.topic_hints.append(str(topic_key).strip())
            topic_sections.append(section_payload_by_key[key])
            topic_evidence_ids.append(evidence.evidence_id)

        topic_inputs[str(topic_key)] = TopicEvidenceInput(
            topic_key=str(topic_key),
            sections=topic_sections,
            evidence_ids=list(dict.fromkeys(topic_evidence_ids)),
            coverage=coverage_map.get(topic_key, {}) if isinstance(coverage_map.get(topic_key, {}), dict) else {},
            metadata={
                **(dict(bundle.get("metadata", {})) if isinstance(bundle.get("metadata", {}), dict) else {}),
                "missing_hints": list(bundle.get("missing_hints", [])) if isinstance(bundle.get("missing_hints", []), list) else [],
                "recall_query": str(bundle.get("recall_query", "")).strip(),
            },
        )

    content_payload = {
        "document_name": document_name,
        "evidence_count": len(evidence_by_key),
        "topic_count": len(topic_inputs),
        "evidences": [item.to_dict() for item in evidence_by_key.values()],
        "topic_inputs": {key: value.to_dict() for key, value in topic_inputs.items()},
    }
    content = json.dumps(content_payload, ensure_ascii=False, indent=2)
    return EvidenceLayerArtifact(
        document_name=document_name,
        evidences=list(evidence_by_key.values()),
        topic_inputs=topic_inputs,
        metadata={
            "evidence_count": len(evidence_by_key),
            "topic_inputs_count": len(topic_inputs),
            "topic_coverages": coverage_map,
            "source_structure_sections": len(structure.metadata.get("sections", [])) if structure.metadata else 0,
        },
        content=content,
        raw_output=content,
    )
