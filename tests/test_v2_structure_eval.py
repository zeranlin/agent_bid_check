from __future__ import annotations

from pathlib import Path

from scripts.eval_v2_structure import build_summary, evaluate_sample, load_samples


def test_load_samples_and_evaluate_structure_fixture() -> None:
    sample_path = Path("data/examples/v2_structure_eval_samples.json")
    samples = load_samples(sample_path)
    assert len(samples) >= 3

    result = evaluate_sample(samples[0], use_llm=False)
    assert result["module_total"] >= 2
    assert 0.0 <= result["module_accuracy"] <= 1.0
    assert 0.0 <= result["key_recall"] <= 1.0
    assert result["structure_llm_used"] is False


def test_build_summary_aggregates_metrics() -> None:
    results = [
        {
            "name": "a",
            "module_total": 2,
            "module_correct": 2,
            "key_total": 2,
            "key_hit": 1,
            "structure_llm_used": False,
            "structure_fallback_used": False,
            "details": [],
        },
        {
            "name": "b",
            "module_total": 2,
            "module_correct": 1,
            "key_total": 1,
            "key_hit": 1,
            "structure_llm_used": True,
            "structure_fallback_used": True,
            "details": [],
        },
    ]
    summary = build_summary(results, Path("samples.json"), use_llm=False)
    assert summary["module_accuracy"] == 0.75
    assert summary["key_recall"] == 2 / 3
    assert summary["llm_used_count"] == 1
    assert summary["fallback_count"] == 1
