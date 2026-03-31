from __future__ import annotations

import json
from pathlib import Path

from app.common.parser import parse_review_markdown


def normalize_text(text: str) -> str:
    return "".join(str(text or "").split()).lower()


def title_match(expected: str, actual: str) -> bool:
    expected_norm = normalize_text(expected)
    actual_norm = normalize_text(actual)
    if not expected_norm or not actual_norm:
        return False
    return expected_norm == actual_norm or expected_norm in actual_norm or actual_norm in expected_norm


def _string_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _section_id(section: dict) -> str:
    start_line = int(section.get("start_line", 0) or 0)
    end_line = int(section.get("end_line", 0) or 0)
    return f"{start_line}-{end_line}"


def _find_section(title: str, sections: list[dict]) -> dict | None:
    for section in sections:
        if isinstance(section, dict) and title_match(title, str(section.get("title", ""))):
            return section
    return None


def extract_actual_risks(system_payload: dict) -> list[dict]:
    comparison = system_payload.get("comparison")
    if isinstance(comparison, dict):
        clusters = comparison.get("clusters", [])
        risks: list[dict] = []
        for cluster in clusters:
            if not isinstance(cluster, dict):
                continue
            risks.append(
                {
                    "title": str(cluster.get("title", "")),
                    "review_type": str(cluster.get("review_type", "")),
                    "severity": str(cluster.get("severity", "需人工复核")),
                    "source_location": "；".join(_string_list(cluster.get("source_locations"))),
                    "source_excerpt": "\n\n".join(_string_list(cluster.get("source_excerpts"))),
                    "manual_review": bool(cluster.get("need_manual_review", False))
                    or str(cluster.get("severity", "")) == "需人工复核",
                    "topics": _string_list(cluster.get("topics")),
                    "source_rule": "comparison",
                }
            )
        return risks

    final_markdown = str(system_payload.get("final_review_markdown", "") or system_payload.get("review_markdown", ""))
    if final_markdown.strip():
        report = parse_review_markdown(final_markdown)
        return [
            {
                "title": risk.title,
                "review_type": risk.review_type,
                "severity": risk.severity,
                "source_location": risk.source_location,
                "source_excerpt": risk.source_excerpt,
                "manual_review": risk.severity == "需人工复核",
                "topics": [],
                "source_rule": "markdown",
            }
            for risk in report.risk_points
        ]

    return []


def extract_actual_structure(system_payload: dict) -> tuple[list[dict], dict[str, dict]]:
    document_map = system_payload.get("document_map", {})
    evidence_map = system_payload.get("evidence_map", {})
    sections = document_map.get("sections", []) if isinstance(document_map, dict) else []
    bundles = evidence_map.get("topic_evidence_bundles", {}) if isinstance(evidence_map, dict) else {}
    return [item for item in sections if isinstance(item, dict)], bundles if isinstance(bundles, dict) else {}


def _risk_match_score(gold_risk: dict, actual_risk: dict) -> float:
    aliases = [str(gold_risk.get("title", "")).strip()] + _string_list(gold_risk.get("aliases"))
    title_score = 0.0
    for alias in aliases:
        if title_match(alias, str(actual_risk.get("title", ""))):
            title_score = 0.7
            break

    if not title_score:
        return 0.0

    review_type = str(gold_risk.get("review_type", "")).strip()
    actual_review_type = str(actual_risk.get("review_type", "")).strip()
    if review_type and actual_review_type and title_match(review_type, actual_review_type):
        title_score += 0.15

    gold_location = str(gold_risk.get("source_location", "")).strip()
    actual_location = str(actual_risk.get("source_location", "")).strip()
    if gold_location and actual_location and title_match(gold_location, actual_location):
        title_score += 0.1

    severity = str(gold_risk.get("severity", "")).strip()
    actual_severity = str(actual_risk.get("severity", "")).strip()
    if severity and actual_severity and severity == actual_severity:
        title_score += 0.05
    elif severity == "需人工复核" and bool(actual_risk.get("manual_review", False)):
        title_score += 0.05

    return title_score


def compare_risks(gold_risks: list[dict], actual_risks: list[dict]) -> dict:
    matched: list[dict] = []
    missed: list[dict] = []
    manual_review_gaps: list[dict] = []
    used_actual_indexes: set[int] = set()

    for gold in gold_risks:
        best_index = -1
        best_score = 0.0
        for index, actual in enumerate(actual_risks):
            if index in used_actual_indexes:
                continue
            score = _risk_match_score(gold, actual)
            if score > best_score:
                best_score = score
                best_index = index

        if best_index >= 0 and best_score >= 0.6:
            actual = actual_risks[best_index]
            used_actual_indexes.add(best_index)
            matched.append(
                {
                    "gold_id": str(gold.get("id", "")),
                    "gold_title": str(gold.get("title", "")),
                    "actual_title": str(actual.get("title", "")),
                    "match_score": round(best_score, 3),
                    "review_type_matched": title_match(str(gold.get("review_type", "")), str(actual.get("review_type", ""))),
                    "location_matched": title_match(
                        str(gold.get("source_location", "")),
                        str(actual.get("source_location", "")),
                    ),
                    "severity_matched": str(gold.get("severity", "")) == str(actual.get("severity", "")),
                }
            )
            gold_manual = bool(gold.get("manual_review", False)) or str(gold.get("severity", "")) == "需人工复核"
            actual_manual = bool(actual.get("manual_review", False)) or str(actual.get("severity", "")) == "需人工复核"
            if gold_manual != actual_manual:
                manual_review_gaps.append(
                    {
                        "gold_id": str(gold.get("id", "")),
                        "title": str(gold.get("title", "")),
                        "expected_manual_review": gold_manual,
                        "actual_manual_review": actual_manual,
                        "actual_title": str(actual.get("title", "")),
                        "reason": "manual_review_flag_mismatch",
                    }
                )
        else:
            missed.append(
                {
                    "gold_id": str(gold.get("id", "")),
                    "title": str(gold.get("title", "")),
                    "review_type": str(gold.get("review_type", "")),
                    "severity": str(gold.get("severity", "")),
                    "source_location": str(gold.get("source_location", "")),
                    "manual_review": bool(gold.get("manual_review", False)),
                }
            )

    false_positive: list[dict] = []
    for index, actual in enumerate(actual_risks):
        if index in used_actual_indexes:
            continue
        false_positive.append(
            {
                "title": str(actual.get("title", "")),
                "review_type": str(actual.get("review_type", "")),
                "severity": str(actual.get("severity", "")),
                "source_location": str(actual.get("source_location", "")),
                "manual_review": bool(actual.get("manual_review", False)),
            }
        )

    return {
        "matched_risks": matched,
        "missed_risks": missed,
        "false_positive_risks": false_positive,
        "manual_review_gaps": manual_review_gaps,
    }


def compare_structure(gold_structure: dict, actual_sections: list[dict], actual_bundles: dict[str, dict]) -> dict:
    required_sections = [
        item for item in gold_structure.get("required_sections", []) if isinstance(item, dict)
    ] if isinstance(gold_structure, dict) else []
    topic_coverages = [
        item for item in gold_structure.get("topic_coverages", []) if isinstance(item, dict)
    ] if isinstance(gold_structure, dict) else []

    matched_sections: list[dict] = []
    missed_sections: list[dict] = []

    for expected in required_sections:
        title = str(expected.get("title", "")).strip()
        matched = _find_section(title, actual_sections)
        if not matched:
            missed_sections.append(
                {
                    "id": str(expected.get("id", "")),
                    "title": title,
                    "expected_module": str(expected.get("module", "")),
                    "reason": "section_not_found",
                }
            )
            continue

        expected_module = str(expected.get("module", "")).strip()
        module_ok = not expected_module or str(matched.get("module", "")).strip() == expected_module
        module_scores = matched.get("module_scores", {}) if isinstance(matched.get("module_scores", {}), dict) else {}
        secondary_modules = _string_list(expected.get("secondary_modules"))
        secondary_ok = all(int(module_scores.get(module, 0) or 0) > 0 for module in secondary_modules) if secondary_modules else True
        if module_ok and secondary_ok:
            matched_sections.append(
                {
                    "id": str(expected.get("id", "")),
                    "title": title,
                    "actual_module": str(matched.get("module", "")),
                    "section_id": _section_id(matched),
                }
            )
        else:
            reason = []
            if not module_ok:
                reason.append("module_mismatch")
            if not secondary_ok:
                reason.append("secondary_modules_missing")
            missed_sections.append(
                {
                    "id": str(expected.get("id", "")),
                    "title": title,
                    "expected_module": expected_module,
                    "actual_module": str(matched.get("module", "")),
                    "reason": ",".join(reason),
                }
            )

    coverage_hits: list[dict] = []
    coverage_gaps: list[dict] = []
    for expected in topic_coverages:
        topic = str(expected.get("topic", "")).strip()
        if not topic:
            continue
        bundle = actual_bundles.get(topic, {}) if isinstance(actual_bundles, dict) else {}
        sections = bundle.get("sections", []) if isinstance(bundle, dict) else []
        section_titles = [str(item.get("title", "")).strip() for item in sections if isinstance(item, dict)]
        modules = list(
            dict.fromkeys(
                str(item.get("module", "")).strip()
                for item in sections
                if isinstance(item, dict) and str(item.get("module", "")).strip()
            )
        )
        required_titles = _string_list(expected.get("required_titles"))
        required_modules = _string_list(expected.get("required_modules"))
        titles_ok = all(any(title_match(title, actual) for actual in section_titles) for title in required_titles)
        modules_ok = all(module in modules for module in required_modules)
        if titles_ok and modules_ok:
            coverage_hits.append({"topic": topic, "required_titles": required_titles, "required_modules": required_modules})
        else:
            coverage_gaps.append(
                {
                    "topic": topic,
                    "required_titles": required_titles,
                    "required_modules": required_modules,
                    "actual_titles": section_titles,
                    "actual_modules": modules,
                    "reason": ",".join(
                        [
                            reason
                            for reason, ok in (("missing_titles", titles_ok), ("missing_modules", modules_ok))
                            if not ok
                        ]
                    ),
                }
            )

    return {
        "matched_sections": matched_sections,
        "missed_sections": missed_sections,
        "matched_topic_coverages": coverage_hits,
        "missed_topic_coverages": coverage_gaps,
    }


def load_result_payload(result_dir: Path) -> dict:
    payload: dict[str, object] = {}
    if (result_dir / "document_map.json").exists():
        payload["document_map"] = json.loads((result_dir / "document_map.json").read_text(encoding="utf-8"))
    if (result_dir / "evidence_map.json").exists():
        payload["evidence_map"] = json.loads((result_dir / "evidence_map.json").read_text(encoding="utf-8"))
    if (result_dir / "comparison.json").exists():
        payload["comparison"] = json.loads((result_dir / "comparison.json").read_text(encoding="utf-8"))
    elif (result_dir / "final_review.md").exists():
        payload["final_review_markdown"] = (result_dir / "final_review.md").read_text(encoding="utf-8")
    return payload
