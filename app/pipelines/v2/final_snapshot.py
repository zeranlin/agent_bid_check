from __future__ import annotations

from datetime import datetime
from typing import Any

from app.common.normalize import dedupe
from app.common.parser import parse_review_markdown

from .compare import compare_review_artifacts
from .output_governance import govern_comparison_artifact
from .problem_layer import build_problem_layer
from .risk_admission import admit_problem_result


SNAPSHOT_VERSION = "v1"


def _build_description_lines(structure, topics) -> list[str]:
    sections = structure.metadata.get("sections", []) if getattr(structure, "metadata", None) else []
    manual_topics = [topic.topic for topic in topics if getattr(topic, "need_manual_review", False)]
    lines = [
        "本审查基于你提供的招标文件文本进行。",
        "本报告结合全文直审、结构增强与专题深审生成。",
        f"结构增强层共识别 {len(sections)} 个候选章节，并按模块进行召回。",
    ]
    if manual_topics:
        lines.append(f"以下专题仍建议人工复核：{', '.join(manual_topics)}。")
    else:
        lines.append("对存在事实基础不足的事项，仍建议结合采购背景继续人工复核。")
    lines.append("下述“风险判断”系合规审查意见，不等同于行政机关最终认定。")
    return lines


def _lookup_problem_map(problems) -> dict[str, Any]:
    return {problem.problem_id: problem for problem in getattr(problems, "problems", [])}


def _first_text(values: list[str], default: str) -> str:
    for value in values:
        normalized = str(value).strip()
        if normalized:
            return normalized
    return default


def _build_final_problem_resolution(candidate, decision) -> dict[str, Any]:
    extras = dict(candidate.extras)
    resolution = extras.get("final_problem_resolution", {})
    if isinstance(resolution, dict) and resolution:
        return dict(resolution)
    return {
        "target_layer": decision.target_layer,
        "admission_reason": decision.admission_reason,
        "formal_gate_rule": decision.formal_gate_rule,
    }


def _build_snapshot_risk_item(candidate, decision, layer: str, problem_map: dict[str, Any]) -> dict[str, Any]:
    extras = dict(candidate.extras)
    problem_id = str(extras.get("problem_id", "")).strip()
    problem = problem_map.get(problem_id)
    problem_rule_ids = extras.get("problem_rule_ids", [])
    problem_evidence_ids = extras.get("problem_evidence_ids", [])
    primary_candidate = getattr(problem, "primary_candidate", None)
    supporting_candidates = list(getattr(problem, "supporting_candidates", [])) if problem is not None else []
    source_candidates = [item for item in [primary_candidate, *supporting_candidates] if item is not None]
    risk_judgment = dedupe(
        [
            str(value).strip()
            for item in source_candidates
            for value in getattr(item, "risk_judgment", [])
            if str(value).strip()
        ]
    )
    legal_basis = dedupe(
        [
            str(value).strip()
            for item in source_candidates
            for value in getattr(item, "legal_basis", [])
            if str(value).strip()
        ]
    )
    rectification = dedupe(
        [
            str(value).strip()
            for item in source_candidates
            for value in getattr(item, "rectification", [])
            if str(value).strip()
        ]
    )
    source_locations = [str(item).strip() for item in candidate.source_locations if str(item).strip()]
    source_excerpts = [str(item).strip() for item in candidate.source_excerpts if str(item).strip()]
    rule_ids = [str(item).strip() for item in problem_rule_ids if str(item).strip()] or [str(candidate.rule_id).strip()]
    evidence_ids = [str(item).strip() for item in problem_evidence_ids if str(item).strip()]
    topic_sources = [str(item).strip() for item in extras.get("problem_topic_sources", []) if str(item).strip()]
    merged_topic_sources = [str(item).strip() for item in extras.get("merged_topic_sources", []) if str(item).strip()]
    merged_family_keys = [str(item).strip() for item in extras.get("merged_family_keys", []) if str(item).strip()]
    return {
        "problem_id": problem_id,
        "title": candidate.title,
        "severity": candidate.severity,
        "review_type": candidate.review_type,
        "layer": layer,
        "problem_kind": str(extras.get("problem_kind", "standard") or "standard"),
        "conflict_type": str(extras.get("conflict_type", "") or ""),
        "evidence_ids": evidence_ids,
        "rule_ids": rule_ids,
        "source_locations": source_locations,
        "source_excerpts": source_excerpts,
        "source_location": _first_text(source_locations, "未发现"),
        "source_excerpt": _first_text(source_excerpts, "未发现"),
        "risk_judgment": risk_judgment,
        "legal_basis": legal_basis,
        "rectification": rectification,
        "topic_sources": topic_sources,
        "merged_topic_sources": merged_topic_sources,
        "merged_family_keys": merged_family_keys,
        "final_problem_resolution": _build_final_problem_resolution(candidate, decision),
        "left_side": dict(extras.get("left_side", {})),
        "right_side": dict(extras.get("right_side", {})),
        "conflict_reason": dict(extras.get("conflict_reason", {})),
        "conflict_evidence_links": list(extras.get("conflict_evidence_links", [])),
        "admission_reason": decision.admission_reason,
        "formal_gate": {
            "formal_gate_passed": decision.formal_gate_passed,
            "formal_gate_reason": decision.formal_gate_reason,
            "formal_gate_rule": decision.formal_gate_rule,
            "formal_gate_exception_whitelist_hit": decision.formal_gate_exception_whitelist_hit,
            "formal_gate_family_allowed": decision.formal_gate_family_allowed,
            "formal_gate_evidence_passed": decision.formal_gate_evidence_passed,
        },
        "trace_summary": {
            "cross_topic_merge_reason": str(extras.get("cross_topic_merge_reason", "") or ""),
            "supporting_candidate_titles": list(extras.get("problem_supporting_candidate_titles", [])),
            "supporting_candidate_rule_ids": list(extras.get("problem_supporting_candidate_rule_ids", [])),
            "layer_conflict_inputs": list(extras.get("layer_conflict_inputs", [])),
        },
        "family_key": getattr(problem, "family_key", candidate.risk_family),
    }


def _build_problem_trace_summary(problems, admission) -> list[dict[str, Any]]:
    problem_items: list[dict[str, Any]] = []
    decision_by_problem_id: dict[str, dict[str, Any]] = {}
    for layer_name, items in (
        ("formal_risks", admission.formal_risks),
        ("pending_review_items", admission.pending_review_items),
        ("excluded_risks", admission.excluded_risks),
    ):
        for item in items:
            problem_id = str(item.extras.get("problem_id", "")).strip()
            if not problem_id:
                continue
            decision = admission.decisions.get(item.rule_id)
            decision_by_problem_id[problem_id] = {
                "target_layer": layer_name,
                "admission_reason": decision.admission_reason if decision else "",
                "formal_gate_rule": decision.formal_gate_rule if decision else "",
            }
    for problem in getattr(problems, "problems", []):
        summary = {
            "problem_id": problem.problem_id,
            "title": problem.canonical_title,
            "family_key": problem.family_key,
            "problem_kind": problem.problem_kind,
            "topic_sources": list(problem.topic_sources),
            "merged_topic_sources": list(problem.merged_topic_sources),
            "merged_family_keys": list(problem.merged_family_keys),
            "rule_ids": list(problem.rule_ids),
            "evidence_ids": list(problem.evidence_ids),
            "cross_topic_merge_reason": problem.cross_topic_merge_reason,
            "final_problem_resolution": dict(problem.final_problem_resolution),
            "conflict_type": problem.conflict_type,
            "decision": decision_by_problem_id.get(problem.problem_id, {}),
        }
        if problem.problem_kind == "conflict":
            summary["left_side"] = dict(problem.left_side)
            summary["right_side"] = dict(problem.right_side)
            summary["conflict_reason"] = dict(problem.conflict_reason)
        problem_items.append(summary)
    return problem_items


def _build_source_trace_summary(structure, topics) -> dict[str, Any]:
    metadata = getattr(structure, "metadata", {}) or {}
    return {
        "structure_section_count": int(metadata.get("section_count", 0) or 0),
        "evidence_bundle_count": int(metadata.get("evidence_bundle_count", 0) or 0),
        "evidence_object_count": int(metadata.get("evidence_object_count", 0) or 0),
        "topics": [
            {
                "topic": topic.topic,
                "summary": topic.summary,
                "risk_count": len(topic.risk_points),
                "need_manual_review": topic.need_manual_review,
                "coverage_note": topic.coverage_note,
            }
            for topic in topics
        ],
    }


def _collect_layer_items(admission, layer_name: str, problem_map: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for candidate in getattr(admission, layer_name):
        decision = admission.decisions.get(candidate.rule_id)
        if decision is None:
            continue
        items.append(_build_snapshot_risk_item(candidate, decision, layer_name, problem_map))
    return items


def _build_summary(final_risks: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    formal = final_risks["formal_risks"]
    pending = final_risks["pending_review_items"]
    excluded = final_risks["excluded_risks"]
    basis_summary = dedupe(
        [
            basis
            for item in formal
            for basis in item.get("legal_basis", [])
            if str(basis).strip()
        ]
    ) or ["需人工复核"]
    return {
        "formal_count": len(formal),
        "pending_count": len(pending),
        "excluded_count": len(excluded),
        "high_risk_titles": [item["title"] for item in formal if item.get("severity") == "高风险"],
        "medium_risk_titles": [item["title"] for item in formal if item.get("severity") == "中风险"],
        "manual_review_titles": [item["title"] for item in pending],
        "excluded_titles": [item["title"] for item in excluded],
        "basis_summary": basis_summary,
    }


def build_v2_final_snapshot(
    document_name: str,
    baseline,
    structure,
    topics,
    comparison=None,
    governance=None,
    problems=None,
    admission=None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    comparison = comparison or compare_review_artifacts(document_name, baseline, topics)
    governance = governance or govern_comparison_artifact(document_name, comparison)
    problems = problems or build_problem_layer(document_name, governance)
    admission = admission or admit_problem_result(document_name, comparison, problems, governance)
    baseline_report = parse_review_markdown(getattr(baseline, "content", ""))
    problem_map = _lookup_problem_map(problems)
    final_risks = {
        "formal_risks": _collect_layer_items(admission, "formal_risks", problem_map),
        "pending_review_items": _collect_layer_items(admission, "pending_review_items", problem_map),
        "excluded_risks": _collect_layer_items(admission, "excluded_risks", problem_map),
    }
    summary = _build_summary(final_risks)
    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "run_metadata": {
            "document_name": document_name,
            "generated_at": generated_at or datetime.now().isoformat(timespec="seconds"),
        },
        "input_metadata": {
            "subject": baseline_report.subject or document_name,
            "description_lines": _build_description_lines(structure, topics),
        },
        "summary": summary,
        "final_risks": final_risks,
        "problem_trace_summary": _build_problem_trace_summary(problems, admission),
        "source_trace_summary": _build_source_trace_summary(structure, topics),
    }


def _render_risk_item(lines: list[str], index: int, item: dict[str, Any]) -> None:
    lines.extend(
        [
            f"## 风险点{index}：{item.get('title', f'风险点{index}')}",
            "",
            f"- 问题定性：{item.get('severity', '需人工复核')}",
            f"- 审查类型：{item.get('review_type', '未发现')}",
            f"- 原文位置：{item.get('source_location', '未发现')}",
            f"- 原文摘录：{item.get('source_excerpt', '未发现')}",
            "- 风险判断：",
        ]
    )
    risk_judgment = [str(value).strip() for value in item.get("risk_judgment", []) if str(value).strip()]
    if not risk_judgment:
        risk_judgment = [str(item.get("admission_reason", "")).strip() or "已通过最终问题对象生成。"]
    lines.extend([f"  - {value}" for value in risk_judgment])
    lines.append("- 法律/政策依据：")
    legal_basis = [str(value).strip() for value in item.get("legal_basis", []) if str(value).strip()] or ["需人工复核"]
    lines.extend([f"  - {value}" for value in legal_basis])
    lines.append("- 整改建议：")
    rectification = [str(value).strip() for value in item.get("rectification", []) if str(value).strip()] or ["未发现"]
    lines.extend([f"  - {value}" for value in rectification])
    lines.append("")


def render_v2_markdown_from_snapshot(snapshot: dict[str, Any]) -> str:
    input_metadata = snapshot.get("input_metadata", {}) if isinstance(snapshot, dict) else {}
    final_risks = snapshot.get("final_risks", {}) if isinstance(snapshot, dict) else {}
    summary = snapshot.get("summary", {}) if isinstance(snapshot, dict) else {}
    lines = [
        "# 招标文件合规审查结果",
        "",
        f"审查对象：`{input_metadata.get('subject', '')}`",
        "",
        "说明：",
    ]
    lines.extend([f"- {item}" for item in input_metadata.get("description_lines", []) or []])
    lines.extend(["", "---", ""])

    for index, item in enumerate(final_risks.get("formal_risks", []) or [], start=1):
        if isinstance(item, dict):
            _render_risk_item(lines, index, item)

    pending = [item for item in (final_risks.get("pending_review_items", []) or []) if isinstance(item, dict)]
    if pending:
        lines.extend(["---", "", "## 待补证复核项", ""])
        for index, item in enumerate(pending, start=1):
            lines.extend(
                [
                    f"### 复核项{index}：{item.get('title', '待补证复核项')}",
                    "",
                    f"- 复核类型：{item.get('review_type', '需人工复核')}",
                    f"- 所属专题：{'、'.join(item.get('topic_sources', []) or []) or '未分类'}",
                    f"- 原文位置：{item.get('source_location', '未发现')}",
                    f"- 原文摘录：{item.get('source_excerpt', '未发现')}",
                    f"- 复核原因：{item.get('admission_reason', '当前证据未完整覆盖对应条款，需补充证据后复核。')}",
                    "",
                ]
            )

    lines.extend(["---", "", "## 综合判断", ""])
    lines.append("- 高风险问题：")
    lines.extend([f"  - {item}" for item in summary.get("high_risk_titles", []) or ["未发现"]])
    lines.append("- 中风险问题：")
    lines.extend([f"  - {item}" for item in summary.get("medium_risk_titles", []) or ["未发现"]])
    lines.append("- 需人工复核事项：")
    lines.extend([f"  - {item}" for item in summary.get("manual_review_titles", []) or ["未发现"]])
    lines.extend(["", "## 主要依据汇总", ""])
    lines.extend([f"- {item}" for item in summary.get("basis_summary", []) or ["需人工复核"]])
    lines.append("")
    return "\n".join(lines)


def _project_legacy_layer(items: list[dict[str, Any]], include_reason: bool = False) -> list[dict[str, Any]]:
    projected: list[dict[str, Any]] = []
    for item in items:
        payload = {
            "title": item.get("title", ""),
            "severity": item.get("severity", "需人工复核"),
            "review_type": item.get("review_type", "未发现"),
            "source_location": item.get("source_location", "未发现"),
            "source_excerpt": item.get("source_excerpt", "未发现"),
        }
        if include_reason:
            payload["reason"] = item.get("admission_reason", "")
            payload["topic"] = "、".join(item.get("topic_sources", []) or [])
        else:
            payload["risk_judgment"] = list(item.get("risk_judgment", []))
            payload["legal_basis"] = list(item.get("legal_basis", []))
            payload["rectification"] = list(item.get("rectification", []))
        projected.append(payload)
    return projected


def project_final_output_from_snapshot(snapshot: dict[str, Any], governance=None, admission=None) -> dict[str, Any]:
    final_risks = snapshot.get("final_risks", {}) if isinstance(snapshot, dict) else {}
    summary = snapshot.get("summary", {}) if isinstance(snapshot, dict) else {}
    projected = {
        "subject": snapshot.get("input_metadata", {}).get("subject", ""),
        "description_lines": list(snapshot.get("input_metadata", {}).get("description_lines", []) or []),
        "formal_risks": _project_legacy_layer(final_risks.get("formal_risks", []) or []),
        "pending_review_items": _project_legacy_layer(final_risks.get("pending_review_items", []) or [], include_reason=True),
        "excluded_risks": _project_legacy_layer(final_risks.get("excluded_risks", []) or [], include_reason=True),
        "summary": {
            "high_risk_titles": list(summary.get("high_risk_titles", []) or []),
            "medium_risk_titles": list(summary.get("medium_risk_titles", []) or []),
            "manual_review_titles": list(summary.get("manual_review_titles", []) or []),
        },
        "basis_summary": list(summary.get("basis_summary", []) or []),
        "snapshot_version": snapshot.get("snapshot_version", SNAPSHOT_VERSION),
    }
    if governance is not None:
        projected["governance"] = governance.to_dict()
    if admission is not None:
        projected["risk_admission"] = admission.to_dict()
    return projected
