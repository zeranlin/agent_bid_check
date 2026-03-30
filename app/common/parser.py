from __future__ import annotations

import re

from .schemas import FIELD_ALIASES, ReviewReport, RiskPoint


RISK_HEADING_RE = re.compile(r"(?m)^##\s+风险点\s*(\d+)\s*[:：]\s*(.+?)\s*$")
ALT_RISK_HEADING_RE = re.compile(r"(?m)^###\s*(\d+)[.、]\s*(.+?)\s*$")
SECTION_HEADING_RE = re.compile(r"(?m)^##\s+(综合判断|主要依据汇总)\s*$")
SUBJECT_RE = re.compile(r"(?m)^审查对象\s*[:：]\s*`?(.+?)`?\s*$")
DESCRIPTION_BLOCK_RE = re.compile(r"(?ms)^说明\s*[:：]\s*(.+?)(?:\n---|\Z)")
FIELD_RE = re.compile(r"^\s*[-*]?\s*\*{0,2}([^:：*]+?)\*{0,2}\s*[:：]\s*(.*)$")
SUMMARY_RE = re.compile(r"^\s*[-*]?\s*(高风险问题|中风险问题|需人工复核事项)\s*[:：]\s*(.*)$")
TABLE_ROW_RE = re.compile(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|$")
TITLE_SEVERITY_RE = re.compile(r"^(.*?)[（(]\s*(高风险|中风险|低风险)\s*[）)]\s*$")
MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+.+$")
SEPARATOR_ONLY_RE = re.compile(r"^[-=*_#\s]{2,}$")
IGNORED_SECTION_TITLES = {
    "审查综述",
    "详细风险点清单",
    "综合整改建议",
    "其他建议",
    "总体差异",
    "风险点清单",
}


def strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[-1].strip().startswith("```"):
        return "\n".join(lines[1:-1]).strip()
    return stripped


def clean_text(text: str) -> str:
    return text.strip().strip("\u3000").strip()


def normalize_field_name(name: str) -> str | None:
    return FIELD_ALIASES.get(clean_text(name).rstrip("：:"))


def parse_bullet_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for raw_line in lines:
        line = clean_text(raw_line)
        if not line:
            continue
        line = re.sub(r"^[-*]\s*", "", line).strip()
        if not line or MARKDOWN_HEADING_RE.match(line) or SEPARATOR_ONLY_RE.match(line):
            continue
        items.append(line)
    return items


def normalize_inline_text(text: str) -> str:
    value = clean_text(text)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = value.replace("&nbsp;", " ")
    value = re.sub(r"\*\*(.+?)\*\*", r"\1", value)
    return value.strip()


def parse_description_lines(text: str) -> list[str]:
    block = DESCRIPTION_BLOCK_RE.search(text)
    if not block:
        return []
    return parse_bullet_items(block.group(1).splitlines())


def parse_subject(text: str) -> str:
    match = SUBJECT_RE.search(text)
    if not match:
        return ""
    return clean_text(match.group(1))


def is_probable_risk_section(title: str, body: str) -> bool:
    normalized_title = clean_text(title)
    normalized_title = TITLE_SEVERITY_RE.sub(r"\1", normalized_title).strip()
    if normalized_title in IGNORED_SECTION_TITLES:
        return False
    if "综述" in normalized_title and "风险点" not in normalized_title:
        return False
    if "建议" in normalized_title and "整改建议" not in normalized_title and "风险点" not in normalized_title:
        return False

    has_structured_field = False
    for raw_line in body.splitlines():
        field_match = FIELD_RE.match(raw_line)
        if field_match:
            field_name = normalize_field_name(field_match.group(1))
            if field_name and field_name != "问题标题":
                has_structured_field = True
                break
        table_match = TABLE_ROW_RE.match(raw_line.strip())
        if table_match:
            field_name = normalize_field_name(normalize_inline_text(table_match.group(1)))
            if field_name and field_name != "问题标题":
                has_structured_field = True
                break
    return has_structured_field


def collect_risk_sections(text: str) -> list[tuple[str, str]]:
    matches = list(RISK_HEADING_RE.finditer(text))
    if not matches:
        matches = list(ALT_RISK_HEADING_RE.finditer(text))
    sections: list[tuple[str, str]] = []
    if not matches:
        return sections
    for index, match in enumerate(matches):
        title = clean_text(match.group(2))
        start = match.end()
        end_candidates = []
        if index + 1 < len(matches):
            end_candidates.append(matches[index + 1].start())
        next_section = SECTION_HEADING_RE.search(text, start)
        if next_section:
            end_candidates.append(next_section.start())
        end = min(end_candidates) if end_candidates else len(text)
        body = text[start:end].strip()
        if is_probable_risk_section(title, body):
            sections.append((title, body))
    return sections


def parse_risk_body(title: str, body: str) -> RiskPoint:
    normalized_title = clean_text(title)
    severity_match = TITLE_SEVERITY_RE.match(normalized_title)
    title_severity = ""
    if severity_match:
        normalized_title = clean_text(severity_match.group(1))
        title_severity = severity_match.group(2)

    risk = RiskPoint(title=normalized_title)
    if title_severity:
        risk.severity = title_severity

    current_field: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal current_field, buffer
        if current_field is None:
            buffer = []
            return
        items = parse_bullet_items(buffer)
        value = "\n".join(line.strip() for line in buffer if line.strip()).strip()
        if current_field == "问题定性":
            risk.severity = value
        elif current_field == "审查类型":
            risk.review_type = value
        elif current_field == "原文位置":
            risk.source_location = value
        elif current_field == "原文摘录":
            risk.source_excerpt = value
        elif current_field == "风险判断":
            risk.risk_judgment = items
        elif current_field == "法律/政策依据":
            risk.legal_basis = items
        elif current_field == "整改建议":
            risk.rectification = items
        buffer = []
        current_field = None

    for raw_line in body.splitlines():
        table_match = TABLE_ROW_RE.match(raw_line.strip())
        if table_match:
            left = normalize_inline_text(table_match.group(1))
            right = normalize_inline_text(table_match.group(2))
            if left in {"项目", ":---"} or right in {"内容", ":---"}:
                continue
            field_name = normalize_field_name(left)
            if field_name and field_name != "问题标题":
                flush()
                current_field = field_name
                buffer = right.splitlines() if right else []
                continue

        match = FIELD_RE.match(raw_line)
        if match:
            field_name = normalize_field_name(match.group(1))
            if field_name and field_name != "问题标题":
                flush()
                current_field = field_name
                inline = normalize_inline_text(match.group(2))
                buffer = [inline] if inline else []
                continue
        if current_field is not None:
            buffer.append(raw_line)
    flush()
    risk.ensure_defaults()
    return risk


def parse_summary_section(text: str) -> tuple[list[str], list[str], list[str]]:
    match = re.search(r"(?ms)^##\s+综合判断\s*$\n(.+?)(?=^##\s+主要依据汇总\s*$|\Z)", text)
    if not match:
        return [], [], []
    current: str | None = None
    mapping = {"高风险问题": [], "中风险问题": [], "需人工复核事项": []}
    for raw_line in match.group(1).splitlines():
        summary_match = SUMMARY_RE.match(raw_line)
        if summary_match:
            current = summary_match.group(1)
            inline = clean_text(summary_match.group(2))
            if inline:
                mapping[current].append(inline)
            continue
        if current:
            mapping[current].extend(parse_bullet_items([raw_line]))
    return mapping["高风险问题"], mapping["中风险问题"], mapping["需人工复核事项"]


def parse_basis_summary(text: str) -> list[str]:
    match = re.search(r"(?ms)^##\s+主要依据汇总\s*$\n(.+?)\Z", text)
    if not match:
        return []
    return parse_bullet_items(match.group(1).splitlines())


def parse_review_markdown(raw_markdown: str) -> ReviewReport:
    text = strip_code_fence(raw_markdown)
    report = ReviewReport()
    report.subject = parse_subject(text)
    report.description_lines = parse_description_lines(text)
    report.risk_points = [parse_risk_body(title, body) for title, body in collect_risk_sections(text)]
    report.summary_high_risk, report.summary_medium_risk, report.summary_manual_review = parse_summary_section(text)
    report.basis_summary = parse_basis_summary(text)
    return report

