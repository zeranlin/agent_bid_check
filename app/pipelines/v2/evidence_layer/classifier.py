from __future__ import annotations

import re
from typing import Any

from .schemas import BusinessDomain, ClauseRole, EvidenceStrength, SourceKind


MODULE_TO_DOMAIN: dict[str, BusinessDomain] = {
    "qualification": "qualification",
    "scoring": "scoring",
    "technical": "technical",
    "contract": "commercial",
    "acceptance": "acceptance",
    "procedure": "procedure",
    "policy": "policy",
}

MODULE_TO_ROLE: dict[str, ClauseRole] = {
    "qualification": "gate",
    "scoring": "scoring_factor",
    "technical": "technical_requirement",
    "contract": "commercial_obligation",
    "acceptance": "acceptance_basis",
    "procedure": "reminder",
    "policy": "reminder",
}

PLACEHOLDER_RE = re.compile(
    r"(_{3,}|＿{2,}|﹍{2,}|▁{2,}|___+|【\s*专用条款\s*】|【\s*】|\[\s*\]|（填写[^）]{0,30}）|\(填写[^)]{0,30}\)|"
    r"(签署日期|日期|项目编号|合同金额)[:：]\s*[　 ]{2,})"
)
CONTRACT_TEMPLATE_RE = re.compile(r"(合同条款及格式|合同范本|协议书格式|政府采购合同专用条款|政府采购合同通用条款|本合同|甲方|乙方)")
CONTRACT_TEMPLATE_TITLE_RE = re.compile(r"(合同|协议书|合同履行|政府采购合同|交货和验收)")
ATTACHMENT_RE = re.compile(r"(承诺函|声明函|授权书|资格承诺函|附件|附表|证明材料)")
FORM_RE = re.compile(r"(报价表|响应表|一览表|明细表|统计表|信息表|清单|登记表)")
FORM_BODY_RE = re.compile(r"(序号.{0,12}(货物名称|项目名称|品牌|型号|单价|合价|数量|单位))")
SAMPLE_RE = re.compile(r"(样品|打样|样办)")
TEMPLATE_RE = re.compile(r"(格式自拟|格式文件|格式要求|填写说明|按格式|格式见附件|示范文本|模板)")
REMINDER_CONTEXT_RE = re.compile(r"(澄清和修改|注意事项|特别提示|提醒|补充通知|浏览公告网站|以公告为准|详见公告)")
REMINDER_ACTION_RE = re.compile(r"(需进一步核实|需确认|建议评估|请关注|有义务|及时关注|自行留意|另行通知)")
QUALIFICATION_RE = re.compile(r"(资格条件|资格要求|资格审查|申请人的资格要求|合格供应商|具备.*资格|投标人资格)")
SCORING_RE = re.compile(r"(评分标准|评分内容|评分因素|评审标准|评审依据|得\d+\s*分|最高得\d+\s*分|综合评分)")
STANDARD_REF_RE = re.compile(
    r"\b(?:GB/T|GB|IEC|ISO|EN|ASTM|UL|BS|CISPR|DIN|ANSI|JIS|DL/T|JB/T|SJ/T)\s*[A-Z0-9.-]*\d+(?:[./-]\d+)*(?::\d{4}|\-\d{4})?",
    re.IGNORECASE,
)
STANDARD_TEXT_RE = re.compile(r"(符合.{0,24}(标准|规范)|执行.{0,24}(标准|规范)|依据.{0,24}(标准|规范)|国家标准|行业标准|技术标准)")
TECHNICAL_RE = re.compile(r"(技术参数|技术要求|技术指标|规格|性能|材质|尺寸|功率|容量|频率|噪声|配置)")
COMMERCIAL_RE = re.compile(r"(付款方式|支付方式|结算方式|合同价款|违约责任|交货期|交货地点|履约保证金|付款|支付)")
ACCEPTANCE_RE = re.compile(r"(验收|验收标准|验收要求|验收方式|履约验收|验收申请|到货验收|组织验收)")
POLICY_RE = re.compile(r"(政府采购政策|价格扣除|中小企业|节能产品|环境标志产品|进口产品|扶持政策)")
PROCEDURE_RE = re.compile(r"(投标文件的澄清和修改|开标|评标|电子投标文件|投标截止|公告|通知|流程|程序)")
PERFORMANCE_STAFF_RE = re.compile(r"(项目负责人|项目经理|技术负责人|团队成员|人员配置|社保|职称|从业人员|岗位证书|人员证书)")
GATE_ACTION_RE = re.compile(r"(应|须|必须|具备|不得投标|资格审查不通过|投标无效|不得参与投标)")
SCORING_ACTION_RE = re.compile(r"(得\d+\s*分|最高得\d+\s*分|满分\d+\s*分|不得分|加\d+\s*分)")
SUPPORTING_MATERIAL_RE = re.compile(r"(提供.*(扫描件|复印件|证明材料|承诺函|声明函|证书|营业执照)|上传.*附件|作为证明材料|提交.*材料)")
REMINDER_ROLE_RE = re.compile(r"(需进一步核实|需确认|建议评估|请关注|以公告为准|另行通知)")
TECHNICAL_REQUIREMENT_RE = re.compile(r"(不小于|不少于|应符合|符合.*标准|必须满足|参数要求|技术要求)")
ACCEPTANCE_BASIS_RE = re.compile(r"(按.*验收|组织验收|验收标准|验收要求|验收合格|检测结果)")
COMMERCIAL_OBLIGATION_RE = re.compile(r"(支付|付款|结算|交货|履约保证金|违约责任|承担.*费用)")
HARD_CONSTRAINT_RE = re.compile(r"(应|须|必须|不得|不得分|投标无效|资格审查不通过|按无效投标处理|最高得\d+\s*分|得\d+\s*分)")


def _section_blob(section: dict[str, object]) -> str:
    return "\n".join(
        [
            str(section.get("title", "")).strip(),
            str(section.get("excerpt", "")).strip(),
            str(section.get("body", "")).strip(),
            str(section.get("location", "")).strip(),
            str(section.get("source", "")).strip(),
        ]
    )


def classify_source_kind(section: dict[str, object]) -> dict[str, Any]:
    title = str(section.get("title", "")).strip()
    excerpt = str(section.get("excerpt", "")).strip()
    body = str(section.get("body", "")).strip()
    blob = _section_blob(section)

    if CONTRACT_TEMPLATE_RE.search(blob) and (
        CONTRACT_TEMPLATE_TITLE_RE.search(title) or "甲方" in excerpt[:80] or "乙方" in excerpt[:80] or "专用条款" in excerpt[:120]
    ):
        return {
            "source_kind": "contract_template",
            "rule": "contract_template_pattern",
            "reason": "命中合同范本/专用条款/甲乙双方等合同格式信号。",
            "signals": [item for item in [title[:40], "专用条款" if "专用条款" in blob else "", "甲乙双方" if "甲乙双方" in blob else ""] if item],
        }

    if SAMPLE_RE.search(blob):
        return {
            "source_kind": "sample_clause",
            "rule": "sample_clause_pattern",
            "reason": "命中样品或打样相关条款信号。",
            "signals": [item for item in [title[:40], "样品"] if item],
        }

    if ATTACHMENT_RE.search(title) or ("附件" in title and ATTACHMENT_RE.search(blob)):
        return {
            "source_kind": "attachment_clause",
            "rule": "attachment_pattern",
            "reason": "命中声明函/承诺函/授权书/附件等附件材料信号。",
            "signals": [item for item in [title[:40], "附件" if "附件" in title else ""] if item],
        }

    if FORM_RE.search(title) or FORM_BODY_RE.search(excerpt) or FORM_BODY_RE.search(body):
        return {
            "source_kind": "form_clause",
            "rule": "form_pattern",
            "reason": "命中报价表/响应表/一览表等表单标题或列头结构。",
            "signals": [item for item in [title[:40], "列头结构" if FORM_BODY_RE.search(excerpt) or FORM_BODY_RE.search(body) else ""] if item],
        }

    if REMINDER_CONTEXT_RE.search(blob) and REMINDER_ACTION_RE.search(blob):
        return {
            "source_kind": "reminder_clause",
            "rule": "reminder_context_pattern",
            "reason": "同时命中提醒场景和待确认/关注类动作表达。",
            "signals": [item for item in [title[:40], "上下文提醒", "动作提示"] if item],
        }

    if PLACEHOLDER_RE.search(blob):
        return {
            "source_kind": "placeholder_clause",
            "rule": "placeholder_pattern",
            "reason": "命中下划线留白、空白占位或待填写占位表达。",
            "signals": [signal for signal in ["下划线占位", "空白占位", "待填写占位"] if signal],
        }

    if TEMPLATE_RE.search(blob) or ("格式" in title and "合同" not in title):
        return {
            "source_kind": "template_clause",
            "rule": "template_pattern",
            "reason": "命中格式自拟、格式文件或一般模板说明。",
            "signals": [item for item in [title[:40], "格式信号"] if item],
        }

    if str(section.get("source", "")).strip():
        return {
            "source_kind": "body_clause",
            "rule": "default_body_clause",
            "reason": "未命中特殊来源规则，按正文条款处理。",
            "signals": [item for item in [title[:40], str(section.get("source", "")).strip()] if item],
        }

    return {
        "source_kind": "unknown",
        "rule": "unknown_fallback",
        "reason": "缺少稳定来源信号，暂落 unknown。",
        "signals": [title[:40]] if title else [],
    }


def infer_source_kind(section: dict[str, object]) -> SourceKind:
    return classify_source_kind(section)["source_kind"]


def classify_business_domain(section: dict[str, object]) -> dict[str, Any]:
    title = str(section.get("title", "")).strip()
    excerpt = str(section.get("excerpt", "")).strip()
    body = str(section.get("body", "")).strip()
    module = str(section.get("module", "")).strip()
    source_kind = infer_source_kind(section)
    blob = _section_blob(section)

    if source_kind == "sample_clause" and not ACCEPTANCE_RE.search(title):
        return {
            "business_domain": "sample",
            "rule": "sample_clause_priority",
            "reason": "来源已判为样品条款，且标题未落入验收场景。",
            "signals": [item for item in [title[:40], source_kind] if item],
        }

    if ACCEPTANCE_RE.search(title):
        return {
            "business_domain": "acceptance",
            "rule": "acceptance_title_priority",
            "reason": "标题直接命中验收语境，优先归入验收条款。",
            "signals": [item for item in [title[:40], "验收标题"] if item],
        }

    if PERFORMANCE_STAFF_RE.search(blob):
        return {
            "business_domain": "performance_staff",
            "rule": "performance_staff_pattern",
            "reason": "命中项目负责人、人员配置、社保、职称或业绩等履约人员/业绩信号。",
            "signals": [item for item in [title[:40], "人员业绩信号"] if item],
        }

    if QUALIFICATION_RE.search(blob) and not SCORING_RE.search(blob):
        return {
            "business_domain": "qualification",
            "rule": "qualification_pattern",
            "reason": "命中资格条件/资格审查等门槛表达，且未落入评分语境。",
            "signals": [item for item in [title[:40], "资格门槛"] if item],
        }

    if SCORING_RE.search(blob):
        return {
            "business_domain": "scoring",
            "rule": "scoring_pattern",
            "reason": "命中评分标准、分值或评审依据表达。",
            "signals": [item for item in [title[:40], "评分语境"] if item],
        }

    if ACCEPTANCE_RE.search(title) or (ACCEPTANCE_RE.search(blob) and not COMMERCIAL_RE.search(title)):
        return {
            "business_domain": "acceptance",
            "rule": "acceptance_pattern",
            "reason": "命中验收标准、验收时间或组织验收表达。",
            "signals": [item for item in [title[:40], "验收语境"] if item],
        }

    if source_kind == "sample_clause" or SAMPLE_RE.search(title):
        return {
            "business_domain": "sample",
            "rule": "sample_pattern",
            "reason": "命中样品标题或样品来源条款。",
            "signals": [item for item in [title[:40], "样品语境"] if item],
        }

    if COMMERCIAL_RE.search(blob):
        return {
            "business_domain": "commercial",
            "rule": "commercial_pattern",
            "reason": "命中付款、结算、履约保证金或交货等商务义务表达。",
            "signals": [item for item in [title[:40], "商务语境"] if item],
        }

    if STANDARD_REF_RE.search(blob) or (STANDARD_TEXT_RE.search(blob) and TECHNICAL_RE.search(blob)):
        return {
            "business_domain": "technical_standard",
            "rule": "technical_standard_pattern",
            "reason": "命中标准编号或技术标准引用表达。",
            "signals": [item for item in [title[:40], "标准引用"] if item],
        }

    if TECHNICAL_RE.search(blob):
        return {
            "business_domain": "technical",
            "rule": "technical_pattern",
            "reason": "命中技术参数、规格或性能表达。",
            "signals": [item for item in [title[:40], "技术参数"] if item],
        }

    if POLICY_RE.search(blob):
        return {
            "business_domain": "policy",
            "rule": "policy_pattern",
            "reason": "命中政府采购政策、价格扣除或节能环保政策表达。",
            "signals": [item for item in [title[:40], "政策语境"] if item],
        }

    if PROCEDURE_RE.search(blob) or module == "procedure":
        return {
            "business_domain": "procedure",
            "rule": "procedure_pattern",
            "reason": "命中流程、公告、澄清修改或电子投标程序表达。",
            "signals": [item for item in [title[:40], module] if item],
        }

    return {
        "business_domain": MODULE_TO_DOMAIN.get(module, "unknown"),
        "rule": "module_fallback",
        "reason": "未命中更强业务边界规则，按模块映射兜底。",
        "signals": [item for item in [title[:40], module] if item],
    }


def infer_business_domain(section: dict[str, object]) -> BusinessDomain:
    return classify_business_domain(section)["business_domain"]


def classify_clause_role(section: dict[str, object]) -> dict[str, Any]:
    title = str(section.get("title", "")).strip()
    module = str(section.get("module", "")).strip()
    blob = _section_blob(section)
    source_kind = infer_source_kind(section)
    business_domain = infer_business_domain(section)

    if business_domain == "acceptance" and ACCEPTANCE_BASIS_RE.search(blob):
        return {
            "clause_role": "acceptance_basis",
            "rule": "acceptance_basis_pattern",
            "reason": "命中验收标准、检测或组织验收表达。",
            "signals": [item for item in [title[:40], "验收依据"] if item],
        }

    if business_domain == "qualification" and ("资格要求" in title or "资格条件" in title or "资格审查" in title) and GATE_ACTION_RE.search(blob):
        return {
            "clause_role": "gate",
            "rule": "qualification_title_gate_pattern",
            "reason": "标题直接命中资格门槛语境，优先按准入门槛处理。",
            "signals": [item for item in [title[:40], "资格标题"] if item],
        }

    if "证明材料" in title or "承诺函" in title or "声明函" in title or SUPPORTING_MATERIAL_RE.search(blob) or source_kind in {
        "attachment_clause",
        "form_clause",
        "sample_clause",
    }:
        return {
            "clause_role": "supporting_material",
            "rule": "supporting_material_pattern",
            "reason": "命中证明材料、附件、表单或样品提交类表达。",
            "signals": [item for item in [title[:40], source_kind, "证明材料"] if item],
        }

    if business_domain == "qualification" and GATE_ACTION_RE.search(blob):
        return {
            "clause_role": "gate",
            "rule": "gate_pattern",
            "reason": "业务域为资格条件，且命中准入门槛动作表达。",
            "signals": [item for item in [title[:40], "资格门槛"] if item],
        }

    if business_domain in {"scoring", "performance_staff"} and SCORING_ACTION_RE.search(blob):
        return {
            "clause_role": "scoring_factor",
            "rule": "scoring_factor_pattern",
            "reason": "命中评分分值、加分或不得分表达。",
            "signals": [item for item in [title[:40], "评分动作"] if item],
        }

    if business_domain in {"technical", "technical_standard"} and TECHNICAL_REQUIREMENT_RE.search(blob):
        return {
            "clause_role": "technical_requirement",
            "rule": "technical_requirement_pattern",
            "reason": "命中技术参数、标准符合或强制满足表达。",
            "signals": [item for item in [title[:40], "技术要求"] if item],
        }

    if business_domain == "commercial" and COMMERCIAL_OBLIGATION_RE.search(blob):
        return {
            "clause_role": "commercial_obligation",
            "rule": "commercial_obligation_pattern",
            "reason": "命中付款、结算、交货或履约保证金义务表达。",
            "signals": [item for item in [title[:40], "商务义务"] if item],
        }

    if source_kind in {"reminder_clause", "template_clause", "placeholder_clause", "contract_template"} or REMINDER_ROLE_RE.search(blob):
        return {
            "clause_role": "reminder",
            "rule": "reminder_role_pattern",
            "reason": "命中提醒、模板、留白或待核实表达。",
            "signals": [item for item in [title[:40], source_kind] if item],
        }

    return {
        "clause_role": MODULE_TO_ROLE.get(module, "unknown"),
        "rule": "module_role_fallback",
        "reason": "未命中更强角色规则，按模块角色兜底。",
        "signals": [item for item in [title[:40], module] if item],
    }


def infer_clause_role(section: dict[str, object]) -> ClauseRole:
    return classify_clause_role(section)["clause_role"]


def classify_evidence_strength(section: dict[str, object]) -> dict[str, Any]:
    title = str(section.get("title", "")).strip()
    excerpt = str(section.get("excerpt", "")).strip()
    body = str(section.get("body", "")).strip()
    blob = _section_blob(section)
    source_kind = infer_source_kind(section)
    clause_role = infer_clause_role(section)
    business_domain = infer_business_domain(section)
    text_len = max(len(excerpt), len(body))

    if source_kind in {"template_clause", "placeholder_clause", "contract_template", "reminder_clause"} or clause_role == "reminder":
        return {
            "evidence_strength": "weak",
            "rule": "template_or_reminder_weak",
            "reason": "模板、留白、提醒类证据默认视为弱证据。",
            "signals": [item for item in [title[:40], source_kind, clause_role] if item],
        }

    if clause_role == "supporting_material":
        return {
            "evidence_strength": "medium",
            "rule": "supporting_material_medium",
            "reason": "证明材料要求可支撑上下文，但通常不是直接硬约束本体。",
            "signals": [item for item in [title[:40], clause_role] if item],
        }

    if clause_role in {"gate", "scoring_factor", "technical_requirement", "acceptance_basis", "commercial_obligation"} and HARD_CONSTRAINT_RE.search(blob):
        return {
            "evidence_strength": "strong",
            "rule": "explicit_constraint_strong",
            "reason": "命中正文硬条款角色且存在明确约束动作表达。",
            "signals": [item for item in [title[:40], clause_role, "明确约束"] if item],
        }

    if text_len >= 60 or business_domain in {"technical_standard", "acceptance", "commercial"}:
        return {
            "evidence_strength": "medium",
            "rule": "contextual_medium",
            "reason": "具备一定上下文和业务约束，但未达到强证据门槛。",
            "signals": [item for item in [title[:40], business_domain] if item],
        }

    return {
        "evidence_strength": "weak",
        "rule": "default_weak",
        "reason": "上下文和约束动作不足，按弱证据处理。",
        "signals": [item for item in [title[:40], business_domain] if item],
    }


def infer_evidence_strength(section: dict[str, object]) -> EvidenceStrength:
    return classify_evidence_strength(section)["evidence_strength"]


def classify_hard_evidence(section: dict[str, object]) -> dict[str, Any]:
    title = str(section.get("title", "")).strip()
    source_kind = infer_source_kind(section)
    business_domain = infer_business_domain(section)
    clause_role = infer_clause_role(section)
    evidence_strength = infer_evidence_strength(section)

    if source_kind not in {"body_clause"}:
        return {
            "hard_evidence": False,
            "rule": "non_body_not_hard",
            "reason": "非正文来源默认不作为正式硬证据。",
            "signals": [item for item in [title[:40], source_kind] if item],
        }

    if clause_role in {"supporting_material", "reminder"}:
        return {
            "hard_evidence": False,
            "rule": "supporting_or_reminder_not_hard",
            "reason": "证明材料或提醒项默认不直接支撑 formal。",
            "signals": [item for item in [title[:40], clause_role] if item],
        }

    if evidence_strength != "strong":
        return {
            "hard_evidence": False,
            "rule": "strength_gate_not_passed",
            "reason": "未达到强证据门槛，保守不放入硬证据。",
            "signals": [item for item in [title[:40], evidence_strength] if item],
        }

    if business_domain in {"qualification", "scoring", "technical", "technical_standard", "acceptance", "commercial", "performance_staff"} and clause_role in {
        "gate",
        "scoring_factor",
        "technical_requirement",
        "acceptance_basis",
        "commercial_obligation",
    }:
        return {
            "hard_evidence": True,
            "rule": "joint_signal_hard_evidence",
            "reason": "正文来源、硬角色、强证据联合满足，允许作为正式硬证据。",
            "signals": [item for item in [title[:40], business_domain, clause_role, evidence_strength] if item],
        }

    return {
        "hard_evidence": False,
        "rule": "default_not_hard",
        "reason": "未满足硬证据联合门槛，保守降为非硬证据。",
        "signals": [item for item in [title[:40], business_domain, clause_role] if item],
    }


def infer_hard_evidence(section: dict[str, object]) -> bool:
    return classify_hard_evidence(section)["hard_evidence"]
