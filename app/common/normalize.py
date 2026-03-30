from __future__ import annotations

from .parser import parse_review_markdown
from .schemas import ReviewReport


def dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def infer_summary(report: ReviewReport) -> None:
    if not report.summary_high_risk:
        report.summary_high_risk = [risk.title for risk in report.risk_points if risk.severity == "高风险"]
    if not report.summary_medium_risk:
        report.summary_medium_risk = [risk.title for risk in report.risk_points if risk.severity == "中风险"]
    if not report.summary_manual_review:
        report.summary_manual_review = [
            risk.title
            for risk in report.risk_points
            if "人工复核" in risk.severity
            or any("人工复核" in item for item in risk.legal_basis)
            or any("人工复核" in item for item in risk.risk_judgment)
        ]
    report.summary_high_risk = dedupe(report.summary_high_risk) or ["未发现"]
    report.summary_medium_risk = dedupe(report.summary_medium_risk) or ["未发现"]
    report.summary_manual_review = dedupe(report.summary_manual_review) or ["未发现"]


def infer_basis_summary(report: ReviewReport) -> None:
    if report.basis_summary:
        report.basis_summary = dedupe(report.basis_summary)
        return
    items: list[str] = []
    for risk in report.risk_points:
        items.extend(risk.legal_basis)
    report.basis_summary = dedupe(items) or ["需人工复核"]


def render_list_field(label: str, items: list[str]) -> list[str]:
    lines = [f"- {label}："]
    for item in items:
        lines.append(f"  - {item}")
    return lines


def render_scalar_field(label: str, value: str) -> str:
    return f"- {label}：{value}"


def normalize_review_markdown(raw_markdown: str, source_name: str) -> str:
    report = parse_review_markdown(raw_markdown)
    report.ensure_defaults(source_name)
    infer_summary(report)
    infer_basis_summary(report)

    lines = ["# 招标文件合规审查结果", "", f"审查对象：`{report.subject}`", "", "说明："]
    lines.extend([f"- {line}" for line in report.description_lines])
    lines.extend(["", "---", ""])

    for index, risk in enumerate(report.risk_points, start=1):
        lines.extend(
            [
                f"## 风险点{index}：{risk.title}",
                "",
                render_scalar_field("问题定性", risk.severity),
                render_scalar_field("审查类型", risk.review_type),
                render_scalar_field("原文位置", risk.source_location),
                render_scalar_field("原文摘录", risk.source_excerpt),
            ]
        )
        lines.extend(render_list_field("风险判断", risk.risk_judgment))
        lines.extend(render_list_field("法律/政策依据", risk.legal_basis))
        lines.extend(render_list_field("整改建议", risk.rectification))
        lines.append("")

    lines.extend(["---", "", "## 综合判断", ""])
    lines.extend(render_list_field("高风险问题", report.summary_high_risk))
    lines.extend(render_list_field("中风险问题", report.summary_medium_risk))
    lines.extend(render_list_field("需人工复核事项", report.summary_manual_review))
    lines.extend(["", "## 主要依据汇总", ""])
    lines.extend([f"- {item}" for item in report.basis_summary])
    lines.append("")
    return "\n".join(lines)

