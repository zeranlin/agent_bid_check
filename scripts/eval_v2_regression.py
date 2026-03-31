from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import PROJECT_ROOT as APP_PROJECT_ROOT
from app.pipelines.v2.regression import compare_risks, compare_structure, extract_actual_risks, extract_actual_structure, load_result_payload


DEFAULT_SAMPLE_PATH = APP_PROJECT_ROOT / "data" / "examples" / "v2_regression_eval_samples.json"


def load_samples(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("回归样本文件必须是数组。")
    return [item for item in data if isinstance(item, dict)]


def evaluate_sample(sample: dict) -> dict:
    gold = sample.get("gold", {}) if isinstance(sample.get("gold", {}), dict) else {}
    system = sample.get("system", {}) if isinstance(sample.get("system", {}), dict) else {}
    gold_structure = gold.get("structure", {}) if isinstance(gold.get("structure", {}), dict) else {}
    gold_risks = [item for item in gold.get("risks", []) if isinstance(item, dict)] if isinstance(gold, dict) else []

    actual_sections, actual_bundles = extract_actual_structure(system)
    actual_risks = extract_actual_risks(system)

    structure_result = compare_structure(gold_structure, actual_sections, actual_bundles)
    risk_result = compare_risks(gold_risks, actual_risks)

    return {
        "sample_id": str(sample.get("sample_id", "sample")),
        "document_name": str(sample.get("document_name", "")),
        "structure_required_total": len([item for item in gold_structure.get("required_sections", []) if isinstance(item, dict)])
        if isinstance(gold_structure, dict)
        else 0,
        "structure_hit_count": len(structure_result["matched_sections"]),
        "structure_miss_count": len(structure_result["missed_sections"]),
        "topic_coverage_total": len([item for item in gold_structure.get("topic_coverages", []) if isinstance(item, dict)])
        if isinstance(gold_structure, dict)
        else 0,
        "topic_coverage_hit_count": len(structure_result["matched_topic_coverages"]),
        "topic_coverage_miss_count": len(structure_result["missed_topic_coverages"]),
        "gold_risk_total": len(gold_risks),
        "matched_risk_count": len(risk_result["matched_risks"]),
        "missed_risk_count": len(risk_result["missed_risks"]),
        "false_positive_risk_count": len(risk_result["false_positive_risks"]),
        "manual_review_gap_count": len(risk_result["manual_review_gaps"]),
        "structure": structure_result,
        "risks": risk_result,
    }


def build_summary(results: list[dict], sample_path: Path | None = None) -> dict:
    structure_required_total = sum(int(item.get("structure_required_total", 0)) for item in results)
    structure_hit_count = sum(int(item.get("structure_hit_count", 0)) for item in results)
    topic_coverage_total = sum(int(item.get("topic_coverage_total", 0)) for item in results)
    topic_coverage_hit_count = sum(int(item.get("topic_coverage_hit_count", 0)) for item in results)
    gold_risk_total = sum(int(item.get("gold_risk_total", 0)) for item in results)
    matched_risk_count = sum(int(item.get("matched_risk_count", 0)) for item in results)
    missed_risk_count = sum(int(item.get("missed_risk_count", 0)) for item in results)
    false_positive_risk_count = sum(int(item.get("false_positive_risk_count", 0)) for item in results)
    manual_review_gap_count = sum(int(item.get("manual_review_gap_count", 0)) for item in results)

    return {
        "sample_path": str(sample_path) if sample_path else "",
        "sample_count": len(results),
        "structure_required_total": structure_required_total,
        "structure_hit_count": structure_hit_count,
        "structure_hit_rate": (structure_hit_count / structure_required_total) if structure_required_total else 1.0,
        "structure_miss_count": max(structure_required_total - structure_hit_count, 0),
        "topic_coverage_total": topic_coverage_total,
        "topic_coverage_hit_count": topic_coverage_hit_count,
        "topic_coverage_hit_rate": (topic_coverage_hit_count / topic_coverage_total) if topic_coverage_total else 1.0,
        "topic_coverage_miss_count": max(topic_coverage_total - topic_coverage_hit_count, 0),
        "gold_risk_total": gold_risk_total,
        "matched_risk_count": matched_risk_count,
        "risk_hit_rate": (matched_risk_count / gold_risk_total) if gold_risk_total else 1.0,
        "missed_risk_count": missed_risk_count,
        "miss_rate": (missed_risk_count / gold_risk_total) if gold_risk_total else 0.0,
        "false_positive_risk_count": false_positive_risk_count,
        "manual_review_gap_count": manual_review_gap_count,
        "samples": results,
    }


def collect_outputs(results: list[dict]) -> dict[str, list[dict]]:
    matched_risks: list[dict] = []
    missed_risks: list[dict] = []
    false_positive_risks: list[dict] = []
    manual_review_gaps: list[dict] = []
    structure_gaps: list[dict] = []

    for item in results:
        sample_id = str(item.get("sample_id", "sample"))
        for matched in item.get("risks", {}).get("matched_risks", []):
            matched_risks.append({"sample_id": sample_id, **matched})
        for missed in item.get("risks", {}).get("missed_risks", []):
            missed_risks.append({"sample_id": sample_id, **missed})
        for fp in item.get("risks", {}).get("false_positive_risks", []):
            false_positive_risks.append({"sample_id": sample_id, **fp})
        for gap in item.get("risks", {}).get("manual_review_gaps", []):
            manual_review_gaps.append({"sample_id": sample_id, **gap})
        for gap in item.get("structure", {}).get("missed_sections", []):
            structure_gaps.append({"sample_id": sample_id, "type": "section", **gap})
        for gap in item.get("structure", {}).get("missed_topic_coverages", []):
            structure_gaps.append({"sample_id": sample_id, "type": "topic_coverage", **gap})

    return {
        "matched_risks": matched_risks,
        "missed_risks": missed_risks,
        "false_positive_risks": false_positive_risks,
        "manual_review_gaps": manual_review_gaps,
        "structure_gaps": structure_gaps,
    }


def write_outputs(output_dir: Path, summary: dict, outputs: dict[str, list[dict]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "matched_risks.json").write_text(json.dumps(outputs["matched_risks"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "missed_risks.json").write_text(json.dumps(outputs["missed_risks"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "false_positive_risks.json").write_text(json.dumps(outputs["false_positive_risks"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "manual_review_gaps.json").write_text(json.dumps(outputs["manual_review_gaps"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "structure_gaps.json").write_text(json.dumps(outputs["structure_gaps"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "regression_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def print_report(summary: dict) -> None:
    print("V2 埋点回归评估结果")
    if summary.get("sample_path"):
        print(f"样本文件: {summary['sample_path']}")
    print(f"样本数: {summary['sample_count']}")
    print(
        f"结构命中率: {summary['structure_hit_count']}/{summary['structure_required_total']} = "
        f"{summary['structure_hit_rate']:.2%}"
    )
    print(
        f"专题覆盖命中率: {summary['topic_coverage_hit_count']}/{summary['topic_coverage_total']} = "
        f"{summary['topic_coverage_hit_rate']:.2%}"
    )
    print(
        f"风险命中率: {summary['matched_risk_count']}/{summary['gold_risk_total']} = "
        f"{summary['risk_hit_rate']:.2%}"
    )
    print(f"漏报数: {summary['missed_risk_count']}")
    print(f"误报数: {summary['false_positive_risk_count']}")
    print(f"人工复核差异数: {summary['manual_review_gap_count']}")


def _evaluate_real_case(gold_path: Path, result_dir: Path) -> tuple[list[dict], Path]:
    gold_payload = json.loads(gold_path.read_text(encoding="utf-8"))
    if not isinstance(gold_payload, dict):
        raise ValueError("gold 文件必须是对象。")
    sample = {
        "sample_id": str(gold_payload.get("sample_id", result_dir.name)),
        "document_name": str(gold_payload.get("document_name", result_dir.name)),
        "gold": gold_payload.get("gold", {}),
        "system": load_result_payload(result_dir),
    }
    return [evaluate_sample(sample)], gold_path


def main() -> int:
    parser = argparse.ArgumentParser(description="对 V2 结构层、专题层、汇总层结果执行埋点回归比对。")
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLE_PATH, help="回归样本 JSON 路径")
    parser.add_argument("--gold", type=Path, help="单个真实案例的金标 JSON 路径")
    parser.add_argument("--result-dir", type=Path, help="单个真实案例的 V2 结果目录")
    parser.add_argument("--output-dir", type=Path, help="回归差异输出目录")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON 汇总结果")
    args = parser.parse_args()

    if args.gold and args.result_dir:
        results, summary_path = _evaluate_real_case(args.gold, args.result_dir)
    else:
        results = [evaluate_sample(sample) for sample in load_samples(args.samples)]
        summary_path = args.samples

    summary = build_summary(results, summary_path)
    outputs = collect_outputs(results)

    if args.output_dir:
        write_outputs(args.output_dir, summary, outputs)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print_report(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
