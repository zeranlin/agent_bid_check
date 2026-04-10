from __future__ import annotations

import re

from .schemas import GovernanceClusterEnvelope


SEVERITY_RANK = {"高风险": 4, "中高风险": 3, "中风险": 2, "低风险": 1, "需人工复核": 0}

FAMILY_RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "acceptance_scheme_scoring",
        re.compile(r"(将项目验收方案纳入评审因素|验收方案作为评分依据)"),
        "将项目验收方案纳入评审因素，违反评审规则合规性要求",
    ),
    (
        "import_consistency",
        re.compile(
            r"(拒绝进口|国外标准|国外部件|采购政策口径|燃油标准引用可能涉及废止版本|非进口项目中出现国外标准|"
            r"电磁兼容标准引用格式混乱且编号不完整|标准编号与名称引用混乱且缺失版本信息|"
            r"燃油标准引用已废止标准\s*GB252)"
        ),
        "拒绝进口 vs 外标/国外部件引用矛盾风险",
    ),
    (
        "acceptance_testing_cost",
        re.compile(r"(验收检测及相关部门验收费用表述笼统|将验收阶段检测费用笼统计入投标总价)"),
        "验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险",
    ),
    (
        "regional_performance",
        re.compile(r"(业绩评分限定特定行政区域|业绩要求限定特定行政区域|地域歧视和排斥潜在投标人风险)"),
        "业绩评分限定特定行政区域，存在地域排斥风险",
    ),
    (
        "guarantee_ratio",
        re.compile(r"(履约保证金比例严重超标|履约保证金比例过高[，,](增加供应商负担|加重供应商负担))"),
        "履约保证金比例严重超标",
    ),
    (
        "personnel_scoring",
        re.compile(
            r"(项目负责人学历及职称要求过高|项目负责人评分中学历、职称、证书要求设置过高且累计分值不合理|"
            r"项目负责人评分项分值畸高且设置不合理|项目负责人评分项设置过高且累计分值不合理|将PMP证书作为评分项)"
        ),
        "项目负责人评分项设置过高且累计分值不合理，存在重复评价和倾向性风险",
    ),
    (
        "scoring_clarity",
        re.compile(r"(评分表达采用定性分档或分点\+分档组合|评分描述量化口径不足|评分标准主观性过强|评分档次缺少量化口径)"),
        "评分描述量化口径不足，存在评审一致性风险",
    ),
    (
        "certification_scoring_bundle",
        re.compile(
            r"(以特定认证及特定发证机构作为评分条件|以特定认证证书作为高分条件|评分标准中要求特定非强制性认证证书|"
            r"综合实力评分中三项体系认证要求过于刚性|综合实力评分中三项体系认证‘全有或全无’设置不合理|"
            r"指定特定认证机构，具有排他性|评分标准中限定特定认证机构，限制竞争|省级标准协会颁发|采用国际标准产品确认证书|采用国际标准产品标志证书|"
            r"CNAS中国认可产品标志证书|CNAS 中国认可产品标志证书|特定协会或认证机构出具相关认证证明)"
        ),
        "以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险",
    ),
    (
        "cert_weight",
        re.compile(r"(综合实力评分中体系认证要求设置不合理|认证项权重偏高且与履约关联不足)"),
        "认证项权重偏高且与履约关联不足，存在倾向性评分风险",
    ),
    (
        "missing_detection_or_cert_requirement",
        re.compile(r"(检测报告及认证资质要求缺失或表述不明|检测报告及认证资质要求缺失或表述模糊)"),
        "检测报告及认证资质要求缺失或表述不明",
    ),
    (
        "energy_policy_missing",
        re.compile(r"(节能环保产品政策条款缺失|节能环保产品政策落实条款缺失)"),
        "节能环保产品政策条款缺失",
    ),
    (
        "acceptance_template_placeholder",
        re.compile(r"(验收流程关键时点留白|验收时点约定缺失，导致验收流程不可操作)"),
        "验收时点约定缺失，导致验收流程不可操作",
    ),
    (
        "software_copyright_competition",
        re.compile(r"(信息化软件服务能力|软件著作权登记证书|著作权人为投标人)"),
        "评分标准中“信息化软件服务能力”要求著作权人为投标人，可能限制竞争",
    ),
    (
        "sample_gate",
        re.compile(
            r"(样品制作要求具有排他性及泄露信息风险|样品隐去信息要求与评审需求存在逻辑矛盾|样品门槛风险|样品要求过细|样品制作要求过于具体|"
            r"样品图样|泄露投标人样品的任何信息|一次性送达)"
        ),
        "样品要求过细且评审规则失衡，存在样品门槛风险",
    ),
    (
        "technical_over_specific",
        re.compile(
            r"(技术参数中尺寸公差及工艺要求过于具体|技术参数中尺寸公差及材料要求过于具体|技术参数存在特定工艺和连接件描述|"
            r"参数过细且特征化|特征化导致的指向性风险|技术参数中部分指标描述模糊或存在逻辑矛盾|存在指向性嫌疑)"
        ),
        "技术参数过细且特征化，存在指向性风险",
    ),
    (
        "contract_change_imbalance",
        re.compile(r"(商务条款中采购人单方变更权过大且结算方式不明|商务条款中采购人单方调整权过大且结算方式不明|商务条款赋予采购人单方面变更权且结算方式不明)"),
        "商务条款中采购人单方变更权过大且结算方式不明",
    ),
    (
        "abnormal_standard_reference",
        re.compile(r"(错误或异常标准引用|技术参数存在错误或异常标准引用|家具采购中引用汽车车门把手标准|标准号存疑)"),
        "技术参数存在错误或异常标准引用，可能导致技术要求失真",
    ),
    (
        "regional_detection_agency_limit",
        re.compile(r"(检测机构地域限制|限定福建省检测机构|福建省检测机构出具的检测报告)"),
        "检测报告限定福建省检测机构，存在检测机构地域限制风险",
    ),
    (
        "acceptance_vendor_standard",
        re.compile(r"(厂家验收标准|验收标准引用“厂家验收标准”及“样品”|验收标准引用‘厂家验收标准’导致依据模糊)"),
        "验收标准引用“厂家验收标准”及“样品”，存在模糊表述和单方裁量风险",
    ),
    (
        "supervision_termination_imbalance",
        re.compile(r"(驻厂检查|终止合同条件过于严苛|履约监督与解除条件失衡)"),
        "履约监督与解除条件失衡",
    ),
    (
        "no_crime_submission_timing",
        re.compile(r"(无犯罪证明|合同签订后的三个月内提供)"),
        "商务条款中关于“无犯罪证明”的提交时限及无效投标处理存在法律风险",
    ),
]

SEVERITY_FLOORS: dict[str, str] = {
    "software_copyright_competition": "中风险",
    "no_crime_submission_timing": "中风险",
}

def infer_family(title: str, *context_parts: str) -> tuple[str, str]:
    normalized = str(title).strip()
    source_blob = "\n".join(part for part in [normalized, *[str(part).strip() for part in context_parts]] if str(part).strip())
    for family_key, pattern, canonical_title in FAMILY_RULES:
        if pattern.search(source_blob):
            return family_key, canonical_title
    fallback = re.sub(r"\s+", "-", normalized.lower()) or "unclassified-risk"
    return fallback, normalized


def apply_family_severity_floor(family_key: str, severity: str) -> str:
    floor = SEVERITY_FLOORS.get(family_key)
    if not floor:
        return severity
    return floor if SEVERITY_RANK.get(floor, -1) > SEVERITY_RANK.get(severity, -1) else severity


def merge_reason_for_family(family_key: str) -> str:
    reasons = {
        "import_consistency": "国外标准/国外部件、废止燃油标准和标准编号格式问题属于同一技术标准一致性风险簇，治理层统一收口为主风险。",
        "regional_performance": "同一风险家族同时覆盖行政区域与业主类型限制，治理层仅保留一个正式主风险。",
        "acceptance_testing_cost": "同一风险家族同时出现费用转嫁与投标总价打包表达，治理层统一归并为一个主风险。",
        "guarantee_ratio": "履约保证金超过法定上限时，治理层优先保留“严重超标”主标题。",
        "personnel_scoring": "项目负责人学历、职称、证书与分值结构属于同一评分风险家族，治理层统一合并。",
        "certification_scoring_bundle": "同一组评分证据同时涉及特定认证证书、特定发证机构、认证组合门槛与分值权重，治理层统一收口为一个主风险。",
        "sample_gate": "样品制作、匿名展示与误映射标题属于同一样品门槛风险簇，治理层统一归并为一个主风险。",
        "technical_over_specific": "尺寸、公差、工艺和连接件描述属于同一技术参数特征化风险簇，治理层统一归并为一个主风险。",
    }
    return reasons.get(family_key, "同一风险家族存在近义候选，治理层已归并为单一主标题。")


def infer_absorption_kind(family_key: str, title: str, canonical_title: str) -> str:
    normalized = str(title).strip()
    if family_key == "sample_gate" and "无犯罪证明" in normalized:
        return "historical_legacy_title"
    if family_key == "import_consistency" and ("GB252" in normalized or "电磁兼容" in normalized or "标准编号" in normalized):
        return "supporting_evidence_item"
    if family_key == "certification_scoring_bundle":
        return "supporting_item"
    if family_key in {"acceptance_testing_cost", "sample_gate", "technical_over_specific", "personnel_scoring"}:
        return "supporting_item"
    if normalized != canonical_title:
        return "legacy_title"
    return "same_family_duplicate"


def pick_higher_severity(current: str, incoming: str) -> str:
    return current if SEVERITY_RANK.get(current, -1) >= SEVERITY_RANK.get(incoming, -1) else incoming
