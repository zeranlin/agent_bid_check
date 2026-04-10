from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


ROOT_CAUSE_LAYERS = {
    "evidence_layer",
    "problem_layer",
    "risk_admission",
    "publish_layer",
    "rule_layer",
    "unknown",
}


def load_feedback_attribution_registry(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path).expanduser().resolve()
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("feedback attribution registry must be a mapping")
    cases = payload.get("feedback_cases", [])
    if not isinstance(cases, list) or not cases:
        raise ValueError("feedback attribution registry must define non-empty feedback_cases")
    normalized = dict(payload)
    normalized["_config_path"] = str(path)
    return normalized


def _resolve_path(raw_path: str, config_path: str | None = None) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path.resolve()
    if config_path:
        return (Path(config_path).resolve().parent / path).resolve()
    return path.resolve()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalize_signals(record: dict[str, Any]) -> set[str]:
    values = record.get("signals", [])
    if not isinstance(values, list):
        return set()
    return {str(item).strip() for item in values if str(item).strip()}


def _iter_snapshot_items(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    final_risks = snapshot.get("final_risks", {}) if isinstance(snapshot, dict) else {}
    items: list[dict[str, Any]] = []
    for layer in ("formal_risks", "pending_review_items", "excluded_risks"):
        layer_items = final_risks.get(layer, [])
        if isinstance(layer_items, list):
            items.extend(item for item in layer_items if isinstance(item, dict))
    return items


def _find_snapshot_item(snapshot: dict[str, Any], record: dict[str, Any]) -> dict[str, Any] | None:
    problem_id = str(record.get("problem_id", "")).strip()
    family_key = str(record.get("family_key", "")).strip()
    title = str(record.get("feedback_title", "")).strip()
    conflict_type = str(record.get("conflict_type", "")).strip()
    for item in _iter_snapshot_items(snapshot):
        if problem_id and str(item.get("problem_id", "")).strip() == problem_id:
            return item
        if family_key and str(item.get("family_key", "")).strip() == family_key:
            return item
        if conflict_type and str(item.get("conflict_type", "")).strip() == conflict_type:
            return item
        if title and str(item.get("title", "")).strip() == title:
            return item
    return None


def _find_problem_trace(snapshot: dict[str, Any], problem_id: str) -> dict[str, Any] | None:
    for item in snapshot.get("problem_trace_summary", []) if isinstance(snapshot, dict) else []:
        if isinstance(item, dict) and str(item.get("problem_id", "")).strip() == problem_id:
            return item
    return None


def _suggest_disposition(root_cause_layer: str, record: dict[str, Any], signals: set[str]) -> str:
    if "invalid_feedback" in signals:
        return "标记为排除/误反馈"
    if root_cause_layer == "publish_layer":
        return "标记为展示修复"
    if root_cause_layer == "rule_layer":
        return "标记为规则补充"
    if "sample_gap" in signals:
        return "标记为样本补充"
    if root_cause_layer == "unknown":
        return "并入已有任务"
    return "新建整改任务"


def _suggest_task_type(root_cause_layer: str) -> str:
    return {
        "evidence_layer": "证据层补强任务",
        "problem_layer": "问题层归并整改任务",
        "risk_admission": "准入层门禁整改任务",
        "publish_layer": "发布层渲染修复任务",
        "rule_layer": "规则纳管补充任务",
        "unknown": "人工复核分诊任务",
    }.get(root_cause_layer, "人工复核分诊任务")


def attribute_feedback_record(
    record: dict[str, Any],
    *,
    replay_summary: dict[str, Any] | None = None,
    final_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = final_snapshot or {}
    summary = replay_summary or {}
    signals = _normalize_signals(record)
    evidence: list[str] = []
    confidence = 0.45

    root_cause_layer = "unknown"
    feedback_type = str(record.get("feedback_type", "")).strip()

    snapshot_item = _find_snapshot_item(snapshot, record)
    if snapshot_item is not None:
        evidence.append(f"matched_snapshot_problem:{snapshot_item.get('problem_id', '')}")
        if snapshot_item.get("conflict_type"):
            evidence.append(f"conflict_type:{snapshot_item.get('conflict_type', '')}")

    if feedback_type == "展示错误" or signals & {"history_leak", "web_render_mismatch", "final_snapshot_projection_gap"}:
        root_cause_layer = "publish_layer"
        confidence = 0.95
        evidence.append("display-symptom-detected")
    elif feedback_type == "层级错误" or (
        str(record.get("expected_layer", "")).strip()
        and str(record.get("actual_layer", "")).strip()
        and str(record.get("expected_layer", "")).strip() != str(record.get("actual_layer", "")).strip()
    ):
        root_cause_layer = "risk_admission"
        confidence = 0.92
        evidence.append(
            f"layer-mismatch:{record.get('actual_layer', '')}->{record.get('expected_layer', '')}"
        )
    elif signals & {
        "template_clause_as_body",
        "placeholder_clause_as_body",
        "source_kind_misclassified",
        "business_domain_misclassified",
        "hard_evidence_wrong",
        "missing_evidence_ids",
    }:
        root_cause_layer = "evidence_layer"
        confidence = 0.9
        evidence.extend(sorted(signals & {
            "template_clause_as_body",
            "placeholder_clause_as_body",
            "source_kind_misclassified",
            "business_domain_misclassified",
            "hard_evidence_wrong",
            "missing_evidence_ids",
        }))
    elif signals & {
        "wrong_merge",
        "cross_topic_overmerge",
        "duplicate_problem",
        "split_problem_missing",
        "conflict_problem_missing",
    }:
        root_cause_layer = "problem_layer"
        confidence = 0.9
        evidence.extend(sorted(signals & {
            "wrong_merge",
            "cross_topic_overmerge",
            "duplicate_problem",
            "split_problem_missing",
            "conflict_problem_missing",
        }))
    elif signals & {"rule_missing", "registry_gap", "canonical_title_registry_drift"}:
        root_cause_layer = "rule_layer"
        confidence = 0.88
        evidence.extend(sorted(signals & {"rule_missing", "registry_gap", "canonical_title_registry_drift"}))
    elif snapshot_item is not None and snapshot_item.get("problem_kind") == "conflict":
        has_conflict_fields = all(
            snapshot_item.get(key)
            for key in ("left_side", "right_side", "conflict_reason", "conflict_evidence_links")
        )
        if not has_conflict_fields:
            problem_trace = _find_problem_trace(snapshot, str(snapshot_item.get("problem_id", "")).strip())
            if problem_trace:
                root_cause_layer = "publish_layer"
                confidence = 0.89
                evidence.append("conflict-fields-missing-in-final-risk-item")
            else:
                root_cause_layer = "problem_layer"
                confidence = 0.75
                evidence.append("conflict-fields-missing-upstream")
    elif feedback_type == "漏报" and summary.get("missing_should_report"):
        root_cause_layer = "rule_layer"
        confidence = 0.72
        evidence.append("replay-summary-missing-should-report")
    elif feedback_type == "追溯缺失" and snapshot_item is not None:
        if not snapshot_item.get("evidence_ids"):
            root_cause_layer = "evidence_layer"
            confidence = 0.78
            evidence.append("snapshot-item-missing-evidence-ids")
        else:
            root_cause_layer = "publish_layer"
            confidence = 0.7
            evidence.append("trace-present-upstream-but-not-visible")

    disposition = _suggest_disposition(root_cause_layer, record, signals)
    suggested_task_type = _suggest_task_type(root_cause_layer)
    attribution_reason = {
        "feedback_type": feedback_type,
        "signals": sorted(signals),
        "why": evidence or ["insufficient-signals"],
    }

    return {
        "feedback_id": str(record.get("feedback_id", "")).strip(),
        "source_document": str(record.get("source_document", "")).strip(),
        "source_run_id": str(record.get("source_run_id", "")).strip(),
        "feedback_type": feedback_type,
        "feedback_title": str(record.get("feedback_title", "")).strip(),
        "expected_behavior": str(record.get("expected_behavior", "")).strip(),
        "actual_behavior": str(record.get("actual_behavior", "")).strip(),
        "suspected_layer": str(record.get("suspected_layer", "")).strip(),
        "root_cause_layer": root_cause_layer,
        "confidence": round(confidence, 2),
        "evidence": evidence,
        "disposition": disposition,
        "suggested_task_type": suggested_task_type,
        "attribution_reason": attribution_reason,
    }


def attribute_feedback_batch(registry: dict[str, Any]) -> list[dict[str, Any]]:
    config_path = registry.get("_config_path")
    decisions: list[dict[str, Any]] = []
    for record in registry.get("feedback_cases", []):
        run_dir = str(record.get("source_run_dir", "")).strip()
        snapshot = {}
        replay_summary = {}
        if run_dir:
            resolved = _resolve_path(run_dir, config_path)
            snapshot = _load_json(resolved / "final_snapshot.json")
            replay_summary = _load_json(resolved / "replay_summary.json")
        decisions.append(attribute_feedback_record(record, replay_summary=replay_summary, final_snapshot=snapshot))
    return decisions
