from __future__ import annotations

import json

from .schemas import EvidenceBundle, ModuleHit, SectionCandidate, TopicCoverage, V2StageArtifact
from .topics import TOPIC_TAXONOMY, TopicDefinition, resolve_topic_definitions, resolve_topic_execution_plan


def _section_id(section: SectionCandidate) -> str:
    return f"{section.start_line}-{section.end_line}"


def _to_section_candidate(payload: dict) -> SectionCandidate:
    return SectionCandidate(
        title=str(payload.get("title", "")).strip() or "未命名章节",
        start_line=int(payload.get("start_line", 0) or 0),
        end_line=int(payload.get("end_line", 0) or 0),
        body=str(payload.get("body", "")).strip(),
        excerpt=str(payload.get("excerpt", "")).strip(),
        module=str(payload.get("module", "")).strip() or "procedure",
        module_scores=dict(payload.get("module_scores", {}) or {}),
        confidence=int(payload.get("confidence", 0) or 0),
        keywords=[str(item).strip() for item in payload.get("keywords", []) if str(item).strip()],
        heading_level=int(payload.get("heading_level", 0) or 0),
        source=str(payload.get("source", "")).strip() or "rule_split",
    )


def _normalize_sections(structure: V2StageArtifact) -> list[SectionCandidate]:
    raw_sections = structure.metadata.get("sections", []) if structure.metadata else []
    return [_to_section_candidate(section) for section in raw_sections if isinstance(section, dict)]


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> tuple[int, list[str]]:
    score = 0
    matched: list[str] = []
    for keyword in keywords:
        count = text.count(keyword)
        score += count
        if count > 0:
            matched.append(keyword)
    return score, matched


def _score_section(section: SectionCandidate, definition: TopicDefinition) -> tuple[int, list[str], list[str]]:
    title_hits, title_keywords = _keyword_hits(section.title, definition.keywords)
    excerpt_hits, excerpt_keywords = _keyword_hits(f"{section.excerpt}\n{section.body}", definition.keywords)
    module_bonus = 18 if section.module in definition.modules else 0
    heading_bonus = 5 if section.heading_level == 1 else 3 if section.heading_level > 1 else 0
    confidence_bonus = min(section.confidence, 12)

    module_hit_bonus = 0
    for module, score in section.module_scores.items():
        if module in definition.modules:
            module_hit_bonus += min(int(score), 8)

    total_score = title_hits * 8 + excerpt_hits * 3 + module_bonus + module_hit_bonus + heading_bonus + confidence_bonus
    reasons: list[str] = []
    if module_bonus:
        reasons.append(f"主模块命中 {section.module}")
    if title_hits:
        reasons.append(f"标题命中 {title_hits} 次关键词")
    if excerpt_hits:
        reasons.append(f"正文命中 {excerpt_hits} 次关键词")
    if section.heading_level:
        reasons.append(f"标题层级 {section.heading_level}")
    matched_keywords = list(dict.fromkeys(title_keywords + excerpt_keywords))
    return total_score, reasons, matched_keywords


def _pick_context_sections(
    ordered_sections: list[SectionCandidate],
    selected_indexes: list[int],
    used_ids: set[str],
    limit: int,
) -> list[SectionCandidate]:
    context_sections: list[SectionCandidate] = []
    for index in selected_indexes:
        for neighbor in (index - 1, index + 1):
            if neighbor < 0 or neighbor >= len(ordered_sections):
                continue
            candidate = ordered_sections[neighbor]
            candidate_id = _section_id(candidate)
            if candidate_id in used_ids:
                continue
            used_ids.add(candidate_id)
            context_sections.append(candidate)
            if len(context_sections) >= limit:
                return context_sections
    return context_sections


def _build_bundle(
    definition: TopicDefinition,
    ordered_sections: list[SectionCandidate],
) -> tuple[EvidenceBundle, TopicCoverage]:
    ranked: list[tuple[int, int, SectionCandidate, list[str], list[str]]] = []
    for index, section in enumerate(ordered_sections):
        score, reasons, matched_keywords = _score_section(section, definition)
        if score > 0:
            ranked.append((score, index, section, reasons, matched_keywords))

    ranked.sort(key=lambda item: (item[0], item[2].line_span, len(item[2].excerpt)), reverse=True)
    primary_ranked = ranked[:4]
    primary_sections = [item[2] for item in primary_ranked]
    primary_ids = [_section_id(section) for section in primary_sections]
    used_ids = set(primary_ids)
    secondary_sections = _pick_context_sections(
        ordered_sections=ordered_sections,
        selected_indexes=[item[1] for item in primary_ranked],
        used_ids=used_ids,
        limit=2,
    )
    secondary_ids = [_section_id(section) for section in secondary_sections]

    combined_sections = sorted(primary_sections + secondary_sections, key=lambda item: (item.start_line, item.end_line))
    covered_modules = list(dict.fromkeys(section.module for section in combined_sections if section.module))
    missing_modules = [module for module in definition.modules if module not in covered_modules]

    missing_hints: list[str] = []
    if not primary_sections:
        missing_hints.append("未召回到高置信专题证据片段。")
    if missing_modules:
        missing_hints.append(f"未覆盖模块：{', '.join(missing_modules)}。")
    if primary_sections and len(primary_sections) == 1:
        missing_hints.append("当前仅召回 1 个核心证据片段，建议人工复核是否存在遗漏章节。")

    module_hits: list[ModuleHit] = []
    if primary_ranked:
        best_scores: dict[str, float] = {}
        keywords_by_module: dict[str, list[str]] = {}
        for _, _, section, _, matched_keywords in primary_ranked:
            module = section.module
            best_scores[module] = max(best_scores.get(module, 0.0), float(section.confidence))
            keywords_by_module.setdefault(module, [])
            for keyword in matched_keywords:
                if keyword not in keywords_by_module[module]:
                    keywords_by_module[module].append(keyword)
        for module, score in sorted(best_scores.items(), key=lambda item: item[1], reverse=True):
            module_hits.append(
                ModuleHit(
                    module=module,
                    score=score,
                    source="evidence_recall",
                    reason="专题证据召回命中该模块的高分片段。",
                    evidence_keywords=keywords_by_module.get(module, [])[:8],
                )
            )

    average_score = sum(item[0] for item in primary_ranked) / len(primary_ranked) if primary_ranked else 0.0
    coverage = TopicCoverage(
        topic=definition.key,
        covered_modules=covered_modules,
        covered_section_ids=primary_ids + secondary_ids,
        missing_modules=missing_modules,
        missing_hints=missing_hints,
        need_manual_review=not primary_sections or bool(missing_modules),
        confidence=min(average_score / 60.0, 1.0),
    )
    bundle = EvidenceBundle(
        topic=definition.key,
        sections=combined_sections,
        primary_section_ids=primary_ids,
        secondary_section_ids=secondary_ids,
        missing_hints=missing_hints,
        recall_query="；".join(
            [
                f"模块={','.join(definition.modules)}",
                f"关键词={','.join(definition.keywords)}",
                "策略=模块+标题+正文+相邻上下文",
            ]
        ),
        metadata={
            "topic_label": definition.label,
            "topic_aliases": list(definition.aliases),
            "priority": definition.priority,
            "boundary": {
                "in_scope": list(definition.boundary.in_scope),
                "out_of_scope": list(definition.boundary.out_of_scope),
                "primary_modules": list(definition.boundary.primary_modules),
                "secondary_modules": list(definition.boundary.secondary_modules),
                "ownership_rule": definition.boundary.ownership_rule,
                "merge_hints": list(definition.boundary.merge_hints),
            },
            "module_hits": [hit.to_dict() for hit in module_hits],
            "primary_scores": [
                {
                    "section_id": _section_id(section),
                    "score": score,
                    "reasons": reasons,
                    "keywords": matched_keywords,
                }
                for score, _, section, reasons, matched_keywords in primary_ranked
            ],
            "recall_strategy": "rule_recall",
        },
    )
    return bundle, coverage


def build_evidence_map(
    document_name: str,
    structure: V2StageArtifact,
    topic_mode: str = "default",
    topic_keys: tuple[str, ...] | list[str] | None = None,
) -> V2StageArtifact:
    plan = resolve_topic_execution_plan(topic_mode=topic_mode, topic_keys=topic_keys)
    topic_definitions = resolve_topic_definitions(topic_mode=topic_mode, topic_keys=topic_keys)
    ordered_sections = _normalize_sections(structure)
    bundle_map: dict[str, dict] = {}
    coverage_map: dict[str, dict] = {}
    bundle_list: list[dict] = []
    coverage_list: list[dict] = []

    for definition in topic_definitions:
        bundle, coverage = _build_bundle(definition, ordered_sections)
        bundle_payload = bundle.to_dict()
        coverage_payload = coverage.to_dict()
        bundle_map[definition.key] = bundle_payload
        coverage_map[definition.key] = coverage_payload
        bundle_list.append(bundle_payload)
        coverage_list.append(coverage_payload)

    content = json.dumps(
        {
            "document_name": document_name,
            "evidence_status": "ready",
            "source_structure_sections": len(ordered_sections),
            "topic_execution_plan": {
                "mode": plan.mode,
                "requested_keys": list(plan.requested_keys),
                "selected_keys": list(plan.selected_keys),
                "skipped_keys": list(plan.skipped_keys),
                "max_topic_calls": plan.max_topic_calls,
                "reason": plan.reason,
            },
            "topic_taxonomy": [
                {
                    "key": definition.key,
                    "label": definition.label,
                    "aliases": list(definition.aliases),
                    "priority": definition.priority,
                    "enabled": definition.enabled,
                    "modules": list(definition.modules),
                    "boundary": {
                        "in_scope": list(definition.boundary.in_scope),
                        "out_of_scope": list(definition.boundary.out_of_scope),
                        "primary_modules": list(definition.boundary.primary_modules),
                        "secondary_modules": list(definition.boundary.secondary_modules),
                        "ownership_rule": definition.boundary.ownership_rule,
                        "merge_hints": list(definition.boundary.merge_hints),
                    },
                }
                for definition in TOPIC_TAXONOMY
            ],
            "topic_evidence_bundles": bundle_list,
            "topic_coverages": coverage_list,
        },
        ensure_ascii=False,
        indent=2,
    )
    return V2StageArtifact(
        name="evidence",
        content=content,
        raw_output=content,
        metadata={
            "topic_execution_plan": {
                "mode": plan.mode,
                "requested_keys": list(plan.requested_keys),
                "selected_keys": list(plan.selected_keys),
                "skipped_keys": list(plan.skipped_keys),
                "max_topic_calls": plan.max_topic_calls,
                "reason": plan.reason,
            },
            "topic_taxonomy": {
                definition.key: {
                    "label": definition.label,
                    "aliases": list(definition.aliases),
                    "priority": definition.priority,
                    "enabled": definition.enabled,
                    "modules": list(definition.modules),
                    "boundary": {
                        "in_scope": list(definition.boundary.in_scope),
                        "out_of_scope": list(definition.boundary.out_of_scope),
                        "primary_modules": list(definition.boundary.primary_modules),
                        "secondary_modules": list(definition.boundary.secondary_modules),
                        "ownership_rule": definition.boundary.ownership_rule,
                        "merge_hints": list(definition.boundary.merge_hints),
                    },
                }
                for definition in TOPIC_TAXONOMY
            },
            "topic_evidence_bundles": bundle_map,
            "topic_coverages": coverage_map,
            "evidence_bundle_count": len(bundle_list),
        },
    )
