from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any

from .schemas import DocumentDomain


@dataclass(frozen=True)
class DomainResultPolicy:
    policy_id: str
    formal_output_strategy: str
    pending_output_strategy: str
    family_repeat_tolerance: int
    weak_signal_threshold: str
    internal_signal_visibility: str
    formal_count_budget: int
    pending_count_budget: int
    family_repeat_budget: int
    low_value_signal_budget: int
    priority_title_patterns: tuple[str, ...] = field(default_factory=tuple)
    low_value_title_patterns: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DOMAIN_RESULT_POLICIES: dict[DocumentDomain, DomainResultPolicy] = {
    "engineering_maintenance_construction": DomainResultPolicy(
        policy_id="domain-policy-engineering-v1",
        formal_output_strategy="protect_formal_hard_risks",
        pending_output_strategy="focus_on_high_value_execution_and_competition_issues",
        family_repeat_tolerance=1,
        weak_signal_threshold="strict",
        internal_signal_visibility="hidden_from_user",
        formal_count_budget=8,
        pending_count_budget=4,
        family_repeat_budget=1,
        low_value_signal_budget=0,
        priority_title_patterns=("品牌", "样品", "验收", "解密", "费用", "施工", "维护"),
        low_value_title_patterns=("中小企业", "证明材料", "政策", "引用不完整", "解释权", "唱标", "保证金", "质疑材料"),
    ),
    "goods_procurement": DomainResultPolicy(
        policy_id="domain-policy-goods-v1",
        formal_output_strategy="protect_formal_hard_risks",
        pending_output_strategy="keep_goods_specific_quality_and_competition_issues",
        family_repeat_tolerance=1,
        weak_signal_threshold="moderate",
        internal_signal_visibility="hidden_from_user",
        formal_count_budget=8,
        pending_count_budget=6,
        family_repeat_budget=1,
        low_value_signal_budget=0,
        priority_title_patterns=("品牌", "样品", "验收", "检测", "认证", "付款", "技术人员", "原厂工程师"),
        low_value_title_patterns=("节能环保政策", "政策条款缺失", "提醒"),
    ),
    "service_procurement": DomainResultPolicy(
        policy_id="domain-policy-service-v1",
        formal_output_strategy="protect_formal_hard_risks",
        pending_output_strategy="prioritize_service_delivery_and_scoring_boundary_issues",
        family_repeat_tolerance=1,
        weak_signal_threshold="strict",
        internal_signal_visibility="hidden_from_user",
        formal_count_budget=8,
        pending_count_budget=8,
        family_repeat_budget=1,
        low_value_signal_budget=0,
        priority_title_patterns=("服务", "物业", "验收", "品牌", "中小企业"),
        low_value_title_patterns=("无犯罪证明", "信息化软件服务能力", "人员配置数量及证书要求"),
    ),
}


def get_domain_result_policy(document_domain: DocumentDomain) -> DomainResultPolicy:
    return DOMAIN_RESULT_POLICIES[document_domain]
