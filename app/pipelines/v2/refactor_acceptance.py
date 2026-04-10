from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REQUIRED_SCOPE_TASKS = [
    "Task-EP1",
    "Task-EP2",
    "Task-EP3",
    "Task-EP4",
    "Task-PB1",
    "Task-PB2",
    "Task-PB3",
    "Task-PB4",
    "Task-PU1",
    "Task-GR1",
    "Task-GR2",
]

TASK_ARTIFACT_HINTS = {
    "Task-EP1": ["data/results/v2/20260410-ep1-diesel-replay"],
    "Task-EP2": ["data/results/v2/20260410-ep2-diesel-source-replay", "data/results/v2/20260410-ep2-fuzhou-source-replay"],
    "Task-EP3": ["data/results/v2/20260410-ep3-diesel-domain-replay", "data/results/v2/20260410-ep3-fuzhou-domain-replay"],
    "Task-EP4": ["data/results/v2/20260410-ep4-diesel-evidence-replay", "data/results/v2/20260410-ep4-fuzhou-evidence-replay"],
    "Task-PB1": ["data/results/v2/20260410-pb1-diesel-problem-layer"],
    "Task-PB2": ["data/results/v2/20260410-pb2-diesel-problem-merge", "data/results/v2/20260410-pb2-fuzhou-fragment-boundary"],
    "Task-PB3": ["data/results/v2/20260410-pb3-diesel-cross-topic-conflict", "data/results/v2/20260410-pb3-fuzhou-no-overmerge"],
    "Task-PB4": ["data/results/v2/20260410-pb4-diesel-import-conflict", "data/results/v2/20260410-pb4-constructed-scoring-conflicts"],
    "Task-PU1": ["data/results/v2/20260410-pu1-diesel-conflict-replay", "data/results/v2/20260410-pu1-fuzhou-replay"],
    "Task-GR1": ["data/results/v2/gr1-diesel-baseline", "data/results/v2/gr1-fujian-baseline", "data/results/v2/gr1-fuzhou-baseline"],
    "Task-GR2": ["docs/trackers/v2-feedback-attribution-ledger.yaml", "scripts/run_feedback_attribution.py"],
}

REQUIRED_REPLAY_ARTIFACTS = [
    "final_snapshot.json",
    "final_output.json",
    "final_review.md",
    "replay_summary.json",
]

GR1_REPLAYS = {
    "diesel": "data/results/v2/gr1-diesel-baseline",
    "fujian": "data/results/v2/gr1-fujian-baseline",
    "fuzhou": "data/results/v2/gr1-fuzhou-baseline",
}

REQUIRED_ACCEPTANCE_DOCS = [
    "docs/governance/v2-evidence-problem-publish-refactor-roadmap.md",
    "docs/governance/v2-refactor-overall-acceptance-2026-04-10.md",
    "docs/trackers/v2-real-replay-baselines.yaml",
    "docs/trackers/v2-real-replay-issue-ledger.yaml",
    "docs/trackers/v2-feedback-attribution-ledger.yaml",
    "docs/tasks/Task-EP1-evidence-layer-foundation.md",
    "docs/tasks/Task-EP2-evidence-source-classification.md",
    "docs/tasks/Task-EP3-evidence-business-domain-classification.md",
    "docs/tasks/Task-EP4-clause-role-and-hard-evidence.md",
]

CONFLICT_SNAPSHOT_PATH = "data/results/v2/20260410-pu1-diesel-conflict-replay/final_snapshot.json"


def parse_tracker_task_statuses(tracker_path: str | Path) -> dict[str, dict[str, str]]:
    path = Path(tracker_path)
    text = path.read_text(encoding="utf-8")
    statuses: dict[str, dict[str, str]] = {}
    pattern = re.compile(r"^\|\s*(Task-[^|]+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$", re.MULTILINE)
    for task_id, task_name, task_type, status, conclusion in pattern.findall(text):
        statuses[task_id.strip()] = {
            "task_name": task_name.strip(),
            "task_type": task_type.strip(),
            "status": status.strip(),
            "conclusion": conclusion.strip(),
        }
    return statuses


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def validate_replay_artifact_dir(replay_dir: str | Path) -> dict[str, Any]:
    path = Path(replay_dir)
    present = [name for name in REQUIRED_REPLAY_ARTIFACTS if (path / name).exists()]
    missing = [name for name in REQUIRED_REPLAY_ARTIFACTS if name not in present]
    summary = _load_json(path / "replay_summary.json") if (path / "replay_summary.json").exists() else {}
    return {
        "replay_dir": str(path),
        "present_artifacts": present,
        "missing_artifacts": missing,
        "passed": not missing and bool(summary.get("passed", False)),
        "summary": summary,
    }


def _check_task_artifacts(root: Path, task_statuses: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for task_id in REQUIRED_SCOPE_TASKS:
        hints = TASK_ARTIFACT_HINTS.get(task_id, [])
        missing = [hint for hint in hints if not (root / hint).exists()]
        results.append(
            {
                "task_id": task_id,
                "status": task_statuses.get(task_id, {}).get("status", ""),
                "artifact_hints": hints,
                "missing_artifacts": missing,
                "artifacts_ok": not missing,
            }
        )
    return results


def _build_replay_alignment(root: Path) -> dict[str, Any]:
    replay_results: dict[str, Any] = {}
    missing_replays: list[str] = []
    failing_replays: list[str] = []
    for key, relative_dir in GR1_REPLAYS.items():
        path = root / relative_dir
        if not path.exists():
            missing_replays.append(key)
            continue
        result = validate_replay_artifact_dir(path)
        replay_results[key] = result
        if not result["passed"]:
            failing_replays.append(key)
    return {
        "replays": replay_results,
        "missing_replays": missing_replays,
        "failing_replays": failing_replays,
    }


def _build_document_alignment(root: Path) -> dict[str, Any]:
    missing = [relative_path for relative_path in REQUIRED_ACCEPTANCE_DOCS if not (root / relative_path).exists()]
    return {"missing_docs": missing, "required_docs": list(REQUIRED_ACCEPTANCE_DOCS)}


def _build_final_snapshot_alignment(root: Path) -> dict[str, Any]:
    path = root / CONFLICT_SNAPSHOT_PATH
    if not path.exists():
        return {"conflict_snapshot_ok": False, "reason": "missing_conflict_snapshot"}
    snapshot = _load_json(path)
    for layer in ("formal_risks", "pending_review_items", "excluded_risks"):
        for item in snapshot.get("final_risks", {}).get(layer, []):
            if item.get("problem_kind") == "conflict":
                ok = all(item.get(key) for key in ("left_side", "right_side", "conflict_reason", "conflict_evidence_links"))
                return {
                    "conflict_snapshot_ok": ok,
                    "problem_id": item.get("problem_id", ""),
                    "title": item.get("title", ""),
                    "conflict_type": item.get("conflict_type", ""),
                }
    return {"conflict_snapshot_ok": False, "reason": "no_conflict_problem"}


def build_refactor_acceptance_summary(root_path: str | Path) -> dict[str, Any]:
    root = Path(root_path).resolve()
    tracker_statuses = parse_tracker_task_statuses(root / "docs" / "trackers" / "v2-remediation-tracker.md")
    missing_tasks = [task_id for task_id in REQUIRED_SCOPE_TASKS if task_id not in tracker_statuses]
    invalid_status_tasks = [
        task_id
        for task_id in REQUIRED_SCOPE_TASKS
        if tracker_statuses.get(task_id, {}).get("status", "") not in {"已通过", "已关闭"}
    ]
    artifact_checks = _check_task_artifacts(root, tracker_statuses)
    artifact_missing_tasks = [item["task_id"] for item in artifact_checks if not item["artifacts_ok"]]
    replay_alignment = _build_replay_alignment(root)
    document_alignment = _build_document_alignment(root)
    final_snapshot_alignment = _build_final_snapshot_alignment(root)
    gate_passed = not any(
        [
            missing_tasks,
            invalid_status_tasks,
            artifact_missing_tasks,
            replay_alignment["missing_replays"],
            replay_alignment["failing_replays"],
            document_alignment["missing_docs"],
            not final_snapshot_alignment["conflict_snapshot_ok"],
        ]
    )
    return {
        "overall_ready_for_closure": gate_passed,
        "gate_passed": gate_passed,
        "tracker_alignment": {
            "missing_tasks": missing_tasks,
            "invalid_status_tasks": invalid_status_tasks,
            "artifact_missing_tasks": artifact_missing_tasks,
            "task_statuses": {task_id: tracker_statuses.get(task_id, {}) for task_id in REQUIRED_SCOPE_TASKS},
            "artifact_checks": artifact_checks,
        },
        "replay_alignment": replay_alignment,
        "document_alignment": document_alignment,
        "final_snapshot_alignment": final_snapshot_alignment,
    }
