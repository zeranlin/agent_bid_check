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
        "technical_layer_decision": getattr(decision, "technical_layer_decision", decision.target_layer),
        "admission_reason": decision.admission_reason,
        "formal_gate_rule": decision.formal_gate_rule,
        "gate_rule": getattr(decision, "gate_rule", ""),
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
        "technical_layer_decision": getattr(decision, "technical_layer_decision", layer),
        "evidence_sufficiency": getattr(decision, "evidence_sufficiency", ""),
        "user_visible_decision_basis": getattr(decision, "user_visible_decision_basis", ""),
        "user_visible_gate": {
            "gate_passed": getattr(decision, "gate_passed", False),
            "gate_reason": getattr(decision, "gate_reason", ""),
            "gate_rule": getattr(decision, "gate_rule", ""),
            "stable_pending_config_id": getattr(decision, "stable_pending_config_id", ""),
        },
        "pending_gate": {
            "pending_gate_reason_code": getattr(decision, "pending_gate_reason_code", ""),
            "pending_gate_reason": getattr(decision, "pending_gate_reason", ""),
        },
        "formal_gate": {
            "formal_gate_passed": decision.formal_gate_passed,
            "formal_gate_reason": decision.formal_gate_reason,
            "formal_gate_rule": decision.formal_gate_rule,
            "formal_gate_exception_whitelist_hit": decision.formal_gate_exception_whitelist_hit,
            "formal_gate_family_allowed": decision.formal_gate_family_allowed,
            "formal_gate_evidence_passed": decision.formal_gate_evidence_passed,
        },
        "budget_trace": {
            "budget_hit": getattr(decision, "budget_hit", False),
            "budget_rule": getattr(decision, "budget_rule", ""),
            "budget_reason": getattr(decision, "budget_reason", ""),
            "budget_policy_id": getattr(decision, "budget_policy_id", ""),
            "absorbed_or_hidden_items": list(getattr(decision, "absorbed_or_hidden_items", [])),
        },
        "trace_summary": {
            "cross_topic_merge_reason": str(extras.get("cross_topic_merge_reason", "") or ""),
            "supporting_candidate_titles": list(extras.get("problem_supporting_candidate_titles", [])),
            "supporting_candidate_rule_ids": list(extras.get("problem_supporting_candidate_rule_ids", [])),
            "layer_conflict_inputs": list(extras.get("layer_conflict_inputs", [])),
            "family_governance_config_id": str(extras.get("problem_trace", {}).get("family_governance_config_id", "") or ""),
        },
        "family_key": getattr(problem, "family_key", candidate.risk_family),
    }


def _is_user_visible_snapshot_item(item: dict[str, Any]) -> bool:
    user_visible_gate = item.get("user_visible_gate", {}) if isinstance(item, dict) else {}
    gate_passed = bool(user_visible_gate.get("gate_passed", False)) if isinstance(user_visible_gate, dict) else False
    return gate_passed


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


def _hidden_reason_label(reason_code: str) -> str:
    mapping = {
        "same_family_absorbed_by_formal_primary": "同一家族已有 formal 主问题保留，当前项吸收到主问题 trace。",
        "supporting_hidden_under_family_primary": "当前项属于 family 附属问题，已吸收到主问题 supporting trace。",
        "internal_trace_only_under_family_primary": "当前项仅保留内部 trace，不再直接进入用户可见结果。",
        "weak_signal_no_rule_support": "当前仅为弱提示项，缺少稳定规则支撑，先不进入用户可见层。",
        "weak_signal_no_material_consequence": "当前仅为弱提示项，缺少明确合规后果，先不进入用户可见层。",
        "missing_user_visible_evidence": "当前缺少可对外展示的有效定位或摘录，仅保留内部 trace。",
        "family_repeat_budget": "同一家族在当前场景下已保留主问题，其余附属项下沉为内部 trace。",
        "low_value_signal_budget": "当前项属于低价值弱提示，在当前场景下不再进入用户可见结果。",
        "pending_count_budget": "当前文档场景下 pending 结果预算已命中，系统优先保留高价值且可解释的问题。",
    }
    normalized = str(reason_code or "").strip()
    return mapping.get(normalized, normalized)


def _build_evidence_anchor(*, locations: list[str] | None = None, excerpts: list[str] | None = None) -> dict[str, str]:
    normalized_locations = [str(item).strip() for item in locations or [] if str(item).strip()]
    normalized_excerpts = [str(item).strip() for item in excerpts or [] if str(item).strip()]
    return {
        "location": _first_text(normalized_locations, "未发现"),
        "excerpt": _first_text(normalized_excerpts, "未发现"),
    }


def _build_candidate_lookup(problem) -> dict[str, Any]:
    candidates = [problem.primary_candidate, *list(getattr(problem, "supporting_candidates", []))]
    lookup: dict[str, Any] = {}
    for item in candidates:
        title = str(getattr(item.decision, "canonical_title", "") or "").strip()
        if title and title not in lookup:
            lookup[title] = item
    return lookup


def _build_visible_ops_entry(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": str(item.get("title", "")).strip() or "未命名问题",
        "family_key": str(item.get("family_key", "")).strip(),
        "originally_detected": True,
        "visible_or_hidden": "visible",
        "hidden_by": "",
        "hidden_reason": str(item.get("user_visible_decision_basis", "")).strip()
        or str(item.get("admission_reason", "")).strip()
        or "该问题已保留在用户可见结果中。",
        "absorbed_by": "",
        "kept_item": {"title": str(item.get("title", "")).strip() or "未命名问题"},
        "source_layer": str(item.get("layer", "")).strip() or "未发现",
        "evidence_anchor": {
            "location": str(item.get("source_location", "")).strip() or "未发现",
            "excerpt": str(item.get("source_excerpt", "")).strip() or "未发现",
        },
    }


def _build_family_hidden_entries(problem) -> list[dict[str, Any]]:
    trace = dict(getattr(problem, "trace", {}) or {})
    family_key = str(getattr(problem, "family_key", "") or "").strip()
    config_id = str(trace.get("family_governance_config_id", "") or "").strip()
    candidate_lookup = _build_candidate_lookup(problem)
    entries: list[dict[str, Any]] = []
    for section_name in ("absorbed_user_visible_items", "internal_trace_only_items"):
        for item in trace.get(section_name, []) or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            matched = candidate_lookup.get(title)
            entries.append(
                {
                    "title": title,
                    "family_key": family_key,
                    "originally_detected": True,
                    "visible_or_hidden": "hidden",
                    "hidden_by": "family_absorption",
                    "hidden_reason": _hidden_reason_label(str(item.get("hidden_reason", "")).strip())
                    or f"已吸收到主问题《{problem.canonical_title}》的 trace 中。",
                    "reason_code": str(item.get("hidden_reason", "")).strip(),
                    "config_id": config_id,
                    "gate_rule": "",
                    "policy_id": "",
                    "absorbed_by": str(item.get("absorbed_by", "")).strip() or problem.canonical_title,
                    "kept_item": {
                        "title": str(item.get("absorbed_by", "")).strip() or problem.canonical_title,
                        "problem_id": str(item.get("absorbed_by_problem_id", "")).strip() or problem.problem_id,
                    },
                    "source_layer": str(item.get("source_bucket", "")).strip()
                    or str(item.get("prior_bucket", "")).strip()
                    or "problem_layer",
                    "source_layer_detail": "problem_layer",
                    "evidence_anchor": _build_evidence_anchor(
                        locations=list(getattr(matched, "source_locations", []) or []),
                        excerpts=list(getattr(matched, "source_excerpts", []) or []),
                    ),
                }
            )
    return entries


def _build_hidden_ops_entries(admission) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for candidate in getattr(admission, "excluded_risks", []):
        decision = admission.decisions.get(candidate.rule_id)
        if decision is None:
            continue
        if str(getattr(decision, "pending_gate_reason_code", "")).strip() == "missing_user_visible_evidence":
            continue
        hidden_by = ""
        if getattr(decision, "budget_hit", False):
            hidden_by = "result_budget"
        elif not getattr(decision, "user_visible_gate_passed", False):
            hidden_by = "user_visible_gate"
        if not hidden_by:
            continue
        linkage = dict((getattr(decision, "absorbed_or_hidden_items", []) or [{}])[0])
        entries.append(
            {
                "title": str(candidate.title).strip() or "未命名问题",
                "family_key": str(candidate.risk_family).strip(),
                "originally_detected": True,
                "visible_or_hidden": "hidden",
                "hidden_by": hidden_by,
                "hidden_reason": str(
                    getattr(decision, "budget_reason", "")
                    if hidden_by == "result_budget"
                    else getattr(decision, "user_visible_gate_reason", "")
                ).strip()
                or str(getattr(decision, "admission_reason", "")).strip()
                or _hidden_reason_label(
                    getattr(decision, "budget_rule", "") if hidden_by == "result_budget" else getattr(decision, "pending_gate_reason_code", "")
                ),
                "reason_code": str(
                    getattr(decision, "budget_rule", "")
                    if hidden_by == "result_budget"
                    else getattr(decision, "pending_gate_reason_code", "")
                ).strip(),
                "config_id": str(getattr(decision, "stable_pending_config_id", "")).strip(),
                "gate_rule": str(getattr(decision, "user_visible_gate_rule", "")).strip() or str(getattr(decision, "gate_rule", "")).strip(),
                "policy_id": str(getattr(decision, "budget_policy_id", "")).strip(),
                "absorbed_by": str(linkage.get("kept_title", "")).strip(),
                "kept_item": (
                    {
                        "title": str(linkage.get("kept_title", "")).strip(),
                        "rule_id": str(linkage.get("kept_rule_id", "")).strip(),
                        "family_key": str(linkage.get("kept_family_key", "")).strip(),
                    }
                    if str(linkage.get("kept_title", "")).strip()
                    else {}
                ),
                "source_layer": str(getattr(decision, "technical_layer_decision", "")).strip() or "excluded_risks",
                "source_layer_detail": "risk_admission",
                "evidence_anchor": _build_evidence_anchor(
                    locations=list(getattr(candidate, "source_locations", []) or []),
                    excerpts=list(getattr(candidate, "source_excerpts", []) or []),
                ),
            }
        )
    return entries


def _build_ops_explanation_summary(problems, admission, final_risks: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    visible_items = [
        _build_visible_ops_entry(item)
        for layer_name in ("formal_risks", "pending_review_items")
        for item in final_risks.get(layer_name, [])
        if isinstance(item, dict)
    ]
    family_hidden = [entry for problem in getattr(problems, "problems", []) for entry in _build_family_hidden_entries(problem)]
    decision_hidden = _build_hidden_ops_entries(admission)
    hidden_items = [*family_hidden, *decision_hidden]
    hidden_by_gate_count = sum(1 for item in hidden_items if item.get("hidden_by") == "user_visible_gate")
    hidden_by_budget_count = sum(1 for item in hidden_items if item.get("hidden_by") == "result_budget")
    absorbed_by_family_count = sum(1 for item in hidden_items if item.get("hidden_by") == "family_absorption")
    excluded_internal_count = len(getattr(admission, "excluded_risks", []) or [])
    return {
        "stats": {
            "hidden_by_gate_count": hidden_by_gate_count,
            "hidden_by_budget_count": hidden_by_budget_count,
            "absorbed_by_family_count": absorbed_by_family_count,
            "excluded_internal_count": excluded_internal_count,
        },
        "visible_items": visible_items,
        "hidden_items": hidden_items,
        "detection_note": "若某标题未出现在 visible_items 或 hidden_items 中，表示本次运行未识别到对应问题。",
    }


def _collect_layer_items(admission, layer_name: str, problem_map: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for candidate in getattr(admission, layer_name):
        decision = admission.decisions.get(candidate.rule_id)
        if decision is None:
            continue
        built = _build_snapshot_risk_item(candidate, decision, layer_name, problem_map)
        if _is_user_visible_snapshot_item(built):
            items.append(built)
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
    ops_explanation_summary = _build_ops_explanation_summary(problems, admission, final_risks)
    domain_context = {}
    if isinstance(getattr(admission, "input_summary", None), dict):
        domain_context = dict(admission.input_summary.get("domain_context", {}) or {})
    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "run_metadata": {
            "document_name": document_name,
            "generated_at": generated_at or datetime.now().isoformat(timespec="seconds"),
            "document_domain": str(domain_context.get("document_domain", "") or ""),
            "domain_confidence": float(domain_context.get("domain_confidence", 0.0) or 0.0),
            "domain_policy_id": str(domain_context.get("domain_policy_id", "") or ""),
            "domain_evidence": list(domain_context.get("domain_evidence", []) or []),
        },
        "input_metadata": {
            "subject": baseline_report.subject or document_name,
            "description_lines": _build_description_lines(structure, topics),
        },
        "summary": summary,
        "final_risks": final_risks,
        "ops_explanation_summary": ops_explanation_summary,
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
    ops_summary = snapshot.get("ops_explanation_summary", {}) if isinstance(snapshot, dict) else {}
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

    excluded = [item for item in (final_risks.get("excluded_risks", []) or []) if isinstance(item, dict)]
    if excluded:
        lines.extend(["---", "", "## 已排除项摘要", ""])
        lines.append(f"- 已排除数量：{len(excluded)}")
        for item in excluded:
            title = str(item.get("title", "")).strip() or "已排除项"
            reason = str(item.get("admission_reason", "")).strip() or "已按准入规则排除。"
            lines.append(f"- {title}：{reason}")

    if isinstance(ops_summary, dict) and (ops_summary.get("hidden_items") or ops_summary.get("visible_items")):
        stats = ops_summary.get("stats", {}) if isinstance(ops_summary.get("stats", {}), dict) else {}
        hidden_items = [item for item in (ops_summary.get("hidden_items", []) or []) if isinstance(item, dict)]
        lines.extend(["---", "", "## 运维解释摘要", ""])
        lines.append(f"- gate 拦截：{int(stats.get('hidden_by_gate_count', 0) or 0)}")
        lines.append(f"- budget 压缩：{int(stats.get('hidden_by_budget_count', 0) or 0)}")
        lines.append(f"- family 吸收：{int(stats.get('absorbed_by_family_count', 0) or 0)}")
        lines.append(f"- excluded/internal：{int(stats.get('excluded_internal_count', 0) or 0)}")
        detection_note = str(ops_summary.get("detection_note", "")).strip()
        if detection_note:
            lines.append(f"- 说明：{detection_note}")
        for item in hidden_items:
            title = str(item.get("title", "")).strip() or "未命名问题"
            hidden_by = str(item.get("hidden_by", "")).strip() or "unknown"
            reason = str(item.get("hidden_reason", "")).strip() or "未发现"
            kept_title = str((item.get("kept_item", {}) or {}).get("title", "")).strip()
            line = f"- {title}：由 {hidden_by} 压下；原因：{reason}"
            if kept_title:
                line += f"；保留主项：{kept_title}"
            lines.append(line)

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
        "ops_explanation_summary": dict(snapshot.get("ops_explanation_summary", {}) or {}),
        "snapshot_version": snapshot.get("snapshot_version", SNAPSHOT_VERSION),
    }
    if governance is not None:
        projected["governance"] = governance.to_dict()
    if admission is not None:
        projected["risk_admission"] = admission.to_dict()
    return projected
