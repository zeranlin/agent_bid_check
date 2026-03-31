from __future__ import annotations

from pathlib import Path

from scripts.eval_v2_compare import build_markdown_report, build_summary, evaluate_sample, load_samples, write_outputs


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


def test_write_outputs_emits_json_and_markdown(tmp_path: Path) -> None:
    summary = build_summary(
        [
            {
                "name": "sample_a",
                "matched_metrics": 2,
                "total_metrics": 3,
                "accuracy": 2 / 3,
                "actual": {"cluster_count": 1},
                "details": [{"metric": "cluster_count", "expected": 1, "actual": 1, "matched": True}],
            }
        ],
        Path("samples.json"),
    )
    write_outputs(tmp_path, summary)
    assert (tmp_path / "compare_eval.json").exists()
    assert (tmp_path / "compare_eval.md").exists()
    assert "# V2 汇总层评估结果" in build_markdown_report(summary)
