from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.pipelines.v2.schemas import V2StageArtifact
from scripts.eval_v2_structure import build_markdown_report, build_summary, evaluate_sample, load_samples, write_outputs


def test_load_samples_and_evaluate_structure_fixture() -> None:
    sample_path = Path("data/examples/v2_structure_eval_samples.json")
    samples = load_samples(sample_path)
    assert len(samples) >= 44

    result = evaluate_sample(samples[0], use_llm=False)
    assert result["module_total"] >= 2
    assert 0.0 <= result["module_accuracy"] <= 1.0
    assert 0.0 <= result["key_recall"] <= 1.0
    assert 0.0 <= result["coverage_recall_rate"] <= 1.0
    assert 0.0 <= result["negative_pass_rate"] <= 1.0
    assert 0.0 <= result["secondary_recall_rate"] <= 1.0
    assert result["structure_llm_used"] is False
    assert result["name"] == samples[0]["sample_id"]
    assert result["document_name"] == samples[0]["document_name"]
    assert "negative_details" in result
    assert "coverage_details" in result


def test_build_summary_aggregates_metrics() -> None:
    results = [
        {
            "name": "a",
            "module_total": 2,
            "module_correct": 2,
            "key_total": 2,
            "key_hit": 1,
            "negative_total": 2,
            "negative_pass_count": 1,
            "coverage_total": 3,
            "coverage_pass_count": 2,
            "secondary_total": 2,
            "secondary_hit": 1,
            "structure_llm_used": False,
            "structure_fallback_used": False,
            "coverage_details": [
                {"topic": "scoring", "passed": False, "failure_reasons": ["missing_modules"]},
                {"topic": "qualification", "passed": True, "failure_reasons": []},
            ],
            "details": [],
        },
        {
            "name": "b",
            "module_total": 2,
            "module_correct": 1,
            "key_total": 1,
            "key_hit": 1,
            "negative_total": 1,
            "negative_pass_count": 1,
            "coverage_total": 1,
            "coverage_pass_count": 1,
            "secondary_total": 1,
            "secondary_hit": 1,
            "structure_llm_used": True,
            "structure_fallback_used": True,
            "coverage_details": [
                {"topic": "procedure", "passed": False, "failure_reasons": ["primary_order_mismatch"]},
            ],
            "details": [],
        },
    ]
    summary = build_summary(results, Path("samples.json"), use_llm=False)
    assert summary["module_accuracy"] == 0.75
    assert summary["key_recall"] == 2 / 3
    assert summary["negative_pass_rate"] == 2 / 3
    assert summary["coverage_recall_rate"] == 3 / 4
    assert summary["mixed_section_secondary_recall_rate"] == 2 / 3
    assert summary["llm_used_count"] == 1
    assert summary["fallback_count"] == 1
    assert summary["topic_failure_summary"] == {"scoring": 1, "procedure": 1}
    assert summary["failure_reason_summary"] == {"missing_modules": 1, "primary_order_mismatch": 1}


def test_evaluate_sample_emits_negative_and_coverage_failures() -> None:
    sample = {
        "sample_id": "structure_test_failure_001",
        "document_name": "失败细节样本",
        "text": "第一章 资格及评分要求\n内容",
        "expected_sections": [
            {
                "title": "第一章 资格及评分要求",
                "module": "qualification",
                "secondary_modules": ["scoring"],
                "key": True,
            }
        ],
        "must_not_primary_modules": {
            "第一章 资格及评分要求": ["qualification"]
        },
        "coverage_expectations": [
            {
                "topic": "scoring",
                "required_modules": ["qualification", "scoring"],
                "required_section_titles": ["第一章 资格及评分要求"],
                "min_sections": 1,
                "expected_primary_titles": ["第一章 资格及评分要求"],
                "expected_shared_topics": ["qualification"],
                "expected_shared_titles": ["第一章 资格及评分要求"],
            }
        ],
    }
    structure_artifact = V2StageArtifact(
        name="structure",
        metadata={
            "sections": [
                {
                    "title": "第一章 资格及评分要求",
                    "start_line": 1,
                    "end_line": 3,
                    "module": "qualification",
                }
            ],
            "structure_llm_used": False,
            "structure_fallback_used": False,
        },
    )
    evidence_artifact = V2StageArtifact(
        name="evidence",
        metadata={
            "topic_evidence_bundles": {
                "scoring": {
                    "sections": [
                        {
                            "title": "第一章 资格及评分要求",
                            "start_line": 1,
                            "end_line": 3,
                            "module": "qualification",
                        }
                    ],
                    "primary_section_ids": [],
                    "secondary_section_ids": ["1-3"],
                },
                "qualification": {
                    "sections": [],
                    "primary_section_ids": [],
                    "secondary_section_ids": [],
                },
            }
        },
    )

    with patch("scripts.eval_v2_structure.build_structure_map", return_value=structure_artifact), patch(
        "scripts.eval_v2_structure.build_evidence_map",
        return_value=evidence_artifact,
    ):
        result = evaluate_sample(sample, use_llm=False)

    assert result["negative_pass_rate"] == 0.0
    assert result["coverage_recall_rate"] == 0.0
    assert result["secondary_recall_rate"] == 0.0
    assert result["negative_details"][0]["passed"] is False
    assert set(result["coverage_details"][0]["failure_reasons"]) == {
        "missing_modules",
        "primary_order_mismatch",
        "shared_topic_unstable",
    }
    assert result["secondary_details"][0]["passed"] is False


def test_write_outputs_emits_json_and_markdown(tmp_path: Path) -> None:
    summary = build_summary(
        [
            {
                "name": "a",
                "module_total": 1,
                "module_correct": 1,
                "key_total": 1,
                "key_hit": 1,
                "negative_total": 0,
                "negative_pass_count": 0,
                "coverage_total": 1,
                "coverage_pass_count": 1,
                "secondary_total": 0,
                "secondary_hit": 0,
                "structure_llm_used": False,
                "structure_fallback_used": False,
                "coverage_details": [],
                "details": [],
            }
        ],
        Path("samples.json"),
        use_llm=False,
    )
    write_outputs(tmp_path, summary)
    assert (tmp_path / "structure_eval.json").exists()
    assert (tmp_path / "structure_eval.md").exists()
    markdown = build_markdown_report(summary)
    assert "# V2 结构层评估结果" in markdown
