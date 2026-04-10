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

GOVERNANCE_FORMAL_REQUIRED_FIELDS = [
    "entry_type",
    "rule_id",
    "status",
    "canonical_title",
    "family_key",
    "allow_formal",
    "requires_hard_evidence",
    "source",
    "rationale",
    "migration_status",
]

GOVERNANCE_FORMAL_REQUIRED_SOURCE_FIELDS = [
    "origin_type",
    "origin_desc",
]

GOVERNANCE_FORMAL_REQUIRED_RATIONALE_FIELDS = [
    "migration_reason",
]

GOVERNANCE_FORMAL_REQUIRED_MIGRATION_STATUS_FIELDS = [
    "state",
]

CANDIDATE_REQUIRED_PATHS = [
    "README.md",
    "sources/README.md",
    "imports/README.md",
    "mappings/README.md",
    "snapshots/README.md",
]
FORMAL_ADMISSION_REQUIRED_FIELDS = [
    "family_key",
    "canonical_title",
    "allow_formal",
    "requires_hard_evidence",
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

    if _is_governance_formal_entry(rule):
        return _validate_governance_formal_dict(rule)

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

    if _is_formal_target_rule(rule):
        formal_admission = rule.get("formal_admission")
        if not isinstance(formal_admission, dict):
            errors.append("missing formal_admission block for formal rule")
        else:
            for field in FORMAL_ADMISSION_REQUIRED_FIELDS:
                if field not in formal_admission:
                    errors.append(f"missing formal_admission.{field}")
            if str(formal_admission.get("family_key", "")).strip() == "":
                errors.append("formal_admission.family_key must not be blank")
            canonical_title = str(formal_admission.get("canonical_title", "")).strip()
            if canonical_title == "":
                errors.append("formal_admission.canonical_title must not be blank")
            output_title = str(rule.get("output", {}).get("formal_title", "")).strip()
            if canonical_title and output_title and canonical_title != output_title:
                errors.append("formal_admission.canonical_title must match output.formal_title")
            allow_formal = formal_admission.get("allow_formal")
            if not isinstance(allow_formal, bool):
                errors.append("formal_admission.allow_formal must be boolean")
            requires_hard_evidence = formal_admission.get("requires_hard_evidence")
            if not isinstance(requires_hard_evidence, bool):
                errors.append("formal_admission.requires_hard_evidence must be boolean")
            status = str(rule.get("status", "")).strip()
            if isinstance(allow_formal, bool):
                if status == "active" and allow_formal is False:
                    errors.append("formal_admission.allow_formal conflicts with active status")
                if status != "active" and allow_formal is True:
                    errors.append("formal_admission.allow_formal conflicts with non-active status")

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
    return [validate_rule_file(item) for item in _iter_registry_yaml_files(root, include_example=True)]


def validate_candidate_directory(path: str | Path) -> ValidationResult:
    root = Path(path)
    errors: list[str] = []
    if not root.exists():
        return ValidationResult(path=root, errors=["candidate root does not exist"])
    if not root.is_dir():
        return ValidationResult(path=root, errors=["candidate root is not a directory"])

    for relative in CANDIDATE_REQUIRED_PATHS:
        candidate_path = root / relative
        if not candidate_path.exists():
            errors.append(f"missing candidate governance path: {relative}")

    subdirs = {
        "sources": root / "sources",
        "imports": root / "imports",
        "mappings": root / "mappings",
        "snapshots": root / "snapshots",
    }
    for name, directory in subdirs.items():
        if directory.exists() and not directory.is_dir():
            errors.append(f"candidate governance path is not a directory: {name}")

    return ValidationResult(path=root, errors=errors)


def validate_formal_admission_sources(registry_rules: list[dict], supplemental_payload: dict) -> list[str]:
    errors: list[str] = []
    registry_by_rule_id: dict[str, dict] = {}
    registry_by_family: dict[str, dict] = {}
    registry_by_title: dict[str, dict] = {}

    for rule in registry_rules:
        if not _is_formal_registry_entry(rule):
            continue
        descriptor = _extract_formal_registry_descriptor(rule)
        if descriptor is None:
            rule_id = str(rule.get("rule_id", "")).strip()
            errors.append(f"formal registry rule missing formal admission descriptor: {rule_id}")
            continue
        rule_id = descriptor["rule_id"]
        family_key = descriptor["family_key"]
        canonical_title = descriptor["canonical_title"]
        allow_formal = descriptor["allow_formal"]
        requires_hard_evidence = descriptor["requires_hard_evidence"]
        status = descriptor["status"]
        if not family_key or not canonical_title:
            errors.append(f"formal registry rule missing family/title mapping: {rule_id}")
            continue
        registry_by_rule_id[rule_id] = rule
        registry_by_family[family_key] = rule
        registry_by_title[canonical_title] = rule
        if status == "active" and allow_formal is not True:
            errors.append(f"formal registry allow_formal/status conflict: {rule_id}")
        if status != "active" and allow_formal is True:
            errors.append(f"formal registry allow_formal/status conflict: {rule_id}")
        if not isinstance(requires_hard_evidence, bool):
            errors.append(f"formal registry requires_hard_evidence invalid: {rule_id}")

    if "registry_overrides" in supplemental_payload:
        errors.append("formal admission supplemental config must not define registry_overrides")

    for item in supplemental_payload.get("supplemental_families", []):
        if not isinstance(item, dict):
            errors.append("supplemental_families must contain mapping items")
            continue
        governance_rule_id = str(item.get("governance_rule_id", "")).strip()
        family_key = str(item.get("family_key", "")).strip()
        canonical_title = str(item.get("canonical_title", "")).strip()
        status = str(item.get("status", "")).strip()
        allow_formal = item.get("allow_formal")
        requires_hard_evidence = item.get("requires_hard_evidence")
        errors.append(f"supplemental runtime families are closed after Q7: {governance_rule_id}")
        if not governance_rule_id.startswith("GOV-"):
            errors.append(f"supplemental family must use GOV- rule id: {governance_rule_id or '<blank>'}")
        if family_key in registry_by_family:
            errors.append(f"supplemental family conflicts with registry family_key: {family_key}")
        if canonical_title in registry_by_title:
            errors.append(f"supplemental family conflicts with registry canonical_title: {canonical_title}")
        if governance_rule_id in registry_by_rule_id:
            errors.append(f"supplemental family conflicts with registry rule_id: {governance_rule_id}")
        if status == "active" and allow_formal is not True:
            errors.append(f"supplemental family allow_formal/status conflict: {governance_rule_id}")
        if status != "active" and allow_formal is True:
            errors.append(f"supplemental family allow_formal/status conflict: {governance_rule_id}")
        if not isinstance(requires_hard_evidence, bool):
            errors.append(f"supplemental family requires_hard_evidence invalid: {governance_rule_id}")

    return errors


def load_registry_rules(path: str | Path) -> list[dict]:
    root = Path(path)
    return [load_rule_file(item) for item in _iter_registry_yaml_files(root)]


def collect_formal_admission_signals(registry_rules: list[dict], supplemental_payload: dict) -> list[str]:
    signals: list[str] = []
    registry_families = {
        descriptor["family_key"]
        for rule in registry_rules
        if (descriptor := _extract_formal_registry_descriptor(rule)) is not None
    }
    registry_titles = {
        descriptor["canonical_title"]
        for rule in registry_rules
        if (descriptor := _extract_formal_registry_descriptor(rule)) is not None
    }
    for item in supplemental_payload.get("supplemental_families", []):
        if not isinstance(item, dict):
            continue
        governance_rule_id = str(item.get("governance_rule_id", "")).strip()
        family_key = str(item.get("family_key", "")).strip()
        canonical_title = str(item.get("canonical_title", "")).strip()
        missing_materials = [str(value).strip() for value in item.get("missing_materials", []) if str(value).strip()]
        governance_signals = item.get("governance_signals", {})
        replay_bound_runs = governance_signals.get("replay_bound_runs", []) if isinstance(governance_signals, dict) else []
        whitelist_bound = bool(governance_signals.get("whitelist_bound")) if isinstance(governance_signals, dict) else False
        if family_key in registry_families or canonical_title in registry_titles:
            signals.append(f"supplemental family duplicates registry main source: {governance_rule_id}")
        if not missing_materials:
            signals.append(f"supplemental family appears migratable but is still retained: {governance_rule_id}")
        if replay_bound_runs or whitelist_bound:
            signals.append(
                f"supplemental family remains long-lived runtime dependency: {governance_rule_id}"
            )
    return signals


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


def _is_formal_target_rule(rule: dict) -> bool:
    classification = rule.get("classification")
    return isinstance(classification, dict) and str(classification.get("target_level", "")).strip() == "formal"


def _is_governance_formal_entry(rule: dict) -> bool:
    return str(rule.get("entry_type", "")).strip() == "governance_formal"


def _is_formal_registry_entry(rule: dict) -> bool:
    return _is_formal_target_rule(rule) or _is_governance_formal_entry(rule)


def _iter_registry_yaml_files(root: Path, *, include_example: bool = False) -> list[Path]:
    files = []
    for item in sorted(root.rglob("*.yaml")):
        if not include_example and item.name.startswith("_example"):
            continue
        files.append(item)
    return files


def _extract_formal_registry_descriptor(rule: dict) -> dict | None:
    if _is_formal_target_rule(rule):
        formal_admission = rule.get("formal_admission")
        if not isinstance(formal_admission, dict):
            return None
        return {
            "rule_id": str(rule.get("rule_id", "")).strip(),
            "family_key": str(formal_admission.get("family_key", "")).strip(),
            "canonical_title": str(formal_admission.get("canonical_title", "")).strip(),
            "allow_formal": formal_admission.get("allow_formal"),
            "requires_hard_evidence": formal_admission.get("requires_hard_evidence"),
            "status": str(rule.get("status", "")).strip(),
        }
    if _is_governance_formal_entry(rule):
        return {
            "rule_id": str(rule.get("rule_id", "")).strip(),
            "family_key": str(rule.get("family_key", "")).strip(),
            "canonical_title": str(rule.get("canonical_title", "")).strip(),
            "allow_formal": rule.get("allow_formal"),
            "requires_hard_evidence": rule.get("requires_hard_evidence"),
            "status": str(rule.get("status", "")).strip(),
        }
    return None


def _validate_governance_formal_dict(rule: dict) -> list[str]:
    errors: list[str] = []
    for field in GOVERNANCE_FORMAL_REQUIRED_FIELDS:
        if field not in rule:
            errors.append(f"missing governance_formal.{field}")

    if str(rule.get("rule_id", "")).strip().startswith("R-"):
        errors.append("governance_formal.rule_id must not use R- prefix")
    if str(rule.get("entry_type", "")).strip() != "governance_formal":
        errors.append("governance_formal.entry_type must equal governance_formal")

    status = rule.get("status")
    if status not in RULE_STATUSES:
        errors.append("invalid governance_formal.status")

    if str(rule.get("canonical_title", "")).strip() == "":
        errors.append("governance_formal.canonical_title must not be blank")
    if str(rule.get("family_key", "")).strip() == "":
        errors.append("governance_formal.family_key must not be blank")
    if not isinstance(rule.get("allow_formal"), bool):
        errors.append("governance_formal.allow_formal must be boolean")
    if not isinstance(rule.get("requires_hard_evidence"), bool):
        errors.append("governance_formal.requires_hard_evidence must be boolean")

    source = rule.get("source")
    if not isinstance(source, dict):
        errors.append("missing governance_formal.source")
    else:
        for field in GOVERNANCE_FORMAL_REQUIRED_SOURCE_FIELDS:
            if str(source.get(field, "")).strip() == "":
                errors.append(f"missing governance_formal.source.{field}")

    rationale = rule.get("rationale")
    if not isinstance(rationale, dict):
        errors.append("missing governance_formal.rationale")
    else:
        for field in GOVERNANCE_FORMAL_REQUIRED_RATIONALE_FIELDS:
            if str(rationale.get(field, "")).strip() == "":
                errors.append(f"missing governance_formal.rationale.{field}")

    migration_status = rule.get("migration_status")
    if not isinstance(migration_status, dict):
        errors.append("missing governance_formal.migration_status")
    else:
        for field in GOVERNANCE_FORMAL_REQUIRED_MIGRATION_STATUS_FIELDS:
            if str(migration_status.get(field, "")).strip() == "":
                errors.append(f"missing governance_formal.migration_status.{field}")

    return errors
