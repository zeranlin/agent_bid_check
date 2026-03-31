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
SCORING_TIER_RE = re.compile(r"(优|良|中|差|一般)\s*(得|计)?\s*\d+\s*分")
SCORING_SUBJECTIVE_SIGNALS = ("综合打分", "综合印象打分", "由评委综合打分", "酌情计分", "结合项目实际确定")
TOPIC_FAILURE_REASON_LABELS = {
    "missing_evidence": "证据不足",
    "topic_not_triggered": "专题未触发",
    "risk_not_extracted": "专题未抽出风险",
    "degraded_to_manual_review": "已降级为人工复核",
}


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


def _build_scoring_fallback_risk(sections: list[dict]) -> RiskPoint | None:
    fragments: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        fragments.extend(
            [
                str(section.get("title", "")).strip(),
                str(section.get("excerpt", "")).strip(),
                str(section.get("body", "")).strip(),
            ]
        )
    combined_text = "\n".join(fragment for fragment in fragments if fragment)
    if not combined_text.strip():
        return None

    has_tier_signal = bool(SCORING_TIER_RE.search(combined_text))
    has_subjective_signal = any(signal in combined_text for signal in SCORING_SUBJECTIVE_SIGNALS)
    if not has_tier_signal and not has_subjective_signal:
        return None

    source_section = next((section for section in sections if isinstance(section, dict)), {})
    source_location = (
        f"{source_section.get('title', '未发现')} 第{source_section.get('start_line', '?')}-{source_section.get('end_line', '?')}行"
        if source_section
        else "未发现"
    )
    source_excerpt = str(source_section.get("excerpt", "")).strip() or "未发现"
    title = "评分档次缺少量化口径" if has_tier_signal else "主观分值裁量空间过大"
    judgments = []
    if has_tier_signal:
        judgments.append("评分分档存在“优、良、中、差”或类似档次，但缺少与各档对应的量化判定标准。")
    if has_subjective_signal:
        judgments.append("条款包含“综合打分”“酌情计分”等表述，评委自由裁量空间较大。")
    return RiskPoint(
        title=title,
        severity="中风险",
        review_type="评分标准不明确",
        source_location=source_location,
        source_excerpt=source_excerpt,
        risk_judgment=judgments or ["评分标准不够明确，需补充量化口径。"],
        legal_basis=["需人工复核"],
        rectification=["补充各评分档次对应的量化标准，并压缩主观裁量空间。"],
    )


def _normalize_missing_evidence_items(value: object) -> list[str]:
    items = _to_list(value, "未发现")
    return [item for item in items if item.strip() and item.strip() != "未发现"]


def _should_tighten_manual_review(payload: dict, risk_points: list[RiskPoint]) -> bool:
    if not bool(payload.get("need_manual_review", False)):
        return False
    if not risk_points:
        return False
    if _normalize_missing_evidence_items(payload.get("missing_evidence")):
        return False
    if any(risk.severity == "需人工复核" for risk in risk_points):
        return False
    return True


def _build_topic_failure_reasons(
    *,
    selected_sections: list[dict],
    missing_evidence: list[str],
    need_manual_review: bool,
    degraded: bool,
    recovered_by_fallback: bool,
) -> list[str]:
    reasons: list[str] = []
    if not selected_sections:
        reasons.append("topic_not_triggered")
    if missing_evidence:
        reasons.append("missing_evidence")
    if degraded or (need_manual_review and missing_evidence):
        reasons.append("degraded_to_manual_review")
    if recovered_by_fallback:
        reasons.append("risk_not_extracted")
    return list(dict.fromkeys(reasons))


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
    summary: str | None = None,
    missing_evidence: list[str] | None = None,
    raw_output: str = "",
    error_type: str = "missing_evidence",
) -> TopicReviewArtifact:
    sections = bundle.get("sections", []) if isinstance(bundle, dict) else []
    missing_items = list(missing_evidence or (coverage.get("missing_hints", []) if isinstance(coverage, dict) else []))
    failure_reasons = _build_topic_failure_reasons(
        selected_sections=[],
        missing_evidence=[item for item in missing_items if item and item != "未发现"],
        need_manual_review=True,
        degraded=True,
        recovered_by_fallback=False,
    )
    return TopicReviewArtifact(
        topic=definition.key,
        summary=summary or f"{definition.label}专题未召回到足够证据，需人工复核。",
        need_manual_review=True,
        coverage_note=_build_default_coverage_note(sections, coverage),
        raw_output=raw_output,
        metadata={
            "topic_label": definition.label,
            "topic_priority": definition.priority,
            "topic_mode": topic_mode,
            "topic_execution_plan": execution_plan,
            "selected_sections": [],
            "missing_evidence": missing_items,
            "failure_reasons": failure_reasons,
            "failure_reason_labels": [TOPIC_FAILURE_REASON_LABELS.get(reason, reason) for reason in failure_reasons],
            "evidence_bundle": bundle,
            "topic_coverage": coverage,
            "degraded": True,
            "degrade_reason": error_type,
        },
    )


def _postprocess_topic_payload(
    definition: TopicDefinition,
    payload: dict,
    bundle: dict,
) -> tuple[dict, list[RiskPoint], list[str]]:
    risk_points: list[RiskPoint] = []
    failure_reasons: list[str] = []
    for item in payload.get("risk_points", []):
        if isinstance(item, dict):
            risk_points.append(_to_risk_point(item, definition.label))

    sections = bundle.get("sections", []) if isinstance(bundle, dict) else []
    if definition.key == "scoring" and not risk_points and not bool(payload.get("need_manual_review", False)):
        fallback = _build_scoring_fallback_risk(sections)
        if fallback:
            risk_points.append(fallback)
            failure_reasons.append("risk_not_extracted")
            summary = str(payload.get("summary", "")).strip()
            payload["summary"] = summary or "评分办法专题完成，并根据评分分档表述补出明确风险。"
            payload["coverage_note"] = str(payload.get("coverage_note", "")).strip() or "已覆盖评分分档与主观评分条款。"
            payload["need_manual_review"] = False
            payload["missing_evidence"] = ["未发现"]

    if _should_tighten_manual_review(payload, risk_points):
        payload["need_manual_review"] = False
        payload["missing_evidence"] = ["未发现"]

    return payload, risk_points, failure_reasons


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
    try:
        response = (
            call_chat_completion_stream(
                base_url=settings.base_url,
                model=settings.model,
                api_key=settings.api_key,
                system_prompt="你是政府采购招标文件专题深审助手，只输出合法 JSON。",
                user_prompt=prompt,
                temperature=settings.temperature,
                max_tokens=min(settings.max_tokens, int(execution_plan.get("per_topic_max_tokens", 3200) or 3200)),
                timeout=min(settings.timeout, int(execution_plan.get("per_topic_timeout", settings.timeout) or settings.timeout)),
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
                max_tokens=min(settings.max_tokens, int(execution_plan.get("per_topic_max_tokens", 3200) or 3200)),
                timeout=min(settings.timeout, int(execution_plan.get("per_topic_timeout", settings.timeout) or settings.timeout)),
            )
        )
    except Exception as exc:
        if not execution_plan.get("allow_degrade_on_error", True):
            raise
        return _build_empty_topic_artifact(
            definition,
            bundle,
            coverage,
            topic_mode,
            execution_plan,
            summary=f"{definition.label}专题调用失败，已自动降级为人工复核。",
            missing_evidence=[f"专题调用失败：{exc}"],
            raw_output="",
            error_type="topic_call_failed",
        )
    raw_output = extract_response_text(response) or ""
    payload = _parse_topic_json(raw_output)
    payload, risk_points, postprocess_failure_reasons = _postprocess_topic_payload(definition, payload, bundle)

    missing_evidence = _to_list(payload.get("missing_evidence"), "未发现")
    normalized_missing_evidence = _normalize_missing_evidence_items(payload.get("missing_evidence"))
    selected_sections = [
        {
            "title": section.get("title", ""),
            "start_line": section.get("start_line"),
            "end_line": section.get("end_line"),
            "module": section.get("module", ""),
        }
        for section in sections
    ]
    failure_reasons = _build_topic_failure_reasons(
        selected_sections=selected_sections,
        missing_evidence=normalized_missing_evidence,
        need_manual_review=bool(payload.get("need_manual_review", False)),
        degraded=False,
        recovered_by_fallback=bool(postprocess_failure_reasons),
    )
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
            "selected_sections": selected_sections,
            "missing_evidence": missing_evidence,
            "failure_reasons": failure_reasons,
            "failure_reason_labels": [TOPIC_FAILURE_REASON_LABELS.get(reason, reason) for reason in failure_reasons],
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
        "per_topic_timeout": plan.per_topic_timeout,
        "per_topic_max_tokens": plan.per_topic_max_tokens,
        "allow_degrade_on_error": plan.allow_degrade_on_error,
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
