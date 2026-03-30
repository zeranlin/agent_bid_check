from __future__ import annotations

import json

from app.common.normalize import dedupe, infer_basis_summary, infer_summary
from app.common.parser import parse_review_markdown
from app.common.schemas import ReviewReport, RiskPoint

from .schemas import TopicReviewArtifact, V2StageArtifact


def _render_report(report: ReviewReport) -> str:
    lines = ["# 招标文件合规审查结果", "", f"审查对象：`{report.subject}`", "", "说明："]
    lines.extend([f"- {line}" for line in report.description_lines])
    lines.extend(["", "---", ""])

    for index, risk in enumerate(report.risk_points, start=1):
        lines.extend(
            [
                f"## 风险点{index}：{risk.title}",
                "",
                f"- 问题定性：{risk.severity}",
                f"- 审查类型：{risk.review_type}",
                f"- 原文位置：{risk.source_location}",
                f"- 原文摘录：{risk.source_excerpt}",
                "- 风险判断：",
            ]
        )
        lines.extend([f"  - {item}" for item in risk.risk_judgment])
        lines.append("- 法律/政策依据：")
        lines.extend([f"  - {item}" for item in risk.legal_basis])
        lines.append("- 整改建议：")
        lines.extend([f"  - {item}" for item in risk.rectification])
        lines.append("")

    lines.extend(["---", "", "## 综合判断", ""])
    lines.append("- 高风险问题：")
    lines.extend([f"  - {item}" for item in report.summary_high_risk])
    lines.append("- 中风险问题：")
    lines.extend([f"  - {item}" for item in report.summary_medium_risk])
    lines.append("- 需人工复核事项：")
    lines.extend([f"  - {item}" for item in report.summary_manual_review])
    lines.extend(["", "## 主要依据汇总", ""])
    lines.extend([f"- {item}" for item in report.basis_summary])
    lines.append("")
    return "\n".join(lines)


def _risk_signature(risk: RiskPoint) -> str:
    excerpt = risk.source_excerpt.strip().replace("`", "").replace(">", "")
    return "|".join(
        [
            risk.title.strip(),
            risk.review_type.strip(),
            risk.source_location.strip(),
            excerpt[:160],
        ]
    )


def _merge_risks(base_risks: list[RiskPoint], topics: list[TopicReviewArtifact]) -> list[RiskPoint]:
    merged: list[RiskPoint] = []
    seen: set[str] = set()

    for risk in base_risks:
        risk.ensure_defaults()
        signature = _risk_signature(risk)
        if signature in seen:
            continue
        seen.add(signature)
        merged.append(risk)

    for topic in topics:
        for risk in topic.risk_points:
            risk.ensure_defaults()
            signature = _risk_signature(risk)
            if signature in seen:
                continue
            seen.add(signature)
            merged.append(risk)
    return merged


def _build_description_lines(structure: V2StageArtifact, topics: list[TopicReviewArtifact]) -> list[str]:
    sections = structure.metadata.get("sections", []) if structure.metadata else []
    manual_topics = [topic.topic for topic in topics if topic.need_manual_review]
    lines = [
        "本审查基于你提供的招标文件文本进行。",
        "本报告结合全文直审、结构增强与专题深审生成。",
        f"结构增强层共识别 {len(sections)} 个候选章节，并按模块进行召回。",
    ]
    if manual_topics:
        lines.append(f"以下专题仍建议人工复核：{', '.join(manual_topics)}。")
    else:
        lines.append("对存在事实基础不足的事项，仍建议结合采购背景继续人工复核。")
    lines.append("下述“风险判断”系合规审查意见，不等同于行政机关最终认定。")
    return lines


def assemble_v2_report(
    document_name: str,
    baseline: V2StageArtifact,
    structure: V2StageArtifact,
    topics: list[TopicReviewArtifact],
) -> str:
    baseline_report = parse_review_markdown(baseline.content)
    report = ReviewReport()
    report.subject = baseline_report.subject or document_name
    report.description_lines = _build_description_lines(structure, topics)
    report.risk_points = _merge_risks(baseline_report.risk_points, topics)
    report.summary_high_risk = dedupe(baseline_report.summary_high_risk)
    report.summary_medium_risk = dedupe(baseline_report.summary_medium_risk)
    report.summary_manual_review = dedupe(
        baseline_report.summary_manual_review + [topic.summary for topic in topics if topic.need_manual_review]
    )

    basis_items = list(baseline_report.basis_summary)
    for topic in topics:
        for risk in topic.risk_points:
            basis_items.extend(risk.legal_basis)
    report.basis_summary = dedupe(basis_items)
    report.ensure_defaults(document_name)
    infer_summary(report)
    infer_basis_summary(report)
    return _render_report(report)


def build_v2_overview(structure: V2StageArtifact, topics: list[TopicReviewArtifact]) -> dict:
    return {
        "structure_sections": structure.metadata.get("section_count", 0),
        "topics": [
            {
                "topic": topic.topic,
                "summary": topic.summary,
                "risk_count": len(topic.risk_points),
                "need_manual_review": topic.need_manual_review,
                "coverage_note": topic.coverage_note,
            }
            for topic in topics
        ],
    }
