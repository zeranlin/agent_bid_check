from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

from app.common.core import maybe_disable_qwen_thinking
from app.common.llm_client import call_chat_completion, call_chat_completion_stream, extract_response_text
from app.config import ReviewSettings

from .prompts.structure import STRUCTURE_LAYER_NOTE, STRUCTURE_LLM_SYSTEM_PROMPT, STRUCTURE_LLM_USER_PROMPT
from .schemas import ModuleHit, SectionCandidate, V2StageArtifact


HEADING_RE = re.compile(
    r"^(第[一二三四五六七八九十百零0-9]+[章节编部分卷篇]|[一二三四五六七八九十]+[、.]|[（(][一二三四五六七八九十0-9]+[）)]).+"
)
JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)
MODULES = ("qualification", "scoring", "contract", "acceptance", "technical", "procedure", "policy")
LLM_REVIEW_LIMIT = 8
RULE_CONFIDENCE_THRESHOLD = 3
RULE_MARGIN_THRESHOLD = 1

MODULE_KEYWORDS = {
    "qualification": ["资格", "资质", "业绩", "证书", "奖项", "人员", "项目经理", "社保", "信用"],
    "scoring": ["评分", "评标", "评审", "分值", "综合评分", "最低评标价", "样品评分", "演示", "答辩"],
    "contract": ["付款", "支付", "履约", "保证金", "违约", "质疑", "解释权", "合同", "商务", "结算"],
    "acceptance": ["验收", "竣工", "交付", "检测", "试运行"],
    "technical": ["技术", "参数", "标准", "样品", "品牌", "型号", "检测报告", "CMA", "CNAS", "施工"],
    "procedure": ["投标", "开标", "响应文件", "澄清", "截止时间", "递交", "公告", "程序"],
    "policy": ["政府采购", "中小企业", "节能", "环保", "政策", "采购法", "财政部"],
}


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if HEADING_RE.match(stripped):
        return True
    return len(stripped) <= 28 and any(key in stripped for key in ("资格", "评分", "商务", "技术", "验收", "付款", "合同"))


def _heading_level(line: str) -> int:
    stripped = line.strip()
    if not stripped:
        return 0
    if stripped.startswith("第") and any(token in stripped for token in ("章", "节", "编", "部分", "卷", "篇")):
        return 1
    if re.match(r"^[一二三四五六七八九十]+[、.]", stripped):
        return 2
    if re.match(r"^[（(][一二三四五六七八九十0-9]+[）)]", stripped):
        return 3
    if _is_heading(stripped):
        return 2
    return 0


def _score_modules(title: str, body: str) -> tuple[str, dict[str, int], list[ModuleHit]]:
    text = f"{title}\n{body}"
    scores: dict[str, int] = {}
    hits: list[ModuleHit] = []
    for module, words in MODULE_KEYWORDS.items():
        score = 0
        matched_keywords: list[str] = []
        for word in words:
            count = text.count(word)
            score += count
            if count > 0:
                matched_keywords.append(word)
        scores[module] = score
        if score > 0:
            hits.append(
                ModuleHit(
                    module=module,
                    score=float(score),
                    source="keyword_rule",
                    reason=f"标题及正文命中 {len(matched_keywords)} 个关键词。",
                    evidence_keywords=matched_keywords[:8],
                )
            )
    top_module = max(scores, key=scores.get) if scores else "procedure"
    if scores.get(top_module, 0) <= 0:
        top_module = "procedure"
    hits.sort(key=lambda item: item.score, reverse=True)
    return top_module, scores, hits


def _rule_margin(scores: dict[str, int]) -> int:
    ordered = sorted(scores.values(), reverse=True)
    if len(ordered) < 2:
        return ordered[0] if ordered else 0
    return ordered[0] - ordered[1]


def _build_sections(extracted_text: str) -> list[SectionCandidate]:
    lines = extracted_text.splitlines()
    if not lines:
        return []
    sections: list[dict[str, object]] = []
    start = 0
    current_title = lines[0].strip()[:120] if _is_heading(lines[0]) else "文档起始"
    for index, line in enumerate(lines):
        if index == 0:
            continue
        if _is_heading(line):
            sections.append(
                {
                    "title": current_title,
                    "start_line": start + 1,
                    "end_line": index,
                    "body": "\n".join(lines[start:index]).strip(),
                }
            )
            current_title = line.strip()[:120]
            start = index
    sections.append(
        {
            "title": current_title,
            "start_line": start + 1,
            "end_line": len(lines),
            "body": "\n".join(lines[start:]).strip(),
        }
    )

    normalized: list[SectionCandidate] = []
    for section in sections:
        title = str(section["title"]).strip()
        body = str(section["body"]).strip()
        if not body:
            continue
        top_module, scores, _ = _score_modules(title, body)
        keywords = [word for word in MODULE_KEYWORDS.get(top_module, []) if word in body or word in title][:6]
        normalized.append(
            SectionCandidate(
                title=title,
                start_line=int(section["start_line"]),
                end_line=int(section["end_line"]),
                body=body,
                excerpt=body[:800],
                module=top_module,
                module_scores=scores,
                confidence=max(scores.values()) if scores else 0,
                keywords=keywords,
                heading_level=_heading_level(title),
                source="rule_split",
            )
        )
    return normalized


def _needs_llm_review(section: SectionCandidate) -> bool:
    if section.source == "llm_refined":
        return False
    if section.confidence <= RULE_CONFIDENCE_THRESHOLD:
        return True
    return _rule_margin(section.module_scores) <= RULE_MARGIN_THRESHOLD


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


def _parse_llm_payload(text: str) -> dict:
    payload = _extract_json_block(text)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {"sections": []}
    return data if isinstance(data, dict) else {"sections": []}


def _build_llm_prompt(sections: list[SectionCandidate]) -> str:
    section_blocks = []
    for index, section in enumerate(sections, start=1):
        module_scores = ", ".join(f"{module}:{score}" for module, score in section.module_scores.items() if score > 0) or "无"
        section_blocks.append(
            "\n".join(
                [
                    f"[片段{index}]",
                    f"index: {index}",
                    f"title: {section.title}",
                    f"line_range: {section.start_line}-{section.end_line}",
                    f"rule_module: {section.module}",
                    f"rule_confidence: {section.confidence}",
                    f"rule_scores: {module_scores}",
                    "excerpt:",
                    section.excerpt[:600] or "未发现",
                ]
            )
        )
    return f"{STRUCTURE_LLM_USER_PROMPT.strip()}\n\n" + "\n\n".join(section_blocks)


def _run_llm_refine(
    sections: list[SectionCandidate],
    settings: ReviewSettings,
    stream_callback: Callable[[str], None] | None = None,
) -> tuple[dict[int, dict], bool]:
    if not sections:
        return {}, False
    prompt = maybe_disable_qwen_thinking(_build_llm_prompt(sections), settings.model)
    try:
        response = (
            call_chat_completion_stream(
                base_url=settings.base_url,
                model=settings.model,
                api_key=settings.api_key,
                system_prompt=STRUCTURE_LLM_SYSTEM_PROMPT,
                user_prompt=prompt,
                temperature=0.0,
                max_tokens=min(settings.max_tokens, 1600),
                timeout=min(settings.timeout, 120),
                on_text=stream_callback,
            )
            if stream_callback
            else call_chat_completion(
                base_url=settings.base_url,
                model=settings.model,
                api_key=settings.api_key,
                system_prompt=STRUCTURE_LLM_SYSTEM_PROMPT,
                user_prompt=prompt,
                temperature=0.0,
                max_tokens=min(settings.max_tokens, 1600),
                timeout=min(settings.timeout, 120),
            )
        )
    except Exception:
        return {}, True

    raw_output = extract_response_text(response) or ""
    payload = _parse_llm_payload(raw_output)
    result: dict[int, dict] = {}
    for item in payload.get("sections", []):
        if not isinstance(item, dict):
            continue
        index = int(item.get("index", 0) or 0)
        if index <= 0 or index > len(sections):
            continue
        module = str(item.get("module", "")).strip()
        if module not in MODULES:
            continue
        confidence = item.get("confidence", 0.0)
        try:
            confidence_value = float(confidence)
        except (TypeError, ValueError):
            confidence_value = 0.0
        keywords = [str(keyword).strip() for keyword in item.get("keywords", []) if str(keyword).strip()][:4]
        result[index - 1] = {
            "module": module,
            "confidence": max(0.0, min(confidence_value, 1.0)),
            "reason": str(item.get("reason", "")).strip(),
            "keywords": keywords,
        }
    return result, False


def _refine_sections_with_llm(
    sections: list[SectionCandidate],
    settings: ReviewSettings,
    stream_callback: Callable[[str], None] | None = None,
) -> tuple[list[SectionCandidate], bool, bool]:
    candidate_indexes = [index for index, section in enumerate(sections) if _needs_llm_review(section)]
    if not candidate_indexes:
        return sections, False, False

    limited_indexes = candidate_indexes[:LLM_REVIEW_LIMIT]
    llm_results, fallback_used = _run_llm_refine(
        [sections[index] for index in limited_indexes],
        settings,
        stream_callback=stream_callback,
    )
    if not llm_results:
        return sections, bool(limited_indexes), fallback_used or bool(limited_indexes)

    for batch_index, section_index in enumerate(limited_indexes):
        payload = llm_results.get(batch_index)
        if not payload:
            continue
        section = sections[section_index]
        llm_module = payload["module"]
        llm_confidence = payload["confidence"]
        llm_reason = payload["reason"] or "LLM 根据章节语义进行了模块复判。"
        llm_keywords = payload["keywords"]

        section.module = llm_module
        section.source = "llm_refined"
        section.keywords = llm_keywords or section.keywords
        section.module_scores = {**section.module_scores, llm_module: max(section.module_scores.get(llm_module, 0), int(round(llm_confidence * 10)))}
        section.confidence = max(section.confidence, int(round(llm_confidence * 10)))

        existing_modules = {section.module}
        augmented_hits = [
            ModuleHit(
                module=llm_module,
                score=round(llm_confidence, 3),
                source="llm_refine",
                reason=llm_reason,
                evidence_keywords=llm_keywords,
            )
        ]
        _, _, rule_hits = _score_modules(section.title, section.body)
        for hit in rule_hits:
            if hit.module in existing_modules:
                continue
            augmented_hits.append(hit)
        section.module_scores = dict(sorted(section.module_scores.items(), key=lambda item: item[1], reverse=True))
        section.body = section.body
        section.excerpt = section.excerpt or section.body[:800]
        setattr(section, "_module_hits_override", augmented_hits[:4])
    return sections, True, fallback_used


def _serialize_sections(sections: list[SectionCandidate]) -> list[dict]:
    serialized: list[dict] = []
    for section in sections:
        payload = section.to_dict()
        override_hits = getattr(section, "_module_hits_override", None)
        if override_hits is not None:
            payload["module_hits"] = [hit.to_dict() for hit in override_hits]
        else:
            _, _, hits = _score_modules(section.title, section.body)
            payload["module_hits"] = [hit.to_dict() for hit in hits[:4]]
        serialized.append(payload)
    return serialized


def build_structure_map(
    input_path: Path,
    extracted_text: str,
    settings: ReviewSettings,
    use_llm: bool = True,
    stream_callback: Callable[[str], None] | None = None,
) -> V2StageArtifact:
    sections = _build_sections(extracted_text)
    if use_llm:
        sections, structure_llm_used, structure_fallback_used = _refine_sections_with_llm(
            sections,
            settings,
            stream_callback=stream_callback,
        )
    else:
        structure_llm_used = False
        structure_fallback_used = False
    serialized_sections = _serialize_sections(sections)
    content = json.dumps(
        {
            "document_name": input_path.name,
            "structure_status": "ready",
            "review_model": settings.model,
            "notes": [line.strip("- ").strip() for line in STRUCTURE_LAYER_NOTE.splitlines() if line.strip()],
            "structure_llm_used": structure_llm_used,
            "structure_fallback_used": structure_fallback_used,
            "sections": serialized_sections,
        },
        ensure_ascii=False,
        indent=2,
    )
    return V2StageArtifact(
        name="structure",
        content=content,
        raw_output=content,
        metadata={
            "section_count": len(sections),
            "sections": serialized_sections,
            "section_candidates": [section.to_dict() for section in sections],
            "structure_llm_used": structure_llm_used,
            "structure_fallback_used": structure_fallback_used,
        },
    )
