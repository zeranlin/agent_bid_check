from __future__ import annotations

from pathlib import Path

from scripts.eval_v2_topics import build_markdown_report, build_summary, evaluate_sample, load_samples, write_outputs


def test_load_samples_and_evaluate_topic_fixture() -> None:
    sample_path = Path("data/examples/v2_topic_eval_samples.json")
    samples = load_samples(sample_path)
    assert len(samples) >= 39

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


def test_scoring_recalled_but_missed_samples_are_recovered_by_postprocess() -> None:
    sample_path = Path("data/examples/v2_topic_eval_samples.json")
    samples = {sample["sample_id"]: sample for sample in load_samples(sample_path)}
    expected_titles = {
        "topic_scoring_recalled_miss_001": "评分档次缺少量化口径",
        "topic_scoring_subjective_miss_001": "主观分值裁量空间过大",
    }
    for sample_id, expected_title in expected_titles.items():
        result = evaluate_sample(samples[sample_id])
        assert result["topic_hit_count"] == 1
        assert result["topic_miss_count"] == 0
        assert expected_title in result["target_topic_detail"]["risk_titles"]
        assert "risk_not_extracted" in result["target_topic_detail"]["failure_reasons"]


def test_multi_topic_recalled_but_missed_samples_are_recovered_by_postprocess() -> None:
    sample_path = Path("data/examples/v2_topic_eval_samples.json")
    samples = {sample["sample_id"]: sample for sample in load_samples(sample_path)}
    expected_titles = {
        "topic_qualification_recalled_miss_001": ["设立常设服务机构的资格限制"],
        "topic_qualification_partial_miss_001": ["设立常设服务机构的资格限制", "业绩与人员要求被设置为资格门槛"],
        "topic_technical_standard_recalled_miss_001": ["标准名称与编号不一致", "引用已废止标准"],
        "topic_contract_payment_recalled_miss_001": ["付款节点与财政资金到位挂钩", "付款安排以验收裁量为前置条件", "付款节点明显偏后"],
        "topic_scoring_partial_miss_001": ["评分档次缺少量化口径", "主观分值裁量空间过大"],
    }
    for sample_id, titles in expected_titles.items():
        result = evaluate_sample(samples[sample_id])
        for title in titles:
            assert title in result["target_topic_detail"]["risk_titles"]
        assert "risk_not_extracted" in result["target_topic_detail"]["failure_reasons"]


def test_technical_standard_detail_samples_cover_explicit_standard_risk_variants() -> None:
    sample_path = Path("data/examples/v2_topic_eval_samples.json")
    samples = {sample["sample_id"]: sample for sample in load_samples(sample_path)}
    expected_titles = {
        "topic_technical_standard_name_mismatch_002": "标准名称与编号不一致",
        "topic_technical_standard_obsolete_002": "引用已废止标准",
        "topic_technical_standard_method_mismatch_002": "检测方法标准与采购要求不匹配",
    }
    for sample_id, expected_title in expected_titles.items():
        result = evaluate_sample(samples[sample_id])
        assert result["topic_hit_count"] == 1
        assert result["topic_miss_count"] == 0
        assert expected_title in result["target_topic_detail"]["risk_titles"]
        assert "risk_not_extracted" in result["target_topic_detail"]["failure_reasons"]


def test_topic_failure_reasons_are_granular_for_partial_and_degraded_cases() -> None:
    sample_path = Path("data/examples/v2_topic_eval_samples.json")
    samples = {sample["sample_id"]: sample for sample in load_samples(sample_path)}

    partial = evaluate_sample(samples["topic_contract_payment_partial_miss_002"])
    assert "risk_not_extracted" in partial["target_topic_detail"]["failure_reasons"]
    assert "topic_triggered_but_partial_miss" in partial["target_topic_detail"]["failure_reasons"]

    shared = evaluate_sample(samples["topic_scoring_cross_topic_shared_002"])
    assert "评分档次缺少量化口径" in shared["target_topic_detail"]["risk_titles"]
    assert "evidence_enough_but_risk_missed" in shared["target_topic_detail"]["failure_reasons"]
    assert "cross_topic_shared_but_single_topic_hit" in shared["target_topic_detail"]["failure_reasons"]

    degraded = evaluate_sample(samples["topic_scoring_degraded_manual_002"])
    assert "degraded_to_manual_review" in degraded["target_topic_detail"]["failure_reasons"]
    assert "risk_degraded_to_manual_review" in degraded["target_topic_detail"]["failure_reasons"]


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


def test_write_outputs_emits_json_and_markdown(tmp_path: Path) -> None:
    summary = build_summary(
        [
            {
                "name": "a",
                "topic_mode": "default",
                "topic_count": 1,
                "high_medium_expected": 1,
                "high_medium_hit": 1,
                "technical_expected": 0,
                "technical_hit": 0,
                "manual_review_count": 0,
                "topic": "qualification",
                "topic_expected_total": 1,
                "topic_hit_count": 1,
                "topic_miss_count": 0,
                "false_positive_total": 0,
                "false_positive_count": 0,
                "manual_review_expected_total": 0,
                "manual_review_hit": 0,
                "manual_review_false_positive_count": 0,
                "topic_execution_plan": {},
                "details": [],
            }
        ],
        Path("samples.json"),
    )
    write_outputs(tmp_path, summary)
    assert (tmp_path / "topics_eval.json").exists()
    assert (tmp_path / "topics_eval.md").exists()
    assert "# V2 专题层评估结果" in build_markdown_report(summary)


def test_build_summary_aggregates_failure_reasons() -> None:
    summary = build_summary(
        [
            {
                "name": "a",
                "topic_mode": "default",
                "topic_count": 1,
                "high_medium_expected": 0,
                "high_medium_hit": 0,
                "technical_expected": 0,
                "technical_hit": 0,
                "manual_review_count": 1,
                "topic": "scoring",
                "topic_expected_total": 0,
                "topic_hit_count": 0,
                "topic_miss_count": 0,
                "false_positive_total": 0,
                "false_positive_count": 0,
                "manual_review_expected_total": 1,
                "manual_review_hit": 1,
                "manual_review_false_positive_count": 0,
                "topic_execution_plan": {},
                "target_topic_detail": {"failure_reasons": ["missing_evidence"]},
                "details": [{"topic": "scoring", "failure_reasons": ["missing_evidence", "degraded_to_manual_review"]}],
            }
        ],
        Path("samples.json"),
    )
    assert summary["failure_reason_summary"] == {
        "missing_evidence": 1,
        "degraded_to_manual_review": 1,
    }
