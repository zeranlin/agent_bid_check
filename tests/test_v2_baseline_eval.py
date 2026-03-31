from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.common.schemas import RiskPoint
from app.config import ReviewSettings
from scripts.eval_v2_baseline import build_summary, evaluate_sample, load_samples


def test_load_samples_and_evaluate_baseline_fixture() -> None:
    sample_path = Path("data/examples/v2_baseline_eval_samples.json")
    samples = load_samples(sample_path)
    assert len(samples) >= 18

    fake_risks = [
        RiskPoint(
            title="评分标准量化不足",
            severity="中风险",
            review_type="评分办法",
            source_location="第二章 评分办法",
            source_excerpt="技术方案优得40分，良得30分",
            risk_judgment=["评分标准缺少量化口径。"],
            legal_basis=["需人工复核"],
            rectification=["补充分档和量化标准。"],
        )
    ]
    with patch("scripts.eval_v2_baseline._run_baseline", return_value=(fake_risks, "# fake markdown")):
        result = evaluate_sample(samples[0], ReviewSettings())

    assert result["sample_id"] == samples[0]["sample_id"]
    assert result["actual_risk_count"] == 1
    assert 0.0 <= result["expected_hit_rate"] <= 1.0
    assert 0.0 <= result["must_hit_rate"] <= 1.0
    assert 0.0 <= result["false_positive_rate"] <= 1.0
    assert 0.0 <= result["report_quality_pass_rate"] <= 1.0
    assert result["report_quality_total"] >= 1
    assert "report_quality_checks" in result


def test_build_baseline_summary_aggregates_metrics() -> None:
    results = [
        {
            "sample_id": "a",
            "expected_total": 2,
            "expected_hit": 1,
            "must_hit_total": 2,
            "must_hit_count": 1,
            "false_positive_total": 1,
            "false_positive_count": 0,
            "high_risk_miss_total": 1,
            "high_risk_miss_count": 1,
            "report_quality_total": 3,
            "report_quality_passed": 2,
            "report_quality_failed": 1,
            "report_quality_all_passed": False,
        },
        {
            "sample_id": "b",
            "expected_total": 3,
            "expected_hit": 3,
            "must_hit_total": 2,
            "must_hit_count": 2,
            "false_positive_total": 2,
            "false_positive_count": 1,
            "high_risk_miss_total": 0,
            "high_risk_miss_count": 0,
            "report_quality_total": 2,
            "report_quality_passed": 2,
            "report_quality_failed": 0,
            "report_quality_all_passed": True,
        },
    ]
    summary = build_summary(results, Path("samples.json"))
    assert summary["risk_hit_rate"] == 4 / 5
    assert summary["must_hit_rate"] == 3 / 4
    assert summary["miss_rate"] == 1 / 4
    assert summary["false_positive_rate"] == 1 / 3
    assert summary["high_risk_miss_rate"] == 1.0
    assert summary["report_quality_pass_rate"] == 4 / 5
    assert summary["report_quality_sample_pass_rate"] == 1 / 2
