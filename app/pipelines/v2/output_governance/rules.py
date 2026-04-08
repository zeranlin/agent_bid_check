from __future__ import annotations

import re

from .schemas import GovernanceClusterEnvelope, GovernanceLayer


SEVERITY_RANK = {"高风险": 4, "中高风险": 3, "中风险": 2, "低风险": 1, "需人工复核": 0}

FAMILY_RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "acceptance_scheme_scoring",
        re.compile(r"(将项目验收方案纳入评审因素|验收方案作为评分依据)"),
        "将项目验收方案纳入评审因素，违反评审规则合规性要求",
    ),
    (
        "import_consistency",
        re.compile(r"(拒绝进口|国外标准|国外部件|采购政策口径|燃油标准引用可能涉及废止版本|非进口项目中出现国外标准)"),
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
        re.compile(r"(项目负责人学历及职称要求过高|项目负责人评分中学历、职称、证书要求设置过高且累计分值不合理|项目负责人评分项分值畸高且设置不合理|项目负责人评分项设置过高且累计分值不合理)"),
        "项目负责人评分项设置过高且累计分值不合理，存在重复评价和倾向性风险",
    ),
    (
        "scoring_clarity",
        re.compile(r"(评分表达采用定性分档或分点\+分档组合|评分描述量化口径不足|评分标准主观性过强)"),
        "评分描述量化口径不足，存在评审一致性风险",
    ),
    (
        "cert_weight",
        re.compile(r"(综合实力评分中体系认证要求设置不合理|认证项权重偏高且与履约关联不足)"),
        "认证项权重偏高且与履约关联不足，存在倾向性评分风险",
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
]

FORMAL_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"(将项目验收方案纳入评审因素，违反评审规则合规性要求)"),
        "该条属于标准规则型正式风险，治理层纠偏后直接纳入正式风险。",
    ),
    (
        re.compile(r"(评分项中要求赠送非项目物资|将付款方式纳入评审因素|强制性标准条款未按评审规则标注★)"),
        "该条具备明确规则依据和正文承载，应由治理层直接纳入正式风险。",
    ),
]

PENDING_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"(残疾人福利性单位及监狱企业政策表述不完整)"),
        "当前更像政策配套表述是否完整的问题，证据不足以直接作为正式风险定性，先转为待补证复核项。",
    ),
    (
        re.compile(r"(节能环保产品政策条款缺失|节能环保产品政策落实条款缺失)"),
        "当前仅能确认节能环保政策章节召回不足，尚不足以直接认定为正式风险，先转为待补证复核项。",
    ),
]

EXCLUDED_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"(社保缴纳证明要求存在例外情形，需关注执行一致性|人员社保要求存在特殊豁免)"),
        "当前属于合理例外说明场景，未见明显失衡或异常豁免，不作为正式风险。",
    ),
    (
        re.compile(r"(验收流程关键时点留白|验收时点约定缺失，导致验收流程不可操作)"),
        "检测到合同/协议模板中的时限占位符，属于模板留白，不直接作为正式风险输出。",
    ),
]


def infer_family(title: str) -> tuple[str, str]:
    normalized = str(title).strip()
    for family_key, pattern, canonical_title in FAMILY_RULES:
        if pattern.search(normalized):
            return family_key, canonical_title
    fallback = re.sub(r"\s+", "-", normalized.lower()) or "unclassified-risk"
    return fallback, normalized


def merge_reason_for_family(family_key: str) -> str:
    reasons = {
        "regional_performance": "同一风险家族同时覆盖行政区域与业主类型限制，治理层仅保留一个正式主风险。",
        "acceptance_testing_cost": "同一风险家族同时出现费用转嫁与投标总价打包表达，治理层统一归并为一个主风险。",
        "guarantee_ratio": "履约保证金超过法定上限时，治理层优先保留“严重超标”主标题。",
        "personnel_scoring": "项目负责人学历、职称、证书与分值结构属于同一评分风险家族，治理层统一合并。",
    }
    return reasons.get(family_key, "同一风险家族存在近义候选，治理层已归并为单一主标题。")


def decide_target_layer(envelope: GovernanceClusterEnvelope) -> tuple[GovernanceLayer, str]:
    title = str(envelope.title).strip()
    source_blob = "\n".join([title, *envelope.source_excerpts, *envelope.source_locations])
    input_layer = envelope.layer
    for pattern, reason in FORMAL_RULES:
        if pattern.search(source_blob):
            return "formal_risks", reason
    for pattern, reason in EXCLUDED_RULES:
        if pattern.search(source_blob):
            return "excluded_risks", reason
    for pattern, reason in PENDING_RULES:
        if pattern.search(source_blob):
            return "pending_review_items", reason
    if input_layer in {"pending_review_items", "excluded_risks"}:
        base_reason = envelope.governance_reason or ""
        if base_reason:
            return input_layer, f"未触发治理层纠偏规则，暂保留 compare 初始层级。{base_reason}"
        return input_layer, "未触发治理层纠偏规则，暂保留 compare 初始层级。"
    if envelope.need_manual_review or envelope.severity == "需人工复核":
        return "pending_review_items", "当前专题已标记需人工复核，治理层将其保留为待补证复核项。"
    return "formal_risks", envelope.governance_reason or "通过治理层准入，保留为正式风险。"


def pick_higher_severity(current: str, incoming: str) -> str:
    return current if SEVERITY_RANK.get(current, -1) >= SEVERITY_RANK.get(incoming, -1) else incoming
