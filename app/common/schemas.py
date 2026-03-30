from __future__ import annotations

from dataclasses import dataclass, field


FIELD_ORDER = [
    "问题定性",
    "审查类型",
    "原文位置",
    "原文摘录",
    "风险判断",
    "法律/政策依据",
    "整改建议",
]

LIST_FIELDS = {"风险判断", "法律/政策依据", "整改建议"}

FIELD_ALIASES = {
    "问题标题": "问题标题",
    "标题": "问题标题",
    "问题定性": "问题定性",
    "定性": "问题定性",
    "审查类型": "审查类型",
    "类型": "审查类型",
    "原文位置": "原文位置",
    "位置": "原文位置",
    "原文摘录": "原文摘录",
    "摘录": "原文摘录",
    "风险判断": "风险判断",
    "判断": "风险判断",
    "法律/政策依据": "法律/政策依据",
    "法律依据": "法律/政策依据",
    "政策依据": "法律/政策依据",
    "依据": "法律/政策依据",
    "整改建议": "整改建议",
    "建议": "整改建议",
}


def default_scalar_value(field_name: str) -> str:
    if field_name == "问题定性":
        return "需人工复核"
    return "未发现"


def default_list_value(field_name: str) -> list[str]:
    if field_name in {"法律/政策依据", "风险判断"}:
        return ["需人工复核"]
    return ["未发现"]


@dataclass
class RiskPoint:
    title: str
    severity: str = "需人工复核"
    review_type: str = "未发现"
    source_location: str = "未发现"
    source_excerpt: str = "未发现"
    risk_judgment: list[str] = field(default_factory=lambda: ["需人工复核"])
    legal_basis: list[str] = field(default_factory=lambda: ["需人工复核"])
    rectification: list[str] = field(default_factory=lambda: ["未发现"])

    def ensure_defaults(self) -> None:
        self.title = self.title.strip() or "需人工复核事项"
        self.severity = self.severity.strip() or default_scalar_value("问题定性")
        self.review_type = self.review_type.strip() or default_scalar_value("审查类型")
        self.source_location = self.source_location.strip() or default_scalar_value("原文位置")
        self.source_excerpt = self.source_excerpt.strip() or default_scalar_value("原文摘录")
        self.risk_judgment = [item.strip() for item in self.risk_judgment if item.strip()] or default_list_value("风险判断")
        self.legal_basis = [item.strip() for item in self.legal_basis if item.strip()] or default_list_value("法律/政策依据")
        self.rectification = [item.strip() for item in self.rectification if item.strip()] or default_list_value("整改建议")


@dataclass
class ReviewReport:
    title: str = "# 招标文件合规审查结果"
    subject: str = ""
    description_lines: list[str] = field(
        default_factory=lambda: [
            "本审查基于你提供的招标文件文本进行。",
            "对于存在事实基础不足、需要采购人补充论证材料才能最终定性的事项，明确标注“需人工复核”。",
            "下述“风险判断”系合规审查意见，不等同于行政机关最终认定。",
        ]
    )
    risk_points: list[RiskPoint] = field(default_factory=list)
    summary_high_risk: list[str] = field(default_factory=list)
    summary_medium_risk: list[str] = field(default_factory=list)
    summary_manual_review: list[str] = field(default_factory=list)
    basis_summary: list[str] = field(default_factory=list)

    def ensure_defaults(self, source_name: str) -> None:
        self.subject = self.subject.strip() or source_name
        self.description_lines = [line.strip() for line in self.description_lines if line.strip()] or [
            "本审查基于你提供的招标文件文本进行。"
        ]
        for index, risk in enumerate(self.risk_points, start=1):
            if not risk.title.strip():
                risk.title = f"需人工复核事项{index}"
            risk.ensure_defaults()
        self.summary_high_risk = [item.strip() for item in self.summary_high_risk if item.strip()]
        self.summary_medium_risk = [item.strip() for item in self.summary_medium_risk if item.strip()]
        self.summary_manual_review = [item.strip() for item in self.summary_manual_review if item.strip()]
        self.basis_summary = [item.strip() for item in self.basis_summary if item.strip()]

