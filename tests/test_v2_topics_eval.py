from __future__ import annotations

from pathlib import Path

from scripts.eval_v2_topics import build_markdown_report, build_summary, evaluate_sample, load_samples, write_outputs


def test_load_samples_and_evaluate_topic_fixture() -> None:
    sample_path = Path("data/examples/v2_topic_eval_samples.json")
    samples = load_samples(sample_path)
    assert len(samples) >= 47

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


def test_performance_staff_samples_enter_by_topic_summary() -> None:
    sample_path = Path("data/examples/v2_topic_eval_samples.json")
    samples = load_samples(sample_path)
    selected = [
        sample
        for sample in samples
        if sample["sample_id"] in {
            "topic_performance_staff_positive_002",
            "topic_performance_staff_negative_002",
            "topic_performance_staff_manual_002",
            "topic_performance_staff_scoring_overlap_002",
        }
    ]
    results = [evaluate_sample(sample) for sample in selected]
    summary = build_summary(results, sample_path)

    assert "performance_staff" in summary["by_topic"]
    assert summary["by_topic"]["performance_staff"]["sample_count"] == 4
    assert summary["by_topic"]["performance_staff"]["topic_hit_count"] == 2
    assert summary["by_topic"]["performance_staff"]["false_positive_count"] == 0
    assert summary["by_topic"]["performance_staff"]["manual_review_hit"] == 1


def test_policy_and_technical_standard_samples_capture_import_policy_and_foreign_standard_signals() -> None:
    sample_path = Path("data/examples/v2_topic_eval_samples.json")
    samples = {sample["sample_id"]: sample for sample in load_samples(sample_path)}

    positive = evaluate_sample(samples["topic_policy_technical_import_conflict_a_003"])
    positive_details = {detail["topic"]: detail for detail in positive["details"]}
    assert positive_details["policy"]["structured_signals"]["import_policy"] == "reject_import"
    assert positive["target_topic_detail"]["structured_signals"]["foreign_standard_refs"] == ["BS EN 61000", "EN55011"]
    assert positive["target_topic_detail"]["structured_signals"]["has_equivalent_standard_clause"] is False
    assert "foreign_standard_conflict" in positive["target_topic_detail"]["failure_reasons"]

    negative = evaluate_sample(samples["topic_policy_technical_import_conflict_c_003"])
    negative_details = {detail["topic"]: detail for detail in negative["details"]}
    assert negative_details["policy"]["structured_signals"]["import_policy"] == "reject_import"
    assert "GB/T 17626" in negative["target_topic_detail"]["structured_signals"]["cn_standard_refs"][0]
    assert negative["target_topic_detail"]["structured_signals"]["has_equivalent_standard_clause"] is True
    assert "foreign_standard_conflict" not in negative["target_topic_detail"]["failure_reasons"]


def test_real_like_technical_parameter_samples_capture_foreign_standard_and_background_boundaries() -> None:
    sample_path = Path("data/examples/v2_topic_eval_samples.json")
    samples = {sample["sample_id"]: sample for sample in load_samples(sample_path)}

    positive = evaluate_sample(samples["topic_technical_standard_parameter_import_conflict_real_004"])
    assert positive["target_topic_detail"]["structured_signals"]["foreign_standard_refs"] == ["BS EN 61000", "EN55011"]
    assert "GB/T 17626" in positive["target_topic_detail"]["structured_signals"]["cn_standard_refs"]
    assert positive["target_topic_detail"]["structured_signals"]["has_equivalent_standard_clause"] is False

    equivalent_negative = evaluate_sample(samples["topic_technical_standard_parameter_equivalent_negative_004"])
    assert equivalent_negative["target_topic_detail"]["structured_signals"]["has_equivalent_standard_clause"] is True
    assert "foreign_standard_conflict" not in equivalent_negative["target_topic_detail"]["failure_reasons"]

    background_negative = evaluate_sample(samples["topic_technical_standard_background_negative_004"])
    assert background_negative["target_topic_detail"]["structured_signals"]["foreign_standard_refs"] == []
    assert background_negative["target_topic_detail"]["structured_signals"]["cn_standard_refs"] == ["GB/T 17626"]
    assert "foreign_standard_conflict" not in background_negative["target_topic_detail"]["failure_reasons"]


def test_scoring_star_rule_and_technical_star_marker_signals_are_extracted_correctly() -> None:
    sample_path = Path("data/examples/v2_topic_eval_samples.json")
    samples = {sample["sample_id"]: sample for sample in load_samples(sample_path)}

    scoring_rule = evaluate_sample(samples["topic_scoring_star_rule_positive_005"])
    assert scoring_rule["target_topic_detail"]["structured_signals"]["star_required_for_gb_non_t"] is True
    assert scoring_rule["target_topic_detail"]["structured_signals"]["star_required_for_mandatory_standard"] is True

    gb_positive = evaluate_sample(samples["topic_technical_standard_star_clause_positive_005"])
    clause = gb_positive["target_topic_detail"]["structured_signals"]["standard_clause_flags"][0]
    assert clause["contains_gb_non_t"] is True
    assert clause["contains_gbt"] is False
    assert clause["has_star_marker"] is False

    gbt_negative = evaluate_sample(samples["topic_technical_standard_star_clause_negative_gbt_005"])
    negative_clause = gbt_negative["target_topic_detail"]["structured_signals"]["standard_clause_flags"][0]
    assert negative_clause["contains_gb_non_t"] is False
    assert negative_clause["contains_gbt"] is True

    starred_negative = evaluate_sample(samples["topic_technical_standard_star_clause_negative_starred_005"])
    starred_clause = starred_negative["target_topic_detail"]["structured_signals"]["standard_clause_flags"][0]
    assert starred_clause["contains_gb_non_t"] is True
    assert starred_clause["has_star_marker"] is True


def test_scoring_acceptance_plan_rule_and_scoring_signals_are_extracted_correctly() -> None:
    sample_path = Path("data/examples/v2_topic_eval_samples.json")
    samples = {sample["sample_id"]: sample for sample in load_samples(sample_path)}

    rule_sample = evaluate_sample(samples["topic_scoring_acceptance_plan_rule_positive_006"])
    rule_signals = rule_sample["target_topic_detail"]["structured_signals"]
    assert rule_signals["acceptance_plan_forbidden_in_scoring"] is True
    assert "不得将项目验收方案作为评审因素" in rule_signals["acceptance_plan_rule_sentences"][0]

    scoring_positive = evaluate_sample(samples["topic_scoring_acceptance_plan_scoring_positive_006"])
    positive_signals = scoring_positive["target_topic_detail"]["structured_signals"]
    assert positive_signals["scoring_contains_acceptance_plan"] is True
    assert positive_signals["acceptance_plan_linked_to_score"] is True
    assert any("项目验收移交衔接方案" in item for item in positive_signals["acceptance_plan_scoring_sentences"])
    assert any("最高得30分" in item for item in positive_signals["acceptance_plan_scoring_sentences"])

    negative = evaluate_sample(samples["topic_scoring_acceptance_plan_negative_contract_only_006"])
    negative_signals = negative["target_topic_detail"]["structured_signals"]
    assert negative_signals["acceptance_plan_forbidden_in_scoring"] is False
    assert negative_signals["scoring_contains_acceptance_plan"] is False
    assert negative_signals["acceptance_plan_linked_to_score"] is False

    strong_positive = evaluate_sample(samples["topic_scoring_acceptance_plan_scoring_strong_positive_006a"])
    strong_signals = strong_positive["target_topic_detail"]["structured_signals"]
    assert strong_signals["acceptance_plan_forbidden_in_scoring"] is True
    assert strong_signals["scoring_contains_acceptance_plan"] is True
    assert strong_signals["acceptance_plan_linked_to_score"] is True
    assert any("项目验收方案设计" in item for item in strong_signals["acceptance_plan_scoring_sentences"])
    assert any("验收标准" in item for item in strong_signals["acceptance_plan_scoring_sentences"])
    assert any("验收流程安排" in item for item in strong_signals["acceptance_plan_scoring_sentences"])
    assert any("验收资料准备节点" in item for item in strong_signals["acceptance_plan_scoring_sentences"])
    assert any("项目验收组织能力" in item for item in strong_signals["acceptance_plan_scoring_sentences"])
    assert any("评价为优得60分" in item for item in strong_signals["acceptance_plan_scoring_sentences"])

    training_negative = evaluate_sample(samples["topic_scoring_acceptance_plan_negative_implementation_only_006a"])
    training_negative_signals = training_negative["target_topic_detail"]["structured_signals"]
    assert training_negative_signals["scoring_contains_acceptance_plan"] is False
    assert training_negative_signals["acceptance_plan_linked_to_score"] is False


def test_scoring_payment_terms_rule_and_scoring_signals_are_extracted_correctly() -> None:
    sample_path = Path("data/examples/v2_topic_eval_samples.json")
    samples = {sample["sample_id"]: sample for sample in load_samples(sample_path)}

    rule_sample = evaluate_sample(samples["topic_scoring_payment_terms_rule_positive_007"])
    rule_signals = rule_sample["target_topic_detail"]["structured_signals"]
    assert rule_signals["payment_terms_forbidden_in_scoring"] is True
    assert "不得将付款方式作为评审因素" in rule_signals["payment_terms_rule_sentences"][0]

    positive = evaluate_sample(samples["topic_scoring_payment_terms_scoring_positive_007"])
    positive_signals = positive["target_topic_detail"]["structured_signals"]
    assert positive_signals["scoring_contains_payment_terms"] is True
    assert positive_signals["payment_terms_linked_to_score"] is True
    assert any("付款周期短于招标文件要求" in item for item in positive_signals["payment_terms_scoring_sentences"])
    assert any("预付款比例更有利于采购人资金安排" in item for item in positive_signals["payment_terms_scoring_sentences"])
    assert any("每项加10分" in item for item in positive_signals["payment_terms_scoring_sentences"])
    assert any("最高加20分" in item for item in positive_signals["payment_terms_scoring_sentences"])

    contract_negative = evaluate_sample(samples["topic_scoring_payment_terms_negative_contract_only_007"])
    contract_negative_signals = contract_negative["target_topic_detail"]["structured_signals"]
    assert contract_negative_signals["scoring_contains_payment_terms"] is False
    assert contract_negative_signals["payment_terms_linked_to_score"] is False


def test_qualification_cancelled_or_non_mandatory_qualification_signals_are_extracted_correctly() -> None:
    sample_path = Path("data/examples/v2_topic_eval_samples.json")
    samples = {sample["sample_id"]: sample for sample in load_samples(sample_path)}

    positive = evaluate_sample(samples["topic_qualification_cancelled_or_non_mandatory_positive_009"])
    positive_signals = positive["target_topic_detail"]["structured_signals"]
    assert positive_signals["qualification_requirement_present"] is True
    assert positive_signals["cancelled_or_non_mandatory_qualification_signal"] is True
    assert positive_signals["cancelled_or_non_mandatory_qualification_used_as_gate"] is True
    assert any(("已明令取消" in item) or ("非强制" in item) for item in positive_signals["cancelled_or_non_mandatory_qualification_sentences"])

    candidate_expression = evaluate_sample(samples["topic_qualification_cancelled_or_non_mandatory_candidate_expression_009"])
    candidate_signals = candidate_expression["target_topic_detail"]["structured_signals"]
    assert candidate_signals["qualification_requirement_present"] is True
    assert candidate_signals["cancelled_or_non_mandatory_qualification_signal"] is True
    assert candidate_signals["cancelled_or_non_mandatory_qualification_used_as_gate"] is True
    assert candidate_signals["cancelled_or_non_mandatory_qualification_prohibition_context"] is True

    negative = evaluate_sample(samples["topic_qualification_cancelled_or_non_mandatory_negative_legal_009"])
    negative_signals = negative["target_topic_detail"]["structured_signals"]
    assert negative_signals["qualification_requirement_present"] is True
    assert negative_signals["cancelled_or_non_mandatory_qualification_signal"] is False
    assert negative_signals["cancelled_or_non_mandatory_qualification_used_as_gate"] is False

    capability_negative = evaluate_sample(samples["topic_scoring_payment_terms_negative_capability_only_007"])
    capability_negative_signals = capability_negative["target_topic_detail"]["structured_signals"]
    assert capability_negative_signals["scoring_contains_payment_terms"] is False
    assert capability_negative_signals["payment_terms_linked_to_score"] is False


def test_scoring_gifts_rule_and_scoring_signals_are_extracted_correctly() -> None:
    sample_path = Path("data/examples/v2_topic_eval_samples.json")
    samples = {sample["sample_id"]: sample for sample in load_samples(sample_path)}

    rule_sample = evaluate_sample(samples["topic_scoring_gifts_rule_positive_008"])
    rule_signals = rule_sample["target_topic_detail"]["structured_signals"]
    assert rule_signals["gifts_or_unrelated_goods_forbidden_in_scoring"] is True
    assert "不得要求提供赠品" in rule_signals["gifts_or_goods_rule_sentences"][0]

    positive = evaluate_sample(samples["topic_scoring_gifts_scoring_positive_008"])
    positive_signals = positive["target_topic_detail"]["structured_signals"]
    assert positive_signals["scoring_contains_gifts_or_unrelated_goods"] is True
    assert positive_signals["gifts_or_goods_linked_to_score"] is True
    assert any("赠送台式电脑" in item for item in positive_signals["gifts_or_goods_scoring_sentences"])
    assert any("打印机" in item for item in positive_signals["gifts_or_goods_scoring_sentences"])
    assert any("得100分" in item for item in positive_signals["gifts_or_goods_scoring_sentences"])

    service_negative = evaluate_sample(samples["topic_scoring_gifts_negative_service_only_008"])
    service_negative_signals = service_negative["target_topic_detail"]["structured_signals"]
    assert service_negative_signals["scoring_contains_gifts_or_unrelated_goods"] is False
    assert service_negative_signals["gifts_or_goods_linked_to_score"] is False

    subject_negative = evaluate_sample(samples["topic_scoring_gifts_negative_procurement_subject_008"])
    subject_negative_signals = subject_negative["target_topic_detail"]["structured_signals"]
    assert subject_negative_signals["scoring_contains_gifts_or_unrelated_goods"] is False
    assert subject_negative_signals["gifts_or_goods_linked_to_score"] is False

    accessories_negative = evaluate_sample(samples["topic_scoring_gifts_negative_necessary_accessories_008"])
    accessories_negative_signals = accessories_negative["target_topic_detail"]["structured_signals"]
    assert accessories_negative_signals["scoring_contains_gifts_or_unrelated_goods"] is False
    assert accessories_negative_signals["gifts_or_goods_linked_to_score"] is False

    hidden_positive = evaluate_sample(samples["topic_scoring_gifts_hidden_positive_008"])
    hidden_positive_signals = hidden_positive["target_topic_detail"]["structured_signals"]
    assert hidden_positive_signals["scoring_contains_gifts_or_unrelated_goods"] is True
    assert hidden_positive_signals["gifts_or_goods_linked_to_score"] is True
    assert any("值班室办公设备配置" in item for item in hidden_positive_signals["gifts_or_goods_scoring_sentences"])
    assert any("会议保障等综合服务内容" in item for item in hidden_positive_signals["gifts_or_goods_scoring_sentences"])


def test_scoring_specific_cert_or_supplier_rule_and_scoring_signals_are_extracted_correctly() -> None:
    sample_path = Path("data/examples/v2_topic_eval_samples.json")
    samples = {sample["sample_id"]: sample for sample in load_samples(sample_path)}

    rule_sample = evaluate_sample(samples["topic_scoring_specific_cert_rule_positive_009"])
    rule_signals = rule_sample["target_topic_detail"]["structured_signals"]
    assert rule_signals["specific_brand_or_supplier_forbidden_in_scoring"] is True
    assert "不得限定或者指定特定的专利" in rule_signals["specific_brand_or_supplier_rule_sentences"][0]

    positive = evaluate_sample(samples["topic_scoring_specific_cert_positive_009"])
    positive_signals = positive["target_topic_detail"]["structured_signals"]
    assert positive_signals["scoring_contains_specific_cert_or_supplier_signal"] is True
    assert positive_signals["specific_cert_or_supplier_score_linked"] is True
    assert any("制造商" in item for item in positive_signals["specific_cert_or_supplier_evidence"])
    assert any("采用国际标准产品确认证书" in item for item in positive_signals["specific_cert_or_supplier_evidence"])
    assert any("CNAS中国认可产品标志证书" in item for item in positive_signals["specific_cert_or_supplier_evidence"])

    negative = evaluate_sample(samples["topic_scoring_specific_cert_negative_generic_proof_009"])
    negative_signals = negative["target_topic_detail"]["structured_signals"]
    assert negative_signals["scoring_contains_specific_cert_or_supplier_signal"] is False
    assert negative_signals["specific_cert_or_supplier_score_linked"] is False


def test_acceptance_testing_cost_rule_and_demand_signals_are_extracted_correctly() -> None:
    sample_path = Path("data/examples/v2_topic_eval_samples.json")
    samples = {sample["sample_id"]: sample for sample in load_samples(sample_path)}

    rule_sample = evaluate_sample(samples["topic_acceptance_testing_cost_rule_positive_010"])
    rule_signals = rule_sample["target_topic_detail"]["structured_signals"]
    assert rule_signals["acceptance_testing_cost_forbidden_to_bidder"] is True
    assert "不得要求中标人承担验收产生的检测费用" in rule_signals["acceptance_testing_cost_rule_sentences"][0]

    positive = evaluate_sample(samples["topic_acceptance_testing_cost_positive_010"])
    positive_signals = positive["target_topic_detail"]["structured_signals"]
    assert positive_signals["demand_contains_acceptance_testing_cost_signal"] is True
    assert positive_signals["acceptance_testing_cost_shifted_to_bidder"] is True
    assert any("相关部门验收" in item for item in positive_signals["acceptance_testing_cost_evidence"])
    assert any("一切费用" in item for item in positive_signals["acceptance_testing_cost_evidence"])

    negative = evaluate_sample(samples["topic_acceptance_testing_cost_negative_selfcheck_010"])
    negative_signals = negative["target_topic_detail"]["structured_signals"]
    assert negative_signals["demand_contains_acceptance_testing_cost_signal"] is False
    assert negative_signals["acceptance_testing_cost_shifted_to_bidder"] is False


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
