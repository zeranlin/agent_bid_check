from __future__ import annotations

import sys
from pathlib import Path

import yaml

import scripts.validate_rule_registry as validate_rule_registry
from app.governance import rule_registry


ROOT = Path(__file__).resolve().parents[1]
AX_STABLE_PENDING_PATH = ROOT / "rules" / "governance" / "ax_stable_pending.yaml"
AX_DOMAIN_POLICY_PATH = ROOT / "rules" / "governance" / "ax_domain_policy.yaml"
AX_BUDGET_POLICY_PATH = ROOT / "rules" / "governance" / "ax_budget_policy.yaml"
AX_FAMILY_GOVERNANCE_PATH = ROOT / "rules" / "governance" / "ax_family_governance.yaml"


def test_ax_governance_source_files_exist() -> None:
    assert AX_STABLE_PENDING_PATH.exists()
    assert AX_DOMAIN_POLICY_PATH.exists()
    assert AX_BUDGET_POLICY_PATH.exists()
    assert AX_FAMILY_GOVERNANCE_PATH.exists()


def test_ax_governance_source_files_have_minimum_metadata() -> None:
    for path in (
        AX_STABLE_PENDING_PATH,
        AX_DOMAIN_POLICY_PATH,
        AX_BUDGET_POLICY_PATH,
        AX_FAMILY_GOVERNANCE_PATH,
    ):
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert payload["version"]
        assert payload["entries"]
        first = payload["entries"][0]
        assert first["id"]
        assert first["status"] in {"active", "deprecated", "draft"}
        assert first["scope"]
        assert first["reason"]
        assert first["source"]
        assert first["version"]
        assert first["owner"]
        assert first["last_updated_at"]


def test_ax_governance_validator_catches_duplicate_ids_and_invalid_references() -> None:
    payloads = {
        "stable_pending": {
            "version": 1,
            "entries": [
                {
                    "id": "ax-sp-001",
                    "status": "active",
                    "scope": {"kind": "family"},
                    "condition": {"family_key": "brand_bias"},
                    "rule": "pending_material_issue_allowed",
                    "reason": "demo",
                    "source": "test",
                    "version": 1,
                    "owner": "T",
                    "last_updated_at": "2026-04-12",
                },
                {
                    "id": "ax-sp-001",
                    "status": "active",
                    "scope": {"kind": "title_pattern"},
                    "pattern": "品牌",
                    "rule": "pending_material_issue_allowed",
                    "reason": "duplicate",
                    "source": "test",
                    "version": 1,
                    "owner": "T",
                    "last_updated_at": "2026-04-12",
                },
            ],
        },
        "domain_policy": {
            "version": 1,
            "entries": [
                {
                    "id": "ax-domain-001",
                    "status": "active",
                    "scope": {"document_domain": "invalid_domain"},
                    "condition": {"document_domain": "invalid_domain"},
                    "rule": {"budget_policy_id": "ax-budget-missing"},
                    "reason": "bad ref",
                    "source": "test",
                    "version": 1,
                    "owner": "T",
                    "last_updated_at": "2026-04-12",
                }
            ],
        },
        "budget_policy": {
            "version": 1,
            "entries": [
                {
                    "id": "ax-budget-001",
                    "status": "deprecated",
                    "scope": {"document_domain": "goods_procurement"},
                    "condition": {"document_domain": "goods_procurement"},
                    "rule": {"pending_count_budget": 4},
                    "reason": "deprecated",
                    "source": "test",
                    "version": 1,
                    "owner": "T",
                    "last_updated_at": "2026-04-12",
                }
            ],
        },
        "family_governance": {
            "version": 1,
            "entries": [
                {
                    "id": "ax-family-001",
                    "status": "active",
                    "scope": {"family_key": "nonexistent_family"},
                    "condition": {"match_family_keys": ["nonexistent_family"]},
                    "rule": {"canonical_title": "demo"},
                    "reason": "bad family",
                    "source": "test",
                    "version": 1,
                    "owner": "T",
                    "last_updated_at": "2026-04-12",
                }
            ],
        },
    }

    errors = rule_registry.validate_ax_governance_sources(payloads)

    assert any("duplicate ax governance id: ax-sp-001" in item for item in errors)
    assert any("invalid ax domain reference: invalid_domain" in item for item in errors)
    assert any("invalid ax budget policy reference: ax-budget-missing" in item for item in errors)
    assert any("invalid ax family reference: nonexistent_family" in item for item in errors)


def test_ax_governance_validator_rejects_deprecated_runtime_reference() -> None:
    payloads = {
        "stable_pending": {"version": 1, "entries": []},
        "domain_policy": {
            "version": 1,
            "entries": [
                {
                    "id": "ax-domain-goods",
                    "status": "active",
                    "scope": {"document_domain": "goods_procurement"},
                    "condition": {"document_domain": "goods_procurement"},
                    "rule": {"budget_policy_id": "ax-budget-goods"},
                    "reason": "goods",
                    "source": "test",
                    "version": 1,
                    "owner": "T",
                    "last_updated_at": "2026-04-12",
                }
            ],
        },
        "budget_policy": {
            "version": 1,
            "entries": [
                {
                    "id": "ax-budget-goods",
                    "status": "deprecated",
                    "scope": {"document_domain": "goods_procurement"},
                    "condition": {"document_domain": "goods_procurement"},
                    "rule": {"pending_count_budget": 4},
                    "reason": "deprecated",
                    "source": "test",
                    "version": 1,
                    "owner": "T",
                    "last_updated_at": "2026-04-12",
                }
            ],
        },
        "family_governance": {"version": 1, "entries": []},
    }

    errors = rule_registry.validate_ax_governance_sources(payloads)

    assert any("deprecated ax budget policy referenced by active domain policy: ax-budget-goods" in item for item in errors)


def test_validate_rule_registry_cli_covers_ax_governance_sources(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["validate_rule_registry.py"])
    exit_code = validate_rule_registry.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"OK {ROOT / 'rules' / 'governance' / 'ax_stable_pending.yaml'}" in captured.out
    assert f"OK {ROOT / 'rules' / 'governance' / 'ax_domain_policy.yaml'}" in captured.out
    assert f"OK {ROOT / 'rules' / 'governance' / 'ax_budget_policy.yaml'}" in captured.out
    assert f"OK {ROOT / 'rules' / 'governance' / 'ax_family_governance.yaml'}" in captured.out
