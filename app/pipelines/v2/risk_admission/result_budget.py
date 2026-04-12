from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .domain_policy import DomainResultPolicy
from .schemas import AdmissionCandidate, AdmissionDecision, AdmissionResult
from .user_visible_gate import STABLE_PENDING_FAMILIES


PRIORITY_CONSEQUENCE_MARKERS = ("限制竞争", "排斥", "验收", "样品", "品牌", "费用", "解密", "评分", "履约")


@dataclass
class _BudgetEntry:
    candidate: AdmissionCandidate
    decision: AdmissionDecision
    score: int
    family_bucket: str
    low_value: bool


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern and pattern in text for pattern in patterns)


def _build_family_bucket(candidate: AdmissionCandidate) -> str:
    family = str(candidate.risk_family or "").strip()
    if family:
        return family
    return f"title::{candidate.title}"


def _score_pending_entry(candidate: AdmissionCandidate, decision: AdmissionDecision, policy: DomainResultPolicy) -> _BudgetEntry:
    title = str(candidate.title).strip()
    family_bucket = _build_family_bucket(candidate)
    score = 100
    if family_bucket in STABLE_PENDING_FAMILIES:
        score += 40
    if _matches_any(title, policy.priority_title_patterns):
        score += 35
    if _matches_any(title, PRIORITY_CONSEQUENCE_MARKERS):
        score += 20
    if decision.source_type in {"compare_rule", "candidate_rule", "formal_rule"}:
        score += 15
    if decision.source_type == "completeness_hint":
        score += 10
    if decision.source_type in {"topic_inference", "warning_only"}:
        score -= 5
    if decision.evidence_sufficiency == "sufficient":
        score += 10
    low_value = _matches_any(title, policy.low_value_title_patterns)
    if low_value:
        score -= 60
    return _BudgetEntry(
        candidate=candidate,
        decision=decision,
        score=score,
        family_bucket=family_bucket,
        low_value=low_value,
    )


def _mark_hidden(
    hidden: _BudgetEntry,
    *,
    rule: str,
    reason: str,
    keeper: _BudgetEntry | None = None,
) -> None:
    decision = hidden.decision
    decision.budget_hit = True
    decision.budget_rule = rule
    decision.budget_reason = reason
    decision.target_layer = "excluded_risks"
    decision.gate_passed = False
    decision.gate_reason = reason
    decision.gate_rule = rule
    decision.user_visible_gate_passed = False
    decision.user_visible_gate_reason = reason
    decision.user_visible_gate_rule = rule
    hidden_payload = {
        "rule_id": hidden.candidate.rule_id,
        "title": hidden.candidate.title,
        "family_key": hidden.family_bucket,
        "hidden_reason": rule,
        "budget_reason": reason,
    }
    if keeper is not None:
        hidden_payload["kept_rule_id"] = keeper.candidate.rule_id
        hidden_payload["kept_title"] = keeper.candidate.title
        hidden_payload["kept_family_key"] = keeper.family_bucket
        keeper.decision.absorbed_or_hidden_items.append(dict(hidden_payload))
        decision.absorbed_or_hidden_items = [
            {
                "kept_rule_id": keeper.candidate.rule_id,
                "kept_title": keeper.candidate.title,
                "kept_family_key": keeper.family_bucket,
                "hidden_reason": rule,
                "budget_reason": reason,
            }
        ]
    else:
        decision.absorbed_or_hidden_items = [hidden_payload]


def apply_result_budget(result: AdmissionResult, policy: DomainResultPolicy) -> dict[str, Any]:
    original_pending = list(result.pending_review_items)
    pending_entries = [_score_pending_entry(item, result.decisions[item.rule_id], policy) for item in original_pending]
    visible_entries = list(pending_entries)
    hidden_entries: list[_BudgetEntry] = []

    family_groups: dict[str, list[_BudgetEntry]] = {}
    for entry in visible_entries:
        family_groups.setdefault(entry.family_bucket, []).append(entry)
    for group in family_groups.values():
        if len(group) <= policy.family_repeat_budget:
            continue
        ranked = sorted(group, key=lambda item: (-item.score, item.candidate.title))
        keepers = ranked[: policy.family_repeat_budget]
        hidden = ranked[policy.family_repeat_budget :]
        for item in hidden:
            keeper = keepers[0]
            _mark_hidden(
                item,
                rule="family_repeat_budget",
                reason="同一问题家族在当前场景下已保留主问题，其余附属待补证项下沉为内部 trace。",
                keeper=keeper,
            )
            hidden_entries.append(item)
    visible_entries = [item for item in visible_entries if not item.decision.budget_hit]

    low_value_entries = [item for item in visible_entries if item.low_value]
    if len(visible_entries) > 2 and len(low_value_entries) > policy.low_value_signal_budget:
        ranked_low_value = sorted(low_value_entries, key=lambda item: (-item.score, item.candidate.title))
        for item in ranked_low_value[policy.low_value_signal_budget :]:
            _mark_hidden(
                item,
                rule="low_value_signal_budget",
                reason="当前问题属于低价值弱提示项，在该文档场景下不再进入用户可见结果，仅保留内部 trace。",
            )
            hidden_entries.append(item)
    visible_entries = [item for item in visible_entries if not item.decision.budget_hit]

    if len(visible_entries) > policy.pending_count_budget:
        ranked_visible = sorted(visible_entries, key=lambda item: (-item.score, item.candidate.title))
        keepers = ranked_visible[: policy.pending_count_budget]
        hidden = ranked_visible[policy.pending_count_budget :]
        for item in hidden:
            keeper = keepers[-1] if keepers else None
            _mark_hidden(
                item,
                rule="pending_count_budget",
                reason="当前文档场景下 pending 结果预算已命中，系统优先保留高价值且可解释的问题，其余下沉为内部 trace。",
                keeper=keeper,
            )
            hidden_entries.append(item)
        visible_entries = keepers

    hidden_rule_ids = {item.candidate.rule_id for item in hidden_entries}
    result.pending_review_items = [item.candidate for item in visible_entries]
    existing_excluded = [item for item in result.excluded_risks if item.rule_id not in hidden_rule_ids]
    result.excluded_risks = [*existing_excluded, *(item.candidate for item in hidden_entries)]

    return {
        "policy_id": policy.policy_id,
        "before_counts": {
            "formal_risks": len(result.formal_risks),
            "pending_review_items": len(original_pending),
            "excluded_risks": len(existing_excluded),
        },
        "after_counts": {
            "formal_risks": len(result.formal_risks),
            "pending_review_items": len(result.pending_review_items),
            "excluded_risks": len(result.excluded_risks),
        },
        "hidden_count": len(hidden_entries),
        "hidden_titles": [item.candidate.title for item in hidden_entries],
        "visible_pending_titles": [item.candidate.title for item in visible_entries],
    }
