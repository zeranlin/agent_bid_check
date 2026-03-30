from __future__ import annotations

import hashlib
import json
import re

from app.common.normalize import dedupe
from app.common.parser import parse_review_markdown
from app.common.schemas import RiskPoint

from .schemas import ComparisonArtifact, MergedRiskCluster, RiskSignature, TopicReviewArtifact, V2StageArtifact


SEVERITY_ORDER = {"高风险": 3, "中风险": 2, "低风险": 1, "需人工复核": 0}


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _excerpt_hash(text: str) -> str:
    normalized = _normalize_text(text)[:500]
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()[:16] if normalized else ""


def _signature_key(risk: RiskPoint) -> str:
    title = _normalize_text(risk.title)
    review_type = _normalize_text(risk.review_type)
    location = _normalize_text(risk.source_location)
    excerpt_hash = _excerpt_hash(risk.source_excerpt)
    if location and title:
        return f"{title}|{review_type}|{location}"
    if excerpt_hash:
        return f"{title}|{review_type}|{excerpt_hash}"
    return f"{title}|{review_type}"


def _best_severity(values: list[str]) -> str:
    if not values:
        return "需人工复核"
    ordered = sorted(values, key=lambda item: SEVERITY_ORDER.get(item, -1), reverse=True)
    explicit = [item for item in ordered if item != "需人工复核"]
    return explicit[0] if explicit else ordered[0]


def _risk_to_signature(risk: RiskPoint, topic: str, source_rule: str) -> RiskSignature:
    risk.ensure_defaults()
    return RiskSignature(
        topic=topic,
        title=risk.title,
        review_type=risk.review_type,
        source_locations=[risk.source_location] if risk.source_location else [],
        source_excerpt_hash=_excerpt_hash(risk.source_excerpt),
        severity=risk.severity,
        source_rule=source_rule,
        source_excerpt=risk.source_excerpt,
    )


def _risk_to_dict(risk: RiskPoint, topic: str, source_rule: str) -> dict:
    risk.ensure_defaults()
    return {
        "topic": topic,
        "source_rule": source_rule,
        "title": risk.title,
        "severity": risk.severity,
        "review_type": risk.review_type,
        "source_location": risk.source_location,
        "source_excerpt": risk.source_excerpt,
    }


def _build_cluster(cluster_id: str, items: list[tuple[RiskPoint, str, str]]) -> MergedRiskCluster:
    risks = [item[0] for item in items]
    severities = [risk.severity for risk in risks]
    topics = [item[1] for item in items]
    source_rules = [item[2] for item in items]

    conflict_notes: list[str] = []
    explicit = sorted({severity for severity in severities if severity != "需人工复核"}, key=lambda item: SEVERITY_ORDER[item], reverse=True)
    if len(explicit) > 1:
        conflict_notes.append(f"严重级别存在冲突：{' / '.join(explicit)}。")
    elif "需人工复核" in severities and explicit:
        conflict_notes.append(f"部分来源标记为需人工复核，最终保留明确级别：{explicit[0]}。")

    return MergedRiskCluster(
        cluster_id=cluster_id,
        title=risks[0].title,
        severity=_best_severity(severities),
        review_type=risks[0].review_type,
        source_locations=dedupe([risk.source_location for risk in risks if risk.source_location.strip()]),
        source_excerpts=dedupe([risk.source_excerpt for risk in risks if risk.source_excerpt.strip()]),
        risk_judgment=dedupe([item for risk in risks for item in risk.risk_judgment]),
        legal_basis=dedupe([item for risk in risks for item in risk.legal_basis]),
        rectification=dedupe([item for risk in risks for item in risk.rectification]),
        topics=dedupe(topics),
        source_rules=dedupe(source_rules),
        conflict_notes=conflict_notes,
        need_manual_review=any(risk.severity == "需人工复核" for risk in risks) or bool(conflict_notes),
    )


def compare_review_artifacts(
    document_name: str,
    baseline: V2StageArtifact,
    topics: list[TopicReviewArtifact],
) -> ComparisonArtifact:
    baseline_report = parse_review_markdown(baseline.content)
    signatures: list[RiskSignature] = []
    grouped: dict[str, list[tuple[RiskPoint, str, str]]] = {}
    baseline_signature_keys: set[str] = set()
    topic_signature_keys: set[str] = set()
    baseline_only_risks: list[dict[str, str]] = []
    topic_only_risks: list[dict[str, str]] = []

    for risk in baseline_report.risk_points:
        key = _signature_key(risk)
        signature = _risk_to_signature(risk, "baseline", "baseline")
        signatures.append(signature)
        grouped.setdefault(key, []).append((risk, "baseline", "baseline"))
        baseline_signature_keys.add(key)

    for topic in topics:
        for risk in topic.risk_points:
            key = _signature_key(risk)
            signature = _risk_to_signature(risk, topic.topic, "topic")
            signatures.append(signature)
            grouped.setdefault(key, []).append((risk, topic.topic, "topic"))
            topic_signature_keys.add(key)

    clusters = [_build_cluster(f"cluster-{index}", items) for index, items in enumerate(grouped.values(), start=1)]
    conflicts = [
        {
            "cluster_id": cluster.cluster_id,
            "title": cluster.title,
            "severity": cluster.severity,
            "topics": cluster.topics,
            "conflict_notes": cluster.conflict_notes,
        }
        for cluster in clusters
        if cluster.conflict_notes
    ]

    missing_topic_coverage: list[str] = []
    manual_review_items: list[str] = []
    coverage_gaps: list[dict[str, object]] = []
    topic_summaries: list[dict[str, object]] = []
    for topic in topics:
        missing_evidence = topic.metadata.get("missing_evidence", []) if topic.metadata else []
        coverage = topic.metadata.get("topic_coverage", {}) if topic.metadata else {}
        selected_sections = topic.metadata.get("selected_sections", []) if topic.metadata else []
        missing_modules = coverage.get("missing_modules", []) if isinstance(coverage, dict) else []
        if topic.need_manual_review:
            manual_review_items.append(f"{topic.topic}: {topic.summary}")
        if missing_evidence:
            missing_topic_coverage.extend([f"{topic.topic}: {item}" for item in missing_evidence if str(item).strip() and str(item).strip() != "未发现"])
            coverage_gaps.append(
                {
                    "topic": topic.topic,
                    "type": "missing_evidence",
                    "items": [str(item) for item in missing_evidence if str(item).strip() and str(item).strip() != "未发现"],
                    "message": f"{topic.topic} 缺少关键证据：{'；'.join([str(item) for item in missing_evidence if str(item).strip() and str(item).strip() != '未发现'])}。",
                }
            )
        if not selected_sections:
            missing_topic_coverage.append(f"{topic.topic}: 未召回到有效证据片段。")
            coverage_gaps.append(
                {
                    "topic": topic.topic,
                    "type": "no_sections",
                    "items": [],
                    "message": f"{topic.topic} 未召回到有效证据片段。",
                }
            )
        if not selected_sections and topic.risk_points:
            manual_review_items.append(f"{topic.topic}: 证据不足但仍输出了结论，需人工复核。")
        if missing_modules:
            coverage_gaps.append(
                {
                    "topic": topic.topic,
                    "type": "missing_modules",
                    "items": list(missing_modules),
                    "message": f"{topic.topic} 缺失模块覆盖：{', '.join(missing_modules)}。",
                }
            )
        if topic.need_manual_review and selected_sections:
            coverage_gaps.append(
                {
                    "topic": topic.topic,
                    "type": "manual_review",
                    "items": list(missing_evidence) if isinstance(missing_evidence, list) else [],
                    "message": f"{topic.topic} 已召回证据但仍需人工复核。",
                }
            )
        topic_summaries.append(
            {
                "topic": topic.topic,
                "risk_count": len(topic.risk_points),
                "need_manual_review": topic.need_manual_review,
                "selected_section_count": len(selected_sections),
                "missing_modules": missing_modules,
            }
        )

    if len(baseline_report.risk_points) == 0 and len(clusters) >= 2:
        manual_review_items.append("基线层未发现风险，但专题层发现多个风险点，建议人工复核专题补充发现。")
        coverage_gaps.append(
            {
                "topic": "cross_check",
                "type": "baseline_topic_gap",
                "items": [],
                "message": "基线层与专题层差异较大，建议人工复核专题新增问题。",
            }
        )

    for risk in baseline_report.risk_points:
        key = _signature_key(risk)
        if key not in topic_signature_keys:
            baseline_only_risks.append(_risk_to_dict(risk, "baseline", "baseline"))

    for topic in topics:
        for risk in topic.risk_points:
            key = _signature_key(risk)
            if key not in baseline_signature_keys:
                topic_only_risks.append(_risk_to_dict(risk, topic.topic, "topic"))

    coverage_summary = {
        "baseline_risk_count": len(baseline_report.risk_points),
        "topic_risk_count": sum(len(topic.risk_points) for topic in topics),
        "cluster_count": len(clusters),
        "topic_count": len(topics),
        "baseline_only_count": len(baseline_only_risks),
        "topic_only_count": len(topic_only_risks),
        "coverage_gap_count": len(coverage_gaps),
        "topic_summaries": topic_summaries,
    }
    comparison_summary = {
        "conflict_count": len(conflicts),
        "manual_review_count": len(dedupe(manual_review_items)),
        "duplicate_reduction": max(len(signatures) - len(clusters), 0),
    }

    return ComparisonArtifact(
        signatures=signatures,
        clusters=clusters,
        conflicts=conflicts,
        coverage_summary=coverage_summary,
        comparison_summary=comparison_summary,
        baseline_only_risks=baseline_only_risks,
        topic_only_risks=topic_only_risks,
        missing_topic_coverage=dedupe(missing_topic_coverage),
        manual_review_items=dedupe(manual_review_items),
        coverage_gaps=coverage_gaps,
        metadata={"document_name": document_name},
    )


def comparison_to_json(artifact: ComparisonArtifact) -> str:
    return json.dumps(artifact.to_dict(), ensure_ascii=False, indent=2)
