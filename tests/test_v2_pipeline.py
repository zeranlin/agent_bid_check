import pytest

from app.common.schemas import RiskPoint
from app.pipelines.v2.assembler import assemble_v2_report
from app.pipelines.v2.evidence import build_evidence_map
from app.pipelines.v2.schemas import (
    EvidenceBundle,
    ModuleHit,
    SectionCandidate,
    TopicCoverage,
    TopicReviewArtifact,
    V2StageArtifact,
)
from app.pipelines.v2.structure import build_structure_map
from app.pipelines.v2.topic_review import run_topic_reviews
from app.pipelines.v2.topics import (
    ACTIVE_TOPIC_KEYS,
    TOPIC_TAXONOMY_MAP,
    get_active_topic_definitions,
    resolve_topic_definitions,
    resolve_topic_execution_plan,
)
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


def test_build_evidence_map_groups_sections_by_topic() -> None:
    text = """
第一章 招标公告
投标人资格要求如下，需提供类似项目业绩和项目经理证书。

第二章 评分办法
综合评分法，技术评分 40 分，商务评分 20 分，演示 10 分。

第三章 技术要求
场地材料应符合 GB 36246-2018 标准，需提供检测报告和样品。

第四章 商务条款
验收合格后 15 个工作日内付款，逾期违约按合同约定执行。
""".strip()
    structure = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
    )
    evidence = build_evidence_map("sample.docx", structure)

    bundles = evidence.metadata["topic_evidence_bundles"]
    coverages = evidence.metadata["topic_coverages"]
    assert set(bundles.keys()) >= {"qualification", "scoring", "contract", "technical"}
    assert bundles["technical"]["primary_section_ids"]
    assert any(section["module"] == "technical" for section in bundles["technical"]["sections"])
    assert bundles["contract"]["sections"]
    assert "contract" in coverages["contract"]["covered_modules"] or "acceptance" in coverages["contract"]["covered_modules"]
    assert evidence.metadata["evidence_bundle_count"] == 4
    assert "technical_standard" in evidence.metadata["topic_taxonomy"]
    assert evidence.metadata["topic_taxonomy"]["qualification"]["boundary"]["ownership_rule"]
    assert evidence.metadata["topic_execution_plan"]["mode"] == "default"
    assert evidence.metadata["topic_execution_plan"]["max_topic_calls"] == 4
    assert evidence.content


def test_topic_taxonomy_and_active_topics_contract() -> None:
    active_topics = get_active_topic_definitions()
    default_plan = resolve_topic_execution_plan("default")
    enhanced_plan = resolve_topic_execution_plan("enhanced")
    assert ACTIVE_TOPIC_KEYS == ("qualification", "scoring", "contract", "technical")
    assert len(TOPIC_TAXONOMY_MAP) >= 10
    assert TOPIC_TAXONOMY_MAP["performance_staff"].enabled is False
    assert TOPIC_TAXONOMY_MAP["technical_bias"].boundary.out_of_scope
    assert TOPIC_TAXONOMY_MAP["technical_standard"].boundary.ownership_rule
    assert TOPIC_TAXONOMY_MAP["performance_staff"].prompt.strip()
    assert TOPIC_TAXONOMY_MAP["samples_demo"].prompt.strip()
    assert TOPIC_TAXONOMY_MAP["technical_bias"].prompt.strip()
    assert TOPIC_TAXONOMY_MAP["technical_standard"].prompt.strip()
    assert TOPIC_TAXONOMY_MAP["contract_payment"].prompt.strip()
    assert TOPIC_TAXONOMY_MAP["acceptance"].prompt.strip()
    assert TOPIC_TAXONOMY_MAP["procedure"].prompt.strip()
    assert TOPIC_TAXONOMY_MAP["policy"].prompt.strip()
    assert [topic.key for topic in active_topics] == list(ACTIVE_TOPIC_KEYS)
    assert [topic.key for topic in resolve_topic_definitions("slim")] == ["qualification", "scoring", "technical"]
    assert list(default_plan.selected_keys) == ["qualification", "scoring", "contract", "technical"]
    assert set(default_plan.skipped_keys) == {"procedure", "policy"}
    assert enhanced_plan.max_topic_calls == 10
    assert len(enhanced_plan.selected_keys) == 10


def test_run_topic_reviews_supports_topic_sets(monkeypatch: pytest.MonkeyPatch) -> None:
    text = """
第一章 招标公告
投标人资格要求如下，需提供类似项目业绩和项目经理证书。

第二章 评分办法
综合评分法，技术评分 40 分，商务评分 20 分，演示 10 分。

第三章 技术要求
场地材料应符合 GB 36246-2018 标准，需提供检测报告和样品。
""".strip()
    structure = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
        use_llm=False,
    )
    evidence = build_evidence_map("sample.docx", structure)

    def fake_call_chat_completion(**kwargs: object) -> dict:
        user_prompt = str(kwargs.get("user_prompt", ""))
        if "专题名称：资格条件" in user_prompt:
            topic_name = "资格条件"
        elif "专题名称：评分办法" in user_prompt:
            topic_name = "评分办法"
        else:
            topic_name = "技术细节"
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "{"
                            f"\"summary\": \"{topic_name}专题完成\", "
                            "\"need_manual_review\": false, "
                            "\"coverage_note\": \"已按证据包审查。\", "
                            "\"missing_evidence\": [\"未发现\"], "
                            "\"risk_points\": []"
                            "}"
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr("app.pipelines.v2.topic_review.call_chat_completion", fake_call_chat_completion)

    topics = run_topic_reviews(
        document_name="sample.docx",
        evidence=evidence,
        settings=ReviewSettings(),
        topic_mode="slim",
    )
    assert [topic.topic for topic in topics] == ["qualification", "scoring", "technical"]
    assert all(topic.metadata["topic_mode"] == "slim" for topic in topics)
    assert all("missing_evidence" in topic.metadata for topic in topics)
    assert all(topic.metadata["topic_execution_plan"]["max_topic_calls"] == 3 for topic in topics)


def test_build_structure_map_uses_llm_refine_for_low_confidence_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    text = """
第一章 其他要求
本章描述供应商提供材料、标准、验收、付款等综合要求。

第二章 投标须知
响应文件递交时间与澄清程序详见本章。
""".strip()

    def fake_call_chat_completion(**_: object) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": """
{
  "sections": [
    {
      "index": 1,
      "module": "contract",
      "confidence": 0.81,
      "reason": "片段同时强调付款和验收要求，更接近合同履约模块。",
      "keywords": ["付款", "验收"]
    }
  ]
}
                        """.strip()
                    }
                }
            ]
        }

    monkeypatch.setattr("app.pipelines.v2.structure.call_chat_completion", fake_call_chat_completion)

    artifact = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
    )
    sections = artifact.metadata["sections"]
    assert artifact.metadata["structure_llm_used"] is True
    assert artifact.metadata["structure_fallback_used"] is False
    assert sections[0]["source"] == "llm_refined"
    assert sections[0]["module"] == "contract"
    assert any(hit["source"] == "llm_refine" for hit in sections[0]["module_hits"])


def test_build_structure_map_llm_failure_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    text = """
第一章 其他事项
本章描述综合要求，没有明显模块边界。
""".strip()

    def fake_call_chat_completion(**_: object) -> dict:
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr("app.pipelines.v2.structure.call_chat_completion", fake_call_chat_completion)

    artifact = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
    )
    assert artifact.metadata["structure_llm_used"] is True
    assert artifact.metadata["structure_fallback_used"] is True
    assert artifact.metadata["sections"][0]["source"] == "rule_split"


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
