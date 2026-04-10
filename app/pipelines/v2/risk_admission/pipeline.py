from __future__ import annotations

from app.pipelines.v2.output_governance import govern_comparison_artifact
from app.pipelines.v2.output_governance.schemas import GovernedResult

from .decision_engine import admit_governed_risk
from .schemas import AdmissionInput, AdmissionResult


def validate_admitted_result(result: AdmissionResult) -> None:
    rule_layers: dict[str, set[str]] = {}
    family_layers: dict[str, set[str]] = {}
    for item in result.formal_risks:
        rule_layers.setdefault(item.rule_id, set()).add("formal_risks")
        family_layers.setdefault(item.risk_family, set()).add("formal_risks")
    for item in result.pending_review_items:
        rule_layers.setdefault(item.rule_id, set()).add("pending_review_items")
        family_layers.setdefault(item.risk_family, set()).add("pending_review_items")
    for item in result.excluded_risks:
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
    )
    result = AdmissionResult(
        document_name=document_name,
        input_summary={"admission_input": admission_input.to_dict()},
    )
    for governed_risk in governance.governed_candidates:
        candidate, decision = admit_governed_risk(governed_risk)
        result.decisions[candidate.rule_id] = decision
        if decision.target_layer == "formal_risks":
            result.formal_risks.append(candidate)
        elif decision.target_layer == "pending_review_items":
            result.pending_review_items.append(candidate)
        else:
            result.excluded_risks.append(candidate)
    validate_admitted_result(result)
    return result
