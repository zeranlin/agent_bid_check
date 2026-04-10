from __future__ import annotations

from .schemas import AdmissionSourceType


def infer_source_type(source_rules: list[str]) -> AdmissionSourceType:
    rules = [str(rule).strip() for rule in source_rules if str(rule).strip()]
    if any(rule.startswith("compare_rule") for rule in rules):
        return "compare_rule"
    if any(rule.startswith("candidate_rule") for rule in rules):
        return "candidate_rule"
    if any(rule.startswith("formal_rule") for rule in rules):
        return "formal_rule"
    if rules and all(rule == "topic" for rule in rules):
        return "topic_inference"
    return "warning_only" if not rules else "completeness_hint"
