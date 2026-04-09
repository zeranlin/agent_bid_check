from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
TRACKER_PATH = ROOT / "docs" / "trackers" / "v2-real-replay-issue-ledger.yaml"
GUIDE_PATH = ROOT / "docs" / "governance" / "v2-real-replay-closure-guideline.md"
TRACKER_README_PATH = ROOT / "docs" / "trackers" / "README.md"
REMEDIATION_TRACKER_PATH = ROOT / "docs" / "trackers" / "v2-remediation-tracker.md"

ALLOWED_PROBLEM_TYPES = {"误报", "漏报", "错层", "重复", "风险文案偏差", "规则归属错误", "证据映射错误"}
ALLOWED_ROOT_LAYERS = {"compare", "output_governance", "risk_admission", "assembler_web"}
ALLOWED_TARGET_ACTIONS = {"删除", "下沉", "升格", "改写", "拆分", "合并"}
ALLOWED_REVIEW_CONCLUSIONS = {"删除正式风险", "移入待补证", "移入排除", "升为正式风险", "保留正式风险", "改写文案", "拆分输出", "合并输出"}
ALLOWED_ACCEPTANCE_STATUS = {"待下发", "整改中", "待验收", "已通过", "未通过", "已关闭"}


def test_real_replay_issue_ledger_exists_and_has_required_sections() -> None:
    payload = yaml.safe_load(TRACKER_PATH.read_text(encoding="utf-8"))

    assert payload["ledger_id"] == "V2-REAL-REPLAY-CLOSURE-001"
    assert payload["single_source"] == "docs/trackers"
    assert payload["fields_definition"]
    assert payload["acceptance_baseline_template"]
    assert payload["issues"]


def test_real_replay_issue_entries_follow_unified_schema() -> None:
    payload = yaml.safe_load(TRACKER_PATH.read_text(encoding="utf-8"))
    required_keys = {
        "issue_id",
        "document_id",
        "document_name",
        "problem_type",
        "current_risk_title",
        "current_layer",
        "m_review_conclusion",
        "target_action",
        "root_cause_layer",
        "root_cause_tags",
        "rule_ids",
        "task_ids",
        "replay_run_ids",
        "replay_result_dirs",
        "acceptance_status",
        "acceptance_result",
    }

    for issue in payload["issues"]:
        assert required_keys <= set(issue), issue["issue_id"]
        assert issue["problem_type"] in ALLOWED_PROBLEM_TYPES
        assert issue["root_cause_layer"] in ALLOWED_ROOT_LAYERS
        assert issue["target_action"] in ALLOWED_TARGET_ACTIONS
        assert issue["m_review_conclusion"] in ALLOWED_REVIEW_CONCLUSIONS
        assert issue["acceptance_status"] in ALLOWED_ACCEPTANCE_STATUS
        assert issue["task_ids"]
        assert issue["replay_run_ids"]
        assert issue["replay_result_dirs"]


def test_real_replay_closure_has_two_real_file_samples() -> None:
    payload = yaml.safe_load(TRACKER_PATH.read_text(encoding="utf-8"))
    document_ids = {issue["document_id"] for issue in payload["issues"]}

    assert "DOC-FUZHOU-DORM-20260409" in document_ids
    assert "DOC-DIESEL-0330-20260409" in document_ids


def test_real_replay_result_index_links_back_to_tracker() -> None:
    payload = yaml.safe_load(TRACKER_PATH.read_text(encoding="utf-8"))
    indexed_runs = payload["result_run_index"]

    assert "20260409-ar2-fuzhou" in indexed_runs
    assert "20260409-w011-diesel" in indexed_runs

    for run_id, run_info in indexed_runs.items():
        result_dir = ROOT / run_info["result_dir"]
        index_path = result_dir / "replay_closure_index.json"
        assert index_path.exists(), run_id

        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
        assert index_payload["run_id"] == run_id
        assert index_payload["tracker_ledger_path"] == "docs/trackers/v2-real-replay-issue-ledger.yaml"
        assert index_payload["issue_ids"]
        assert index_payload["task_ids"]


def test_real_replay_tracker_and_task_tracker_are_cross_linked() -> None:
    tracker_text = TRACKER_README_PATH.read_text(encoding="utf-8")
    remediation_text = REMEDIATION_TRACKER_PATH.read_text(encoding="utf-8")
    guide_text = GUIDE_PATH.read_text(encoding="utf-8")

    assert "v2-real-replay-issue-ledger.yaml" in tracker_text
    assert "Task-AR3" in remediation_text
    assert "docs/trackers/v2-real-replay-issue-ledger.yaml" in guide_text
    assert "replay_closure_index.json" in guide_text


def test_real_replay_acceptance_baseline_template_is_actionable() -> None:
    payload = yaml.safe_load(TRACKER_PATH.read_text(encoding="utf-8"))
    template = payload["acceptance_baseline_template"]

    assert template["required_fields"] == [
        "当前风险标题",
        "当前层级",
        "M复核结论",
        "目标动作",
        "根因层级",
        "对应规则编号",
        "对应任务单编号",
        "验收状态",
        "验证通过回放",
    ]
    assert "M 如何验收" in GUIDE_PATH.read_text(encoding="utf-8")
