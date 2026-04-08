from __future__ import annotations

import sys
from pathlib import Path

import yaml
from app.common.file_extract import extract_document_text

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
G9_TASK_PATH = ROOT / "docs" / "tasks" / "Task-G9-real-candidate-triage.md"
G10_TASK_PATH = ROOT / "docs" / "tasks" / "Task-G10-first-priority-formalization.md"
G10_GUIDE_PATH = ROOT / "docs" / "governance" / "candidate-rule-first-priority-formalization-guide.md"
G10_PACKAGE_PATH = CANDIDATE_ROOT / "mappings" / "first_priority_formalization_package_2026-04-07.yaml"
RC003_MODEL_PATH = CANDIDATE_ROOT / "mappings" / "rc003_industry_evidence_model_2026-04-08.yaml"
RC003_SAMPLES_PATH = CANDIDATE_ROOT / "imports" / "rc003_industry_samples_2026-04-08.yaml"
RC003_REPLAY_PATH = CANDIDATE_ROOT / "mappings" / "rc003_industry_replay_summary_2026-04-08.yaml"
RC003_GUIDE_PATH = ROOT / "docs" / "governance" / "rc003-industry-evidence-model-2026-04-08.md"
RC004_QUAL_MODEL_PATH = CANDIDATE_ROOT / "mappings" / "rc004_qualification_side_model_2026-04-08.yaml"
RC004_QUAL_SAMPLES_PATH = CANDIDATE_ROOT / "imports" / "rc004_qualification_side_samples_2026-04-08.yaml"
RC004_QUAL_SUMMARY_PATH = CANDIDATE_ROOT / "mappings" / "rc004_qualification_side_summary_2026-04-08.yaml"
RC004_QUAL_GUIDE_PATH = ROOT / "docs" / "governance" / "rc004-qualification-side-model-2026-04-08.md"
RC013_MODEL_PATH = CANDIDATE_ROOT / "mappings" / "rc013_safety_standardization_model_2026-04-08.yaml"
RC013_SAMPLES_PATH = CANDIDATE_ROOT / "imports" / "rc013_safety_standardization_samples_2026-04-08.yaml"
RC013_REPLAY_PATH = CANDIDATE_ROOT / "mappings" / "rc013_safety_standardization_replay_summary_2026-04-08.yaml"
RC013_GUIDE_PATH = ROOT / "docs" / "governance" / "rc013-safety-standardization-model-2026-04-08.md"
RC014_MODEL_PATH = CANDIDATE_ROOT / "mappings" / "rc014_hidden_tenure_model_2026-04-08.yaml"
RC014_SAMPLES_PATH = CANDIDATE_ROOT / "imports" / "rc014_hidden_tenure_samples_2026-04-08.yaml"
RC014_PACKAGE_PATH = CANDIDATE_ROOT / "mappings" / "rc014_hidden_tenure_strengthening_package_2026-04-08.yaml"
RC014_GUIDE_PATH = ROOT / "docs" / "governance" / "rc014-hidden-tenure-model-2026-04-08.md"
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
RC003_REQUIRED_FIELDS = [
    "procurement_object",
    "procurement_scene",
    "qualification_name",
    "qualification_usage",
    "demand_relevance",
    "industry_match_level",
    "evidence_sufficiency",
    "decision_layer",
]
RC003_ALLOWED_RELEVANCE = {"与履约直接相关", "间接相关", "相关性不足"}
RC003_ALLOWED_MATCH = {"行业匹配", "跨行业疑似错配", "明显错配"}
RC003_ALLOWED_SUFFICIENCY = {"证据充分", "证据一般", "证据不足"}
RC003_ALLOWED_LAYER = {"正式风险", "待补证", "排除"}
RC004_QUAL_REQUIRED_FIELDS = [
    "qualification_context",
    "certificate_name",
    "certificate_holder",
    "gate_usage",
    "necessity_level",
    "qualification_side_match",
    "evidence_sufficiency",
    "decision_layer",
]
RC004_ALLOWED_CONTEXT = {"资格条件", "合格供应商条件", "资格审查门槛"}
RC004_ALLOWED_HOLDER = {"企业人员", "项目负责人", "现场作业人员"}
RC004_ALLOWED_NECESSITY = {"法定/常见必要", "场景化待确认", "超出履约必要"}
RC004_ALLOWED_MATCH = {"合理", "可疑", "不当"}
RC013_REQUIRED_FIELDS = [
    "procurement_object",
    "procurement_scene",
    "requirement_name",
    "requirement_usage",
    "safety_requirement_kind",
    "scene_relevance",
    "evidence_sufficiency",
    "decision_layer",
]
RC013_ALLOWED_KIND = {"安全生产标准化证书", "安全生产许可证", "法定安全资格"}
RC013_ALLOWED_RELEVANCE = {"相关性不足", "场景相关待确认", "与施工实施直接相关"}
RC014_REQUIRED_FIELDS = [
    "expression_pattern",
    "certificate_context",
    "certificate_name",
    "time_constraint_expression",
    "implicit_business_age_signal",
    "score_or_bias_linkage",
    "evidence_sufficiency",
    "decision_layer",
]
RC014_ALLOWED_PATTERN = {
    "取得证书满X年",
    "连续持有证书满X年",
    "发证日期早于某时间点",
    "持证延续历史体现经营稳定性",
    "正常有效期校验",
}
RC014_ALLOWED_CONTEXT = {"评分项", "倾向性证书条件", "合规有效性校验"}
RC014_ALLOWED_SIGNAL = {"明确", "可疑", "无"}
RC014_ALLOWED_LINKAGE = {"评分直接挂钩", "倾向性条件挂钩", "仅合规校验"}


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


def test_first_priority_formalization_package_exists_and_is_readable() -> None:
    payload = yaml.safe_load(G10_PACKAGE_PATH.read_text(encoding="utf-8"))
    assert payload["task_id"] == "Task-G10"
    assert payload["selection_scope"]["max_items"] <= 6
    assert payload["formalization_candidates"]
    assert G10_GUIDE_PATH.exists()
    assert G10_TASK_PATH.exists()
    assert G9_TASK_PATH.exists()


def test_first_priority_formalization_candidates_have_clear_ownership() -> None:
    payload = yaml.safe_load(G10_PACKAGE_PATH.read_text(encoding="utf-8"))
    candidates = payload["formalization_candidates"]
    assert len(candidates) <= payload["selection_scope"]["max_items"]
    for item in candidates:
        assert item["candidate_id"]
        assert item["source_rule_text"]
        assert item["ownership"]["route"] in {"new_rule", "strengthen_existing_rule"}
        if item["ownership"]["route"] == "new_rule":
            assert item["ownership"]["proposed_rule_id"].startswith("R-0")
            assert item["new_rule_draft"]["rule_name"]
            assert item["new_rule_draft"]["rule_goal"]
            assert item["new_rule_draft"]["trigger_conditions"]
            assert item["new_rule_draft"]["exclude_conditions"]
            assert item["new_rule_draft"]["formal_title"]
            assert item["new_rule_draft"]["remediation_advice"]
        else:
            assert item["ownership"]["target_rule_id"].startswith("R-0")
            assert item["strengthen_existing_rule"]["target_rule_id"] == item["ownership"]["target_rule_id"]
            assert item["strengthen_existing_rule"]["strengthen_scope"]


def test_rc003_evidence_model_exists_and_has_required_fields() -> None:
    payload = yaml.safe_load(RC003_MODEL_PATH.read_text(encoding="utf-8"))
    assert payload["candidate_id"] == "RC-003"
    assert payload["required_fields"] == RC003_REQUIRED_FIELDS
    assert RC003_GUIDE_PATH.exists()


def test_rc003_industry_logic_defines_three_decision_layers() -> None:
    payload = yaml.safe_load(RC003_MODEL_PATH.read_text(encoding="utf-8"))
    assert payload["industry_scope"] == ["柴油发电机组", "机电安装", "配套设备采购"]
    assert payload["decision_layers"] == ["正式风险", "待补证", "排除"]
    assert {"formal_risk", "pending_review", "exclude"} <= set(payload["decision_rules"])


def test_rc003_samples_cover_positive_negative_and_boundary_cases() -> None:
    payload = yaml.safe_load(RC003_SAMPLES_PATH.read_text(encoding="utf-8"))
    assert payload["candidate_id"] == "RC-003"
    assert payload["positive_samples"]
    assert payload["negative_samples"]
    assert payload["boundary_samples"]
    for key in ("positive_samples", "negative_samples", "boundary_samples"):
        for item in payload[key]:
            assert set(RC003_REQUIRED_FIELDS) <= set(item), item
            assert item["demand_relevance"] in RC003_ALLOWED_RELEVANCE
            assert item["industry_match_level"] in RC003_ALLOWED_MATCH
            assert item["evidence_sufficiency"] in RC003_ALLOWED_SUFFICIENCY
            assert item["decision_layer"] in RC003_ALLOWED_LAYER


def test_rc003_replay_summary_and_upgrade_recommendation_are_present() -> None:
    payload = yaml.safe_load(RC003_REPLAY_PATH.read_text(encoding="utf-8"))
    assert payload["candidate_id"] == "RC-003"
    assert payload["real_replay"]
    assert payload["industry_replay"]
    assert payload["upgrade_recommendation"]["candidate_id"] == "RC-003"
    assert isinstance(payload["upgrade_recommendation"]["recommend_r013"], bool)
    assert payload["upgrade_recommendation"]["recommendation_reason"]


def test_rc003_replay_summary_counts_match_sample_layers() -> None:
    samples = yaml.safe_load(RC003_SAMPLES_PATH.read_text(encoding="utf-8"))
    replay = yaml.safe_load(RC003_REPLAY_PATH.read_text(encoding="utf-8"))
    expected = {"正式风险": 0, "待补证": 0, "排除": 0}
    for key in ("positive_samples", "negative_samples", "boundary_samples"):
        for item in samples[key]:
            expected[item["decision_layer"]] += 1
    assert replay["industry_replay"]["decision_counts"] == expected


def test_rc003_real_replay_excerpt_matches_current_source_file() -> None:
    replay = yaml.safe_load(RC003_REPLAY_PATH.read_text(encoding="utf-8"))
    target_file = Path(replay["real_replay"]["target_file"])
    text = extract_document_text(target_file)
    assert replay["real_replay"]["observed_qualification"]["evidence_excerpt"] in text
    assert replay["real_replay"]["observed_qualification"]["decision_layer"] == "排除"


def test_rc003_upgrade_recommendation_currently_blocks_r013() -> None:
    replay = yaml.safe_load(RC003_REPLAY_PATH.read_text(encoding="utf-8"))
    assert replay["upgrade_recommendation"]["recommend_r013"] is False
    assert replay["upgrade_recommendation"]["current_blockers"]


def test_first_priority_formalization_avoids_duplicate_construction() -> None:
    payload = yaml.safe_load(G10_PACKAGE_PATH.read_text(encoding="utf-8"))
    absorbed_ids = {item["candidate_id"] for item in payload["already_absorbed_or_skip"]}
    candidate_ids = {item["candidate_id"] for item in payload["formalization_candidates"]}
    assert not (absorbed_ids & candidate_ids)
    assert any(item["ownership"]["route"] == "new_rule" for item in payload["formalization_candidates"])


def test_rc004_qualification_side_model_exists_and_is_scoped_to_gate_only() -> None:
    payload = yaml.safe_load(RC004_QUAL_MODEL_PATH.read_text(encoding="utf-8"))
    assert payload["candidate_id"] == "RC-004"
    assert payload["scope"]["included"] == [
        "特定企业人员证书作为资格条件",
        "特定企业人员证书作为合格供应商条件",
        "特定企业人员证书作为资格审查通过门槛",
    ]
    assert "评分因素侧" in payload["scope"]["excluded"]
    assert payload["required_fields"] == RC004_QUAL_REQUIRED_FIELDS
    assert RC004_QUAL_GUIDE_PATH.exists()


def test_rc004_qualification_side_model_explicitly_separates_from_scoring_side() -> None:
    payload = yaml.safe_load(RC004_QUAL_MODEL_PATH.read_text(encoding="utf-8"))
    boundary = payload["boundary_rules"]
    assert boundary["qualification_side_only"] is True
    assert boundary["scoring_side_owner"]["target_rule_id"] == "R-006"
    assert "资格条件侧不并入 R-006" in boundary["ownership_split_note"]
    assert "R-009" in boundary["not_covered_by_existing_rules"]
    assert "R-012" in boundary["not_covered_by_existing_rules"]


def test_rc004_qualification_side_samples_cover_positive_negative_and_boundary_cases() -> None:
    payload = yaml.safe_load(RC004_QUAL_SAMPLES_PATH.read_text(encoding="utf-8"))
    assert payload["candidate_id"] == "RC-004"
    assert payload["positive_samples"]
    assert payload["negative_samples"]
    assert payload["boundary_samples"]
    for key in ("positive_samples", "negative_samples", "boundary_samples"):
        for item in payload[key]:
            assert set(RC004_QUAL_REQUIRED_FIELDS) <= set(item), item
            assert item["qualification_context"] in RC004_ALLOWED_CONTEXT
            assert item["certificate_holder"] in RC004_ALLOWED_HOLDER
            assert item["necessity_level"] in RC004_ALLOWED_NECESSITY
            assert item["qualification_side_match"] in RC004_ALLOWED_MATCH
            assert item["evidence_sufficiency"] in RC003_ALLOWED_SUFFICIENCY
            assert item["decision_layer"] in RC003_ALLOWED_LAYER


def test_rc004_qualification_side_negative_and_boundary_samples_cover_required_guardrails() -> None:
    payload = yaml.safe_load(RC004_QUAL_SAMPLES_PATH.read_text(encoding="utf-8"))
    negative_rationales = "\n".join(item["rationale"] for item in payload["negative_samples"])
    negative_names = {item["certificate_name"] for item in payload["negative_samples"]}
    boundary_names = {item["certificate_name"] for item in payload["boundary_samples"]}
    assert "法定" in negative_rationales or "常见" in negative_rationales
    assert any("建造师" in name for name in negative_names)
    assert any("特种作业" in name or "电工" in name for name in negative_names)
    assert any("厂商" in name or "原厂" in name or "集成" in name for name in boundary_names)


def test_rc004_qualification_side_summary_has_single_explicit_ownership_conclusion() -> None:
    payload = yaml.safe_load(RC004_QUAL_SUMMARY_PATH.read_text(encoding="utf-8"))
    assert payload["candidate_id"] == "RC-004"
    conclusion = payload["ownership_recommendation"]
    assert conclusion["route"] in {"strengthen_existing_rule", "propose_new_rule"}
    assert conclusion["route"] == "propose_new_rule"
    assert conclusion["proposed_direction"]["why_not_r006"]
    assert conclusion["proposed_direction"]["why_not_r009_to_r012"]
    assert conclusion["proposed_direction"]["future_rule_direction"]
    assert conclusion["three_layer_summary"] == {"正式风险": 2, "待补证": 3, "排除": 3}


def test_rc013_safety_standardization_model_exists_and_has_required_fields() -> None:
    payload = yaml.safe_load(RC013_MODEL_PATH.read_text(encoding="utf-8"))
    assert payload["candidate_id"] == "RC-013"
    assert payload["required_fields"] == RC013_REQUIRED_FIELDS
    assert RC013_GUIDE_PATH.exists()


def test_rc013_boundary_model_separates_standardization_from_other_safety_requirements() -> None:
    payload = yaml.safe_load(RC013_MODEL_PATH.read_text(encoding="utf-8"))
    boundary = payload["boundary_rules"]
    assert boundary["distinguish_objects"] == [
        "安全生产标准化证书",
        "安全生产许可证",
        "与特定施工实施直接相关的法定安全资格",
    ]
    assert boundary["do_not_mix_standardization_with_permit"] is True
    assert payload["scene_scope"] == ["柴油发电机组及机电安装", "设备采购+安装实施混合场景", "纯货物采购场景"]


def test_rc013_samples_cover_positive_negative_and_boundary_cases() -> None:
    payload = yaml.safe_load(RC013_SAMPLES_PATH.read_text(encoding="utf-8"))
    assert payload["candidate_id"] == "RC-013"
    assert payload["positive_samples"]
    assert payload["negative_samples"]
    assert payload["boundary_samples"]
    for key in ("positive_samples", "negative_samples", "boundary_samples"):
        for item in payload[key]:
            assert set(RC013_REQUIRED_FIELDS) <= set(item), item
            assert item["safety_requirement_kind"] in RC013_ALLOWED_KIND
            assert item["scene_relevance"] in RC013_ALLOWED_RELEVANCE
            assert item["evidence_sufficiency"] in RC003_ALLOWED_SUFFICIENCY
            assert item["decision_layer"] in RC003_ALLOWED_LAYER


def test_rc013_samples_cover_required_scene_matrix_and_guardrails() -> None:
    payload = yaml.safe_load(RC013_SAMPLES_PATH.read_text(encoding="utf-8"))
    positive_scenes = {item["procurement_scene"] for item in payload["positive_samples"]}
    negative_names = {item["requirement_name"] for item in payload["negative_samples"]}
    boundary_scenes = {item["procurement_scene"] for item in payload["boundary_samples"]}
    assert any("纯货物采购" in scene for scene in positive_scenes)
    assert any("混合" in scene or "安装" in scene for scene in boundary_scenes)
    assert "安全生产许可证" in negative_names
    assert any("特种作业" in name or "安全员" in name for name in negative_names)


def test_rc013_replay_summary_distinguishes_industry_replay_and_real_file_check() -> None:
    payload = yaml.safe_load(RC013_REPLAY_PATH.read_text(encoding="utf-8"))
    assert payload["candidate_id"] == "RC-013"
    assert payload["industry_replay"]
    assert payload["real_file_check"]
    assert payload["upgrade_recommendation"]["candidate_id"] == "RC-013"
    assert isinstance(payload["upgrade_recommendation"]["recommend_formal_rule"], bool)


def test_rc013_industry_replay_counts_match_sample_layers() -> None:
    samples = yaml.safe_load(RC013_SAMPLES_PATH.read_text(encoding="utf-8"))
    replay = yaml.safe_load(RC013_REPLAY_PATH.read_text(encoding="utf-8"))
    expected = {"正式风险": 0, "待补证": 0, "排除": 0}
    for key in ("positive_samples", "negative_samples", "boundary_samples"):
        for item in samples[key]:
            expected[item["decision_layer"]] += 1
    assert replay["industry_replay"]["decision_counts"] == expected


def test_rc013_real_file_check_is_supporting_only() -> None:
    replay = yaml.safe_load(RC013_REPLAY_PATH.read_text(encoding="utf-8"))
    target_file = Path(replay["real_file_check"]["target_file"])
    text = extract_document_text(target_file)
    for excerpt in replay["real_file_check"]["searched_excerpts"]:
        assert excerpt in text
    assert replay["real_file_check"]["role"] == "辅助核查"


def test_rc014_hidden_tenure_model_exists_and_targets_r006_sub_boundary() -> None:
    payload = yaml.safe_load(RC014_MODEL_PATH.read_text(encoding="utf-8"))
    assert payload["candidate_id"] == "RC-014"
    assert payload["ownership"]["target_rule_id"] == "R-006"
    assert payload["ownership"]["sub_boundary"] == "certificate_tenure_as_hidden_business_age"
    assert RC014_GUIDE_PATH.exists()


def test_rc014_hidden_tenure_model_clearly_excludes_normal_validity_checks() -> None:
    payload = yaml.safe_load(RC014_MODEL_PATH.read_text(encoding="utf-8"))
    exclusions = payload["exclusion_rules"]["normal_validity_checks"]
    assert exclusions == ["证书在有效期内", "证书未过期", "续期有效", "法定合规校验"]
    assert payload["scope"]["primary_scene"] == "评分侧为主"
    assert payload["ownership"]["target_rule_id"] != "R-010"


def test_rc014_hidden_tenure_samples_cover_positive_negative_and_boundary_cases() -> None:
    payload = yaml.safe_load(RC014_SAMPLES_PATH.read_text(encoding="utf-8"))
    assert payload["candidate_id"] == "RC-014"
    assert payload["positive_samples"]
    assert payload["negative_samples"]
    assert payload["boundary_samples"]
    for key in ("positive_samples", "negative_samples", "boundary_samples"):
        for item in payload[key]:
            assert set(RC014_REQUIRED_FIELDS) <= set(item), item
            assert item["expression_pattern"] in RC014_ALLOWED_PATTERN
            assert item["certificate_context"] in RC014_ALLOWED_CONTEXT
            assert item["implicit_business_age_signal"] in RC014_ALLOWED_SIGNAL
            assert item["score_or_bias_linkage"] in RC014_ALLOWED_LINKAGE
            assert item["evidence_sufficiency"] in RC003_ALLOWED_SUFFICIENCY
            assert item["decision_layer"] in RC003_ALLOWED_LAYER


def test_rc014_negative_and_boundary_samples_cover_required_guardrails() -> None:
    payload = yaml.safe_load(RC014_SAMPLES_PATH.read_text(encoding="utf-8"))
    negative_expressions = {item["time_constraint_expression"] for item in payload["negative_samples"]}
    boundary_patterns = {item["expression_pattern"] for item in payload["boundary_samples"]}
    assert {"证书在有效期内", "证书未过期", "续期有效"} <= negative_expressions
    assert "法定合规校验" in "\n".join(item["rationale"] for item in payload["negative_samples"])
    assert "发证日期早于某时间点" in boundary_patterns or "持证延续历史体现经营稳定性" in boundary_patterns


def test_rc014_strengthening_package_writes_final_conclusion_to_r006_only() -> None:
    payload = yaml.safe_load(RC014_PACKAGE_PATH.read_text(encoding="utf-8"))
    assert payload["candidate_id"] == "RC-014"
    assert payload["final_conclusion"]["target_rule_id"] == "R-006"
    assert payload["final_conclusion"]["sub_boundary"] == "certificate_tenure_as_hidden_business_age"
    assert payload["final_conclusion"]["recommend_new_rule"] is False
    assert payload["final_conclusion"]["target_rule_id"] != "R-010"
