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
QUALIFICATION_LOCAL_SERVICE_RE = re.compile(r"(本市|当地|项目所在地).{0,8}(常设服务机构|服务机构|驻点|驻场)")
QUALIFICATION_PERFORMANCE_RE = re.compile(r"(同类项目业绩不少于\d+项|近三年同类业绩不少于\d+项|项目负责人须具备.+(职称|社保|证书))")
TECHNICAL_STANDARD_MISMATCH_RE = re.compile(r"(人造草\s*GB\s*36246-2018|人工材料体育场地使用要求及检验方法（?GB/T\s*20033-2006）?)")
TECHNICAL_STANDARD_OBSOLETE_RE = re.compile(r"GB/T\s*1040\.2-2006")
TECHNICAL_STANDARD_METHOD_MISMATCH_RE = re.compile(
    r"(检测方法|试验方法).{0,24}(作为交付验收依据|检测报告|验收依据)|"
    r"(透水率试验方法|塑料薄膜和薄片透水率试验方法)"
)
CONTRACT_PAYMENT_FISCAL_RE = re.compile(r"财政资金.{0,10}(到位|拨付)")
CONTRACT_PAYMENT_ACCEPTANCE_RE = re.compile(r"((终验|最终验收|审计).{0,12}(后|通过后)|验收.{0,8}(后|通过后).{0,8}(60|90|120)个工作日).{0,12}(支付|付款)")
CONTRACT_PAYMENT_DELAY_RE = re.compile(r"(60|90|120)个工作日内(支付|付款)")
IMPORT_REJECT_RE = re.compile(
    r"(不接受.{0,12}进口产品|拒绝进口|不允许选用进口产品|本项目不允许选用进口产品|仅接受国产|只接受国产)"
)
IMPORT_ACCEPT_RE = re.compile(
    r"((?<!不)(?<!拒绝)接受进口产品参与投标|允许进口产品参与投标|可采购进口产品|允许选用进口产品|(?<!不)(?<!拒绝)接受进口)"
)
FOREIGN_STANDARD_REF_RE = re.compile(
    r"\b(?:BS\s*EN|EN|IEC|ISO|ANSI|UL|DIN|ASTM|JIS|CISPR)\s*[A-Z0-9.-]*\d+(?:[./-]\d+)*(?::\d{4}|\-\d{4})?",
    re.IGNORECASE,
)
CN_STANDARD_REF_RE = re.compile(
    r"\b(?:GB/T|GB|YY/T|YY|HJ/T|HJ|GA/T|GA|JB/T|JB|SJ/T|SJ|DL/T|DL|HG/T|HG|CJ/T|CJ|QB/T|QB|JGJ|JT/T|JT)\s*[A-Z0-9.-]*\d+(?:[./-]\d+)*(?::\d{4}|\-\d{4})?",
    re.IGNORECASE,
)
EQUIVALENT_STANDARD_RE = re.compile(
    r"(等效标准.{0,8}(可接受|均可接受)|满足同等技术要求的等效标准均可接受|同等标准均可接受|或同等标准|等同或优于上述标准)"
)
STAR_RULE_GB_NON_T_RE = re.compile(r"(含有\s*GB\s*[（(]?\s*不含\s*GB/T\s*[)）]?|GB\s*[（(]?\s*不含\s*GB/T\s*[)）]?)")
STAR_RULE_MANDATORY_STANDARD_RE = re.compile(r"(国家强制性标准|强制性标准)")
STAR_RULE_REQUIREMENT_RE = re.compile(r"(需含有?★号|应标注★|需标注★|实质性条款需加★|必须加注★|应加注★)")
ACCEPTANCE_PLAN_FORBIDDEN_RE = re.compile(
    r"(不得将项目验收方案作为评审因素|验收方案不得纳入评分|验收移交方案不得作为评审项|验收资料不得作为评分因素|"
    r"不得将.{0,16}(项目)?验收(方案|移交方案|资料|资料移交安排).{0,12}(作为评审因素|纳入评分|作为评审项|作为评分因素))"
)
PAYMENT_TERMS_FORBIDDEN_RE = re.compile(
    r"(不得将付款方式作为评审因素|付款方式不得纳入评分|付款条件不得作为评分项|付款条款不得作为评审因素|"
    r"不得将.{0,16}付款(方式|条件|条款).{0,12}(作为评审因素|纳入评分|作为评分项|作为评审项))"
)
GIFTS_OR_UNRELATED_GOODS_FORBIDDEN_RE = re.compile(
    r"(不得要求提供赠品|不得要求提供回扣|不得要求提供与采购无关的其他商品|不得要求提供与采购无关的其他服务|"
    r"赠品不得作为评审因素|回扣不得纳入评分|不得要求提供赠品、回扣或者与采购无关的其他商品、服务)"
)
ACCEPTANCE_PLAN_TERM_RE = re.compile(
    r"(项目验收移交衔接方案|项目验收资料编制与移交衔接安排|项目验收方案设计|验收标准|验收流程安排|"
    r"验收资料准备节点|项目验收组织能力|验收衔接计划|验收移交方案|项目验收方案|竣工验收方案|"
    r"验收方案|项目验收|验收移交|移交衔接|验收资料|验收安排)"
)
PAYMENT_TERMS_TERM_RE = re.compile(
    r"(付款周期短于招标文件要求|预付款比例更有利于采购人资金安排|付款节点更优|支付安排优于招标文件要求|"
    r"付款周期|预付款比例|付款方式|付款条件|付款节点|支付安排|付款期限|预付款|首付款|尾款)"
)
GIFTS_OR_UNRELATED_GOODS_TERM_RE = re.compile(
    r"(额外向采购人值班室赠送台式电脑、打印机各1套|赠送台式电脑|赠送打印机|额外赠送|额外提供|赠送|赠品|"
    r"台式电脑|打印机|回扣|返利|无关商品|无关服务|值班室办公设备配置|会议保障等综合服务内容|"
    r"办公设备配置|会议保障|综合服务内容)"
)
PROCUREMENT_SUBJECT_GOODS_CONTEXT_RE = re.compile(
    r"(本项目采购标的包括|采购标的包括|采购内容包括|采购范围包括|本次采购包括|本项目包含).{0,40}(台式电脑|打印机)"
)
SCORING_SCORE_LINK_RE = re.compile(
    r"(评审内容|评审标准|评分因素|得分|加分|计分|最高得\s*\d+\s*分|最高得分|满分\s*\d+\s*分|"
    r"每体现\s*\d+\s*点加\s*\d+\s*分|每项加\s*\d+\s*分|最高加\s*\d+\s*分|予以加分|"
    r"评价为[优良中差]\s*得\s*\d+\s*分|评价为差[，,、]?\s*不得分|不得分)"
)
GB_NON_T_REF_RE = re.compile(r"\bGB(?!\s*/\s*T)\s*[- ]?[A-Z0-9.-]*\d+(?:[./-]\d+)*(?::\d{4}|\-\d{4})?", re.IGNORECASE)
GB_T_REF_RE = re.compile(r"\bGB\s*/\s*T\s*[A-Z0-9.-]*\d+(?:[./-]\d+)*(?::\d{4}|\-\d{4})?", re.IGNORECASE)
MANDATORY_STANDARD_TEXT_RE = re.compile(r"(国家强制性标准|强制性标准)")
TOPIC_FAILURE_REASON_LABELS = {
    "missing_evidence": "证据不足",
    "topic_not_triggered": "专题未触发",
    "risk_not_extracted": "专题未抽出风险",
    "degraded_to_manual_review": "已降级为人工复核",
    "evidence_enough_but_risk_missed": "证据已足够但风险未抽出",
    "topic_triggered_but_partial_miss": "专题已触发但只抽出部分风险",
    "risk_degraded_to_manual_review": "存在风险但被降级为人工复核",
    "cross_topic_shared_but_single_topic_hit": "共享证据场景下仅命中单专题",
    "foreign_standard_conflict": "拒绝进口与外标直引存在潜在冲突",
    "star_marker_missing_for_mandatory_standard": "强制性标准条款未按评审规则标注★",
    "acceptance_plan_in_scoring_forbidden": "将项目验收方案纳入评审因素",
    "payment_terms_in_scoring_forbidden": "将付款方式纳入评审因素",
    "gifts_or_unrelated_goods_in_scoring_forbidden": "将赠送额外商品作为评分条件",
}
SCORING_RELEVANCE_RE = re.compile(r"(排版美观|封面设计|版式完整|装订质量|字体美观)")
SCORING_INCONSISTENT_RE = re.compile(r"(满分\s*10\s*分.{0,20}满分\s*15\s*分|满分\s*15\s*分.{0,20}满分\s*10\s*分)")
TECHNICAL_STANDARD_PRIMARY_TITLE_SIGNALS = ("规格及技术参数", "技术参数", "技术要求", "主要技术参数", "技术规格", "参数要求")
COMPACT_IMPORT_CLAUSE_RE = re.compile(r"(本项目[^。；;\n]{0,80}(?:不接受|拒绝|允许)[^。；;\n]{0,60}进口[^。；;\n]{0,30}|(?:不接受|拒绝|允许)[^。；;\n]{0,60}进口[^。；;\n]{0,30})")
COMPACT_STANDARD_CLAUSE_RE = re.compile(r"((?:\b\d{1,2}\.\d{1,2}\b\s*[^\d。；;\n:：]{0,20}[:：]\s*)?(?:符合|满足)[^。；;\n]{0,120}?(?:标准|规范))")


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


def _collect_section_text(sections: list[dict]) -> tuple[str, dict]:
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
    source_section = next((section for section in sections if isinstance(section, dict)), {})
    return combined_text, source_section


def _section_id(section: dict) -> str:
    return f"{int(section.get('start_line', 0) or 0)}-{int(section.get('end_line', 0) or 0)}"


def _dedupe_preserve(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if str(item).strip()))


def _excerpt_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if not normalized:
        return []
    parts = re.split(r"(?<=[。；;！？!?])\s*", normalized)
    return [part.strip() for part in parts if part.strip()]


def _section_sentences(section: dict) -> list[str]:
    return _excerpt_sentences(str(section.get("excerpt", "")).strip() or str(section.get("body", "")).strip())


def _find_matching_sentences(section: dict, patterns: list[re.Pattern[str]]) -> list[str]:
    matches: list[str] = []
    for sentence in _section_sentences(section):
        if any(pattern.search(sentence) for pattern in patterns):
            matches.append(sentence)
    return _dedupe_preserve(matches)


def _find_match_fragments(section: dict, pattern: re.Pattern[str], window: int = 28) -> list[str]:
    text = re.sub(r"\s+", " ", str(section.get("excerpt", "")).strip() or str(section.get("body", "")).strip())
    if not text:
        return []
    fragments: list[str] = []
    for match in pattern.finditer(text):
        start = max(match.start() - window, 0)
        end = min(match.end() + window, len(text))
        while start > 0 and text[start - 1] not in "。；;!?！？\n":
            start -= 1
        while end < len(text) and text[end] not in "。；;!?！？\n":
            end += 1
        fragment = text[start:end].strip(" ，,;；")
        if fragment:
            fragments.append(fragment)
    return _dedupe_preserve(fragments)


def _compress_import_fragments(fragments: list[str], reject_matches: list[str], accept_matches: list[str]) -> list[str]:
    compressed: list[str] = []
    for fragment in fragments:
        match = COMPACT_IMPORT_CLAUSE_RE.search(fragment)
        if match:
            compressed.append(match.group(1).strip(" ，,;；"))
        elif len(fragment) <= 90:
            compressed.append(fragment)
    if not compressed:
        compressed.extend(reject_matches[:1])
        compressed.extend([item for item in accept_matches[:1] if item not in compressed])
    return _dedupe_preserve(compressed)


def _compress_standard_fragments(fragments: list[str], refs: list[str]) -> list[str]:
    compressed: list[str] = []
    for fragment in fragments:
        match = COMPACT_STANDARD_CLAUSE_RE.search(fragment)
        if match:
            compressed.append(match.group(1).strip(" ，,;；"))
        elif len(fragment) <= 120:
            compressed.append(fragment)
    if not compressed and refs:
        compressed.append("符合 " + "、".join(refs[:3]) + " 标准")
    return _dedupe_preserve(compressed)


def _normalize_signal_sections(sections: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title", "")).strip()
        if not title:
            continue
        normalized.append(
            {
                "section_id": _section_id(section),
                "title": title,
                "start_line": section.get("start_line"),
                "end_line": section.get("end_line"),
                "module": str(section.get("module", "")).strip(),
            }
        )
    return normalized


def _dedupe_signal_sections(sections: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id", "")).strip() or f"{section.get('title', '')}:{section.get('start_line', '')}:{section.get('end_line', '')}"
        if section_id in seen:
            continue
        seen.add(section_id)
        result.append(section)
    return result


def _has_star_marker_near_text(text: str) -> bool:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    if not compact:
        return False
    return compact.startswith("★") or " ★" in compact[:12] or "★" in compact[:8]


def _extract_import_policy_signals(sections: list[dict]) -> dict[str, object]:
    combined_text, _ = _collect_section_text(sections)
    reject_matches = _dedupe_preserve([match.group(0).strip() for match in IMPORT_REJECT_RE.finditer(combined_text)])
    accept_matches = _dedupe_preserve([match.group(0).strip() for match in IMPORT_ACCEPT_RE.finditer(combined_text)])
    matched_sections: list[dict] = []
    matched_sentences: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_sentences = _find_match_fragments(section, IMPORT_REJECT_RE) + _find_match_fragments(section, IMPORT_ACCEPT_RE)
        if section_sentences:
            matched_sections.extend(_normalize_signal_sections([section]))
            matched_sentences.extend(section_sentences)
    matched_sentences = _compress_import_fragments(matched_sentences, reject_matches, accept_matches)
    if reject_matches and accept_matches:
        policy = "mixed_or_unclear"
    elif reject_matches:
        policy = "reject_import"
    elif accept_matches:
        policy = "accept_import"
    else:
        policy = "mixed_or_unclear"
    return {
        "import_policy": policy,
        "import_policy_reject_phrases": reject_matches,
        "import_policy_accept_phrases": accept_matches,
        "import_policy_sections": matched_sections,
        "import_policy_sentences": _dedupe_preserve(matched_sentences),
    }


def _extract_standard_reference_signals(sections: list[dict]) -> dict[str, object]:
    combined_text, _ = _collect_section_text(sections)
    foreign_refs = _dedupe_preserve([match.group(0).strip() for match in FOREIGN_STANDARD_REF_RE.finditer(combined_text)])
    cn_refs = _dedupe_preserve([match.group(0).strip() for match in CN_STANDARD_REF_RE.finditer(combined_text)])
    has_equivalent_standard_clause = bool(EQUIVALENT_STANDARD_RE.search(combined_text))
    foreign_sections: list[dict] = []
    cn_sections: list[dict] = []
    equivalent_sections: list[dict] = []
    foreign_sentences: list[str] = []
    cn_sentences: list[str] = []
    equivalent_sentences: list[str] = []
    gb_non_t_sections: list[dict] = []
    gb_non_t_sentences: list[str] = []
    gbt_sections: list[dict] = []
    gbt_sentences: list[str] = []
    mandatory_standard_sections: list[dict] = []
    mandatory_standard_sentences: list[str] = []
    standard_clause_flags: list[dict[str, object]] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_foreign_sentences = _find_match_fragments(section, FOREIGN_STANDARD_REF_RE)
        section_cn_sentences = _find_match_fragments(section, CN_STANDARD_REF_RE)
        section_equivalent_sentences = _find_match_fragments(section, EQUIVALENT_STANDARD_RE)
        section_gb_non_t_sentences = _find_match_fragments(section, GB_NON_T_REF_RE)
        section_gbt_sentences = _find_match_fragments(section, GB_T_REF_RE)
        section_mandatory_sentences = _find_match_fragments(section, MANDATORY_STANDARD_TEXT_RE)
        if section_foreign_sentences:
            foreign_sections.extend(_normalize_signal_sections([section]))
            foreign_sentences.extend(section_foreign_sentences)
        if section_cn_sentences:
            cn_sections.extend(_normalize_signal_sections([section]))
            cn_sentences.extend(section_cn_sentences)
        if section_equivalent_sentences:
            equivalent_sections.extend(_normalize_signal_sections([section]))
            equivalent_sentences.extend(section_equivalent_sentences)
        if section_gb_non_t_sentences:
            gb_non_t_sections.extend(_normalize_signal_sections([section]))
            gb_non_t_sentences.extend(section_gb_non_t_sentences)
        if section_gbt_sentences:
            gbt_sections.extend(_normalize_signal_sections([section]))
            gbt_sentences.extend(section_gbt_sentences)
        if section_mandatory_sentences:
            mandatory_standard_sections.extend(_normalize_signal_sections([section]))
            mandatory_standard_sentences.extend(section_mandatory_sentences)
        clause_sentences = _dedupe_preserve(section_gb_non_t_sentences + section_gbt_sentences + section_mandatory_sentences)
        for clause in clause_sentences:
            clause_text = re.sub(r"\s+", " ", clause).strip()
            standard_clause_flags.append(
                {
                    "section_id": _section_id(section),
                    "title": str(section.get("title", "")).strip(),
                    "start_line": section.get("start_line"),
                    "end_line": section.get("end_line"),
                    "clause_text": clause_text,
                    "contains_gb_non_t": bool(GB_NON_T_REF_RE.search(clause_text)),
                    "contains_gbt": bool(GB_T_REF_RE.search(clause_text)),
                    "contains_mandatory_standard": bool(MANDATORY_STANDARD_TEXT_RE.search(clause_text)),
                    "has_star_marker": _has_star_marker_near_text(clause_text) or _has_star_marker_near_text(str(section.get("title", ""))),
                }
            )
    foreign_sentences = _compress_standard_fragments(foreign_sentences, foreign_refs)
    cn_sentences = _compress_standard_fragments(cn_sentences, cn_refs)
    if foreign_refs and cn_refs:
        standard_system_mix = "mixed_cn_foreign"
    elif foreign_refs:
        standard_system_mix = "foreign_only"
    elif cn_refs:
        standard_system_mix = "cn_only"
    else:
        standard_system_mix = "none"
    return {
        "foreign_standard_refs": foreign_refs,
        "cn_standard_refs": cn_refs,
        "has_equivalent_standard_clause": has_equivalent_standard_clause,
        "standard_system_mix": standard_system_mix,
        "foreign_standard_has_version": any(re.search(r"[:\-]\d{4}$", ref) for ref in foreign_refs),
        "foreign_standard_sections": foreign_sections,
        "foreign_standard_sentences": _dedupe_preserve(foreign_sentences),
        "cn_standard_sections": cn_sections,
        "cn_standard_sentences": _dedupe_preserve(cn_sentences),
        "equivalent_standard_sections": equivalent_sections,
        "equivalent_standard_sentences": _dedupe_preserve(equivalent_sentences),
        "contains_gb_non_t": bool(gb_non_t_sentences),
        "contains_gbt": any(bool(item.get("contains_gbt", False)) for item in standard_clause_flags),
        "contains_mandatory_standard": bool(mandatory_standard_sentences),
        "gb_non_t_sections": gb_non_t_sections,
        "gb_non_t_sentences": _dedupe_preserve(gb_non_t_sentences),
        "gbt_sections": gbt_sections,
        "gbt_sentences": _dedupe_preserve(gbt_sentences),
        "mandatory_standard_sections": mandatory_standard_sections,
        "mandatory_standard_sentences": _dedupe_preserve(mandatory_standard_sentences),
        "has_star_marker": any(bool(item.get("has_star_marker")) for item in standard_clause_flags),
        "standard_clause_flags": standard_clause_flags,
    }


def _extract_star_rule_signals(sections: list[dict]) -> dict[str, object]:
    matched_sections: list[dict] = []
    matched_sentences: list[str] = []
    star_required_for_gb_non_t = False
    star_required_for_mandatory_standard = False
    for section in sections:
        if not isinstance(section, dict):
            continue
        text = "\n".join(
            part for part in (str(section.get("title", "")).strip(), str(section.get("excerpt", "")).strip(), str(section.get("body", "")).strip()) if part
        )
        if not text:
            continue
        has_star_requirement = bool(STAR_RULE_REQUIREMENT_RE.search(text))
        has_gb_non_t_rule = bool(STAR_RULE_GB_NON_T_RE.search(text))
        has_mandatory_standard_rule = bool(STAR_RULE_MANDATORY_STANDARD_RE.search(text))
        if has_star_requirement and (has_gb_non_t_rule or has_mandatory_standard_rule):
            matched_sections.extend(_normalize_signal_sections([section]))
            matched_sentences.extend(_find_match_fragments(section, STAR_RULE_REQUIREMENT_RE))
        if has_star_requirement and has_gb_non_t_rule:
            star_required_for_gb_non_t = True
        if has_star_requirement and has_mandatory_standard_rule:
            star_required_for_mandatory_standard = True
    return {
        "star_required_for_gb_non_t": star_required_for_gb_non_t,
        "star_required_for_mandatory_standard": star_required_for_mandatory_standard,
        "star_rule_sections": _dedupe_signal_sections(matched_sections) if matched_sections else [],
        "star_rule_sentences": _dedupe_preserve(matched_sentences),
    }


def _extract_acceptance_plan_scoring_signals(sections: list[dict]) -> dict[str, object]:
    rule_sections: list[dict] = []
    rule_sentences: list[str] = []
    acceptance_sections: list[dict] = []
    acceptance_sentences: list[str] = []
    scoring_contains_acceptance_plan = False
    acceptance_plan_linked_to_score = False

    for section in sections:
        if not isinstance(section, dict):
            continue
        text = "\n".join(
            part for part in (str(section.get("title", "")).strip(), str(section.get("excerpt", "")).strip(), str(section.get("body", "")).strip()) if part
        )
        if not text:
            continue
        has_forbidden_rule = bool(ACCEPTANCE_PLAN_FORBIDDEN_RE.search(text))
        has_acceptance_term = bool(ACCEPTANCE_PLAN_TERM_RE.search(text))
        has_score_link = bool(SCORING_SCORE_LINK_RE.search(text))

        if has_forbidden_rule:
            rule_sections.extend(_normalize_signal_sections([section]))
            fragments = _find_match_fragments(section, ACCEPTANCE_PLAN_FORBIDDEN_RE)
            rule_sentences.extend(fragments or _find_match_fragments(section, SCORING_SCORE_LINK_RE))

        if has_acceptance_term:
            scoring_contains_acceptance_plan = True
            acceptance_sections.extend(_normalize_signal_sections([section]))
            acceptance_sentences.extend(_find_match_fragments(section, ACCEPTANCE_PLAN_TERM_RE))

        if has_acceptance_term and has_score_link:
            acceptance_plan_linked_to_score = True
            acceptance_sections.extend(_normalize_signal_sections([section]))
            acceptance_sentences.extend(_find_match_fragments(section, SCORING_SCORE_LINK_RE))

    return {
        "acceptance_plan_forbidden_in_scoring": bool(rule_sections),
        "acceptance_plan_rule_sections": _dedupe_signal_sections(rule_sections),
        "acceptance_plan_rule_sentences": _dedupe_preserve(rule_sentences),
        "scoring_contains_acceptance_plan": scoring_contains_acceptance_plan,
        "acceptance_plan_scoring_sections": _dedupe_signal_sections(acceptance_sections),
        "acceptance_plan_scoring_sentences": _dedupe_preserve(acceptance_sentences),
        "acceptance_plan_linked_to_score": acceptance_plan_linked_to_score,
    }


def _extract_payment_terms_scoring_signals(sections: list[dict]) -> dict[str, object]:
    rule_sections: list[dict] = []
    rule_sentences: list[str] = []
    payment_sections: list[dict] = []
    payment_sentences: list[str] = []
    scoring_contains_payment_terms = False
    payment_terms_linked_to_score = False

    for section in sections:
        if not isinstance(section, dict):
            continue
        text = "\n".join(
            part for part in (str(section.get("title", "")).strip(), str(section.get("excerpt", "")).strip(), str(section.get("body", "")).strip()) if part
        )
        if not text:
            continue
        has_forbidden_rule = bool(PAYMENT_TERMS_FORBIDDEN_RE.search(text))
        has_payment_term = bool(PAYMENT_TERMS_TERM_RE.search(text))
        has_score_link = bool(SCORING_SCORE_LINK_RE.search(text))

        if has_forbidden_rule:
            rule_sections.extend(_normalize_signal_sections([section]))
            fragments = _find_match_fragments(section, PAYMENT_TERMS_FORBIDDEN_RE)
            rule_sentences.extend(fragments or _find_match_fragments(section, SCORING_SCORE_LINK_RE))

        if has_payment_term:
            scoring_contains_payment_terms = True
            payment_sections.extend(_normalize_signal_sections([section]))
            payment_sentences.extend(_find_match_fragments(section, PAYMENT_TERMS_TERM_RE))

        if has_payment_term and has_score_link:
            payment_terms_linked_to_score = True
            payment_sections.extend(_normalize_signal_sections([section]))
            payment_sentences.extend(_find_match_fragments(section, SCORING_SCORE_LINK_RE))

    return {
        "payment_terms_forbidden_in_scoring": bool(rule_sections),
        "payment_terms_rule_sections": _dedupe_signal_sections(rule_sections),
        "payment_terms_rule_sentences": _dedupe_preserve(rule_sentences),
        "scoring_contains_payment_terms": scoring_contains_payment_terms,
        "payment_terms_scoring_sections": _dedupe_signal_sections(payment_sections),
        "payment_terms_scoring_sentences": _dedupe_preserve(payment_sentences),
        "payment_terms_linked_to_score": payment_terms_linked_to_score,
    }


def _extract_gifts_or_unrelated_goods_scoring_signals(sections: list[dict]) -> dict[str, object]:
    rule_sections: list[dict] = []
    rule_sentences: list[str] = []
    goods_sections: list[dict] = []
    goods_sentences: list[str] = []
    scoring_contains_gifts_or_unrelated_goods = False
    gifts_or_goods_linked_to_score = False

    for section in sections:
        if not isinstance(section, dict):
            continue
        text = "\n".join(
            part for part in (str(section.get("title", "")).strip(), str(section.get("excerpt", "")).strip(), str(section.get("body", "")).strip()) if part
        )
        if not text:
            continue
        has_forbidden_rule = bool(GIFTS_OR_UNRELATED_GOODS_FORBIDDEN_RE.search(text))
        has_goods_term = bool(GIFTS_OR_UNRELATED_GOODS_TERM_RE.search(text))
        has_score_link = bool(SCORING_SCORE_LINK_RE.search(text))
        goods_is_procurement_subject = bool(PROCUREMENT_SUBJECT_GOODS_CONTEXT_RE.search(text))

        if has_forbidden_rule:
            rule_sections.extend(_normalize_signal_sections([section]))
            fragments = _find_match_fragments(section, GIFTS_OR_UNRELATED_GOODS_FORBIDDEN_RE)
            rule_sentences.extend(fragments or _find_match_fragments(section, SCORING_SCORE_LINK_RE))

        if has_goods_term and not goods_is_procurement_subject:
            scoring_contains_gifts_or_unrelated_goods = True
            goods_sections.extend(_normalize_signal_sections([section]))
            goods_sentences.extend(_find_match_fragments(section, GIFTS_OR_UNRELATED_GOODS_TERM_RE))

        if has_goods_term and has_score_link and not goods_is_procurement_subject:
            gifts_or_goods_linked_to_score = True
            goods_sections.extend(_normalize_signal_sections([section]))
            goods_sentences.extend(_find_match_fragments(section, SCORING_SCORE_LINK_RE))

    return {
        "gifts_or_unrelated_goods_forbidden_in_scoring": bool(rule_sections),
        "gifts_or_goods_rule_sections": _dedupe_signal_sections(rule_sections),
        "gifts_or_goods_rule_sentences": _dedupe_preserve(rule_sentences),
        "scoring_contains_gifts_or_unrelated_goods": scoring_contains_gifts_or_unrelated_goods,
        "gifts_or_goods_scoring_sections": _dedupe_signal_sections(goods_sections),
        "gifts_or_goods_scoring_sentences": _dedupe_preserve(goods_sentences),
        "gifts_or_goods_linked_to_score": gifts_or_goods_linked_to_score,
    }


def _is_strong_technical_standard_section(section: dict) -> bool:
    title = str(section.get("title", "")).strip()
    module = str(section.get("module", "")).strip()
    return module == "technical" and any(signal in title for signal in TECHNICAL_STANDARD_PRIMARY_TITLE_SIGNALS)


def _should_relax_technical_standard_manual_review(
    definition: TopicDefinition,
    payload: dict,
    bundle: dict,
) -> bool:
    if definition.key != "technical_standard":
        return False
    if not bool(payload.get("need_manual_review", False)):
        return False
    if not _normalize_missing_evidence_items(payload.get("missing_evidence")):
        return False
    primary_ids = {str(item).strip() for item in bundle.get("primary_section_ids", []) if str(item).strip()} if isinstance(bundle, dict) else set()
    sections = [section for section in bundle.get("sections", []) if isinstance(section, dict)] if isinstance(bundle, dict) else []
    primary_sections = [section for section in sections if _section_id(section) in primary_ids] or sections
    if not primary_sections:
        return False
    if not any(_is_strong_technical_standard_section(section) for section in primary_sections):
        return False
    structured_signals = _extract_standard_reference_signals(primary_sections)
    if not structured_signals.get("foreign_standard_refs") and not structured_signals.get("cn_standard_refs"):
        return False
    return True


def _build_risk_point(
    *,
    source_section: dict,
    title: str,
    review_type: str,
    judgments: list[str],
    rectification: list[str],
    severity: str = "中风险",
) -> RiskPoint:
    source_location = (
        f"{source_section.get('title', '未发现')} 第{source_section.get('start_line', '?')}-{source_section.get('end_line', '?')}行"
        if source_section
        else "未发现"
    )
    source_excerpt = str(source_section.get("excerpt", "")).strip() or "未发现"
    return RiskPoint(
        title=title,
        severity=severity,
        review_type=review_type,
        source_location=source_location,
        source_excerpt=source_excerpt,
        risk_judgment=judgments or ["需人工复核"],
        legal_basis=["需人工复核"],
        rectification=rectification or ["未发现"],
    )


def _build_scoring_fallback_risks(sections: list[dict], existing_titles: set[str]) -> list[RiskPoint]:
    combined_text, source_section = _collect_section_text(sections)
    if not combined_text.strip():
        return []
    has_tier_signal = bool(SCORING_TIER_RE.search(combined_text))
    has_subjective_signal = any(signal in combined_text for signal in SCORING_SUBJECTIVE_SIGNALS)
    risks: list[RiskPoint] = []
    if has_tier_signal:
        title = "评分档次缺少量化口径"
        if title not in existing_titles:
            risks.append(
                _build_risk_point(
                    source_section=source_section,
                    title=title,
                    review_type="评分标准不明确",
                    judgments=["评分分档存在“优、良、中、差”或类似档次，但缺少与各档对应的量化判定标准。"],
                    rectification=["补充各评分档次对应的量化标准，并压缩主观裁量空间。"],
                )
            )
    if has_subjective_signal:
        title = "主观分值裁量空间过大"
        if title not in existing_titles:
            risks.append(
                _build_risk_point(
                    source_section=source_section,
                    title=title,
                    review_type="评分标准不明确",
                    judgments=["条款包含“综合打分”“酌情计分”等表述，评委自由裁量空间较大。"],
                    rectification=["删除纯主观评分表述，改为可操作的量化评分标准。"],
                )
            )
    if SCORING_RELEVANCE_RE.search(combined_text):
        title = "评分依据与采购标的关联性不足"
        if title not in existing_titles:
            risks.append(
                _build_risk_point(
                    source_section=source_section,
                    title=title,
                    review_type="评分因素相关性",
                    judgments=["评分因素聚焦排版、封面等形式内容，与采购标的或履约能力关联性不足。"],
                    rectification=["删除与采购标的和履约能力无直接关系的评分因素。"],
                )
            )
    if SCORING_INCONSISTENT_RE.search(combined_text):
        title = "评分口径前后不一致"
        if title not in existing_titles:
            risks.append(
                _build_risk_point(
                    source_section=source_section,
                    title=title,
                    review_type="评分标准不明确",
                    judgments=["同一评分项的分值或评分口径前后不一致，可能影响评审可操作性。"],
                    rectification=["统一评分项分值及评分口径表述。"],
                )
            )
    return risks


def _build_topic_rule_fallback_risks(
    definition: TopicDefinition,
    sections: list[dict],
    existing_titles: set[str],
) -> list[RiskPoint]:
    combined_text, source_section = _collect_section_text(sections)
    if not combined_text.strip():
        return []

    risks: list[RiskPoint] = []
    if definition.key == "scoring":
        return _build_scoring_fallback_risks(sections, existing_titles)

    if definition.key == "qualification":
        if QUALIFICATION_LOCAL_SERVICE_RE.search(combined_text):
            title = "设立常设服务机构的资格限制"
            if title not in existing_titles:
                risks.append(
                    _build_risk_point(
                        source_section=source_section,
                        title=title,
                        review_type="资格条件",
                        judgments=["资格条件要求供应商在本地设立常设服务机构，可能形成地域性准入限制。"],
                        rectification=["删除本地常设机构准入门槛，改为履约阶段服务响应要求。"],
                        severity="高风险",
                    )
                )
        if QUALIFICATION_PERFORMANCE_RE.search(combined_text) and ("资格" in combined_text or "须具备" in combined_text):
            title = "业绩与人员要求被设置为资格门槛"
            if title not in existing_titles:
                risks.append(
                    _build_risk_point(
                        source_section=source_section,
                        title=title,
                        review_type="资格条件/业绩人员",
                        judgments=["业绩或人员条件直接并入资格门槛，需审查是否与主体准入及履约直接相关。"],
                        rectification=["将与主体准入无直接关系的业绩、人员条件从资格门槛中剥离。"],
                    )
                )

    if definition.key == "technical_standard":
        if TECHNICAL_STANDARD_OBSOLETE_RE.search(combined_text):
            title = "引用已废止标准"
            if title not in existing_titles:
                risks.append(
                    _build_risk_point(
                        source_section=source_section,
                        title=title,
                        review_type="技术标准",
                        judgments=["技术条款引用的标准版本较旧，存在已废止或被替代的风险。"],
                        rectification=["核对标准现行有效版本，并统一更新标准引用。"],
                    )
                )
        if TECHNICAL_STANDARD_MISMATCH_RE.search(combined_text):
            title = "标准名称与编号不一致"
            if title not in existing_titles:
                risks.append(
                    _build_risk_point(
                        source_section=source_section,
                        title=title,
                        review_type="技术标准",
                        judgments=["标准名称、编号或引用方式可能存在不一致，需核对标准全称与适用范围。"],
                        rectification=["统一标准名称、编号和适用对象的表述。"],
                    )
                )
        if TECHNICAL_STANDARD_METHOD_MISMATCH_RE.search(combined_text):
            title = "检测方法标准与采购要求不匹配"
            if title not in existing_titles:
                risks.append(
                    _build_risk_point(
                        source_section=source_section,
                        title=title,
                        review_type="技术标准",
                        judgments=["检测方法或试验方法与采购标的、交付要求之间匹配关系不足，可能导致验收依据偏离采购需求。"],
                        rectification=["核对检测方法标准与采购标的、验收指标的一致性，删除与采购要求不匹配的检测依据。"],
                    )
                )

    if definition.key == "contract_payment":
        if CONTRACT_PAYMENT_FISCAL_RE.search(combined_text):
            title = "付款节点与财政资金到位挂钩"
            if title not in existing_titles:
                risks.append(
                    _build_risk_point(
                        source_section=source_section,
                        title=title,
                        review_type="商务条款失衡",
                        judgments=["付款节点与财政资金到位挂钩，供应商回款时间存在较大不确定性。"],
                        rectification=["删除以财政资金到位作为付款前提的表述，改为明确付款时间节点。"],
                        severity="高风险",
                    )
                )
        if CONTRACT_PAYMENT_ACCEPTANCE_RE.search(combined_text):
            title = "付款安排以验收裁量为前置条件"
            if title not in existing_titles:
                risks.append(
                    _build_risk_point(
                        source_section=source_section,
                        title=title,
                        review_type="付款条款/验收联动",
                        judgments=["付款触发条件与验收裁量高度耦合，可能放大采购人单方控制空间。"],
                        rectification=["明确验收标准和支付触发条件，避免付款完全受验收裁量控制。"],
                    )
                )
        if CONTRACT_PAYMENT_DELAY_RE.search(combined_text):
            title = "付款节点明显偏后"
            if title not in existing_titles:
                risks.append(
                    _build_risk_point(
                        source_section=source_section,
                        title=title,
                        review_type="付款条款",
                        judgments=["付款时间设置偏后，可能对供应商形成较大资金占压。"],
                        rectification=["结合履约进度优化付款比例和付款时点。"],
                    )
                )
    return risks


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
    recovered_reason_codes: list[str] | None = None,
) -> list[str]:
    reasons: list[str] = []
    if not selected_sections:
        reasons.append("topic_not_triggered")
    if missing_evidence:
        reasons.append("missing_evidence")
    if degraded or (need_manual_review and missing_evidence):
        reasons.append("degraded_to_manual_review")
    if need_manual_review and selected_sections and missing_evidence:
        reasons.append("risk_degraded_to_manual_review")
    recovered_reason_codes = [str(item).strip() for item in (recovered_reason_codes or []) if str(item).strip()]
    if recovered_reason_codes:
        reasons.append("risk_not_extracted")
        reasons.extend(recovered_reason_codes)
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
    structured_signals = _build_structured_signals(definition, sections)
    missing_items = list(missing_evidence or (coverage.get("missing_hints", []) if isinstance(coverage, dict) else []))
    selected_sections = [
        {
            "title": section.get("title", ""),
            "start_line": section.get("start_line"),
            "end_line": section.get("end_line"),
            "module": section.get("module", ""),
        }
        for section in sections
        if isinstance(section, dict)
    ]
    failure_reasons = _build_topic_failure_reasons(
        selected_sections=selected_sections,
        missing_evidence=[item for item in missing_items if item and item != "未发现"],
        need_manual_review=True,
        degraded=True,
        recovered_reason_codes=[],
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
            "selected_sections": selected_sections,
            "missing_evidence": missing_items,
            "failure_reasons": failure_reasons,
            "failure_reason_labels": [TOPIC_FAILURE_REASON_LABELS.get(reason, reason) for reason in failure_reasons],
            "evidence_bundle": bundle,
            "topic_coverage": coverage,
            "degraded": True,
            "degrade_reason": error_type,
            "structured_signals": structured_signals,
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
    section_modules = {
        str(section.get("module", "")).strip()
        for section in sections
        if isinstance(section, dict) and str(section.get("module", "")).strip()
    }
    boundary_modules = set(definition.boundary.primary_modules or definition.modules) | set(definition.boundary.secondary_modules)
    has_shared_section_signal = any(
        sum(
            1
            for module, score in dict(section.get("module_scores", {}) or {}).items()
            if module in boundary_modules and int(score or 0) >= 3
        )
        >= 2
        for section in sections
        if isinstance(section, dict)
    )
    existing_titles = {risk.title for risk in risk_points if risk.title.strip()}
    existing_risk_count = len(existing_titles)
    normalized_missing_evidence = _normalize_missing_evidence_items(payload.get("missing_evidence"))
    fallback_risks = (
        _build_topic_rule_fallback_risks(definition, sections, existing_titles)
        if not normalized_missing_evidence
        else []
    )
    if fallback_risks:
        risk_points.extend(fallback_risks)
        if existing_risk_count > 0:
            failure_reasons.append("topic_triggered_but_partial_miss")
        else:
            failure_reasons.append("evidence_enough_but_risk_missed")
        if len(section_modules) >= 2 or len(sections) >= 2 or has_shared_section_signal:
            failure_reasons.append("cross_topic_shared_but_single_topic_hit")
        summary = str(payload.get("summary", "")).strip()
        payload["summary"] = summary or f"{definition.label}专题完成，并根据已召回证据补出明确风险。"
        payload["coverage_note"] = str(payload.get("coverage_note", "")).strip() or "已覆盖专题关键条款。"
        payload["need_manual_review"] = False
        payload["missing_evidence"] = ["未发现"]

    if _should_tighten_manual_review(payload, risk_points):
        payload["need_manual_review"] = False
        payload["missing_evidence"] = ["未发现"]
    if _should_relax_technical_standard_manual_review(definition, payload, bundle):
        payload["need_manual_review"] = False
        payload["missing_evidence"] = ["未发现"]
        payload["coverage_note"] = str(payload.get("coverage_note", "")).strip() or "已覆盖核心技术标准条款。"

    return payload, risk_points, failure_reasons


def _build_structured_signals(definition: TopicDefinition, sections: list[dict]) -> dict[str, object]:
    signals: dict[str, object] = {}
    if definition.key in {"policy", "qualification", "procedure"}:
        signals.update(_extract_import_policy_signals(sections))
    if definition.key == "scoring":
        signals.update(_extract_star_rule_signals(sections))
        signals.update(_extract_acceptance_plan_scoring_signals(sections))
        signals.update(_extract_payment_terms_scoring_signals(sections))
        signals.update(_extract_gifts_or_unrelated_goods_scoring_signals(sections))
    if definition.key == "technical_standard":
        signals.update(_extract_standard_reference_signals(sections))
    return signals


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
    try:
        raw_output = extract_response_text(response) or ""
    except Exception as exc:
        if not execution_plan.get("allow_degrade_on_error", True):
            raise
        return _build_empty_topic_artifact(
            definition,
            bundle,
            coverage,
            topic_mode,
            execution_plan,
            summary=f"{definition.label}专题响应解析失败，已自动降级为人工复核。",
            missing_evidence=[f"专题响应解析失败：{exc}"],
            raw_output="",
            error_type="topic_response_parse_failed",
        )

    try:
        payload = _parse_topic_json(raw_output)
        payload, risk_points, postprocess_failure_reasons = _postprocess_topic_payload(definition, payload, bundle)
    except Exception as exc:
        if not execution_plan.get("allow_degrade_on_error", True):
            raise
        return _build_empty_topic_artifact(
            definition,
            bundle,
            coverage,
            topic_mode,
            execution_plan,
            summary=f"{definition.label}专题后处理失败，已自动降级为人工复核。",
            missing_evidence=[f"专题后处理失败：{exc}"],
            raw_output=raw_output,
            error_type="topic_postprocess_failed",
        )

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
    signal_sections = sections
    if definition.key == "technical_standard":
        primary_ids = {
            str(item).strip() for item in bundle.get("primary_section_ids", []) if str(item).strip()
        } if isinstance(bundle, dict) else set()
        if primary_ids:
            primary_sections = [
                section for section in sections if isinstance(section, dict) and _section_id(section) in primary_ids
            ]
            if primary_sections:
                signal_sections = primary_sections
    structured_signals = _build_structured_signals(definition, signal_sections)
    failure_reasons = _build_topic_failure_reasons(
        selected_sections=selected_sections,
        missing_evidence=normalized_missing_evidence,
        need_manual_review=bool(payload.get("need_manual_review", False)),
        degraded=False,
        recovered_reason_codes=postprocess_failure_reasons,
    )
    if (
        definition.key == "technical_standard"
        and structured_signals.get("foreign_standard_refs")
        and not structured_signals.get("has_equivalent_standard_clause", False)
    ):
        failure_reasons = list(dict.fromkeys(failure_reasons + ["foreign_standard_conflict"]))
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
            "structured_signals": structured_signals,
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
