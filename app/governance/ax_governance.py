from __future__ import annotations

from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
AX_GOVERNANCE_PATHS = {
    "stable_pending": ROOT / "rules" / "governance" / "ax_stable_pending.yaml",
    "domain_policy": ROOT / "rules" / "governance" / "ax_domain_policy.yaml",
    "budget_policy": ROOT / "rules" / "governance" / "ax_budget_policy.yaml",
    "family_governance": ROOT / "rules" / "governance" / "ax_family_governance.yaml",
}
AX_ALLOWED_STATUSES = {"active", "deprecated", "draft"}
VALID_DOCUMENT_DOMAINS = {
    "engineering_maintenance_construction",
    "goods_procurement",
    "service_procurement",
}
KNOWN_AX_FAMILY_REFERENCES = {
    "acceptance_testing_cost",
    "brand_bias",
    "certification_scoring_bundle",
    "energy_policy_missing",
    "import_consistency",
    "missing_detection_or_cert_requirement",
    "no_crime_submission_timing",
    "sample_acceptance_gate",
    "scoring_clarity",
    "software_copyright_competition",
}
LEGACY_CODE_CONSTANTS = {
    "app.pipelines.v2.risk_admission.user_visible_gate": ("STABLE_PENDING_FAMILIES", "STABLE_PENDING_TITLE_RULES"),
    "app.pipelines.v2.risk_admission.domain_policy": ("DOMAIN_RESULT_POLICIES",),
    "app.pipelines.v2.problem_layer.pipeline": ("FAMILY_PRODUCT_RULES",),
}
AX_REQUIRED_ENTRY_FIELDS = {
    "id",
    "status",
    "scope",
    "reason",
    "source",
    "version",
    "owner",
    "last_updated_at",
}


@dataclass(frozen=True)
class StablePendingFamilyConfig:
    config_id: str
    family_key: str
    reason: str
    gate_rule: str


@dataclass(frozen=True)
class StablePendingPatternConfig:
    config_id: str
    pattern: str
    reason: str
    gate_rule: str


@dataclass(frozen=True)
class DomainResultPolicy:
    policy_id: str
    document_domain: str
    formal_output_strategy: str
    pending_output_strategy: str
    family_repeat_tolerance: int
    weak_signal_threshold: str
    internal_signal_visibility: str
    budget_policy_id: str
    reason: str
    source: str
    version: int
    owner: str
    last_updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BudgetPolicy:
    policy_id: str
    document_domain: str
    formal_count_budget: int
    pending_count_budget: int
    family_repeat_budget: int
    low_value_signal_budget: int
    priority_title_patterns: tuple[str, ...] = field(default_factory=tuple)
    low_value_title_patterns: tuple[str, ...] = field(default_factory=tuple)
    reason: str = ""
    source: str = ""
    version: int = 1
    owner: str = ""
    last_updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FamilyGovernanceConfig:
    config_id: str
    family_key: str
    canonical_title: str
    match_family_keys: tuple[str, ...] = field(default_factory=tuple)
    match_title_patterns: tuple[str, ...] = field(default_factory=tuple)
    require_any_title_patterns: tuple[str, ...] = field(default_factory=tuple)
    preferred_topics: tuple[str, ...] = field(default_factory=tuple)
    primary_title_patterns: tuple[str, ...] = field(default_factory=tuple)
    internal_title_patterns: tuple[str, ...] = field(default_factory=tuple)
    merge_reason: str = ""
    primary_selection_reason: str = ""
    supporting_visible_problem_limit: int = 0
    source: str = ""
    version: int = 1
    owner: str = ""
    last_updated_at: str = ""

    def to_problem_rule(self) -> dict[str, Any]:
        return {
            "config_id": self.config_id,
            "canonical_title": self.canonical_title,
            "match_family_keys": self.match_family_keys,
            "match_title_patterns": self.match_title_patterns,
            "require_any_title_patterns": self.require_any_title_patterns,
            "preferred_topics": self.preferred_topics,
            "primary_title_patterns": self.primary_title_patterns,
            "internal_title_patterns": self.internal_title_patterns,
            "merge_reason": self.merge_reason,
            "primary_selection_reason": self.primary_selection_reason,
            "supporting_visible_problem_limit": self.supporting_visible_problem_limit,
            "source": self.source,
            "version": self.version,
            "owner": self.owner,
            "last_updated_at": self.last_updated_at,
        }


@dataclass(frozen=True)
class AxGovernanceIndex:
    stable_pending_families: dict[str, StablePendingFamilyConfig]
    stable_pending_patterns: tuple[StablePendingPatternConfig, ...]
    domain_policies: dict[str, DomainResultPolicy]
    budget_policies: dict[str, BudgetPolicy]
    family_governance: dict[str, FamilyGovernanceConfig]


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"ax governance file must be mapping: {path}")
    return payload


def load_ax_governance_sources() -> dict[str, dict[str, Any]]:
    return {name: _load_yaml(path) for name, path in AX_GOVERNANCE_PATHS.items()}


def clear_ax_governance_cache() -> None:
    load_ax_governance_index.cache_clear()


def _entry_errors(kind: str, entry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in AX_REQUIRED_ENTRY_FIELDS:
        if field not in entry:
            errors.append(f"missing ax governance field {kind}.{field}: {entry.get('id', '<unknown>')}")
    status = str(entry.get("status", "")).strip()
    if status not in AX_ALLOWED_STATUSES:
        errors.append(f"invalid ax governance status: {entry.get('id', '<unknown>')} -> {status}")
    if not isinstance(entry.get("scope"), dict):
        errors.append(f"ax governance scope must be mapping: {entry.get('id', '<unknown>')}")
    return errors


def _validate_stable_pending(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for entry in payload.get("entries", []):
        errors.extend(_entry_errors("stable_pending", entry))
        condition = entry.get("condition", {})
        if not isinstance(condition, dict):
            errors.append(f"stable_pending condition must be mapping: {entry.get('id', '<unknown>')}")
            continue
        family_key = str(condition.get("family_key", "")).strip()
        pattern = str(entry.get("pattern", "")).strip()
        if not family_key and not pattern:
            errors.append(f"stable_pending requires family_key or pattern: {entry.get('id', '<unknown>')}")
        if family_key and family_key not in KNOWN_AX_FAMILY_REFERENCES:
            errors.append(f"invalid ax family reference: {family_key}")
        rule = entry.get("rule", {})
        if isinstance(rule, str):
            if not rule.strip():
                errors.append(f"stable_pending rule must not be blank: {entry.get('id', '<unknown>')}")
        elif not isinstance(rule, dict):
            errors.append(f"stable_pending rule must be mapping or string: {entry.get('id', '<unknown>')}")
    return errors


def _validate_budget_policy(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for entry in payload.get("entries", []):
        errors.extend(_entry_errors("budget_policy", entry))
        condition = entry.get("condition", {})
        if not isinstance(condition, dict):
            errors.append(f"budget_policy condition must be mapping: {entry.get('id', '<unknown>')}")
            continue
        document_domain = str(condition.get("document_domain", "")).strip()
        if document_domain not in VALID_DOCUMENT_DOMAINS:
            errors.append(f"invalid ax domain reference: {document_domain or '<blank>'}")
        rule = entry.get("rule", {})
        if not isinstance(rule, dict):
            errors.append(f"budget_policy rule must be mapping: {entry.get('id', '<unknown>')}")
            continue
        for field in ("formal_count_budget", "pending_count_budget", "family_repeat_budget", "low_value_signal_budget"):
            if not isinstance(rule.get(field), int):
                errors.append(f"budget_policy missing numeric field {field}: {entry.get('id', '<unknown>')}")
    return errors


def _validate_domain_policy(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for entry in payload.get("entries", []):
        errors.extend(_entry_errors("domain_policy", entry))
        condition = entry.get("condition", {})
        if not isinstance(condition, dict):
            errors.append(f"domain_policy condition must be mapping: {entry.get('id', '<unknown>')}")
            continue
        document_domain = str(condition.get("document_domain", "")).strip()
        if document_domain not in VALID_DOCUMENT_DOMAINS:
            errors.append(f"invalid ax domain reference: {document_domain or '<blank>'}")
        rule = entry.get("rule", {})
        if not isinstance(rule, dict):
            errors.append(f"domain_policy rule must be mapping: {entry.get('id', '<unknown>')}")
            continue
        if not str(rule.get("budget_policy_id", "")).strip():
            errors.append(f"domain_policy missing budget_policy_id: {entry.get('id', '<unknown>')}")
    return errors


def _validate_family_governance(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for entry in payload.get("entries", []):
        errors.extend(_entry_errors("family_governance", entry))
        scope = entry.get("scope", {})
        condition = entry.get("condition", {})
        family_key = str(scope.get("family_key", "")).strip() if isinstance(scope, dict) else ""
        if family_key not in KNOWN_AX_FAMILY_REFERENCES:
            errors.append(f"invalid ax family reference: {family_key or '<blank>'}")
        if not isinstance(condition, dict):
            errors.append(f"family_governance condition must be mapping: {entry.get('id', '<unknown>')}")
            continue
        match_family_keys = [str(item).strip() for item in condition.get("match_family_keys", []) if str(item).strip()]
        for item in match_family_keys:
            if item not in KNOWN_AX_FAMILY_REFERENCES:
                errors.append(f"invalid ax family reference: {item}")
        rule = entry.get("rule", {})
        if not isinstance(rule, dict):
            errors.append(f"family_governance rule must be mapping: {entry.get('id', '<unknown>')}")
            continue
        if not str(rule.get("canonical_title", "")).strip():
            errors.append(f"family_governance missing canonical_title: {entry.get('id', '<unknown>')}")
    return errors


def _validate_duplicate_ids(payloads: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for payload in payloads.values():
        for entry in payload.get("entries", []):
            entry_id = str(entry.get("id", "")).strip()
            if not entry_id:
                continue
            if entry_id in seen:
                errors.append(f"duplicate ax governance id: {entry_id}")
            seen.add(entry_id)
    return errors


def _validate_runtime_references(payloads: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    budget_status = {
        str(entry.get("id", "")).strip(): str(entry.get("status", "")).strip()
        for entry in payloads.get("budget_policy", {}).get("entries", [])
    }
    for entry in payloads.get("domain_policy", {}).get("entries", []):
        if str(entry.get("status", "")).strip() != "active":
            continue
        rule = entry.get("rule", {})
        budget_policy_id = str(rule.get("budget_policy_id", "")).strip() if isinstance(rule, dict) else ""
        if not budget_policy_id:
            continue
        if budget_policy_id not in budget_status:
            errors.append(f"invalid ax budget policy reference: {budget_policy_id}")
            continue
        if budget_status[budget_policy_id] != "active":
            errors.append(f"deprecated ax budget policy referenced by active domain policy: {budget_policy_id}")
    return errors


def _validate_no_dual_source_constants() -> list[str]:
    errors: list[str] = []
    for module_name, names in LEGACY_CODE_CONSTANTS.items():
        module = __import__(module_name, fromlist=["_unused"])
        for name in names:
            if hasattr(module, name):
                errors.append(f"legacy ax governance constant still exists in code: {module_name}.{name}")
    return errors


def validate_ax_governance_sources(payloads: dict[str, dict[str, Any]] | None = None) -> list[str]:
    payloads = payloads or load_ax_governance_sources()
    errors: list[str] = []
    errors.extend(_validate_duplicate_ids(payloads))
    errors.extend(_validate_stable_pending(payloads.get("stable_pending", {})))
    errors.extend(_validate_domain_policy(payloads.get("domain_policy", {})))
    errors.extend(_validate_budget_policy(payloads.get("budget_policy", {})))
    errors.extend(_validate_family_governance(payloads.get("family_governance", {})))
    errors.extend(_validate_runtime_references(payloads))
    errors.extend(_validate_no_dual_source_constants())
    return errors


@lru_cache(maxsize=1)
def load_ax_governance_index() -> AxGovernanceIndex:
    payloads = load_ax_governance_sources()
    errors = validate_ax_governance_sources(payloads)
    if errors:
        raise ValueError("invalid ax governance sources: " + "; ".join(errors))

    stable_pending_families: dict[str, StablePendingFamilyConfig] = {}
    stable_pending_patterns: list[StablePendingPatternConfig] = []
    for entry in payloads["stable_pending"].get("entries", []):
        if str(entry.get("status", "")).strip() != "active":
            continue
        condition = entry.get("condition", {})
        family_key = str(condition.get("family_key", "")).strip() if isinstance(condition, dict) else ""
        rule = entry.get("rule", {})
        gate_rule = (
            str(rule.get("user_visible_gate_rule", "")).strip()
            if isinstance(rule, dict)
            else str(rule).strip()
        ) or "pending_material_issue_allowed"
        if family_key:
            stable_pending_families[family_key] = StablePendingFamilyConfig(
                config_id=str(entry["id"]),
                family_key=family_key,
                reason=str(entry["reason"]),
                gate_rule=gate_rule,
            )
            continue
        stable_pending_patterns.append(
            StablePendingPatternConfig(
                config_id=str(entry["id"]),
                pattern=str(entry.get("pattern", "")),
                reason=str(entry["reason"]),
                gate_rule=gate_rule,
            )
        )

    domain_policies: dict[str, DomainResultPolicy] = {}
    for entry in payloads["domain_policy"].get("entries", []):
        if str(entry.get("status", "")).strip() != "active":
            continue
        condition = entry.get("condition", {})
        rule = entry.get("rule", {})
        document_domain = str(condition.get("document_domain", "")).strip()
        domain_policies[document_domain] = DomainResultPolicy(
            policy_id=str(entry["id"]),
            document_domain=document_domain,
            formal_output_strategy=str(rule.get("formal_output_strategy", "")),
            pending_output_strategy=str(rule.get("pending_output_strategy", "")),
            family_repeat_tolerance=int(rule.get("family_repeat_tolerance", 1)),
            weak_signal_threshold=str(rule.get("weak_signal_threshold", "")),
            internal_signal_visibility=str(rule.get("internal_signal_visibility", "")),
            budget_policy_id=str(rule.get("budget_policy_id", "")),
            reason=str(entry["reason"]),
            source=str(entry["source"]),
            version=int(entry["version"]),
            owner=str(entry["owner"]),
            last_updated_at=str(entry["last_updated_at"]),
        )

    budget_policies: dict[str, BudgetPolicy] = {}
    for entry in payloads["budget_policy"].get("entries", []):
        if str(entry.get("status", "")).strip() != "active":
            continue
        condition = entry.get("condition", {})
        rule = entry.get("rule", {})
        budget_policies[str(entry["id"])] = BudgetPolicy(
            policy_id=str(entry["id"]),
            document_domain=str(condition.get("document_domain", "")),
            formal_count_budget=int(rule.get("formal_count_budget", 0)),
            pending_count_budget=int(rule.get("pending_count_budget", 0)),
            family_repeat_budget=int(rule.get("family_repeat_budget", 0)),
            low_value_signal_budget=int(rule.get("low_value_signal_budget", 0)),
            priority_title_patterns=tuple(str(item) for item in rule.get("priority_title_patterns", []) if str(item).strip()),
            low_value_title_patterns=tuple(str(item) for item in rule.get("low_value_title_patterns", []) if str(item).strip()),
            reason=str(entry["reason"]),
            source=str(entry["source"]),
            version=int(entry["version"]),
            owner=str(entry["owner"]),
            last_updated_at=str(entry["last_updated_at"]),
        )

    family_governance: dict[str, FamilyGovernanceConfig] = {}
    for entry in payloads["family_governance"].get("entries", []):
        if str(entry.get("status", "")).strip() != "active":
            continue
        scope = entry.get("scope", {})
        condition = entry.get("condition", {})
        rule = entry.get("rule", {})
        family_key = str(scope.get("family_key", "")).strip()
        family_governance[family_key] = FamilyGovernanceConfig(
            config_id=str(entry["id"]),
            family_key=family_key,
            canonical_title=str(rule.get("canonical_title", "")),
            match_family_keys=tuple(str(item) for item in condition.get("match_family_keys", []) if str(item).strip()),
            match_title_patterns=tuple(str(item) for item in condition.get("match_title_patterns", []) if str(item).strip()),
            require_any_title_patterns=tuple(str(item) for item in condition.get("require_any_title_patterns", []) if str(item).strip()),
            preferred_topics=tuple(str(item) for item in rule.get("preferred_topics", []) if str(item).strip()),
            primary_title_patterns=tuple(str(item) for item in rule.get("primary_title_patterns", []) if str(item).strip()),
            internal_title_patterns=tuple(str(item) for item in rule.get("internal_title_patterns", []) if str(item).strip()),
            merge_reason=str(rule.get("merge_reason", "")),
            primary_selection_reason=str(rule.get("primary_selection_reason", "")),
            supporting_visible_problem_limit=int(rule.get("supporting_visible_problem_limit", 0)),
            source=str(entry["source"]),
            version=int(entry["version"]),
            owner=str(entry["owner"]),
            last_updated_at=str(entry["last_updated_at"]),
        )

    return AxGovernanceIndex(
        stable_pending_families=stable_pending_families,
        stable_pending_patterns=tuple(stable_pending_patterns),
        domain_policies=domain_policies,
        budget_policies=budget_policies,
        family_governance=family_governance,
    )
