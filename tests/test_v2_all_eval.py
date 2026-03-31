from __future__ import annotations

import json
from pathlib import Path

from scripts.eval_v2_all import build_markdown_report, build_overall_summary, build_stage_result, write_outputs


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
    assert summary["passed_stage_count"] == 1
    assert summary["total_checks"] == 3
    assert summary["passed_checks"] == 2
    assert summary["status"] == "failed"


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
    assert "# V2 总评估报告" in build_markdown_report(summary)
