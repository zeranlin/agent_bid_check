from __future__ import annotations

from dataclasses import dataclass, field

from .prompts.topic_acceptance import TOPIC_ACCEPTANCE_PROMPT
from .prompts.topic_contract_payment import TOPIC_CONTRACT_PAYMENT_PROMPT
from .prompts.topic_contract import TOPIC_CONTRACT_PROMPT
from .prompts.topic_performance_staff import TOPIC_PERFORMANCE_STAFF_PROMPT
from .prompts.topic_policy import TOPIC_POLICY_PROMPT
from .prompts.topic_procedure import TOPIC_PROCEDURE_PROMPT
from .prompts.topic_qualification import TOPIC_QUALIFICATION_PROMPT
from .prompts.topic_samples_demo import TOPIC_SAMPLES_DEMO_PROMPT
from .prompts.topic_scoring import TOPIC_SCORING_PROMPT
from .prompts.topic_technical_bias import TOPIC_TECHNICAL_BIAS_PROMPT
from .prompts.topic_technical_standard import TOPIC_TECHNICAL_STANDARD_PROMPT
from .prompts.topic_technical import TOPIC_TECHNICAL_PROMPT


@dataclass(frozen=True)
class TopicBoundary:
    in_scope: tuple[str, ...]
    out_of_scope: tuple[str, ...] = ()
    primary_modules: tuple[str, ...] = ()
    secondary_modules: tuple[str, ...] = ()
    ownership_rule: str = ""
    merge_hints: tuple[str, ...] = ()


@dataclass(frozen=True)
class TopicDefinition:
    key: str
    label: str
    prompt: str = ""
    keywords: tuple[str, ...] = ()
    modules: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    priority: str = "high"
    enabled: bool = True
    boundary: TopicBoundary = field(default_factory=TopicBoundary)


@dataclass(frozen=True)
class TopicExecutionPlan:
    mode: str
    requested_keys: tuple[str, ...]
    selected_keys: tuple[str, ...]
    skipped_keys: tuple[str, ...] = ()
    max_topic_calls: int = 0
    reason: str = ""


def _topic(
    *,
    key: str,
    label: str,
    prompt: str = "",
    keywords: tuple[str, ...],
    primary_modules: tuple[str, ...],
    secondary_modules: tuple[str, ...] = (),
    in_scope: tuple[str, ...],
    out_of_scope: tuple[str, ...] = (),
    aliases: tuple[str, ...] = (),
    priority: str = "high",
    enabled: bool = True,
    ownership_rule: str,
    merge_hints: tuple[str, ...] = (),
) -> TopicDefinition:
    boundary = TopicBoundary(
        in_scope=in_scope,
        out_of_scope=out_of_scope,
        primary_modules=primary_modules,
        secondary_modules=secondary_modules,
        ownership_rule=ownership_rule,
        merge_hints=merge_hints,
    )
    return TopicDefinition(
        key=key,
        label=label,
        prompt=prompt,
        keywords=keywords,
        modules=primary_modules + secondary_modules,
        aliases=aliases,
        priority=priority,
        enabled=enabled,
        boundary=boundary,
    )


TOPIC_TAXONOMY = (
    _topic(
        key="qualification",
        label="资格条件",
        prompt=TOPIC_QUALIFICATION_PROMPT,
        keywords=("资格", "资质", "信用", "联合体", "主体资格", "准入", "资格审查"),
        primary_modules=("qualification",),
        secondary_modules=("procedure",),
        aliases=("法定资格", "特定资格"),
        priority="high",
        enabled=True,
        in_scope=("法定资格", "特定资格", "联合体要求", "供应商主体资格", "信用条件"),
        out_of_scope=("业绩要求", "人员要求", "证书奖项", "评分加分"),
        ownership_rule="只处理供应商主体准入、法定资格与特定资格，不吸收业绩、人员、奖项类要求。",
        merge_hints=("与 performance_staff 同章时，凡属于准入门槛的条款归 qualification。",),
    ),
    _topic(
        key="performance_staff",
        label="业绩与人员",
        prompt=TOPIC_PERFORMANCE_STAFF_PROMPT,
        keywords=("业绩", "证书", "奖项", "人员", "项目经理", "社保", "驻场", "团队"),
        primary_modules=("qualification",),
        secondary_modules=("scoring",),
        aliases=("业绩证书", "人员配置"),
        priority="high",
        enabled=False,
        in_scope=("类似业绩", "人员配置", "证书奖项", "社保要求", "驻场要求"),
        out_of_scope=("法定资格", "主体资格", "联合体资格"),
        ownership_rule="只处理业绩、证书、奖项、人员与社保驻场要求，不处理主体资格准入。",
        merge_hints=("若同一项既是准入门槛又参与评分，准入部分归 qualification，评分部分归 scoring。",),
    ),
    _topic(
        key="scoring",
        label="评分办法",
        prompt=TOPIC_SCORING_PROMPT,
        keywords=("评分", "评标", "评审", "分值", "综合评分", "量化", "最低评标价", "加分"),
        primary_modules=("scoring",),
        secondary_modules=(),
        aliases=("评分项", "评审标准"),
        priority="high",
        enabled=True,
        in_scope=("评分办法", "评分项", "分值设置", "量化标准", "主观分描述"),
        out_of_scope=("资格准入", "合同履约", "技术标准有效性"),
        ownership_rule="只处理评分逻辑、分值和量化标准，不处理准入资格或合同执行条件。",
        merge_hints=("样品、演示、答辩若作为评分项，其评分逻辑归 scoring，要求本身归 samples_demo。",),
    ),
    _topic(
        key="samples_demo",
        label="样品演示答辩",
        prompt=TOPIC_SAMPLES_DEMO_PROMPT,
        keywords=("样品", "演示", "答辩", "现场展示", "原型", "讲解", "试样"),
        primary_modules=("scoring", "technical"),
        secondary_modules=("procedure",),
        aliases=("样品要求", "演示答辩"),
        priority="medium",
        enabled=False,
        in_scope=("样品提交", "样品评审", "演示要求", "答辩要求", "现场展示"),
        out_of_scope=("一般技术参数", "一般评分条款", "验收样品"),
        ownership_rule="只处理样品、演示、答辩本身及其评审安排，不扩展到一般技术参数或普通评分项。",
        merge_hints=("如样品同时涉及技术参数与评分，样品义务归 samples_demo，评分分值归 scoring。",),
    ),
    _topic(
        key="technical_bias",
        label="技术倾向性",
        prompt=TOPIC_TECHNICAL_BIAS_PROMPT,
        keywords=("品牌", "型号", "专利", "专有技术", "唯一", "指定", "兼容", "原厂"),
        primary_modules=("technical",),
        secondary_modules=("acceptance",),
        aliases=("技术参数倾向", "品牌型号"),
        priority="high",
        enabled=False,
        in_scope=("品牌型号指向", "专利专有技术", "唯一性要求", "原厂证明", "兼容性指向"),
        out_of_scope=("标准有效性", "检测认证有效性", "付款履约"),
        ownership_rule="只处理技术参数对特定产品或供应商的指向性，不处理标准编号有效性问题。",
        merge_hints=("引用标准但重点在品牌型号限制时归 technical_bias；标准废止或错引归 technical_standard。",),
    ),
    _topic(
        key="technical_standard",
        label="技术标准与检测",
        prompt=TOPIC_TECHNICAL_STANDARD_PROMPT,
        keywords=("标准", "规范", "GB", "GB/T", "检测", "CMA", "CNAS", "认证", "报告"),
        primary_modules=("technical", "acceptance"),
        secondary_modules=(),
        aliases=("标准引用", "检测认证"),
        priority="high",
        enabled=False,
        in_scope=("标准引用", "标准名称编号一致性", "标准有效性", "检测报告", "认证要求"),
        out_of_scope=("品牌型号倾向", "纯评分规则", "付款节点"),
        ownership_rule="只处理标准、规范、检测认证及其有效性问题，不处理品牌型号倾向或评分分值。",
        merge_hints=("若标准要求直接形成验收门槛，仍由 technical_standard 主归属，acceptance 只看验收机制。",),
    ),
    _topic(
        key="contract_payment",
        label="付款与履约",
        prompt=TOPIC_CONTRACT_PAYMENT_PROMPT,
        keywords=("付款", "支付", "结算", "履约", "保证金", "违约", "期限", "质保"),
        primary_modules=("contract",),
        secondary_modules=("acceptance", "procedure"),
        aliases=("付款条款", "履约责任"),
        priority="high",
        enabled=False,
        in_scope=("付款节点", "结算方式", "履约期限", "保证金", "违约责任", "质保期"),
        out_of_scope=("验收主体", "标准有效性", "评分项"),
        ownership_rule="只处理付款、履约、保证金和违约责任，不处理验收组织方式本身。",
        merge_hints=("若付款节点以验收为触发条件，付款合理性归 contract_payment，验收程序归 acceptance。",),
    ),
    _topic(
        key="acceptance",
        label="验收条款",
        prompt=TOPIC_ACCEPTANCE_PROMPT,
        keywords=("验收", "交付", "试运行", "检测", "抽检", "验收主体", "验收标准"),
        primary_modules=("acceptance",),
        secondary_modules=("contract", "technical"),
        aliases=("交付验收", "验收机制"),
        priority="high",
        enabled=False,
        in_scope=("验收主体", "验收方式", "验收流程", "验收标准", "交付试运行"),
        out_of_scope=("付款节点", "品牌型号倾向", "一般程序条款"),
        ownership_rule="只处理验收主体、方式、流程与标准，不处理单纯付款或技术品牌限制。",
        merge_hints=("验收标准引用错误归 technical_standard；验收程序与主体安排归 acceptance。",),
    ),
    _topic(
        key="procedure",
        label="程序条款",
        prompt=TOPIC_PROCEDURE_PROMPT,
        keywords=("质疑", "澄清", "解释权", "截止时间", "递交", "开标", "废标", "投诉"),
        primary_modules=("procedure",),
        secondary_modules=("contract",),
        aliases=("程序门槛", "质疑澄清"),
        priority="medium",
        enabled=False,
        in_scope=("质疑", "澄清", "解释权", "投标程序", "递交要求", "开评标流程"),
        out_of_scope=("资格要求", "评分规则", "付款验收"),
        ownership_rule="只处理程序门槛、质疑澄清和解释权安排，不处理资格、评分和技术要求。",
        merge_hints=("若程序条款被设置为资格门槛，程序要求归 procedure，门槛效果归 qualification。",),
    ),
    _topic(
        key="policy",
        label="政策条款",
        prompt=TOPIC_POLICY_PROMPT,
        keywords=("中小企业", "节能", "环保", "政策", "扶持", "残疾人", "监狱企业"),
        primary_modules=("policy",),
        secondary_modules=("procedure",),
        aliases=("政策落实", "政策适用"),
        priority="medium",
        enabled=False,
        in_scope=("中小企业扶持", "节能环保", "残疾人福利", "监狱企业", "政策适用"),
        out_of_scope=("技术标准", "评分主观分", "付款履约"),
        ownership_rule="只处理政策适用与落实条款，不处理技术、评分或合同执行问题。",
        merge_hints=("政策条款若影响评分，仅政策适用本身归 policy，分值逻辑归 scoring。",),
    ),
    _topic(
        key="technical",
        label="技术细节",
        prompt=TOPIC_TECHNICAL_PROMPT,
        keywords=("技术", "参数", "标准", "品牌", "型号", "检测", "CMA", "CNAS", "样品", "GB", "GB/T"),
        primary_modules=("technical", "acceptance"),
        secondary_modules=(),
        aliases=("技术总览", "技术综合"),
        priority="high",
        enabled=True,
        in_scope=("V2 当前兼容专题：技术参数、品牌型号、标准检测、样品要求"),
        out_of_scope=("付款履约", "评分分值", "主体资格"),
        ownership_rule="这是 V2 现阶段兼容专题，临时承接 technical_bias、technical_standard、部分 samples_demo。",
        merge_hints=("后续专题扩容后，technical 应逐步拆分为 technical_bias、technical_standard 与 samples_demo。",),
    ),
    _topic(
        key="contract",
        label="合同履约",
        prompt=TOPIC_CONTRACT_PROMPT,
        keywords=("付款", "支付", "验收", "履约", "违约", "保证金", "质疑", "解释权", "合同", "商务"),
        primary_modules=("contract", "acceptance", "procedure"),
        secondary_modules=(),
        aliases=("商务合同", "履约综合"),
        priority="high",
        enabled=True,
        in_scope=("V2 当前兼容专题：付款、履约、验收、程序性合同条款"),
        out_of_scope=("主体资格", "技术标准独立问题", "评分办法"),
        ownership_rule="这是 V2 现阶段兼容专题，临时承接 contract_payment、acceptance、部分 procedure。",
        merge_hints=("后续专题扩容后，contract 应逐步拆分为 contract_payment、acceptance 与 procedure。",),
    ),
)


TOPIC_TAXONOMY_MAP = {topic.key: topic for topic in TOPIC_TAXONOMY}
ACTIVE_TOPIC_KEYS = ("qualification", "scoring", "contract", "technical")
TOPIC_SET_REGISTRY = {
    "default": ACTIVE_TOPIC_KEYS + ("procedure", "policy"),
    "slim": ("qualification", "scoring", "technical"),
    "enhanced": (
        "qualification",
        "performance_staff",
        "scoring",
        "samples_demo",
        "technical_bias",
        "technical_standard",
        "contract_payment",
        "acceptance",
        "procedure",
        "policy",
    ),
    "mature": (
        "qualification",
        "performance_staff",
        "scoring",
        "samples_demo",
        "technical_bias",
        "technical_standard",
        "contract_payment",
        "acceptance",
        "procedure",
        "policy",
    ),
}
TOPIC_MODE_BUDGETS = {
    "slim": 3,
    "default": 4,
    "enhanced": 10,
    "mature": 10,
}
TOPIC_DEFINITIONS = tuple(TOPIC_TAXONOMY_MAP[key] for key in ACTIVE_TOPIC_KEYS)
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def get_topic_definition(topic_key: str) -> TopicDefinition:
    return TOPIC_TAXONOMY_MAP[topic_key]


def get_active_topic_definitions() -> tuple[TopicDefinition, ...]:
    return TOPIC_DEFINITIONS


def resolve_topic_execution_plan(
    topic_mode: str = "default",
    topic_keys: tuple[str, ...] | list[str] | None = None,
) -> TopicExecutionPlan:
    if topic_keys:
        requested_keys = tuple(dict.fromkeys(str(key).strip() for key in topic_keys if str(key).strip()))
        selected_keys = tuple(key for key in requested_keys if key in TOPIC_TAXONOMY_MAP)
        return TopicExecutionPlan(
            mode=topic_mode,
            requested_keys=requested_keys,
            selected_keys=selected_keys,
            skipped_keys=tuple(key for key in requested_keys if key not in selected_keys),
            max_topic_calls=len(selected_keys),
            reason="custom_topic_keys",
        )

    requested_keys = TOPIC_SET_REGISTRY.get(topic_mode, TOPIC_SET_REGISTRY["default"])
    max_topic_calls = TOPIC_MODE_BUDGETS.get(topic_mode, TOPIC_MODE_BUDGETS["default"])
    available_keys = [key for key in requested_keys if key in TOPIC_TAXONOMY_MAP]
    ranked_keys = sorted(
        available_keys,
        key=lambda key: (
            PRIORITY_ORDER.get(TOPIC_TAXONOMY_MAP[key].priority, 99),
            available_keys.index(key),
        ),
    )
    selected_keys = tuple(ranked_keys[:max_topic_calls])
    skipped_keys = tuple(key for key in requested_keys if key not in selected_keys)
    return TopicExecutionPlan(
        mode=topic_mode,
        requested_keys=tuple(requested_keys),
        selected_keys=selected_keys,
        skipped_keys=skipped_keys,
        max_topic_calls=max_topic_calls,
        reason="budget_limited" if skipped_keys else "full_budget",
    )


def resolve_topic_definitions(
    topic_mode: str = "default",
    topic_keys: tuple[str, ...] | list[str] | None = None,
) -> tuple[TopicDefinition, ...]:
    plan = resolve_topic_execution_plan(topic_mode=topic_mode, topic_keys=topic_keys)
    return tuple(TOPIC_TAXONOMY_MAP[key] for key in plan.selected_keys if key in TOPIC_TAXONOMY_MAP)
