from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


RULE_STATUSES = [
    "draft",
    "in_progress",
    "review",
    "active",
    "rejected",
    "deprecated",
]

RULE_STATUS_TRANSITIONS = {
    "draft": {"in_progress", "rejected"},
    "in_progress": {"review", "draft", "rejected"},
    "review": {"active", "in_progress", "rejected", "deprecated"},
    "active": {"deprecated", "review"},
    "rejected": set(),
    "deprecated": set(),
}

REQUIRED_TOP_LEVEL_FIELDS = [
    "rule_id",
    "rule_name",
    "rule_version",
    "status",
    "owner",
    "source",
    "classification",
    "trigger_conditions",
    "exclude_conditions",
    "downgrade_conditions",
    "output",
    "samples",
    "tests",
    "task_refs",
    "activation",
    "history",
]


@dataclass
class ValidationResult:
    path: Path
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def load_rule_file(path: str | Path) -> dict:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValueError("rule file must contain a top-level mapping")
    return payload


def can_transition_rule_status(current_status: str, next_status: str) -> bool:
    if current_status not in RULE_STATUS_TRANSITIONS:
        return False
    if current_status == next_status:
        return True
    return next_status in RULE_STATUS_TRANSITIONS[current_status]


def validate_rule_dict(rule: dict) -> list[str]:
    errors: list[str] = []

    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in rule:
            errors.append(f"missing required field: {field}")

    status = rule.get("status")
    if status not in RULE_STATUSES:
        errors.append(
            "invalid status: expected one of "
            + ", ".join(RULE_STATUSES)
        )

    trigger_conditions = rule.get("trigger_conditions")
    if not _has_condition_content(trigger_conditions):
        errors.append("missing trigger_conditions content")

    exclude_conditions = rule.get("exclude_conditions")
    if not _has_condition_content(exclude_conditions):
        errors.append("missing exclude_conditions content")

    output = rule.get("output")
    if not isinstance(output, dict) or not str(output.get("formal_title", "")).strip():
        errors.append("missing output.formal_title")

    samples = rule.get("samples")
    if not _has_reference_content(samples):
        errors.append("missing samples references")

    tests = rule.get("tests")
    if not _has_reference_content(tests):
        errors.append("missing tests references")

    task_refs = rule.get("task_refs")
    if not _has_reference_content(task_refs):
        errors.append("missing task_refs references")

    return errors


def validate_rule_file(path: str | Path) -> ValidationResult:
    resolved = Path(path)
    try:
        payload = load_rule_file(resolved)
    except Exception as exc:  # pragma: no cover - defensive path
        return ValidationResult(path=resolved, errors=[f"failed to load rule file: {exc}"])
    return ValidationResult(path=resolved, errors=validate_rule_dict(payload))


def validate_rule_directory(path: str | Path) -> list[ValidationResult]:
    root = Path(path)
    return [validate_rule_file(item) for item in sorted(root.glob("*.yaml"))]


def _has_condition_content(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    for key in ("all_of", "any_of"):
        value = payload.get(key)
        if isinstance(value, list) and any(str(item).strip() for item in value):
            return True
    return False


def _has_reference_content(payload: object) -> bool:
    if isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list) and any(str(item).strip() for item in value):
                return True
    if isinstance(payload, list):
        return any(str(item).strip() for item in payload)
    return False

