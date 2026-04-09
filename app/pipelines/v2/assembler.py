from __future__ import annotations

import json
from copy import deepcopy

from app.common.normalize import dedupe, infer_basis_summary
from app.common.parser import parse_review_markdown
from app.common.schemas import ReviewReport, RiskPoint

from .compare import compare_review_artifacts
from .output_governance import govern_comparison_artifact, validate_governed_result
from .output_governance.schemas import GovernedResult
from .risk_admission import admit_governance_result, validate_admitted_result
from .risk_admission.schemas import AdmissionCandidate, AdmissionResult
from .schemas import ComparisonArtifact, MergedRiskCluster, TopicReviewArtifact, V2StageArtifact


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

    pending_review_items = getattr(report, "pending_review_items", [])
    if pending_review_items:
        lines.extend(["---", "", "## 待补证复核项", ""])
        for index, item in enumerate(pending_review_items, start=1):
            lines.extend(
                [
                    f"### 复核项{index}：{item.get('title', '待补证复核项')}",
                    "",
                    f"- 复核类型：{item.get('review_type', '需人工复核')}",
                    f"- 所属专题：{item.get('topic', '未分类')}",
                    f"- 原文位置：{item.get('source_location', '未发现')}",
                    f"- 原文摘录：{item.get('source_excerpt', '未发现')}",
                    f"- 复核原因：{item.get('reason', '当前证据未完整覆盖对应条款，需补充证据后复核。')}",
                    "",
                ]
            )

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


def _cluster_to_risk_point(cluster: MergedRiskCluster) -> RiskPoint:
    judgment = list(cluster.risk_judgment)
    if cluster.conflict_notes:
        judgment.extend(cluster.conflict_notes)
    legal_basis = [item for item in cluster.legal_basis if str(item).strip()]
    if not legal_basis:
        if "compare_rule" in cluster.source_rules and cluster.severity != "需人工复核" and not cluster.need_manual_review:
            legal_basis = ["已结合规则库交叉校验与原文条款综合判断。"]
        else:
            legal_basis = ["需人工复核"]
    risk = RiskPoint(
        title=cluster.title,
        severity=cluster.severity,
        review_type=cluster.review_type,
        source_location="；".join(cluster.source_locations) if cluster.source_locations else "未发现",
        source_excerpt="\n\n".join(cluster.source_excerpts[:2]) if cluster.source_excerpts else "未发现",
        risk_judgment=judgment or ["需人工复核"],
        legal_basis=legal_basis,
        rectification=cluster.rectification or ["未发现"],
    )
    risk.ensure_defaults()
    return risk


def _governed_risk_to_risk_point(governed_risk) -> RiskPoint:
    judgment = list(governed_risk.risk_judgment)
    legal_basis = [item for item in governed_risk.legal_basis if str(item).strip()]
    if not legal_basis:
        if "compare_rule" in governed_risk.source_rules and governed_risk.severity != "需人工复核" and not governed_risk.need_manual_review:
            legal_basis = ["已结合规则库交叉校验与原文条款综合判断。"]
        else:
            legal_basis = ["需人工复核"]
    risk = RiskPoint(
        title=governed_risk.decision.canonical_title,
        severity=governed_risk.severity,
        review_type=governed_risk.review_type,
        source_location="；".join(governed_risk.source_locations) if governed_risk.source_locations else "未发现",
        source_excerpt="\n\n".join(governed_risk.source_excerpts[:2]) if governed_risk.source_excerpts else "未发现",
        risk_judgment=judgment or ["需人工复核"],
        legal_basis=legal_basis,
        rectification=governed_risk.rectification or ["未发现"],
    )
    risk.ensure_defaults()
    return risk


def _admitted_risk_to_risk_point(candidate: AdmissionCandidate, governed_risk=None) -> RiskPoint:
    if governed_risk is None:
        risk = RiskPoint(
            title=candidate.title,
            severity=candidate.severity,
            review_type=candidate.review_type,
            source_location="；".join(candidate.source_locations) if candidate.source_locations else "未发现",
            source_excerpt="\n\n".join(candidate.source_excerpts[:2]) if candidate.source_excerpts else "未发现",
            risk_judgment=["已通过 risk_admission 准入层裁决。"],
            legal_basis=["需结合 risk_admission / output_governance 留痕查看。"],
            rectification=["未发现"],
        )
        risk.ensure_defaults()
        return risk

    risk = _governed_risk_to_risk_point(governed_risk)
    risk.title = candidate.title
    risk.severity = candidate.severity
    risk.review_type = candidate.review_type or risk.review_type
    risk.source_location = "；".join(candidate.source_locations) if candidate.source_locations else risk.source_location
    risk.source_excerpt = "\n\n".join(candidate.source_excerpts[:2]) if candidate.source_excerpts else risk.source_excerpt
    risk.ensure_defaults()
    return risk


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


def _build_report(
    document_name: str,
    baseline: V2StageArtifact,
    structure: V2StageArtifact,
    topics: list[TopicReviewArtifact],
    comparison: ComparisonArtifact,
    governance: GovernedResult | None = None,
    admission: AdmissionResult | None = None,
) -> ReviewReport:
    baseline_report = parse_review_markdown(baseline.content)
    report = ReviewReport()
    report.subject = baseline_report.subject or document_name
    report.description_lines = _build_description_lines(structure, topics)
    governance = governance or govern_comparison_artifact(document_name, comparison)
    admission = admission or admit_governance_result(document_name, comparison, governance)
    governed_by_rule = {item.identity.rule_id: item for item in governance.iter_all()}
    report.risk_points = [
        _admitted_risk_to_risk_point(item, governed_by_rule.get(item.rule_id))
        for item in admission.formal_risks
    ]
    for risk in report.risk_points:
        risk.ensure_defaults()
    report.pending_review_items = [
        {
            "title": item.title,
            "severity": item.severity,
            "review_type": item.review_type,
            "topic": item.extras.get("topic", ""),
            "source_location": "；".join(item.source_locations) if item.source_locations else "未发现",
            "source_excerpt": item.source_excerpts[0] if item.source_excerpts else "未发现",
            "reason": admission.decisions[item.rule_id].admission_reason,
        }
        for item in admission.pending_review_items
    ]
    report.summary_high_risk = dedupe([risk.title for risk in report.risk_points if risk.severity == "高风险"]) or ["未发现"]
    report.summary_medium_risk = dedupe([risk.title for risk in report.risk_points if risk.severity == "中风险"]) or ["未发现"]
    report.summary_manual_review = dedupe(
        [
            str(item.get("title", "")).strip()
            for item in report.pending_review_items
            if isinstance(item, dict)
        ]
    ) or ["未发现"]

    basis_items = list(baseline_report.basis_summary)
    for item in governance.formal_risks:
        basis_items.extend(item.legal_basis)
    report.basis_summary = dedupe(basis_items)
    report.ensure_defaults(document_name)
    infer_basis_summary(report)
    return report


def build_v2_final_output(
    document_name: str,
    baseline: V2StageArtifact,
    structure: V2StageArtifact,
    topics: list[TopicReviewArtifact],
    comparison: ComparisonArtifact | None = None,
    governance: GovernedResult | None = None,
    admission: AdmissionResult | None = None,
) -> dict:
    comparison = comparison or compare_review_artifacts(document_name, baseline, topics)
    governance = governance or govern_comparison_artifact(document_name, comparison)
    admission = admission or admit_governance_result(document_name, comparison, governance)
    validate_governed_result(governance)
    validate_admitted_result(admission)
    report = _build_report(document_name, baseline, structure, topics, comparison, governance=governance, admission=admission)
    return {
        "subject": report.subject,
        "description_lines": list(report.description_lines),
        "formal_risks": [
            {
                "title": risk.title,
                "severity": risk.severity,
                "review_type": risk.review_type,
                "source_location": risk.source_location,
                "source_excerpt": risk.source_excerpt,
                "risk_judgment": list(risk.risk_judgment),
                "legal_basis": list(risk.legal_basis),
                "rectification": list(risk.rectification),
            }
            for risk in report.risk_points
        ],
        "pending_review_items": deepcopy(
            [
                {
                    "title": item.title,
                    "severity": item.severity,
                    "review_type": item.review_type,
                    "topic": item.extras.get("topic", ""),
                    "source_location": "；".join(item.source_locations) if item.source_locations else "未发现",
                    "source_excerpt": item.source_excerpts[0] if item.source_excerpts else "未发现",
                    "reason": admission.decisions[item.rule_id].admission_reason,
                }
                for item in admission.pending_review_items
            ]
        ),
        "excluded_risks": deepcopy(
            [
                {
                    "title": item.title,
                    "severity": item.severity,
                    "review_type": item.review_type,
                    "source_location": "；".join(item.source_locations) if item.source_locations else "未发现",
                    "source_excerpt": item.source_excerpts[0] if item.source_excerpts else "未发现",
                    "reason": admission.decisions[item.rule_id].admission_reason,
                }
                for item in admission.excluded_risks
            ]
        ),
        "summary": {
            "high_risk_titles": list(report.summary_high_risk),
            "medium_risk_titles": list(report.summary_medium_risk),
            "manual_review_titles": list(report.summary_manual_review),
        },
        "basis_summary": list(report.basis_summary),
        "governance": governance.to_dict(),
        "risk_admission": admission.to_dict(),
    }


def assemble_v2_report(
    document_name: str,
    baseline: V2StageArtifact,
    structure: V2StageArtifact,
    topics: list[TopicReviewArtifact],
    comparison: ComparisonArtifact | None = None,
    governance: GovernedResult | None = None,
    admission: AdmissionResult | None = None,
) -> str:
    comparison = comparison or compare_review_artifacts(document_name, baseline, topics)
    report = _build_report(document_name, baseline, structure, topics, comparison, governance=governance, admission=admission)
    return _render_report(report)


def build_v2_overview(structure: V2StageArtifact, topics: list[TopicReviewArtifact]) -> dict:
    return {
        "structure_sections": structure.metadata.get("section_count", 0),
        "evidence_bundles": structure.metadata.get("evidence_bundle_count", 0) if structure.metadata else 0,
        "comparison_available": True,
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
