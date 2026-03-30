from app.common.schemas import RiskPoint
from app.pipelines.v2.assembler import assemble_v2_report
from app.pipelines.v2.schemas import (
    EvidenceBundle,
    ModuleHit,
    SectionCandidate,
    TopicCoverage,
    TopicReviewArtifact,
    V2StageArtifact,
)
from app.pipelines.v2.structure import build_structure_map
from app.config import ReviewSettings


def test_build_structure_map_identifies_modules() -> None:
    text = """
第一章 招标公告
投标人资格要求如下。

第二章 评分办法
综合评分法，技术评分 40 分，商务评分 20 分。

第三章 技术要求
场地材料应符合 GB 36246-2018 标准。

第四章 商务条款
验收合格后 15 个工作日内付款。
""".strip()
    artifact = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
    )
    sections = artifact.metadata["sections"]
    modules = {section["module"] for section in sections}
    assert "qualification" in modules or "procedure" in modules
    assert "scoring" in modules
    assert "technical" in modules
    assert "contract" in modules or "acceptance" in modules
    assert all("heading_level" in section for section in sections)
    assert all("source" in section for section in sections)
    assert any(section["title"] == "第二章 评分办法" and section["heading_level"] == 1 for section in sections)
    assert any(section.get("module_hits") for section in sections)
    assert artifact.metadata["section_candidates"][0]["body"]


def test_assemble_v2_report_merges_topic_risks() -> None:
    baseline = V2StageArtifact(
        name="baseline",
        content="""
# 招标文件合规审查结果

审查对象：`sample.docx`

说明：
- 本审查基于你提供的招标文件文本进行。

## 风险点1：资格条件不合理

- 问题定性：高风险
- 审查类型：资格条件
- 原文位置：第一章
- 原文摘录：要求成立满五年
- 风险判断：
  - 可能限制竞争
- 法律/政策依据：
  - 《政府采购法》第二十二条
- 整改建议：
  - 删除成立年限要求
""".strip(),
    )
    structure = V2StageArtifact(
        name="structure",
        content="{}",
        metadata={"section_count": 3, "sections": [{"title": "第三章 技术要求"}]},
    )
    technical_topic = TopicReviewArtifact(
        topic="technical",
        summary="发现标准引用细节风险。",
        risk_points=[
            RiskPoint(
                title="标准名称与编号不一致",
                severity="中风险",
                review_type="技术参数/标准引用",
                source_location="第三章 技术要求",
                source_excerpt="满足人造草 GB36246-2018 标准",
                risk_judgment=["标准名称与编号对应关系不清。"],
                legal_basis=["需人工复核"],
                rectification=["核对标准全称并统一表述。"],
            )
        ],
        need_manual_review=False,
        coverage_note="召回 2 个技术片段。",
    )

    result = assemble_v2_report("sample.docx", baseline, structure, [technical_topic])
    assert "## 风险点1：资格条件不合理" in result
    assert "## 风险点2：标准名称与编号不一致" in result
    assert "本报告结合全文直审、结构增强与专题深审生成。" in result


def test_v2_structure_contract_schemas_serialize_cleanly() -> None:
    section = SectionCandidate(
        title="第三章 技术要求",
        start_line=12,
        end_line=30,
        body="样品品牌：Aokang",
        excerpt="样品品牌：Aokang",
        module="technical",
        module_scores={"technical": 4, "contract": 1},
        confidence=4,
        keywords=["品牌", "样品"],
        heading_level=1,
    )
    hit = ModuleHit(
        module="technical",
        score=0.88,
        source="rule",
        reason="技术关键词命中较多",
        evidence_keywords=["品牌", "样品"],
    )
    bundle = EvidenceBundle(
        topic="technical_standard",
        sections=[section],
        primary_section_ids=["12-30"],
        secondary_section_ids=[],
        missing_hints=["未发现检测报告要求章节"],
        recall_query="标准、品牌、检测报告",
        metadata={"module_hits": [hit.to_dict()]},
    )
    coverage = TopicCoverage(
        topic="technical_standard",
        covered_modules=["technical"],
        covered_section_ids=["12-30"],
        missing_modules=["acceptance"],
        missing_hints=["未发现验收标准片段"],
        need_manual_review=True,
        confidence=0.72,
    )

    assert section.line_span == 19
    assert section.to_dict()["module"] == "technical"
    assert hit.to_dict()["score"] == 0.88
    assert bundle.to_dict()["sections"][0]["title"] == "第三章 技术要求"
    assert coverage.to_dict()["need_manual_review"] is True
