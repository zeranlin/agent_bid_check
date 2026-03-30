from __future__ import annotations

import json
import re
from pathlib import Path

from app.config import ReviewSettings

from .prompts.structure import STRUCTURE_LAYER_NOTE
from .schemas import ModuleHit, SectionCandidate, V2StageArtifact


HEADING_RE = re.compile(
    r"^(第[一二三四五六七八九十百零0-9]+[章节编部分卷篇]|[一二三四五六七八九十]+[、.]|[（(][一二三四五六七八九十0-9]+[）)]).+"
)

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


def _build_sections(extracted_text: str) -> list[SectionCandidate]:
    lines = extracted_text.splitlines()
    sections: list[dict[str, object]] = []
    start = 0
    current_title = "文档起始"
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
        top_module, scores, hits = _score_modules(title, body)
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


def _serialize_sections(sections: list[SectionCandidate]) -> list[dict]:
    serialized: list[dict] = []
    for section in sections:
        payload = section.to_dict()
        _, _, hits = _score_modules(section.title, section.body)
        payload["module_hits"] = [hit.to_dict() for hit in hits[:4]]
        serialized.append(payload)
    return serialized


def build_structure_map(input_path: Path, extracted_text: str, settings: ReviewSettings) -> V2StageArtifact:
    sections = _build_sections(extracted_text)
    serialized_sections = _serialize_sections(sections)
    content = json.dumps(
        {
            "document_name": input_path.name,
            "structure_status": "ready",
            "review_model": settings.model,
            "notes": [line.strip("- ").strip() for line in STRUCTURE_LAYER_NOTE.splitlines() if line.strip()],
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
        },
    )
