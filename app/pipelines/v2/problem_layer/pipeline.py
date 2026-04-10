from __future__ import annotations

from hashlib import md5
from typing import Iterable

from app.pipelines.v2.output_governance.schemas import GovernedResult, GovernedRisk

from .models import Problem, ProblemLayerResult


SEVERITY_RANK = {"高风险": 4, "中高风险": 3, "中风险": 2, "低风险": 1, "需人工复核": 0}
LAYER_PRIORITY = {"formal_risks": 3, "pending_review_items": 2, "excluded_risks": 1}

PROBLEM_GROUP_RULES: dict[str, dict[str, object]] = {
    "certification_scoring_bundle": {
        "families": {"certification_scoring_bundle", "cert_weight"},
        "primary_family": "certification_scoring_bundle",
        "merge_reason": "特定认证证书、特定发证机构与认证权重属于同一评分问题簇，问题层统一保留一个主问题并吸收附属评分说明。",
    },
    "import_consistency": {
        "families": {"import_consistency"},
        "primary_family": "import_consistency",
        "merge_reason": "国外标准/国外部件与采购政策口径冲突属于同一跨专题一致性问题，问题层统一收口为一个主问题。",
    },
    "acceptance_testing_cost": {
        "families": {"acceptance_testing_cost"},
        "canonical_titles": {
            "验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险",
            "将验收产生的检测费用计入投标人承担范围，存在需求条款合规风险",
        },
        "primary_family": "acceptance_testing_cost",
        "merge_reason": "验收检测费用转嫁与费用边界不清属于同一费用风险家族，问题层统一保留 formal 主问题并吸收附属待补证标题。",
    },
}

CROSS_TOPIC_FAMILY_REASONS: dict[str, str] = {
    "import_consistency": "技术标准专题与政策专题同时命中同一进口口径矛盾，问题层按白名单跨专题合并为单一问题。",
    "certification_scoring_bundle": "同一认证评分问题被多个专题从不同侧面命中，问题层按白名单跨专题合并为单一问题。",
}

CONFLICT_RULES: list[dict[str, object]] = [
    {
        "conflict_type": "import_consistency_conflict",
        "title": "非进口项目要求与外标/国外部件引用存在一致性冲突",
        "family_key": "import_consistency",
    },
    {
        "conflict_type": "acceptance_plan_scoring_conflict",
        "title": "评分规则禁止将验收方案作为评审因素，但评分项实际纳入验收方案",
        "family_key": "acceptance_scheme_scoring",
    },
    {
        "conflict_type": "payment_scoring_conflict",
        "title": "评分规则禁止将付款方式作为评审因素，但评分项实际按付款条件加分",
        "family_key": "payment_scoring_conflict",
    },
]


def _stable_problem_id(candidate: GovernedRisk) -> tuple[str, str]:
    rule_ids = [candidate.identity.rule_id]
    evidence_ids = list(candidate.identity.evidence_anchors or candidate.extras.get("evidence_ids", []) or [])
    seed = "|".join(
        [
            candidate.family.family_key,
            candidate.decision.canonical_title,
            ",".join(sorted(rule_ids)),
            ",".join(sorted(str(item) for item in evidence_ids)),
        ]
    )
    digest = md5(seed.encode("utf-8")).hexdigest()[:12]
    return f"problem-{digest}", seed


def _stable_conflict_problem_id(conflict_type: str, left_problem_id: str, right_problem_id: str) -> tuple[str, str]:
    seed = "|".join([conflict_type, *sorted([left_problem_id, right_problem_id])])
    digest = md5(seed.encode("utf-8")).hexdigest()[:12]
    return f"problem-{digest}", seed


def _problem_group_key(candidate: GovernedRisk) -> str:
    family_key = candidate.family.family_key
    title = candidate.decision.canonical_title
    for group_key, rule in PROBLEM_GROUP_RULES.items():
        families = {str(item) for item in rule.get("families", set())}
        canonical_titles = {str(item) for item in rule.get("canonical_titles", set())}
        if family_key in families or title in canonical_titles:
            return group_key
    return family_key


def _merge_reason_for_group(group_key: str) -> str:
    rule = PROBLEM_GROUP_RULES.get(group_key, {})
    return str(rule.get("merge_reason", "问题层已将同簇候选归并为主问题与附属说明。"))


def _unique_strings(values: Iterable[object]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in values if str(item).strip()))


def _candidate_evidence_ids(candidate: GovernedRisk) -> list[str]:
    return _unique_strings(candidate.identity.evidence_anchors or candidate.extras.get("evidence_ids", []) or [])


def _candidate_compare_source_buckets(candidate: GovernedRisk) -> list[str]:
    buckets = candidate.extras.get("compare_source_buckets")
    if isinstance(buckets, list) and buckets:
        return _unique_strings(buckets)
    bucket = str(candidate.extras.get("compare_source_bucket", "formal_risks")).strip()
    return [bucket] if bucket else ["formal_risks"]


def _collect_layer_conflict_inputs(candidates: list[GovernedRisk]) -> list[dict[str, object]]:
    collected: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for candidate in candidates:
        for bucket in _candidate_compare_source_buckets(candidate):
            key = (bucket, candidate.identity.rule_id, candidate.decision.canonical_title)
            if key in seen:
                continue
            seen.add(key)
            collected.append(
                {
                    "source_bucket": bucket,
                    "candidate_rule_id": candidate.identity.rule_id,
                    "candidate_title": candidate.decision.canonical_title,
                    "family_key": candidate.family.family_key,
                    "topic_sources": _unique_strings(candidate.identity.source_topics),
                    "source_locations": list(candidate.source_locations),
                    "source_excerpts": list(candidate.source_excerpts),
                    "evidence_ids": _candidate_evidence_ids(candidate),
                }
            )
    return sorted(collected, key=lambda item: (-LAYER_PRIORITY.get(str(item["source_bucket"]), 0), str(item["candidate_title"])))


def _cross_topic_merge_reason(group_key: str, topic_sources: list[str]) -> str:
    if len(topic_sources) <= 1:
        return ""
    return CROSS_TOPIC_FAMILY_REASONS.get(group_key, "")


def _pick_primary_candidate(group_key: str, candidates: list[GovernedRisk]) -> GovernedRisk:
    rule = PROBLEM_GROUP_RULES.get(group_key, {})
    preferred_family = str(rule.get("primary_family", "")).strip()

    def sort_key(item: GovernedRisk) -> tuple[int, int, int, str]:
        is_preferred = 1 if item.family.family_key == preferred_family else 0
        severity_rank = SEVERITY_RANK.get(item.severity, -1)
        evidence_rank = len(_candidate_evidence_ids(item))
        return (is_preferred, severity_rank, evidence_rank, item.decision.canonical_title)

    return sorted(candidates, key=sort_key, reverse=True)[0]


def _stable_problem_id_for_group(
    group_key: str,
    primary: GovernedRisk,
    candidates: list[GovernedRisk],
) -> tuple[str, str]:
    rule_ids = _unique_strings(item.identity.rule_id for item in candidates)
    evidence_ids = _unique_strings(evidence_id for item in candidates for evidence_id in _candidate_evidence_ids(item))
    family_keys = _unique_strings(item.family.family_key for item in candidates)
    seed = "|".join(
        [
            group_key,
            primary.decision.canonical_title,
            ",".join(sorted(family_keys)),
            ",".join(sorted(rule_ids)),
            ",".join(sorted(evidence_ids)),
        ]
    )
    digest = md5(seed.encode("utf-8")).hexdigest()[:12]
    return f"problem-{digest}", seed


def _problem_trace(
    *,
    seed: str,
    group_key: str,
    source_candidates: list[GovernedRisk],
    evidence_ids: list[str],
    topic_sources: list[str],
    merged_family_keys: list[str],
    problem_merge_reason: str,
    absorbed_supporting_titles: list[str],
    absorbed_supporting_rule_ids: list[str],
    cross_topic_reason: str,
    layer_conflict_inputs: list[dict[str, object]],
    problem_kind: str = "standard",
    conflict_type: str = "",
    left_side: dict[str, object] | None = None,
    right_side: dict[str, object] | None = None,
    conflict_reason: dict[str, object] | None = None,
    conflict_evidence_links: list[dict[str, object]] | None = None,
    replaced_problem_ids: list[str] | None = None,
) -> dict[str, object]:
    return {
        "source_governed_rule_ids": [item.identity.rule_id for item in source_candidates],
        "source_candidate_titles": [item.decision.proposed_title for item in source_candidates],
        "source_evidence_ids": list(evidence_ids),
        "source_topics": list(topic_sources),
        "source_rule_tags": _unique_strings(source_rule for item in source_candidates for source_rule in item.source_rules),
        "problem_group_key": group_key,
        "problem_family_keys": list(merged_family_keys),
        "problem_merge_reason": problem_merge_reason,
        "absorbed_supporting_titles": list(absorbed_supporting_titles),
        "absorbed_supporting_rule_ids": list(absorbed_supporting_rule_ids),
        "absorbed_user_visible_items": [],
        "user_visible_dedupe_reason": "",
        "merged_topic_sources": list(topic_sources),
        "merged_family_keys": list(merged_family_keys),
        "cross_topic_merge_reason": cross_topic_reason,
        "layer_conflict_inputs": list(layer_conflict_inputs),
        "final_problem_resolution": {},
        "problem_kind": problem_kind,
        "conflict_type": conflict_type,
        "left_side": dict(left_side or {}),
        "right_side": dict(right_side or {}),
        "conflict_reason": dict(conflict_reason or {}),
        "conflict_evidence_links": list(conflict_evidence_links or []),
        "replaced_problem_ids": list(replaced_problem_ids or []),
        "problem_id_seed": seed,
    }


def _build_problem(candidate: GovernedRisk) -> Problem:
    problem_id, seed = _stable_problem_id(candidate)
    evidence_ids = _candidate_evidence_ids(candidate)
    topic_sources = _unique_strings(candidate.identity.source_topics)
    rule_ids = [candidate.identity.rule_id]
    merged_family_keys = [candidate.family.family_key]
    layer_conflict_inputs = _collect_layer_conflict_inputs([candidate])
    cross_topic_reason = _cross_topic_merge_reason(candidate.family.family_key, topic_sources)
    trace = _problem_trace(
        seed=seed,
        group_key=candidate.family.family_key,
        source_candidates=[candidate],
        evidence_ids=evidence_ids,
        topic_sources=topic_sources,
        merged_family_keys=merged_family_keys,
        problem_merge_reason="",
        absorbed_supporting_titles=[],
        absorbed_supporting_rule_ids=[],
        cross_topic_reason=cross_topic_reason,
        layer_conflict_inputs=layer_conflict_inputs,
    )
    return Problem(
        problem_id=problem_id,
        canonical_title=candidate.decision.canonical_title,
        family_key=candidate.family.family_key,
        problem_kind="standard",
        primary_candidate=candidate,
        supporting_candidates=[],
        evidence_ids=evidence_ids,
        topic_sources=topic_sources,
        rule_ids=rule_ids,
        merged_topic_sources=list(topic_sources),
        merged_family_keys=list(merged_family_keys),
        cross_topic_merge_reason=cross_topic_reason,
        layer_conflict_inputs=layer_conflict_inputs,
        final_problem_resolution={},
        conflict_type="",
        left_side={},
        right_side={},
        conflict_reason={},
        conflict_evidence_links=[],
        trace=trace,
    )


def _build_problem_from_group(group_key: str, candidates: list[GovernedRisk]) -> Problem:
    if len(candidates) == 1:
        return _build_problem(candidates[0])

    primary = _pick_primary_candidate(group_key, candidates)
    support = [item for item in candidates if item is not primary]
    problem_id, seed = _stable_problem_id_for_group(group_key, primary, candidates)
    evidence_ids = _unique_strings(evidence_id for item in candidates for evidence_id in _candidate_evidence_ids(item))
    topic_sources = _unique_strings(topic for item in candidates for topic in item.identity.source_topics)
    rule_ids = _unique_strings(item.identity.rule_id for item in candidates)
    merged_family_keys = _unique_strings(item.family.family_key for item in candidates)
    layer_conflict_inputs = _collect_layer_conflict_inputs(candidates)
    cross_topic_reason = _cross_topic_merge_reason(group_key, topic_sources)
    supporting_titles = [item.decision.canonical_title for item in support]
    trace = _problem_trace(
        seed=seed,
        group_key=group_key,
        source_candidates=candidates,
        evidence_ids=evidence_ids,
        topic_sources=topic_sources,
        merged_family_keys=merged_family_keys,
        problem_merge_reason=_merge_reason_for_group(group_key),
        absorbed_supporting_titles=supporting_titles,
        absorbed_supporting_rule_ids=[item.identity.rule_id for item in support],
        cross_topic_reason=cross_topic_reason,
        layer_conflict_inputs=layer_conflict_inputs,
    )
    trace["primary_selection_reason"] = "优先保留预设主 family，其次保留风险级别更高、证据锚点更完整的候选作为主问题。"
    if group_key == "acceptance_testing_cost" and support:
        trace["user_visible_dedupe_reason"] = "family_visible_output_absorbed_by_primary"
        trace["absorbed_user_visible_items"] = [
            {
                "title": item.decision.canonical_title,
                "source_bucket": "pending_review_items",
                "absorbed_by": primary.decision.canonical_title,
                "hidden_reason": "same_family_absorbed_by_formal_primary",
            }
            for item in support
        ]
    return Problem(
        problem_id=problem_id,
        canonical_title=primary.decision.canonical_title,
        family_key=group_key,
        problem_kind="standard",
        primary_candidate=primary,
        supporting_candidates=support,
        evidence_ids=evidence_ids,
        topic_sources=topic_sources,
        rule_ids=rule_ids,
        merged_topic_sources=list(topic_sources),
        merged_family_keys=list(merged_family_keys),
        cross_topic_merge_reason=cross_topic_reason,
        layer_conflict_inputs=layer_conflict_inputs,
        final_problem_resolution={},
        conflict_type="",
        left_side={},
        right_side={},
        conflict_reason={},
        conflict_evidence_links=[],
        trace=trace,
    )


def _build_base_problem_layer(governance: GovernedResult) -> list[Problem]:
    grouped: dict[str, list[GovernedRisk]] = {}
    for item in governance.governed_candidates:
        grouped.setdefault(_problem_group_key(item), []).append(item)
    return [_build_problem_from_group(group_key, candidates) for group_key, candidates in grouped.items()]


def _problem_supporting_candidates(problem: Problem) -> list[GovernedRisk]:
    return [problem.primary_candidate, *problem.supporting_candidates]


def _dedupe_governed_candidates(candidates: list[GovernedRisk]) -> list[GovernedRisk]:
    deduped: list[GovernedRisk] = []
    seen: set[tuple[str, str, str]] = set()
    for item in candidates:
        key = (
            item.identity.rule_id,
            item.decision.canonical_title,
            "|".join(item.source_locations),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _problem_sort_key(problem: Problem) -> tuple[int, int, int, str]:
    severity_rank = SEVERITY_RANK.get(problem.primary_candidate.severity, -1)
    evidence_rank = len(problem.evidence_ids)
    return (severity_rank, evidence_rank, len(problem.supporting_candidates), problem.canonical_title)


def _pick_primary_problem(left: Problem, right: Problem) -> Problem:
    return sorted([left, right], key=_problem_sort_key, reverse=True)[0]


def _build_side_payload(problem: Problem, preferred_topic: str) -> dict[str, object]:
    topic = preferred_topic if preferred_topic in problem.merged_topic_sources else (problem.merged_topic_sources[0] if problem.merged_topic_sources else "")
    return {
        "problem_id": problem.problem_id,
        "topic": topic,
        "family_key": problem.family_key,
        "title": problem.canonical_title,
        "source_locations": list(problem.primary_candidate.source_locations),
        "source_excerpts": list(problem.primary_candidate.source_excerpts),
        "evidence_ids": list(problem.evidence_ids),
    }


def _build_conflict_reason(left_side: dict[str, object], right_side: dict[str, object], why_conflict: str) -> dict[str, object]:
    return {
        "left": str(left_side.get("title", "")),
        "right": str(right_side.get("title", "")),
        "why_conflict": why_conflict,
    }


def _build_conflict_evidence_links(left_side: dict[str, object], right_side: dict[str, object]) -> list[dict[str, object]]:
    return [
        {
            "side": "left",
            "problem_id": left_side.get("problem_id", ""),
            "topic": left_side.get("topic", ""),
            "source_locations": list(left_side.get("source_locations", [])),
            "evidence_ids": list(left_side.get("evidence_ids", [])),
        },
        {
            "side": "right",
            "problem_id": right_side.get("problem_id", ""),
            "topic": right_side.get("topic", ""),
            "source_locations": list(right_side.get("source_locations", [])),
            "evidence_ids": list(right_side.get("evidence_ids", [])),
        },
    ]


def _build_conflict_problem(
    *,
    conflict_type: str,
    title: str,
    family_key: str,
    left: Problem,
    right: Problem,
    left_topic: str,
    right_topic: str,
    why_conflict: str,
) -> Problem:
    primary_problem = _pick_primary_problem(left, right)
    secondary_problem = right if primary_problem is left else left
    primary_candidate = primary_problem.primary_candidate
    supporting_candidates = _dedupe_governed_candidates(
        _problem_supporting_candidates(primary_problem) + _problem_supporting_candidates(secondary_problem)
    )
    if primary_candidate in supporting_candidates:
        supporting_candidates.remove(primary_candidate)
    problem_id, seed = _stable_conflict_problem_id(conflict_type, left.problem_id, right.problem_id)
    evidence_ids = _unique_strings([*left.evidence_ids, *right.evidence_ids])
    topic_sources = _unique_strings([*left.merged_topic_sources, *right.merged_topic_sources])
    rule_ids = _unique_strings([*left.rule_ids, *right.rule_ids])
    merged_family_keys = _unique_strings([*left.merged_family_keys, *right.merged_family_keys])
    layer_conflict_inputs = list(left.layer_conflict_inputs) + [
        item for item in right.layer_conflict_inputs if item not in left.layer_conflict_inputs
    ]
    left_side = _build_side_payload(left, left_topic)
    right_side = _build_side_payload(right, right_topic)
    conflict_reason = _build_conflict_reason(left_side, right_side, why_conflict)
    conflict_links = _build_conflict_evidence_links(left_side, right_side)
    trace = _problem_trace(
        seed=seed,
        group_key=conflict_type,
        source_candidates=[primary_candidate, *supporting_candidates],
        evidence_ids=evidence_ids,
        topic_sources=topic_sources,
        merged_family_keys=merged_family_keys,
        problem_merge_reason="问题层已将跨专题一致性冲突收口为单一 conflict problem。",
        absorbed_supporting_titles=[item.decision.canonical_title for item in supporting_candidates],
        absorbed_supporting_rule_ids=[item.identity.rule_id for item in supporting_candidates],
        cross_topic_reason="跨专题一致性冲突已按白名单规则合并为单一 conflict problem。",
        layer_conflict_inputs=layer_conflict_inputs,
        problem_kind="conflict",
        conflict_type=conflict_type,
        left_side=left_side,
        right_side=right_side,
        conflict_reason=conflict_reason,
        conflict_evidence_links=conflict_links,
        replaced_problem_ids=[left.problem_id, right.problem_id],
    )
    return Problem(
        problem_id=problem_id,
        canonical_title=title,
        family_key=family_key,
        problem_kind="conflict",
        primary_candidate=primary_candidate,
        supporting_candidates=supporting_candidates,
        evidence_ids=evidence_ids,
        topic_sources=topic_sources,
        rule_ids=rule_ids,
        merged_topic_sources=topic_sources,
        merged_family_keys=merged_family_keys,
        cross_topic_merge_reason="跨专题一致性冲突已按白名单规则合并为单一 conflict problem。",
        layer_conflict_inputs=layer_conflict_inputs,
        final_problem_resolution={},
        conflict_type=conflict_type,
        left_side=left_side,
        right_side=right_side,
        conflict_reason=conflict_reason,
        conflict_evidence_links=conflict_links,
        trace=trace,
    )


def _match_import_consistency_conflict(problem: Problem) -> Problem | None:
    if problem.family_key != "import_consistency":
        return None
    topics = set(problem.merged_topic_sources)
    if not {"technical_standard", "policy"}.issubset(topics):
        return None
    return _build_conflict_problem(
        conflict_type="import_consistency_conflict",
        title="非进口项目要求与外标/国外部件引用存在一致性冲突",
        family_key="import_consistency",
        left=problem,
        right=problem,
        left_topic="policy",
        right_topic="technical_standard",
        why_conflict="同一采购文件一侧要求非进口/限制进口，另一侧又引用外标或国外部件要求，两边不能同时作为一致的采购口径成立。",
    )


def _find_problem_by_patterns(problems: list[Problem], *, topic: str, title_patterns: tuple[str, ...]) -> Problem | None:
    for problem in problems:
        if topic not in problem.merged_topic_sources:
            continue
        title = problem.canonical_title
        if any(pattern in title for pattern in title_patterns):
            return problem
    return None


def _match_acceptance_plan_scoring_conflict(problems: list[Problem]) -> Problem | None:
    left = _find_problem_by_patterns(
        problems,
        topic="policy",
        title_patterns=("不得将验收方案作为评审因素", "验收方案不得作为评审因素"),
    )
    right = _find_problem_by_patterns(
        problems,
        topic="scoring",
        title_patterns=("验收方案纳入评审因素", "验收方案作为评分依据", "将项目验收方案纳入评审因素"),
    )
    if not left or not right or left.problem_id == right.problem_id:
        return None
    return _build_conflict_problem(
        conflict_type="acceptance_plan_scoring_conflict",
        title="评分规则禁止将验收方案作为评审因素，但评分项实际纳入验收方案",
        family_key="acceptance_scheme_scoring",
        left=left,
        right=right,
        left_topic="policy",
        right_topic="scoring",
        why_conflict="一侧规则明确禁止将验收方案作为评审因素，另一侧评分细则却直接按照验收方案打分，两边不能同时成立。",
    )


def _match_payment_scoring_conflict(problems: list[Problem]) -> Problem | None:
    left = _find_problem_by_patterns(
        problems,
        topic="policy",
        title_patterns=("不得将付款方式作为评审因素", "付款方式不得作为评审因素"),
    )
    right = _find_problem_by_patterns(
        problems,
        topic="scoring",
        title_patterns=("付款周期", "预付款比例", "付款方式"),
    )
    if not left or not right or left.problem_id == right.problem_id:
        return None
    return _build_conflict_problem(
        conflict_type="payment_scoring_conflict",
        title="评分规则禁止将付款方式作为评审因素，但评分项实际按付款条件加分",
        family_key="payment_scoring_conflict",
        left=left,
        right=right,
        left_topic="policy",
        right_topic="scoring",
        why_conflict="一侧规则禁止按付款条件评分，另一侧评分项却按付款周期或预付款比例加分，两边不能同时作为一致评审口径成立。",
    )


def _apply_conflict_rules(problems: list[Problem]) -> tuple[list[Problem], int]:
    conflict_problems: list[Problem] = []
    consumed_ids: set[str] = set()

    for problem in problems:
        conflict = _match_import_consistency_conflict(problem)
        if conflict is not None:
            conflict_problems.append(conflict)
            consumed_ids.add(problem.problem_id)

    acceptance_conflict = _match_acceptance_plan_scoring_conflict([item for item in problems if item.problem_id not in consumed_ids])
    if acceptance_conflict is not None:
        conflict_problems.append(acceptance_conflict)
        consumed_ids.update(acceptance_conflict.trace.get("replaced_problem_ids", []))

    payment_conflict = _match_payment_scoring_conflict([item for item in problems if item.problem_id not in consumed_ids])
    if payment_conflict is not None:
        conflict_problems.append(payment_conflict)
        consumed_ids.update(payment_conflict.trace.get("replaced_problem_ids", []))

    retained = [item for item in problems if item.problem_id not in consumed_ids]
    return [*retained, *conflict_problems], len(conflict_problems)


def build_problem_layer(document_name: str, governance: GovernedResult, *, enable_conflicts: bool = True) -> ProblemLayerResult:
    base_problems = _build_base_problem_layer(governance)
    problems = list(base_problems)
    conflict_problem_count = 0
    if enable_conflicts:
        problems, conflict_problem_count = _apply_conflict_rules(base_problems)
    absorbed_candidate_count = sum(max(len({_problem_group_key(item) for item in [problem.primary_candidate, *problem.supporting_candidates]}) - 1, 0) for problem in base_problems)
    return ProblemLayerResult(
        document_name=document_name,
        input_summary={
            "governed_candidate_count": len(governance.governed_candidates),
            "base_problem_count": len(base_problems),
            "problem_count": len(problems),
            "absorbed_candidate_count": absorbed_candidate_count,
            "cross_topic_problem_count": sum(1 for item in problems if len(item.merged_topic_sources) > 1),
            "layer_conflict_problem_count": sum(1 for item in problems if len(item.layer_conflict_inputs) > 1),
            "conflict_problem_count": conflict_problem_count,
        },
        problems=problems,
    )
