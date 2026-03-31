from __future__ import annotations

from pathlib import Path

from scripts.eval_v2_topics import build_summary, evaluate_sample, load_samples


def test_load_samples_and_evaluate_topic_fixture() -> None:
    sample_path = Path("data/examples/v2_topic_eval_samples.json")
    samples = load_samples(sample_path)
    assert len(samples) >= 16

    result = evaluate_sample(samples[0])
    assert result["topic_count"] >= 1
    assert 0.0 <= result["high_medium_hit_rate"] <= 1.0
    assert 0.0 <= result["technical_hit_rate"] <= 1.0
    assert 0.0 <= result["manual_review_ratio"] <= 1.0
    assert 0.0 <= result["topic_hit_rate"] <= 1.0
    assert 0.0 <= result["topic_miss_rate"] <= 1.0
    assert 0.0 <= result["false_positive_rate"] <= 1.0
    assert "selected_keys" in result["topic_execution_plan"]
    assert "target_topic_detail" in result


def test_build_topic_summary_aggregates_metrics() -> None:
    results = [
        {
            "name": "a",
            "topic_mode": "default",
            "topic_count": 4,
            "high_medium_expected": 2,
            "high_medium_hit": 1,
            "technical_expected": 1,
            "technical_hit": 1,
            "manual_review_count": 1,
            "topic": "qualification",
            "topic_expected_total": 2,
            "topic_hit_count": 1,
            "topic_miss_count": 1,
            "false_positive_total": 1,
            "false_positive_count": 0,
            "manual_review_expected_total": 1,
            "manual_review_hit": 1,
            "manual_review_false_positive_count": 0,
            "topic_execution_plan": {},
            "details": [],
        },
        {
            "name": "b",
            "topic_mode": "slim",
            "topic_count": 3,
            "high_medium_expected": 3,
            "high_medium_hit": 3,
            "technical_expected": 2,
            "technical_hit": 1,
            "manual_review_count": 0,
            "topic": "scoring",
            "topic_expected_total": 3,
            "topic_hit_count": 3,
            "topic_miss_count": 0,
            "false_positive_total": 1,
            "false_positive_count": 1,
            "manual_review_expected_total": 0,
            "manual_review_hit": 0,
            "manual_review_false_positive_count": 1,
            "topic_execution_plan": {},
            "details": [],
        },
    ]
    summary = build_summary(results, Path("samples.json"))
    assert summary["high_medium_hit_rate"] == 4 / 5
    assert summary["technical_hit_rate"] == 2 / 3
    assert summary["manual_review_ratio"] == 1 / 7
    assert summary["topic_hit_rate"] == 4 / 5
    assert summary["topic_miss_rate"] == 1 / 5
    assert summary["false_positive_rate"] == 1 / 2
    assert summary["manual_review_expected_rate"] == 1.0
    assert summary["manual_review_false_positive_count"] == 1
    assert summary["by_topic"]["qualification"]["topic_miss_rate"] == 1 / 2
    assert summary["by_topic"]["scoring"]["false_positive_rate"] == 1.0
