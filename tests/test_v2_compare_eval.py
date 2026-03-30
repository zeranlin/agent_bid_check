from __future__ import annotations

from pathlib import Path

from scripts.eval_v2_compare import build_summary, evaluate_sample, load_samples


def test_load_samples_and_evaluate_compare_fixture() -> None:
    sample_path = Path("data/examples/v2_compare_eval_samples.json")
    samples = load_samples(sample_path)
    assert len(samples) >= 2

    result = evaluate_sample(samples[0])
    assert result["total_metrics"] >= 4
    assert 0.0 <= result["accuracy"] <= 1.0
    assert "actual" in result


def test_build_compare_summary_aggregates_metrics() -> None:
    results = [
        {"name": "a", "matched_metrics": 3, "total_metrics": 4, "accuracy": 0.75, "actual": {}, "details": []},
        {"name": "b", "matched_metrics": 5, "total_metrics": 6, "accuracy": 5 / 6, "actual": {}, "details": []},
    ]
    summary = build_summary(results, Path("samples.json"))
    assert summary["matched_metrics"] == 8
    assert summary["total_metrics"] == 10
    assert summary["accuracy"] == 0.8
