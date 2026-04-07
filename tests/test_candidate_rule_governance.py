from __future__ import annotations

import sys
from pathlib import Path

import yaml

import scripts.validate_rule_registry as validate_rule_registry


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_ROOT = ROOT / "rules" / "candidates"
IMPORT_PATH = CANDIDATE_ROOT / "imports" / "candidate_rules_2026-04-07_seed.yaml"
LEDGER_PATH = CANDIDATE_ROOT / "mappings" / "candidate_rule_ledger_2026-04-07_seed.yaml"
SNAPSHOT_PATH = CANDIDATE_ROOT / "snapshots" / "SNAP-2026-04-07-triage-001.md"
MIGRATION_SNAPSHOT_PATH = CANDIDATE_ROOT / "snapshots" / "SNAP-2026-04-07-migrate-001.md"
FIRST_BATCH_PATH = CANDIDATE_ROOT / "mappings" / "first_batch_candidate_migration_2026-04-07.yaml"
ROLLBACK_GUIDE_PATH = ROOT / "docs" / "governance" / "candidate-rule-snapshot-and-rollback-guide.md"
FIRST_BATCH_GUIDE_PATH = ROOT / "docs" / "governance" / "candidate-rule-first-batch-migration-guide.md"
REAL_SOURCE_INDEX_PATH = CANDIDATE_ROOT / "sources" / "external-review-points-real-2026-04-07.md"
REAL_IMPORT_PATH = CANDIDATE_ROOT / "imports" / "candidate_rules_2026-04-07_real_batch_001.yaml"
REAL_LEDGER_PATH = CANDIDATE_ROOT / "mappings" / "candidate_rule_ledger_2026-04-07_real_batch_001.yaml"
REAL_SUMMARY_PATH = CANDIDATE_ROOT / "mappings" / "candidate_rule_triage_summary_2026-04-07_real_batch_001.yaml"
REAL_SNAPSHOT_PATH = CANDIDATE_ROOT / "snapshots" / "SNAP-2026-04-07-triage-002.md"
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
    assert {item["candidate_id"] for item in payload["candidate_items"]} >= {"CR-001", "CR-005", "CR-006", "CR-007"}


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


def test_candidate_snapshot_file_exists_and_has_minimum_sections() -> None:
    content = SNAPSHOT_PATH.read_text(encoding="utf-8")
    assert "SNAP-2026-04-07-triage-001" in content
    assert "输入来源" in content
    assert "分流范围" in content
    assert "任务单范围" in content
    assert "状态摘要" in content
    assert "回滚说明" in content


def test_candidate_validator_supports_candidate_root_mode(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["validate_rule_registry.py", "--candidate-root", str(CANDIDATE_ROOT)],
    )
    exit_code = validate_rule_registry.main()
    captured = capsys.readouterr()
    assert exit_code == 0
    assert f"OK {CANDIDATE_ROOT}" in captured.out


def test_candidate_rollback_guide_has_minimum_recovery_scenarios() -> None:
    content = ROLLBACK_GUIDE_PATH.read_text(encoding="utf-8")
    assert "导入批次" in content
    assert "分流批次" in content
    assert "迁移批次" in content
    assert "候选池分流判断错误" in content
    assert "某批纳管引入误报" in content
    assert "已入正式规则但后续发现问题" in content
    assert "rules/candidates/imports/" in content
    assert "rules/candidates/mappings/" in content
    assert "rules/candidates/snapshots/" in content
    assert "rules/registry/" in content


def test_first_batch_candidate_migration_list_exists_and_is_readable() -> None:
    payload = yaml.safe_load(FIRST_BATCH_PATH.read_text(encoding="utf-8"))
    assert payload["batch_id"] == "CAND-MIGRATE-2026-04-07-001"
    assert payload["snapshot_id"] == "SNAP-2026-04-07-migrate-001"
    assert payload["first_batch_recommendations"]["formal_rule"]
    assert FIRST_BATCH_GUIDE_PATH.exists()
    assert MIGRATION_SNAPSHOT_PATH.exists()


def test_first_batch_candidate_migration_mapping_is_complete() -> None:
    payload = yaml.safe_load(FIRST_BATCH_PATH.read_text(encoding="utf-8"))
    formal_items = payload["first_batch_recommendations"]["formal_rule"]
    for item in formal_items:
        assert item["mapping_task_id"]
        assert item["samples_status"] in {"seeded", "ready"}
        assert item["tests_status"] in {"seeded", "ready"}
        assert item["absorbed_by_rule_id"] or item["proposed_rule_id"]


def test_absorbed_candidates_are_marked_and_not_relisted_as_new_rules() -> None:
    payload = yaml.safe_load(FIRST_BATCH_PATH.read_text(encoding="utf-8"))
    formal_items = payload["first_batch_recommendations"]["formal_rule"]
    absorbed = {item["candidate_id"]: item["absorbed_by_rule_id"] for item in formal_items}
    assert absorbed["CR-001"] == "R-003"
    assert absorbed["CR-005"] == "R-004"
    assert absorbed["CR-006"] == "R-008"
    assert absorbed["CR-007"] == "R-005"
    assert all(not item["proposed_rule_id"] for item in formal_items)


def test_real_candidate_import_file_is_readable() -> None:
    payload = yaml.safe_load(REAL_IMPORT_PATH.read_text(encoding="utf-8"))
    assert payload["batch_id"] == "CAND-IMPORT-2026-04-07-REAL-001"
    assert payload["source_name"] == "合规性审查点反馈表分层映射清单"
    assert payload["candidate_items"]
    assert len(payload["candidate_items"]) >= 150
    assert REAL_SOURCE_INDEX_PATH.exists()


def test_real_candidate_ledger_fields_and_decisions_are_complete() -> None:
    payload = yaml.safe_load(REAL_LEDGER_PATH.read_text(encoding="utf-8"))
    entries = payload["entries"]
    assert len(entries) >= 150
    for entry in entries:
        assert REQUIRED_LEDGER_FIELDS <= set(entry), entry
        assert entry["decision"] in ALLOWED_DECISIONS


def test_real_candidate_absorbed_markers_exist() -> None:
    payload = yaml.safe_load(REAL_LEDGER_PATH.read_text(encoding="utf-8"))
    absorbed = {
        entry["source_rule_text"]: entry.get("target_rule_id", "")
        for entry in payload["entries"]
        if entry.get("status") == "absorbed" or "已被现有规则吸收" in str(entry.get("decision_reason", ""))
    }
    assert absorbed["不得将“项目验收方案”作为评审因素，"] == "R-003"
    assert absorbed["不得将“付款方式”作为评审因素。"] == "R-004"
    assert absorbed["不得要求提供赠品、回扣或者与采购无关的其他商品、服务"] == "R-005"
    assert absorbed["含有GB（不含GB/T）或国家强制性标准的描述中需含有★号"] == "R-002"


def test_real_candidate_triage_summary_matches_ledger_counts() -> None:
    ledger = yaml.safe_load(REAL_LEDGER_PATH.read_text(encoding="utf-8"))
    summary = yaml.safe_load(REAL_SUMMARY_PATH.read_text(encoding="utf-8"))
    counts: dict[str, int] = {key: 0 for key in ALLOWED_DECISIONS}
    for entry in ledger["entries"]:
        counts[entry["decision"]] += 1
    assert summary["counts"] == counts
    assert summary["total_candidates"] == len(ledger["entries"])
    assert summary["first_priority_candidates"]
    assert summary["capability_backlog"]
    assert REAL_SNAPSHOT_PATH.exists()
