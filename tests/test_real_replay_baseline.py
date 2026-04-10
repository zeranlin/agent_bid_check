from __future__ import annotations

import json
from pathlib import Path

import yaml

from app.pipelines.v2.replay_baseline import (
    evaluate_replay_assertions,
    load_real_replay_baseline_suite,
    run_real_replay_baseline,
    run_real_replay_baseline_batch,
)

ROOT = Path(__file__).resolve().parents[1]


def _write_seed_run(seed_dir: Path, title: str) -> None:
    seed_dir.mkdir(parents=True, exist_ok=True)
    (seed_dir / "baseline_review.md").write_text(
        f"""
# 招标文件合规审查结果

审查对象：`sample.txt`

## 风险点1：{title}

- 问题定性：高风险
- 审查类型：评分因素合规性审查
- 原文位置：第一章
- 原文摘录：验收方案优的得满分。
- 风险判断：
  - 示例判断
- 法律/政策依据：
  - 示例依据
- 整改建议：
  - 示例建议
""".strip(),
        encoding="utf-8",
    )
    (seed_dir / "topic_reviews").mkdir(parents=True, exist_ok=True)


def _write_config(config_path: Path, source_file: Path, seed_dir: Path) -> None:
    payload = {
        "suite_id": "REAL-REPLAY-BASELINE-TEST",
        "single_source": "docs/trackers",
        "documents": [
            {
                "document_id": "DOC-TEST-001",
                "document_name": "sample.txt",
                "file_path": str(source_file),
                "topic_mode": "mature",
                "seed_result_dir": str(seed_dir),
                "result_dir": "data/results/v2/gr1-test-sample",
                "notes": ["测试说明"],
                "baseline_assertions": {
                    "should_report": [
                        {
                            "id": "acceptance-score-formal",
                            "title": "将项目验收方案纳入评审因素，违反评审规则合规性要求",
                            "family_key": "acceptance_scheme_scoring",
                        }
                    ],
                    "should_not_report": [
                        {
                            "id": "template-placeholder",
                            "title": "验收时间条款留白，导致履约验收时点不明确，缺乏可操作性",
                        }
                    ],
                    "should_pending": [],
                },
            }
        ],
    }
    config_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_load_real_replay_baseline_suite_reads_tracker_style_config(tmp_path: Path) -> None:
    source_file = tmp_path / "sample.txt"
    source_file.write_text("示例正文", encoding="utf-8")
    seed_dir = tmp_path / "seed-run"
    _write_seed_run(seed_dir, "将项目验收方案纳入评审因素，违反评审规则合规性要求")
    config_path = tmp_path / "replay-suite.yaml"
    _write_config(config_path, source_file, seed_dir)

    suite = load_real_replay_baseline_suite(config_path)

    assert suite["suite_id"] == "REAL-REPLAY-BASELINE-TEST"
    assert suite["documents"][0]["document_id"] == "DOC-TEST-001"
    assert suite["documents"][0]["baseline_assertions"]["should_report"][0]["family_key"] == "acceptance_scheme_scoring"


def test_run_real_replay_baseline_generates_standard_outputs_and_assertions(tmp_path: Path) -> None:
    source_file = tmp_path / "sample.txt"
    source_file.write_text("示例正文", encoding="utf-8")
    seed_dir = tmp_path / "seed-run"
    _write_seed_run(seed_dir, "将项目验收方案纳入评审因素，违反评审规则合规性要求")
    config_path = tmp_path / "replay-suite.yaml"
    _write_config(config_path, source_file, seed_dir)
    suite = load_real_replay_baseline_suite(config_path)

    result = run_real_replay_baseline(suite, document_id="DOC-TEST-001", output_root=tmp_path / "outputs")
    output_dir = Path(result["result_dir"])

    for name in (
        "final_snapshot.json",
        "final_output.json",
        "final_review.md",
        "replay_assertions.json",
        "replay_summary.json",
    ):
        assert (output_dir / name).exists(), name

    summary = json.loads((output_dir / "replay_summary.json").read_text(encoding="utf-8"))
    assert summary["missing_should_report"] == []
    assert summary["unexpected_reported"] == []
    assert summary["missing_should_pending"] == []
    assert summary["unexpected_pending"] == []
    assert summary["mismatched_layers"] == []
    assert summary["formal_count"] == 1


def test_run_real_replay_baseline_reports_clear_layer_mismatch_and_unexpected_report(tmp_path: Path) -> None:
    source_file = tmp_path / "sample.txt"
    source_file.write_text("示例正文", encoding="utf-8")
    seed_dir = tmp_path / "seed-run"
    _write_seed_run(seed_dir, "将项目验收方案纳入评审因素，违反评审规则合规性要求")
    config_path = tmp_path / "replay-suite.yaml"
    _write_config(config_path, source_file, seed_dir)
    suite = load_real_replay_baseline_suite(config_path)
    suite["documents"][0]["baseline_assertions"]["should_report"] = []
    suite["documents"][0]["baseline_assertions"]["should_pending"] = [
        {
            "id": "should-be-pending",
            "title": "将项目验收方案纳入评审因素，违反评审规则合规性要求",
            "family_key": "acceptance_scheme_scoring",
        }
    ]
    suite["documents"][0]["baseline_assertions"]["should_not_report"] = [
        {
            "id": "should-not-formal",
            "title": "将项目验收方案纳入评审因素，违反评审规则合规性要求",
            "family_key": "acceptance_scheme_scoring",
        }
    ]

    result = run_real_replay_baseline(suite, document_id="DOC-TEST-001", output_root=tmp_path / "outputs")
    summary = json.loads((Path(result["result_dir"]) / "replay_summary.json").read_text(encoding="utf-8"))

    assert summary["missing_should_pending"] == ["should-be-pending"]
    assert summary["unexpected_reported"] == ["should-not-formal"]
    assert summary["unexpected_pending"] == []
    assert summary["mismatched_layers"][0]["assertion_id"] == "should-be-pending"
    assert summary["mismatched_layers"][0]["expected_layer"] == "pending_review_items"
    assert summary["mismatched_layers"][0]["actual_layers"] == ["formal_risks"]


def test_evaluate_replay_assertions_allows_should_report_items_to_land_in_pending() -> None:
    snapshot = {
        "final_risks": {
            "formal_risks": [],
            "pending_review_items": [
                {
                    "title": "评分描述量化口径不足，存在评审一致性风险",
                    "family_key": "scoring_clarity",
                    "problem_kind": "standard",
                }
            ],
            "excluded_risks": [],
        }
    }
    _, summary = evaluate_replay_assertions(
        snapshot,
        {
            "should_report": [
                {
                    "id": "reported-in-pending",
                    "title": "评分描述量化口径不足，存在评审一致性风险",
                    "family_key": "scoring_clarity",
                }
            ],
            "should_not_report": [],
            "should_pending": [],
        },
    )

    assert summary["missing_should_report"] == []
    assert summary["mismatched_layers"] == []
    assert summary["pending_count"] == 1


def test_run_real_replay_baseline_batch_supports_three_documents(tmp_path: Path) -> None:
    documents = []
    for index in range(1, 4):
        source_file = tmp_path / f"sample-{index}.txt"
        source_file.write_text(f"示例正文-{index}", encoding="utf-8")
        seed_dir = tmp_path / f"seed-run-{index}"
        _write_seed_run(seed_dir, "将项目验收方案纳入评审因素，违反评审规则合规性要求")
        documents.append(
            {
                "document_id": f"DOC-TEST-00{index}",
                "document_name": f"sample-{index}.txt",
                "file_path": str(source_file),
                "topic_mode": "mature",
                "seed_result_dir": str(seed_dir),
                "result_dir": f"data/results/v2/gr1-test-sample-{index}",
                "notes": [f"测试说明-{index}"],
                "baseline_assertions": {
                    "should_report": [
                        {
                            "id": f"report-{index}",
                            "title": "将项目验收方案纳入评审因素，违反评审规则合规性要求",
                            "family_key": "acceptance_scheme_scoring",
                        }
                    ],
                    "should_not_report": [],
                    "should_pending": [],
                },
            }
        )
    suite = {
        "suite_id": "REAL-REPLAY-BASELINE-TEST",
        "single_source": "docs/trackers",
        "documents": documents,
    }

    results = run_real_replay_baseline_batch(suite, output_root=tmp_path / "outputs")

    assert len(results) == 3
    assert {item["document_id"] for item in results} == {"DOC-TEST-001", "DOC-TEST-002", "DOC-TEST-003"}
    for item in results:
        summary = json.loads((Path(item["result_dir"]) / "replay_summary.json").read_text(encoding="utf-8"))
        assert summary["missing_should_report"] == []


def test_tracker_replay_baseline_config_contains_three_real_documents_and_notes() -> None:
    config_path = ROOT / "docs" / "trackers" / "v2-real-replay-baselines.yaml"
    suite = load_real_replay_baseline_suite(config_path)

    assert [item["document_id"] for item in suite["documents"]] == [
        "DOC-DIESEL-0330-BASELINE",
        "DOC-FUJIAN-PROPERTY-BASELINE",
        "DOC-FUZHOU-DORM-BASELINE",
    ]
    for document in suite["documents"]:
        assertions = document["baseline_assertions"]
        assert document["notes"]
        assert "should_report" in assertions
        assert "should_not_report" in assertions
        assert "should_pending" in assertions
