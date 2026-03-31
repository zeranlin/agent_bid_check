from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import PROJECT_ROOT as APP_PROJECT_ROOT, ReviewSettings
from app.pipelines.v2.evidence import build_evidence_map
from app.pipelines.v2.structure import build_structure_map
from app.pipelines.v2.topic_review import run_topic_reviews


DEFAULT_SAMPLE_PATH = APP_PROJECT_ROOT / "data" / "examples" / "v2_topic_eval_samples.json"
TECHNICAL_TOPIC_KEYS = {"technical", "technical_bias", "technical_standard", "samples_demo"}
HIGH_MEDIUM_SEVERITIES = {"高风险", "中风险"}


def load_samples(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("评估样本文件必须是数组。")
    return [item for item in data if isinstance(item, dict)]


def _normalize_text(text: str) -> str:
    return "".join(text.split()).lower()


def _match_title(expected_title: str, actual_titles: list[str]) -> bool:
    expected_norm = _normalize_text(expected_title)
    for title in actual_titles:
        actual_norm = _normalize_text(title)
        if expected_norm == actual_norm or expected_norm in actual_norm or actual_norm in expected_norm:
            return True
    return False


def _mock_call_factory(mock_topic_outputs: dict[str, dict]):
    def fake_call_chat_completion(**kwargs: object) -> dict:
        user_prompt = str(kwargs.get("user_prompt", ""))
        for topic_key, payload in mock_topic_outputs.items():
            marker = f"专题键：{topic_key}"
            if marker in user_prompt:
                return {"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]}
        fallback = {
            "summary": "未命中专题 mock，需人工复核。",
            "need_manual_review": True,
            "coverage_note": "未命中专题 mock。",
            "missing_evidence": ["未命中专题 mock。"],
            "risk_points": [],
        }
        return {"choices": [{"message": {"content": json.dumps(fallback, ensure_ascii=False)}}]}

    return fake_call_chat_completion


def _expected_topic_titles(sample: dict, topic_key: str) -> list[str]:
    titles = [str(item).strip() for item in sample.get("expected_high_medium_titles", []) if str(item).strip()]
    if titles:
        return titles
    if topic_key in TECHNICAL_TOPIC_KEYS:
        return [str(item).strip() for item in sample.get("expected_technical_titles", []) if str(item).strip()]
    return []


def _find_topic_result(topic_key: str, topics) -> object | None:
    for topic in topics:
        if topic.topic == topic_key:
            return topic
    return None


def evaluate_sample(sample: dict) -> dict:
    settings = ReviewSettings()
    name = str(sample.get("name", "sample"))
    topic_mode = str(sample.get("topic_mode", "default"))
    topic_keys = sample.get("topic_keys")
    topic_keys_list = topic_keys if isinstance(topic_keys, list) else None
    text = str(sample.get("text", ""))
    target_topic = str(sample.get("topic", "")).strip()
    case_type = str(sample.get("case_type", "unknown")).strip()

    structure = build_structure_map(
        input_path=Path(f"{name}.txt"),
        extracted_text=text,
        settings=settings,
        use_llm=False,
    )
    evidence = build_evidence_map(name, structure, topic_mode=topic_mode, topic_keys=topic_keys_list)

    mock_topic_outputs = sample.get("mock_topic_outputs", {})
    with patch("app.pipelines.v2.topic_review.call_chat_completion", _mock_call_factory(mock_topic_outputs)):
        topics = run_topic_reviews(
            document_name=f"{name}.txt",
            evidence=evidence,
            settings=settings,
            topic_mode=topic_mode,
            topic_keys=topic_keys_list,
        )

    target_topic_result = _find_topic_result(target_topic, topics) if target_topic else None
    target_risk_titles = [risk.title for risk in target_topic_result.risk_points] if target_topic_result else []
    expected_topic_titles = _expected_topic_titles(sample, target_topic)
    topic_hits = sum(1 for title in expected_topic_titles if _match_title(title, target_risk_titles))
    topic_miss_count = max(len(expected_topic_titles) - topic_hits, 0)
    false_positive_count = 1 if case_type == "negative" and target_risk_titles else 0
    manual_review_expected = 1 if case_type == "manual_review" else 0
    manual_review_hit = 1 if manual_review_expected and target_topic_result and target_topic_result.need_manual_review else 0
    manual_review_false_positive = (
        1 if case_type == "negative" and target_topic_result and target_topic_result.need_manual_review else 0
    )

    actual_high_medium_titles = [
        risk.title
        for topic in topics
        for risk in topic.risk_points
        if risk.severity in HIGH_MEDIUM_SEVERITIES
    ]
    actual_technical_titles = [
        risk.title
        for topic in topics
        for risk in topic.risk_points
        if topic.topic in TECHNICAL_TOPIC_KEYS
    ]
    expected_high_medium_titles = [str(item).strip() for item in sample.get("expected_high_medium_titles", []) if str(item).strip()]
    expected_technical_titles = [str(item).strip() for item in sample.get("expected_technical_titles", []) if str(item).strip()]

    high_medium_hits = sum(1 for title in expected_high_medium_titles if _match_title(title, actual_high_medium_titles))
    technical_hits = sum(1 for title in expected_technical_titles if _match_title(title, actual_technical_titles))
    manual_review_count = sum(1 for topic in topics if topic.need_manual_review)

    return {
        "name": name,
        "sample_id": str(sample.get("sample_id", name)),
        "topic_mode": topic_mode,
        "topic": target_topic,
        "case_type": case_type,
        "topic_count": len(topics),
        "high_medium_expected": len(expected_high_medium_titles),
        "high_medium_hit": high_medium_hits,
        "high_medium_hit_rate": (high_medium_hits / len(expected_high_medium_titles)) if expected_high_medium_titles else 0.0,
        "technical_expected": len(expected_technical_titles),
        "technical_hit": technical_hits,
        "technical_hit_rate": (technical_hits / len(expected_technical_titles)) if expected_technical_titles else 0.0,
        "manual_review_count": manual_review_count,
        "manual_review_ratio": (manual_review_count / len(topics)) if topics else 0.0,
        "topic_expected_total": len(expected_topic_titles),
        "topic_hit_count": topic_hits,
        "topic_hit_rate": (topic_hits / len(expected_topic_titles)) if expected_topic_titles else 1.0,
        "topic_miss_count": topic_miss_count,
        "topic_miss_rate": (topic_miss_count / len(expected_topic_titles)) if expected_topic_titles else 0.0,
        "false_positive_total": 1 if case_type == "negative" else 0,
        "false_positive_count": false_positive_count,
        "false_positive_rate": float(false_positive_count) if case_type == "negative" else 0.0,
        "manual_review_expected_total": manual_review_expected,
        "manual_review_hit": manual_review_hit,
        "manual_review_expected_rate": float(manual_review_hit) if manual_review_expected else 1.0,
        "manual_review_false_positive_count": manual_review_false_positive,
        "target_topic_detail": {
            "topic": target_topic,
            "found": target_topic_result is not None,
            "risk_titles": target_risk_titles,
            "need_manual_review": bool(target_topic_result.need_manual_review) if target_topic_result else False,
            "expected_titles": expected_topic_titles,
        },
        "topic_execution_plan": evidence.metadata.get("topic_execution_plan", {}),
        "details": [
            {
                "topic": topic.topic,
                "summary": topic.summary,
                "risk_titles": [risk.title for risk in topic.risk_points],
                "need_manual_review": topic.need_manual_review,
            }
            for topic in topics
        ],
    }


def build_summary(results: list[dict], sample_path: Path) -> dict:
    sample_count = len(results)
    high_medium_expected = sum(int(result["high_medium_expected"]) for result in results)
    high_medium_hit = sum(int(result["high_medium_hit"]) for result in results)
    technical_expected = sum(int(result["technical_expected"]) for result in results)
    technical_hit = sum(int(result["technical_hit"]) for result in results)
    total_topics = sum(int(result["topic_count"]) for result in results)
    manual_review_count = sum(int(result["manual_review_count"]) for result in results)
    topic_expected_total = sum(int(result.get("topic_expected_total", 0)) for result in results)
    topic_hit_count = sum(int(result.get("topic_hit_count", 0)) for result in results)
    topic_miss_count = sum(int(result.get("topic_miss_count", 0)) for result in results)
    false_positive_total = sum(int(result.get("false_positive_total", 0)) for result in results)
    false_positive_count = sum(int(result.get("false_positive_count", 0)) for result in results)
    manual_review_expected_total = sum(int(result.get("manual_review_expected_total", 0)) for result in results)
    manual_review_hit = sum(int(result.get("manual_review_hit", 0)) for result in results)
    manual_review_false_positive_count = sum(int(result.get("manual_review_false_positive_count", 0)) for result in results)
    by_topic: dict[str, dict[str, int]] = {}
    for result in results:
        topic = str(result.get("topic", "")).strip() or "unknown"
        bucket = by_topic.setdefault(
            topic,
            {
                "sample_count": 0,
                "topic_expected_total": 0,
                "topic_hit_count": 0,
                "topic_miss_count": 0,
                "false_positive_total": 0,
                "false_positive_count": 0,
                "manual_review_expected_total": 0,
                "manual_review_hit": 0,
            },
        )
        bucket["sample_count"] += 1
        bucket["topic_expected_total"] += int(result.get("topic_expected_total", 0))
        bucket["topic_hit_count"] += int(result.get("topic_hit_count", 0))
        bucket["topic_miss_count"] += int(result.get("topic_miss_count", 0))
        bucket["false_positive_total"] += int(result.get("false_positive_total", 0))
        bucket["false_positive_count"] += int(result.get("false_positive_count", 0))
        bucket["manual_review_expected_total"] += int(result.get("manual_review_expected_total", 0))
        bucket["manual_review_hit"] += int(result.get("manual_review_hit", 0))
    return {
        "sample_path": str(sample_path),
        "sample_count": sample_count,
        "high_medium_expected": high_medium_expected,
        "high_medium_hit": high_medium_hit,
        "high_medium_hit_rate": (high_medium_hit / high_medium_expected) if high_medium_expected else 0.0,
        "technical_expected": technical_expected,
        "technical_hit": technical_hit,
        "technical_hit_rate": (technical_hit / technical_expected) if technical_expected else 0.0,
        "topic_count": total_topics,
        "manual_review_count": manual_review_count,
        "manual_review_ratio": (manual_review_count / total_topics) if total_topics else 0.0,
        "topic_expected_total": topic_expected_total,
        "topic_hit_count": topic_hit_count,
        "topic_hit_rate": (topic_hit_count / topic_expected_total) if topic_expected_total else 1.0,
        "topic_miss_count": topic_miss_count,
        "topic_miss_rate": (topic_miss_count / topic_expected_total) if topic_expected_total else 0.0,
        "false_positive_total": false_positive_total,
        "false_positive_count": false_positive_count,
        "false_positive_rate": (false_positive_count / false_positive_total) if false_positive_total else 0.0,
        "manual_review_expected_total": manual_review_expected_total,
        "manual_review_hit": manual_review_hit,
        "manual_review_expected_rate": (
            manual_review_hit / manual_review_expected_total if manual_review_expected_total else 1.0
        ),
        "manual_review_false_positive_count": manual_review_false_positive_count,
        "by_topic": {
            topic: {
                **bucket,
                "topic_hit_rate": (
                    bucket["topic_hit_count"] / bucket["topic_expected_total"]
                    if bucket["topic_expected_total"]
                    else 1.0
                ),
                "topic_miss_rate": (
                    bucket["topic_miss_count"] / bucket["topic_expected_total"]
                    if bucket["topic_expected_total"]
                    else 0.0
                ),
                "false_positive_rate": (
                    bucket["false_positive_count"] / bucket["false_positive_total"]
                    if bucket["false_positive_total"]
                    else 0.0
                ),
                "manual_review_expected_rate": (
                    bucket["manual_review_hit"] / bucket["manual_review_expected_total"]
                    if bucket["manual_review_expected_total"]
                    else 1.0
                ),
            }
            for topic, bucket in by_topic.items()
        },
        "samples": results,
    }


def print_report(summary: dict) -> None:
    print("V2 专题层评估结果")
    print(f"样本文件: {summary['sample_path']}")
    print(f"样本数: {summary['sample_count']}")
    print(
        f"高中风险命中率: {summary['high_medium_hit']}/{summary['high_medium_expected']} = "
        f"{summary['high_medium_hit_rate']:.2%}"
    )
    print(
        f"技术细节命中率: {summary['technical_hit']}/{summary['technical_expected']} = "
        f"{summary['technical_hit_rate']:.2%}"
    )
    print(
        f"人工复核比例: {summary['manual_review_count']}/{summary['topic_count']} = "
        f"{summary['manual_review_ratio']:.2%}"
    )
    print(f"专题命中率: {summary['topic_hit_count']}/{summary['topic_expected_total']} = {summary['topic_hit_rate']:.2%}")
    print(f"专题漏检率: {summary['topic_miss_count']}/{summary['topic_expected_total']} = {summary['topic_miss_rate']:.2%}")
    print(
        f"专题误报率: {summary['false_positive_count']}/{summary['false_positive_total']} = "
        f"{summary['false_positive_rate']:.2%}"
    )
    print(
        f"人工复核合理率: {summary['manual_review_hit']}/{summary['manual_review_expected_total']} = "
        f"{summary['manual_review_expected_rate']:.2%}"
    )
    print(f"人工复核误报数: {summary['manual_review_false_positive_count']}")
    if summary.get("by_topic"):
        print(f"按专题汇总: {summary['by_topic']}")
    print("")
    for sample in summary["samples"]:
        print(f"[{sample['name']}] 模式={sample['topic_mode']} 专题={sample['topic']} 类型={sample['case_type']}")
        print(
            f"  高中风险命中率: {sample['high_medium_hit']}/{sample['high_medium_expected']} = "
            f"{sample['high_medium_hit_rate']:.2%}"
        )
        print(
            f"  技术细节命中率: {sample['technical_hit']}/{sample['technical_expected']} = "
            f"{sample['technical_hit_rate']:.2%}"
        )
        print(
            f"  人工复核比例: {sample['manual_review_count']}/{sample['topic_count']} = "
            f"{sample['manual_review_ratio']:.2%}"
        )
        print(
            f"  专题命中: {sample['topic_hit_count']}/{sample['topic_expected_total']} = {sample['topic_hit_rate']:.2%} | "
            f"漏检: {sample['topic_miss_count']}/{sample['topic_expected_total']} = {sample['topic_miss_rate']:.2%} | "
            f"误报: {sample['false_positive_count']}/{sample['false_positive_total']} = {sample['false_positive_rate']:.2%}"
        )
        print(
            f"  人工复核合理: {sample['manual_review_hit']}/{sample['manual_review_expected_total']} = "
            f"{sample['manual_review_expected_rate']:.2%}"
        )
        print(
            f"  执行计划: selected={sample['topic_execution_plan'].get('selected_keys', [])} "
            f"skipped={sample['topic_execution_plan'].get('skipped_keys', [])}"
        )
        for detail in sample["details"]:
            print(
                f"  - {detail['topic']} | need_manual_review={detail['need_manual_review']} | "
                f"risk_titles={detail['risk_titles']}"
            )
        print("")


def main() -> int:
    parser = argparse.ArgumentParser(description="评估 V2 专题层的命中率与人工复核比例。")
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
