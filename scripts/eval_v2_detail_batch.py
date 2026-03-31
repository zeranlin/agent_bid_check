from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import PROJECT_ROOT as APP_PROJECT_ROOT
from scripts.eval_v2_topics import build_summary as build_topics_summary
from scripts.eval_v2_topics import evaluate_sample as evaluate_topic_sample
from scripts.eval_v2_topics import load_samples as load_topic_samples


DEFAULT_TOPIC_SAMPLE_PATH = APP_PROJECT_ROOT / "data" / "examples" / "v2_topic_eval_samples.json"
DEFAULT_BATCH_SAMPLE_PATH = APP_PROJECT_ROOT / "data" / "examples" / "v2_detail_batch_samples.json"


def load_detail_batches(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("细节风险批次文件必须是数组。")
    return [item for item in payload if isinstance(item, dict)]


def _index_topic_samples(samples: list[dict]) -> dict[str, dict]:
    indexed: dict[str, dict] = {}
    for sample in samples:
        sample_id = str(sample.get("sample_id", "")).strip()
        if sample_id:
            indexed[sample_id] = sample
    return indexed


def evaluate_detail_batch(batch: dict, topic_index: dict[str, dict]) -> dict:
    sample_ids = [str(item).strip() for item in batch.get("sample_ids", []) if str(item).strip()]
    selected_samples = [topic_index[sample_id] for sample_id in sample_ids if sample_id in topic_index]
    missing_sample_ids = [sample_id for sample_id in sample_ids if sample_id not in topic_index]
    results = [evaluate_topic_sample(sample) for sample in selected_samples]
    summary = build_topics_summary(results, Path(f"detail-batch:{batch.get('batch_key', 'unknown')}"))
    return {
        "batch_key": str(batch.get("batch_key", "")).strip(),
        "label": str(batch.get("label", "")).strip(),
        "topic": str(batch.get("topic", "")).strip(),
        "sample_ids": sample_ids,
        "found_sample_count": len(selected_samples),
        "missing_sample_ids": missing_sample_ids,
        "summary": summary,
    }


def build_overall_summary(batch_results: list[dict], batch_path: Path, topic_sample_path: Path) -> dict:
    total_expected = 0
    total_hits = 0
    total_false_positive_total = 0
    total_false_positive_count = 0
    total_manual_expected = 0
    total_manual_hit = 0
    total_sample_count = 0
    total_missing_samples = 0
    for result in batch_results:
        summary = result.get("summary", {})
        total_expected += int(summary.get("topic_expected_total", 0))
        total_hits += int(summary.get("topic_hit_count", 0))
        total_false_positive_total += int(summary.get("false_positive_total", 0))
        total_false_positive_count += int(summary.get("false_positive_count", 0))
        total_manual_expected += int(summary.get("manual_review_expected_total", 0))
        total_manual_hit += int(summary.get("manual_review_hit", 0))
        total_sample_count += int(summary.get("sample_count", 0))
        total_missing_samples += len(result.get("missing_sample_ids", []))

    return {
        "batch_path": str(batch_path),
        "topic_sample_path": str(topic_sample_path),
        "batch_count": len(batch_results),
        "sample_count": total_sample_count,
        "topic_hit_rate": (total_hits / total_expected) if total_expected else 1.0,
        "topic_miss_rate": ((total_expected - total_hits) / total_expected) if total_expected else 0.0,
        "false_positive_rate": (
            total_false_positive_count / total_false_positive_total if total_false_positive_total else 0.0
        ),
        "manual_review_expected_rate": (
            total_manual_hit / total_manual_expected if total_manual_expected else 1.0
        ),
        "missing_sample_count": total_missing_samples,
        "batches": batch_results,
    }


def build_markdown_report(summary: dict) -> str:
    lines = [
        "# V2 细节风险专项回归批次",
        "",
        f"- 批次配置：`{summary['batch_path']}`",
        f"- 专题样本：`{summary['topic_sample_path']}`",
        f"- 批次数：`{summary['batch_count']}`",
        f"- 样本数：`{summary['sample_count']}`",
        f"- 总体命中率：`{summary['topic_hit_rate']:.2%}`",
        f"- 总体漏检率：`{summary['topic_miss_rate']:.2%}`",
        f"- 总体误报率：`{summary['false_positive_rate']:.2%}`",
        f"- 人工复核合理率：`{summary['manual_review_expected_rate']:.2%}`",
        f"- 缺失样本数：`{summary['missing_sample_count']}`",
        "",
        "## 分批结果",
        "",
    ]
    for batch in summary.get("batches", []):
        item = batch.get("summary", {})
        lines.extend(
            [
                f"### {batch.get('label', batch.get('batch_key', 'unknown'))}",
                "",
                f"- 批次键：`{batch.get('batch_key', 'unknown')}`",
                f"- 专题：`{batch.get('topic', 'unknown')}`",
                f"- 样本数：`{item.get('sample_count', 0)}`",
                f"- 命中率：`{item.get('topic_hit_rate', 0.0):.2%}`",
                f"- 漏检率：`{item.get('topic_miss_rate', 0.0):.2%}`",
                f"- 误报率：`{item.get('false_positive_rate', 0.0):.2%}`",
                f"- 人工复核合理率：`{item.get('manual_review_expected_rate', 0.0):.2%}`",
                f"- 失败原因分布：`{item.get('failure_reason_summary', {})}`",
                f"- 缺失样本：`{batch.get('missing_sample_ids', [])}`",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def write_outputs(output_dir: Path, summary: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "detail_batch_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "detail_batch_summary.md").write_text(build_markdown_report(summary), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="执行 V2 细节风险专项回归批次。")
    parser.add_argument("--batch-samples", type=Path, default=DEFAULT_BATCH_SAMPLE_PATH, help="细节风险批次配置")
    parser.add_argument("--topic-samples", type=Path, default=DEFAULT_TOPIC_SAMPLE_PATH, help="专题层样本文件")
    parser.add_argument("--output-dir", type=Path, help="输出目录")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON 摘要")
    args = parser.parse_args()

    topic_samples = load_topic_samples(args.topic_samples)
    batch_specs = load_detail_batches(args.batch_samples)
    topic_index = _index_topic_samples(topic_samples)
    batch_results = [evaluate_detail_batch(batch, topic_index) for batch in batch_specs]
    summary = build_overall_summary(batch_results, args.batch_samples, args.topic_samples)

    if args.output_dir:
        write_outputs(args.output_dir, summary)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(build_markdown_report(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
