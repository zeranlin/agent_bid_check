from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_ROOT = ROOT / "rules" / "candidates"
IMPORT_PATH = CANDIDATE_ROOT / "imports" / "candidate_rules_2026-04-07_seed.yaml"
LEDGER_PATH = CANDIDATE_ROOT / "mappings" / "candidate_rule_ledger_2026-04-07_seed.yaml"
ALLOWED_DECISIONS = {"formal_rule", "conditional_rule", "capability_item", "drop"}
REQUIRED_LEDGER_FIELDS = {
    "candidate_id",
    "source_name",
    "source_rule_text",
    "source_category",
    "decision",
    "decision_reason",
    "target_rule_id",
    "target_layer",
    "profile_dependency",
    "negative_conditions",
    "samples_status",
    "tests_status",
    "task_id",
    "status",
    "snapshot_id",
}


def test_candidate_rule_governance_directories_exist() -> None:
    expected_paths = [
        CANDIDATE_ROOT / "README.md",
        CANDIDATE_ROOT / "sources" / "README.md",
        CANDIDATE_ROOT / "imports" / "README.md",
        CANDIDATE_ROOT / "mappings" / "README.md",
        CANDIDATE_ROOT / "snapshots" / "README.md",
    ]
    for path in expected_paths:
        assert path.exists(), path

    assert (ROOT / "rules" / "registry").exists()
    assert CANDIDATE_ROOT != ROOT / "rules" / "registry"


def test_candidate_rule_import_template_is_readable() -> None:
    payload = yaml.safe_load(IMPORT_PATH.read_text(encoding="utf-8"))
    assert payload["batch_id"] == "CAND-IMPORT-2026-04-07-001"
    assert payload["source_name"] == "外部审查点样例批次"
    assert payload["candidate_items"]
    first_item = payload["candidate_items"][0]
    assert {"candidate_id", "source_rule_text", "source_category"} <= set(first_item)


def test_candidate_rule_ledger_fields_are_complete() -> None:
    payload = yaml.safe_load(LEDGER_PATH.read_text(encoding="utf-8"))
    assert payload["ledger_version"] == 1
    assert payload["entries"]
    for entry in payload["entries"]:
        assert REQUIRED_LEDGER_FIELDS <= set(entry), entry


def test_candidate_rule_ledger_decisions_are_valid_and_seeded() -> None:
    payload = yaml.safe_load(LEDGER_PATH.read_text(encoding="utf-8"))
    decisions = {entry["decision"] for entry in payload["entries"]}
    assert decisions <= ALLOWED_DECISIONS
    assert decisions == ALLOWED_DECISIONS
    assert set(payload["decisions"]) == ALLOWED_DECISIONS
