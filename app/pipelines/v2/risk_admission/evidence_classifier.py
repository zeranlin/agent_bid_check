from __future__ import annotations

import re

from .schemas import EvidenceKind


CONTRACT_TEMPLATE_RE = re.compile(
    r"(合同条款及格式|合同范本|协议书格式|本合同|甲方|乙方|待甲方中标|待中标（成交）后|仅供参考|合同文本)"
)
DECLARATION_TEMPLATE_RE = re.compile(r"(声明函|承诺函|说明函|授权书|投标函)")
DECLARATION_GUIDE_RE = re.compile(r"(填写指引|本声明函|下划线处|请依照|内容填写|无需提供|说明：|请仔细填写)")
JOINT_VENTURE_TEMPLATE_RE = re.compile(r"(联合体协议|联合协议|联合体投标协议|联合体各方|联合体成员)")
SUBCONTRACT_TEMPLATE_RE = re.compile(r"(分包意向协议|分包协议|分包合同标的|分包合同|分包内容)")
OPTIONAL_FORM_RE = re.compile(r"(若有|无需提供|可不提供|可以不填写|仅适用于|仅针对|可根据自身情况填写)")
PLACEHOLDER_RE = re.compile(r"(_{3,}|＿{2,}|﹍{2,}|▁{2,}|[【\[]\s*[】\]]|[□■])")


def infer_evidence_kind(
    *,
    review_type: str,
    title: str,
    source_locations: list[str],
    source_excerpts: list[str],
) -> EvidenceKind:
    blob = "\n".join([review_type, title, *source_locations, *source_excerpts])

    if SUBCONTRACT_TEMPLATE_RE.search(blob):
        return "subcontract_template"
    if JOINT_VENTURE_TEMPLATE_RE.search(blob):
        return "joint_venture_template"
    if DECLARATION_TEMPLATE_RE.search(blob) and (DECLARATION_GUIDE_RE.search(blob) or PLACEHOLDER_RE.search(blob)):
        return "declaration_template"
    if CONTRACT_TEMPLATE_RE.search(blob) and (PLACEHOLDER_RE.search(blob) or "合同" in blob or "协议" in blob):
        return "contract_template"
    if OPTIONAL_FORM_RE.search(blob):
        return "optional_form"
    if "评分" in blob:
        return "scoring_clause"
    if "资格" in blob:
        return "qualification_clause"
    if "验收" in blob:
        return "acceptance_clause"
    if "合同模板" in blob:
        return "contract_template"
    return "body_clause"


def infer_evidence_support_signal(section: dict[str, object]) -> dict[str, object]:
    source_kind = str(section.get("source_kind", "")).strip()
    business_domain = str(section.get("business_domain", "")).strip()
    clause_role = str(section.get("clause_role", "")).strip()
    evidence_strength = str(section.get("evidence_strength", "")).strip()
    hard_evidence = bool(section.get("hard_evidence", False))

    evidence_passed = (
        hard_evidence
        and source_kind == "body_clause"
        and clause_role in {"gate", "scoring_factor", "technical_requirement", "acceptance_basis", "commercial_obligation"}
        and business_domain
        in {"qualification", "scoring", "technical", "technical_standard", "acceptance", "commercial", "performance_staff"}
        and evidence_strength == "strong"
    )

    return {
        "admission_evidence_passed": evidence_passed,
        "admission_reason": "hard_evidence_available" if evidence_passed else "hard_evidence_not_satisfied",
        "admission_signals": {
            "source_kind": source_kind,
            "business_domain": business_domain,
            "clause_role": clause_role,
            "evidence_strength": evidence_strength,
            "hard_evidence": hard_evidence,
        },
    }
