from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.common.eval_dataset import DEFAULT_EVAL_ROOT
from scripts.eval_v2_compare import build_summary as build_compare_summary
from scripts.eval_v2_compare import evaluate_sample as evaluate_compare_sample
from scripts.eval_v2_compare import load_samples as load_compare_samples
from scripts.eval_v2_compare import resolve_v2_eval_sample_path as resolve_compare_sample_path
from scripts.eval_v2_regression import build_summary as build_regression_summary
from scripts.eval_v2_regression import evaluate_sample as evaluate_regression_sample
from scripts.eval_v2_regression import load_samples as load_regression_samples
from scripts.eval_v2_regression import resolve_v2_eval_sample_path as resolve_regression_sample_path
from scripts.eval_v2_structure import build_summary as build_structure_summary
from scripts.eval_v2_structure import evaluate_sample as evaluate_structure_sample
from scripts.eval_v2_structure import load_samples as load_structure_samples
from scripts.eval_v2_structure import resolve_v2_eval_sample_path as resolve_structure_sample_path
from scripts.eval_v2_topics import build_summary as build_topics_summary
from scripts.eval_v2_topics import evaluate_sample as evaluate_topics_sample
from scripts.eval_v2_topics import load_samples as load_topics_samples
from scripts.eval_v2_topics import resolve_v2_eval_sample_path as resolve_topics_sample_path


DEFAULT_THRESHOLDS = {
    "structure": {
        "module_accuracy": 0.85,
        "key_recall": 0.95,
        "coverage_recall_rate": 0.95,
        "negative_pass_rate": 0.95,
        "mixed_section_secondary_recall_rate": 0.85,
    },
    "topics": {
        "high_medium_hit_rate": 0.95,
        "topic_hit_rate": 0.95,
        "false_positive_rate_max": 0.10,
        "manual_review_expected_rate": 0.90,
    },
    "compare": {
        "accuracy": 0.95,
    },
    "regression": {
        "structure_hit_rate": 0.80,
        "topic_coverage_hit_rate": 0.80,
        "risk_hit_rate": 0.80,
        "miss_rate_max": 0.20,
    },
}


def _make_check(metric: str, actual: float, target: float, *, comparator: str = ">=") -> dict:
    if comparator == "<=":
        passed = actual <= target
    else:
        passed = actual >= target
    return {
        "metric": metric,
        "actual": actual,
        "target": target,
        "comparator": comparator,
        "passed": passed,
    }


def run_structure_stage(dataset_root: Path | None) -> dict:
    sample_path = resolve_structure_sample_path("structure", dataset_root=dataset_root)
    results = [evaluate_structure_sample(sample) for sample in load_structure_samples(sample_path)]
    summary = build_structure_summary(results, sample_path, use_llm=False)
    thresholds = DEFAULT_THRESHOLDS["structure"]
    checks = [
        _make_check("module_accuracy", float(summary.get("module_accuracy", 0.0)), thresholds["module_accuracy"]),
        _make_check("key_recall", float(summary.get("key_recall", 0.0)), thresholds["key_recall"]),
        _make_check(
            "coverage_recall_rate",
            float(summary.get("coverage_recall_rate", 0.0)),
            thresholds["coverage_recall_rate"],
        ),
        _make_check(
            "negative_pass_rate",
            float(summary.get("negative_pass_rate", 0.0)),
            thresholds["negative_pass_rate"],
        ),
        _make_check(
            "mixed_section_secondary_recall_rate",
            float(summary.get("mixed_section_secondary_recall_rate", 0.0)),
            thresholds["mixed_section_secondary_recall_rate"],
        ),
    ]
    return build_stage_result("structure", summary, checks)


def run_topics_stage(dataset_root: Path | None) -> dict:
    sample_path = resolve_topics_sample_path("topics", dataset_root=dataset_root)
    results = [evaluate_topics_sample(sample) for sample in load_topics_samples(sample_path)]
    summary = build_topics_summary(results, sample_path)
    thresholds = DEFAULT_THRESHOLDS["topics"]
    checks = [
        _make_check(
            "high_medium_hit_rate",
            float(summary.get("high_medium_hit_rate", 0.0)),
            thresholds["high_medium_hit_rate"],
        ),
        _make_check("topic_hit_rate", float(summary.get("topic_hit_rate", 0.0)), thresholds["topic_hit_rate"]),
        _make_check(
            "false_positive_rate",
            float(summary.get("false_positive_rate", 0.0)),
            thresholds["false_positive_rate_max"],
            comparator="<=",
        ),
        _make_check(
            "manual_review_expected_rate",
            float(summary.get("manual_review_expected_rate", 0.0)),
            thresholds["manual_review_expected_rate"],
        ),
    ]
    return build_stage_result("topics", summary, checks)


def run_compare_stage(dataset_root: Path | None) -> dict:
    sample_path = resolve_compare_sample_path("compare", dataset_root=dataset_root)
    results = [evaluate_compare_sample(sample) for sample in load_compare_samples(sample_path)]
    summary = build_compare_summary(results, sample_path)
    checks = [_make_check("accuracy", float(summary.get("accuracy", 0.0)), DEFAULT_THRESHOLDS["compare"]["accuracy"])]
    return build_stage_result("compare", summary, checks)


def run_regression_stage(dataset_root: Path | None) -> dict:
    sample_path = resolve_regression_sample_path("regression", dataset_root=dataset_root)
    results = [evaluate_regression_sample(sample) for sample in load_regression_samples(sample_path)]
    summary = build_regression_summary(results, sample_path)
    thresholds = DEFAULT_THRESHOLDS["regression"]
    checks = [
        _make_check(
            "structure_hit_rate",
            float(summary.get("structure_hit_rate", 0.0)),
            thresholds["structure_hit_rate"],
        ),
        _make_check(
            "topic_coverage_hit_rate",
            float(summary.get("topic_coverage_hit_rate", 0.0)),
            thresholds["topic_coverage_hit_rate"],
        ),
        _make_check("risk_hit_rate", float(summary.get("risk_hit_rate", 0.0)), thresholds["risk_hit_rate"]),
        _make_check("miss_rate", float(summary.get("miss_rate", 0.0)), thresholds["miss_rate_max"], comparator="<="),
    ]
    return build_stage_result("regression", summary, checks)


def build_stage_result(stage: str, summary: dict, checks: list[dict]) -> dict:
    passed_checks = sum(1 for item in checks if item["passed"])
    total_checks = len(checks)
    return {
        "stage": stage,
        "status": "passed" if passed_checks == total_checks else "failed",
        "passed_checks": passed_checks,
        "total_checks": total_checks,
        "check_pass_rate": (passed_checks / total_checks) if total_checks else 1.0,
        "checks": checks,
        "summary": summary,
    }


def build_overall_summary(stage_results: list[dict], dataset_root: Path | None = None) -> dict:
    stage_count = len(stage_results)
    passed_stage_count = sum(1 for item in stage_results if item["status"] == "passed")
    total_checks = sum(int(item["total_checks"]) for item in stage_results)
    passed_checks = sum(int(item["passed_checks"]) for item in stage_results)
    return {
        "dataset_root": str(dataset_root or DEFAULT_EVAL_ROOT),
        "stage_count": stage_count,
        "passed_stage_count": passed_stage_count,
        "stage_pass_rate": (passed_stage_count / stage_count) if stage_count else 1.0,
        "total_checks": total_checks,
        "passed_checks": passed_checks,
        "check_pass_rate": (passed_checks / total_checks) if total_checks else 1.0,
        "status": "passed" if passed_stage_count == stage_count else "failed",
        "stages": stage_results,
    }


def build_markdown_report(summary: dict) -> str:
    lines = [
        "# V2 总评估报告",
        "",
        f"- 数据集目录：`{summary['dataset_root']}`",
        f"- 阶段通过率：`{summary['passed_stage_count']}/{summary['stage_count']} = {summary['stage_pass_rate']:.2%}`",
        f"- 检查项通过率：`{summary['passed_checks']}/{summary['total_checks']} = {summary['check_pass_rate']:.2%}`",
        f"- 总体状态：`{summary['status']}`",
        "",
        "## 分阶段结果",
        "",
    ]
    for stage in summary.get("stages", []):
        lines.extend(
            [
                f"### {stage['stage']}",
                "",
                f"- 状态：`{stage['status']}`",
                f"- 检查项通过率：`{stage['passed_checks']}/{stage['total_checks']} = {stage['check_pass_rate']:.2%}`",
                f"- 样本数：`{stage['summary'].get('sample_count', 0)}`",
                "",
            ]
        )
        for check in stage.get("checks", []):
            comparator_label = "≤" if check["comparator"] == "<=" else "≥"
            lines.append(
                f"- `{check['metric']}`：实际 `{check['actual']:.2%}`，目标 `{comparator_label} {check['target']:.2%}`，结果 `{check['passed']}`"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def write_outputs(output_dir: Path, summary: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "v2_all_eval.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "v2_all_eval.md").write_text(build_markdown_report(summary), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="聚合 V2 结构层、专题层、汇总层、回归层评估并输出总报告。")
    parser.add_argument("--dataset-root", type=Path, default=None, help=f"固定评估数据集目录，默认 {DEFAULT_EVAL_ROOT}")
    parser.add_argument("--output-dir", type=Path, default=None, help="将总评估结果写入指定目录")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON 汇总结果")
    args = parser.parse_args()

    stage_results = [
        run_structure_stage(args.dataset_root),
        run_topics_stage(args.dataset_root),
        run_compare_stage(args.dataset_root),
        run_regression_stage(args.dataset_root),
    ]
    summary = build_overall_summary(stage_results, args.dataset_root)
    if args.output_dir:
        write_outputs(args.output_dir, summary)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(build_markdown_report(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
