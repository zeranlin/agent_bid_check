from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import PROJECT_ROOT as APP_PROJECT_ROOT, ReviewSettings
from app.common.eval_dataset import DEFAULT_EVAL_ROOT, resolve_v2_eval_sample_path
from app.common.markdown_utils import parse_review_markdown
from app.common.schemas import RiskPoint
from app.pipelines.v2.baseline import run_baseline_review


DEFAULT_SAMPLE_PATH = APP_PROJECT_ROOT / "data" / "examples" / "v2_baseline_eval_samples.json"
SUMMARY_ONLY_MARKERS = ("审查综述", "总体结论", "总体判断", "综合结论", "风险概览")


def load_samples(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("评估样本文件必须是数组。")
    return [item for item in data if isinstance(item, dict)]


def _normalize_text(text: str) -> str:
    return "".join(str(text).split()).lower()


def _contains_any_keyword(text: str, keywords: list[str]) -> bool:
    normalized = _normalize_text(text)
    return any(_normalize_text(keyword) in normalized for keyword in keywords if str(keyword).strip())


def _matches_expected(expected: dict, risk: RiskPoint) -> bool:
    title_keywords = [str(item).strip() for item in expected.get("title_keywords", []) if str(item).strip()]
    review_type_keywords = [str(item).strip() for item in expected.get("review_type_keywords", []) if str(item).strip()]
    severity_allowed = [str(item).strip() for item in expected.get("severity_allowed", []) if str(item).strip()]

    title_ok = True if not title_keywords else _contains_any_keyword(risk.title, title_keywords)
    review_type_ok = True if not review_type_keywords else _contains_any_keyword(risk.review_type, review_type_keywords)
    severity_ok = True if not severity_allowed else risk.severity in severity_allowed
    return title_ok and review_type_ok and severity_ok


def _find_match(expected: dict, risks: list[RiskPoint]) -> RiskPoint | None:
    for risk in risks:
        if _matches_expected(expected, risk):
            return risk
    return None


def _run_baseline(sample: dict, settings: ReviewSettings) -> tuple[list[RiskPoint], str]:
    text = str(sample.get("text", ""))
    sample_id = str(sample.get("sample_id", "sample"))
    with tempfile.TemporaryDirectory(prefix="v2-baseline-eval-") as tmpdir:
        input_path = Path(tmpdir) / f"{sample_id}.txt"
        input_path.write_text(text, encoding="utf-8")
        artifact = run_baseline_review(input_path=input_path, settings=settings)
        report = parse_review_markdown(artifact.content)
        return report.risk_points, artifact.content


def _is_missing_text(value: str) -> bool:
    normalized = str(value or "").strip()
    return normalized in {"", "未发现", "需人工复核"}


def _evaluate_report_quality(sample: dict, actual_risks: list[RiskPoint], final_markdown: str) -> dict:
    rules = sample.get("report_quality", {})
    if not isinstance(rules, dict):
        rules = {}

    checks: dict[str, dict] = {}

    if rules.get("require_structured_risk_points"):
        passed = len(actual_risks) > 0 or "未发现" in final_markdown
        checks["structured_risk_points"] = {
            "required": True,
            "passed": passed,
            "detail": "已解析出风险点或报告明确写明未发现。" if passed else "未解析出结构化风险点，且报告未明确给出未发现结论。",
        }

    if rules.get("forbid_summary_only"):
        has_summary_marker = any(marker in final_markdown for marker in SUMMARY_ONLY_MARKERS)
        has_risk_heading = any(f"风险点{index}" in final_markdown for index in range(1, 6)) or "问题定性" in final_markdown
        passed = not (has_summary_marker and not has_risk_heading and actual_risks == [])
        checks["forbid_summary_only"] = {
            "required": True,
            "passed": passed,
            "detail": "报告不是纯综述输出。" if passed else "报告疑似只有综述性内容，缺少结构化风险点。",
        }

    if rules.get("prefer_fixed_fields"):
        passed = True
        failed_fields: list[str] = []
        for risk in actual_risks:
            if rules.get("require_title") and not risk.title.strip():
                passed = False
                failed_fields.append("问题标题")
            if rules.get("require_severity") and _is_missing_text(risk.severity):
                passed = False
                failed_fields.append("问题定性")
            if rules.get("require_review_type") and _is_missing_text(risk.review_type):
                passed = False
                failed_fields.append("审查类型")
        checks["fixed_fields"] = {
            "required": True,
            "passed": passed,
            "detail": "结构化字段完整。" if passed else f"存在缺失字段: {sorted(set(failed_fields))}",
        }

    if rules.get("require_location_or_excerpt"):
        missing_support = []
        for risk in actual_risks:
            if _is_missing_text(risk.source_location) and _is_missing_text(risk.source_excerpt):
                missing_support.append(risk.title or "未命名风险点")
        passed = not missing_support
        checks["location_or_excerpt"] = {
            "required": True,
            "passed": passed,
            "detail": "每个风险点均包含原文位置或原文摘录。" if passed else f"以下风险点缺少位置和摘录支撑: {missing_support}",
        }

    required_total = len(checks)
    passed_count = sum(1 for item in checks.values() if item["passed"])
    return {
        "required_total": required_total,
        "passed_count": passed_count,
        "pass_rate": (passed_count / required_total) if required_total else 1.0,
        "failed_count": required_total - passed_count,
        "all_passed": passed_count == required_total,
        "checks": checks,
    }


def evaluate_sample(sample: dict, settings: ReviewSettings) -> dict:
    actual_risks, final_markdown = _run_baseline(sample, settings)
    expected_risks = [item for item in sample.get("expected_risks", []) if isinstance(item, dict)]
    must_hit = [item for item in sample.get("must_hit", []) if isinstance(item, dict)]
    must_not_hit = [item for item in sample.get("must_not_hit", []) if isinstance(item, dict)]
    case_type = str(sample.get("case_type", "unknown"))

    expected_hit = 0
    expected_details: list[dict] = []
    for expected in expected_risks:
        matched = _find_match(expected, actual_risks)
        if matched:
            expected_hit += 1
        expected_details.append(
            {
                "expected": expected,
                "matched": matched.title if matched else "未命中",
                "matched_severity": matched.severity if matched else "未命中",
                "matched_review_type": matched.review_type if matched else "未命中",
            }
        )

    must_hit_count = 0
    must_hit_details: list[dict] = []
    for expected in must_hit:
        matched = _find_match(expected, actual_risks)
        if matched:
            must_hit_count += 1
        must_hit_details.append(
            {
                "expected": expected,
                "matched": matched.title if matched else "未命中",
                "matched_severity": matched.severity if matched else "未命中",
            }
        )

    false_positive_count = 0
    false_positive_details: list[dict] = []
    for blocked in must_not_hit:
        matched = _find_match(blocked, actual_risks)
        if matched:
            false_positive_count += 1
        false_positive_details.append(
            {
                "blocked": blocked,
                "matched": matched.title if matched else "未命中",
                "matched_severity": matched.severity if matched else "未命中",
            }
        )

    actual_titles = [risk.title for risk in actual_risks]
    report_quality = _evaluate_report_quality(sample, actual_risks, final_markdown)
    return {
        "sample_id": str(sample.get("sample_id", "sample")),
        "document_name": str(sample.get("document_name", "")),
        "case_type": case_type,
        "risk_family": list(sample.get("risk_family", [])),
        "priority": str(sample.get("priority", "")),
        "actual_risk_count": len(actual_risks),
        "actual_risk_titles": actual_titles,
        "expected_total": len(expected_risks),
        "expected_hit": expected_hit,
        "expected_hit_rate": (expected_hit / len(expected_risks)) if expected_risks else 1.0,
        "must_hit_total": len(must_hit),
        "must_hit_count": must_hit_count,
        "must_hit_rate": (must_hit_count / len(must_hit)) if must_hit else 1.0,
        "false_positive_total": len(must_not_hit),
        "false_positive_count": false_positive_count,
        "false_positive_rate": (false_positive_count / len(must_not_hit)) if must_not_hit else 0.0,
        "high_risk_miss_total": len(must_hit) if case_type == "high_risk" else 0,
        "high_risk_miss_count": (len(must_hit) - must_hit_count) if case_type == "high_risk" else 0,
        "report_quality_total": int(report_quality["required_total"]),
        "report_quality_passed": int(report_quality["passed_count"]),
        "report_quality_pass_rate": report_quality["pass_rate"],
        "report_quality_failed": int(report_quality["failed_count"]),
        "report_quality_all_passed": bool(report_quality["all_passed"]),
        "report_quality_checks": report_quality["checks"],
        "expected_details": expected_details,
        "must_hit_details": must_hit_details,
        "false_positive_details": false_positive_details,
        "final_markdown": final_markdown,
    }


def build_summary(results: list[dict], sample_path: Path) -> dict:
    sample_count = len(results)
    expected_total = sum(int(result["expected_total"]) for result in results)
    expected_hit = sum(int(result["expected_hit"]) for result in results)
    must_hit_total = sum(int(result["must_hit_total"]) for result in results)
    must_hit_count = sum(int(result["must_hit_count"]) for result in results)
    false_positive_total = sum(int(result["false_positive_total"]) for result in results)
    false_positive_count = sum(int(result["false_positive_count"]) for result in results)
    high_risk_miss_total = sum(int(result["high_risk_miss_total"]) for result in results)
    high_risk_miss_count = sum(int(result["high_risk_miss_count"]) for result in results)
    report_quality_total = sum(int(result.get("report_quality_total", 0)) for result in results)
    report_quality_passed = sum(int(result.get("report_quality_passed", 0)) for result in results)
    report_quality_failed = sum(int(result.get("report_quality_failed", 0)) for result in results)
    report_quality_sample_total = len([result for result in results if int(result.get("report_quality_total", 0)) > 0])
    report_quality_all_passed_count = len([result for result in results if result.get("report_quality_all_passed") is True])

    return {
        "sample_path": str(sample_path),
        "sample_count": sample_count,
        "expected_total": expected_total,
        "expected_hit": expected_hit,
        "risk_hit_rate": (expected_hit / expected_total) if expected_total else 1.0,
        "must_hit_total": must_hit_total,
        "must_hit_count": must_hit_count,
        "must_hit_rate": (must_hit_count / must_hit_total) if must_hit_total else 1.0,
        "miss_rate": ((must_hit_total - must_hit_count) / must_hit_total) if must_hit_total else 0.0,
        "false_positive_total": false_positive_total,
        "false_positive_count": false_positive_count,
        "false_positive_rate": (false_positive_count / false_positive_total) if false_positive_total else 0.0,
        "high_risk_miss_total": high_risk_miss_total,
        "high_risk_miss_count": high_risk_miss_count,
        "high_risk_miss_rate": (high_risk_miss_count / high_risk_miss_total) if high_risk_miss_total else 0.0,
        "report_quality_total": report_quality_total,
        "report_quality_passed": report_quality_passed,
        "report_quality_failed": report_quality_failed,
        "report_quality_pass_rate": (report_quality_passed / report_quality_total) if report_quality_total else 1.0,
        "report_quality_sample_total": report_quality_sample_total,
        "report_quality_all_passed_count": report_quality_all_passed_count,
        "report_quality_sample_pass_rate": (
            report_quality_all_passed_count / report_quality_sample_total
            if report_quality_sample_total
            else 1.0
        ),
        "samples": results,
    }


def print_report(summary: dict) -> None:
    print("V2 第一层 baseline 评估结果")
    print(f"样本文件: {summary['sample_path']}")
    print(f"样本数: {summary['sample_count']}")
    print(f"风险命中率: {summary['expected_hit']}/{summary['expected_total']} = {summary['risk_hit_rate']:.2%}")
    print(f"必须命中命中率: {summary['must_hit_count']}/{summary['must_hit_total']} = {summary['must_hit_rate']:.2%}")
    print(f"漏检率: {summary['miss_rate']:.2%}")
    print(
        f"误报率: {summary['false_positive_count']}/{summary['false_positive_total']} = "
        f"{summary['false_positive_rate']:.2%}"
    )
    print(
        f"高风险漏检率: {summary['high_risk_miss_count']}/{summary['high_risk_miss_total']} = "
        f"{summary['high_risk_miss_rate']:.2%}"
    )
    print(
        f"报告质量通过率: {summary['report_quality_passed']}/{summary['report_quality_total']} = "
        f"{summary['report_quality_pass_rate']:.2%}"
    )
    print(
        f"报告质量样本全通过率: {summary['report_quality_all_passed_count']}/{summary['report_quality_sample_total']} = "
        f"{summary['report_quality_sample_pass_rate']:.2%}"
    )
    print("")
    for sample in summary["samples"]:
        print(f"[{sample['sample_id']}] type={sample['case_type']} priority={sample['priority']}")
        print(
            f"  风险命中率: {sample['expected_hit']}/{sample['expected_total']} = {sample['expected_hit_rate']:.2%} | "
            f"必须命中: {sample['must_hit_count']}/{sample['must_hit_total']} = {sample['must_hit_rate']:.2%} | "
            f"误报: {sample['false_positive_count']}/{sample['false_positive_total']} = {sample['false_positive_rate']:.2%} | "
            f"报告质量: {sample['report_quality_passed']}/{sample['report_quality_total']} = {sample['report_quality_pass_rate']:.2%}"
        )
        print(f"  实际风险标题: {sample['actual_risk_titles']}")
        for detail in sample["must_hit_details"]:
            expected = detail["expected"]
            print(
                f"  - must_hit {expected.get('title_keywords', [])} -> {detail['matched']} "
                f"({detail['matched_severity']})"
            )
        for detail in sample["false_positive_details"]:
            blocked = detail["blocked"]
            if detail["matched"] != "未命中":
                print(
                    f"  - false_positive {blocked.get('title_keywords', [])} -> "
                    f"{detail['matched']} ({detail['matched_severity']})"
                )
        for name, check in sample.get("report_quality_checks", {}).items():
            if not check.get("passed"):
                print(f"  - report_quality {name} -> {check.get('detail', '')}")
        print("")


def main() -> int:
    parser = argparse.ArgumentParser(description="评估 V2 第一层全文直审的命中率、漏检率和误报率。")
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLE_PATH, help="baseline 评估样本 JSON 路径")
    parser.add_argument("--dataset-root", type=Path, default=None, help=f"固定评估数据集目录，默认 {DEFAULT_EVAL_ROOT}")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=6400)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--json", action="store_true", help="仅输出 JSON 汇总结果")
    args = parser.parse_args()

    settings = ReviewSettings.from_env()
    if args.base_url:
        settings.base_url = args.base_url
    if args.model:
        settings.model = args.model
    if args.api_key:
        settings.api_key = args.api_key
    settings.temperature = args.temperature
    settings.max_tokens = args.max_tokens
    settings.timeout = args.timeout

    sample_path = resolve_v2_eval_sample_path("baseline", samples_path=args.samples, dataset_root=args.dataset_root)
    results = [evaluate_sample(sample, settings) for sample in load_samples(sample_path)]
    summary = build_summary(results, sample_path)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print_report(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
