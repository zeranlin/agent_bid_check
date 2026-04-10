from __future__ import annotations

from pathlib import Path

from app.common.schemas import RiskPoint
from app.pipelines.v2.compare import compare_review_artifacts
from app.pipelines.v2.evidence import build_evidence_map
from app.pipelines.v2.evidence_layer.classifier import (
    infer_business_domain,
    infer_clause_role,
    infer_evidence_strength,
    infer_hard_evidence,
    infer_source_kind,
)
from app.pipelines.v2.evidence_layer.pipeline import build_evidence_layer
from app.pipelines.v2.schemas import TopicReviewArtifact, V2StageArtifact
from app.pipelines.v2.structure import build_structure_map
from app.pipelines.v2.topic_review import _get_evidence_bundle, run_topic_reviews
from app.config import ReviewSettings


def _sample_structure_and_evidence() -> tuple[V2StageArtifact, V2StageArtifact]:
    text = """
第一章 招标公告
投标人资格要求如下。

第二章 评分办法
综合评分法，技术评分40分，商务评分20分。

第三章 技术要求
场地材料应符合 GB 36246-2018 标准，需提供检测报告和样品。

第四章 商务条款
验收合格后 15 个工作日内付款。
""".strip()
    structure = build_structure_map(
        input_path=Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
        use_llm=False,
    )
    evidence_map = build_evidence_map("sample.docx", structure, topic_mode="mature")
    return structure, evidence_map


def test_build_evidence_layer_constructs_unified_evidence_objects() -> None:
    structure, evidence_map = _sample_structure_and_evidence()

    evidence_layer = build_evidence_layer("sample.docx", structure, evidence_map)

    assert evidence_layer.document_name == "sample.docx"
    assert evidence_layer.evidences
    first = evidence_layer.evidences[0]
    assert first.evidence_id
    assert first.excerpt
    assert first.location
    assert first.source_kind
    assert "source_kind_trace" in first.metadata
    assert first.business_domain
    assert "business_domain_trace" in first.metadata
    assert first.clause_role
    assert "clause_role_trace" in first.metadata
    assert first.evidence_strength
    assert "evidence_strength_trace" in first.metadata
    assert isinstance(first.hard_evidence, bool)
    assert "hard_evidence_trace" in first.metadata
    assert isinstance(first.topic_hints, list)
    assert isinstance(first.metadata, dict)
    assert evidence_layer.metadata["evidence_count"] == len(evidence_layer.evidences)
    assert "scoring" in evidence_layer.topic_inputs


def test_topic_review_can_consume_evidence_layer_input() -> None:
    structure, evidence_map = _sample_structure_and_evidence()
    evidence_layer = build_evidence_layer("sample.docx", structure, evidence_map)

    bundle = _get_evidence_bundle(evidence_layer, "technical_standard")

    assert bundle["sections"]
    assert bundle["evidence_ids"]
    assert all(section.get("evidence_id") for section in bundle["sections"])


def test_compare_candidates_keep_evidence_trace_ids() -> None:
    _, evidence_map = _sample_structure_and_evidence()
    evidence_layer = build_evidence_layer("sample.docx", V2StageArtifact(name="structure", metadata={}), evidence_map)
    scoring_bundle = _get_evidence_bundle(evidence_layer, "scoring")

    topic = TopicReviewArtifact(
        topic="scoring",
        summary="scoring",
        risk_points=[
            RiskPoint(
                title="将项目验收方案纳入评审因素，违反评审规则合规性要求",
                severity="高风险",
                review_type="评分办法",
                source_location="第二章 评分办法",
                source_excerpt="综合评分法，技术评分40分，商务评分20分。",
                risk_judgment=["验收方案不得纳入评审因素。"],
                legal_basis=["评审规则合规性要求。"],
                rectification=["删除相关评分项。"],
            )
        ],
        metadata={
            "selected_sections": scoring_bundle["sections"],
            "selected_evidence_ids": scoring_bundle["evidence_ids"],
            "evidence_bundle": scoring_bundle,
            "topic_coverage": evidence_layer.metadata["topic_coverages"]["scoring"],
        },
    )

    artifact = compare_review_artifacts(
        "sample.docx",
        V2StageArtifact(name="baseline", content="# 招标文件合规审查结果"),
        [topic],
    )

    assert artifact.clusters
    assert artifact.clusters[0].evidence_ids
    assert set(artifact.clusters[0].evidence_ids).issubset(set(scoring_bundle["evidence_ids"]))


def test_run_topic_reviews_accepts_evidence_layer_artifact(monkeypatch) -> None:
    structure, evidence_map = _sample_structure_and_evidence()
    evidence_layer = build_evidence_layer("sample.docx", structure, evidence_map)
    captured: dict[str, object] = {}

    def fake_run_single_topic(**kwargs):
        captured["evidence"] = kwargs["evidence"]
        return TopicReviewArtifact(topic=kwargs["definition"].key, summary="ok")

    monkeypatch.setattr("app.pipelines.v2.topic_review._run_single_topic", fake_run_single_topic)

    topics = run_topic_reviews(
        document_name="sample.docx",
        evidence=evidence_layer,
        settings=ReviewSettings(),
        topic_mode="slim",
    )

    assert topics
    assert captured["evidence"] is evidence_layer


def test_infer_source_kind_recognizes_body_clause() -> None:
    source_kind = infer_source_kind(
        {
            "title": "技术要求",
            "source": "rule_split",
            "body": "设备应符合国家标准要求，完成安装调试。",
            "excerpt": "设备应符合国家标准要求，完成安装调试。",
            "location": "技术要求（第 12-18 行）",
        }
    )

    assert source_kind == "body_clause"


def test_infer_source_kind_recognizes_template_clause() -> None:
    source_kind = infer_source_kind(
        {
            "title": "制造商发电机组资质证书（格式自拟）",
            "source": "rule_split",
            "body": "投标人自行按照本项目评审项内容提供资料。",
            "excerpt": "制造商发电机组资质证书（格式自拟）",
        }
    )

    assert source_kind == "template_clause"


def test_infer_source_kind_recognizes_placeholder_clause_separately() -> None:
    source_kind = infer_source_kind(
        {
            "title": "履约验收时间：供应商提出验收申请之日起_______日内组织验收",
            "source": "rule_split",
            "body": "计划于何时验收/供应商提出验收申请之日起_______日内组织验收。",
            "excerpt": "供应商提出验收申请之日起_______日内组织验收",
        }
    )

    assert source_kind == "placeholder_clause"


def test_infer_source_kind_recognizes_contract_template_separately() -> None:
    source_kind = infer_source_kind(
        {
            "title": "6.合同履行",
            "source": "rule_split",
            "body": "甲乙双方应当按照【政府采购合同专用条款】约定顺序履行合同义务。",
            "excerpt": "甲乙双方应当按照【政府采购合同专用条款】约定顺序履行合同义务。",
        }
    )

    assert source_kind == "contract_template"


def test_infer_source_kind_recognizes_attachment_clause() -> None:
    source_kind = infer_source_kind(
        {
            "title": "资格承诺函",
            "source": "rule_split",
            "body": "采用资格承诺制的供应商，应当根据格式文件要求提供资格承诺函。",
            "excerpt": "采用资格承诺制的供应商，应当根据格式文件要求提供资格承诺函。",
        }
    )

    assert source_kind == "attachment_clause"


def test_infer_source_kind_recognizes_reminder_clause_with_context() -> None:
    source_kind = infer_source_kind(
        {
            "title": "招标文件的澄清和修改",
            "source": "rule_split",
            "body": "投标人有义务在招标期间浏览公告网站，如有需进一步核实的内容应及时关注补充通知。",
            "excerpt": "投标人有义务在招标期间浏览公告网站，如有需进一步核实的内容应及时关注补充通知。",
        }
    )

    assert source_kind == "reminder_clause"


def test_infer_source_kind_recognizes_form_clause() -> None:
    source_kind = infer_source_kind(
        {
            "title": "项目报价表",
            "source": "rule_split",
            "body": "序号 货物名称 品牌 型号（规格） 原产地 制造商名称 单位 数量 单价 合价",
            "excerpt": "项目报价表 序号 货物名称 品牌 型号（规格） 原产地 制造商名称 单位 数量 单价 合价",
        }
    )

    assert source_kind == "form_clause"


def test_infer_source_kind_recognizes_sample_clause() -> None:
    source_kind = infer_source_kind(
        {
            "title": "样品要求",
            "source": "rule_split",
            "body": "样品为投标文件有效组成部分，未提供样品按无效投标处理。",
            "excerpt": "样品为投标文件有效组成部分，未提供样品按无效投标处理。",
        }
    )

    assert source_kind == "sample_clause"


def test_build_evidence_layer_writes_source_kind_trace_into_topic_sections() -> None:
    structure, evidence_map = _sample_structure_and_evidence()
    evidence_layer = build_evidence_layer("sample.docx", structure, evidence_map)

    scoring_sections = evidence_layer.topic_inputs["scoring"].sections

    assert scoring_sections
    assert all("source_kind" in section for section in scoring_sections)
    assert all("source_kind_trace" in section for section in scoring_sections)


def test_infer_business_domain_recognizes_qualification() -> None:
    business_domain = infer_business_domain(
        {
            "title": "投标人资格要求",
            "source": "rule_split",
            "module": "procedure",
            "body": "投标人须具备独立承担民事责任能力，资格审查不通过的投标无效。",
            "excerpt": "投标人须具备独立承担民事责任能力，资格审查不通过的投标无效。",
        }
    )

    assert business_domain == "qualification"


def test_infer_business_domain_recognizes_scoring() -> None:
    business_domain = infer_business_domain(
        {
            "title": "评分标准",
            "source": "rule_split",
            "module": "scoring",
            "body": "每提供1项类似项目业绩得5分，最高得10分。",
            "excerpt": "每提供1项类似项目业绩得5分，最高得10分。",
        }
    )

    assert business_domain == "scoring"


def test_infer_business_domain_recognizes_technical() -> None:
    business_domain = infer_business_domain(
        {
            "title": "技术参数",
            "source": "rule_split",
            "module": "technical",
            "body": "额定输出功率不小于200kW，连续运行时间不少于8小时。",
            "excerpt": "额定输出功率不小于200kW，连续运行时间不少于8小时。",
        }
    )

    assert business_domain == "technical"


def test_infer_business_domain_recognizes_technical_standard_separately() -> None:
    business_domain = infer_business_domain(
        {
            "title": "技术要求",
            "source": "rule_split",
            "module": "technical",
            "body": "设备应符合 GB/T 2820.5-2009、IEC 60034 等标准要求。",
            "excerpt": "设备应符合 GB/T 2820.5-2009、IEC 60034 等标准要求。",
        }
    )

    assert business_domain == "technical_standard"


def test_infer_business_domain_recognizes_commercial_separately_from_acceptance() -> None:
    business_domain = infer_business_domain(
        {
            "title": "付款方式",
            "source": "rule_split",
            "module": "contract",
            "body": "项目终验完成后，采购人收到发票后15个工作日内支付合同总价的95%。",
            "excerpt": "项目终验完成后，采购人收到发票后15个工作日内支付合同总价的95%。",
        }
    )

    assert business_domain == "commercial"


def test_infer_business_domain_recognizes_acceptance_separately_from_sample() -> None:
    business_domain = infer_business_domain(
        {
            "title": "设备验收",
            "source": "rule_split",
            "module": "acceptance",
            "body": "按招标文件、投标文件及国家相关规范组织验收。",
            "excerpt": "按招标文件、投标文件及国家相关规范组织验收。",
        }
    )

    assert business_domain == "acceptance"


def test_infer_business_domain_recognizes_sample_separately_from_acceptance() -> None:
    business_domain = infer_business_domain(
        {
            "title": "样品要求",
            "source": "rule_split",
            "module": "technical",
            "body": "样品为投标文件有效组成部分，未提供样品按无效投标处理。",
            "excerpt": "样品为投标文件有效组成部分，未提供样品按无效投标处理。",
        }
    )

    assert business_domain == "sample"


def test_infer_business_domain_recognizes_performance_staff_in_scoring_context() -> None:
    business_domain = infer_business_domain(
        {
            "title": "评分内容",
            "source": "rule_split",
            "module": "scoring",
            "body": "项目负责人具有高级工程师职称得5分，近三年类似项目业绩每项得2分。",
            "excerpt": "项目负责人具有高级工程师职称得5分，近三年类似项目业绩每项得2分。",
        }
    )

    assert business_domain == "performance_staff"


def test_build_evidence_layer_writes_business_domain_trace_into_topic_sections() -> None:
    structure, evidence_map = _sample_structure_and_evidence()
    evidence_layer = build_evidence_layer("sample.docx", structure, evidence_map)

    technical_sections = evidence_layer.topic_inputs["technical_standard"].sections

    assert technical_sections
    assert all("business_domain" in section for section in technical_sections)
    assert all("business_domain_trace" in section for section in technical_sections)


def test_infer_clause_role_recognizes_gate() -> None:
    clause_role = infer_clause_role(
        {
            "title": "投标人资格要求",
            "source": "rule_split",
            "module": "procedure",
            "body": "投标人须具备独立承担民事责任能力，不满足资格条件的资格审查不通过。",
            "excerpt": "投标人须具备独立承担民事责任能力，不满足资格条件的资格审查不通过。",
        }
    )

    assert clause_role == "gate"


def test_infer_clause_role_recognizes_scoring_factor() -> None:
    clause_role = infer_clause_role(
        {
            "title": "评分标准",
            "source": "rule_split",
            "module": "scoring",
            "body": "每提供1项类似项目业绩得5分，最高得10分。",
            "excerpt": "每提供1项类似项目业绩得5分，最高得10分。",
        }
    )

    assert clause_role == "scoring_factor"


def test_infer_clause_role_recognizes_technical_requirement() -> None:
    clause_role = infer_clause_role(
        {
            "title": "技术要求",
            "source": "rule_split",
            "module": "technical",
            "body": "设备应符合 GB/T 2820.5-2009 标准，额定输出功率不小于200kW。",
            "excerpt": "设备应符合 GB/T 2820.5-2009 标准，额定输出功率不小于200kW。",
        }
    )

    assert clause_role == "technical_requirement"


def test_infer_clause_role_recognizes_acceptance_basis() -> None:
    clause_role = infer_clause_role(
        {
            "title": "验收标准",
            "source": "rule_split",
            "module": "acceptance",
            "body": "按招标文件、投标文件及国家相关规范组织验收。",
            "excerpt": "按招标文件、投标文件及国家相关规范组织验收。",
        }
    )

    assert clause_role == "acceptance_basis"


def test_infer_clause_role_recognizes_commercial_obligation() -> None:
    clause_role = infer_clause_role(
        {
            "title": "付款方式",
            "source": "rule_split",
            "module": "contract",
            "body": "采购人收到发票后15个工作日内支付合同价款。",
            "excerpt": "采购人收到发票后15个工作日内支付合同价款。",
        }
    )

    assert clause_role == "commercial_obligation"


def test_infer_clause_role_recognizes_supporting_material_without_misclassifying_gate() -> None:
    clause_role = infer_clause_role(
        {
            "title": "资格证明材料要求",
            "source": "rule_split",
            "module": "qualification",
            "body": "投标人须提供营业执照扫描件、资质证书复印件作为证明材料。",
            "excerpt": "投标人须提供营业执照扫描件、资质证书复印件作为证明材料。",
        }
    )

    assert clause_role == "supporting_material"


def test_infer_clause_role_recognizes_reminder() -> None:
    clause_role = infer_clause_role(
        {
            "title": "招标文件的澄清和修改",
            "source": "rule_split",
            "module": "procedure",
            "body": "投标人有义务及时关注补充通知，需进一步核实的以公告为准。",
            "excerpt": "投标人有义务及时关注补充通知，需进一步核实的以公告为准。",
        }
    )

    assert clause_role == "reminder"


def test_infer_evidence_strength_recognizes_weak_for_template_or_reminder() -> None:
    evidence_strength = infer_evidence_strength(
        {
            "title": "第七章 电子投标文件格式",
            "source": "rule_split",
            "module": "procedure",
            "body": "本章提供格式仅供参考，投标人应根据自身情况填写。",
            "excerpt": "本章提供格式仅供参考，投标人应根据自身情况填写。",
        }
    )

    assert evidence_strength == "weak"


def test_infer_evidence_strength_recognizes_medium_for_supporting_material() -> None:
    evidence_strength = infer_evidence_strength(
        {
            "title": "资格证明材料要求",
            "source": "rule_split",
            "module": "qualification",
            "body": "投标人须提供营业执照扫描件、资质证书复印件。",
            "excerpt": "投标人须提供营业执照扫描件、资质证书复印件。",
        }
    )

    assert evidence_strength == "medium"


def test_infer_evidence_strength_recognizes_strong_for_explicit_hard_clause() -> None:
    evidence_strength = infer_evidence_strength(
        {
            "title": "评分标准",
            "source": "rule_split",
            "module": "scoring",
            "body": "每提供1项类似项目业绩得5分，最高得10分，未提供不得分。",
            "excerpt": "每提供1项类似项目业绩得5分，最高得10分，未提供不得分。",
        }
    )

    assert evidence_strength == "strong"


def test_infer_hard_evidence_requires_joint_signal_not_body_length_only() -> None:
    hard_evidence = infer_hard_evidence(
        {
            "title": "评分标准",
            "source": "rule_split",
            "module": "scoring",
            "body": "每提供1项类似项目业绩得5分，最高得10分，未提供不得分。",
            "excerpt": "每提供1项类似项目业绩得5分，最高得10分，未提供不得分。",
        }
    )

    assert hard_evidence is True


def test_infer_hard_evidence_rejects_supporting_material_and_reminder() -> None:
    supporting_hard = infer_hard_evidence(
        {
            "title": "资格证明材料要求",
            "source": "rule_split",
            "module": "qualification",
            "body": "投标人须提供营业执照扫描件、资质证书复印件。",
            "excerpt": "投标人须提供营业执照扫描件、资质证书复印件。",
        }
    )
    reminder_hard = infer_hard_evidence(
        {
            "title": "招标文件的澄清和修改",
            "source": "rule_split",
            "module": "procedure",
            "body": "投标人有义务及时关注补充通知，需进一步核实的以公告为准。",
            "excerpt": "投标人有义务及时关注补充通知，需进一步核实的以公告为准。",
        }
    )

    assert supporting_hard is False
    assert reminder_hard is False


def test_build_evidence_layer_writes_clause_strength_and_hard_evidence_traces_into_sections() -> None:
    structure, evidence_map = _sample_structure_and_evidence()
    evidence_layer = build_evidence_layer("sample.docx", structure, evidence_map)

    scoring_sections = evidence_layer.topic_inputs["scoring"].sections

    assert scoring_sections
    assert all("clause_role" in section for section in scoring_sections)
    assert all("clause_role_trace" in section for section in scoring_sections)
    assert all("evidence_strength" in section for section in scoring_sections)
    assert all("evidence_strength_trace" in section for section in scoring_sections)
    assert all("hard_evidence" in section for section in scoring_sections)
    assert all("hard_evidence_trace" in section for section in scoring_sections)
