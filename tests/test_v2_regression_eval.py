from __future__ import annotations

import json
from pathlib import Path

from app.pipelines.v2.regression import compare_risks, compare_structure, extract_actual_risks, extract_actual_structure
from scripts.eval_v2_regression import build_summary, collect_outputs, evaluate_sample, load_samples


def test_load_samples_and_evaluate_regression_fixture() -> None:
    sample_path = Path("data/examples/v2_regression_eval_samples.json")
    samples = load_samples(sample_path)
    assert len(samples) >= 2

    result = evaluate_sample(samples[0])
    assert result["sample_id"] == samples[0]["sample_id"]
    assert result["matched_risk_count"] == 2
    assert result["false_positive_risk_count"] == 1
    assert result["manual_review_gap_count"] == 1
    assert result["structure_hit_count"] == 1
    assert result["topic_coverage_hit_count"] == 2


def test_build_summary_aggregates_regression_metrics() -> None:
    results = [
        {
            "sample_id": "a",
            "structure_required_total": 2,
            "structure_hit_count": 1,
            "topic_coverage_total": 2,
            "topic_coverage_hit_count": 1,
            "gold_risk_total": 3,
            "matched_risk_count": 2,
            "missed_risk_count": 1,
            "false_positive_risk_count": 1,
            "manual_review_gap_count": 0,
        },
        {
            "sample_id": "b",
            "structure_required_total": 1,
            "structure_hit_count": 1,
            "topic_coverage_total": 1,
            "topic_coverage_hit_count": 1,
            "gold_risk_total": 1,
            "matched_risk_count": 1,
            "missed_risk_count": 0,
            "false_positive_risk_count": 0,
            "manual_review_gap_count": 1,
        },
    ]
    summary = build_summary(results, Path("samples.json"))
    assert summary["structure_hit_rate"] == 2 / 3
    assert summary["topic_coverage_hit_rate"] == 2 / 3
    assert summary["risk_hit_rate"] == 3 / 4
    assert summary["miss_rate"] == 1 / 4
    assert summary["false_positive_risk_count"] == 1
    assert summary["manual_review_gap_count"] == 1


def test_collect_outputs_contains_risk_and_structure_gaps() -> None:
    result = evaluate_sample(load_samples(Path("data/examples/v2_regression_eval_samples.json"))[1])
    outputs = collect_outputs([result])
    assert len(outputs["missed_risks"]) == 1
    assert len(outputs["structure_gaps"]) == 2


def test_compare_helpers_support_structure_and_manual_review_gap() -> None:
    sample = load_samples(Path("data/examples/v2_regression_eval_samples.json"))[0]
    sections, bundles = extract_actual_structure(sample["system"])
    risks = extract_actual_risks(sample["system"])

    structure = compare_structure(sample["gold"]["structure"], sections, bundles)
    risk_result = compare_risks(sample["gold"]["risks"], risks)

    assert len(structure["matched_sections"]) == 1
    assert len(structure["missed_topic_coverages"]) == 0
    assert len(risk_result["manual_review_gaps"]) == 1
    assert risk_result["manual_review_gaps"][0]["reason"] == "manual_review_flag_mismatch"


def test_regression_fixture_json_is_valid_utf8() -> None:
    payload = json.loads(Path("data/examples/v2_regression_eval_samples.json").read_text(encoding="utf-8"))
    assert isinstance(payload, list)
