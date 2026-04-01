from __future__ import annotations

import hashlib
import json
import re

from app.common.normalize import dedupe
from app.common.parser import parse_review_markdown
from app.common.schemas import RiskPoint

from .schemas import ComparisonArtifact, MergedRiskCluster, RiskSignature, TopicReviewArtifact, V2StageArtifact


SEVERITY_ORDER = {"高风险": 3, "中高风险": 2.5, "中风险": 2, "低风险": 1, "需人工复核": 0}


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
        source_location_parts.append("评审规则：" + "；".join(scoring_locations[:2]))
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
        source_location_parts.append("评审规则：" + "；".join(rule_locations[:2]))
    if scoring_locations:
        source_location_parts.append("评分条款：" + "；".join(scoring_locations[:2]))

    source_excerpt_parts = []
    if rule_sentences:
        source_excerpt_parts.append("规则要求：" + "；".join(rule_sentences[:1]))
    if scoring_sentences:
        source_excerpt_parts.append("评分内容：" + "；".join(scoring_sentences[:3]))

    risk = RiskPoint(
        title="将项目验收方案纳入评审因素，违反评审规则合规性要求",
        severity="中高风险",
        review_type="评分因素合规性 / 评审规则设置合法性",
        source_location="；".join(source_location_parts) if source_location_parts else "未发现",
        source_excerpt="\n\n".join(source_excerpt_parts) if source_excerpt_parts else "未发现",
        risk_judgment=[
            "评审规则已明确不得将项目验收方案作为评审因素。",
            "当前评分内容中纳入了验收移交方案或验收资料移交安排。",
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
        source_location_parts.append("评审规则：" + "；".join(rule_locations[:2]))
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


def compare_review_artifacts(
    document_name: str,
    baseline: V2StageArtifact,
    topics: list[TopicReviewArtifact],
) -> ComparisonArtifact:
    baseline_report = parse_review_markdown(baseline.content)
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
        metadata = topic.metadata if isinstance(topic.metadata, dict) else {}
        structured_signals = metadata.get("structured_signals", {}) if isinstance(metadata.get("structured_signals", {}), dict) else {}
        selected_sections = metadata.get("selected_sections", []) if isinstance(metadata.get("selected_sections", []), list) else []
        section_titles = [str(section.get("title", "")).strip() for section in selected_sections if isinstance(section, dict) and str(section.get("title", "")).strip()]
        if topic.topic in policy_signal_topics:
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
            policy_locations_by_topic[topic.topic] = dedupe(
                policy_locations_by_topic.get(topic.topic, []) + topic_policy_locations
            )
            policy_sentences_by_topic[topic.topic] = dedupe(
                policy_sentences_by_topic.get(topic.topic, []) + topic_policy_sentences
            )
        if topic.topic == "technical_standard":
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
        if topic.topic == "scoring":
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

    clusters = [_build_cluster(f"cluster-{index}", items) for index, items in enumerate(grouped.values(), start=1)]
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
        },
    )


def comparison_to_json(artifact: ComparisonArtifact) -> str:
    return json.dumps(artifact.to_dict(), ensure_ascii=False, indent=2)
