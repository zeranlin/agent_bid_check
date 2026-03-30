from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import PROJECT_ROOT as APP_PROJECT_ROOT, ReviewSettings
from app.pipelines.v2.structure import build_structure_map


DEFAULT_SAMPLE_PATH = APP_PROJECT_ROOT / "data" / "examples" / "v2_structure_eval_samples.json"


def load_samples(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("评估样本文件必须是数组。")
    return [item for item in data if isinstance(item, dict)]


def _normalize_text(text: str) -> str:
    return "".join(text.split()).lower()


def _match_section(expected_title: str, sections: list[dict]) -> dict | None:
    expected_norm = _normalize_text(expected_title)
    for section in sections:
        title = str(section.get("title", ""))
        title_norm = _normalize_text(title)
        if expected_norm == title_norm or expected_norm in title_norm or title_norm in expected_norm:
            return section
    return None


def evaluate_sample(sample: dict, use_llm: bool = False) -> dict:
    settings = ReviewSettings()
    artifact = build_structure_map(
        input_path=Path(str(sample.get("name", "sample")) + ".txt"),
        extracted_text=str(sample.get("text", "")),
        settings=settings,
        use_llm=use_llm,
    )
    sections = artifact.metadata.get("sections", []) if artifact.metadata else []
    expected_sections = sample.get("expected_sections", [])

    module_total = 0
    module_correct = 0
    key_total = 0
    key_hit = 0
    details: list[dict] = []

    for expected in expected_sections:
        if not isinstance(expected, dict):
            continue
        expected_title = str(expected.get("title", "")).strip()
        expected_module = str(expected.get("module", "")).strip()
        is_key = bool(expected.get("key", False))
        matched = _match_section(expected_title, sections)

        matched_title = str(matched.get("title", "")) if matched else ""
        predicted_module = str(matched.get("module", "")) if matched else ""
        found = matched is not None
        module_ok = found and predicted_module == expected_module

        if expected_module:
            module_total += 1
            if module_ok:
                module_correct += 1
        if is_key:
            key_total += 1
            if found:
                key_hit += 1

        details.append(
            {
                "expected_title": expected_title,
                "matched_title": matched_title or "未匹配",
                "expected_module": expected_module or "未标注",
                "predicted_module": predicted_module or "未匹配",
                "found": found,
                "module_correct": module_ok,
                "key_section": is_key,
            }
        )

    return {
        "name": sample.get("name", "sample"),
        "section_count": len(sections),
        "structure_llm_used": artifact.metadata.get("structure_llm_used", False),
        "structure_fallback_used": artifact.metadata.get("structure_fallback_used", False),
        "module_total": module_total,
        "module_correct": module_correct,
        "module_accuracy": (module_correct / module_total) if module_total else 0.0,
        "key_total": key_total,
        "key_hit": key_hit,
        "key_recall": (key_hit / key_total) if key_total else 0.0,
        "details": details,
    }


def build_summary(results: list[dict], sample_path: Path, use_llm: bool) -> dict:
    sample_count = len(results)
    module_total = sum(int(result["module_total"]) for result in results)
    module_correct = sum(int(result["module_correct"]) for result in results)
    key_total = sum(int(result["key_total"]) for result in results)
    key_hit = sum(int(result["key_hit"]) for result in results)
    llm_used_count = sum(1 for result in results if result.get("structure_llm_used"))
    fallback_count = sum(1 for result in results if result.get("structure_fallback_used"))
    return {
        "sample_path": str(sample_path),
        "sample_count": sample_count,
        "use_llm": use_llm,
        "module_total": module_total,
        "module_correct": module_correct,
        "module_accuracy": (module_correct / module_total) if module_total else 0.0,
        "key_total": key_total,
        "key_hit": key_hit,
        "key_recall": (key_hit / key_total) if key_total else 0.0,
        "llm_used_count": llm_used_count,
        "fallback_count": fallback_count,
        "samples": results,
    }


def print_report(summary: dict) -> None:
    print("V2 结构层评估结果")
    print(f"样本文件: {summary['sample_path']}")
    print(f"样本数: {summary['sample_count']}")
    print(f"是否启用 LLM 二次识别: {'是' if summary['use_llm'] else '否'}")
    print(f"模块主归属一致率: {summary['module_correct']}/{summary['module_total']} = {summary['module_accuracy']:.2%}")
    print(f"关键章节召回率: {summary['key_hit']}/{summary['key_total']} = {summary['key_recall']:.2%}")
    print(f"LLM 触发样本数: {summary['llm_used_count']}")
    print(f"LLM 回退样本数: {summary['fallback_count']}")
    print("")
    for sample in summary["samples"]:
        print(f"[{sample['name']}]")
        print(
            f"  模块一致率: {sample['module_correct']}/{sample['module_total']} = {sample['module_accuracy']:.2%} | "
            f"关键章节召回率: {sample['key_hit']}/{sample['key_total']} = {sample['key_recall']:.2%}"
        )
        for detail in sample["details"]:
            print(
                f"  - {detail['expected_title']} -> {detail['predicted_module']} "
                f"(期望 {detail['expected_module']}, 匹配: {detail['matched_title']})"
            )
        print("")


def main() -> int:
    parser = argparse.ArgumentParser(description="评估 V2 结构层的模块识别与关键章节召回表现。")
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLE_PATH, help="评估样本 JSON 路径")
    parser.add_argument("--use-llm", action="store_true", help="启用结构层 LLM 二次识别进行评估")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON 汇总结果")
    args = parser.parse_args()

    results = [evaluate_sample(sample, use_llm=args.use_llm) for sample in load_samples(args.samples)]
    summary = build_summary(results, args.samples, args.use_llm)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print_report(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
