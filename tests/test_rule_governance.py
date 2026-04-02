from __future__ import annotations

from pathlib import Path

from app.governance.rule_registry import (
    RULE_STATUSES,
    can_transition_rule_status,
    load_rule_file,
    validate_rule_dict,
    validate_rule_file,
)


ROOT = Path(__file__).resolve().parents[1]


def test_rule_template_can_be_loaded() -> None:
    template = load_rule_file(ROOT / "rules/templates/rule_template.yaml")
    assert template["rule_id"] == "R-000"
    assert template["status"] == "draft"
    assert "trigger_conditions" in template
    assert "output" in template
    assert "formal_title" in template["output"]


def test_rule_validator_fails_when_required_fields_are_missing() -> None:
    errors = validate_rule_dict(
        {
            "rule_id": "R-BAD",
            "rule_name": "缺字段规则",
            "status": "draft",
            "output": {},
            "samples": {},
            "tests": {},
            "task_refs": {},
        }
    )
    assert "missing required field: trigger_conditions" in errors
    assert "missing required field: exclude_conditions" in errors
    assert "missing output.formal_title" in errors
    assert "missing samples references" in errors
    assert "missing tests references" in errors
    assert "missing task_refs references" in errors


def test_example_rule_file_passes_validation() -> None:
    result = validate_rule_file(ROOT / "rules/registry/_example_rule.yaml")
    assert result.ok, result.errors


def test_rule_status_flow_is_defined() -> None:
    assert RULE_STATUSES == [
        "draft",
        "in_progress",
        "review",
        "active",
        "rejected",
        "deprecated",
    ]
    assert can_transition_rule_status("draft", "in_progress") is True
    assert can_transition_rule_status("review", "active") is True
    assert can_transition_rule_status("active", "draft") is False
