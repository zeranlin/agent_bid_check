from __future__ import annotations

import json
import re
from typing import Callable

from app.common.core import maybe_disable_qwen_thinking
from app.common.llm_client import call_chat_completion, call_chat_completion_stream, extract_response_text
from app.common.schemas import RiskPoint
from app.config import ReviewSettings

from .schemas import TopicReviewArtifact, V2StageArtifact
from .topics import TopicDefinition, resolve_topic_definitions, resolve_topic_execution_plan


JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL)
SCORING_TIER_RE = re.compile(r"(优|良|中|差|一般)\s*(得|计)?\s*\d+\s*分")
SCORING_SUBJECTIVE_SIGNALS = ("综合打分", "综合印象打分", "由评委综合打分", "酌情计分", "结合项目实际确定")
QUALIFICATION_LOCAL_SERVICE_RE = re.compile(r"(本市|当地|项目所在地).{0,8}(常设服务机构|服务机构|驻点|驻场)")
QUALIFICATION_PERFORMANCE_RE = re.compile(r"(同类项目业绩不少于\d+项|近三年同类业绩不少于\d+项|项目负责人须具备.+(职称|社保|证书))")
QUALIFICATION_REQUIREMENT_RE = re.compile(r"(资格条件|合格供应商条件|资格审查(?:表)?|投标人资格要求|供应商资格要求)")
QUALIFICATION_GATE_RE = re.compile(
    r"(作为资格条件|作为投标资格条件|作为合格供应商条件|资格审查(?:通过)?条件|投标人资格要求|供应商资格要求|"
    r"未提供.{0,24}(资格审查不通过|投标无效)|不满足.{0,12}(不得投标|不得参与投标|资格审查不通过)|"
    r"(应|须|必须)具备)"
)
QUALIFICATION_CANCELLED_OR_NON_MANDATORY_RE = re.compile(
    r"(已取消(?:的)?(?:资质|资格)|已明令取消(?:的)?(?:资质|资格)?|国务院已明令取消(?:的)?(?:资质|资格)?|"
    r"非强制(?:性)?(?:的)?(?:资质|资格)|行政机关非强制(?:性)?(?:的)?(?:资质|资格)?)"
)
QUALIFICATION_PROHIBITION_CONTEXT_RE = re.compile(r"(不得将|不得要求|严禁将)")
QUALIFICATION_MATERIAL_SUBMISSION_RE = re.compile(
    r"(资格证明文件|证明材料|资质证明文件|证照|证件|电子证照|扫描件|复印件|纸质版|纸质证照)"
)
SUPPLIER_GATE_REQUIREMENT_RE = re.compile(
    r"(资格条件|合格供应商条件|资格审查(?:表)?|投标人资格要求|合格供应商要求|供应商资格要求|"
    r"投标准入门槛|合格供应商资质条款|资格要求|投标门槛)"
)
SUPPLIER_IDENTITY_OR_REGION_LIMIT_RE = re.compile(
    r"(所有制形式|组织形式|注册地|所在地|分支机构|经营网点|某行政区域内|项目所在行政区域内|"
    r"本地公司|本地分公司|设立分支机构|常设服务机构|服务网点)"
)
SUPPLIER_GATE_USE_RE = re.compile(
    r"(作为资格条件|作为投标准入门槛|作为合格供应商条件|作为资格审查(?:通过)?条件|"
    r"作为合格供应商资质条款|资格审查不通过|投标无效|未通过资格审查|"
    r"不满足上述要求|不作为资格条件|不作为资格要求|不作为投标门槛|资格要求|投标门槛)"
)
SUPPLIER_POST_AWARD_OR_SERVICE_ONLY_RE = re.compile(
    r"(中标后|履约阶段|服务响应|售后服务|驻场服务人员|安排驻场服务人员|安排服务人员)"
)
SUPPLIER_LEGAL_CONTEXT_RE = re.compile(r"(根据法律法规要求|依法设定|依法|法定|法律法规明确要求)")
SUPPLIER_CONVENIENCE_ONLY_RE = re.compile(r"(为便于|便于沟通协调|优先考虑|建议供应商)")
ORIGINAL_OR_PAPER_CERTIFICATE_RE = re.compile(
    r"(证照原件|证件原件|资质证明文件原件|有关资质证明文件、证照、证件原件|电子证照的纸质证照|"
    r"电子证照纸质版|电子证照纸质件|纸质证照|须提供原件|必须提交原件|提交原件|提供原件)"
)
ORIGINAL_OR_PAPER_CERTIFICATE_GATE_RE = re.compile(
    r"(投标文件提交要求|资格审查材料|证明文件要求|未提交.{0,24}(资格审查不通过|投标无效|视为无效|不得分)|"
    r"资格审查不通过|投标无效|视为无效|必须提交|须提交|应提交)"
)
POST_AWARD_OR_BACKUP_CONTEXT_RE = re.compile(r"(中标后|签约前|原件备查|备查|质疑|投诉|核验|核查)")
LEGAL_VERIFICATION_CONTEXT_RE = re.compile(r"(根据法律法规要求|法律法规明确要求|依法|法定)")
SCORING_REQUIREMENT_RE = re.compile(r"(评分内容|评分标准|评分项|评审标准|评审因素|加分|得分|分值|档次评价)")
SCORING_CANCELLED_OR_NON_MANDATORY_CREDENTIAL_RE = re.compile(
    r"(已取消(?:的)?(?:资质|资格|认证)|已明令取消(?:的)?(?:资质|资格|认证)?|国务院已明令取消(?:的)?(?:资质|资格|认证)?|"
    r"非强制(?:性)?(?:的)?(?:认证|资格|资质)|行政机关非强制(?:性)?(?:的)?(?:认证|资格|资质)?)"
)
TECHNICAL_STANDARD_MISMATCH_RE = re.compile(r"(人造草\s*GB\s*36246-2018|人工材料体育场地使用要求及检验方法（?GB/T\s*20033-2006）?)")
TECHNICAL_STANDARD_OBSOLETE_RE = re.compile(r"GB/T\s*1040\.2-2006")
TECHNICAL_STANDARD_METHOD_MISMATCH_RE = re.compile(
    r"(检测方法|试验方法).{0,24}(作为交付验收依据|检测报告|验收依据)|"
    r"(透水率试验方法|塑料薄膜和薄片透水率试验方法)"
)
CONTRACT_PAYMENT_FISCAL_RE = re.compile(r"财政资金.{0,10}(到位|拨付)")
CONTRACT_PAYMENT_ACCEPTANCE_RE = re.compile(r"((终验|最终验收|审计).{0,12}(后|通过后)|验收.{0,8}(后|通过后).{0,8}(60|90|120)个工作日).{0,12}(支付|付款)")
CONTRACT_PAYMENT_DELAY_RE = re.compile(r"(60|90|120)个工作日内(支付|付款)")
IMPORT_REJECT_RE = re.compile(
    r"(不接受.{0,12}进口产品|拒绝进口|不允许选用进口产品|本项目不允许选用进口产品|仅接受国产|只接受国产)"
)
IMPORT_ACCEPT_RE = re.compile(
    r"((?<!不)(?<!拒绝)接受进口产品参与投标|允许进口产品参与投标|可采购进口产品|允许选用进口产品|(?<!不)(?<!拒绝)接受进口)"
)
FOREIGN_STANDARD_REF_RE = re.compile(
    r"\b(?:BS\s*EN|EN|IEC|ISO|ANSI|UL|DIN|ASTM|JIS|CISPR)\s*[A-Z0-9.-]*\d+(?:[./-]\d+)*(?::\d{4}|\-\d{4})?",
    re.IGNORECASE,
)
CN_STANDARD_REF_RE = re.compile(
    r"\b(?:GB/T|GB|YY/T|YY|HJ/T|HJ|GA/T|GA|JB/T|JB|SJ/T|SJ|DL/T|DL|HG/T|HG|CJ/T|CJ|QB/T|QB|JGJ|JT/T|JT)\s*[A-Z0-9.-]*\d+(?:[./-]\d+)*(?::\d{4}|\-\d{4})?",
    re.IGNORECASE,
)
EQUIVALENT_STANDARD_RE = re.compile(
    r"(等效标准.{0,8}(可接受|均可接受)|满足同等技术要求的等效标准均可接受|同等标准均可接受|或同等标准|等同或优于上述标准)"
)
STAR_RULE_GB_NON_T_RE = re.compile(r"(含有\s*GB\s*[（(]?\s*不含\s*GB/T\s*[)）]?|GB\s*[（(]?\s*不含\s*GB/T\s*[)）]?)")
STAR_RULE_MANDATORY_STANDARD_RE = re.compile(r"(国家强制性标准|强制性标准)")
STAR_RULE_REQUIREMENT_RE = re.compile(r"(需含有?★号|应标注★|需标注★|实质性条款需加★|必须加注★|应加注★)")
ACCEPTANCE_PLAN_FORBIDDEN_RE = re.compile(
    r"(不得将项目验收方案作为评审因素|验收方案不得纳入评分|验收移交方案不得作为评审项|验收资料不得作为评分因素|"
    r"不得将.{0,16}(项目)?验收(方案|移交方案|资料|资料移交安排).{0,12}(作为评审因素|纳入评分|作为评审项|作为评分因素))"
)
PAYMENT_TERMS_FORBIDDEN_RE = re.compile(
    r"(不得将付款方式作为评审因素|付款方式不得纳入评分|付款条件不得作为评分项|付款条款不得作为评审因素|"
    r"不得将.{0,16}付款(方式|条件|条款).{0,12}(作为评审因素|纳入评分|作为评分项|作为评审项))"
)
GIFTS_OR_UNRELATED_GOODS_FORBIDDEN_RE = re.compile(
    r"(不得要求提供赠品|不得要求提供回扣|不得要求提供与采购无关的其他商品|不得要求提供与采购无关的其他服务|"
    r"赠品不得作为评审因素|回扣不得纳入评分|不得要求提供赠品、回扣或者与采购无关的其他商品、服务)"
)
SPECIFIC_BRAND_OR_SUPPLIER_FORBIDDEN_RE = re.compile(
    r"(不得限定或者指定特定的专利|不得限定或者指定特定的商标|不得限定或者指定特定的品牌|"
    r"不得限定或者指定特定的供应商|不得以特定认证作为倾向性评分条件|"
    r"不得限定或者指定特定的专利、商标、品牌或者供应商)"
)
ACCEPTANCE_TESTING_COST_FORBIDDEN_RE = re.compile(
    r"(不得要求中标人承担验收产生的检测费用|验收检测费用不得由中标人承担|验收相关检测费用不得转嫁供应商)"
)
ACCEPTANCE_PLAN_TERM_RE = re.compile(
    r"(项目验收移交衔接方案|项目验收资料编制与移交衔接安排|项目验收方案设计|验收标准|验收流程安排|"
    r"验收资料准备节点|项目验收组织能力|验收衔接计划|验收移交方案|项目验收方案|竣工验收方案|"
    r"安装、检测、验收、培训计划|验收、培训计划|验收计划|验收方案|项目验收|验收移交|移交衔接|验收资料|验收安排)"
)
PAYMENT_TERMS_TERM_RE = re.compile(
    r"(付款周期短于招标文件要求|预付款比例更有利于采购人资金安排|付款节点更优|支付安排优于招标文件要求|"
    r"付款周期|预付款比例|付款方式|付款条件|付款节点|支付安排|付款期限|预付款|首付款|尾款)"
)
GIFTS_OR_UNRELATED_GOODS_TERM_RE = re.compile(
    r"(额外向采购人值班室赠送台式电脑、打印机各1套|赠送台式电脑|赠送打印机|赠送办公设备|赠送值班室物资|"
    r"附送|额外赠送|额外提供|无偿提供|赠送|赠品|台式电脑|打印机|办公设备|礼品|值班室物资|"
    r"回扣|返利|无关商品|无关服务|值班室办公设备配置|会议保障等综合服务内容|"
    r"办公设备配置|会议保障|综合服务内容)"
)
GIFTS_OR_UNRELATED_GOODS_NEGATIVE_RE = re.compile(
    r"(随机附件|随机配件|安装辅材|调试辅材|必要配套|配套附件|备品备件|延保服务|培训服务|维保服务)"
)
SPECIFIC_CERT_OR_SUPPLIER_TERM_RE = re.compile(
    r"(制造商|特定认证证书|标志证书|采用国际标准产品确认证书|采用国际标准产品标志证书|"
    r"CNAS中国认可产品标志证书|CNAS|省级标准协会|指定品牌|指定供应商|指定认证体系|"
    r"每具备一项得\d+\s*分|累计最高得分|最高得\d+\s*分)"
)
GENERIC_COMPLIANCE_PROOF_RE = re.compile(
    r"(合格证明|合格证|检验报告|检测报告|法定资质|法定许可|必备资质|国家规定的证明材料)"
)
ACCEPTANCE_TESTING_TERM_RE = re.compile(r"(检测|检验|抽检|专项检测|第三方检测|法定检测)")
ACCEPTANCE_STAGE_TERM_RE = re.compile(r"(验收|相关部门验收|验收合格之前|验收阶段|竣工验收)")
COST_SHIFT_TERM_RE = re.compile(r"(投标总价包括|自行计入|一切费用|由投标人承担|由中标人承担|负责承担|全部费用)")
ACCEPTANCE_TESTING_COST_NEGATIVE_RE = re.compile(r"(采购人承担|采购人另行委托|依法另行委托|出厂检验|自检|安装调试)")
FOREIGN_COMPONENT_PROOF_RE = re.compile(
    r"(国外生产的部件.{0,24}(合法的进货渠道证明|原产地证明)|原产地证明|国外部件|进口部件)"
)
PAYMENT_STAGE_SIGNING_RE = re.compile(r"(合同签订后|双方合同签订后)")
PAYMENT_STAGE_DELIVERY_RE = re.compile(r"(送达采购人现场|全部货物达到合同及合同附件所有要求|到货|交货)")
PAYMENT_STAGE_ACCEPTANCE_RE = re.compile(r"(验收合格|设备正常运行三个月后|终验后|最终验收后)")
PAYMENT_PERCENT_RE = re.compile(r"(\d{1,3})\s*%")
PROCUREMENT_SUBJECT_GOODS_CONTEXT_RE = re.compile(
    r"(本项目采购标的包括|采购标的包括|采购内容包括|采购范围包括|本次采购包括|本项目包含).{0,40}(台式电脑|打印机)"
)
POLICY_DISCOUNT_RE = re.compile(r"(投标总价给予\s*\d+%?\s*的扣除|给予\s*\d+%?\s*的扣除|\d+%?\s*的扣除)")
POLICY_SUBJECT_RE = re.compile(r"(中小企业|小型企业|微型企业|残疾人福利性单位|监狱企业)")
ECO_POLICY_RE = re.compile(
    r"(节能产品政府采购|环境标志产品政府采购|节能产品认证证书|环境标志产品|调整优化节能产品、环境标志产品政府采购执行机制)"
)
COMPLIANCE_PROOF_RE = re.compile(r"(合格证书|机组合格证书|认证合格证|3C认证|原产地证明|三包条例证书|节能产品认证证书)")
ANNOUNCEMENT_REFERENCE_RE = re.compile(r"(具体时间详见.*招标公告|资格要求详见.*招标公告|以公告为准|详见深圳政府采购智慧平台招标公告)")
ELECTRONIC_PROCUREMENT_RE = re.compile(r"(电子投标|电子化|智慧平台|CA签名|电子签章|深圳政府采购智慧平台|声明函不需要盖章或签字)")
CONTRACT_TEMPLATE_RE = re.compile(r"(合同条款及格式|仅供参考|合同范本|格式仅供参考)")
BRAND_DISCLOSURE_ONLY_RE = re.compile(r"(提供品牌、规格和型号)")
PARAMETER_TOLERANCE_RE = re.compile(r"(允许偏差\s*[+-]?\d+%?|允许偏差\+\d+%)")
SCORING_SCORE_LINK_RE = re.compile(
    r"(评审内容|评审标准|评分因素|得分|加分|计分|最高得\s*\d+\s*分|最高得分|满分\s*\d+\s*分|"
    r"每体现\s*\d+\s*点加\s*\d+\s*分|每项加\s*\d+\s*分|最高加\s*\d+\s*分|予以加分|"
    r"评价为[优良中差]\s*得\s*\d+\s*分|评价为差[，,、]?\s*不得分|不得分)"
)
GB_NON_T_REF_RE = re.compile(r"\bGB(?!\s*/\s*T)\s*[- ]?[A-Z0-9.-]*\d+(?:[./-]\d+)*(?::\d{4}|\-\d{4})?", re.IGNORECASE)
GB_T_REF_RE = re.compile(r"\bGB\s*/\s*T\s*[A-Z0-9.-]*\d+(?:[./-]\d+)*(?::\d{4}|\-\d{4})?", re.IGNORECASE)
MANDATORY_STANDARD_TEXT_RE = re.compile(r"(国家强制性标准|强制性标准)")
TOPIC_FAILURE_REASON_LABELS = {
    "missing_evidence": "证据不足",
    "topic_not_triggered": "专题未触发",
    "risk_not_extracted": "专题未抽出风险",
    "degraded_to_manual_review": "已降级为人工复核",
    "evidence_enough_but_risk_missed": "证据已足够但风险未抽出",
    "topic_triggered_but_partial_miss": "专题已触发但只抽出部分风险",
    "risk_degraded_to_manual_review": "存在风险但被降级为人工复核",
    "cross_topic_shared_but_single_topic_hit": "共享证据场景下仅命中单专题",
    "foreign_standard_conflict": "拒绝进口与外标直引存在潜在冲突",
    "star_marker_missing_for_mandatory_standard": "强制性标准条款未按评审规则标注★",
    "acceptance_plan_in_scoring_forbidden": "将项目验收方案纳入评审因素",
    "payment_terms_in_scoring_forbidden": "将付款方式纳入评审因素",
    "gifts_or_unrelated_goods_in_scoring_forbidden": "评分项中要求赠送非项目物资",
    "specific_brand_or_supplier_in_scoring_forbidden": "以制造商特定认证证书作为高分条件",
    "acceptance_testing_cost_shifted_to_bidder": "将验收产生的检测费用计入投标人承担范围",
    "cancelled_or_non_mandatory_qualification_as_gate": "将已取消或非强制资质资格作为资格条件",
    "cancelled_or_non_mandatory_credential_in_scoring": "将已取消或非强制资质资格认证作为评审因素",
    "original_or_paper_certificate_submission_gate": "要求提供资质证照原件或电子证照纸质件",
    "supplier_identity_or_region_limit_as_gate": "以供应商主体身份或地域条件设置准入门槛",
}
BUNDLED_RULE_SECTION_TITLES = {
    "star_marker": "内置规则库：实质性条款星标规则",
    "acceptance_plan_scoring": "内置规则库：评分因素合规性",
    "payment_terms_scoring": "内置规则库：商务评分合规性",
    "gifts_scoring": "内置规则库：评分因素相关性",
    "specific_brand_scoring": "内置规则库：评分因素公平竞争",
    "acceptance_testing_cost": "内置规则库：需求合规性",
}
BUILTIN_RULE_SENTENCES = {
    "star_required_for_gb_non_t": "评审规则合理性-含有GB（不含GB/T）或国家强制性标准的描述中需含有★号。",
    "star_required_for_mandatory_standard": "评审规则合理性-含有GB（不含GB/T）或国家强制性标准的描述中需含有★号。",
    "acceptance_plan_forbidden_in_scoring": "评审规则合规性-不得将项目验收方案作为评审因素。",
    "payment_terms_forbidden_in_scoring": "评审规则合规性-不得将付款方式作为评审因素。",
    "gifts_or_unrelated_goods_forbidden_in_scoring": "评审规则合规性-不得要求提供赠品、回扣或者与采购无关的其他商品、服务。",
    "specific_brand_or_supplier_forbidden_in_scoring": "评审规则合理性-不得限定或者指定特定的专利、商标、品牌或者供应商。",
    "acceptance_testing_cost_forbidden_to_bidder": "需求合规性-不得要求中标人承担验收产生的检测费用。",
}
SCORING_RELEVANCE_RE = re.compile(r"(排版美观|封面设计|版式完整|装订质量|字体美观)")
SCORING_INCONSISTENT_RE = re.compile(r"(满分\s*10\s*分.{0,20}满分\s*15\s*分|满分\s*15\s*分.{0,20}满分\s*10\s*分)")
TECHNICAL_STANDARD_PRIMARY_TITLE_SIGNALS = ("规格及技术参数", "技术参数", "技术要求", "主要技术参数", "技术规格", "参数要求")
COMPACT_IMPORT_CLAUSE_RE = re.compile(r"(本项目[^。；;\n]{0,80}(?:不接受|拒绝|允许)[^。；;\n]{0,60}进口[^。；;\n]{0,30}|(?:不接受|拒绝|允许)[^。；;\n]{0,60}进口[^。；;\n]{0,30})")
COMPACT_STANDARD_CLAUSE_RE = re.compile(r"((?:\b\d{1,2}\.\d{1,2}\b\s*[^\d。；;\n:：]{0,20}[:：]\s*)?(?:符合|满足)[^。；;\n]{0,120}?(?:标准|规范))")


def _extract_json_block(text: str) -> str:
    stripped = text.strip()
    match = JSON_BLOCK_RE.search(stripped)
    if match:
        return match.group(1).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped


def _parse_topic_json(text: str) -> dict:
    payload = _extract_json_block(text)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {
            "summary": "模型输出未能解析为结构化 JSON，需人工复核。",
            "need_manual_review": True,
            "coverage_note": "模型返回了非 JSON 结构。",
            "missing_evidence": ["模型返回了非 JSON 结构。"],
            "risk_points": [],
        }
    if not isinstance(data, dict):
        return {
            "summary": "模型输出结构异常，需人工复核。",
            "need_manual_review": True,
            "coverage_note": "模型返回顶层不是对象。",
            "missing_evidence": ["模型返回顶层不是对象。"],
            "risk_points": [],
        }
    return data


def _to_list(value: object, fallback: str) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or [fallback]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return [fallback]


def _to_risk_point(item: dict, topic_label: str) -> RiskPoint:
    risk = RiskPoint(
        title=str(item.get("title", "")).strip() or f"{topic_label}需人工复核事项",
        severity=str(item.get("severity", "")).strip() or "需人工复核",
        review_type=str(item.get("review_type", "")).strip() or topic_label,
        source_location=str(item.get("source_location", "")).strip() or "未发现",
        source_excerpt=str(item.get("source_excerpt", "")).strip() or "未发现",
        risk_judgment=_to_list(item.get("risk_judgment"), "需人工复核"),
        legal_basis=_to_list(item.get("legal_basis"), "需人工复核"),
        rectification=_to_list(item.get("rectification"), "未发现"),
    )
    risk.ensure_defaults()
    return risk


def _collect_section_text(sections: list[dict]) -> tuple[str, dict]:
    fragments: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        fragments.extend(
            [
                str(section.get("title", "")).strip(),
                str(section.get("excerpt", "")).strip(),
                str(section.get("body", "")).strip(),
            ]
        )
    combined_text = "\n".join(fragment for fragment in fragments if fragment)
    source_section = next((section for section in sections if isinstance(section, dict)), {})
    return combined_text, source_section


def _section_id(section: dict) -> str:
    return f"{int(section.get('start_line', 0) or 0)}-{int(section.get('end_line', 0) or 0)}"


def _dedupe_preserve(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if str(item).strip()))


def _excerpt_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if not normalized:
        return []
    parts = re.split(r"(?<=[。；;！？!?])\s*", normalized)
    return [part.strip() for part in parts if part.strip()]


def _section_sentences(section: dict) -> list[str]:
    return _excerpt_sentences(str(section.get("excerpt", "")).strip() or str(section.get("body", "")).strip())


def _find_matching_sentences(section: dict, patterns: list[re.Pattern[str]]) -> list[str]:
    matches: list[str] = []
    for sentence in _section_sentences(section):
        if any(pattern.search(sentence) for pattern in patterns):
            matches.append(sentence)
    return _dedupe_preserve(matches)


def _find_match_fragments(section: dict, pattern: re.Pattern[str], window: int = 28) -> list[str]:
    text = re.sub(r"\s+", " ", str(section.get("excerpt", "")).strip() or str(section.get("body", "")).strip())
    if not text:
        return []
    fragments: list[str] = []
    for match in pattern.finditer(text):
        start = max(match.start() - window, 0)
        end = min(match.end() + window, len(text))
        while start > 0 and text[start - 1] not in "。；;!?！？\n":
            start -= 1
        while end < len(text) and text[end] not in "。；;!?！？\n":
            end += 1
        fragment = text[start:end].strip(" ，,;；")
        if fragment:
            fragments.append(fragment)
    return _dedupe_preserve(fragments)


def _compress_import_fragments(fragments: list[str], reject_matches: list[str], accept_matches: list[str]) -> list[str]:
    compressed: list[str] = []
    for fragment in fragments:
        match = COMPACT_IMPORT_CLAUSE_RE.search(fragment)
        if match:
            compressed.append(match.group(1).strip(" ，,;；"))
        elif len(fragment) <= 90:
            compressed.append(fragment)
    if not compressed:
        compressed.extend(reject_matches[:1])
        compressed.extend([item for item in accept_matches[:1] if item not in compressed])
    return _dedupe_preserve(compressed)


def _compress_standard_fragments(fragments: list[str], refs: list[str]) -> list[str]:
    compressed: list[str] = []
    for fragment in fragments:
        match = COMPACT_STANDARD_CLAUSE_RE.search(fragment)
        if match:
            compressed.append(match.group(1).strip(" ，,;；"))
        elif len(fragment) <= 120:
            compressed.append(fragment)
    if not compressed and refs:
        compressed.append("符合 " + "、".join(refs[:3]) + " 标准")
    return _dedupe_preserve(compressed)


def _normalize_signal_sections(sections: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title", "")).strip()
        if not title:
            continue
        normalized.append(
            {
                "section_id": _section_id(section),
                "title": title,
                "start_line": section.get("start_line"),
                "end_line": section.get("end_line"),
                "module": str(section.get("module", "")).strip(),
            }
        )
    return normalized


def _dedupe_signal_sections(sections: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id", "")).strip() or f"{section.get('title', '')}:{section.get('start_line', '')}:{section.get('end_line', '')}"
        if section_id in seen:
            continue
        seen.add(section_id)
        result.append(section)
    return result


def _builtin_rule_section(kind: str) -> dict[str, object]:
    return {
        "section_id": f"builtin:{kind}",
        "title": BUNDLED_RULE_SECTION_TITLES.get(kind, "内置规则库"),
        "start_line": 0,
        "end_line": 0,
        "module": "builtin_rule",
    }


def _inject_builtin_rule_signal(
    *,
    enabled: bool,
    rule_key: str,
    section_kind: str,
    rule_sections: list[dict],
    rule_sentences: list[str],
) -> tuple[list[dict], list[str]]:
    if not enabled:
        return rule_sections, rule_sentences
    rule_sections = _dedupe_signal_sections(rule_sections + [_builtin_rule_section(section_kind)])
    rule_sentences = _dedupe_preserve(rule_sentences + [BUILTIN_RULE_SENTENCES[rule_key]])
    return rule_sections, rule_sentences


def _has_star_marker_near_text(text: str) -> bool:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    if not compact:
        return False
    return compact.startswith("★") or " ★" in compact[:12] or "★" in compact[:8]


def _extract_import_policy_signals(sections: list[dict]) -> dict[str, object]:
    combined_text, _ = _collect_section_text(sections)
    reject_matches = _dedupe_preserve([match.group(0).strip() for match in IMPORT_REJECT_RE.finditer(combined_text)])
    accept_matches = _dedupe_preserve([match.group(0).strip() for match in IMPORT_ACCEPT_RE.finditer(combined_text)])
    matched_sections: list[dict] = []
    matched_sentences: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_sentences = _find_match_fragments(section, IMPORT_REJECT_RE) + _find_match_fragments(section, IMPORT_ACCEPT_RE)
        if section_sentences:
            matched_sections.extend(_normalize_signal_sections([section]))
            matched_sentences.extend(section_sentences)
    matched_sentences = _compress_import_fragments(matched_sentences, reject_matches, accept_matches)
    if reject_matches and accept_matches:
        policy = "mixed_or_unclear"
    elif reject_matches:
        policy = "reject_import"
    elif accept_matches:
        policy = "accept_import"
    else:
        policy = "mixed_or_unclear"
    return {
        "import_policy": policy,
        "import_policy_reject_phrases": reject_matches,
        "import_policy_accept_phrases": accept_matches,
        "import_policy_sections": matched_sections,
        "import_policy_sentences": _dedupe_preserve(matched_sentences),
    }


def _extract_cancelled_or_non_mandatory_qualification_signals(sections: list[dict]) -> dict[str, object]:
    requirement_sections: list[dict] = []
    requirement_sentences: list[str] = []
    signal_sections: list[dict] = []
    signal_sentences: list[str] = []
    gate_sections: list[dict] = []
    gate_sentences: list[str] = []
    qualification_requirement_present = False
    cancelled_or_non_mandatory_qualification_signal = False
    cancelled_or_non_mandatory_qualification_used_as_gate = False
    cancelled_or_non_mandatory_qualification_prohibition_context = False

    for section in sections:
        if not isinstance(section, dict):
            continue
        text = "\n".join(
            part for part in (str(section.get("title", "")).strip(), str(section.get("excerpt", "")).strip(), str(section.get("body", "")).strip()) if part
        )
        if not text:
            continue
        has_requirement = bool(QUALIFICATION_REQUIREMENT_RE.search(text))
        has_signal = bool(QUALIFICATION_CANCELLED_OR_NON_MANDATORY_RE.search(text))
        has_gate = bool(QUALIFICATION_GATE_RE.search(text)) or has_requirement
        has_prohibition_context = bool(QUALIFICATION_PROHIBITION_CONTEXT_RE.search(text))

        if has_requirement:
            qualification_requirement_present = True
            requirement_sections.extend(_normalize_signal_sections([section]))
            requirement_sentences.extend(_find_matching_sentences(section, [QUALIFICATION_REQUIREMENT_RE]))

        if has_signal:
            cancelled_or_non_mandatory_qualification_signal = True
            signal_sections.extend(_normalize_signal_sections([section]))
            signal_sentences.extend(_find_matching_sentences(section, [QUALIFICATION_CANCELLED_OR_NON_MANDATORY_RE]))

        if has_signal and has_gate:
            cancelled_or_non_mandatory_qualification_used_as_gate = True
            gate_sections.extend(_normalize_signal_sections([section]))
            gate_sentences.extend(
                _find_matching_sentences(section, [QUALIFICATION_CANCELLED_OR_NON_MANDATORY_RE, QUALIFICATION_GATE_RE])
            )

        if has_signal and has_prohibition_context:
            cancelled_or_non_mandatory_qualification_prohibition_context = True

    return {
        "qualification_requirement_present": qualification_requirement_present,
        "qualification_requirement_sections": _dedupe_signal_sections(requirement_sections),
        "qualification_requirement_sentences": _dedupe_preserve(requirement_sentences),
        "cancelled_or_non_mandatory_qualification_signal": cancelled_or_non_mandatory_qualification_signal,
        "cancelled_or_non_mandatory_qualification_sections": _dedupe_signal_sections(signal_sections),
        "cancelled_or_non_mandatory_qualification_sentences": _dedupe_preserve(signal_sentences),
        "cancelled_or_non_mandatory_qualification_used_as_gate": cancelled_or_non_mandatory_qualification_used_as_gate,
        "cancelled_or_non_mandatory_qualification_gate_sections": _dedupe_signal_sections(gate_sections),
        "cancelled_or_non_mandatory_qualification_gate_sentences": _dedupe_preserve(gate_sentences),
        "cancelled_or_non_mandatory_qualification_prohibition_context": cancelled_or_non_mandatory_qualification_prohibition_context,
    }


def _extract_original_or_paper_certificate_submission_signals(sections: list[dict]) -> dict[str, object]:
    requirement_sections: list[dict] = []
    requirement_sentences: list[str] = []
    signal_sections: list[dict] = []
    signal_sentences: list[str] = []
    gate_sections: list[dict] = []
    gate_sentences: list[str] = []
    qualification_material_submission_present = False
    original_or_paper_certificate_requirement_signal = False
    original_or_paper_certificate_used_as_submission_gate = False
    original_or_paper_certificate_post_award_only = False
    original_or_paper_certificate_legal_verification_context = False

    for section in sections:
        if not isinstance(section, dict):
            continue
        matched_requirement_sentences: list[str] = []
        matched_signal_sentences: list[str] = []
        matched_gate_sentences: list[str] = []

        for sentence in _section_sentences(section):
            has_requirement = bool(QUALIFICATION_MATERIAL_SUBMISSION_RE.search(sentence))
            has_signal = bool(ORIGINAL_OR_PAPER_CERTIFICATE_RE.search(sentence))
            has_gate = bool(ORIGINAL_OR_PAPER_CERTIFICATE_GATE_RE.search(sentence))
            has_post_award = bool(POST_AWARD_OR_BACKUP_CONTEXT_RE.search(sentence))
            has_legal = bool(LEGAL_VERIFICATION_CONTEXT_RE.search(sentence))

            if has_requirement:
                qualification_material_submission_present = True
                matched_requirement_sentences.append(sentence)

            if has_signal:
                original_or_paper_certificate_requirement_signal = True
                matched_signal_sentences.append(sentence)
                if has_post_award:
                    original_or_paper_certificate_post_award_only = True
                if has_legal:
                    original_or_paper_certificate_legal_verification_context = True

            if has_signal and has_gate and not has_post_award and not has_legal:
                original_or_paper_certificate_used_as_submission_gate = True
                matched_gate_sentences.append(sentence)

        if matched_requirement_sentences:
            requirement_sections.extend(_normalize_signal_sections([section]))
            requirement_sentences.extend(matched_requirement_sentences)
        if matched_signal_sentences:
            signal_sections.extend(_normalize_signal_sections([section]))
            signal_sentences.extend(matched_signal_sentences)
        if matched_gate_sentences:
            gate_sections.extend(_normalize_signal_sections([section]))
            gate_sentences.extend(matched_gate_sentences)

    return {
        "qualification_material_submission_present": qualification_material_submission_present,
        "qualification_material_submission_sections": _dedupe_signal_sections(requirement_sections),
        "qualification_material_submission_sentences": _dedupe_preserve(requirement_sentences),
        "original_or_paper_certificate_requirement_signal": original_or_paper_certificate_requirement_signal,
        "original_or_paper_certificate_requirement_sections": _dedupe_signal_sections(signal_sections),
        "original_or_paper_certificate_requirement_sentences": _dedupe_preserve(signal_sentences),
        "original_or_paper_certificate_used_as_submission_gate": original_or_paper_certificate_used_as_submission_gate,
        "original_or_paper_certificate_gate_sections": _dedupe_signal_sections(gate_sections),
        "original_or_paper_certificate_gate_sentences": _dedupe_preserve(gate_sentences),
        "original_or_paper_certificate_post_award_only": original_or_paper_certificate_post_award_only,
        "original_or_paper_certificate_legal_verification_context": original_or_paper_certificate_legal_verification_context,
    }


def _extract_supplier_identity_or_region_gate_signals(sections: list[dict]) -> dict[str, object]:
    requirement_sections: list[dict] = []
    requirement_sentences: list[str] = []
    signal_sections: list[dict] = []
    signal_sentences: list[str] = []
    gate_sections: list[dict] = []
    gate_sentences: list[str] = []
    supplier_gate_requirement_present = False
    supplier_identity_or_region_limit_signal = False
    supplier_identity_or_region_limit_used_as_gate = False
    supplier_identity_or_region_post_award_service_only = False
    supplier_identity_or_region_legal_context = False

    for section in sections:
        if not isinstance(section, dict):
            continue
        matched_requirement_sentences: list[str] = []
        matched_signal_sentences: list[str] = []
        matched_gate_sentences: list[str] = []

        for sentence in _section_sentences(section):
            has_requirement = bool(SUPPLIER_GATE_REQUIREMENT_RE.search(sentence))
            has_signal = bool(SUPPLIER_IDENTITY_OR_REGION_LIMIT_RE.search(sentence))
            has_gate = bool(SUPPLIER_GATE_USE_RE.search(sentence)) or has_requirement
            has_post_award = bool(SUPPLIER_POST_AWARD_OR_SERVICE_ONLY_RE.search(sentence))
            has_legal = bool(SUPPLIER_LEGAL_CONTEXT_RE.search(sentence))
            has_convenience = bool(SUPPLIER_CONVENIENCE_ONLY_RE.search(sentence))

            if has_requirement:
                supplier_gate_requirement_present = True
                matched_requirement_sentences.append(sentence)

            if has_signal:
                supplier_identity_or_region_limit_signal = True
                matched_signal_sentences.append(sentence)
                if has_post_award:
                    supplier_identity_or_region_post_award_service_only = True
                if has_legal or has_convenience:
                    supplier_identity_or_region_legal_context = True

            if has_signal and has_gate and not has_post_award and not has_legal and not has_convenience:
                supplier_identity_or_region_limit_used_as_gate = True
                matched_gate_sentences.append(sentence)

        if matched_requirement_sentences:
            requirement_sections.extend(_normalize_signal_sections([section]))
            requirement_sentences.extend(matched_requirement_sentences)
        if matched_signal_sentences:
            signal_sections.extend(_normalize_signal_sections([section]))
            signal_sentences.extend(matched_signal_sentences)
        if matched_gate_sentences:
            gate_sections.extend(_normalize_signal_sections([section]))
            gate_sentences.extend(matched_gate_sentences)

    return {
        "supplier_gate_requirement_present": supplier_gate_requirement_present,
        "supplier_gate_requirement_sections": _dedupe_signal_sections(requirement_sections),
        "supplier_gate_requirement_sentences": _dedupe_preserve(requirement_sentences),
        "supplier_identity_or_region_limit_signal": supplier_identity_or_region_limit_signal,
        "supplier_identity_or_region_limit_sections": _dedupe_signal_sections(signal_sections),
        "supplier_identity_or_region_limit_sentences": _dedupe_preserve(signal_sentences),
        "supplier_identity_or_region_limit_used_as_gate": supplier_identity_or_region_limit_used_as_gate,
        "supplier_identity_or_region_gate_sections": _dedupe_signal_sections(gate_sections),
        "supplier_identity_or_region_gate_sentences": _dedupe_preserve(gate_sentences),
        "supplier_identity_or_region_post_award_service_only": supplier_identity_or_region_post_award_service_only,
        "supplier_identity_or_region_legal_context": supplier_identity_or_region_legal_context,
    }


def _extract_standard_reference_signals(sections: list[dict]) -> dict[str, object]:
    combined_text, _ = _collect_section_text(sections)
    foreign_refs = _dedupe_preserve([match.group(0).strip() for match in FOREIGN_STANDARD_REF_RE.finditer(combined_text)])
    cn_refs = _dedupe_preserve([match.group(0).strip() for match in CN_STANDARD_REF_RE.finditer(combined_text)])
    has_equivalent_standard_clause = bool(EQUIVALENT_STANDARD_RE.search(combined_text))
    foreign_sections: list[dict] = []
    cn_sections: list[dict] = []
    equivalent_sections: list[dict] = []
    foreign_sentences: list[str] = []
    cn_sentences: list[str] = []
    equivalent_sentences: list[str] = []
    gb_non_t_sections: list[dict] = []
    gb_non_t_sentences: list[str] = []
    gbt_sections: list[dict] = []
    gbt_sentences: list[str] = []
    mandatory_standard_sections: list[dict] = []
    mandatory_standard_sentences: list[str] = []
    standard_clause_flags: list[dict[str, object]] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_foreign_sentences = _find_match_fragments(section, FOREIGN_STANDARD_REF_RE)
        section_cn_sentences = _find_match_fragments(section, CN_STANDARD_REF_RE)
        section_equivalent_sentences = _find_match_fragments(section, EQUIVALENT_STANDARD_RE)
        section_gb_non_t_sentences = _find_match_fragments(section, GB_NON_T_REF_RE)
        section_gbt_sentences = _find_match_fragments(section, GB_T_REF_RE)
        section_mandatory_sentences = _find_match_fragments(section, MANDATORY_STANDARD_TEXT_RE)
        if section_foreign_sentences:
            foreign_sections.extend(_normalize_signal_sections([section]))
            foreign_sentences.extend(section_foreign_sentences)
        if section_cn_sentences:
            cn_sections.extend(_normalize_signal_sections([section]))
            cn_sentences.extend(section_cn_sentences)
        if section_equivalent_sentences:
            equivalent_sections.extend(_normalize_signal_sections([section]))
            equivalent_sentences.extend(section_equivalent_sentences)
        if section_gb_non_t_sentences:
            gb_non_t_sections.extend(_normalize_signal_sections([section]))
            gb_non_t_sentences.extend(section_gb_non_t_sentences)
        if section_gbt_sentences:
            gbt_sections.extend(_normalize_signal_sections([section]))
            gbt_sentences.extend(section_gbt_sentences)
        if section_mandatory_sentences:
            mandatory_standard_sections.extend(_normalize_signal_sections([section]))
            mandatory_standard_sentences.extend(section_mandatory_sentences)
        clause_sentences = _dedupe_preserve(section_gb_non_t_sentences + section_gbt_sentences + section_mandatory_sentences)
        for clause in clause_sentences:
            clause_text = re.sub(r"\s+", " ", clause).strip()
            standard_clause_flags.append(
                {
                    "section_id": _section_id(section),
                    "title": str(section.get("title", "")).strip(),
                    "start_line": section.get("start_line"),
                    "end_line": section.get("end_line"),
                    "clause_text": clause_text,
                    "contains_gb_non_t": bool(GB_NON_T_REF_RE.search(clause_text)),
                    "contains_gbt": bool(GB_T_REF_RE.search(clause_text)),
                    "contains_mandatory_standard": bool(MANDATORY_STANDARD_TEXT_RE.search(clause_text)),
                    "has_star_marker": _has_star_marker_near_text(clause_text) or _has_star_marker_near_text(str(section.get("title", ""))),
                }
            )
    foreign_sentences = _compress_standard_fragments(foreign_sentences, foreign_refs)
    cn_sentences = _compress_standard_fragments(cn_sentences, cn_refs)
    if foreign_refs and cn_refs:
        standard_system_mix = "mixed_cn_foreign"
    elif foreign_refs:
        standard_system_mix = "foreign_only"
    elif cn_refs:
        standard_system_mix = "cn_only"
    else:
        standard_system_mix = "none"
    return {
        "foreign_standard_refs": foreign_refs,
        "cn_standard_refs": cn_refs,
        "has_equivalent_standard_clause": has_equivalent_standard_clause,
        "standard_system_mix": standard_system_mix,
        "foreign_standard_has_version": any(re.search(r"[:\-]\d{4}$", ref) for ref in foreign_refs),
        "foreign_standard_sections": foreign_sections,
        "foreign_standard_sentences": _dedupe_preserve(foreign_sentences),
        "cn_standard_sections": cn_sections,
        "cn_standard_sentences": _dedupe_preserve(cn_sentences),
        "equivalent_standard_sections": equivalent_sections,
        "equivalent_standard_sentences": _dedupe_preserve(equivalent_sentences),
        "contains_gb_non_t": bool(gb_non_t_sentences),
        "contains_gbt": any(bool(item.get("contains_gbt", False)) for item in standard_clause_flags),
        "contains_mandatory_standard": bool(mandatory_standard_sentences),
        "gb_non_t_sections": gb_non_t_sections,
        "gb_non_t_sentences": _dedupe_preserve(gb_non_t_sentences),
        "gbt_sections": gbt_sections,
        "gbt_sentences": _dedupe_preserve(gbt_sentences),
        "mandatory_standard_sections": mandatory_standard_sections,
        "mandatory_standard_sentences": _dedupe_preserve(mandatory_standard_sentences),
        "has_star_marker": any(bool(item.get("has_star_marker")) for item in standard_clause_flags),
        "standard_clause_flags": standard_clause_flags,
    }


def _extract_star_rule_signals(sections: list[dict]) -> dict[str, object]:
    matched_sections: list[dict] = []
    matched_sentences: list[str] = []
    star_required_for_gb_non_t = False
    star_required_for_mandatory_standard = False
    for section in sections:
        if not isinstance(section, dict):
            continue
        text = "\n".join(
            part for part in (str(section.get("title", "")).strip(), str(section.get("excerpt", "")).strip(), str(section.get("body", "")).strip()) if part
        )
        if not text:
            continue
        has_star_requirement = bool(STAR_RULE_REQUIREMENT_RE.search(text))
        has_gb_non_t_rule = bool(STAR_RULE_GB_NON_T_RE.search(text))
        has_mandatory_standard_rule = bool(STAR_RULE_MANDATORY_STANDARD_RE.search(text))
        if has_star_requirement and (has_gb_non_t_rule or has_mandatory_standard_rule):
            matched_sections.extend(_normalize_signal_sections([section]))
            matched_sentences.extend(_find_match_fragments(section, STAR_RULE_REQUIREMENT_RE))
        if has_star_requirement and has_gb_non_t_rule:
            star_required_for_gb_non_t = True
        if has_star_requirement and has_mandatory_standard_rule:
            star_required_for_mandatory_standard = True
    star_required_for_gb_non_t = True
    star_required_for_mandatory_standard = True
    matched_sections, matched_sentences = _inject_builtin_rule_signal(
        enabled=True,
        rule_key="star_required_for_gb_non_t",
        section_kind="star_marker",
        rule_sections=matched_sections,
        rule_sentences=matched_sentences,
    )
    return {
        "star_required_for_gb_non_t": star_required_for_gb_non_t,
        "star_required_for_mandatory_standard": star_required_for_mandatory_standard,
        "star_rule_sections": _dedupe_signal_sections(matched_sections) if matched_sections else [],
        "star_rule_sentences": _dedupe_preserve(matched_sentences),
    }


def _extract_acceptance_plan_scoring_signals(sections: list[dict]) -> dict[str, object]:
    rule_sections: list[dict] = []
    rule_sentences: list[str] = []
    acceptance_sections: list[dict] = []
    acceptance_sentences: list[str] = []
    scoring_contains_acceptance_plan = False
    acceptance_plan_linked_to_score = False

    for section in sections:
        if not isinstance(section, dict):
            continue
        text = "\n".join(
            part for part in (str(section.get("title", "")).strip(), str(section.get("excerpt", "")).strip(), str(section.get("body", "")).strip()) if part
        )
        if not text:
            continue
        has_forbidden_rule = bool(ACCEPTANCE_PLAN_FORBIDDEN_RE.search(text))
        has_acceptance_term = bool(ACCEPTANCE_PLAN_TERM_RE.search(text))
        has_score_link = bool(SCORING_SCORE_LINK_RE.search(text))

        if has_forbidden_rule:
            rule_sections.extend(_normalize_signal_sections([section]))
            fragments = _find_match_fragments(section, ACCEPTANCE_PLAN_FORBIDDEN_RE)
            rule_sentences.extend(fragments or _find_match_fragments(section, SCORING_SCORE_LINK_RE))

        if has_acceptance_term:
            scoring_contains_acceptance_plan = True
            acceptance_sections.extend(_normalize_signal_sections([section]))
            acceptance_sentences.extend(_find_match_fragments(section, ACCEPTANCE_PLAN_TERM_RE))

        if has_acceptance_term and has_score_link:
            acceptance_plan_linked_to_score = True
            acceptance_sections.extend(_normalize_signal_sections([section]))
            acceptance_sentences.extend(_find_match_fragments(section, SCORING_SCORE_LINK_RE))
    rule_sections, rule_sentences = _inject_builtin_rule_signal(
        enabled=True,
        rule_key="acceptance_plan_forbidden_in_scoring",
        section_kind="acceptance_plan_scoring",
        rule_sections=rule_sections,
        rule_sentences=rule_sentences,
    )

    return {
        "acceptance_plan_forbidden_in_scoring": bool(rule_sections),
        "acceptance_plan_rule_sections": _dedupe_signal_sections(rule_sections),
        "acceptance_plan_rule_sentences": _dedupe_preserve(rule_sentences),
        "scoring_contains_acceptance_plan": scoring_contains_acceptance_plan,
        "acceptance_plan_scoring_sections": _dedupe_signal_sections(acceptance_sections),
        "acceptance_plan_scoring_sentences": _dedupe_preserve(acceptance_sentences),
        "acceptance_plan_linked_to_score": acceptance_plan_linked_to_score,
    }


def _extract_payment_terms_scoring_signals(sections: list[dict]) -> dict[str, object]:
    rule_sections: list[dict] = []
    rule_sentences: list[str] = []
    payment_sections: list[dict] = []
    payment_sentences: list[str] = []
    scoring_contains_payment_terms = False
    payment_terms_linked_to_score = False

    for section in sections:
        if not isinstance(section, dict):
            continue
        text = "\n".join(
            part for part in (str(section.get("title", "")).strip(), str(section.get("excerpt", "")).strip(), str(section.get("body", "")).strip()) if part
        )
        if not text:
            continue
        has_forbidden_rule = bool(PAYMENT_TERMS_FORBIDDEN_RE.search(text))
        has_payment_term = bool(PAYMENT_TERMS_TERM_RE.search(text))
        has_score_link = bool(SCORING_SCORE_LINK_RE.search(text))

        if has_forbidden_rule:
            rule_sections.extend(_normalize_signal_sections([section]))
            fragments = _find_match_fragments(section, PAYMENT_TERMS_FORBIDDEN_RE)
            rule_sentences.extend(fragments or _find_match_fragments(section, SCORING_SCORE_LINK_RE))

        if has_payment_term:
            scoring_contains_payment_terms = True
            payment_sections.extend(_normalize_signal_sections([section]))
            payment_sentences.extend(_find_match_fragments(section, PAYMENT_TERMS_TERM_RE))

        if has_payment_term and has_score_link:
            payment_terms_linked_to_score = True
            payment_sections.extend(_normalize_signal_sections([section]))
            payment_sentences.extend(_find_match_fragments(section, SCORING_SCORE_LINK_RE))
    rule_sections, rule_sentences = _inject_builtin_rule_signal(
        enabled=True,
        rule_key="payment_terms_forbidden_in_scoring",
        section_kind="payment_terms_scoring",
        rule_sections=rule_sections,
        rule_sentences=rule_sentences,
    )

    return {
        "payment_terms_forbidden_in_scoring": bool(rule_sections),
        "payment_terms_rule_sections": _dedupe_signal_sections(rule_sections),
        "payment_terms_rule_sentences": _dedupe_preserve(rule_sentences),
        "scoring_contains_payment_terms": scoring_contains_payment_terms,
        "payment_terms_scoring_sections": _dedupe_signal_sections(payment_sections),
        "payment_terms_scoring_sentences": _dedupe_preserve(payment_sentences),
        "payment_terms_linked_to_score": payment_terms_linked_to_score,
    }


def _extract_gifts_or_unrelated_goods_scoring_signals(sections: list[dict]) -> dict[str, object]:
    rule_sections: list[dict] = []
    rule_sentences: list[str] = []
    goods_sections: list[dict] = []
    goods_sentences: list[str] = []
    scoring_contains_gifts_or_unrelated_goods = False
    gifts_or_goods_linked_to_score = False

    for section in sections:
        if not isinstance(section, dict):
            continue
        text = "\n".join(
            part for part in (str(section.get("title", "")).strip(), str(section.get("excerpt", "")).strip(), str(section.get("body", "")).strip()) if part
        )
        if not text:
            continue
        has_forbidden_rule = bool(GIFTS_OR_UNRELATED_GOODS_FORBIDDEN_RE.search(text))
        has_goods_term = bool(GIFTS_OR_UNRELATED_GOODS_TERM_RE.search(text))
        has_score_link = bool(SCORING_SCORE_LINK_RE.search(text))
        goods_is_procurement_subject = bool(PROCUREMENT_SUBJECT_GOODS_CONTEXT_RE.search(text))

        if has_forbidden_rule:
            rule_sections.extend(_normalize_signal_sections([section]))
            fragments = _find_match_fragments(section, GIFTS_OR_UNRELATED_GOODS_FORBIDDEN_RE)
            rule_sentences.extend(fragments or _find_match_fragments(section, SCORING_SCORE_LINK_RE))

        goods_is_project_related = bool(GIFTS_OR_UNRELATED_GOODS_NEGATIVE_RE.search(text))

        if has_goods_term and not goods_is_procurement_subject and not goods_is_project_related:
            scoring_contains_gifts_or_unrelated_goods = True
            goods_sections.extend(_normalize_signal_sections([section]))
            goods_sentences.extend(_find_match_fragments(section, GIFTS_OR_UNRELATED_GOODS_TERM_RE))

        if has_goods_term and has_score_link and not goods_is_procurement_subject and not goods_is_project_related:
            gifts_or_goods_linked_to_score = True
            goods_sections.extend(_normalize_signal_sections([section]))
            goods_sentences.extend(_find_match_fragments(section, SCORING_SCORE_LINK_RE))
    rule_sections, rule_sentences = _inject_builtin_rule_signal(
        enabled=True,
        rule_key="gifts_or_unrelated_goods_forbidden_in_scoring",
        section_kind="gifts_scoring",
        rule_sections=rule_sections,
        rule_sentences=rule_sentences,
    )

    return {
        "gifts_or_unrelated_goods_forbidden_in_scoring": bool(rule_sections),
        "gifts_or_goods_rule_sections": _dedupe_signal_sections(rule_sections),
        "gifts_or_goods_rule_sentences": _dedupe_preserve(rule_sentences),
        "scoring_contains_gifts_or_unrelated_goods": scoring_contains_gifts_or_unrelated_goods,
        "gifts_or_goods_scoring_sections": _dedupe_signal_sections(goods_sections),
        "gifts_or_goods_scoring_sentences": _dedupe_preserve(goods_sentences),
        "gifts_or_goods_linked_to_score": gifts_or_goods_linked_to_score,
    }


def _extract_specific_cert_or_supplier_scoring_signals(sections: list[dict]) -> dict[str, object]:
    rule_sections: list[dict] = []
    rule_sentences: list[str] = []
    scoring_sections: list[dict] = []
    scoring_sentences: list[str] = []
    scoring_contains_specific_cert_or_supplier_signal = False
    specific_cert_or_supplier_score_linked = False

    for section in sections:
        if not isinstance(section, dict):
            continue
        text = "\n".join(
            part for part in (str(section.get("title", "")).strip(), str(section.get("excerpt", "")).strip(), str(section.get("body", "")).strip()) if part
        )
        if not text:
            continue
        has_forbidden_rule = bool(SPECIFIC_BRAND_OR_SUPPLIER_FORBIDDEN_RE.search(text))
        has_specific_signal = bool(SPECIFIC_CERT_OR_SUPPLIER_TERM_RE.search(text))
        has_score_link = bool(SCORING_SCORE_LINK_RE.search(text))
        is_generic_proof_only = bool(GENERIC_COMPLIANCE_PROOF_RE.search(text)) and not (
            "制造商" in text or "CNAS" in text or "标志证书" in text or "确认证书" in text or "省级标准协会" in text
        )

        if has_forbidden_rule:
            rule_sections.extend(_normalize_signal_sections([section]))
            fragments = _find_match_fragments(section, SPECIFIC_BRAND_OR_SUPPLIER_FORBIDDEN_RE)
            rule_sentences.extend(fragments or _find_match_fragments(section, SCORING_SCORE_LINK_RE))

        if has_specific_signal and not is_generic_proof_only:
            scoring_contains_specific_cert_or_supplier_signal = True
            scoring_sections.extend(_normalize_signal_sections([section]))
            scoring_sentences.extend(_find_match_fragments(section, SPECIFIC_CERT_OR_SUPPLIER_TERM_RE))

        if has_specific_signal and has_score_link and not is_generic_proof_only:
            specific_cert_or_supplier_score_linked = True
            scoring_sections.extend(_normalize_signal_sections([section]))
            scoring_sentences.extend(_find_match_fragments(section, SCORING_SCORE_LINK_RE))
    rule_sections, rule_sentences = _inject_builtin_rule_signal(
        enabled=True,
        rule_key="specific_brand_or_supplier_forbidden_in_scoring",
        section_kind="specific_brand_scoring",
        rule_sections=rule_sections,
        rule_sentences=rule_sentences,
    )

    return {
        "specific_brand_or_supplier_forbidden_in_scoring": bool(rule_sections),
        "specific_brand_or_supplier_rule_sections": _dedupe_signal_sections(rule_sections),
        "specific_brand_or_supplier_rule_sentences": _dedupe_preserve(rule_sentences),
        "scoring_contains_specific_cert_or_supplier_signal": scoring_contains_specific_cert_or_supplier_signal,
        "specific_cert_or_supplier_scoring_sections": _dedupe_signal_sections(scoring_sections),
        "specific_cert_or_supplier_evidence": _dedupe_preserve(scoring_sentences),
        "specific_cert_or_supplier_score_linked": specific_cert_or_supplier_score_linked,
    }


def _extract_cancelled_or_non_mandatory_scoring_credential_signals(sections: list[dict]) -> dict[str, object]:
    scoring_sections: list[dict] = []
    scoring_sentences: list[str] = []
    signal_sections: list[dict] = []
    signal_sentences: list[str] = []
    linked_sections: list[dict] = []
    linked_sentences: list[str] = []
    scoring_requirement_present = False
    cancelled_or_non_mandatory_scoring_credential_signal = False
    cancelled_or_non_mandatory_scoring_credential_linked_to_score = False

    for section in sections:
        if not isinstance(section, dict):
            continue
        text = "\n".join(
            part for part in (str(section.get("title", "")).strip(), str(section.get("excerpt", "")).strip(), str(section.get("body", "")).strip()) if part
        )
        if not text:
            continue
        matched_scoring_sentences: list[str] = []
        matched_signal_sentences: list[str] = []
        matched_linked_sentences: list[str] = []
        for sentence in _section_sentences(section):
            sentence_has_scoring_requirement = bool(SCORING_REQUIREMENT_RE.search(sentence))
            sentence_has_signal = bool(SCORING_CANCELLED_OR_NON_MANDATORY_CREDENTIAL_RE.search(sentence))
            sentence_has_score_link = bool(SCORING_SCORE_LINK_RE.search(sentence))

            if sentence_has_scoring_requirement:
                scoring_requirement_present = True
                matched_scoring_sentences.append(sentence)

            if sentence_has_signal and sentence_has_scoring_requirement:
                cancelled_or_non_mandatory_scoring_credential_signal = True
                matched_signal_sentences.append(sentence)

            if sentence_has_signal and sentence_has_score_link:
                cancelled_or_non_mandatory_scoring_credential_linked_to_score = True
                matched_linked_sentences.append(sentence)

        if matched_scoring_sentences:
            scoring_sections.extend(_normalize_signal_sections([section]))
            scoring_sentences.extend(matched_scoring_sentences)

        if matched_signal_sentences:
            signal_sections.extend(_normalize_signal_sections([section]))
            signal_sentences.extend(matched_signal_sentences)

        if matched_linked_sentences:
            linked_sections.extend(_normalize_signal_sections([section]))
            linked_sentences.extend(matched_linked_sentences)

    return {
        "scoring_requirement_present": scoring_requirement_present,
        "scoring_requirement_sections": _dedupe_signal_sections(scoring_sections),
        "scoring_requirement_sentences": _dedupe_preserve(scoring_sentences),
        "cancelled_or_non_mandatory_scoring_credential_signal": cancelled_or_non_mandatory_scoring_credential_signal,
        "cancelled_or_non_mandatory_scoring_credential_sections": _dedupe_signal_sections(signal_sections),
        "cancelled_or_non_mandatory_scoring_credential_sentences": _dedupe_preserve(signal_sentences),
        "cancelled_or_non_mandatory_scoring_credential_linked_to_score": cancelled_or_non_mandatory_scoring_credential_linked_to_score,
        "cancelled_or_non_mandatory_scoring_credential_linked_sections": _dedupe_signal_sections(linked_sections),
        "cancelled_or_non_mandatory_scoring_credential_linked_sentences": _dedupe_preserve(linked_sentences),
    }


def _extract_acceptance_testing_cost_signals(sections: list[dict]) -> dict[str, object]:
    rule_sections: list[dict] = []
    rule_sentences: list[str] = []
    demand_sections: list[dict] = []
    demand_sentences: list[str] = []
    demand_contains_acceptance_testing_cost_signal = False
    acceptance_testing_cost_shifted_to_bidder = False

    for section in sections:
        if not isinstance(section, dict):
            continue
        text = "\n".join(
            part for part in (str(section.get("title", "")).strip(), str(section.get("excerpt", "")).strip(), str(section.get("body", "")).strip()) if part
        )
        if not text:
            continue
        has_forbidden_rule = bool(ACCEPTANCE_TESTING_COST_FORBIDDEN_RE.search(text))
        has_testing_term = bool(ACCEPTANCE_TESTING_TERM_RE.search(text))
        has_acceptance_term = bool(ACCEPTANCE_STAGE_TERM_RE.search(text))
        has_cost_shift_term = bool(COST_SHIFT_TERM_RE.search(text))
        has_negative_context = bool(ACCEPTANCE_TESTING_COST_NEGATIVE_RE.search(text))

        if has_forbidden_rule:
            rule_sections.extend(_normalize_signal_sections([section]))
            fragments = _find_match_fragments(section, ACCEPTANCE_TESTING_COST_FORBIDDEN_RE)
            rule_sentences.extend(fragments or _find_match_fragments(section, ACCEPTANCE_STAGE_TERM_RE))

        if has_testing_term and has_acceptance_term and not has_negative_context:
            demand_contains_acceptance_testing_cost_signal = True
            demand_sections.extend(_normalize_signal_sections([section]))
            demand_sentences.extend(_find_matching_sentences(section, [ACCEPTANCE_TESTING_TERM_RE, ACCEPTANCE_STAGE_TERM_RE]))

        if has_testing_term and has_acceptance_term and has_cost_shift_term and not has_negative_context:
            acceptance_testing_cost_shifted_to_bidder = True
            demand_sections.extend(_normalize_signal_sections([section]))
            demand_sentences.extend(_find_matching_sentences(section, [ACCEPTANCE_TESTING_TERM_RE, ACCEPTANCE_STAGE_TERM_RE, COST_SHIFT_TERM_RE]))
    rule_sections, rule_sentences = _inject_builtin_rule_signal(
        enabled=True,
        rule_key="acceptance_testing_cost_forbidden_to_bidder",
        section_kind="acceptance_testing_cost",
        rule_sections=rule_sections,
        rule_sentences=rule_sentences,
    )

    return {
        "acceptance_testing_cost_forbidden_to_bidder": bool(rule_sections),
        "acceptance_testing_cost_rule_sections": _dedupe_signal_sections(rule_sections),
        "acceptance_testing_cost_rule_sentences": _dedupe_preserve(rule_sentences),
        "demand_contains_acceptance_testing_cost_signal": demand_contains_acceptance_testing_cost_signal,
        "acceptance_testing_cost_sections": _dedupe_signal_sections(demand_sections),
        "acceptance_testing_cost_evidence": _dedupe_preserve(demand_sentences),
        "acceptance_testing_cost_shifted_to_bidder": acceptance_testing_cost_shifted_to_bidder,
    }


def _extract_policy_execution_signals(sections: list[dict]) -> dict[str, object]:
    discount_sections: list[dict] = []
    discount_sentences: list[str] = []
    eco_sections: list[dict] = []
    eco_sentences: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        discount_matches = _find_matching_sentences(section, [POLICY_DISCOUNT_RE, POLICY_SUBJECT_RE])
        eco_matches = _find_matching_sentences(section, [ECO_POLICY_RE])
        if discount_matches:
            discount_sections.extend(_normalize_signal_sections([section]))
            discount_sentences.extend(discount_matches)
        if eco_matches:
            eco_sections.extend(_normalize_signal_sections([section]))
            eco_sentences.extend(eco_matches)
    return {
        "policy_discount_present": bool(discount_sections),
        "policy_discount_sections": _dedupe_signal_sections(discount_sections),
        "policy_discount_sentences": _dedupe_preserve(discount_sentences),
        "eco_policy_present": bool(eco_sections),
        "eco_policy_sections": _dedupe_signal_sections(eco_sections),
        "eco_policy_sentences": _dedupe_preserve(eco_sentences),
    }


def _extract_compliance_proof_signals(sections: list[dict]) -> dict[str, object]:
    proof_sections: list[dict] = []
    proof_sentences: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        matches = _find_matching_sentences(section, [COMPLIANCE_PROOF_RE])
        if matches:
            proof_sections.extend(_normalize_signal_sections([section]))
            proof_sentences.extend(matches)
    return {
        "compliance_proof_present": bool(proof_sections),
        "compliance_proof_sections": _dedupe_signal_sections(proof_sections),
        "compliance_proof_sentences": _dedupe_preserve(proof_sentences),
    }


def _extract_foreign_component_proof_signals(sections: list[dict]) -> dict[str, object]:
    proof_sections: list[dict] = []
    proof_sentences: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        matches = _find_matching_sentences(section, [FOREIGN_COMPONENT_PROOF_RE])
        if matches:
            proof_sections.extend(_normalize_signal_sections([section]))
            proof_sentences.extend(matches)
    return {
        "foreign_component_requirement_present": bool(proof_sections),
        "foreign_component_sections": _dedupe_signal_sections(proof_sections),
        "foreign_component_sentences": _dedupe_preserve(proof_sentences),
    }


def _extract_contract_payment_signals(sections: list[dict]) -> dict[str, object]:
    payment_sections: list[dict] = []
    payment_sentences: list[str] = []
    percentages: list[int] = []
    has_signing_stage = False
    has_delivery_stage = False
    has_acceptance_stage = False
    for section in sections:
        if not isinstance(section, dict):
            continue
        text = "\n".join(
            part for part in (str(section.get("title", "")).strip(), str(section.get("excerpt", "")).strip(), str(section.get("body", "")).strip()) if part
        )
        if not text:
            continue
        section_percentages = [int(match.group(1)) for match in PAYMENT_PERCENT_RE.finditer(text)]
        section_has_payment_signal = bool(section_percentages) and ("支付" in text or "付款" in text)
        if section_has_payment_signal:
            payment_sections.extend(_normalize_signal_sections([section]))
            payment_sentences.extend(_find_matching_sentences(section, [PAYMENT_STAGE_SIGNING_RE, PAYMENT_STAGE_DELIVERY_RE, PAYMENT_STAGE_ACCEPTANCE_RE]))
            if not payment_sentences:
                payment_sentences.extend(_find_match_fragments(section, PAYMENT_PERCENT_RE))
            percentages.extend(section_percentages)
        has_signing_stage = has_signing_stage or bool(PAYMENT_STAGE_SIGNING_RE.search(text))
        has_delivery_stage = has_delivery_stage or bool(PAYMENT_STAGE_DELIVERY_RE.search(text))
        has_acceptance_stage = has_acceptance_stage or bool(PAYMENT_STAGE_ACCEPTANCE_RE.search(text))
    unique_percentages = _dedupe_preserve([str(item) for item in percentages])
    percent_sum = sum(int(item) for item in unique_percentages if str(item).isdigit())
    payment_chain_complete = (
        bool(payment_sections)
        and has_signing_stage
        and has_delivery_stage
        and has_acceptance_stage
        and percent_sum >= 90
        and len(unique_percentages) >= 3
    )
    return {
        "payment_chain_complete": payment_chain_complete,
        "payment_chain_sections": _dedupe_signal_sections(payment_sections),
        "payment_chain_sentences": _dedupe_preserve(payment_sentences),
        "payment_stage_count": int(has_signing_stage) + int(has_delivery_stage) + int(has_acceptance_stage),
        "payment_percentages": [int(item) for item in unique_percentages if str(item).isdigit()],
    }


def _extract_boundary_context_signals(sections: list[dict]) -> dict[str, object]:
    announcement_sections: list[dict] = []
    announcement_sentences: list[str] = []
    electronic_sections: list[dict] = []
    electronic_sentences: list[str] = []
    contract_template_sections: list[dict] = []
    brand_disclosure_sections: list[dict] = []
    parameter_tolerance_sections: list[dict] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title", "")).strip()
        text = "\n".join(
            part for part in (title, str(section.get("excerpt", "")).strip(), str(section.get("body", "")).strip()) if part
        )
        if ANNOUNCEMENT_REFERENCE_RE.search(text):
            announcement_sections.extend(_normalize_signal_sections([section]))
            announcement_sentences.extend(_find_matching_sentences(section, [ANNOUNCEMENT_REFERENCE_RE]))
        if ELECTRONIC_PROCUREMENT_RE.search(text):
            electronic_sections.extend(_normalize_signal_sections([section]))
            electronic_sentences.extend(_find_matching_sentences(section, [ELECTRONIC_PROCUREMENT_RE]))
        if CONTRACT_TEMPLATE_RE.search(text):
            contract_template_sections.extend(_normalize_signal_sections([section]))
        if BRAND_DISCLOSURE_ONLY_RE.search(text):
            brand_disclosure_sections.extend(_normalize_signal_sections([section]))
        if PARAMETER_TOLERANCE_RE.search(text):
            parameter_tolerance_sections.extend(_normalize_signal_sections([section]))
    return {
        "announcement_reference_present": bool(announcement_sections),
        "announcement_reference_sections": _dedupe_signal_sections(announcement_sections),
        "announcement_reference_sentences": _dedupe_preserve(announcement_sentences),
        "electronic_procurement_present": bool(electronic_sections),
        "electronic_procurement_sections": _dedupe_signal_sections(electronic_sections),
        "electronic_procurement_sentences": _dedupe_preserve(electronic_sentences),
        "contract_template_present": bool(contract_template_sections),
        "contract_template_sections": _dedupe_signal_sections(contract_template_sections),
        "brand_disclosure_only_present": bool(brand_disclosure_sections),
        "brand_disclosure_sections": _dedupe_signal_sections(brand_disclosure_sections),
        "parameter_tolerance_present": bool(parameter_tolerance_sections),
        "parameter_tolerance_sections": _dedupe_signal_sections(parameter_tolerance_sections),
    }


def _is_strong_technical_standard_section(section: dict) -> bool:
    title = str(section.get("title", "")).strip()
    module = str(section.get("module", "")).strip()
    return module == "technical" and any(signal in title for signal in TECHNICAL_STANDARD_PRIMARY_TITLE_SIGNALS)


def _should_relax_technical_standard_manual_review(
    definition: TopicDefinition,
    payload: dict,
    bundle: dict,
) -> bool:
    if definition.key != "technical_standard":
        return False
    if not bool(payload.get("need_manual_review", False)):
        return False
    if not _normalize_missing_evidence_items(payload.get("missing_evidence")):
        return False
    primary_ids = {str(item).strip() for item in bundle.get("primary_section_ids", []) if str(item).strip()} if isinstance(bundle, dict) else set()
    sections = [section for section in bundle.get("sections", []) if isinstance(section, dict)] if isinstance(bundle, dict) else []
    primary_sections = [section for section in sections if _section_id(section) in primary_ids] or sections
    if not primary_sections:
        return False
    if not any(_is_strong_technical_standard_section(section) for section in primary_sections):
        return False
    structured_signals = _extract_standard_reference_signals(primary_sections)
    if not structured_signals.get("foreign_standard_refs") and not structured_signals.get("cn_standard_refs"):
        return False
    return True


def _build_risk_point(
    *,
    source_section: dict,
    title: str,
    review_type: str,
    judgments: list[str],
    rectification: list[str],
    severity: str = "中风险",
) -> RiskPoint:
    source_location = (
        f"{source_section.get('title', '未发现')} 第{source_section.get('start_line', '?')}-{source_section.get('end_line', '?')}行"
        if source_section
        else "未发现"
    )
    source_excerpt = str(source_section.get("excerpt", "")).strip() or "未发现"
    return RiskPoint(
        title=title,
        severity=severity,
        review_type=review_type,
        source_location=source_location,
        source_excerpt=source_excerpt,
        risk_judgment=judgments or ["需人工复核"],
        legal_basis=["需人工复核"],
        rectification=rectification or ["未发现"],
    )


def _build_scoring_fallback_risks(sections: list[dict], existing_titles: set[str]) -> list[RiskPoint]:
    combined_text, source_section = _collect_section_text(sections)
    if not combined_text.strip():
        return []
    has_tier_signal = bool(SCORING_TIER_RE.search(combined_text))
    has_subjective_signal = any(signal in combined_text for signal in SCORING_SUBJECTIVE_SIGNALS)
    risks: list[RiskPoint] = []
    if has_tier_signal:
        title = "评分档次缺少量化口径"
        if title not in existing_titles:
            risks.append(
                _build_risk_point(
                    source_section=source_section,
                    title=title,
                    review_type="评分标准不明确",
                    judgments=["评分分档存在“优、良、中、差”或类似档次，但缺少与各档对应的量化判定标准。"],
                    rectification=["补充各评分档次对应的量化标准，并压缩主观裁量空间。"],
                )
            )
    if has_subjective_signal:
        title = "主观分值裁量空间过大"
        if title not in existing_titles:
            risks.append(
                _build_risk_point(
                    source_section=source_section,
                    title=title,
                    review_type="评分标准不明确",
                    judgments=["条款包含“综合打分”“酌情计分”等表述，评委自由裁量空间较大。"],
                    rectification=["删除纯主观评分表述，改为可操作的量化评分标准。"],
                )
            )
    if SCORING_RELEVANCE_RE.search(combined_text):
        title = "评分依据与采购标的关联性不足"
        if title not in existing_titles:
            risks.append(
                _build_risk_point(
                    source_section=source_section,
                    title=title,
                    review_type="评分因素相关性",
                    judgments=["评分因素聚焦排版、封面等形式内容，与采购标的或履约能力关联性不足。"],
                    rectification=["删除与采购标的和履约能力无直接关系的评分因素。"],
                )
            )
    if SCORING_INCONSISTENT_RE.search(combined_text):
        title = "评分口径前后不一致"
        if title not in existing_titles:
            risks.append(
                _build_risk_point(
                    source_section=source_section,
                    title=title,
                    review_type="评分标准不明确",
                    judgments=["同一评分项的分值或评分口径前后不一致，可能影响评审可操作性。"],
                    rectification=["统一评分项分值及评分口径表述。"],
                )
            )
    return risks


def _build_topic_rule_fallback_risks(
    definition: TopicDefinition,
    sections: list[dict],
    existing_titles: set[str],
) -> list[RiskPoint]:
    combined_text, source_section = _collect_section_text(sections)
    if not combined_text.strip():
        return []

    risks: list[RiskPoint] = []
    if definition.key == "scoring":
        return _build_scoring_fallback_risks(sections, existing_titles)

    if definition.key == "qualification":
        if QUALIFICATION_LOCAL_SERVICE_RE.search(combined_text):
            title = "设立常设服务机构的资格限制"
            if title not in existing_titles:
                risks.append(
                    _build_risk_point(
                        source_section=source_section,
                        title=title,
                        review_type="资格条件",
                        judgments=["资格条件要求供应商在本地设立常设服务机构，可能形成地域性准入限制。"],
                        rectification=["删除本地常设机构准入门槛，改为履约阶段服务响应要求。"],
                        severity="高风险",
                    )
                )
        if QUALIFICATION_PERFORMANCE_RE.search(combined_text) and ("资格" in combined_text or "须具备" in combined_text):
            title = "业绩与人员要求被设置为资格门槛"
            if title not in existing_titles:
                risks.append(
                    _build_risk_point(
                        source_section=source_section,
                        title=title,
                        review_type="资格条件/业绩人员",
                        judgments=["业绩或人员条件直接并入资格门槛，需审查是否与主体准入及履约直接相关。"],
                        rectification=["将与主体准入无直接关系的业绩、人员条件从资格门槛中剥离。"],
                    )
                )

    if definition.key == "technical_standard":
        if TECHNICAL_STANDARD_OBSOLETE_RE.search(combined_text):
            title = "引用已废止标准"
            if title not in existing_titles:
                risks.append(
                    _build_risk_point(
                        source_section=source_section,
                        title=title,
                        review_type="技术标准",
                        judgments=["技术条款引用的标准版本较旧，存在已废止或被替代的风险。"],
                        rectification=["核对标准现行有效版本，并统一更新标准引用。"],
                    )
                )
        if TECHNICAL_STANDARD_MISMATCH_RE.search(combined_text):
            title = "标准名称与编号不一致"
            if title not in existing_titles:
                risks.append(
                    _build_risk_point(
                        source_section=source_section,
                        title=title,
                        review_type="技术标准",
                        judgments=["标准名称、编号或引用方式可能存在不一致，需核对标准全称与适用范围。"],
                        rectification=["统一标准名称、编号和适用对象的表述。"],
                    )
                )
        if TECHNICAL_STANDARD_METHOD_MISMATCH_RE.search(combined_text):
            title = "检测方法标准与采购要求不匹配"
            if title not in existing_titles:
                risks.append(
                    _build_risk_point(
                        source_section=source_section,
                        title=title,
                        review_type="技术标准",
                        judgments=["检测方法或试验方法与采购标的、交付要求之间匹配关系不足，可能导致验收依据偏离采购需求。"],
                        rectification=["核对检测方法标准与采购标的、验收指标的一致性，删除与采购要求不匹配的检测依据。"],
                    )
                )

    if definition.key == "contract_payment":
        if CONTRACT_PAYMENT_FISCAL_RE.search(combined_text):
            title = "付款节点与财政资金到位挂钩"
            if title not in existing_titles:
                risks.append(
                    _build_risk_point(
                        source_section=source_section,
                        title=title,
                        review_type="商务条款失衡",
                        judgments=["付款节点与财政资金到位挂钩，供应商回款时间存在较大不确定性。"],
                        rectification=["删除以财政资金到位作为付款前提的表述，改为明确付款时间节点。"],
                        severity="高风险",
                    )
                )
        if CONTRACT_PAYMENT_ACCEPTANCE_RE.search(combined_text):
            title = "付款安排以验收裁量为前置条件"
            if title not in existing_titles:
                risks.append(
                    _build_risk_point(
                        source_section=source_section,
                        title=title,
                        review_type="付款条款/验收联动",
                        judgments=["付款触发条件与验收裁量高度耦合，可能放大采购人单方控制空间。"],
                        rectification=["明确验收标准和支付触发条件，避免付款完全受验收裁量控制。"],
                    )
                )
        if CONTRACT_PAYMENT_DELAY_RE.search(combined_text):
            title = "付款节点明显偏后"
            if title not in existing_titles:
                risks.append(
                    _build_risk_point(
                        source_section=source_section,
                        title=title,
                        review_type="付款条款",
                        judgments=["付款时间设置偏后，可能对供应商形成较大资金占压。"],
                        rectification=["结合履约进度优化付款比例和付款时点。"],
                    )
                )
    return risks


def _normalize_missing_evidence_items(value: object) -> list[str]:
    items = _to_list(value, "未发现")
    return [item for item in items if item.strip() and item.strip() != "未发现"]


def _should_tighten_manual_review(payload: dict, risk_points: list[RiskPoint]) -> bool:
    if not bool(payload.get("need_manual_review", False)):
        return False
    if not risk_points:
        return False
    if _normalize_missing_evidence_items(payload.get("missing_evidence")):
        return False
    if any(risk.severity == "需人工复核" for risk in risk_points):
        return False
    return True


def _build_topic_failure_reasons(
    *,
    selected_sections: list[dict],
    missing_evidence: list[str],
    need_manual_review: bool,
    degraded: bool,
    recovered_reason_codes: list[str] | None = None,
) -> list[str]:
    reasons: list[str] = []
    if not selected_sections:
        reasons.append("topic_not_triggered")
    if missing_evidence:
        reasons.append("missing_evidence")
    if degraded or (need_manual_review and missing_evidence):
        reasons.append("degraded_to_manual_review")
    if need_manual_review and selected_sections and missing_evidence:
        reasons.append("risk_degraded_to_manual_review")
    recovered_reason_codes = [str(item).strip() for item in (recovered_reason_codes or []) if str(item).strip()]
    if recovered_reason_codes:
        reasons.append("risk_not_extracted")
        reasons.extend(recovered_reason_codes)
    return list(dict.fromkeys(reasons))


def _snippet_from_section(section: dict) -> str:
    lines = [
        f"标题：{section.get('title', '未命名章节')}",
        f"位置：第 {section.get('start_line', '?')} - {section.get('end_line', '?')} 行",
        f"识别模块：{section.get('module', '待识别')}",
        f"关键词：{', '.join(section.get('keywords', [])) or '未发现'}",
        "正文片段：",
        section.get("excerpt", "").strip() or "未发现",
    ]
    return "\n".join(lines)


def _get_evidence_bundle(evidence: V2StageArtifact, topic_key: str) -> dict:
    if not evidence.metadata:
        return {}
    bundles = evidence.metadata.get("topic_evidence_bundles", {}) or {}
    bundle = bundles.get(topic_key, {})
    return bundle if isinstance(bundle, dict) else {}


def _get_topic_coverage(evidence: V2StageArtifact, topic_key: str) -> dict:
    if not evidence.metadata:
        return {}
    coverages = evidence.metadata.get("topic_coverages", {}) or {}
    coverage = coverages.get(topic_key, {})
    return coverage if isinstance(coverage, dict) else {}


def _build_topic_prompt(document_name: str, topic: TopicDefinition, bundle: dict, coverage: dict) -> str:
    sections = bundle.get("sections", []) if isinstance(bundle, dict) else []
    evidence_blocks = "\n\n".join(
        [f"[证据{index}]\n{_snippet_from_section(section)}" for index, section in enumerate(sections, start=1)]
    ) or "未发现相关证据片段。"
    missing_hints = bundle.get("missing_hints", []) if isinstance(bundle, dict) else []
    recall_query = str(bundle.get("recall_query", "")).strip() if isinstance(bundle, dict) else ""
    boundary = bundle.get("metadata", {}).get("boundary", {}) if isinstance(bundle, dict) else {}
    covered_modules = coverage.get("covered_modules", []) if isinstance(coverage, dict) else []
    missing_modules = coverage.get("missing_modules", []) if isinstance(coverage, dict) else []

    schema = {
        "summary": "专题结论摘要",
        "need_manual_review": False,
        "coverage_note": "本专题召回范围说明",
        "missing_evidence": ["如存在关键证据缺口，在这里列出"],
        "risk_points": [
            {
                "title": "问题标题",
                "severity": "高风险/中风险/低风险/需人工复核",
                "review_type": "审查类型",
                "source_location": "原文位置",
                "source_excerpt": "原文摘录",
                "risk_judgment": ["分点说明1", "分点说明2"],
                "legal_basis": ["法律政策依据1"],
                "rectification": ["整改建议1"],
            }
        ],
    }

    return (
        f"{topic.prompt.strip()}\n\n"
        "请仅依据我提供的证据片段进行审查，不要凭空补造原文。"
        " 如果证据不足，可以保守判断并标记 need_manual_review=true。"
        " 输出必须是 JSON 对象，不要输出 Markdown，不要解释。\n\n"
        f"文档名称：{document_name}\n"
        f"专题名称：{topic.label}\n"
        f"专题键：{topic.key}\n"
        f"专题优先级：{topic.priority}\n\n"
        f"专题边界-纳入范围：{'；'.join(boundary.get('in_scope', [])) or '未提供'}\n"
        f"专题边界-排除范围：{'；'.join(boundary.get('out_of_scope', [])) or '未提供'}\n"
        f"主归属规则：{boundary.get('ownership_rule', '未提供')}\n"
        f"模块覆盖：{', '.join(covered_modules) or '未发现'}\n"
        f"缺失模块：{', '.join(missing_modules) or '未发现'}\n"
        f"证据召回说明：{recall_query or '未提供'}\n"
        f"召回缺口提示：{'；'.join(missing_hints) if missing_hints else '未发现明显缺口。'}\n\n"
        "JSON 结构示例：\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        "证据片段如下：\n"
        f"{evidence_blocks}\n"
    )


def _build_default_coverage_note(sections: list[dict], coverage: dict) -> str:
    covered_modules = coverage.get("covered_modules", []) if isinstance(coverage, dict) else []
    missing_hints = coverage.get("missing_hints", []) if isinstance(coverage, dict) else []
    return (
        f"召回 {len(sections)} 个证据片段，覆盖模块：{', '.join(covered_modules) or '未发现'}。"
        f"{' 缺口：' + '；'.join(missing_hints) if missing_hints else ''}"
    )


def _build_empty_topic_artifact(
    definition: TopicDefinition,
    bundle: dict,
    coverage: dict,
    topic_mode: str,
    execution_plan: dict,
    summary: str | None = None,
    missing_evidence: list[str] | None = None,
    raw_output: str = "",
    error_type: str = "missing_evidence",
) -> TopicReviewArtifact:
    sections = bundle.get("sections", []) if isinstance(bundle, dict) else []
    structured_signals = _build_structured_signals(definition, sections)
    missing_items = list(missing_evidence or (coverage.get("missing_hints", []) if isinstance(coverage, dict) else []))
    selected_sections = [
        {
            "title": section.get("title", ""),
            "start_line": section.get("start_line"),
            "end_line": section.get("end_line"),
            "module": section.get("module", ""),
        }
        for section in sections
        if isinstance(section, dict)
    ]
    failure_reasons = _build_topic_failure_reasons(
        selected_sections=selected_sections,
        missing_evidence=[item for item in missing_items if item and item != "未发现"],
        need_manual_review=True,
        degraded=True,
        recovered_reason_codes=[],
    )
    return TopicReviewArtifact(
        topic=definition.key,
        summary=summary or f"{definition.label}专题未召回到足够证据，需人工复核。",
        need_manual_review=True,
        coverage_note=_build_default_coverage_note(sections, coverage),
        raw_output=raw_output,
        metadata={
            "topic_label": definition.label,
            "topic_priority": definition.priority,
            "topic_mode": topic_mode,
            "topic_execution_plan": execution_plan,
            "selected_sections": selected_sections,
            "missing_evidence": missing_items,
            "failure_reasons": failure_reasons,
            "failure_reason_labels": [TOPIC_FAILURE_REASON_LABELS.get(reason, reason) for reason in failure_reasons],
            "evidence_bundle": bundle,
            "topic_coverage": coverage,
            "degraded": True,
            "degrade_reason": error_type,
            "structured_signals": structured_signals,
        },
    )


def _postprocess_topic_payload(
    definition: TopicDefinition,
    payload: dict,
    bundle: dict,
) -> tuple[dict, list[RiskPoint], list[str]]:
    risk_points: list[RiskPoint] = []
    failure_reasons: list[str] = []
    for item in payload.get("risk_points", []):
        if isinstance(item, dict):
            risk_points.append(_to_risk_point(item, definition.label))

    sections = bundle.get("sections", []) if isinstance(bundle, dict) else []
    section_modules = {
        str(section.get("module", "")).strip()
        for section in sections
        if isinstance(section, dict) and str(section.get("module", "")).strip()
    }
    boundary_modules = set(definition.boundary.primary_modules or definition.modules) | set(definition.boundary.secondary_modules)
    has_shared_section_signal = any(
        sum(
            1
            for module, score in dict(section.get("module_scores", {}) or {}).items()
            if module in boundary_modules and int(score or 0) >= 3
        )
        >= 2
        for section in sections
        if isinstance(section, dict)
    )
    existing_titles = {risk.title for risk in risk_points if risk.title.strip()}
    existing_risk_count = len(existing_titles)
    normalized_missing_evidence = _normalize_missing_evidence_items(payload.get("missing_evidence"))
    fallback_risks = (
        _build_topic_rule_fallback_risks(definition, sections, existing_titles)
        if not normalized_missing_evidence
        else []
    )
    if fallback_risks:
        risk_points.extend(fallback_risks)
        if existing_risk_count > 0:
            failure_reasons.append("topic_triggered_but_partial_miss")
        else:
            failure_reasons.append("evidence_enough_but_risk_missed")
        if len(section_modules) >= 2 or len(sections) >= 2 or has_shared_section_signal:
            failure_reasons.append("cross_topic_shared_but_single_topic_hit")
        summary = str(payload.get("summary", "")).strip()
        payload["summary"] = summary or f"{definition.label}专题完成，并根据已召回证据补出明确风险。"
        payload["coverage_note"] = str(payload.get("coverage_note", "")).strip() or "已覆盖专题关键条款。"
        payload["need_manual_review"] = False
        payload["missing_evidence"] = ["未发现"]

    if _should_tighten_manual_review(payload, risk_points):
        payload["need_manual_review"] = False
        payload["missing_evidence"] = ["未发现"]
    if _should_relax_technical_standard_manual_review(definition, payload, bundle):
        payload["need_manual_review"] = False
        payload["missing_evidence"] = ["未发现"]
        payload["coverage_note"] = str(payload.get("coverage_note", "")).strip() or "已覆盖核心技术标准条款。"

    return payload, risk_points, failure_reasons


def _build_structured_signals(definition: TopicDefinition, sections: list[dict]) -> dict[str, object]:
    signals: dict[str, object] = {}
    if definition.key in {"policy", "qualification", "procedure"}:
        signals.update(_extract_import_policy_signals(sections))
        signals.update(_extract_policy_execution_signals(sections))
        signals.update(_extract_boundary_context_signals(sections))
    if definition.key in {"technical_standard", "qualification", "acceptance", "policy"}:
        signals.update(_extract_compliance_proof_signals(sections))
        signals.update(_extract_foreign_component_proof_signals(sections))
    if definition.key == "qualification":
        signals.update(_extract_cancelled_or_non_mandatory_qualification_signals(sections))
        signals.update(_extract_original_or_paper_certificate_submission_signals(sections))
        signals.update(_extract_supplier_identity_or_region_gate_signals(sections))
    if definition.key == "scoring":
        signals.update(_extract_star_rule_signals(sections))
        signals.update(_extract_acceptance_plan_scoring_signals(sections))
        signals.update(_extract_payment_terms_scoring_signals(sections))
        signals.update(_extract_gifts_or_unrelated_goods_scoring_signals(sections))
        signals.update(_extract_specific_cert_or_supplier_scoring_signals(sections))
        signals.update(_extract_cancelled_or_non_mandatory_scoring_credential_signals(sections))
        signals.update(_extract_boundary_context_signals(sections))
    if definition.key == "technical_standard":
        signals.update(_extract_standard_reference_signals(sections))
        signals.update(_extract_boundary_context_signals(sections))
    if definition.key == "acceptance":
        signals.update(_extract_acceptance_testing_cost_signals(sections))
        signals.update(_extract_boundary_context_signals(sections))
    if definition.key == "contract_payment":
        signals.update(_extract_contract_payment_signals(sections))
        signals.update(_extract_boundary_context_signals(sections))
    return signals


def _run_single_topic(
    definition: TopicDefinition,
    document_name: str,
    evidence: V2StageArtifact,
    settings: ReviewSettings,
    topic_mode: str,
    execution_plan: dict,
    stream_callback: Callable[[str], None] | None = None,
) -> TopicReviewArtifact:
    bundle = _get_evidence_bundle(evidence, definition.key)
    coverage = _get_topic_coverage(evidence, definition.key)
    sections = bundle.get("sections", []) if isinstance(bundle, dict) else []
    coverage_note = _build_default_coverage_note(sections, coverage)
    if not sections:
        return _build_empty_topic_artifact(definition, bundle, coverage, topic_mode, execution_plan)

    prompt = _build_topic_prompt(document_name, definition, bundle, coverage)
    prompt = maybe_disable_qwen_thinking(prompt, settings.model)
    if stream_callback:
        stream_callback(f"\n\n[第三层专题深审·{definition.label}]\n")
    try:
        response = (
            call_chat_completion_stream(
                base_url=settings.base_url,
                model=settings.model,
                api_key=settings.api_key,
                system_prompt="你是政府采购招标文件专题深审助手，只输出合法 JSON。",
                user_prompt=prompt,
                temperature=settings.temperature,
                max_tokens=min(settings.max_tokens, int(execution_plan.get("per_topic_max_tokens", 3200) or 3200)),
                timeout=min(settings.timeout, int(execution_plan.get("per_topic_timeout", settings.timeout) or settings.timeout)),
                on_text=stream_callback,
            )
            if stream_callback
            else call_chat_completion(
                base_url=settings.base_url,
                model=settings.model,
                api_key=settings.api_key,
                system_prompt="你是政府采购招标文件专题深审助手，只输出合法 JSON。",
                user_prompt=prompt,
                temperature=settings.temperature,
                max_tokens=min(settings.max_tokens, int(execution_plan.get("per_topic_max_tokens", 3200) or 3200)),
                timeout=min(settings.timeout, int(execution_plan.get("per_topic_timeout", settings.timeout) or settings.timeout)),
            )
        )
    except Exception as exc:
        if not execution_plan.get("allow_degrade_on_error", True):
            raise
        return _build_empty_topic_artifact(
            definition,
            bundle,
            coverage,
            topic_mode,
            execution_plan,
            summary=f"{definition.label}专题调用失败，已自动降级为人工复核。",
            missing_evidence=[f"专题调用失败：{exc}"],
            raw_output="",
            error_type="topic_call_failed",
        )
    try:
        raw_output = extract_response_text(response) or ""
    except Exception as exc:
        if not execution_plan.get("allow_degrade_on_error", True):
            raise
        return _build_empty_topic_artifact(
            definition,
            bundle,
            coverage,
            topic_mode,
            execution_plan,
            summary=f"{definition.label}专题响应解析失败，已自动降级为人工复核。",
            missing_evidence=[f"专题响应解析失败：{exc}"],
            raw_output="",
            error_type="topic_response_parse_failed",
        )

    try:
        payload = _parse_topic_json(raw_output)
        payload, risk_points, postprocess_failure_reasons = _postprocess_topic_payload(definition, payload, bundle)
    except Exception as exc:
        if not execution_plan.get("allow_degrade_on_error", True):
            raise
        return _build_empty_topic_artifact(
            definition,
            bundle,
            coverage,
            topic_mode,
            execution_plan,
            summary=f"{definition.label}专题后处理失败，已自动降级为人工复核。",
            missing_evidence=[f"专题后处理失败：{exc}"],
            raw_output=raw_output,
            error_type="topic_postprocess_failed",
        )

    missing_evidence = _to_list(payload.get("missing_evidence"), "未发现")
    normalized_missing_evidence = _normalize_missing_evidence_items(payload.get("missing_evidence"))
    selected_sections = [
        {
            "title": section.get("title", ""),
            "start_line": section.get("start_line"),
            "end_line": section.get("end_line"),
            "module": section.get("module", ""),
        }
        for section in sections
    ]
    signal_sections = sections
    if definition.key == "technical_standard":
        primary_ids = {
            str(item).strip() for item in bundle.get("primary_section_ids", []) if str(item).strip()
        } if isinstance(bundle, dict) else set()
        if primary_ids:
            primary_sections = [
                section for section in sections if isinstance(section, dict) and _section_id(section) in primary_ids
            ]
            if primary_sections:
                supplemental_sections = []
                for section in sections:
                    if not isinstance(section, dict):
                        continue
                    if _section_id(section) in primary_ids:
                        continue
                    text = "\n".join(
                        part
                        for part in (
                            str(section.get("title", "")).strip(),
                            str(section.get("excerpt", "")).strip(),
                            str(section.get("body", "")).strip(),
                        )
                        if part
                    )
                    if FOREIGN_STANDARD_REF_RE.search(text) or CN_STANDARD_REF_RE.search(text) or GB_NON_T_REF_RE.search(text):
                        supplemental_sections.append(section)
                signal_sections = primary_sections + supplemental_sections[:2]
    structured_signals = _build_structured_signals(definition, signal_sections)
    failure_reasons = _build_topic_failure_reasons(
        selected_sections=selected_sections,
        missing_evidence=normalized_missing_evidence,
        need_manual_review=bool(payload.get("need_manual_review", False)),
        degraded=False,
        recovered_reason_codes=postprocess_failure_reasons,
    )
    if (
        definition.key == "technical_standard"
        and structured_signals.get("foreign_standard_refs")
        and not structured_signals.get("has_equivalent_standard_clause", False)
    ):
        failure_reasons = list(dict.fromkeys(failure_reasons + ["foreign_standard_conflict"]))
    return TopicReviewArtifact(
        topic=definition.key,
        summary=str(payload.get("summary", "")).strip() or f"{definition.label}专题已完成。",
        risk_points=risk_points,
        need_manual_review=bool(payload.get("need_manual_review", False)),
        coverage_note=str(payload.get("coverage_note", "")).strip() or coverage_note,
        raw_output=raw_output,
        metadata={
            "topic_label": definition.label,
            "topic_priority": definition.priority,
            "topic_mode": topic_mode,
            "topic_execution_plan": execution_plan,
            "selected_sections": selected_sections,
            "missing_evidence": missing_evidence,
            "failure_reasons": failure_reasons,
            "failure_reason_labels": [TOPIC_FAILURE_REASON_LABELS.get(reason, reason) for reason in failure_reasons],
            "evidence_bundle": bundle,
            "topic_coverage": coverage,
            "structured_signals": structured_signals,
        },
    )


def run_topic_reviews(
    document_name: str,
    evidence: V2StageArtifact,
    settings: ReviewSettings,
    topic_mode: str = "default",
    topic_keys: tuple[str, ...] | list[str] | None = None,
    stream_callback: Callable[[str], None] | None = None,
) -> list[TopicReviewArtifact]:
    plan = resolve_topic_execution_plan(topic_mode=topic_mode, topic_keys=topic_keys)
    definitions = resolve_topic_definitions(topic_mode=topic_mode, topic_keys=topic_keys)
    execution_plan = {
        "mode": plan.mode,
        "requested_keys": list(plan.requested_keys),
        "selected_keys": list(plan.selected_keys),
        "skipped_keys": list(plan.skipped_keys),
        "max_topic_calls": plan.max_topic_calls,
        "per_topic_timeout": plan.per_topic_timeout,
        "per_topic_max_tokens": plan.per_topic_max_tokens,
        "allow_degrade_on_error": plan.allow_degrade_on_error,
        "reason": plan.reason,
    }
    return [
        _run_single_topic(
            definition=definition,
            document_name=document_name,
            evidence=evidence,
            settings=settings,
            topic_mode=topic_mode,
            execution_plan=execution_plan,
            stream_callback=stream_callback,
        )
        for definition in definitions
    ]
