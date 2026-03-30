from __future__ import annotations

import re


FIELD_ORDER = [
    "问题定性",
    "审查类型",
    "原文位置",
    "原文摘录",
    "风险判断",
    "法律/政策依据",
    "整改建议",
]
LIST_FIELDS = {"风险判断", "法律/政策依据", "整改建议"}
RISK_HEADING_RE = re.compile(r"(?m)^##\s+风险点(\d+)[:：](.+?)\s*$")


def strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[-1].strip().startswith("```"):
        return "\n".join(lines[1:-1]).strip()
    return stripped


def default_field_value(field: str) -> str | list[str]:
    if field == "法律/政策依据":
        return ["需人工复核"]
    if field in LIST_FIELDS:
        return ["未发现"]
    return "未发现"


def clean_title(title: str) -> str:
    text = title.strip()
    text = re.sub(r"^(问题标题|标题)\s*[:：]\s*", "", text)
    return text or "需人工复核"


def parse_field_line(line: str) -> tuple[str | None, str]:
    match = re.match(r"^\s*[-*]?\s*(问题定性|审查类型|原文位置|原文摘录|风险判断|法律/政策依据|整改建议)\s*[:：]\s*(.*)$", line)
    if not match:
        return None, ""
    return match.group(1), match.group(2)


def parse_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        text = line.rstrip()
        if not text.strip():
            continue
        text = re.sub(r"^\s*[-*]\s*", "", text).strip()
        items.append(text)
    return items


def format_field(field: str, value: str | list[str]) -> list[str]:
    if field in LIST_FIELDS:
        items = value if isinstance(value, list) else [value]
        normalized = [item.strip() for item in items if item and item.strip()]
        if not normalized:
            normalized = list(default_field_value(field))
        lines = [f"- {field}："]
        lines.extend([f"  - {item}" for item in normalized])
        return lines
    text = str(value).strip() or str(default_field_value(field))
    return [f"- {field}：{text}"]


def parse_risk_body(body: str) -> dict[str, str | list[str]]:
    fields: dict[str, str | list[str]] = {}
    current_field: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal current_field, buffer
        if current_field is None:
            buffer = []
            return
        if current_field in LIST_FIELDS:
            fields[current_field] = parse_items(buffer)
        else:
            text = "\n".join(line.strip() for line in buffer if line.strip()).strip()
            fields[current_field] = text
        current_field = None
        buffer = []

    for raw_line in body.splitlines():
        field, inline = parse_field_line(raw_line)
        if field:
            flush()
            current_field = field
            buffer = [inline] if inline else []
            continue
        if current_field is not None:
            buffer.append(raw_line)
    flush()

    for field in FIELD_ORDER:
        value = fields.get(field)
        if field not in fields:
            fields[field] = default_field_value(field)
        elif isinstance(value, list) and not value:
            fields[field] = default_field_value(field)
        elif isinstance(value, str) and not value.strip():
            fields[field] = default_field_value(field)
    return fields


def ensure_summary_section(text: str) -> str:
    if re.search(r"(?m)^##\s+综合判断\s*$", text):
        return text
    extra = [
        "",
        "---",
        "",
        "## 综合判断",
        "",
        "- 高风险问题：",
        "  - 未发现",
        "- 中风险问题：",
        "  - 未发现",
        "- 需人工复核事项：",
        "  - 需人工复核",
    ]
    return text.rstrip() + "\n" + "\n".join(extra) + "\n"


def ensure_basis_section(text: str) -> str:
    if re.search(r"(?m)^##\s+主要依据汇总\s*$", text):
        return text
    extra = ["", "## 主要依据汇总", "", "- 需人工复核"]
    return text.rstrip() + "\n" + "\n".join(extra) + "\n"


def lightly_postprocess_review(raw_markdown: str, source_name: str) -> str:
    text = strip_code_fence(raw_markdown)
    matches = list(RISK_HEADING_RE.finditer(text))
    if not matches:
        return text.strip() + "\n"

    output: list[str] = []

    prefix = text[:matches[0].start()].strip()
    if prefix:
        output.append(prefix)
    else:
        output.extend(
            [
                "# 招标文件合规审查结果",
                "",
                f"审查对象：`{source_name}`",
                "",
                "说明：",
                "- 本审查基于你提供的招标文件文本进行。",
                "- 对于存在事实基础不足、需要采购人补充论证材料才能最终定性的事项，明确标注“需人工复核”。",
                "- 下述“风险判断”系合规审查意见，不等同于行政机关最终认定。",
                "",
                "---",
            ]
        )

    for index, match in enumerate(matches, start=1):
        title = clean_title(match.group(2))
        start = match.end()
        end = matches[index].start() if index < len(matches) else len(text)
        body = text[start:end].strip()
        section_fields = parse_risk_body(body)
        output.extend(["", f"## 风险点{index}：{title}", ""])
        for field in FIELD_ORDER:
            output.extend(format_field(field, section_fields[field]))

    merged = "\n".join(output).strip() + "\n"
    merged = ensure_summary_section(merged)
    merged = ensure_basis_section(merged)
    return merged


__all__ = ["lightly_postprocess_review"]
