from __future__ import annotations

import json
import re

from .schemas import EvidenceBundle, ModuleHit, SectionCandidate, TopicCoverage, V2StageArtifact
from .topics import TOPIC_TAXONOMY, TopicDefinition, resolve_topic_definitions, resolve_topic_execution_plan

SCORING_PRIMARY_TITLE_SIGNALS = ("评分办法", "评标办法", "评审办法", "综合评分表", "评分细则", "评审因素表", "评分标准")
SCORING_DETAIL_TITLE_SIGNALS = ("评分内容", "评分标准", "评分因素", "评分准则", "综合评分表", "评分细则", "评审因素表")
SCORING_GENERIC_METHOD_TITLE_SIGNALS = ("综合评分法", "评审程序", "评审方法", "评标方法")
SCORING_SCORE_LINK_RE = re.compile(
    r"(得\s*\d+\s*分|加\s*\d+\s*分|最高得\s*\d+\s*分|最高加\s*\d+\s*分|不得分|每具备一项得|每体现\s*\d+\s*点加)"
)
SCORING_RISK_SIGNAL_RE = re.compile(
    r"(安装、检测、验收、培训计划|验收、培训计划|验收方案|验收标准|验收流程|验收资料|"
    r"验收组织能力|制造商|认证证书|CNAS|省级标准协会|GB\d+|BS2869)"
)
POLICY_FIXED_SIGNAL_RE = re.compile(
    r"(关于享受优惠政策的主体及价格扣除比例|中小企业声明函|残疾人福利性单位声明函|监狱企业|"
    r"节能产品政府采购|环境标志产品政府采购|节能产品认证证书|价格扣除比例|投标总价给予\s*\d+%?\s*的扣除|"
    r"给予\s*\d+%?\s*的扣除|优惠政策)"
)
COMPLIANCE_PROOF_SIGNAL_RE = re.compile(
    r"(合格证书|机组合格证书|认证合格证|3C认证|原产地证明|三包条例证书|节能产品认证证书)"
)
ANNOUNCEMENT_REFERENCE_SIGNAL_RE = re.compile(
    r"(具体时间详见.*招标公告|资格要求详见.*招标公告|以公告为准|详见深圳政府采购智慧平台招标公告)"
)
ELECTRONIC_PROCUREMENT_SIGNAL_RE = re.compile(
    r"(电子投标|电子化|智慧平台|CA签名|电子签章|深圳政府采购智慧平台|声明函不需要盖章或签字)"
)
CONTRACT_TEMPLATE_SIGNAL_RE = re.compile(r"(合同条款及格式|仅供参考|合同范本|格式仅供参考)")
TECHNICAL_STANDARD_PRIMARY_TITLE_SIGNALS = ("规格及技术参数", "技术参数", "技术要求", "主要技术参数", "技术规格", "参数要求")
TECHNICAL_STANDARD_NEGATIVE_TITLE_SIGNALS = ("售后服务", "付款方式", "设备验收", "商务要求", "商务条款", "其他商务")
TECHNICAL_STANDARD_FOREIGN_REF_RE = re.compile(
    r"\b(?:BS\s*EN|EN|IEC|ISO|ANSI|UL|DIN|ASTM|JIS|CISPR)\s*[A-Z0-9.-]*\d+(?:[./-]\d+)*(?::\d{4}|\-\d{4})?",
    re.IGNORECASE,
)
TECHNICAL_STANDARD_CN_REF_RE = re.compile(
    r"\b(?:GB/T|GB|YY/T|YY|HJ/T|HJ|GA/T|GA|JB/T|JB|SJ/T|SJ|DL/T|DL|HG/T|HG|CJ/T|CJ|QB/T|QB|JGJ|JT/T|JT)\s*[A-Z0-9.-]*\d+(?:[./-]\d+)*(?::\d{4}|\-\d{4})?",
    re.IGNORECASE,
)
TECHNICAL_STANDARD_CLAUSE_RE = re.compile(r"(符合.{0,24}(标准|规范)|执行.{0,16}(标准|规范)|依据.{0,16}(标准|规范))")
TECHNICAL_PARAMETER_SIGNAL_RE = re.compile(r"(参数|技术要求|技术指标|规格|性能|电磁|噪声|材质|输出|容量|频率|功率)")
CONTRACT_PAYMENT_TITLE_SIGNALS = ("付款方式", "付款条件", "支付安排", "结算方式", "合同价款")
CONTRACT_PAYMENT_CHAIN_RE = re.compile(
    r"((合同签订后|收到发票后|送达采购人现场后|验收合格|运行三个月后).{0,30}(支付|付款).{0,12}\d{1,3}\s*%)"
)


def _section_id(section: SectionCandidate) -> str:
    return f"{section.start_line}-{section.end_line}"


def _to_section_candidate(payload: dict) -> SectionCandidate:
    return SectionCandidate(
        title=str(payload.get("title", "")).strip() or "未命名章节",
        start_line=int(payload.get("start_line", 0) or 0),
        end_line=int(payload.get("end_line", 0) or 0),
        body=str(payload.get("body", "")).strip(),
        excerpt=str(payload.get("excerpt", "")).strip(),
        module=str(payload.get("module", "")).strip() or "procedure",
        module_scores=dict(payload.get("module_scores", {}) or {}),
        confidence=int(payload.get("confidence", 0) or 0),
        keywords=[str(item).strip() for item in payload.get("keywords", []) if str(item).strip()],
        heading_level=int(payload.get("heading_level", 0) or 0),
        source=str(payload.get("source", "")).strip() or "rule_split",
    )


def _normalize_sections(structure: V2StageArtifact) -> list[SectionCandidate]:
    raw_sections = structure.metadata.get("sections", []) if structure.metadata else []
    return [_to_section_candidate(section) for section in raw_sections if isinstance(section, dict)]


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> tuple[int, list[str]]:
    score = 0
    matched: list[str] = []
    for keyword in keywords:
        count = text.count(keyword)
        score += count
        if count > 0:
            matched.append(keyword)
    return score, matched


def _is_compact_row_title(title: str) -> bool:
    stripped = title.strip()
    return ("\t" in stripped) or stripped.startswith(("1 ", "2 ", "3 ", "4 ", "5 "))


def _has_joint_signal(section: SectionCandidate, primary_modules: set[str], secondary_modules: set[str]) -> bool:
    scores = {str(module): int(score or 0) for module, score in (section.module_scores or {}).items()}
    return any(scores.get(module, 0) >= 3 for module in primary_modules) and any(
        scores.get(module, 0) >= 3 for module in secondary_modules
    )


def _dedupe_list(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _technical_standard_profile(section: SectionCandidate) -> dict[str, object]:
    text = "\n".join(part for part in (section.title, section.excerpt, section.body) if part)
    title = section.title or ""
    foreign_refs = _dedupe_list([match.group(0).strip() for match in TECHNICAL_STANDARD_FOREIGN_REF_RE.finditer(text)])
    cn_refs = _dedupe_list([match.group(0).strip() for match in TECHNICAL_STANDARD_CN_REF_RE.finditer(text)])
    title_has_primary_signal = any(signal in title for signal in TECHNICAL_STANDARD_PRIMARY_TITLE_SIGNALS)
    title_has_negative_signal = any(signal in title for signal in TECHNICAL_STANDARD_NEGATIVE_TITLE_SIGNALS)
    has_standard_clause = bool(TECHNICAL_STANDARD_CLAUSE_RE.search(text))
    has_parameter_signal = bool(TECHNICAL_PARAMETER_SIGNAL_RE.search(text))
    has_standard_keyword = ("标准" in text) or ("规范" in text)
    strong_standard_section = bool(foreign_refs or cn_refs) and (title_has_primary_signal or has_standard_clause or has_parameter_signal)
    return {
        "foreign_refs": foreign_refs,
        "cn_refs": cn_refs,
        "title_has_primary_signal": title_has_primary_signal,
        "title_has_negative_signal": title_has_negative_signal,
        "has_standard_clause": has_standard_clause,
        "has_parameter_signal": has_parameter_signal,
        "has_standard_keyword": has_standard_keyword,
        "strong_standard_section": strong_standard_section,
    }


def _score_section(section: SectionCandidate, definition: TopicDefinition) -> tuple[int, list[str], list[str]]:
    title_hits, title_keywords = _keyword_hits(section.title, definition.keywords)
    excerpt_hits, excerpt_keywords = _keyword_hits(f"{section.excerpt}\n{section.body}", definition.keywords)
    excerpt_hits_for_score = min(excerpt_hits, 12) if definition.key == "scoring" else excerpt_hits
    text = "\n".join(part for part in (section.title, section.excerpt, section.body) if part)
    primary_modules = set(definition.boundary.primary_modules or definition.modules)
    secondary_modules = set(definition.boundary.secondary_modules)
    primary_module_bonus = 24 if section.module in primary_modules else 0
    secondary_module_bonus = 12 if section.module in secondary_modules else 0
    heading_bonus = 5 if section.heading_level == 1 else 3 if section.heading_level > 1 else 0
    heading_bonus -= 4 if _is_compact_row_title(section.title) else 0
    confidence_bonus = min(section.confidence, 12)

    module_hit_bonus = 0
    module_signal_bonus = 0
    raw_scores = {str(module): int(score or 0) for module, score in (section.module_scores or {}).items()}
    for module, score in section.module_scores.items():
        score_value = min(int(score), 8)
        if module in primary_modules:
            module_hit_bonus += score_value
            module_signal_bonus += 4
        elif module in secondary_modules:
            module_hit_bonus += min(score_value, 5)
            module_signal_bonus += 2

    special_bonus = 0
    if definition.key == "contract_payment":
        if raw_scores.get("contract", 0) >= 3 and raw_scores.get("acceptance", 0) >= 3:
            special_bonus += 10
        if "商务" in section.title and "验收" in section.title:
            special_bonus += 6
        if any(signal in section.title for signal in CONTRACT_PAYMENT_TITLE_SIGNALS):
            special_bonus += 32
        if CONTRACT_PAYMENT_CHAIN_RE.search(text):
            special_bonus += 28
    if definition.key == "scoring":
        if raw_scores.get("qualification", 0) >= 3:
            special_bonus += 4
        if any(signal in section.title for signal in ("评分表", "综合评分表", "评分细则", "评审因素表")):
            special_bonus += 8
        if raw_scores.get("technical", 0) >= 3 or raw_scores.get("procedure", 0) >= 3:
            special_bonus += 3
        if any(signal in section.title for signal in SCORING_DETAIL_TITLE_SIGNALS):
            special_bonus += 24
        if SCORING_SCORE_LINK_RE.search(text):
            special_bonus += 18
        if SCORING_RISK_SIGNAL_RE.search(text):
            special_bonus += 14
        if re.search(r"(安装、检测、验收、培训计划|验收、培训计划)", text) and SCORING_SCORE_LINK_RE.search(text):
            special_bonus += 30
        if any(signal in section.title for signal in SCORING_GENERIC_METHOD_TITLE_SIGNALS) and not any(
            signal in section.title for signal in SCORING_DETAIL_TITLE_SIGNALS
        ):
            special_bonus -= 18
        if "是指" in text and "综合评分法" in section.title and not SCORING_SCORE_LINK_RE.search(text):
            special_bonus -= 12
        if section.module == "procedure" and not SCORING_SCORE_LINK_RE.search(text):
            special_bonus -= 8
        if section.line_span >= 18 and not any(signal in section.title for signal in SCORING_DETAIL_TITLE_SIGNALS):
            special_bonus -= 18
    if definition.key == "technical_standard":
        profile = _technical_standard_profile(section)
        foreign_refs = profile["foreign_refs"]
        cn_refs = profile["cn_refs"]
        if profile["title_has_primary_signal"]:
            special_bonus += 22
        if profile["has_standard_clause"]:
            special_bonus += 12
        if profile["has_parameter_signal"]:
            special_bonus += 8
        if profile["has_standard_keyword"]:
            special_bonus += 4
        if foreign_refs:
            special_bonus += 26 + min(len(foreign_refs) * 10, 30)
        if cn_refs:
            special_bonus += min(len(cn_refs) * 6, 18)
        if foreign_refs and cn_refs:
            special_bonus += 8
        if profile["strong_standard_section"]:
            special_bonus += 12
        if profile["title_has_negative_signal"] and not (foreign_refs or profile["strong_standard_section"]):
            special_bonus -= 28
        if section.module in {"contract", "acceptance"} and not (foreign_refs or cn_refs):
            special_bonus -= 12
        if COMPLIANCE_PROOF_SIGNAL_RE.search(text):
            special_bonus += 10
    if definition.key == "policy":
        if POLICY_FIXED_SIGNAL_RE.search(text):
            special_bonus += 28
        if re.search(r"\d+\s*%\s*的扣除", text):
            special_bonus += 22
        if "其他关键信息" in section.title or "政策" in section.title:
            special_bonus += 8
    if definition.key == "procedure":
        if ANNOUNCEMENT_REFERENCE_SIGNAL_RE.search(text):
            special_bonus += 20
        if ELECTRONIC_PROCUREMENT_SIGNAL_RE.search(text):
            special_bonus += 10
    if definition.key == "qualification":
        if ANNOUNCEMENT_REFERENCE_SIGNAL_RE.search(text):
            special_bonus += 12
        if COMPLIANCE_PROOF_SIGNAL_RE.search(text):
            special_bonus += 8
    if definition.key in {"acceptance", "contract_payment"}:
        if CONTRACT_TEMPLATE_SIGNAL_RE.search(text):
            special_bonus -= 24

    total_score = (
        title_hits * 8
        + excerpt_hits_for_score * 3
        + primary_module_bonus
        + secondary_module_bonus
        + module_hit_bonus
        + module_signal_bonus
        + special_bonus
        + heading_bonus
        + confidence_bonus
    )
    reasons: list[str] = []
    if primary_module_bonus:
        reasons.append(f"主模块命中 {section.module}")
    elif secondary_module_bonus:
        reasons.append(f"主模块命中 {section.module}")
    if title_hits:
        reasons.append(f"标题命中 {title_hits} 次关键词")
    if excerpt_hits:
        reasons.append(f"正文命中 {excerpt_hits} 次关键词")
    if section.heading_level:
        reasons.append(f"标题层级 {section.heading_level}")
    if _is_compact_row_title(section.title):
        reasons.append("表格行标题降权")
    if special_bonus:
        reasons.append(f"专题特殊加权 {special_bonus}")
    if definition.key == "technical_standard":
        profile = _technical_standard_profile(section)
        if profile["foreign_refs"]:
            reasons.append(f"外标命中 {len(profile['foreign_refs'])} 处")
        if profile["cn_refs"]:
            reasons.append(f"国标命中 {len(profile['cn_refs'])} 处")
        if profile["title_has_primary_signal"]:
            reasons.append("技术参数标题优先")
        if profile["title_has_negative_signal"] and not profile["foreign_refs"]:
            reasons.append("商务/验收标题降权")
    matched_keywords = list(dict.fromkeys(title_keywords + excerpt_keywords))
    return total_score, reasons, matched_keywords


def _pick_context_sections(
    ordered_sections: list[SectionCandidate],
    selected_indexes: list[int],
    used_ids: set[str],
    limit: int,
) -> list[SectionCandidate]:
    context_sections: list[SectionCandidate] = []
    for index in selected_indexes:
        for neighbor in (index - 1, index + 1):
            if neighbor < 0 or neighbor >= len(ordered_sections):
                continue
            candidate = ordered_sections[neighbor]
            candidate_id = _section_id(candidate)
            if candidate_id in used_ids:
                continue
            used_ids.add(candidate_id)
            context_sections.append(candidate)
            if len(context_sections) >= limit:
                return context_sections
    return context_sections


def _build_bundle(
    definition: TopicDefinition,
    ordered_sections: list[SectionCandidate],
) -> tuple[EvidenceBundle, TopicCoverage]:
    ranked: list[tuple[int, int, SectionCandidate, list[str], list[str]]] = []
    for index, section in enumerate(ordered_sections):
        score, reasons, matched_keywords = _score_section(section, definition)
        if score > 0:
            ranked.append((score, index, section, reasons, matched_keywords))

    primary_modules = set(definition.boundary.primary_modules or definition.modules)
    secondary_modules = set(definition.boundary.secondary_modules)
    ranked.sort(
        key=lambda item: (
            (
                definition.key == "technical_standard"
                and bool(_technical_standard_profile(item[2])["foreign_refs"])
            ),
            (
                definition.key == "technical_standard"
                and bool(_technical_standard_profile(item[2])["strong_standard_section"])
            ),
            (
                definition.key == "technical_standard"
                and bool(_technical_standard_profile(item[2])["title_has_primary_signal"])
            ),
            (
                definition.key == "technical_standard"
                and not bool(_technical_standard_profile(item[2])["title_has_negative_signal"])
            ),
            (definition.key == "contract_payment" and _has_joint_signal(item[2], primary_modules, secondary_modules)),
            item[2].module in primary_modules,
            any((item[2].module_scores or {}).get(module, 0) > 0 for module in primary_modules),
            item[0],
            item[2].line_span,
            len(item[2].excerpt),
        ),
        reverse=True,
    )

    max_primary = 2 if len(primary_modules) >= 2 or definition.key == "scoring" else 1
    if definition.key == "scoring":
        max_primary = 5
    if definition.key == "technical_standard":
        max_primary = 1
    primary_ranked: list[tuple[int, int, SectionCandidate, list[str], list[str]]] = []
    fallback_ranked: list[tuple[int, int, SectionCandidate, list[str], list[str]]] = []
    for item in ranked:
        section = item[2]
        primary_signal_threshold = 6 if definition.key == "scoring" and section.module not in primary_modules else 3
        technical_profile = _technical_standard_profile(section) if definition.key == "technical_standard" else None
        has_primary_signal = (
            (definition.key == "contract_payment" and _has_joint_signal(section, primary_modules, secondary_modules))
            or (
                definition.key == "contract_payment"
                and (
                    any(signal in section.title for signal in CONTRACT_PAYMENT_TITLE_SIGNALS)
                    or bool(CONTRACT_PAYMENT_CHAIN_RE.search("\n".join(part for part in (section.title, section.excerpt, section.body) if part)))
                )
            )
            or section.module in primary_modules
            or (
                definition.key == "technical_standard"
                and technical_profile is not None
                and (
                    technical_profile["strong_standard_section"]
                    or technical_profile["title_has_primary_signal"]
                )
            )
            or (
                definition.key == "scoring"
                and (
                    any(signal in section.title for signal in SCORING_PRIMARY_TITLE_SIGNALS)
                    or (
                        any(signal in section.title for signal in SCORING_DETAIL_TITLE_SIGNALS)
                        and SCORING_SCORE_LINK_RE.search("\n".join(part for part in (section.title, section.excerpt, section.body) if part))
                    )
                )
            )
            or any(
            int((section.module_scores or {}).get(module, 0) or 0) >= primary_signal_threshold for module in primary_modules
            )
        )
        if has_primary_signal and len(primary_ranked) < max_primary:
            primary_ranked.append(item)
        else:
            fallback_ranked.append(item)
    if not primary_ranked:
        primary_ranked = ranked[:max_primary]
        fallback_ranked = ranked[max_primary:]
    if definition.key == "technical_standard" and ranked:
        strongest_foreign_ref = next(
            (
                item
                for item in ranked
                if _technical_standard_profile(item[2])["foreign_refs"]
                and (
                    _technical_standard_profile(item[2])["strong_standard_section"]
                    or item[2].module in primary_modules
                )
            ),
            None,
        )
        if strongest_foreign_ref is not None and strongest_foreign_ref not in primary_ranked:
            if len(primary_ranked) < max_primary:
                primary_ranked.append(strongest_foreign_ref)
                fallback_ranked = [item for item in fallback_ranked if item != strongest_foreign_ref]
            elif primary_ranked:
                replaced = primary_ranked[-1]
                primary_ranked[-1] = strongest_foreign_ref
                fallback_ranked = [item for item in fallback_ranked if item != strongest_foreign_ref]
                fallback_ranked.append(replaced)
    if definition.key == "contract_payment" and ranked:
        strongest_payment_clause = next(
            (
                item
                for item in ranked
                if any(signal in item[2].title for signal in CONTRACT_PAYMENT_TITLE_SIGNALS)
                or bool(CONTRACT_PAYMENT_CHAIN_RE.search("\n".join(part for part in (item[2].title, item[2].excerpt, item[2].body) if part)))
            ),
            None,
        )
        if strongest_payment_clause is not None and strongest_payment_clause not in primary_ranked:
            if len(primary_ranked) < max_primary:
                primary_ranked.append(strongest_payment_clause)
                fallback_ranked = [item for item in fallback_ranked if item != strongest_payment_clause]
            elif primary_ranked:
                replaced = primary_ranked[-1]
                primary_ranked[-1] = strongest_payment_clause
                fallback_ranked = [item for item in fallback_ranked if item != strongest_payment_clause]
                fallback_ranked.append(replaced)

    primary_sections = [item[2] for item in primary_ranked]
    primary_ids = [_section_id(section) for section in primary_sections]
    used_ids = set(primary_ids)
    secondary_sections: list[SectionCandidate] = []
    secondary_ranked = sorted(
        fallback_ranked,
        key=lambda item: (
            (
                definition.key == "technical_standard"
                and bool(_technical_standard_profile(item[2])["foreign_refs"])
            ),
            (
                definition.key == "technical_standard"
                and bool(_technical_standard_profile(item[2])["cn_refs"])
            ),
            (
                definition.key == "technical_standard"
                and bool(_technical_standard_profile(item[2])["strong_standard_section"])
            ),
            (
                definition.key == "scoring"
                and any(signal in item[2].title for signal in SCORING_DETAIL_TITLE_SIGNALS)
            ),
            (
                definition.key == "scoring"
                and bool(SCORING_SCORE_LINK_RE.search("\n".join(part for part in (item[2].title, item[2].excerpt, item[2].body) if part)))
            ),
            (
                definition.key == "scoring"
                and bool(SCORING_RISK_SIGNAL_RE.search("\n".join(part for part in (item[2].title, item[2].excerpt, item[2].body) if part)))
            ),
            (
                definition.key == "scoring"
                and any(signal in item[2].title for signal in ("评分表", "综合评分表", "评分细则", "评审因素表"))
            ),
            item[2].module in secondary_modules,
            any((item[2].module_scores or {}).get(module, 0) > 0 for module in secondary_modules),
            item[0],
            -item[1],
        ),
        reverse=True,
    )
    for _, _, section, _, _ in secondary_ranked:
        if len(secondary_sections) >= 2:
            break
        candidate_id = _section_id(section)
        if candidate_id in used_ids:
            continue
        if (
            definition.key == "technical_standard"
            and (
                _technical_standard_profile(section)["foreign_refs"]
                or _technical_standard_profile(section)["cn_refs"]
                or _technical_standard_profile(section)["strong_standard_section"]
            )
        ) or section.module in secondary_modules or any((section.module_scores or {}).get(module, 0) > 0 for module in secondary_modules):
            used_ids.add(candidate_id)
            secondary_sections.append(section)
    if len(secondary_sections) < 2:
        secondary_sections.extend(
            _pick_context_sections(
                ordered_sections=ordered_sections,
                selected_indexes=[item[1] for item in primary_ranked],
                used_ids=used_ids,
                limit=2 - len(secondary_sections),
            )
        )
    secondary_ids = [_section_id(section) for section in secondary_sections]

    combined_sections = sorted(primary_sections + secondary_sections, key=lambda item: (item.start_line, item.end_line))
    covered_modules = list(
        dict.fromkeys(
            module
            for section in combined_sections
            for module in (
                [section.module]
                + [
                    key
                    for key, value in (section.module_scores or {}).items()
                    if int(value or 0) > 0 and key in definition.modules
                ]
            )
            if module
        )
    )
    missing_modules = [module for module in definition.modules if module not in covered_modules]

    missing_hints: list[str] = []
    if not primary_sections:
        missing_hints.append("未召回到高置信专题证据片段。")
    if missing_modules:
        missing_hints.append(f"未覆盖模块：{', '.join(missing_modules)}。")
    if primary_sections and len(primary_sections) == 1:
        missing_hints.append("当前仅召回 1 个核心证据片段，建议人工复核是否存在遗漏章节。")

    module_hits: list[ModuleHit] = []
    if primary_ranked:
        best_scores: dict[str, float] = {}
        keywords_by_module: dict[str, list[str]] = {}
        for _, _, section, _, matched_keywords in primary_ranked:
            module = section.module
            best_scores[module] = max(best_scores.get(module, 0.0), float(section.confidence))
            keywords_by_module.setdefault(module, [])
            for keyword in matched_keywords:
                if keyword not in keywords_by_module[module]:
                    keywords_by_module[module].append(keyword)
        for module, score in sorted(best_scores.items(), key=lambda item: item[1], reverse=True):
            module_hits.append(
                ModuleHit(
                    module=module,
                    score=score,
                    source="evidence_recall",
                    reason="专题证据召回命中该模块的高分片段。",
                    evidence_keywords=keywords_by_module.get(module, [])[:8],
                )
            )

    average_score = sum(item[0] for item in primary_ranked) / len(primary_ranked) if primary_ranked else 0.0
    coverage = TopicCoverage(
        topic=definition.key,
        covered_modules=covered_modules,
        covered_section_ids=primary_ids + secondary_ids,
        missing_modules=missing_modules,
        missing_hints=missing_hints,
        need_manual_review=not primary_sections or bool(missing_modules),
        confidence=min(average_score / 60.0, 1.0),
    )
    bundle = EvidenceBundle(
        topic=definition.key,
        sections=combined_sections,
        primary_section_ids=primary_ids,
        secondary_section_ids=secondary_ids,
        missing_hints=missing_hints,
        recall_query="；".join(
            [
                f"模块={','.join(definition.modules)}",
                f"关键词={','.join(definition.keywords)}",
                "策略=模块+标题+正文+相邻上下文",
            ]
        ),
        metadata={
            "topic_label": definition.label,
            "topic_aliases": list(definition.aliases),
            "priority": definition.priority,
            "boundary": {
                "in_scope": list(definition.boundary.in_scope),
                "out_of_scope": list(definition.boundary.out_of_scope),
                "primary_modules": list(definition.boundary.primary_modules),
                "secondary_modules": list(definition.boundary.secondary_modules),
                "ownership_rule": definition.boundary.ownership_rule,
                "merge_hints": list(definition.boundary.merge_hints),
            },
            "module_hits": [hit.to_dict() for hit in module_hits],
            "primary_scores": [
                {
                    "section_id": _section_id(section),
                    "score": score,
                    "reasons": reasons,
                    "keywords": matched_keywords,
                }
                for score, _, section, reasons, matched_keywords in primary_ranked
            ],
            "recall_strategy": "rule_recall",
        },
    )
    return bundle, coverage


def build_evidence_map(
    document_name: str,
    structure: V2StageArtifact,
    topic_mode: str = "default",
    topic_keys: tuple[str, ...] | list[str] | None = None,
) -> V2StageArtifact:
    plan = resolve_topic_execution_plan(topic_mode=topic_mode, topic_keys=topic_keys)
    topic_definitions = resolve_topic_definitions(topic_mode=topic_mode, topic_keys=topic_keys)
    ordered_sections = _normalize_sections(structure)
    bundle_map: dict[str, dict] = {}
    coverage_map: dict[str, dict] = {}
    bundle_list: list[dict] = []
    coverage_list: list[dict] = []

    for definition in topic_definitions:
        bundle, coverage = _build_bundle(definition, ordered_sections)
        bundle_payload = bundle.to_dict()
        coverage_payload = coverage.to_dict()
        bundle_map[definition.key] = bundle_payload
        coverage_map[definition.key] = coverage_payload
        bundle_list.append(bundle_payload)
        coverage_list.append(coverage_payload)

    content = json.dumps(
        {
            "document_name": document_name,
            "evidence_status": "ready",
            "source_structure_sections": len(ordered_sections),
            "topic_execution_plan": {
                "mode": plan.mode,
                "requested_keys": list(plan.requested_keys),
                "selected_keys": list(plan.selected_keys),
                "skipped_keys": list(plan.skipped_keys),
                "max_topic_calls": plan.max_topic_calls,
                "reason": plan.reason,
            },
            "topic_taxonomy": [
                {
                    "key": definition.key,
                    "label": definition.label,
                    "aliases": list(definition.aliases),
                    "priority": definition.priority,
                    "enabled": definition.enabled,
                    "modules": list(definition.modules),
                    "boundary": {
                        "in_scope": list(definition.boundary.in_scope),
                        "out_of_scope": list(definition.boundary.out_of_scope),
                        "primary_modules": list(definition.boundary.primary_modules),
                        "secondary_modules": list(definition.boundary.secondary_modules),
                        "ownership_rule": definition.boundary.ownership_rule,
                        "merge_hints": list(definition.boundary.merge_hints),
                    },
                }
                for definition in TOPIC_TAXONOMY
            ],
            "topic_evidence_bundles": bundle_list,
            "topic_coverages": coverage_list,
        },
        ensure_ascii=False,
        indent=2,
    )
    return V2StageArtifact(
        name="evidence",
        content=content,
        raw_output=content,
        metadata={
            "topic_execution_plan": {
                "mode": plan.mode,
                "requested_keys": list(plan.requested_keys),
                "selected_keys": list(plan.selected_keys),
                "skipped_keys": list(plan.skipped_keys),
                "max_topic_calls": plan.max_topic_calls,
                "reason": plan.reason,
            },
            "topic_taxonomy": {
                definition.key: {
                    "label": definition.label,
                    "aliases": list(definition.aliases),
                    "priority": definition.priority,
                    "enabled": definition.enabled,
                    "modules": list(definition.modules),
                    "boundary": {
                        "in_scope": list(definition.boundary.in_scope),
                        "out_of_scope": list(definition.boundary.out_of_scope),
                        "primary_modules": list(definition.boundary.primary_modules),
                        "secondary_modules": list(definition.boundary.secondary_modules),
                        "ownership_rule": definition.boundary.ownership_rule,
                        "merge_hints": list(definition.boundary.merge_hints),
                    },
                }
                for definition in TOPIC_TAXONOMY
            },
            "topic_evidence_bundles": bundle_map,
            "topic_coverages": coverage_map,
            "evidence_bundle_count": len(bundle_list),
        },
    )
