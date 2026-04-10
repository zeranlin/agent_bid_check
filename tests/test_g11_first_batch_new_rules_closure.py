from __future__ import annotations

from pathlib import Path

from app.governance.rule_registry import load_rule_file, validate_rule_file


ROOT = Path(__file__).resolve().parents[1]
TRACKER = ROOT / "docs" / "trackers" / "v2-remediation-tracker.md"
EXAMPLES = ROOT / "docs" / "governance" / "first-batch-new-rules-hit-examples-2026-04-08.md"
CLOSURE_NOTE = ROOT / "docs" / "governance" / "first-batch-new-rules-closure-note-2026-04-08.md"
TASK_G11 = ROOT / "docs" / "tasks" / "Task-G11-first-batch-new-rules-closure.md"


def test_g11_artifacts_exist() -> None:
    assert TRACKER.exists()
    assert EXAMPLES.exists()
    assert CLOSURE_NOTE.exists()
    assert TASK_G11.exists()


def test_r009_to_r012_rules_have_closed_or_waiting_statuses_and_valid_refs() -> None:
    expected_status = {
        "R-009": "active",
        "R-010": "active",
        "R-011": "active",
        "R-012": "active",
    }
    for rule_id, status in expected_status.items():
        path = ROOT / "rules" / "registry" / f"{rule_id}.yaml"
        result = validate_rule_file(path)
        assert result.ok, result.errors
        payload = load_rule_file(path)
        assert payload["status"] == status


def test_r009_to_r012_tasks_tracker_and_examples_are_aligned() -> None:
    tracker_text = TRACKER.read_text(encoding="utf-8")
    examples_text = EXAMPLES.read_text(encoding="utf-8")
    closure_text = CLOSURE_NOTE.read_text(encoding="utf-8")
    g11_text = TASK_G11.read_text(encoding="utf-8")

    expectations = {
        "R-009": "已通过",
        "R-010": "已通过",
        "R-011": "已通过",
        "R-012": "已通过",
    }
    for rule_id, task_status in expectations.items():
        task_path = ROOT / "docs" / "tasks" / f"{rule_id}.md"
        task_text = task_path.read_text(encoding="utf-8")
        assert f"任务编号：`{rule_id}`" in task_text or f"任务编号：{rule_id}" in task_text
        assert task_status in task_text
        assert rule_id in tracker_text
        assert rule_id in examples_text
        assert rule_id in closure_text
        assert rule_id in g11_text
