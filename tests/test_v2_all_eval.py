from __future__ import annotations

import json
from pathlib import Path

from scripts.eval_v2_all import build_markdown_report, build_overall_summary, build_stage_result, write_outputs
from scripts.eval_v2_gate_batch import build_batch_markdown, build_run_label


def test_build_overall_summary_aggregates_stage_status() -> None:
    structure_stage = build_stage_result(
        "structure",
        {"sample_count": 10, "module_accuracy": 0.9},
        [
            {"metric": "module_accuracy", "actual": 0.9, "target": 0.85, "comparator": ">=", "passed": True},
            {"metric": "key_recall", "actual": 1.0, "target": 0.95, "comparator": ">=", "passed": True},
        ],
    )
    regression_stage = build_stage_result(
        "regression",
        {"sample_count": 2, "risk_hit_rate": 0.6},
        [
            {"metric": "risk_hit_rate", "actual": 0.6, "target": 0.8, "comparator": ">=", "passed": False},
        ],
    )
    summary = build_overall_summary([structure_stage, regression_stage], Path("data/eval"))
    assert summary["stage_count"] == 2
    assert summary["passed_delivery_stage_count"] == 2
    assert summary["passed_quality_stage_count"] == 1
    assert summary["total_checks"] == 3
    assert summary["passed_checks"] == 2
    assert summary["p2_delivery_status"] == "passed"
    assert summary["quality_gate_status"] == "failed"
    assert summary["quality_gate_passed"] is False
    assert summary["gate_blocker_count"] == 1
    assert summary["gate_blockers"][0]["metric"] == "risk_hit_rate"
    assert "regression" in summary["gate_thresholds"]


def test_write_outputs_emits_json_and_markdown(tmp_path: Path) -> None:
    summary = build_overall_summary(
        [
            build_stage_result(
                "compare",
                {"sample_count": 2, "accuracy": 1.0},
                [{"metric": "accuracy", "actual": 1.0, "target": 0.95, "comparator": ">=", "passed": True}],
            )
        ],
        Path("data/eval"),
    )
    write_outputs(tmp_path, summary)
    payload = json.loads((tmp_path / "v2_all_eval.json").read_text(encoding="utf-8"))
    assert payload["stage_count"] == 1
    assert (tmp_path / "v2_all_eval.md").exists()
    report = build_markdown_report(summary)
    assert "# V2 总评估报告" in report
    assert "## 门禁阈值" in report
    assert "## 门禁阻塞项" in report


def test_build_run_label_and_batch_markdown() -> None:
    label = build_run_label(__import__("datetime").datetime(2026, 3, 31, 12, 30, 45))
    assert label == "20260331-123045"

    overall_summary = build_overall_summary(
        [
            build_stage_result(
                "regression",
                {"sample_count": 1, "risk_hit_rate": 1.0},
                [{"metric": "risk_hit_rate", "actual": 1.0, "target": 0.8, "comparator": ">=", "passed": True}],
            )
        ],
        Path("data/eval"),
    )
    batch_markdown = build_batch_markdown(
        {
            "run_label": "20260331-123045",
            "dataset_root": "data/eval",
            "run_dir": "data/eval_runs/v2/20260331-123045",
            "commands": ["python scripts/eval_v2_regression.py --dataset-root data/eval"],
            "regression": {
                "structure_hit_rate": 1.0,
                "topic_coverage_hit_rate": 1.0,
                "risk_hit_rate": 1.0,
                "miss_rate": 0.0,
            },
            "overall": {"quality_gate_status": "passed", "gate_blocker_count": 0},
        },
        overall_summary,
    )
    assert "# V2 固定回归跑批结果" in batch_markdown
    assert "python scripts/eval_v2_regression.py --dataset-root data/eval" in batch_markdown
