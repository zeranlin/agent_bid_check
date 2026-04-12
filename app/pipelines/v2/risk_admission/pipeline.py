from __future__ import annotations

from app.pipelines.v2.output_governance import govern_comparison_artifact
from app.pipelines.v2.output_governance.schemas import GovernedResult
from app.pipelines.v2.problem_layer import build_problem_layer
from app.pipelines.v2.problem_layer.models import ProblemLayerResult

from .decision_engine import admit_governed_risk, admit_problem
from .domain_classifier import classify_document_domain
from .domain_policy import get_domain_result_policy
from .result_budget import apply_result_budget
from .schemas import AdmissionInput, AdmissionResult


def validate_admitted_result(result: AdmissionResult) -> None:
    rule_layers: dict[str, set[str]] = {}
    family_layers: dict[str, set[str]] = {}
    for item in result.formal_risks:
        decision = result.decisions.get(item.rule_id)
        if decision is not None and decision.budget_hit:
            continue
        rule_layers.setdefault(item.rule_id, set()).add("formal_risks")
        family_layers.setdefault(item.risk_family, set()).add("formal_risks")
    for item in result.pending_review_items:
        decision = result.decisions.get(item.rule_id)
        if decision is not None and decision.budget_hit:
            continue
        rule_layers.setdefault(item.rule_id, set()).add("pending_review_items")
        family_layers.setdefault(item.risk_family, set()).add("pending_review_items")
    for item in result.excluded_risks:
        decision = result.decisions.get(item.rule_id)
        if decision is not None and decision.budget_hit:
            continue
        rule_layers.setdefault(item.rule_id, set()).add("excluded_risks")
        family_layers.setdefault(item.risk_family, set()).add("excluded_risks")
    conflicts = {rule_id: sorted(layers) for rule_id, layers in rule_layers.items() if len(layers) > 1}
    if conflicts:
        raise ValueError(f"risk_admission produced duplicate rule outputs across layers: {conflicts}")
    family_conflicts = {family: sorted(layers) for family, layers in family_layers.items() if len(layers) > 1}
    if family_conflicts:
        raise ValueError(f"risk_admission produced duplicate family outputs across layers: {family_conflicts}")


def admit_governance_result(document_name: str, comparison, governance: GovernedResult | None = None) -> AdmissionResult:
    governance = governance or govern_comparison_artifact(document_name, comparison)
    problems = build_problem_layer(document_name, governance)
    return admit_problem_result(document_name, comparison, problems, governance)


def admit_problem_result(
    document_name: str,
    comparison,
    problems: ProblemLayerResult,
    governance: GovernedResult | None = None,
) -> AdmissionResult:
    governance = governance or govern_comparison_artifact(document_name, comparison)
    admission_input = AdmissionInput(
        document_name=document_name,
        comparison_summary={
            "cluster_count": len(comparison.clusters),
            "pending_count": len(comparison.metadata.get("pending_review_items", [])) if isinstance(comparison.metadata, dict) else 0,
            "excluded_count": len(comparison.metadata.get("excluded_risks", [])) if isinstance(comparison.metadata, dict) else 0,
        },
        governance_summary={
            "candidate_count": len(governance.governed_candidates),
        },
        problem_summary={
            "problem_count": len(problems.problems),
        },
    )
    result = AdmissionResult(
        document_name=document_name,
        input_summary={
            "admission_input": admission_input.to_dict(),
            "comparison_summary": dict(admission_input.comparison_summary),
            "governance_summary": dict(admission_input.governance_summary),
            "problem_summary": dict(admission_input.problem_summary),
        },
    )
    for problem in problems.problems:
        candidate, decision = admit_problem(problem)
        result.decisions[candidate.rule_id] = decision
        if decision.target_layer == "formal_risks":
            result.formal_risks.append(candidate)
        elif decision.target_layer == "pending_review_items":
            result.pending_review_items.append(candidate)
        else:
            result.excluded_risks.append(candidate)
    domain_context = classify_document_domain(document_name, comparison, problems)
    domain_policy = get_domain_result_policy(domain_context.document_domain)
    for decision in result.decisions.values():
        decision.document_domain = domain_context.document_domain
        decision.domain_confidence = domain_context.domain_confidence
        decision.domain_evidence = list(domain_context.domain_evidence)
        decision.domain_policy_id = domain_context.domain_policy_id
    result.input_summary["domain_context"] = domain_context.to_dict()
    result.input_summary["domain_policy"] = domain_policy.to_dict()
    result.input_summary["budget_summary"] = apply_result_budget(result, domain_policy)
    validate_admitted_result(result)
    return result
