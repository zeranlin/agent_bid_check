from __future__ import annotations

from pathlib import Path

import yaml


FEEDBACK_ROOT = Path("feedback")
REQUIRED_KEYS = {
    "feedback_id",
    "file_name",
    "feedback_type",
    "source_location",
    "customer_feedback",
    "m_initial_analysis",
    "root_cause_layer",
    "task_type",
    "linked_task",
    "fix_summary",
    "real_regression_output",
    "regression_result",
}


def test_feedback_records_follow_unified_schema() -> None:
    template = yaml.safe_load((FEEDBACK_ROOT / "templates/customer_feedback_template.yaml").read_text(encoding="utf-8"))
    assert REQUIRED_KEYS.issubset(template.keys())

    record_paths = sorted((FEEDBACK_ROOT / "records").glob("FB-*.yaml"))
    assert len(record_paths) >= 2

    for path in record_paths:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert REQUIRED_KEYS.issubset(payload.keys()), path.name
        assert payload["feedback_type"] in {"漏报", "误报"}
        assert payload["linked_task"] == "G-004"
        assert isinstance(payload["fix_summary"], list) and payload["fix_summary"]


def test_feedback_matrix_covers_closed_loop_cases() -> None:
    matrix = (FEEDBACK_ROOT / "records" / "G-004-feedback-matrix.md").read_text(encoding="utf-8")
    assert "FB-G004-001" in matrix
    assert "FB-G004-002" in matrix
    assert "漏报" in matrix
    assert "误报" in matrix
