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
from app.web.v2_app import build_review_view


REAL_FILE = Path("data/uploads/v2/20260401-124322-9d7d80-SZDL2025000495-A.docx")


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
    assert "技术标准引用与采购政策口径不一致，存在潜在倾向性和理解冲突" in titles
    assert "强制性标准条款未按评审规则标注★，可能导致实质性响应边界不清" in titles
    assert "将项目验收方案纳入评审因素，违反评审规则合规性要求" in titles
    assert "以制造商特定认证证书作为高分条件，存在限定特定供应商和倾向性评分风险" in titles
    assert "将验收产生的检测费用计入投标人承担范围，存在需求条款合规风险" in titles


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
