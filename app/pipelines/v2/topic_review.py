from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.common.core import maybe_disable_qwen_thinking
from app.common.llm_client import call_chat_completion, extract_response_text
from app.common.schemas import RiskPoint
from app.config import ReviewSettings

from .prompts.topic_contract import TOPIC_CONTRACT_PROMPT
from .prompts.topic_qualification import TOPIC_QUALIFICATION_PROMPT
from .prompts.topic_scoring import TOPIC_SCORING_PROMPT
from .prompts.topic_technical import TOPIC_TECHNICAL_PROMPT
from .schemas import TopicReviewArtifact, V2StageArtifact


JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)


@dataclass(frozen=True)
class TopicDefinition:
    key: str
    label: str
    prompt: str
    modules: tuple[str, ...]
    keywords: tuple[str, ...]


TOPIC_DEFINITIONS = (
    TopicDefinition(
        key="qualification",
        label="资格条件",
        prompt=TOPIC_QUALIFICATION_PROMPT,
        modules=("qualification", "procedure"),
        keywords=("资格", "资质", "业绩", "证书", "奖项", "人员", "社保", "信用"),
    ),
    TopicDefinition(
        key="scoring",
        label="评分办法",
        prompt=TOPIC_SCORING_PROMPT,
        modules=("scoring",),
        keywords=("评分", "评标", "评审", "分值", "样品", "演示", "答辩", "最低评标价"),
    ),
    TopicDefinition(
        key="contract",
        label="合同履约",
        prompt=TOPIC_CONTRACT_PROMPT,
        modules=("contract", "acceptance", "procedure"),
        keywords=("付款", "支付", "验收", "履约", "违约", "保证金", "质疑", "解释权", "合同", "商务"),
    ),
    TopicDefinition(
        key="technical",
        label="技术细节",
        prompt=TOPIC_TECHNICAL_PROMPT,
        modules=("technical", "acceptance"),
        keywords=("技术", "参数", "标准", "品牌", "型号", "检测", "CMA", "CNAS", "样品", "GB", "GB/T"),
    ),
)


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
            "risk_points": [],
        }
    if not isinstance(data, dict):
        return {
            "summary": "模型输出结构异常，需人工复核。",
            "need_manual_review": True,
            "coverage_note": "模型返回顶层不是对象。",
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


def _select_sections(extracted_text: str, structure: V2StageArtifact, definition: TopicDefinition) -> list[dict]:
    sections = structure.metadata.get("sections", []) if structure.metadata else []
    ranked: list[tuple[int, dict]] = []
    for section in sections:
        title = str(section.get("title", ""))
        excerpt = str(section.get("excerpt", ""))
        module = str(section.get("module", ""))
        haystack = f"{title}\n{excerpt}"
        keyword_hits = sum(haystack.count(word) for word in definition.keywords)
        module_bonus = 12 if module in definition.modules else 0
        confidence_bonus = min(int(section.get("confidence", 0) or 0), 12)
        length_bonus = min(max(len(excerpt) // 80, 0), 8)
        line_span = max(int(section.get("end_line", 0) or 0) - int(section.get("start_line", 0) or 0), 0)
        span_bonus = min(line_span // 3, 6)
        score = keyword_hits * 4 + module_bonus + confidence_bonus + length_bonus + span_bonus
        if any(word in title for word in definition.keywords):
            score += 10
        if module in definition.modules and line_span >= 3:
            score += 8
        if score > 0:
            ranked.append((score, section))
    if ranked:
        ranked.sort(
            key=lambda item: (
                item[0],
                int(item[1].get("end_line", 0) or 0) - int(item[1].get("start_line", 0) or 0),
                len(str(item[1].get("excerpt", ""))),
            ),
            reverse=True,
        )
        return [section for _, section in ranked[:6]]

    lines = extracted_text.splitlines()
    fallback: list[dict] = []
    for index, line in enumerate(lines):
        if any(word in line for word in definition.keywords):
            start = max(0, index - 3)
            end = min(len(lines), index + 6)
            fallback.append(
                {
                    "title": f"关键词命中片段 {len(fallback) + 1}",
                    "start_line": start + 1,
                    "end_line": end,
                    "module": "fallback",
                    "keywords": [word for word in definition.keywords if word in line][:5],
                    "excerpt": "\n".join(lines[start:end]).strip(),
                }
            )
            if len(fallback) >= 5:
                break
    return fallback


def _build_topic_prompt(document_name: str, topic: TopicDefinition, sections: list[dict]) -> str:
    evidence_blocks = "\n\n".join(
        [f"[证据{index}]\n{_snippet_from_section(section)}" for index, section in enumerate(sections, start=1)]
    ) or "未发现相关证据片段。"

    schema = {
        "summary": "专题结论摘要",
        "need_manual_review": False,
        "coverage_note": "本专题召回范围说明",
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
        f"专题名称：{topic.label}\n\n"
        "JSON 结构示例：\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        "证据片段如下：\n"
        f"{evidence_blocks}\n"
    )


def _run_single_topic(
    definition: TopicDefinition,
    document_name: str,
    extracted_text: str,
    structure: V2StageArtifact,
    settings: ReviewSettings,
) -> TopicReviewArtifact:
    sections = _select_sections(extracted_text, structure, definition)
    coverage_note = f"召回 {len(sections)} 个相关章节/片段。"
    if not sections:
        return TopicReviewArtifact(
            topic=definition.key,
            summary=f"{definition.label}专题未召回到足够证据，需人工复核。",
            need_manual_review=True,
            coverage_note=coverage_note,
            raw_output="",
            metadata={"selected_sections": []},
        )

    prompt = _build_topic_prompt(document_name, definition, sections)
    prompt = maybe_disable_qwen_thinking(prompt, settings.model)
    response = call_chat_completion(
        base_url=settings.base_url,
        model=settings.model,
        api_key=settings.api_key,
        system_prompt="你是政府采购招标文件专题深审助手，只输出合法 JSON。",
        user_prompt=prompt,
        temperature=settings.temperature,
        max_tokens=min(settings.max_tokens, 3200),
        timeout=settings.timeout,
    )
    raw_output = extract_response_text(response) or ""
    payload = _parse_topic_json(raw_output)

    risk_points: list[RiskPoint] = []
    for item in payload.get("risk_points", []):
        if isinstance(item, dict):
            risk_points.append(_to_risk_point(item, definition.label))

    return TopicReviewArtifact(
        topic=definition.key,
        summary=str(payload.get("summary", "")).strip() or f"{definition.label}专题已完成。",
        risk_points=risk_points,
        need_manual_review=bool(payload.get("need_manual_review", False)),
        coverage_note=str(payload.get("coverage_note", "")).strip() or coverage_note,
        raw_output=raw_output,
        metadata={
            "selected_sections": [
                {
                    "title": section.get("title", ""),
                    "start_line": section.get("start_line"),
                    "end_line": section.get("end_line"),
                    "module": section.get("module", ""),
                }
                for section in sections
            ]
        },
    )


def run_topic_reviews(
    document_name: str,
    extracted_text: str,
    structure: V2StageArtifact,
    settings: ReviewSettings,
) -> list[TopicReviewArtifact]:
    return [
        _run_single_topic(
            definition=definition,
            document_name=document_name,
            extracted_text=extracted_text,
            structure=structure,
            settings=settings,
        )
        for definition in TOPIC_DEFINITIONS
    ]
