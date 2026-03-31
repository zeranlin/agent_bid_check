from __future__ import annotations

import json
from pathlib import Path

from scripts.eval_v2_detail_batch import (
    build_markdown_report,
    build_overall_summary,
    evaluate_detail_batch,
    load_detail_batches,
    write_outputs,
)
from scripts.eval_v2_topics import load_samples as load_topic_samples


def test_load_detail_batches_and_evaluate() -> None:
    batch_specs = load_detail_batches(Path("data/examples/v2_detail_batch_samples.json"))
    topic_samples = load_topic_samples(Path("data/examples/v2_topic_eval_samples.json"))
    topic_index = {sample["sample_id"]: sample for sample in topic_samples}

    assert len(batch_specs) == 4
    result = evaluate_detail_batch(batch_specs[0], topic_index)
    assert result["batch_key"] == "technical_standard"
    assert result["found_sample_count"] == len(batch_specs[0]["sample_ids"])
    assert result["missing_sample_ids"] == []
    assert result["summary"]["sample_count"] == len(batch_specs[0]["sample_ids"])


def test_build_overall_summary_and_markdown() -> None:
    batch_specs = load_detail_batches(Path("data/examples/v2_detail_batch_samples.json"))
    topic_samples = load_topic_samples(Path("data/examples/v2_topic_eval_samples.json"))
    topic_index = {sample["sample_id"]: sample for sample in topic_samples}
    results = [evaluate_detail_batch(batch, topic_index) for batch in batch_specs]

    summary = build_overall_summary(
        results,
        Path("data/examples/v2_detail_batch_samples.json"),
        Path("data/examples/v2_topic_eval_samples.json"),
    )
    assert summary["batch_count"] == 4
    assert summary["sample_count"] == sum(len(batch["sample_ids"]) for batch in batch_specs)
    assert summary["missing_sample_count"] == 0

    report = build_markdown_report(summary)
    assert "# V2 细节风险专项回归批次" in report
    assert "### 标准类细节风险批次" in report
    assert "### 评分类细节风险批次" in report


def test_write_outputs_emits_json_and_markdown(tmp_path: Path) -> None:
    batch_specs = load_detail_batches(Path("data/examples/v2_detail_batch_samples.json"))
    topic_samples = load_topic_samples(Path("data/examples/v2_topic_eval_samples.json"))
    topic_index = {sample["sample_id"]: sample for sample in topic_samples}
    results = [evaluate_detail_batch(batch, topic_index) for batch in batch_specs]
    summary = build_overall_summary(
        results,
        Path("data/examples/v2_detail_batch_samples.json"),
        Path("data/examples/v2_topic_eval_samples.json"),
    )

    write_outputs(tmp_path, summary)
    payload = json.loads((tmp_path / "detail_batch_summary.json").read_text(encoding="utf-8"))
    assert payload["batch_count"] == 4
    assert (tmp_path / "detail_batch_summary.md").exists()
