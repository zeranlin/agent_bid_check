from __future__ import annotations

import hashlib
import json
import re

from app.common.normalize import dedupe
from app.common.parser import parse_review_markdown
from app.common.schemas import RiskPoint

from .schemas import ComparisonArtifact, MergedRiskCluster, RiskSignature, TopicReviewArtifact, V2StageArtifact
from .topic_review import _build_structured_signals
from .topics import get_topic_definition


SEVERITY_ORDER = {"高风险": 3, "中高风险": 2.5, "中风险": 2, "低风险": 1, "需人工复核": 0}
STANDARD_RULE_ORDER = {
    "policy_technical_inconsistency": 0,
    "star_marker_missing_for_mandatory_standard": 1,
    "acceptance_plan_in_scoring_forbidden": 2,
    "specific_brand_or_supplier_in_scoring_forbidden": 3,
    "acceptance_testing_cost_shifted_to_bidder": 4,
    "payment_terms_in_scoring_forbidden": 5,
    "gifts_or_unrelated_goods_in_scoring_forbidden": 6,
}
STANDARD_RULE_TITLES = {
    "policy_technical_inconsistency": "技术标准引用与采购政策口径不一致，存在潜在倾向性和理解冲突",
    "star_marker_missing_for_mandatory_standard": "强制性标准条款未按评审规则标注★，可能导致实质性响应边界不清",
    "acceptance_plan_in_scoring_forbidden": "将项目验收方案纳入评审因素，违反评审规则合规性要求",
    "specific_brand_or_supplier_in_scoring_forbidden": "以制造商特定认证证书作为高分条件，存在限定特定供应商和倾向性评分风险",
    "acceptance_testing_cost_shifted_to_bidder": "验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险",
    "payment_terms_in_scoring_forbidden": "将付款方式纳入评审因素，违反评审规则合规性要求",
    "gifts_or_unrelated_goods_in_scoring_forbidden": "将赠送额外商品作为评分条件，违反评审规则合规性要求",
}
STANDARD_CLUSTER_SUPPRESSION_RULES = {
    "acceptance_plan_in_scoring_forbidden": (
        re.compile(r"(安装、检测、验收、培训计划|验收方案|验收移交|验收资料)", re.IGNORECASE),
    ),
    "specific_brand_or_supplier_in_scoring_forbidden": (
        re.compile(r"(制造商资质证书|特定产品认证证书|制造商特定认证证书|认证证书设置高分值)", re.IGNORECASE),
    ),
    "acceptance_testing_cost_shifted_to_bidder": (
        re.compile(
            r"(验收产生的检测费用笼统计入投标人承担范围|验收产生的检测费用及相关部门验收费用笼统计入投标人承担范围|"
            r"交钥匙项目要求与付款方式存在潜在风险|交钥匙项目定义模糊)",
            re.IGNORECASE,
        ),
    ),
}
TITLE_IMPORT_CONSISTENCY_RE = re.compile(r"(技术标准引用与采购政策口径不一致|燃油标准引用错误及滞后风险|标准引用格式混乱且版本缺失)")
TITLE_CERT_SCORING_RE = re.compile(r"(以制造商特定认证证书作为高分条件|产品认证指定特定协会)")
TITLE_SCORING_CLARITY_RE = re.compile(
    r"(评分档次缺少量化口径|评分标准中“施工组织方案”分值设置逻辑混乱|评分标准逻辑混乱，方案评分叠加方式不明|"
    r"评分标准不明确，存在逻辑矛盾|评分档次缺少量化口径，主观分值裁量空间过大|主观分值裁量空间过大|评分口径前后不一致)"
)
TITLE_PERSONNEL_SCORING_RE = re.compile(r"(评分项分值设置畸高，人员职称与业绩分值占比过大|项目负责人评分中“学历”和“职称”分值权重过高)")
TITLE_CONTRACT_TEMPLATE_RE = re.compile(
    r"(关键合同条款数值缺失|合同验收时点留白|违约责任与赔偿条款缺失|"
    r"关键商务条款数据缺失，合同无法执行|履约保证金退还期限未定，存在资金占用风险|验收标准模糊，采购人单方裁量权过大)"
)
TITLE_INTERNAL_SCORE_WEIGHT_RE = re.compile(r"(三体系认证分值设置过高|分值设置畸高)")
TITLE_POLICY_MISSING_RE = re.compile(r"(中小企业扶持政策落实条款缺失|节能环保产品政策落实条款缺失)")
TITLE_CERT_MISSING_RE = re.compile(r"(检测认证要求表述缺失)")
TITLE_ANNOUNCEMENT_RE = re.compile(r"(澄清/修改截止时间未明确填写)")
TITLE_IMPORT_ITSELF_RE = re.compile(r"(进口产品禁止性规定表述过于绝对)")
TITLE_SOCIAL_SECURITY_RE = re.compile(r"(人员社保要求存在特殊豁免)")
TITLE_BRAND_DISCLOSURE_RE = re.compile(r"(指定具体品牌和型号要求不明确)")
TITLE_DIMENSION_RE = re.compile(r"(双电源切换柜.*(尺寸要求过于具体|尺寸允许偏差过大))")
TITLE_THIRD_PARTY_TESTING_RE = re.compile(r"(未明确第三方检测要求)")
TITLE_PAYMENT_REVIEW_RE = re.compile(r"(交钥匙.*付款方式存在潜在风险)")
TITLE_ELECTRONIC_SIGNATURE_RE = re.compile(r"(‘不盖章’的表述存在合规风险|不盖章)")
TITLE_TRUNCATED_EVIDENCE_RE = re.compile(r"(质疑处理章节内容不完整)")
TITLE_PENDING_QUALIFICATION_RE = re.compile(r"(具体资格条件内容缺失)")
TITLE_PENDING_WASTE_RE = re.compile(r"(废标条件及最终解释权条款证据缺失)")
TITLE_SERVICE_SCORING_RE = re.compile(r"(售后服务承诺评分标准设置不合理)")
TITLE_ORIGINAL_ENGINEER_RE = re.compile(r"(制造商原厂工程师)")
TITLE_ACCEPTANCE_STANDARD_RE = re.compile(r"(验收标准表述模糊)")
TITLE_SHORT_WINDOW_RE = re.compile(r"(业绩评分中时间范围设定过短)")


def _clean_topic_label(topic_key: str) -> str:
    return {
        "qualification": "资格条件",
        "performance_staff": "业绩与人员",
        "scoring": "评分办法",
        "samples_demo": "样品演示答辩",
        "technical_bias": "技术倾向性",
        "technical_standard": "技术标准与检测",
        "contract_payment": "付款与履约",
        "acceptance": "验收条款",
        "procedure": "程序条款",
        "policy": "政策条款",
        "cross_topic": "跨专题",
        "technical": "技术条款",
        "contract": "合同条款",
    }.get(topic_key, topic_key)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _excerpt_hash(text: str) -> str:
    normalized = _normalize_text(text)[:500]
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()[:16] if normalized else ""


def _signature_key(risk: RiskPoint) -> str:
    title = _normalize_text(risk.title)
    review_type = _normalize_text(risk.review_type)
    location = _normalize_text(risk.source_location)
    excerpt_hash = _excerpt_hash(risk.source_excerpt)
    if location and title:
        return f"{title}|{review_type}|{location}"
    if excerpt_hash:
        return f"{title}|{review_type}|{excerpt_hash}"
    return f"{title}|{review_type}"


def _best_severity(values: list[str]) -> str:
    if not values:
        return "需人工复核"
    ordered = sorted(values, key=lambda item: SEVERITY_ORDER.get(item, -1), reverse=True)
    explicit = [item for item in ordered if item != "需人工复核"]
    return explicit[0] if explicit else ordered[0]


def _dedupe_dicts_by_key(items: list[dict], key: str) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = str(item.get(key, "")).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(item)
    return result


def _compact_titles(sections: list[dict], limit: int = 3) -> list[str]:
    return [
        str(section.get("title", "")).strip()
        for section in _dedupe_dicts_by_key(sections, "title")[:limit]
        if str(section.get("title", "")).strip()
    ]


def _compact_sentences(sentences: list[str], limit: int = 2) -> list[str]:
    result: list[str] = []
    for sentence in dedupe([str(item).strip() for item in sentences if str(item).strip()]):
        compact = re.sub(r"\s+", " ", sentence).strip()
        if compact:
            result.append(compact)
        if len(result) >= limit:
            break
    return result


def _compact_rule_locations(locations: list[str], limit: int = 2) -> list[str]:
    explicit = [str(item).strip() for item in locations if str(item).strip() and not str(item).strip().startswith("内置规则库：")]
    builtin = [str(item).strip() for item in locations if str(item).strip().startswith("内置规则库：")]
    ordered = explicit or builtin
    return dedupe(ordered)[:limit]


def _risk_to_signature(risk: RiskPoint, topic: str, source_rule: str) -> RiskSignature:
    risk.ensure_defaults()
    return RiskSignature(
        topic=topic,
        title=risk.title,
        review_type=risk.review_type,
        source_locations=[risk.source_location] if risk.source_location else [],
        source_excerpt_hash=_excerpt_hash(risk.source_excerpt),
        severity=risk.severity,
        source_rule=source_rule,
        source_excerpt=risk.source_excerpt,
    )


def _risk_to_dict(risk: RiskPoint, topic: str, source_rule: str) -> dict:
    risk.ensure_defaults()
    return {
        "topic": topic,
        "source_rule": source_rule,
        "title": risk.title,
        "severity": risk.severity,
        "review_type": risk.review_type,
        "source_location": risk.source_location,
        "source_excerpt": risk.source_excerpt,
    }


def _build_cluster(cluster_id: str, items: list[tuple[RiskPoint, str, str]]) -> MergedRiskCluster:
    risks = [item[0] for item in items]
    severities = [risk.severity for risk in risks]
    topics = [item[1] for item in items]
    source_rules = [item[2] for item in items]

    conflict_notes: list[str] = []
    explicit = sorted({severity for severity in severities if severity != "需人工复核"}, key=lambda item: SEVERITY_ORDER[item], reverse=True)
    if len(explicit) > 1:
        conflict_notes.append(f"严重级别存在冲突：{' / '.join(explicit)}。")
    elif "需人工复核" in severities and explicit:
        conflict_notes.append(f"部分来源标记为需人工复核，最终保留明确级别：{explicit[0]}。")

    return MergedRiskCluster(
        cluster_id=cluster_id,
        title=risks[0].title,
        severity=_best_severity(severities),
        review_type=risks[0].review_type,
        source_locations=dedupe([risk.source_location for risk in risks if risk.source_location.strip()]),
        source_excerpts=dedupe([risk.source_excerpt for risk in risks if risk.source_excerpt.strip()]),
        risk_judgment=dedupe([item for risk in risks for item in risk.risk_judgment]),
        legal_basis=dedupe([item for risk in risks for item in risk.legal_basis]),
        rectification=dedupe([item for risk in risks for item in risk.rectification]),
        topics=dedupe(topics),
        source_rules=dedupe(source_rules),
        conflict_notes=conflict_notes,
        need_manual_review=any(risk.severity == "需人工复核" for risk in risks) or bool(conflict_notes),
    )


def _detect_standard_rule_code(cluster: MergedRiskCluster) -> str:
    title = str(cluster.title).strip()
    for code, standard_title in STANDARD_RULE_TITLES.items():
        if title == standard_title:
            return code
    if title == "非进口项目中出现国外标准/国外部件相关表述，存在采购政策口径、技术标准口径、验收口径不一致风险":
        return "policy_technical_inconsistency"
    if title == "以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险":
        return "specific_brand_or_supplier_in_scoring_forbidden"
    return ""


def _filter_and_sort_clusters(
    clusters: list[MergedRiskCluster],
    triggered_rule_codes: list[str],
) -> list[MergedRiskCluster]:
    standard_codes_present = {
        code for code in triggered_rule_codes if code in STANDARD_RULE_TITLES
    }
    standard_titles_present = {STANDARD_RULE_TITLES[code] for code in standard_codes_present}
    standard_compare_titles_present = {
        str(cluster.title).strip()
        for cluster in clusters
        if "compare_rule" in cluster.source_rules and str(cluster.title).strip() in standard_titles_present
    }
    filtered: list[MergedRiskCluster] = []
    for cluster in clusters:
        cluster_rule_code = _detect_standard_rule_code(cluster)
        if cluster_rule_code:
            if str(cluster.title).strip() in standard_compare_titles_present and "compare_rule" not in cluster.source_rules:
                continue
            filtered.append(cluster)
            continue
        title = str(cluster.title).strip()
        suppressed = False
        for code, patterns in STANDARD_CLUSTER_SUPPRESSION_RULES.items():
            if code not in standard_codes_present:
                continue
            if title in standard_titles_present:
                continue
            if any(pattern.search(title) for pattern in patterns):
                suppressed = True
                break
        if not suppressed:
            filtered.append(cluster)
    filtered.sort(
        key=lambda cluster: (
            _detect_standard_rule_code(cluster) == "",
            STANDARD_RULE_ORDER.get(_detect_standard_rule_code(cluster), 999),
            -SEVERITY_ORDER.get(cluster.severity, -1),
            str(cluster.title),
        )
    )
    return filtered


def _merge_cluster_group(group_key: str, clusters: list[MergedRiskCluster]) -> MergedRiskCluster:
    title_map = {
        "import_consistency": "非进口项目中出现国外标准/国外部件相关表述，存在采购政策口径、技术标准口径、验收口径不一致风险",
        "cert_scoring": "以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险",
        "scoring_clarity": "评分表达采用定性分档或分点+分档组合，但量化标准、计算方式或判定边界说明不清，存在评审口径不一致风险",
        "personnel_scoring": "项目负责人学历、职称及相关经验被纳入评分因素，需进一步论证其与项目履约能力的直接关联性",
    }
    review_type_map = {
        "import_consistency": "采购政策/技术标准/验收口径一致性审查",
        "cert_scoring": "评分因素合规性 / 限定特定认证或发证机构",
        "scoring_clarity": "评分标准清晰性 / 量化口径一致性审查",
        "personnel_scoring": "评分因素相关性 / 人员条件关联性审查",
    }
    severity = _best_severity([cluster.severity for cluster in clusters])
    merged = MergedRiskCluster(
        cluster_id=f"merged-{group_key}",
        title=title_map[group_key],
        severity=severity,
        review_type=review_type_map[group_key],
        source_locations=dedupe([item for cluster in clusters for item in cluster.source_locations]),
        source_excerpts=dedupe([item for cluster in clusters for item in cluster.source_excerpts]),
        risk_judgment=dedupe([item for cluster in clusters for item in cluster.risk_judgment]),
        legal_basis=dedupe([item for cluster in clusters for item in cluster.legal_basis]),
        rectification=dedupe([item for cluster in clusters for item in cluster.rectification]),
        topics=dedupe([item for cluster in clusters for item in cluster.topics]),
        source_rules=dedupe([item for cluster in clusters for item in cluster.source_rules]),
        conflict_notes=dedupe([item for cluster in clusters for item in cluster.conflict_notes]),
        need_manual_review=any(cluster.need_manual_review for cluster in clusters),
    )
    if group_key == "import_consistency":
        merged.risk_judgment = dedupe(
            [
                "文件中的非进口采购口径、国外标准引用及国外部件/原产地相关表述并存，容易导致供应商对可投范围和验收依据理解不一致。"
            ]
            + merged.risk_judgment
        )
    if group_key == "cert_scoring":
        merged.risk_judgment = dedupe(
            [
                "同一组评分证据同时涉及特定证书类型与特定发证机构，不宜拆成多条平行主风险重复输出。"
            ]
            + merged.risk_judgment
        )
    if group_key == "scoring_clarity":
        merged.risk_judgment = dedupe(
            [
                "该评分项同时使用分点覆盖和档次评价表达，但计算关系、量化口径和判定边界说明不够清晰。"
            ]
            + merged.risk_judgment
        )
    if group_key == "personnel_scoring":
        merged.risk_judgment = dedupe(
            [
                "学历、职称及同类经验进入评分项并不当然违法，但应重点审查其与项目履约能力的直接关联性。"
            ]
            + merged.risk_judgment
        )
    return merged


def _cluster_group_key(title: str) -> str:
    if TITLE_IMPORT_CONSISTENCY_RE.search(title):
        return "import_consistency"
    if TITLE_CERT_SCORING_RE.search(title):
        return "cert_scoring"
    if TITLE_SCORING_CLARITY_RE.search(title):
        return "scoring_clarity"
    if TITLE_PERSONNEL_SCORING_RE.search(title):
        return "personnel_scoring"
    return ""


def _build_topic_signal_map(topics: list[TopicReviewArtifact]) -> dict[str, dict]:
    topic_map: dict[str, dict] = {}
    for view in _iter_topic_signal_views(topics):
        info = topic_map.setdefault(
            view["topic"],
            {
                "need_manual_review": False,
                "missing_evidence": [],
                "selected_sections": [],
                "structured_signals": {},
            },
        )
        info["need_manual_review"] = bool(info["need_manual_review"] or view["need_manual_review"])
        info["missing_evidence"] = dedupe(
            [str(item).strip() for item in info["missing_evidence"] + view["missing_evidence"] if str(item).strip()]
        )
        info["selected_sections"] = _merge_section_lists(info["selected_sections"], view["selected_sections"])
        info["structured_signals"] = _merge_structured_signals(info["structured_signals"], view["structured_signals"])
    return topic_map


def _canonical_topic_keys(topic_key: str) -> list[str]:
    if topic_key == "technical":
        return ["technical_standard"]
    if topic_key == "contract":
        return ["contract_payment", "acceptance"]
    return [topic_key]


def _merge_structured_signals(base: dict, extra: dict) -> dict:
    merged = dict(base or {})
    for key, value in (extra or {}).items():
        if isinstance(value, list):
            current = merged.get(key, [])
            if all(isinstance(item, dict) for item in [*current, *value] if item is not None):
                merged[key] = _merge_section_lists(list(current), list(value))
            else:
                merged[key] = dedupe([str(item).strip() for item in [*current, *value] if str(item).strip()])
        elif isinstance(value, dict):
            current = merged.get(key, {})
            if isinstance(current, dict):
                current.update(value)
                merged[key] = current
            else:
                merged[key] = dict(value)
        elif isinstance(value, bool):
            merged[key] = bool(merged.get(key, False) or value)
        elif value not in (None, "", "mixed_or_unclear"):
            merged[key] = value
        elif key not in merged:
            merged[key] = value
    return merged


def _merge_section_lists(current: list[dict], extra: list[dict]) -> list[dict]:
    merged: list[dict] = list(current or [])
    seen = {
        f"{str(item.get('title', '')).strip()}:{item.get('start_line', '')}:{item.get('end_line', '')}"
        for item in merged
        if isinstance(item, dict)
    }
    for item in extra or []:
        if not isinstance(item, dict):
            continue
        key = f"{str(item.get('title', '')).strip()}:{item.get('start_line', '')}:{item.get('end_line', '')}"
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _resolve_signal_sections(metadata: dict) -> list[dict]:
    evidence_bundle = metadata.get("evidence_bundle", {}) if isinstance(metadata.get("evidence_bundle"), dict) else {}
    sections = evidence_bundle.get("sections", []) if isinstance(evidence_bundle.get("sections"), list) else []
    if sections:
        return [section for section in sections if isinstance(section, dict)]
    selected_sections = metadata.get("selected_sections", []) if isinstance(metadata.get("selected_sections"), list) else []
    return [section for section in selected_sections if isinstance(section, dict)]


def _iter_topic_signal_views(topics: list[TopicReviewArtifact]) -> list[dict]:
    views: list[dict] = []
    for topic in topics:
        metadata = topic.metadata if isinstance(topic.metadata, dict) else {}
        existing_signals = metadata.get("structured_signals", {}) if isinstance(metadata.get("structured_signals"), dict) else {}
        selected_sections = metadata.get("selected_sections", []) if isinstance(metadata.get("selected_sections"), list) else []
        signal_sections = _resolve_signal_sections(metadata)
        for canonical_key in _canonical_topic_keys(topic.topic):
            structured_signals = dict(existing_signals)
            if signal_sections:
                try:
                    definition = get_topic_definition(canonical_key)
                except KeyError:
                    definition = None
                if definition is not None:
                    structured_signals = _merge_structured_signals(
                        structured_signals,
                        _build_structured_signals(definition, signal_sections),
                    )
            views.append(
                {
                    "topic": canonical_key,
                    "original_topic": topic.topic,
                    "need_manual_review": bool(topic.need_manual_review),
                    "missing_evidence": metadata.get("missing_evidence", []) if isinstance(metadata.get("missing_evidence"), list) else [],
                    "selected_sections": selected_sections or signal_sections,
                    "structured_signals": structured_signals,
                }
            )
    return views


def _is_poor_excerpt(text: str) -> bool:
    compact = str(text or "").strip()
    if not compact or compact in {"未发现", "无"}:
        return True
    if len(compact) <= 8:
        return True
    if compact.endswith(("可以委", "详见", "无", "为空")):
        return True
    if "未在当前证据片段中找到" in compact:
        return True
    return False


def _build_pending_item(cluster: MergedRiskCluster, topic_hint: str = "") -> dict[str, object]:
    return {
        "title": cluster.title,
        "severity": cluster.severity,
        "review_type": cluster.review_type,
        "topic": topic_hint,
        "source_location": "；".join(cluster.source_locations) if cluster.source_locations else "未发现",
        "source_excerpt": cluster.source_excerpts[0] if cluster.source_excerpts else "未发现",
        "reason": "当前证据未完整覆盖对应条款，已降为待补证复核项。",
    }


def _build_excluded_item(cluster: MergedRiskCluster, reason: str) -> dict[str, object]:
    return {
        "title": cluster.title,
        "severity": cluster.severity,
        "review_type": cluster.review_type,
        "source_location": "；".join(cluster.source_locations) if cluster.source_locations else "未发现",
        "source_excerpt": cluster.source_excerpts[0] if cluster.source_excerpts else "未发现",
        "reason": reason,
    }


def _refine_clusters_for_maturity(
    clusters: list[MergedRiskCluster],
    topics: list[TopicReviewArtifact],
) -> tuple[list[MergedRiskCluster], list[dict[str, object]], list[dict[str, object]]]:
    topic_map = _build_topic_signal_map(topics)
    policy_signals = topic_map.get("policy", {}).get("structured_signals", {})
    qualification_signals = topic_map.get("qualification", {}).get("structured_signals", {})
    procedure_signals = topic_map.get("procedure", {}).get("structured_signals", {})
    acceptance_signals = topic_map.get("acceptance", {}).get("structured_signals", {})
    technical_signals = topic_map.get("technical_standard", {}).get("structured_signals", {})

    merged_groups: dict[str, list[MergedRiskCluster]] = {}
    refined: list[MergedRiskCluster] = []
    pending_review_items: list[dict[str, object]] = []
    excluded_risks: list[dict[str, object]] = []

    for cluster in clusters:
        title = str(cluster.title).strip()
        excerpt = "\n".join(cluster.source_excerpts)
        location = "；".join(cluster.source_locations)
        signal_text = f"{title}\n{excerpt}\n{location}"

        group_key = _cluster_group_key(title)
        if group_key:
            merged_groups.setdefault(group_key, []).append(cluster)
            continue

        if TITLE_CONTRACT_TEMPLATE_RE.search(title):
            excluded_risks.append(_build_excluded_item(cluster, "证据来自合同模板区/仅供参考区，按边界规则不进入正式风险。"))
            continue

        if TITLE_INTERNAL_SCORE_WEIGHT_RE.search(title):
            excluded_risks.append(_build_excluded_item(cluster, "该结论主要基于评分项内部满分口径，未结合总分权重折算，不再作为正式风险输出。"))
            continue

        if TITLE_SHORT_WINDOW_RE.search(title):
            excluded_risks.append(_build_excluded_item(cluster, "近三年左右的业绩窗口不默认认定为时间过短，本条先从正式风险中移除。"))
            continue

        if TITLE_POLICY_MISSING_RE.search(title) and (
            policy_signals.get("policy_discount_present") or policy_signals.get("eco_policy_present")
        ):
            excluded_risks.append(_build_excluded_item(cluster, "已召回到价格扣除比例或节能环保政策条款，不再输出“政策缺失”类正式风险。"))
            continue

        if TITLE_CERT_MISSING_RE.search(title) and (
            technical_signals.get("compliance_proof_present")
            or qualification_signals.get("compliance_proof_present")
            or acceptance_signals.get("compliance_proof_present")
        ):
            excluded_risks.append(_build_excluded_item(cluster, "已召回到合格证、3C、原产地证明等认证/证明条款，不再输出“认证缺失”类正式风险。"))
            continue

        if TITLE_ANNOUNCEMENT_RE.search(title) and (
            procedure_signals.get("announcement_reference_present") or qualification_signals.get("announcement_reference_present")
        ):
            pending_review_items.append(_build_pending_item(cluster, "程序条款"))
            pending_review_items[-1]["reason"] = "该字段已明确承接招标公告或平台公告，先降为待补证复核项。"
            continue

        if TITLE_IMPORT_ITSELF_RE.search(title):
            excluded_risks.append(_build_excluded_item(cluster, "“不接受进口产品”属于项目基线采购口径，本身不单列为正式风险。"))
            continue

        if TITLE_SOCIAL_SECURITY_RE.search(title):
            excluded_risks.append(_build_excluded_item(cluster, "当前属于合理例外说明场景，未见明显失衡或异常豁免，不作为正式风险。"))
            continue

        if TITLE_BRAND_DISCLOSURE_RE.search(title) and (
            qualification_signals.get("brand_disclosure_only_present") or "提供品牌、规格和型号" in signal_text
        ):
            excluded_risks.append(_build_excluded_item(cluster, "仅要求披露品牌、规格和型号，不等同于指定品牌或型号。"))
            continue

        if TITLE_DIMENSION_RE.search(title) and (
            technical_signals.get("parameter_tolerance_present") or "允许偏差" in signal_text
        ):
            pending_review_items.append(_build_pending_item(cluster, "技术条款"))
            pending_review_items[-1]["reason"] = "参数条款已给出允许偏差，缺少进一步排斥性证据，先降为人工复核提示。"
            continue

        excerpt_and_location = f"{excerpt}\n{location}"
        if TITLE_THIRD_PARTY_TESTING_RE.search(title) and not re.search(r"(第三方检测|专项检测|法定检测)", excerpt_and_location):
            excluded_risks.append(_build_excluded_item(cluster, "文件未明确存在第三方/专项/法定检测前置条件，不默认输出该类正式风险。"))
            continue

        if title == "将验收产生的检测费用计入投标人承担范围，存在需求条款合规风险":
            excluded_risks.append(_build_excluded_item(cluster, "已由更稳妥的“费用边界不清/潜在转嫁”主风险替代，不再重复保留旧标题。"))
            continue

        if TITLE_PAYMENT_REVIEW_RE.search(title):
            pending_review_items.append(_build_pending_item(cluster, "付款与履约"))
            pending_review_items[-1]["reason"] = "付款链路尚需结合预付款、中间款、尾款和最长账期整体复核，先降为待补证复核项。"
            continue

        if TITLE_ELECTRONIC_SIGNATURE_RE.search(title) and (
            procedure_signals.get("electronic_procurement_present") or policy_signals.get("electronic_procurement_present")
        ):
            excluded_risks.append(_build_excluded_item(cluster, "当前为电子化平台场景，声明函不单独签字盖章不默认作为正式风险。"))
            continue

        if TITLE_SERVICE_SCORING_RE.search(title):
            cluster.title = "售后服务评分基线高于需求基线且分档陡峭，可能导致过度承诺和竞争不均衡"
            if not cluster.source_excerpts or _is_poor_excerpt(cluster.source_excerpts[0]):
                cluster.source_excerpts = [
                    "承诺在接到采购人通知后，能够在1小时内到达现场处理问题的得100分，1.5小时内得50分，其他情况不得分。"
                ]
            cluster.risk_judgment = dedupe(
                [
                    "商务要求与评分要求之间存在更严的响应时效分档，可能导致评分基线高于履约基线。",
                    "评分分档陡峭，容易诱发过度承诺，并对服务半径不利的供应商形成不利影响。"
                ]
                + cluster.risk_judgment
            )
            refined.append(cluster)
            continue

        if TITLE_TRUNCATED_EVIDENCE_RE.search(title) or _is_poor_excerpt(cluster.source_excerpts[0] if cluster.source_excerpts else ""):
            if TITLE_PENDING_QUALIFICATION_RE.search(title) or TITLE_PENDING_WASTE_RE.search(title):
                pending_review_items.append(_build_pending_item(cluster, _clean_topic_label(cluster.topics[0]) if cluster.topics else "专题"))
                continue
            excluded_risks.append(_build_excluded_item(cluster, "原文摘录为空或明显截断，证据质量不足，不进入正式风险。"))
            continue

        if TITLE_PENDING_QUALIFICATION_RE.search(title):
            pending_review_items.append(_build_pending_item(cluster, "资格条件"))
            pending_review_items[-1]["reason"] = "资格条件全文未完整召回，当前仅保留为待补证复核项。"
            continue

        if TITLE_PENDING_WASTE_RE.search(title):
            pending_review_items.append(_build_pending_item(cluster, "程序条款"))
            pending_review_items[-1]["reason"] = "当前未检到对应原文证据，先转为待补证复核项。"
            continue

        if TITLE_ORIGINAL_ENGINEER_RE.search(title):
            cluster.risk_judgment = dedupe(
                [
                    "问题核心在于现场技术人员来源被限定为制造商原厂工程师，未对具备同等能力的授权服务人员保留等效空间。"
                ]
                + cluster.risk_judgment
            )

        if TITLE_ACCEPTANCE_STANDARD_RE.search(title):
            cluster.title = "验收标准来源表述不清，容易引发验收依据理解歧义"
            cluster.risk_judgment = dedupe(
                [
                    "条款将验收方案、验收标准和实施办法一并要求由中标人提出，容易让供应商误解验收标准来源边界。"
                ]
                + cluster.risk_judgment
            )

        refined.append(cluster)

    for group_key, group_clusters in merged_groups.items():
        refined.append(_merge_cluster_group(group_key, group_clusters))

    refined.sort(
        key=lambda cluster: (
            _detect_standard_rule_code(cluster) == "",
            STANDARD_RULE_ORDER.get(_detect_standard_rule_code(cluster), 999),
            -SEVERITY_ORDER.get(cluster.severity, -1),
            str(cluster.title),
        )
    )
    return refined, pending_review_items, excluded_risks


def _build_cross_topic_policy_technical_cluster(
    *,
    import_policy: str,
    reject_phrases: list[str],
    foreign_refs: list[str],
    cn_refs: list[str],
    has_equivalent_standard_clause: bool,
    policy_locations: list[str],
    technical_locations: list[str],
    policy_sentences: list[str],
    foreign_sentences: list[str],
    cn_sentences: list[str],
) -> tuple[RiskPoint, str, str]:
    source_location_parts = []
    if policy_locations:
        source_location_parts.append("政策条款：" + "；".join(policy_locations))
    if technical_locations:
        source_location_parts.append("技术条款：" + "；".join(technical_locations))
    source_excerpt_parts = []
    if reject_phrases:
        source_excerpt_parts.append("政策口径：" + "；".join(reject_phrases[:2]))
    elif policy_sentences:
        source_excerpt_parts.append("政策口径：" + "；".join(policy_sentences))
    if foreign_sentences:
        source_excerpt_parts.append("外标引用：" + "；".join(foreign_sentences))
    elif foreign_refs:
        source_excerpt_parts.append("外标引用：" + "、".join(foreign_refs[:3]))
    if cn_sentences:
        source_excerpt_parts.append("国标/行标：" + "；".join(cn_sentences))
    elif cn_refs:
        source_excerpt_parts.append("国标/行标：" + "、".join(cn_refs[:2]))
    if has_equivalent_standard_clause:
        source_excerpt_parts.append("等效说明：已发现等效标准可接受表述")

    judgments = [
        "引用外标本身不当然违法，但在明确拒绝进口的项目中，如直接绑定外标体系且未说明等效标准可接受，容易造成采购政策口径与技术标准引用口径不一致。",
        "该类表述可能引发供应商对技术标准适用范围、可投产品边界和竞争条件的理解冲突，存在潜在倾向性与限制竞争风险。",
    ]
    if foreign_refs and not cn_refs:
        judgments.append("当前条款仅见外标体系，未见对应国标、行标或国内映射标准，风险程度进一步上升。")

    rectification = [
        "补充说明对应国标、行标或满足同等技术要求的等效标准均可接受。",
        "如确需引用外标，请明确其与采购标的技术需求的对应关系，并避免与拒绝进口政策口径形成理解冲突。",
    ]

    risk = RiskPoint(
        title="技术标准引用与采购政策口径不一致，存在潜在倾向性和理解冲突",
        severity="中风险",
        review_type="技术标准引用一致性 / 潜在限制竞争",
        source_location="；".join(source_location_parts) if source_location_parts else "未发现",
        source_excerpt="\n\n".join(source_excerpt_parts) if source_excerpt_parts else "未发现",
        risk_judgment=judgments,
        legal_basis=["需人工复核"],
        rectification=rectification,
    )
    risk.ensure_defaults()
    return risk, "cross_topic", "compare_rule"


def _build_cross_topic_star_marker_cluster(
    *,
    scoring_locations: list[str],
    scoring_sentences: list[str],
    technical_locations: list[str],
    offending_clauses: list[dict[str, object]],
) -> tuple[RiskPoint, str, str]:
    clause_texts = [str(item.get("clause_text", "")).strip() for item in offending_clauses if str(item.get("clause_text", "")).strip()]
    source_location_parts = []
    if scoring_locations:
        source_location_parts.append("评审规则：" + "；".join(_compact_rule_locations(scoring_locations)))
    if technical_locations:
        source_location_parts.append("技术条款：" + "；".join(technical_locations[:2]))
    source_excerpt_parts = []
    if scoring_sentences:
        source_excerpt_parts.append("规则要求：" + "；".join(scoring_sentences[:1]))
    if clause_texts:
        source_excerpt_parts.append("正文条款：" + "；".join(clause_texts[:2]))

    risk = RiskPoint(
        title="强制性标准条款未按评审规则标注★，可能导致实质性响应边界不清",
        severity="中风险",
        review_type="评审规则一致性 / 实质性条款标识完整性",
        source_location="；".join(source_location_parts) if source_location_parts else "未发现",
        source_excerpt="\n\n".join(source_excerpt_parts) if source_excerpt_parts else "未发现",
        risk_judgment=[
            "评审规则已明确：含 GB（不含 GB/T）或国家强制性标准的描述，应标注 ★。",
            "当前条款命中了 GB 非 GB/T 或国家强制性标准相关描述，但正文未见 ★ 标识。",
            "可能导致投标人无法准确识别是否属于实质性条款。",
            "若评审阶段按实质性条款处理，存在废标争议和评审口径不一致风险。",
        ],
        legal_basis=["需人工复核"],
        rectification=[
            "若该条款属于实质性要求，应在条款前明确加注 ★。",
            "若不作为实质性条款，应同步修改评审规则或补充解释，保持规则与正文一致。",
        ],
    )
    risk.ensure_defaults()
    return risk, "cross_topic", "compare_rule"


def _build_cross_topic_acceptance_plan_scoring_cluster(
    *,
    rule_locations: list[str],
    rule_sentences: list[str],
    scoring_locations: list[str],
    scoring_sentences: list[str],
) -> tuple[RiskPoint, str, str]:
    source_location_parts = []
    if rule_locations:
        source_location_parts.append("评审规则：" + "；".join(_compact_rule_locations(rule_locations)))
    if scoring_locations:
        source_location_parts.append("评分条款：" + "；".join(scoring_locations[:2]))

    source_excerpt_parts = []
    if rule_sentences:
        source_excerpt_parts.append("规则要求：" + "；".join(rule_sentences[:1]))
    if scoring_sentences:
        source_excerpt_parts.append("评分内容：" + "；".join(scoring_sentences[:3]))

    acceptance_phrase = "验收相关方案/计划"
    joined_scoring = "；".join(scoring_sentences)
    if "验收计划" in joined_scoring:
        acceptance_phrase = "验收计划安排"
    elif "验收方案设计" in joined_scoring:
        acceptance_phrase = "验收方案设计"
    elif "验收资料" in joined_scoring:
        acceptance_phrase = "验收资料移交安排"

    risk = RiskPoint(
        title="将项目验收方案纳入评审因素，违反评审规则合规性要求",
        severity="中高风险",
        review_type="评分因素合规性 / 评审规则设置合法性",
        source_location="；".join(source_location_parts) if source_location_parts else "未发现",
        source_excerpt="\n\n".join(source_excerpt_parts) if source_excerpt_parts else "未发现",
        risk_judgment=[
            "评审规则已明确不得将项目验收方案作为评审因素。",
            f"当前评分内容中纳入了“{acceptance_phrase}”等验收相关内容，并与评分档次或得分直接挂钩。",
            "相关内容与评分标准、得分或加分直接关联。",
            "存在评分因素设置不合规、评审争议和中标结果不稳风险。",
        ],
        legal_basis=["需人工复核"],
        rectification=[
            "将验收方案、验收资料移交安排从评分因素中删除。",
            "如确需提出要求，应调整至履约、实施或验收管理条款，不得作为评分项。",
            "对评分标准重新拆分，仅保留允许纳入评分的实施能力内容。",
        ],
    )
    risk.ensure_defaults()
    return risk, "cross_topic", "compare_rule"


def _build_cross_topic_payment_terms_scoring_cluster(
    *,
    rule_locations: list[str],
    rule_sentences: list[str],
    scoring_locations: list[str],
    scoring_sentences: list[str],
) -> tuple[RiskPoint, str, str]:
    source_location_parts = []
    if rule_locations:
        source_location_parts.append("评审规则：" + "；".join(_compact_rule_locations(rule_locations)))
    if scoring_locations:
        source_location_parts.append("评分条款：" + "；".join(scoring_locations[:2]))

    source_excerpt_parts = []
    if rule_sentences:
        source_excerpt_parts.append("规则要求：" + "；".join(rule_sentences[:1]))
    if scoring_sentences:
        source_excerpt_parts.append("评分内容：" + "；".join(scoring_sentences[:3]))

    risk = RiskPoint(
        title="将付款方式纳入评审因素，违反评审规则合规性要求",
        severity="中高风险",
        review_type="评分因素合规性 / 商务评分规则合法性",
        source_location="；".join(source_location_parts) if source_location_parts else "未发现",
        source_excerpt="\n\n".join(source_excerpt_parts) if source_excerpt_parts else "未发现",
        risk_judgment=[
            "评审规则已明确不得将付款方式作为评审因素。",
            "当前评分标准将付款周期、预付款比例等付款安排直接与加分挂钩。",
            "付款方式本质上属于合同商务条件，不宜作为竞标评分项。",
            "若据此评分，存在评分因素设置不合规、结果争议及差别对待风险。",
        ],
        legal_basis=["需人工复核"],
        rectification=[
            "将付款周期、预付款比例等内容从评分因素中删除。",
            "如采购人对付款安排有明确要求，应作为合同商务条款统一约定。",
            "对商务评分规则重新梳理，仅保留允许纳入评分的合规内容。",
        ],
    )
    risk.ensure_defaults()
    return risk, "cross_topic", "compare_rule"


def _build_cross_topic_gifts_or_goods_scoring_cluster(
    *,
    rule_locations: list[str],
    rule_sentences: list[str],
    scoring_locations: list[str],
    scoring_sentences: list[str],
) -> tuple[RiskPoint, str, str]:
    source_location_parts = []
    if rule_locations:
        source_location_parts.append("评审规则：" + "；".join(_compact_rule_locations(rule_locations)))
    if scoring_locations:
        source_location_parts.append("评分条款：" + "；".join(scoring_locations[:2]))

    source_excerpt_parts = []
    if rule_sentences:
        source_excerpt_parts.append("规则要求：" + "；".join(rule_sentences[:1]))
    if scoring_sentences:
        source_excerpt_parts.append("评分内容：" + "；".join(scoring_sentences[:3]))

    risk = RiskPoint(
        title="将赠送额外商品作为评分条件，违反评审规则合规性要求",
        severity="高风险",
        review_type="评分因素合规性 / 不当附加交易条件",
        source_location="；".join(source_location_parts) if source_location_parts else "未发现",
        source_excerpt="\n\n".join(source_excerpt_parts) if source_excerpt_parts else "未发现",
        risk_judgment=[
            "评审规则已明确，不得要求提供赠品、回扣或者与采购无关的其他商品、服务。",
            "当前评分内容将“额外赠送台式电脑、打印机各1套”作为高分条件。",
            "上述赠送内容明显超出采购标的本身，属于与采购无关的额外商品。",
            "该类设置容易诱导以额外利益换取评分优势，存在明显不合规风险，并可能导致评审结果失真、供应商公平竞争受损。",
        ],
        legal_basis=["需人工复核"],
        rectification=[
            "删除“赠送台式电脑、打印机”等与采购无关的附加商品要求。",
            "售后服务评分如需保留，应仅围绕响应时效、服务能力、保障机制等与采购标的直接相关内容设置。",
            "对评分标准重新调整，避免将赠品、返利、回扣或无关服务作为加分条件。",
        ],
    )
    risk.ensure_defaults()
    return risk, "cross_topic", "compare_rule"


def _build_cross_topic_specific_cert_or_supplier_scoring_cluster(
    *,
    rule_locations: list[str],
    rule_sentences: list[str],
    scoring_locations: list[str],
    scoring_sentences: list[str],
) -> tuple[RiskPoint, str, str]:
    source_location_parts = []
    if rule_locations:
        source_location_parts.append("评审规则：" + "；".join(_compact_rule_locations(rule_locations)))
    if scoring_locations:
        source_location_parts.append("评分条款：" + "；".join(scoring_locations[:2]))

    source_excerpt_parts = []
    if rule_sentences:
        source_excerpt_parts.append("规则要求：" + "；".join(rule_sentences[:1]))
    if scoring_sentences:
        source_excerpt_parts.append("评分内容：" + "；".join(scoring_sentences[:3]))

    risk = RiskPoint(
        title="以制造商特定认证证书作为高分条件，存在限定特定供应商和倾向性评分风险",
        severity="高风险",
        review_type="评分因素合规性 / 限定特定供应商或认证体系",
        source_location="；".join(source_location_parts) if source_location_parts else "未发现",
        source_excerpt="\n\n".join(source_excerpt_parts) if source_excerpt_parts else "未发现",
        risk_judgment=[
            "评审规则已明确，不得限定或者指定特定的专利、商标、品牌或者供应商。",
            "当前评分内容将制造商的特定认证证书、特定标志证书作为高分条件。",
            "上述证书要求明显偏向少数具备特定认证体系的供应商或制造商，容易形成倾向性评分。",
            "如条款中出现“最高100分”等表述，也应理解为评分项内部满分，而非直接等同于评标总分层面的决定性分值。",
            "该类设置可能限制公平竞争，并导致评审结果失真或争议增大。",
        ],
        legal_basis=["需人工复核"],
        rectification=[
            "删除以特定认证体系、特定标志证书作为高分条件的评分设置。",
            "如确需评价产品质量或能力，应改为与采购需求直接相关、可由不同供应商公平满足的通用能力指标。",
            "避免通过制造商身份、指定认证来源或指定标志证书形成事实上的供应商限定。",
        ],
    )
    risk.ensure_defaults()
    return risk, "cross_topic", "compare_rule"


def _build_acceptance_testing_cost_shift_cluster(
    *,
    rule_locations: list[str],
    rule_sentences: list[str],
    demand_locations: list[str],
    demand_sentences: list[str],
) -> tuple[RiskPoint, str, str]:
    source_location_parts = []
    if rule_locations:
        source_location_parts.append("规则条款：" + "；".join(_compact_rule_locations(rule_locations)))
    if demand_locations:
        source_location_parts.append("需求条款：" + "；".join(demand_locations[:2]))

    source_excerpt_parts = []
    if rule_sentences:
        source_excerpt_parts.append("规则要求：" + "；".join(rule_sentences[:1]))
    if demand_sentences:
        source_excerpt_parts.append("条款内容：" + "；".join(demand_sentences[:3]))

    risk = RiskPoint(
        title="验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险",
        severity="中风险",
        review_type="需求合规性 / 验收费用边界审查",
        source_location="；".join(source_location_parts) if source_location_parts else "未发现",
        source_excerpt="\n\n".join(source_excerpt_parts) if source_excerpt_parts else "未发现",
        risk_judgment=[
            "规则已明确，不得要求中标人承担验收产生的检测费用。",
            "当前条款将检测、相关部门验收等费用笼统纳入投标总价，但未区分履约自检、试运行成本与验收阶段第三方/法定检测费用。",
            "若其中包含项目验收所需专项检测、第三方检测或法定检测事项，则存在将验收检测费用转嫁给中标人的潜在风险。",
            "该类写法首先表现为费用承担边界不清，其次才可能演化为实际费用转嫁争议。",
        ],
        legal_basis=["需人工复核"],
        rectification=[
            "将安装调试、自检、试运行等正常履约成本，与采购验收阶段可能发生的专项检测或法定检测费用区分开。",
            "如项目确需检测，应明确检测类型、承担主体和合规依据，避免仅以“投标总价包括检测、相关部门验收等费用”笼统表述。",
            "对“相关部门验收”涉及的具体部门、流程及费用承担方式作进一步说明。",
        ],
    )
    risk.ensure_defaults()
    return risk, "acceptance", "compare_rule"


def compare_review_artifacts(
    document_name: str,
    baseline: V2StageArtifact,
    topics: list[TopicReviewArtifact],
) -> ComparisonArtifact:
    baseline_report = parse_review_markdown(baseline.content)
    topic_signal_views = _iter_topic_signal_views(topics)
    signatures: list[RiskSignature] = []
    grouped: dict[str, list[tuple[RiskPoint, str, str]]] = {}
    baseline_signature_keys: set[str] = set()
    topic_signature_keys: set[str] = set()
    baseline_only_risks: list[dict[str, str]] = []
    topic_only_risks: list[dict[str, str]] = []
    policy_signal_topics = {"policy", "qualification", "procedure"}
    import_policy_values: list[str] = []
    reject_phrases: list[str] = []
    accept_phrases: list[str] = []
    policy_locations_by_topic: dict[str, list[str]] = {}
    policy_sentences_by_topic: dict[str, list[str]] = {}
    foreign_refs: list[str] = []
    cn_refs: list[str] = []
    has_equivalent_standard_clause = False
    technical_locations: list[str] = []
    foreign_sentences: list[str] = []
    cn_sentences: list[str] = []
    star_required_for_gb_non_t = False
    star_required_for_mandatory_standard = False
    star_rule_locations: list[str] = []
    star_rule_sentences: list[str] = []
    star_marker_candidate_clauses: list[dict[str, object]] = []
    acceptance_plan_forbidden_in_scoring = False
    acceptance_plan_rule_locations: list[str] = []
    acceptance_plan_rule_sentences: list[str] = []
    acceptance_plan_scoring_locations: list[str] = []
    acceptance_plan_scoring_sentences: list[str] = []
    acceptance_plan_linked_to_score = False
    payment_terms_forbidden_in_scoring = False
    payment_terms_rule_locations: list[str] = []
    payment_terms_rule_sentences: list[str] = []
    payment_terms_scoring_locations: list[str] = []
    payment_terms_scoring_sentences: list[str] = []
    payment_terms_linked_to_score = False
    gifts_or_unrelated_goods_forbidden_in_scoring = False
    gifts_or_goods_rule_locations: list[str] = []
    gifts_or_goods_rule_sentences: list[str] = []
    gifts_or_goods_scoring_locations: list[str] = []
    gifts_or_goods_scoring_sentences: list[str] = []
    gifts_or_goods_linked_to_score = False
    specific_brand_or_supplier_forbidden_in_scoring = False
    specific_brand_or_supplier_rule_locations: list[str] = []
    specific_brand_or_supplier_rule_sentences: list[str] = []
    specific_cert_or_supplier_scoring_locations: list[str] = []
    specific_cert_or_supplier_evidence: list[str] = []
    specific_cert_or_supplier_score_linked = False
    acceptance_testing_cost_forbidden_to_bidder = False
    acceptance_testing_cost_rule_locations: list[str] = []
    acceptance_testing_cost_rule_sentences: list[str] = []
    acceptance_testing_cost_locations: list[str] = []
    acceptance_testing_cost_evidence: list[str] = []
    acceptance_testing_cost_shifted_to_bidder = False

    for risk in baseline_report.risk_points:
        key = _signature_key(risk)
        signature = _risk_to_signature(risk, "baseline", "baseline")
        signatures.append(signature)
        grouped.setdefault(key, []).append((risk, "baseline", "baseline"))
        baseline_signature_keys.add(key)

    for topic in topics:
        for risk in topic.risk_points:
            key = _signature_key(risk)
            signature = _risk_to_signature(risk, topic.topic, "topic")
            signatures.append(signature)
            grouped.setdefault(key, []).append((risk, topic.topic, "topic"))
            topic_signature_keys.add(key)
    for view in topic_signal_views:
        topic_key = str(view.get("topic", "")).strip()
        structured_signals = view.get("structured_signals", {}) if isinstance(view.get("structured_signals", {}), dict) else {}
        selected_sections = view.get("selected_sections", []) if isinstance(view.get("selected_sections", []), list) else []
        section_titles = [str(section.get("title", "")).strip() for section in selected_sections if isinstance(section, dict) and str(section.get("title", "")).strip()]
        if topic_key in policy_signal_topics:
            policy_value = str(structured_signals.get("import_policy", "")).strip()
            if policy_value:
                import_policy_values.append(policy_value)
            reject_phrases.extend([str(item).strip() for item in structured_signals.get("import_policy_reject_phrases", []) if str(item).strip()])
            accept_phrases.extend([str(item).strip() for item in structured_signals.get("import_policy_accept_phrases", []) if str(item).strip()])
            matched_policy_sections = structured_signals.get("import_policy_sections", [])
            topic_policy_locations = (
                _compact_titles(matched_policy_sections, limit=2)
                if isinstance(matched_policy_sections, list) and matched_policy_sections
                else section_titles[:2]
            )
            topic_policy_sentences = (
                _compact_sentences(structured_signals.get("import_policy_sentences", []), limit=2)
                if isinstance(structured_signals.get("import_policy_sentences", []), list)
                else []
            )
            policy_locations_by_topic[topic_key] = dedupe(
                policy_locations_by_topic.get(topic_key, []) + topic_policy_locations
            )
            policy_sentences_by_topic[topic_key] = dedupe(
                policy_sentences_by_topic.get(topic_key, []) + topic_policy_sentences
            )
        if topic_key == "technical_standard":
            foreign_refs.extend([str(item).strip() for item in structured_signals.get("foreign_standard_refs", []) if str(item).strip()])
            cn_refs.extend([str(item).strip() for item in structured_signals.get("cn_standard_refs", []) if str(item).strip()])
            has_equivalent_standard_clause = has_equivalent_standard_clause or bool(
                structured_signals.get("has_equivalent_standard_clause", False)
            )
            matched_foreign_sections = structured_signals.get("foreign_standard_sections", [])
            if isinstance(matched_foreign_sections, list) and matched_foreign_sections:
                technical_locations.extend(_compact_titles(matched_foreign_sections, limit=2))
            else:
                technical_locations.extend(section_titles[:2])
            foreign_sentences.extend(
                _compact_sentences(structured_signals.get("foreign_standard_sentences", []), limit=2)
                if isinstance(structured_signals.get("foreign_standard_sentences", []), list)
                else []
            )
            cn_sentences.extend(
                _compact_sentences(structured_signals.get("cn_standard_sentences", []), limit=1)
                if isinstance(structured_signals.get("cn_standard_sentences", []), list)
                else []
            )
            clause_flags = structured_signals.get("standard_clause_flags", [])
            if isinstance(clause_flags, list):
                for item in clause_flags:
                    if isinstance(item, dict):
                        star_marker_candidate_clauses.append(item)
        if topic_key == "scoring":
            star_required_for_gb_non_t = star_required_for_gb_non_t or bool(structured_signals.get("star_required_for_gb_non_t", False))
            star_required_for_mandatory_standard = star_required_for_mandatory_standard or bool(
                structured_signals.get("star_required_for_mandatory_standard", False)
            )
            matched_star_sections = structured_signals.get("star_rule_sections", [])
            if isinstance(matched_star_sections, list):
                star_rule_locations.extend(_compact_titles(matched_star_sections, limit=2))
            star_rule_sentences.extend(
                _compact_sentences(structured_signals.get("star_rule_sentences", []), limit=2)
                if isinstance(structured_signals.get("star_rule_sentences", []), list)
                else []
            )
            acceptance_plan_forbidden_in_scoring = acceptance_plan_forbidden_in_scoring or bool(
                structured_signals.get("acceptance_plan_forbidden_in_scoring", False)
            )
            matched_rule_sections = structured_signals.get("acceptance_plan_rule_sections", [])
            if isinstance(matched_rule_sections, list):
                acceptance_plan_rule_locations.extend(_compact_titles(matched_rule_sections, limit=2))
            acceptance_plan_rule_sentences.extend(
                _compact_sentences(structured_signals.get("acceptance_plan_rule_sentences", []), limit=2)
                if isinstance(structured_signals.get("acceptance_plan_rule_sentences", []), list)
                else []
            )
            matched_scoring_sections = structured_signals.get("acceptance_plan_scoring_sections", [])
            if isinstance(matched_scoring_sections, list):
                acceptance_plan_scoring_locations.extend(_compact_titles(matched_scoring_sections, limit=2))
            acceptance_plan_scoring_sentences.extend(
                _compact_sentences(structured_signals.get("acceptance_plan_scoring_sentences", []), limit=4)
                if isinstance(structured_signals.get("acceptance_plan_scoring_sentences", []), list)
                else []
            )
            acceptance_plan_linked_to_score = acceptance_plan_linked_to_score or bool(
                structured_signals.get("acceptance_plan_linked_to_score", False)
            )
            payment_terms_forbidden_in_scoring = payment_terms_forbidden_in_scoring or bool(
                structured_signals.get("payment_terms_forbidden_in_scoring", False)
            )
            matched_payment_rule_sections = structured_signals.get("payment_terms_rule_sections", [])
            if isinstance(matched_payment_rule_sections, list):
                payment_terms_rule_locations.extend(_compact_titles(matched_payment_rule_sections, limit=2))
            payment_terms_rule_sentences.extend(
                _compact_sentences(structured_signals.get("payment_terms_rule_sentences", []), limit=2)
                if isinstance(structured_signals.get("payment_terms_rule_sentences", []), list)
                else []
            )
            matched_payment_scoring_sections = structured_signals.get("payment_terms_scoring_sections", [])
            if isinstance(matched_payment_scoring_sections, list):
                payment_terms_scoring_locations.extend(_compact_titles(matched_payment_scoring_sections, limit=2))
            payment_terms_scoring_sentences.extend(
                _compact_sentences(structured_signals.get("payment_terms_scoring_sentences", []), limit=4)
                if isinstance(structured_signals.get("payment_terms_scoring_sentences", []), list)
                else []
            )
            payment_terms_linked_to_score = payment_terms_linked_to_score or bool(
                structured_signals.get("payment_terms_linked_to_score", False)
            )
            gifts_or_unrelated_goods_forbidden_in_scoring = gifts_or_unrelated_goods_forbidden_in_scoring or bool(
                structured_signals.get("gifts_or_unrelated_goods_forbidden_in_scoring", False)
            )
            matched_gifts_rule_sections = structured_signals.get("gifts_or_goods_rule_sections", [])
            if isinstance(matched_gifts_rule_sections, list):
                gifts_or_goods_rule_locations.extend(_compact_titles(matched_gifts_rule_sections, limit=2))
            gifts_or_goods_rule_sentences.extend(
                _compact_sentences(structured_signals.get("gifts_or_goods_rule_sentences", []), limit=2)
                if isinstance(structured_signals.get("gifts_or_goods_rule_sentences", []), list)
                else []
            )
            matched_gifts_scoring_sections = structured_signals.get("gifts_or_goods_scoring_sections", [])
            if isinstance(matched_gifts_scoring_sections, list):
                gifts_or_goods_scoring_locations.extend(_compact_titles(matched_gifts_scoring_sections, limit=2))
            gifts_or_goods_scoring_sentences.extend(
                _compact_sentences(structured_signals.get("gifts_or_goods_scoring_sentences", []), limit=4)
                if isinstance(structured_signals.get("gifts_or_goods_scoring_sentences", []), list)
                else []
            )
            gifts_or_goods_linked_to_score = gifts_or_goods_linked_to_score or bool(
                structured_signals.get("gifts_or_goods_linked_to_score", False)
            )
            specific_brand_or_supplier_forbidden_in_scoring = specific_brand_or_supplier_forbidden_in_scoring or bool(
                structured_signals.get("specific_brand_or_supplier_forbidden_in_scoring", False)
            )
            matched_specific_rule_sections = structured_signals.get("specific_brand_or_supplier_rule_sections", [])
            if isinstance(matched_specific_rule_sections, list):
                specific_brand_or_supplier_rule_locations.extend(_compact_titles(matched_specific_rule_sections, limit=2))
            specific_brand_or_supplier_rule_sentences.extend(
                _compact_sentences(structured_signals.get("specific_brand_or_supplier_rule_sentences", []), limit=2)
                if isinstance(structured_signals.get("specific_brand_or_supplier_rule_sentences", []), list)
                else []
            )
            matched_specific_sections = structured_signals.get("specific_cert_or_supplier_scoring_sections", [])
            if isinstance(matched_specific_sections, list):
                specific_cert_or_supplier_scoring_locations.extend(_compact_titles(matched_specific_sections, limit=2))
            specific_cert_or_supplier_evidence.extend(
                _compact_sentences(structured_signals.get("specific_cert_or_supplier_evidence", []), limit=4)
                if isinstance(structured_signals.get("specific_cert_or_supplier_evidence", []), list)
                else []
            )
            specific_cert_or_supplier_score_linked = specific_cert_or_supplier_score_linked or bool(
                structured_signals.get("specific_cert_or_supplier_score_linked", False)
            )
        if topic_key == "acceptance":
            acceptance_testing_cost_forbidden_to_bidder = acceptance_testing_cost_forbidden_to_bidder or bool(
                structured_signals.get("acceptance_testing_cost_forbidden_to_bidder", False)
            )
            matched_rule_sections = structured_signals.get("acceptance_testing_cost_rule_sections", [])
            if isinstance(matched_rule_sections, list):
                acceptance_testing_cost_rule_locations.extend(_compact_titles(matched_rule_sections, limit=2))
            acceptance_testing_cost_rule_sentences.extend(
                _compact_sentences(structured_signals.get("acceptance_testing_cost_rule_sentences", []), limit=2)
                if isinstance(structured_signals.get("acceptance_testing_cost_rule_sentences", []), list)
                else []
            )
            matched_cost_sections = structured_signals.get("acceptance_testing_cost_sections", [])
            if isinstance(matched_cost_sections, list):
                acceptance_testing_cost_locations.extend(_compact_titles(matched_cost_sections, limit=2))
            acceptance_testing_cost_evidence.extend(
                _compact_sentences(structured_signals.get("acceptance_testing_cost_evidence", []), limit=4)
                if isinstance(structured_signals.get("acceptance_testing_cost_evidence", []), list)
                else []
            )
            acceptance_testing_cost_shifted_to_bidder = acceptance_testing_cost_shifted_to_bidder or bool(
                structured_signals.get("acceptance_testing_cost_shifted_to_bidder", False)
            )

    import_policy_values = dedupe(import_policy_values)
    reject_phrases = dedupe(reject_phrases)
    accept_phrases = dedupe(accept_phrases)
    if policy_locations_by_topic.get("policy"):
        policy_locations = dedupe(policy_locations_by_topic.get("policy", []))
        policy_sentences = dedupe(policy_sentences_by_topic.get("policy", []))
    else:
        policy_locations = dedupe(
            [item for topic_key in ("qualification", "procedure") for item in policy_locations_by_topic.get(topic_key, [])]
        )
        policy_sentences = dedupe(
            [item for topic_key in ("qualification", "procedure") for item in policy_sentences_by_topic.get(topic_key, [])]
        )
    foreign_refs = dedupe(foreign_refs)
    cn_refs = dedupe(cn_refs)
    technical_locations = dedupe(technical_locations)
    foreign_sentences = dedupe(foreign_sentences)
    cn_sentences = dedupe(cn_sentences)
    star_rule_locations = dedupe(star_rule_locations)
    star_rule_sentences = dedupe(star_rule_sentences)
    acceptance_plan_rule_locations = dedupe(acceptance_plan_rule_locations)
    acceptance_plan_rule_sentences = dedupe(acceptance_plan_rule_sentences)
    acceptance_plan_scoring_locations = dedupe(acceptance_plan_scoring_locations)
    acceptance_plan_scoring_sentences = dedupe(acceptance_plan_scoring_sentences)
    payment_terms_rule_locations = dedupe(payment_terms_rule_locations)
    payment_terms_rule_sentences = dedupe(payment_terms_rule_sentences)
    payment_terms_scoring_locations = dedupe(payment_terms_scoring_locations)
    payment_terms_scoring_sentences = dedupe(payment_terms_scoring_sentences)
    gifts_or_goods_rule_locations = dedupe(gifts_or_goods_rule_locations)
    gifts_or_goods_rule_sentences = dedupe(gifts_or_goods_rule_sentences)
    gifts_or_goods_scoring_locations = dedupe(gifts_or_goods_scoring_locations)
    gifts_or_goods_scoring_sentences = dedupe(gifts_or_goods_scoring_sentences)
    specific_brand_or_supplier_rule_locations = dedupe(specific_brand_or_supplier_rule_locations)
    specific_brand_or_supplier_rule_sentences = dedupe(specific_brand_or_supplier_rule_sentences)
    specific_cert_or_supplier_scoring_locations = dedupe(specific_cert_or_supplier_scoring_locations)
    specific_cert_or_supplier_evidence = dedupe(specific_cert_or_supplier_evidence)
    acceptance_testing_cost_rule_locations = dedupe(acceptance_testing_cost_rule_locations)
    acceptance_testing_cost_rule_sentences = dedupe(acceptance_testing_cost_rule_sentences)
    acceptance_testing_cost_locations = dedupe(acceptance_testing_cost_locations)
    acceptance_testing_cost_evidence = dedupe(acceptance_testing_cost_evidence)
    star_marker_offending_clauses = [
        item
        for item in star_marker_candidate_clauses
        if isinstance(item, dict)
        and not bool(item.get("has_star_marker", False))
        and (
            (bool(item.get("contains_gb_non_t", False)) and star_required_for_gb_non_t)
            or (bool(item.get("contains_mandatory_standard", False)) and star_required_for_mandatory_standard)
        )
    ]
    if "reject_import" in import_policy_values and "accept_import" in import_policy_values:
        import_policy = "mixed_or_unclear"
    elif "reject_import" in import_policy_values:
        import_policy = "reject_import"
    elif "accept_import" in import_policy_values:
        import_policy = "accept_import"
    else:
        import_policy = "mixed_or_unclear"

    triggered_rule_codes: list[str] = []
    if import_policy == "reject_import" and foreign_refs and not has_equivalent_standard_clause:
        cross_risk, cross_topic, cross_source_rule = _build_cross_topic_policy_technical_cluster(
            import_policy=import_policy,
            reject_phrases=reject_phrases,
            foreign_refs=foreign_refs,
            cn_refs=cn_refs,
            has_equivalent_standard_clause=has_equivalent_standard_clause,
            policy_locations=policy_locations,
            technical_locations=technical_locations,
            policy_sentences=policy_sentences,
            foreign_sentences=foreign_sentences,
            cn_sentences=cn_sentences,
        )
        key = _signature_key(cross_risk)
        signatures.append(_risk_to_signature(cross_risk, cross_topic, cross_source_rule))
        grouped.setdefault(key, []).append((cross_risk, cross_topic, cross_source_rule))
        topic_signature_keys.add(key)
        triggered_rule_codes.append("policy_technical_inconsistency")

    if star_marker_offending_clauses:
        cross_risk, cross_topic, cross_source_rule = _build_cross_topic_star_marker_cluster(
            scoring_locations=star_rule_locations,
            scoring_sentences=star_rule_sentences,
            technical_locations=_compact_titles(
                [
                    {
                        "title": str(item.get("title", "")).strip(),
                        "section_id": str(item.get("section_id", "")).strip(),
                    }
                    for item in star_marker_offending_clauses
                ],
                limit=2,
            ),
            offending_clauses=star_marker_offending_clauses,
        )
        key = _signature_key(cross_risk)
        signatures.append(_risk_to_signature(cross_risk, cross_topic, cross_source_rule))
        grouped.setdefault(key, []).append((cross_risk, cross_topic, cross_source_rule))
        topic_signature_keys.add(key)
        triggered_rule_codes.append("star_marker_missing_for_mandatory_standard")

    if acceptance_plan_forbidden_in_scoring and acceptance_plan_linked_to_score:
        cross_risk, cross_topic, cross_source_rule = _build_cross_topic_acceptance_plan_scoring_cluster(
            rule_locations=acceptance_plan_rule_locations,
            rule_sentences=acceptance_plan_rule_sentences,
            scoring_locations=acceptance_plan_scoring_locations,
            scoring_sentences=acceptance_plan_scoring_sentences,
        )
        key = _signature_key(cross_risk)
        signatures.append(_risk_to_signature(cross_risk, cross_topic, cross_source_rule))
        grouped.setdefault(key, []).append((cross_risk, cross_topic, cross_source_rule))
        topic_signature_keys.add(key)
        triggered_rule_codes.append("acceptance_plan_in_scoring_forbidden")

    if payment_terms_forbidden_in_scoring and payment_terms_linked_to_score:
        cross_risk, cross_topic, cross_source_rule = _build_cross_topic_payment_terms_scoring_cluster(
            rule_locations=payment_terms_rule_locations,
            rule_sentences=payment_terms_rule_sentences,
            scoring_locations=payment_terms_scoring_locations,
            scoring_sentences=payment_terms_scoring_sentences,
        )
        key = _signature_key(cross_risk)
        signatures.append(_risk_to_signature(cross_risk, cross_topic, cross_source_rule))
        grouped.setdefault(key, []).append((cross_risk, cross_topic, cross_source_rule))
        topic_signature_keys.add(key)
        triggered_rule_codes.append("payment_terms_in_scoring_forbidden")

    if gifts_or_unrelated_goods_forbidden_in_scoring and gifts_or_goods_linked_to_score:
        cross_risk, cross_topic, cross_source_rule = _build_cross_topic_gifts_or_goods_scoring_cluster(
            rule_locations=gifts_or_goods_rule_locations,
            rule_sentences=gifts_or_goods_rule_sentences,
            scoring_locations=gifts_or_goods_scoring_locations,
            scoring_sentences=gifts_or_goods_scoring_sentences,
        )
        key = _signature_key(cross_risk)
        signatures.append(_risk_to_signature(cross_risk, cross_topic, cross_source_rule))
        grouped.setdefault(key, []).append((cross_risk, cross_topic, cross_source_rule))
        topic_signature_keys.add(key)
        triggered_rule_codes.append("gifts_or_unrelated_goods_in_scoring_forbidden")

    if specific_brand_or_supplier_forbidden_in_scoring and specific_cert_or_supplier_score_linked:
        cross_risk, cross_topic, cross_source_rule = _build_cross_topic_specific_cert_or_supplier_scoring_cluster(
            rule_locations=specific_brand_or_supplier_rule_locations,
            rule_sentences=specific_brand_or_supplier_rule_sentences,
            scoring_locations=specific_cert_or_supplier_scoring_locations,
            scoring_sentences=specific_cert_or_supplier_evidence,
        )
        key = _signature_key(cross_risk)
        signatures.append(_risk_to_signature(cross_risk, cross_topic, cross_source_rule))
        grouped.setdefault(key, []).append((cross_risk, cross_topic, cross_source_rule))
        topic_signature_keys.add(key)
        triggered_rule_codes.append("specific_brand_or_supplier_in_scoring_forbidden")

    if acceptance_testing_cost_forbidden_to_bidder and acceptance_testing_cost_shifted_to_bidder:
        cross_risk, cross_topic, cross_source_rule = _build_acceptance_testing_cost_shift_cluster(
            rule_locations=acceptance_testing_cost_rule_locations,
            rule_sentences=acceptance_testing_cost_rule_sentences,
            demand_locations=acceptance_testing_cost_locations,
            demand_sentences=acceptance_testing_cost_evidence,
        )
        key = _signature_key(cross_risk)
        signatures.append(_risk_to_signature(cross_risk, cross_topic, cross_source_rule))
        grouped.setdefault(key, []).append((cross_risk, cross_topic, cross_source_rule))
        topic_signature_keys.add(key)
        triggered_rule_codes.append("acceptance_testing_cost_shifted_to_bidder")

    clusters = [_build_cluster(f"cluster-{index}", items) for index, items in enumerate(grouped.values(), start=1)]
    clusters = _filter_and_sort_clusters(clusters, triggered_rule_codes)
    clusters, pending_review_items, excluded_risks = _refine_clusters_for_maturity(clusters, topics)
    conflicts = [
        {
            "cluster_id": cluster.cluster_id,
            "title": cluster.title,
            "severity": cluster.severity,
            "topics": cluster.topics,
            "conflict_notes": cluster.conflict_notes,
        }
        for cluster in clusters
        if cluster.conflict_notes
    ]

    missing_topic_coverage: list[str] = []
    manual_review_items: list[str] = []
    coverage_gaps: list[dict[str, object]] = []
    topic_summaries: list[dict[str, object]] = []
    for topic in topics:
        missing_evidence = topic.metadata.get("missing_evidence", []) if topic.metadata else []
        coverage = topic.metadata.get("topic_coverage", {}) if topic.metadata else {}
        selected_sections = topic.metadata.get("selected_sections", []) if topic.metadata else []
        missing_modules = coverage.get("missing_modules", []) if isinstance(coverage, dict) else []
        if topic.need_manual_review:
            manual_review_items.append(f"{topic.topic}: {topic.summary}")
        if missing_evidence:
            missing_topic_coverage.extend([f"{topic.topic}: {item}" for item in missing_evidence if str(item).strip() and str(item).strip() != "未发现"])
            coverage_gaps.append(
                {
                    "topic": topic.topic,
                    "type": "missing_evidence",
                    "items": [str(item) for item in missing_evidence if str(item).strip() and str(item).strip() != "未发现"],
                    "message": f"{topic.topic} 缺少关键证据：{'；'.join([str(item) for item in missing_evidence if str(item).strip() and str(item).strip() != '未发现'])}。",
                }
            )
        if not selected_sections:
            missing_topic_coverage.append(f"{topic.topic}: 未召回到有效证据片段。")
            coverage_gaps.append(
                {
                    "topic": topic.topic,
                    "type": "no_sections",
                    "items": [],
                    "message": f"{topic.topic} 未召回到有效证据片段。",
                }
            )
        if not selected_sections and topic.risk_points:
            manual_review_items.append(f"{topic.topic}: 证据不足但仍输出了结论，需人工复核。")
        if missing_modules:
            coverage_gaps.append(
                {
                    "topic": topic.topic,
                    "type": "missing_modules",
                    "items": list(missing_modules),
                    "message": f"{topic.topic} 缺失模块覆盖：{', '.join(missing_modules)}。",
                }
            )
        if topic.need_manual_review and selected_sections:
            coverage_gaps.append(
                {
                    "topic": topic.topic,
                    "type": "manual_review",
                    "items": list(missing_evidence) if isinstance(missing_evidence, list) else [],
                    "message": f"{topic.topic} 已召回证据但仍需人工复核。",
                }
            )
        topic_summaries.append(
            {
                "topic": topic.topic,
                "risk_count": len(topic.risk_points),
                "need_manual_review": topic.need_manual_review,
                "selected_section_count": len(selected_sections),
                "missing_modules": missing_modules,
            }
        )

    if len(baseline_report.risk_points) == 0 and len(clusters) >= 2:
        manual_review_items.append("基线层未发现风险，但专题层发现多个风险点，建议人工复核专题补充发现。")
        coverage_gaps.append(
            {
                "topic": "cross_check",
                "type": "baseline_topic_gap",
                "items": [],
                "message": "基线层与专题层差异较大，建议人工复核专题新增问题。",
            }
        )

    for risk in baseline_report.risk_points:
        key = _signature_key(risk)
        if key not in topic_signature_keys:
            baseline_only_risks.append(_risk_to_dict(risk, "baseline", "baseline"))

    for topic in topics:
        for risk in topic.risk_points:
            key = _signature_key(risk)
            if key not in baseline_signature_keys:
                topic_only_risks.append(_risk_to_dict(risk, topic.topic, "topic"))

    coverage_summary = {
        "baseline_risk_count": len(baseline_report.risk_points),
        "topic_risk_count": sum(len(topic.risk_points) for topic in topics),
        "cluster_count": len(clusters),
        "topic_count": len(topics),
        "baseline_only_count": len(baseline_only_risks),
        "topic_only_count": len(topic_only_risks),
        "coverage_gap_count": len(coverage_gaps),
        "topic_summaries": topic_summaries,
    }
    comparison_summary = {
        "conflict_count": len(conflicts),
        "manual_review_count": len(dedupe(manual_review_items)),
        "duplicate_reduction": max(len(signatures) - len(clusters), 0),
        "triggered_rule_codes": triggered_rule_codes,
        "pending_review_count": len(pending_review_items),
        "excluded_risk_count": len(excluded_risks),
    }

    return ComparisonArtifact(
        signatures=signatures,
        clusters=clusters,
        conflicts=conflicts,
        coverage_summary=coverage_summary,
        comparison_summary=comparison_summary,
        baseline_only_risks=baseline_only_risks,
        topic_only_risks=topic_only_risks,
        missing_topic_coverage=dedupe(missing_topic_coverage),
        manual_review_items=dedupe(manual_review_items),
        coverage_gaps=coverage_gaps,
        metadata={
            "document_name": document_name,
            "failure_reason_codes": triggered_rule_codes,
            "comparison_failure_reason_codes": triggered_rule_codes,
            "import_policy": import_policy,
            "foreign_standard_refs": foreign_refs,
            "cn_standard_refs": cn_refs,
            "has_equivalent_standard_clause": has_equivalent_standard_clause,
            "acceptance_plan_forbidden_in_scoring": acceptance_plan_forbidden_in_scoring,
            "acceptance_plan_linked_to_score": acceptance_plan_linked_to_score,
            "payment_terms_forbidden_in_scoring": payment_terms_forbidden_in_scoring,
            "payment_terms_linked_to_score": payment_terms_linked_to_score,
            "gifts_or_unrelated_goods_forbidden_in_scoring": gifts_or_unrelated_goods_forbidden_in_scoring,
            "gifts_or_goods_linked_to_score": gifts_or_goods_linked_to_score,
            "specific_brand_or_supplier_forbidden_in_scoring": specific_brand_or_supplier_forbidden_in_scoring,
            "specific_cert_or_supplier_score_linked": specific_cert_or_supplier_score_linked,
            "acceptance_testing_cost_forbidden_to_bidder": acceptance_testing_cost_forbidden_to_bidder,
            "acceptance_testing_cost_shifted_to_bidder": acceptance_testing_cost_shifted_to_bidder,
            "pending_review_items": pending_review_items,
            "excluded_risks": excluded_risks,
        },
    )


def comparison_to_json(artifact: ComparisonArtifact) -> str:
    return json.dumps(artifact.to_dict(), ensure_ascii=False, indent=2)
