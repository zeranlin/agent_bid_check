from __future__ import annotations

import json
import re
from typing import Callable

from app.common.core import maybe_disable_qwen_thinking
from app.common.llm_client import call_chat_completion, call_chat_completion_stream, extract_response_text
from app.common.schemas import RiskPoint
from app.config import ReviewSettings

from .schemas import TopicReviewArtifact, V2StageArtifact
from .topics import TopicDefinition, resolve_topic_definitions, resolve_topic_execution_plan


JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)


def _extract_json_block(text: str) -> str:
    stripped = text.strip()
    match = JSON_BLOCK_RE.search(stripped)
    if match:
        return match.group(1).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped


def _parse_topic_json(text: str) -> dict:
    payload = _extract_json_block(text)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {
            "summary": "模型输出未能解析为结构化 JSON，需人工复核。",
            "need_manual_review": True,
            "coverage_note": "模型返回了非 JSON 结构。",
            "missing_evidence": ["模型返回了非 JSON 结构。"],
            "risk_points": [],
        }
    if not isinstance(data, dict):
        return {
            "summary": "模型输出结构异常，需人工复核。",
            "need_manual_review": True,
            "coverage_note": "模型返回顶层不是对象。",
            "missing_evidence": ["模型返回顶层不是对象。"],
            "risk_points": [],
        }
    return data


def _to_list(value: object, fallback: str) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or [fallback]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return [fallback]


def _to_risk_point(item: dict, topic_label: str) -> RiskPoint:
    risk = RiskPoint(
        title=str(item.get("title", "")).strip() or f"{topic_label}需人工复核事项",
        severity=str(item.get("severity", "")).strip() or "需人工复核",
        review_type=str(item.get("review_type", "")).strip() or topic_label,
        source_location=str(item.get("source_location", "")).strip() or "未发现",
        source_excerpt=str(item.get("source_excerpt", "")).strip() or "未发现",
        risk_judgment=_to_list(item.get("risk_judgment"), "需人工复核"),
        legal_basis=_to_list(item.get("legal_basis"), "需人工复核"),
        rectification=_to_list(item.get("rectification"), "未发现"),
    )
    risk.ensure_defaults()
    return risk


def _snippet_from_section(section: dict) -> str:
    lines = [
        f"标题：{section.get('title', '未命名章节')}",
        f"位置：第 {section.get('start_line', '?')} - {section.get('end_line', '?')} 行",
        f"识别模块：{section.get('module', '待识别')}",
        f"关键词：{', '.join(section.get('keywords', [])) or '未发现'}",
        "正文片段：",
        section.get("excerpt", "").strip() or "未发现",
    ]
    return "\n".join(lines)


def _get_evidence_bundle(evidence: V2StageArtifact, topic_key: str) -> dict:
    if not evidence.metadata:
        return {}
    bundles = evidence.metadata.get("topic_evidence_bundles", {}) or {}
    bundle = bundles.get(topic_key, {})
    return bundle if isinstance(bundle, dict) else {}


def _get_topic_coverage(evidence: V2StageArtifact, topic_key: str) -> dict:
    if not evidence.metadata:
        return {}
    coverages = evidence.metadata.get("topic_coverages", {}) or {}
    coverage = coverages.get(topic_key, {})
    return coverage if isinstance(coverage, dict) else {}


def _build_topic_prompt(document_name: str, topic: TopicDefinition, bundle: dict, coverage: dict) -> str:
    sections = bundle.get("sections", []) if isinstance(bundle, dict) else []
    evidence_blocks = "\n\n".join(
        [f"[证据{index}]\n{_snippet_from_section(section)}" for index, section in enumerate(sections, start=1)]
    ) or "未发现相关证据片段。"
    missing_hints = bundle.get("missing_hints", []) if isinstance(bundle, dict) else []
    recall_query = str(bundle.get("recall_query", "")).strip() if isinstance(bundle, dict) else ""
    boundary = bundle.get("metadata", {}).get("boundary", {}) if isinstance(bundle, dict) else {}
    covered_modules = coverage.get("covered_modules", []) if isinstance(coverage, dict) else []
    missing_modules = coverage.get("missing_modules", []) if isinstance(coverage, dict) else []

    schema = {
        "summary": "专题结论摘要",
        "need_manual_review": False,
        "coverage_note": "本专题召回范围说明",
        "missing_evidence": ["如存在关键证据缺口，在这里列出"],
        "risk_points": [
            {
                "title": "问题标题",
                "severity": "高风险/中风险/低风险/需人工复核",
                "review_type": "审查类型",
                "source_location": "原文位置",
                "source_excerpt": "原文摘录",
                "risk_judgment": ["分点说明1", "分点说明2"],
                "legal_basis": ["法律政策依据1"],
                "rectification": ["整改建议1"],
            }
        ],
    }

    return (
        f"{topic.prompt.strip()}\n\n"
        "请仅依据我提供的证据片段进行审查，不要凭空补造原文。"
        " 如果证据不足，可以保守判断并标记 need_manual_review=true。"
        " 输出必须是 JSON 对象，不要输出 Markdown，不要解释。\n\n"
        f"文档名称：{document_name}\n"
        f"专题名称：{topic.label}\n"
        f"专题键：{topic.key}\n"
        f"专题优先级：{topic.priority}\n\n"
        f"专题边界-纳入范围：{'；'.join(boundary.get('in_scope', [])) or '未提供'}\n"
        f"专题边界-排除范围：{'；'.join(boundary.get('out_of_scope', [])) or '未提供'}\n"
        f"主归属规则：{boundary.get('ownership_rule', '未提供')}\n"
        f"模块覆盖：{', '.join(covered_modules) or '未发现'}\n"
        f"缺失模块：{', '.join(missing_modules) or '未发现'}\n"
        f"证据召回说明：{recall_query or '未提供'}\n"
        f"召回缺口提示：{'；'.join(missing_hints) if missing_hints else '未发现明显缺口。'}\n\n"
        "JSON 结构示例：\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        "证据片段如下：\n"
        f"{evidence_blocks}\n"
    )


def _build_default_coverage_note(sections: list[dict], coverage: dict) -> str:
    covered_modules = coverage.get("covered_modules", []) if isinstance(coverage, dict) else []
    missing_hints = coverage.get("missing_hints", []) if isinstance(coverage, dict) else []
    return (
        f"召回 {len(sections)} 个证据片段，覆盖模块：{', '.join(covered_modules) or '未发现'}。"
        f"{' 缺口：' + '；'.join(missing_hints) if missing_hints else ''}"
    )


def _build_empty_topic_artifact(
    definition: TopicDefinition,
    bundle: dict,
    coverage: dict,
    topic_mode: str,
    execution_plan: dict,
) -> TopicReviewArtifact:
    sections = bundle.get("sections", []) if isinstance(bundle, dict) else []
    return TopicReviewArtifact(
        topic=definition.key,
        summary=f"{definition.label}专题未召回到足够证据，需人工复核。",
        need_manual_review=True,
        coverage_note=_build_default_coverage_note(sections, coverage),
        raw_output="",
        metadata={
            "topic_label": definition.label,
            "topic_priority": definition.priority,
            "topic_mode": topic_mode,
            "topic_execution_plan": execution_plan,
            "selected_sections": [],
            "missing_evidence": coverage.get("missing_hints", []) if isinstance(coverage, dict) else [],
            "evidence_bundle": bundle,
            "topic_coverage": coverage,
        },
    )


def _run_single_topic(
    definition: TopicDefinition,
    document_name: str,
    evidence: V2StageArtifact,
    settings: ReviewSettings,
    topic_mode: str,
    execution_plan: dict,
    stream_callback: Callable[[str], None] | None = None,
) -> TopicReviewArtifact:
    bundle = _get_evidence_bundle(evidence, definition.key)
    coverage = _get_topic_coverage(evidence, definition.key)
    sections = bundle.get("sections", []) if isinstance(bundle, dict) else []
    coverage_note = _build_default_coverage_note(sections, coverage)
    if not sections:
        return _build_empty_topic_artifact(definition, bundle, coverage, topic_mode, execution_plan)

    prompt = _build_topic_prompt(document_name, definition, bundle, coverage)
    prompt = maybe_disable_qwen_thinking(prompt, settings.model)
    if stream_callback:
        stream_callback(f"\n\n[第三层专题深审·{definition.label}]\n")
    response = (
        call_chat_completion_stream(
            base_url=settings.base_url,
            model=settings.model,
            api_key=settings.api_key,
            system_prompt="你是政府采购招标文件专题深审助手，只输出合法 JSON。",
            user_prompt=prompt,
            temperature=settings.temperature,
            max_tokens=min(settings.max_tokens, 3200),
            timeout=settings.timeout,
            on_text=stream_callback,
        )
        if stream_callback
        else call_chat_completion(
            base_url=settings.base_url,
            model=settings.model,
            api_key=settings.api_key,
            system_prompt="你是政府采购招标文件专题深审助手，只输出合法 JSON。",
            user_prompt=prompt,
            temperature=settings.temperature,
            max_tokens=min(settings.max_tokens, 3200),
            timeout=settings.timeout,
        )
    )
    raw_output = extract_response_text(response) or ""
    payload = _parse_topic_json(raw_output)

    risk_points: list[RiskPoint] = []
    for item in payload.get("risk_points", []):
        if isinstance(item, dict):
            risk_points.append(_to_risk_point(item, definition.label))

    missing_evidence = _to_list(payload.get("missing_evidence"), "未发现")
    return TopicReviewArtifact(
        topic=definition.key,
        summary=str(payload.get("summary", "")).strip() or f"{definition.label}专题已完成。",
        risk_points=risk_points,
        need_manual_review=bool(payload.get("need_manual_review", False)),
        coverage_note=str(payload.get("coverage_note", "")).strip() or coverage_note,
        raw_output=raw_output,
        metadata={
            "topic_label": definition.label,
            "topic_priority": definition.priority,
            "topic_mode": topic_mode,
            "topic_execution_plan": execution_plan,
            "selected_sections": [
                {
                    "title": section.get("title", ""),
                    "start_line": section.get("start_line"),
                    "end_line": section.get("end_line"),
                    "module": section.get("module", ""),
                }
                for section in sections
            ],
            "missing_evidence": missing_evidence,
            "evidence_bundle": bundle,
            "topic_coverage": coverage,
        },
    )


def run_topic_reviews(
    document_name: str,
    evidence: V2StageArtifact,
    settings: ReviewSettings,
    topic_mode: str = "default",
    topic_keys: tuple[str, ...] | list[str] | None = None,
    stream_callback: Callable[[str], None] | None = None,
) -> list[TopicReviewArtifact]:
    plan = resolve_topic_execution_plan(topic_mode=topic_mode, topic_keys=topic_keys)
    definitions = resolve_topic_definitions(topic_mode=topic_mode, topic_keys=topic_keys)
    execution_plan = {
        "mode": plan.mode,
        "requested_keys": list(plan.requested_keys),
        "selected_keys": list(plan.selected_keys),
        "skipped_keys": list(plan.skipped_keys),
        "max_topic_calls": plan.max_topic_calls,
        "reason": plan.reason,
    }
    return [
        _run_single_topic(
            definition=definition,
            document_name=document_name,
            evidence=evidence,
            settings=settings,
            topic_mode=topic_mode,
            execution_plan=execution_plan,
            stream_callback=stream_callback,
        )
        for definition in definitions
    ]
