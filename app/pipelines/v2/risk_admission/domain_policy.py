from __future__ import annotations

from app.governance.ax_governance import BudgetPolicy, DomainResultPolicy, load_ax_governance_index


def get_domain_result_policy(document_domain: str) -> DomainResultPolicy:
    index = load_ax_governance_index()
    return index.domain_policies[document_domain]


def get_budget_policy(policy_id: str) -> BudgetPolicy:
    index = load_ax_governance_index()
    return index.budget_policies[policy_id]
