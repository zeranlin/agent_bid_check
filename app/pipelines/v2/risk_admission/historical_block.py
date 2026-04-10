from __future__ import annotations

import re


HISTORICAL_HARD_BLOCK_RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "historical_pseudo_rule_block",
        re.compile(r"(缺失检测报告及认证资质要求)"),
        "该条属于历史已关停伪规则标题，阻断优先级高于一般 formal 准入逻辑，不得再次进入正式风险。",
    ),
]


def match_historical_hard_block(*parts: str) -> tuple[str, str] | None:
    source_blob = "\n".join(part for part in parts if part)
    for rule_name, pattern, reason in HISTORICAL_HARD_BLOCK_RULES:
        if pattern.search(source_blob):
            return rule_name, reason
    return None
