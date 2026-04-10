from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml

from app.governance.rule_registry import load_registry_rules, validate_formal_admission_sources


PROJECT_ROOT = Path(__file__).resolve().parents[4]
RULE_REGISTRY_ROOT = PROJECT_ROOT / "rules" / "registry"
FORMAL_ADMISSION_REGISTRY_PATH = PROJECT_ROOT / "rules" / "governance" / "formal_admission_registry.yaml"

RegistrySource = Literal["registry", "governance_config"]
ResolutionOutcome = Literal["matched", "missing", "mismatch"]


@dataclass(frozen=True)
class FormalRegistryEntry:
    rule_id: str
    family_key: str
    canonical_title: str
    status: str
    source: RegistrySource
    allow_formal: bool
    requires_hard_evidence: bool


@dataclass(frozen=True)
class FormalRegistryResolution:
    outcome: ResolutionOutcome
    reason: str
    entry: FormalRegistryEntry | None


@dataclass(frozen=True)
class FormalRegistryIndex:
    by_rule_id: dict[str, FormalRegistryEntry]
    by_family_key: dict[str, FormalRegistryEntry]
    by_title: dict[str, FormalRegistryEntry]


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _normalize_rule_id(rule_id: str) -> str:
    value = str(rule_id or "").strip()
    if not value:
        return ""
    if "::" in value:
        tail = value.split("::", 1)[1]
        if tail.startswith("R-"):
            return tail
    return value


@lru_cache(maxsize=1)
def load_formal_registry_index() -> FormalRegistryIndex:
    governance_payload = _load_yaml(FORMAL_ADMISSION_REGISTRY_PATH)
    registry_rules = load_registry_rules(RULE_REGISTRY_ROOT)
    consistency_errors = validate_formal_admission_sources(registry_rules, governance_payload)
    if consistency_errors:
        raise ValueError("formal admission source inconsistency: " + " | ".join(consistency_errors))

    by_rule_id: dict[str, FormalRegistryEntry] = {}
    by_family_key: dict[str, FormalRegistryEntry] = {}
    by_title: dict[str, FormalRegistryEntry] = {}

    for payload in registry_rules:
        rule_id = str(payload.get("rule_id", "")).strip()
        status = str(payload.get("status", "")).strip()
        if str(payload.get("entry_type", "")).strip() == "governance_formal":
            title = str(payload.get("canonical_title", "")).strip()
            family_key = str(payload.get("family_key", "")).strip()
            canonical_title = title
            allow_formal = bool(payload.get("allow_formal", False))
            requires_hard_evidence = bool(payload.get("requires_hard_evidence", True))
        else:
            title = str(payload.get("output", {}).get("formal_title", "")).strip()
            if str(payload.get("classification", {}).get("target_level", "")).strip() != "formal":
                continue
            formal_admission = payload.get("formal_admission", {})
            family_key = str(formal_admission.get("family_key", "")).strip()
            canonical_title = str(formal_admission.get("canonical_title", "")).strip()
            allow_formal = bool(formal_admission.get("allow_formal", False))
            requires_hard_evidence = bool(formal_admission.get("requires_hard_evidence", True))
        if not rule_id or not title:
            continue
        entry = FormalRegistryEntry(
            rule_id=rule_id,
            family_key=family_key,
            canonical_title=canonical_title,
            status=status,
            source="registry",
            allow_formal=allow_formal,
            requires_hard_evidence=requires_hard_evidence,
        )
        by_rule_id[rule_id] = entry
        by_family_key[family_key] = entry
        by_title[title] = entry
        by_title[canonical_title] = entry

    for item in governance_payload.get("supplemental_families", []):
        if not isinstance(item, dict):
            continue
        family_key = str(item.get("family_key", "")).strip()
        canonical_title = str(item.get("canonical_title", "")).strip()
        governance_rule_id = str(item.get("governance_rule_id", "")).strip()
        status = str(item.get("status", "")).strip()
        if not family_key or not canonical_title or not governance_rule_id or not status:
            continue
        entry = FormalRegistryEntry(
            rule_id=governance_rule_id,
            family_key=family_key,
            canonical_title=canonical_title,
            status=status,
            source="governance_config",
            allow_formal=status == "active" and bool(item.get("allow_formal", True)),
            requires_hard_evidence=bool(item.get("requires_hard_evidence", True)),
        )
        by_rule_id[governance_rule_id] = entry
        by_family_key[family_key] = entry
        by_title.setdefault(canonical_title, entry)

    return FormalRegistryIndex(by_rule_id=by_rule_id, by_family_key=by_family_key, by_title=by_title)


def resolve_formal_registry_resolution(
    *,
    rule_id: str,
    family_key: str,
    title: str,
) -> FormalRegistryResolution:
    index = load_formal_registry_index()
    normalized_rule_id = _normalize_rule_id(rule_id)
    entry_by_rule = index.by_rule_id.get(normalized_rule_id)
    entry_by_family = index.by_family_key.get(str(family_key or "").strip())
    entry_by_title = index.by_title.get(str(title or "").strip())

    if entry_by_family is not None and entry_by_title is not None and entry_by_family.rule_id != entry_by_title.rule_id:
        return FormalRegistryResolution(
            outcome="mismatch",
            reason="family_key 与标题分别指向不同 formal registry 条目，默认不放入 formal。",
            entry=entry_by_family,
        )

    entry = entry_by_family or entry_by_title
    if entry is not None:
        return FormalRegistryResolution(
            outcome="matched",
            reason="family_key/title 已命中 formal registry。",
            entry=entry,
        )

    if entry_by_rule is not None:
        return FormalRegistryResolution(
            outcome="matched",
            reason="rule_id 已命中 formal registry。",
            entry=entry_by_rule,
        )

    return FormalRegistryResolution(
        outcome="missing",
        reason="未找到 family_key / rule_id / 标题对应的 formal registry 配置。",
        entry=None,
    )


def clear_formal_registry_cache() -> None:
    load_formal_registry_index.cache_clear()
