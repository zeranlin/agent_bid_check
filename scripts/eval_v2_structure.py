from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import PROJECT_ROOT as APP_PROJECT_ROOT, ReviewSettings
from app.pipelines.v2.evidence import build_evidence_map
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


def _normalize_list(values: list[str] | tuple[str, ...] | None) -> list[str]:
    return [str(value).strip() for value in (values or []) if str(value).strip()]


def _title_in_list(expected_title: str, actual_titles: list[str]) -> bool:
    expected_norm = _normalize_text(expected_title)
    return any(
        expected_norm in _normalize_text(actual) or _normalize_text(actual) in expected_norm
        for actual in actual_titles
        if str(actual).strip()
    )


def _evaluate_negative_module_constraints(must_not_primary_modules: dict, sections: list[dict]) -> tuple[int, int, list[dict]]:
    total = 0
    pass_count = 0
    details: list[dict] = []
    for title, blocked_modules in (must_not_primary_modules or {}).items():
        matched = _match_section(str(title), sections)
        blocked = _normalize_list(blocked_modules if isinstance(blocked_modules, list) else [])
        if not matched or not blocked:
            continue
        predicted_module = str(matched.get("module", "")).strip()
        total += 1
        passed = predicted_module not in blocked
        if passed:
            pass_count += 1
        details.append(
            {
                "title": str(title),
                "predicted_module": predicted_module or "未匹配",
                "blocked_modules": blocked,
                "passed": passed,
            }
        )
    return total, pass_count, details


def _evaluate_coverage_expectations(sample: dict, structure_artifact) -> tuple[int, int, list[dict]]:
    expectations = [item for item in sample.get("coverage_expectations", []) if isinstance(item, dict)]
    if not expectations:
        return 0, 0, []

    evidence = build_evidence_map(
        document_name=str(sample.get("document_name") or sample.get("sample_id") or "sample"),
        structure=structure_artifact,
        topic_mode="enhanced",
    )
    bundles = evidence.metadata.get("topic_evidence_bundles", {}) if evidence.metadata else {}
    total = 0
    pass_count = 0
    details: list[dict] = []

    for item in expectations:
        topic = str(item.get("topic", "")).strip()
        if not topic:
            continue
        required_modules = _normalize_list(item.get("required_modules"))
        required_titles = _normalize_list(item.get("required_section_titles"))
        expected_primary_titles = _normalize_list(item.get("expected_primary_titles"))
        expected_secondary_titles = _normalize_list(item.get("expected_secondary_titles"))
        expected_shared_topics = _normalize_list(item.get("expected_shared_topics"))
        expected_shared_titles = _normalize_list(item.get("expected_shared_titles")) or required_titles
        min_sections = int(item.get("min_sections", 1) or 1)
        bundle = bundles.get(topic, {}) if isinstance(bundles, dict) else {}
        sections = bundle.get("sections", []) if isinstance(bundle, dict) else []
        primary_ids = set(_normalize_list(bundle.get("primary_section_ids", [])))
        secondary_ids = set(_normalize_list(bundle.get("secondary_section_ids", [])))
        recalled_titles = [str(section.get("title", "")).strip() for section in sections if isinstance(section, dict)]
        recalled_modules = list(
            dict.fromkeys(
                module
                for section in sections
                if isinstance(section, dict)
                for module in (
                    [str(section.get("module", "")).strip()]
                    + [
                        str(key).strip()
                        for key, value in dict(section.get("module_scores", {}) or {}).items()
                        if int(value or 0) > 0
                    ]
                )
                if module
            )
        )
        primary_titles = [
            str(section.get("title", "")).strip()
            for section in sections
            if isinstance(section, dict)
            and f"{int(section.get('start_line', 0) or 0)}-{int(section.get('end_line', 0) or 0)}" in primary_ids
        ]
        secondary_titles = [
            str(section.get("title", "")).strip()
            for section in sections
            if isinstance(section, dict)
            and f"{int(section.get('start_line', 0) or 0)}-{int(section.get('end_line', 0) or 0)}" in secondary_ids
        ]

        titles_ok = all(_title_in_list(expected, recalled_titles) for expected in required_titles)
        modules_ok = all(module in recalled_modules for module in required_modules)
        section_count_ok = len(sections) >= min_sections
        primary_order_ok = all(_title_in_list(expected, primary_titles) for expected in expected_primary_titles)
        secondary_order_ok = all(_title_in_list(expected, secondary_titles) for expected in expected_secondary_titles)

        shared_topics_ok = True
        shared_topic_hits: dict[str, list[str]] = {}
        for shared_topic in expected_shared_topics:
            shared_bundle = bundles.get(shared_topic, {}) if isinstance(bundles, dict) else {}
            shared_sections = shared_bundle.get("sections", []) if isinstance(shared_bundle, dict) else []
            shared_titles = [str(section.get("title", "")).strip() for section in shared_sections if isinstance(section, dict)]
            shared_topic_hits[shared_topic] = shared_titles
            if not all(_title_in_list(expected, shared_titles) for expected in expected_shared_titles):
                shared_topics_ok = False

        passed = titles_ok and modules_ok and section_count_ok and primary_order_ok and secondary_order_ok and shared_topics_ok

        total += 1
        if passed:
            pass_count += 1
        details.append(
            {
                "topic": topic,
                "required_modules": required_modules,
                "required_section_titles": required_titles,
                "min_sections": min_sections,
                "recalled_modules": recalled_modules,
                "recalled_titles": recalled_titles,
                "primary_titles": primary_titles,
                "secondary_titles": secondary_titles,
                "recalled_section_count": len(sections),
                "passed": passed,
                "expected_primary_titles": expected_primary_titles,
                "expected_secondary_titles": expected_secondary_titles,
                "expected_shared_topics": expected_shared_topics,
                "expected_shared_titles": expected_shared_titles,
                "shared_topic_hits": shared_topic_hits,
                "failure_reasons": [
                    reason
                    for reason, ok in (
                        ("missing_titles", titles_ok),
                        ("missing_modules", modules_ok),
                        ("insufficient_sections", section_count_ok),
                        ("primary_order_mismatch", primary_order_ok),
                        ("secondary_order_mismatch", secondary_order_ok),
                        ("shared_topic_unstable", shared_topics_ok),
                    )
                    if not ok
                ],
            }
        )
    return total, pass_count, details


def _evaluate_secondary_module_recall(expected_sections: list[dict], sections: list[dict], case_type: str) -> tuple[int, int, list[dict]]:
    total = 0
    hit = 0
    details: list[dict] = []

    for expected in expected_sections:
        if not isinstance(expected, dict):
            continue
        expected_title = str(expected.get("title", "")).strip()
        secondary_modules = _normalize_list(expected.get("secondary_modules"))
        if not secondary_modules:
            continue

        matched = _match_section(expected_title, sections)
        module_scores = matched.get("module_scores", {}) if isinstance(matched, dict) else {}
        predicted_primary = str(matched.get("module", "")).strip() if isinstance(matched, dict) else ""
        matched_secondary = [
            module for module in secondary_modules if int(module_scores.get(module, 0) or 0) > 0
        ]
        section_total = len(secondary_modules)
        section_hit = len(matched_secondary)
        total += section_total
        hit += section_hit
        details.append(
            {
                "title": expected_title,
                "predicted_primary_module": predicted_primary or "未匹配",
                "expected_secondary_modules": secondary_modules,
                "matched_secondary_modules": matched_secondary,
                "module_scores": module_scores,
                "passed": section_hit == section_total if section_total else True,
                "case_type": case_type,
            }
        )
    return total, hit, details


def evaluate_sample(sample: dict, use_llm: bool = False) -> dict:
    settings = ReviewSettings()
    sample_name = str(sample.get("sample_id") or sample.get("name") or "sample")
    artifact = build_structure_map(
        input_path=Path(sample_name + ".txt"),
        extracted_text=str(sample.get("text", "")),
        settings=settings,
        use_llm=use_llm,
    )
    sections = artifact.metadata.get("sections", []) if artifact.metadata else []
    expected_sections = sample.get("expected_sections", [])
    case_type = str(sample.get("case_type") or "unknown")
    negative_total, negative_pass_count, negative_details = _evaluate_negative_module_constraints(
        sample.get("must_not_primary_modules", {}),
        sections,
    )
    coverage_total, coverage_pass_count, coverage_details = _evaluate_coverage_expectations(sample, artifact)
    secondary_total, secondary_hit, secondary_details = _evaluate_secondary_module_recall(
        expected_sections,
        sections,
        case_type=case_type,
    )

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
        "name": sample_name,
        "document_name": str(sample.get("document_name") or sample.get("name") or sample_name),
        "case_type": case_type,
        "focus_modules": list(sample.get("focus_modules", [])),
        "section_count": len(sections),
        "structure_llm_used": artifact.metadata.get("structure_llm_used", False),
        "structure_fallback_used": artifact.metadata.get("structure_fallback_used", False),
        "module_total": module_total,
        "module_correct": module_correct,
        "module_accuracy": (module_correct / module_total) if module_total else 0.0,
        "key_total": key_total,
        "key_hit": key_hit,
        "key_recall": (key_hit / key_total) if key_total else 0.0,
        "negative_total": negative_total,
        "negative_pass_count": negative_pass_count,
        "negative_pass_rate": (negative_pass_count / negative_total) if negative_total else 1.0,
        "coverage_total": coverage_total,
        "coverage_pass_count": coverage_pass_count,
        "coverage_recall_rate": (coverage_pass_count / coverage_total) if coverage_total else 1.0,
        "secondary_total": secondary_total,
        "secondary_hit": secondary_hit,
        "secondary_recall_rate": (secondary_hit / secondary_total) if secondary_total else 1.0,
        "details": details,
        "negative_details": negative_details,
        "coverage_details": coverage_details,
        "secondary_details": secondary_details,
    }


def build_summary(results: list[dict], sample_path: Path, use_llm: bool) -> dict:
    sample_count = len(results)
    module_total = sum(int(result["module_total"]) for result in results)
    module_correct = sum(int(result["module_correct"]) for result in results)
    key_total = sum(int(result["key_total"]) for result in results)
    key_hit = sum(int(result["key_hit"]) for result in results)
    negative_total = sum(int(result.get("negative_total", 0)) for result in results)
    negative_pass_count = sum(int(result.get("negative_pass_count", 0)) for result in results)
    coverage_total = sum(int(result.get("coverage_total", 0)) for result in results)
    coverage_pass_count = sum(int(result.get("coverage_pass_count", 0)) for result in results)
    secondary_total = sum(int(result.get("secondary_total", 0)) for result in results)
    secondary_hit = sum(int(result.get("secondary_hit", 0)) for result in results)
    llm_used_count = sum(1 for result in results if result.get("structure_llm_used"))
    fallback_count = sum(1 for result in results if result.get("structure_fallback_used"))
    topic_failure_summary: dict[str, int] = {}
    for result in results:
        for detail in result.get("coverage_details", []):
            if detail.get("passed"):
                continue
            topic = str(detail.get("topic", "")).strip() or "unknown"
            topic_failure_summary[topic] = topic_failure_summary.get(topic, 0) + 1
    failure_reason_summary: dict[str, int] = {}
    for result in results:
        for detail in result.get("coverage_details", []):
            for reason in detail.get("failure_reasons", []):
                failure_reason_summary[reason] = failure_reason_summary.get(reason, 0) + 1
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
        "negative_total": negative_total,
        "negative_pass_count": negative_pass_count,
        "negative_pass_rate": (negative_pass_count / negative_total) if negative_total else 1.0,
        "coverage_total": coverage_total,
        "coverage_pass_count": coverage_pass_count,
        "coverage_recall_rate": (coverage_pass_count / coverage_total) if coverage_total else 1.0,
        "secondary_total": secondary_total,
        "secondary_hit": secondary_hit,
        "mixed_section_secondary_recall_rate": (secondary_hit / secondary_total) if secondary_total else 1.0,
        "llm_used_count": llm_used_count,
        "fallback_count": fallback_count,
        "topic_failure_summary": topic_failure_summary,
        "failure_reason_summary": failure_reason_summary,
        "samples": results,
    }


def print_report(summary: dict) -> None:
    print("V2 结构层评估结果")
    print(f"样本文件: {summary['sample_path']}")
    print(f"样本数: {summary['sample_count']}")
    print(f"是否启用 LLM 二次识别: {'是' if summary['use_llm'] else '否'}")
    print(f"模块主归属一致率: {summary['module_correct']}/{summary['module_total']} = {summary['module_accuracy']:.2%}")
    print(f"关键章节召回率: {summary['key_hit']}/{summary['key_total']} = {summary['key_recall']:.2%}")
    print(
        f"负向主模块约束通过率: {summary['negative_pass_count']}/{summary['negative_total']} = "
        f"{summary['negative_pass_rate']:.2%}"
    )
    print(
        f"coverage 召回通过率: {summary['coverage_pass_count']}/{summary['coverage_total']} = "
        f"{summary['coverage_recall_rate']:.2%}"
    )
    print(
        f"混合章节副召回覆盖率: {summary['secondary_hit']}/{summary['secondary_total']} = "
        f"{summary['mixed_section_secondary_recall_rate']:.2%}"
    )
    print(f"LLM 触发样本数: {summary['llm_used_count']}")
    print(f"LLM 回退样本数: {summary['fallback_count']}")
    if summary.get("topic_failure_summary"):
        print(f"专题失败分布: {summary['topic_failure_summary']}")
    if summary.get("failure_reason_summary"):
        print(f"失败原因分布: {summary['failure_reason_summary']}")
    print("")
    for sample in summary["samples"]:
        print(f"[{sample['name']}]")
        print(
            f"  模块一致率: {sample['module_correct']}/{sample['module_total']} = {sample['module_accuracy']:.2%} | "
            f"关键章节召回率: {sample['key_hit']}/{sample['key_total']} = {sample['key_recall']:.2%} | "
            f"coverage: {sample['coverage_pass_count']}/{sample['coverage_total']} = {sample['coverage_recall_rate']:.2%} | "
            f"secondary: {sample['secondary_hit']}/{sample['secondary_total']} = {sample['secondary_recall_rate']:.2%}"
        )
        for detail in sample["details"]:
            print(
                f"  - {detail['expected_title']} -> {detail['predicted_module']} "
                f"(期望 {detail['expected_module']}, 匹配: {detail['matched_title']})"
            )
        for detail in sample.get("negative_details", []):
            if not detail.get("passed"):
                print(
                    f"  - negative_constraint {detail['title']} -> {detail['predicted_module']} "
                    f"(禁止 {detail['blocked_modules']})"
                )
        for detail in sample.get("coverage_details", []):
            if not detail.get("passed"):
                print(
                    f"  - coverage {detail['topic']} 未通过: {detail['failure_reasons']} "
                    f"(召回标题 {detail['recalled_titles']})"
                )
        for detail in sample.get("secondary_details", []):
            if not detail.get("passed"):
                print(
                    f"  - secondary {detail['title']} 未通过: "
                    f"期望 {detail['expected_secondary_modules']}，命中 {detail['matched_secondary_modules']}"
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
