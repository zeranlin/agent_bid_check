from __future__ import annotations

import json
from pathlib import Path

from app.pipelines.v2.regression import compare_risks, compare_structure, extract_actual_risks, extract_actual_structure
from scripts.eval_v2_regression import (
    build_markdown_report,
    build_summary,
    collect_outputs,
    describe_failure_code,
    evaluate_sample,
    load_samples,
    normalize_failure_code,
    print_report,
)


def test_load_samples_and_evaluate_regression_fixture() -> None:
    sample_path = Path("data/examples/v2_regression_eval_samples.json")
    samples = load_samples(sample_path)
    assert len(samples) >= 9

    result = evaluate_sample(samples[0])
    assert result["sample_id"] == samples[0]["sample_id"]
    assert result["matched_risk_count"] == 2
    assert result["false_positive_risk_count"] == 1
    assert result["manual_review_gap_count"] == 1
    assert result["structure_hit_count"] == 1
    assert result["topic_coverage_hit_count"] == 2
    assert result["failure_analysis"]["primary_blocker_layer"] == "topic"
    assert result["failure_analysis"]["root_cause_details"][0]["code"] == "false_positive_risk"


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
            "failure_analysis": {
                "root_causes": ["risk_not_extracted", "false_positive_risk"],
                "layers": [
                    {"layer": "topic", "failed": True},
                    {"layer": "compare", "failed": True},
                ],
            },
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
            "failure_analysis": {
                "root_causes": ["manual_review_flag_mismatch"],
                "layers": [
                    {"layer": "topic", "failed": True},
                ],
            },
            "comparison_failure_reason_codes": ["policy_technical_inconsistency"],
        },
    ]
    summary = build_summary(results, Path("samples.json"))
    assert summary["structure_hit_rate"] == 2 / 3
    assert summary["topic_coverage_hit_rate"] == 2 / 3
    assert summary["risk_hit_rate"] == 3 / 4
    assert summary["miss_rate"] == 1 / 4
    assert summary["false_positive_risk_count"] == 1
    assert summary["manual_review_gap_count"] == 1
    assert summary["root_cause_summary"] == {
        "risk_not_extracted": 1,
        "false_positive_risk": 1,
        "manual_review_flag_mismatch": 1,
    }
    assert summary["standardized_failure_summary"]["risk_not_extracted"]["layer"] == "topic"
    assert summary["standardized_failure_summary"]["false_positive_risk"]["category"] == "false_positive"
    assert summary["layer_failure_summary"] == {"topic": 2, "compare": 1}
    assert summary["comparison_failure_reason_summary"] == {"policy_technical_inconsistency": 1}


def test_collect_outputs_contains_risk_and_structure_gaps() -> None:
    result = evaluate_sample(load_samples(Path("data/examples/v2_regression_eval_samples.json"))[1])
    outputs = collect_outputs([result])
    assert len(outputs["missed_risks"]) == 1
    assert len(outputs["structure_gaps"]) == 2
    assert len(outputs["failure_analysis"]) == 1
    assert outputs["failure_analysis"][0]["primary_blocker_layer"] == "structure"
    assert outputs["failure_analysis"][0]["cascaded_failure"] is True


def test_regression_structure_gap_fixture_marks_structure_as_primary_blocker() -> None:
    result = evaluate_sample(load_samples(Path("data/examples/v2_regression_eval_samples.json"))[1])
    assert result["failure_analysis"]["primary_blocker_layer"] == "structure"
    assert result["failure_analysis"]["cascaded_failure"] is True
    assert "section_not_found" in result["failure_analysis"]["root_causes"]
    assert "missing_titles" in result["failure_analysis"]["root_causes"]
    assert "missing_modules" in result["failure_analysis"]["root_causes"]
    assert "risk_not_extracted" in result["failure_analysis"]["root_causes"]


def test_regression_breakpoint_samples_separate_coverage_topic_and_manual_review_failures() -> None:
    samples = {
        sample["sample_id"]: sample for sample in load_samples(Path("data/examples/v2_regression_breakpoint_samples.json"))
    }

    coverage_result = evaluate_sample(samples["regression_coverage_gap_after_section_recall_001"])
    topic_result = evaluate_sample(samples["regression_topic_miss_after_recall_001"])
    manual_result = evaluate_sample(samples["regression_manual_review_boundary_after_recall_001"])

    assert coverage_result["failure_analysis"]["primary_blocker_layer"] == "structure"
    assert "missing_titles" in coverage_result["failure_analysis"]["root_causes"]
    assert coverage_result["breakpoint"]["current_failure_point"] == "coverage_gap_after_section_recall"

    assert topic_result["failure_analysis"]["primary_blocker_layer"] == "topic"
    assert topic_result["matched_risk_count"] == 0
    assert topic_result["missed_risk_count"] == 1
    assert topic_result["breakpoint"]["expected_topics"] == ["technical_standard"]

    assert manual_result["failure_analysis"]["primary_blocker_layer"] == "topic"
    assert manual_result["manual_review_gap_count"] == 1
    assert manual_result["matched_risk_count"] == 1
    assert manual_result["breakpoint"]["expected_risk_titles"] == ["将注册资本设为资格门槛"]


def test_failure_codebook_normalizes_unknown_reason() -> None:
    assert normalize_failure_code("missing_titles") == "missing_titles"
    assert normalize_failure_code("unknown_new_reason") == "unknown_reason"
    assert describe_failure_code("unknown_new_reason")["label"] == "未归类失败原因"


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


def test_expanded_regression_dataset_can_pass_thresholds() -> None:
    samples = load_samples(Path("data/examples/v2_regression_eval_samples.json"))
    summary = build_summary([evaluate_sample(sample) for sample in samples], Path("data/examples/v2_regression_eval_samples.json"))
    assert summary["structure_hit_rate"] >= 0.80
    assert summary["topic_coverage_hit_rate"] >= 0.80
    assert summary["risk_hit_rate"] >= 0.80
    assert summary["miss_rate"] <= 0.20


def test_regression_markdown_report_contains_layered_failures_and_suggestions(tmp_path: Path) -> None:
    result = evaluate_sample(load_samples(Path("data/examples/v2_regression_eval_samples.json"))[1])
    outputs = collect_outputs([result])
    summary = build_summary([result], Path("data/examples/v2_regression_eval_samples.json"))
    report = build_markdown_report(summary, outputs)
    assert "# V2 埋点回归失败报告" in report
    assert "### regression_structure_gap_001" in report
    assert "#### 分层状态" in report
    assert "#### 结构差异" in report
    assert "#### 风险差异" in report
    assert "优先补章节切分与标题识别规则。" in report


def test_regression_markdown_report_includes_breakpoint_details() -> None:
    samples = load_samples(Path("data/examples/v2_regression_breakpoint_samples.json"))
    sample = next(item for item in samples if item["sample_id"] == "regression_topic_miss_after_recall_001")
    result = evaluate_sample(sample)
    outputs = collect_outputs([result])
    summary = build_summary([result], Path("data/examples/v2_regression_breakpoint_samples.json"))
    report = build_markdown_report(summary, outputs)
    assert "#### 断点说明" in report
    assert "topic_miss_after_recall" in report
    assert "第三章 技术标准与检测要求" in report
    assert "technical_standard" in report


def test_regression_cross_topic_import_conflict_samples_are_classified_correctly() -> None:
    samples = {sample["sample_id"]: sample for sample in load_samples(Path("data/examples/v2_regression_eval_samples.json"))}
    positive = evaluate_sample(samples["regression_policy_technical_import_conflict_a_003"])
    negative = evaluate_sample(samples["regression_policy_technical_import_negative_c_003"])

    assert positive["matched_risk_count"] == 1
    assert positive["comparison_failure_reason_codes"] == ["policy_technical_inconsistency"]
    assert negative["matched_risk_count"] == 0
    assert negative["missed_risk_count"] == 0
    assert negative["comparison_failure_reason_codes"] == []


def test_regression_real_like_import_conflict_samples_cover_technical_parameter_recall_boundary() -> None:
    samples = {sample["sample_id"]: sample for sample in load_samples(Path("data/examples/v2_regression_eval_samples.json"))}
    positive = evaluate_sample(samples["regression_policy_technical_parameter_import_conflict_real_004"])
    negative = evaluate_sample(samples["regression_policy_technical_parameter_background_negative_004"])

    assert positive["structure_hit_count"] == 2
    assert positive["topic_coverage_hit_count"] == 2
    assert positive["matched_risk_count"] == 1
    assert positive["comparison_failure_reason_codes"] == ["policy_technical_inconsistency"]

    assert negative["structure_hit_count"] == 2
    assert negative["topic_coverage_hit_count"] == 2
    assert negative["matched_risk_count"] == 0
    assert negative["comparison_failure_reason_codes"] == []


def test_regression_star_marker_samples_are_classified_correctly() -> None:
    samples = {sample["sample_id"]: sample for sample in load_samples(Path("data/examples/v2_regression_eval_samples.json"))}
    positive = evaluate_sample(samples["regression_star_marker_missing_positive_005"])
    negative = evaluate_sample(samples["regression_star_marker_missing_negative_gbt_005"])

    assert positive["matched_risk_count"] == 1
    assert positive["missed_risk_count"] == 0
    assert positive["comparison_failure_reason_codes"] == ["star_marker_missing_for_mandatory_standard"]

    assert negative["matched_risk_count"] == 0
    assert negative["missed_risk_count"] == 0
    assert negative["comparison_failure_reason_codes"] == []


def test_print_report_defaults_to_markdown(capsys) -> None:
    result = evaluate_sample(load_samples(Path("data/examples/v2_regression_eval_samples.json"))[1])
    outputs = collect_outputs([result])
    summary = build_summary([result], Path("data/examples/v2_regression_eval_samples.json"))
    print_report(summary, outputs)
    captured = capsys.readouterr()
    assert "# V2 埋点回归失败报告" in captured.out
    assert "## 样本明细" in captured.out


def test_print_report_supports_text_mode(capsys) -> None:
    result = evaluate_sample(load_samples(Path("data/examples/v2_regression_eval_samples.json"))[0])
    outputs = collect_outputs([result])
    summary = build_summary([result], Path("data/examples/v2_regression_eval_samples.json"))
    print_report(summary, outputs, as_markdown=False)
    captured = capsys.readouterr()
    assert "V2 埋点回归评估结果" in captured.out
    assert "# V2 埋点回归失败报告" not in captured.out
