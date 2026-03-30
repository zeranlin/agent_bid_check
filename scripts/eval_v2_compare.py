from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.common.schemas import RiskPoint
from app.config import PROJECT_ROOT as APP_PROJECT_ROOT
from app.pipelines.v2.compare import compare_review_artifacts
from app.pipelines.v2.schemas import TopicReviewArtifact, V2StageArtifact


DEFAULT_SAMPLE_PATH = APP_PROJECT_ROOT / "data" / "examples" / "v2_compare_eval_samples.json"


def load_samples(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("评估样本文件必须是数组。")
    return [item for item in data if isinstance(item, dict)]


def _build_topic(topic_payload: dict) -> TopicReviewArtifact:
    risks: list[RiskPoint] = []
    for item in topic_payload.get("risk_points", []):
        if isinstance(item, dict):
            risks.append(
                RiskPoint(
                    title=str(item.get("title", "")),
                    severity=str(item.get("severity", "需人工复核")),
                    review_type=str(item.get("review_type", "未发现")),
                    source_location=str(item.get("source_location", "未发现")),
                    source_excerpt=str(item.get("source_excerpt", "未发现")),
                    risk_judgment=[str(v) for v in item.get("risk_judgment", ["需人工复核"])],
                    legal_basis=[str(v) for v in item.get("legal_basis", ["需人工复核"])],
                    rectification=[str(v) for v in item.get("rectification", ["未发现"])],
                )
            )
    return TopicReviewArtifact(
        topic=str(topic_payload.get("topic", "unknown")),
        summary=str(topic_payload.get("summary", "")),
        risk_points=risks,
        need_manual_review=bool(topic_payload.get("need_manual_review", False)),
        coverage_note=str(topic_payload.get("coverage_note", "")),
        metadata=topic_payload.get("metadata", {}) if isinstance(topic_payload.get("metadata", {}), dict) else {},
    )


def evaluate_sample(sample: dict) -> dict:
    baseline = V2StageArtifact(name="baseline", content=str(sample.get("baseline_markdown", "")))
    topics = [_build_topic(item) for item in sample.get("topics", []) if isinstance(item, dict)]
    comparison = compare_review_artifacts(str(sample.get("name", "sample")), baseline, topics)
    expected = sample.get("expected", {})

    actual = {
        "cluster_count": len(comparison.clusters),
        "conflict_count": len(comparison.conflicts),
        "duplicate_reduction": int(comparison.comparison_summary.get("duplicate_reduction", 0)),
        "baseline_only_count": len(comparison.baseline_only_risks),
        "topic_only_count": len(comparison.topic_only_risks),
        "coverage_gap_count": len(comparison.coverage_gaps),
    }
    matched_metrics = 0
    total_metrics = 0
    details: list[dict[str, object]] = []
    for key, expected_value in expected.items():
        total_metrics += 1
        actual_value = actual.get(key)
        ok = actual_value == expected_value
        if ok:
            matched_metrics += 1
        details.append({"metric": key, "expected": expected_value, "actual": actual_value, "matched": ok})

    return {
        "name": str(sample.get("name", "sample")),
        "matched_metrics": matched_metrics,
        "total_metrics": total_metrics,
        "accuracy": (matched_metrics / total_metrics) if total_metrics else 0.0,
        "actual": actual,
        "details": details,
    }


def build_summary(results: list[dict], sample_path: Path) -> dict:
    matched_metrics = sum(int(item["matched_metrics"]) for item in results)
    total_metrics = sum(int(item["total_metrics"]) for item in results)
    return {
        "sample_path": str(sample_path),
        "sample_count": len(results),
        "matched_metrics": matched_metrics,
        "total_metrics": total_metrics,
        "accuracy": (matched_metrics / total_metrics) if total_metrics else 0.0,
        "samples": results,
    }


def print_report(summary: dict) -> None:
    print("V2 汇总层评估结果")
    print(f"样本文件: {summary['sample_path']}")
    print(f"样本数: {summary['sample_count']}")
    print(f"聚类/冲突/去重指标命中率: {summary['matched_metrics']}/{summary['total_metrics']} = {summary['accuracy']:.2%}")
    print("")
    for sample in summary["samples"]:
        print(f"[{sample['name']}] {sample['matched_metrics']}/{sample['total_metrics']} = {sample['accuracy']:.2%}")
        for detail in sample["details"]:
            print(
                f"  - {detail['metric']}: expected={detail['expected']} actual={detail['actual']} matched={detail['matched']}"
            )
        print("")


def main() -> int:
    parser = argparse.ArgumentParser(description="评估 V2 汇总层的聚类、冲突和覆盖分析表现。")
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLE_PATH, help="评估样本 JSON 路径")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON 汇总结果")
    args = parser.parse_args()

    results = [evaluate_sample(sample) for sample in load_samples(args.samples)]
    summary = build_summary(results, args.samples)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print_report(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
