from __future__ import annotations

import re


FORMAL_EXCEPTION_WHITELIST_RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "protected_formal_titles",
        re.compile(
            r"(商务条款中采购人单方调整权过大且结算方式不明|"
            r"商务条款中采购人单方变更权过大且结算方式不明|"
            r"商务条款赋予采购人单方面变更权且结算方式不明|"
            r"验收标准引用“厂家验收标准”及“样品”，存在模糊表述和单方裁量风险)"
        ),
        "命中 formal 例外白名单，允许保留为正式风险。",
    ),
]


def match_formal_exception_whitelist(*parts: str) -> tuple[str, str] | None:
    source_blob = "\n".join(part for part in parts if part)
    for rule_name, pattern, reason in FORMAL_EXCEPTION_WHITELIST_RULES:
        if pattern.search(source_blob):
            return rule_name, reason
    return None
