from __future__ import annotations

import json
from pathlib import Path

from app.common.file_extract import extract_text
from app.common.markdown_utils import parse_review_markdown
from app.common.schemas import RiskPoint
from app.config import ReviewSettings
from app.pipelines.v2.assembler import assemble_v2_report
from app.pipelines.v2.compare import compare_review_artifacts, comparison_to_json
from app.pipelines.v2.evidence import build_evidence_map
from app.pipelines.v2.schemas import TopicReviewArtifact, V2StageArtifact
from app.pipelines.v2.structure import build_structure_map
from app.pipelines.v2.topic_review import (
    CN_STANDARD_REF_RE,
    FOREIGN_STANDARD_REF_RE,
    GB_NON_T_REF_RE,
    _build_structured_signals,
)
from app.pipelines.v2.topics import get_topic_definition
from app.web.v2_app import build_review_view


REAL_FILE = Path("data/uploads/v2/20260401-124322-9d7d80-SZDL2025000495-A.docx")
W005_SOURCE_RUN = Path("data/results/v2/20260402-100336-szdl2025000495a-mature-review/topic_reviews")
W006_SOURCE_RUN = Path("data/results/v2/20260402-120909-w005f-default-entry-rerun/topic_reviews")


def _build_settings() -> ReviewSettings:
    return ReviewSettings()


def _build_real_file_topics() -> tuple[V2StageArtifact, V2StageArtifact, list[TopicReviewArtifact]]:
    text = extract_text(REAL_FILE)
    structure = build_structure_map(REAL_FILE, text, _build_settings(), use_llm=False)
    evidence = build_evidence_map(REAL_FILE.name, structure, topic_mode="mature")
    topics: list[TopicReviewArtifact] = []
    for topic_key in ("policy", "scoring", "technical_standard", "acceptance"):
        bundle = evidence.metadata["topic_evidence_bundles"][topic_key]
        sections = [section for section in bundle.get("sections", []) if isinstance(section, dict)]
        signal_sections = sections
        if topic_key == "technical_standard":
            primary_ids = {str(item).strip() for item in bundle.get("primary_section_ids", []) if str(item).strip()}
            primary_sections = [
                section
                for section in sections
                if f"{section.get('start_line', 0)}-{section.get('end_line', 0)}" in primary_ids
            ]
            supplemental_sections = []
            for section in sections:
                section_id = f"{section.get('start_line', 0)}-{section.get('end_line', 0)}"
                if section_id in primary_ids:
                    continue
                text_blob = "\n".join(
                    [
                        str(section.get("title", "")).strip(),
                        str(section.get("excerpt", "")).strip(),
                        str(section.get("body", "")).strip(),
                    ]
                )
                if FOREIGN_STANDARD_REF_RE.search(text_blob) or CN_STANDARD_REF_RE.search(text_blob) or GB_NON_T_REF_RE.search(text_blob):
                    supplemental_sections.append(section)
            signal_sections = primary_sections + supplemental_sections[:2]
        structured_signals = _build_structured_signals(type("Definition", (), {"key": topic_key})(), signal_sections)
        topics.append(
            TopicReviewArtifact(
                topic=topic_key,
                summary=f"{topic_key} real-file replay",
                risk_points=[],
                need_manual_review=False,
                coverage_note="真实文件回放测试",
                metadata={
                    "selected_sections": [
                        {
                            "title": section.get("title", ""),
                            "start_line": section.get("start_line"),
                            "end_line": section.get("end_line"),
                            "module": section.get("module", ""),
                        }
                        for section in sections
                    ],
                    "missing_evidence": ["未发现"],
                    "structured_signals": structured_signals,
                },
            )
        )
    baseline = V2StageArtifact(
        name="baseline",
        content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_FILE.name}`\n",
    )
    return structure, evidence, [topic for topic in topics]


def _build_real_file_replay_topics() -> tuple[V2StageArtifact, V2StageArtifact, list[TopicReviewArtifact]]:
    text = extract_text(REAL_FILE)
    structure = build_structure_map(REAL_FILE, text, _build_settings(), use_llm=False)
    evidence = build_evidence_map(REAL_FILE.name, structure, topic_mode="mature")
    source_run = Path("data/results/v2/20260401-173633-92447616/topic_reviews")
    topics: list[TopicReviewArtifact] = []
    for path in sorted(source_run.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        topic_key = payload.get("topic", path.stem)
        definition = get_topic_definition(topic_key)
        bundle = evidence.metadata["topic_evidence_bundles"][topic_key]
        sections = [section for section in bundle.get("sections", []) if isinstance(section, dict)]
        metadata = {
            **dict(payload.get("metadata", {}) or {}),
            "selected_sections": [
                {
                    "title": section.get("title", ""),
                    "start_line": section.get("start_line"),
                    "end_line": section.get("end_line"),
                    "module": section.get("module", ""),
                }
                for section in sections
            ],
            "structured_signals": _build_structured_signals(definition, sections),
            "evidence_bundle": bundle,
            "topic_coverage": evidence.metadata["topic_coverages"][topic_key],
        }
        topics.append(
            TopicReviewArtifact(
                topic=topic_key,
                summary=payload.get("summary", ""),
                risk_points=[RiskPoint(**risk) for risk in payload.get("risk_points", [])],
                need_manual_review=payload.get("need_manual_review", False),
                coverage_note=payload.get("coverage_note", ""),
                metadata=metadata,
            )
        )
    return structure, evidence, topics


def _build_w005_source_topics() -> tuple[V2StageArtifact, V2StageArtifact, list[TopicReviewArtifact]]:
    text = extract_text(REAL_FILE)
    structure = build_structure_map(REAL_FILE, text, _build_settings(), use_llm=False)
    evidence = build_evidence_map(REAL_FILE.name, structure, topic_mode="mature")
    bundles = evidence.metadata["topic_evidence_bundles"]
    coverages = evidence.metadata["topic_coverages"]
    topics: list[TopicReviewArtifact] = []
    evidence_aliases = {
        "qualification": ["qualification"],
        "scoring": ["scoring"],
        "technical": ["technical_standard"],
        "contract": ["contract_payment", "acceptance"],
    }
    for path in sorted(W005_SOURCE_RUN.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        topic_key = payload.get("topic", path.stem)
        bundle_sections: list[dict] = []
        topic_coverage = {}
        for alias_key in evidence_aliases.get(topic_key, [topic_key]):
            bundle = bundles.get(alias_key, {})
            bundle_sections.extend(bundle.get("sections", []))
            if not topic_coverage and alias_key in coverages:
                topic_coverage = coverages.get(alias_key, {})
        selected_sections = [
            {
                "title": section.get("title", ""),
                "start_line": section.get("start_line"),
                "end_line": section.get("end_line"),
                "module": section.get("module", ""),
            }
            for section in bundle_sections
            if isinstance(section, dict)
        ]
        metadata = {
            **dict(payload.get("metadata", {}) or {}),
            "selected_sections": selected_sections,
            "evidence_bundle": {"sections": bundle_sections},
            "topic_coverage": topic_coverage,
        }
        topics.append(
            TopicReviewArtifact(
                topic=topic_key,
                summary=payload.get("summary", ""),
                risk_points=[RiskPoint(**risk) for risk in payload.get("risk_points", [])],
                need_manual_review=payload.get("need_manual_review", False),
                coverage_note=payload.get("coverage_note", ""),
                metadata=metadata,
            )
        )
    for synthetic_topic_key in ("policy",):
        bundle = bundles.get(synthetic_topic_key, {})
        coverage = coverages.get(synthetic_topic_key, {})
        sections = bundle.get("sections", [])
        topics.append(
            TopicReviewArtifact(
                topic=synthetic_topic_key,
                summary=f"{synthetic_topic_key} synthetic replay",
                risk_points=[],
                need_manual_review=False,
                coverage_note="真实文件当前结构召回补充",
                metadata={
                    "selected_sections": [
                        {
                            "title": section.get("title", ""),
                            "start_line": section.get("start_line"),
                            "end_line": section.get("end_line"),
                            "module": section.get("module", ""),
                        }
                        for section in sections
                        if isinstance(section, dict)
                    ],
                    "missing_evidence": ["未发现"],
                    "evidence_bundle": bundle,
                    "topic_coverage": coverage,
                },
            )
        )
    baseline = V2StageArtifact(
        name="baseline",
        content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_FILE.name}`\n",
    )
    return structure, evidence, topics


def _build_w006_source_topics() -> tuple[V2StageArtifact, V2StageArtifact, list[TopicReviewArtifact]]:
    text = extract_text(REAL_FILE)
    structure = build_structure_map(REAL_FILE, text, _build_settings(), use_llm=False)
    evidence = build_evidence_map(REAL_FILE.name, structure, topic_mode="mature")
    topics: list[TopicReviewArtifact] = []
    for path in sorted(W006_SOURCE_RUN.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        topics.append(
            TopicReviewArtifact(
                topic=payload.get("topic", path.stem),
                summary=payload.get("summary", ""),
                risk_points=[RiskPoint(**risk) for risk in payload.get("risk_points", [])],
                need_manual_review=payload.get("need_manual_review", False),
                coverage_note=payload.get("coverage_note", ""),
                metadata=dict(payload.get("metadata", {}) or {}),
            )
        )
    baseline = V2StageArtifact(
        name="baseline",
        content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_FILE.name}`\n",
    )
    return structure, evidence, topics


def test_w002_real_file_compare_matrix_is_complete() -> None:
    structure, evidence, topics = _build_real_file_topics()
    comparison = compare_review_artifacts(REAL_FILE.name, V2StageArtifact(name="baseline", content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_FILE.name}`\n"), topics)
    codes = comparison.metadata["comparison_failure_reason_codes"]
    assert "policy_technical_inconsistency" in codes
    assert "star_marker_missing_for_mandatory_standard" in codes
    assert "acceptance_plan_in_scoring_forbidden" in codes
    assert "specific_brand_or_supplier_in_scoring_forbidden" in codes
    assert "acceptance_testing_cost_shifted_to_bidder" in codes
    assert "payment_terms_in_scoring_forbidden" not in codes
    assert "gifts_or_unrelated_goods_in_scoring_forbidden" not in codes

    scoring_topic = next(topic for topic in topics if topic.topic == "scoring")
    scoring_titles = [section["title"] for section in scoring_topic.metadata["selected_sections"]]
    assert "二、评审标准：" in scoring_titles

    technical_topic = next(topic for topic in topics if topic.topic == "technical_standard")
    technical_sections = [section["title"] for section in technical_topic.metadata["selected_sections"]]
    assert "（5） ▲排量： ≥50L" in technical_sections
    assert technical_topic.metadata["structured_signals"]["contains_gb_non_t"] is True

    titles = [cluster.title for cluster in comparison.clusters]
    assert "非进口项目中出现国外标准/国外部件相关表述，存在采购政策口径、技术标准口径、验收口径不一致风险" in titles
    assert "强制性标准条款未按评审规则标注★，可能导致实质性响应边界不清" in titles
    assert "将项目验收方案纳入评审因素，违反评审规则合规性要求" in titles
    assert "以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险" in titles
    assert "验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险" in titles


def test_w002_real_file_web_titles_follow_comparison_titles() -> None:
    structure, evidence, topics = _build_real_file_topics()
    baseline = V2StageArtifact(name="baseline", content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_FILE.name}`\n")
    comparison = compare_review_artifacts(REAL_FILE.name, baseline, topics)
    report_markdown = assemble_v2_report(REAL_FILE.name, baseline, structure, topics, comparison=comparison)
    comparison_dict = json.loads(comparison_to_json(comparison))
    review_view = build_review_view(parse_review_markdown(report_markdown), comparison_dict)
    card_titles = [card["title"] for card in review_view["all_cards"]]
    assert "将项目验收方案纳入评审因素，违反评审规则合规性要求" in card_titles
    assert "将付款方式纳入评审因素，违反评审规则合规性要求" not in card_titles
    assert "将赠送额外商品作为评分条件，违反评审规则合规性要求" not in card_titles


def test_w004_real_file_refinement_separates_formal_pending_and_excluded() -> None:
    structure, evidence, replay_topics = _build_real_file_replay_topics()
    baseline = V2StageArtifact(name="baseline", content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_FILE.name}`\n")
    comparison = compare_review_artifacts(REAL_FILE.name, baseline, replay_topics)
    formal_titles = [cluster.title for cluster in comparison.clusters]
    pending_titles = [item["title"] for item in comparison.metadata["pending_review_items"]]
    excluded_titles = [item["title"] for item in comparison.metadata["excluded_risks"]]
    assert "非进口项目中出现国外标准/国外部件相关表述，存在采购政策口径、技术标准口径、验收口径不一致风险" in formal_titles
    assert "评分表达采用定性分档或分点+分档组合，但量化标准、计算方式或判定边界说明不清，存在评审口径不一致风险" in formal_titles
    assert "具体资格条件内容缺失，无法判断是否存在排斥性条款" in pending_titles
    assert "废标条件及最终解释权条款证据缺失" in pending_titles
    assert "关键合同条款数值缺失，导致付款与履约责任无法评估" in excluded_titles
    assert "中小企业扶持政策落实条款缺失关键执行参数" in excluded_titles


def test_w005_real_file_full_run_topics_are_refined_to_target_matrix() -> None:
    structure, evidence, replay_topics = _build_w005_source_topics()
    baseline = V2StageArtifact(name="baseline", content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_FILE.name}`\n")
    comparison = compare_review_artifacts(REAL_FILE.name, baseline, replay_topics)

    formal_titles = [cluster.title for cluster in comparison.clusters]
    pending_titles = [item["title"] for item in comparison.metadata["pending_review_items"]]
    excluded_titles = [item["title"] for item in comparison.metadata["excluded_risks"]]

    assert "非进口项目中出现国外标准/国外部件相关表述，存在采购政策口径、技术标准口径、验收口径不一致风险" in formal_titles
    assert "强制性标准条款未按评审规则标注★，可能导致实质性响应边界不清" in formal_titles
    assert "验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险" in formal_titles

    assert "关键商务条款数据缺失，合同无法执行" not in formal_titles
    assert "履约保证金退还期限未定，存在资金占用风险" not in formal_titles
    assert "验收标准模糊，采购人单方裁量权过大" not in formal_titles
    assert "评分标准不明确，存在逻辑矛盾" not in formal_titles
    assert "双电源切换柜尺寸允许偏差过大，可能不符合电气安装规范" not in formal_titles

    assert "关键商务条款数据缺失，合同无法执行" in excluded_titles
    assert "履约保证金退还期限未定，存在资金占用风险" in excluded_titles
    assert "验收标准模糊，采购人单方裁量权过大" in excluded_titles
    assert "双电源切换柜尺寸允许偏差过大，可能不符合电气安装规范" in pending_titles


def test_w006_real_file_output_is_layered_correctly() -> None:
    structure, evidence, replay_topics = _build_w006_source_topics()
    baseline = V2StageArtifact(name="baseline", content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_FILE.name}`\n")
    comparison = compare_review_artifacts(REAL_FILE.name, baseline, replay_topics)

    formal_titles = [cluster.title for cluster in comparison.clusters]
    pending_titles = [item["title"] for item in comparison.metadata["pending_review_items"]]
    excluded_titles = [item["title"] for item in comparison.metadata["excluded_risks"]]

    for title in [
        "付款条款关键数据缺失，无法评估公平性与节点衔接",
        "合同验收时点条款留白，验收流程缺乏明确的可操作性",
        "履约保证金金额及退还期限未明确",
        "验收期限留白，影响付款节点触发",
        "质量保证金及违约责任条款缺失",
        "标准编号与名称引用混乱且缺失版本信息",
        "燃油标准引用可能涉及废止或滞后版本",
        "澄清截止时间未明确填写",
        "采购标的所属行业未明确，影响中小企业声明函填写",
        "人员社保证明要求存在特殊豁免，需防范虚假人员风险",
        "电子投标文件容量限制可能增加投标负担",
    ]:
        assert title not in formal_titles

    for title in [
        "具体资格条款缺失，无法判断是否存在排斥性要求",
        "关键人员配置及业绩要求证据缺失，需人工复核",
        "政策导向章节内容缺失，无法确认节能环保等政策落实情况",
        "缺失检测报告及认证要求的具体规定",
        "三体系认证设置高分值，需评估与项目履约的关联性",
        "业绩评分内容与采购标的履约能力关联度存疑",
    ]:
        assert title in pending_titles

    for title in [
        "付款条款关键数据缺失，无法评估公平性与节点衔接",
        "合同验收时点条款留白，验收流程缺乏明确的可操作性",
        "履约保证金金额及退还期限未明确",
        "验收期限留白，影响付款节点触发",
        "质量保证金及违约责任条款缺失",
        "澄清截止时间未明确填写",
        "采购标的所属行业未明确，影响中小企业声明函填写",
        "人员社保证明要求存在特殊豁免，需防范虚假人员风险",
        "电子投标文件容量限制可能增加投标负担",
    ]:
        assert title in excluded_titles
