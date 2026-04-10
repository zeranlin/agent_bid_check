from __future__ import annotations

from pathlib import Path

from app.governance.rule_registry import (
    RULE_STATUSES,
    can_transition_rule_status,
    collect_formal_admission_signals,
    validate_formal_admission_sources,
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


def test_formal_rule_validator_requires_formal_admission_fields() -> None:
    errors = validate_rule_dict(
        {
            "rule_id": "R-BAD",
            "rule_name": "缺治理字段规则",
            "rule_version": 1,
            "status": "active",
            "owner": {"reviewer": "M", "implementer": "T"},
            "source": {"origin_type": "demo", "origin_desc": "demo", "created_date": "2026-04-10", "last_updated_date": "2026-04-10"},
            "classification": {"category": "demo", "rule_type": "risk_detection", "target_level": "formal", "severity": "high"},
            "trigger_conditions": {"all_of": ["a"]},
            "exclude_conditions": {"any_of": ["b"]},
            "downgrade_conditions": {"any_of": ["c"]},
            "output": {"formal_title": "示例正式风险"},
            "samples": {"positive": ["a"]},
            "tests": {"unit": ["b"]},
            "task_refs": {"remediation_tasks": ["c"]},
            "activation": {"approved_by": "M", "approved_date": "2026-04-10", "effective_scope": ["mature"]},
            "history": [{"version": 1, "date": "2026-04-10", "change": "init", "author": "T"}],
        }
    )

    assert "missing formal_admission block for formal rule" in errors


def test_governance_formal_entry_requires_required_fields() -> None:
    errors = validate_rule_dict(
        {
            "entry_type": "governance_formal",
            "rule_id": "GOV-sample_gate",
            "status": "active",
            "canonical_title": "样品要求过细且评审规则失衡，存在样品门槛风险",
            "family_key": "sample_gate",
            "allow_formal": True,
            "requires_hard_evidence": True,
        }
    )

    assert "missing governance_formal.source" in errors
    assert "missing governance_formal.rationale" in errors
    assert "missing governance_formal.migration_status" in errors


def test_formal_admission_source_validator_detects_registry_and_transition_conflict() -> None:
    registry_rules = [
        {
            "rule_id": "R-001",
            "status": "active",
            "classification": {"target_level": "formal"},
            "output": {"formal_title": "标题A"},
            "formal_admission": {
                "family_key": "family-a",
                "canonical_title": "标题A",
                "allow_formal": True,
                "requires_hard_evidence": True,
            },
        }
    ]
    supplemental_payload = {
        "supplemental_families": [
            {
                "governance_rule_id": "GOV-conflict",
                "family_key": "family-a",
                "canonical_title": "标题A-冲突",
                "status": "active",
                "allow_formal": True,
                "requires_hard_evidence": True,
            }
        ]
    }

    errors = validate_formal_admission_sources(registry_rules, supplemental_payload)

    assert any("supplemental family conflicts with registry family_key: family-a" in item for item in errors)


def test_formal_admission_source_validator_requires_retained_supplemental_exit_plan() -> None:
    supplemental_payload = {
        "supplemental_families": [
            {
                "governance_rule_id": "GOV-retained",
                "family_key": "retained-family",
                "canonical_title": "保留项",
                "status": "active",
                "allow_formal": True,
                "requires_hard_evidence": True,
            }
        ]
    }

    errors = validate_formal_admission_sources([], supplemental_payload)

    assert any("supplemental runtime families are closed after Q7: GOV-retained" in item for item in errors)


def test_formal_admission_signal_marks_long_lived_supplemental_dependency() -> None:
    supplemental_payload = {
        "supplemental_families": [
            {
                "governance_rule_id": "GOV-retained",
                "family_key": "retained-family",
                "canonical_title": "保留项",
                "status": "active",
                "allow_formal": True,
                "requires_hard_evidence": True,
                "retention_reason": "暂留",
                "missing_materials": ["缺跨文件 replay"],
                "exit_conditions": ["补齐 replay"],
                "governance_signals": {
                    "replay_bound_runs": ["data/results/v2/demo-run"],
                    "whitelist_bound": True,
                },
            }
        ]
    }

    signals = collect_formal_admission_signals([], supplemental_payload)

    assert "supplemental family remains long-lived runtime dependency: GOV-retained" in signals


def test_formal_admission_source_validator_fails_when_whitelist_bound_item_still_uses_supplemental() -> None:
    supplemental_payload = {
        "supplemental_families": [
            {
                "governance_rule_id": "GOV-whitelist-bound",
                "family_key": "software_copyright_competition",
                "canonical_title": "评分标准中“信息化软件服务能力”要求著作权人为投标人，可能限制竞争",
                "status": "active",
                "allow_formal": True,
                "requires_hard_evidence": True,
                "terminal_decision": "retire_from_runtime_formal_source",
                "governance_signals": {"whitelist_bound": True},
            }
        ]
    }

    errors = validate_formal_admission_sources([], supplemental_payload)

    assert any("supplemental runtime families are closed after Q7: GOV-whitelist-bound" in item for item in errors)


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
