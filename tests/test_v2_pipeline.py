import pytest

from app.common.schemas import RiskPoint
from app.pipelines.v2.assembler import assemble_v2_report, build_v2_final_output
from app.pipelines.v2.evidence import build_evidence_map
from app.pipelines.v2.schemas import (
    ComparisonArtifact,
    EvidenceBundle,
    MergedRiskCluster,
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


def test_build_structure_map_recognizes_scoring_title_variants() -> None:
    text = """
附表1 综合评分表
价格分最高得30分，技术分最高得40分，商务分最高得20分。

第六章 评审办法
采用综合评分法，按评分细则计算总分。
""".strip()
    artifact = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
        use_llm=False,
    )
    sections = artifact.metadata["sections"]
    assert any(section["title"] == "附表1 综合评分表" and section["module"] == "scoring" for section in sections)
    assert any(section["title"] == "第六章 评审办法" and section["module"] == "scoring" for section in sections)


def test_build_structure_map_merges_attachment_heading_with_next_scoring_title() -> None:
    text = """
附表1
综合评分表
价格分最高得30分，技术分最高得40分，商务分最高得20分。

第七章 投标须知
递交时间和开标程序见本章。
""".strip()
    artifact = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
        use_llm=False,
    )
    sections = artifact.metadata["sections"]
    assert sections[0]["title"] == "附表1 综合评分表"
    assert sections[0]["module"] == "scoring"


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


def test_build_v2_final_output_uses_comparison_as_single_source() -> None:
    baseline = V2StageArtifact(
        name="baseline",
        content="""
# 招标文件合规审查结果

审查对象：`sample.docx`

## 综合判断

- 高风险问题：
  - 旧标题
""".strip(),
    )
    artifact = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="cluster-1",
                title="正式风险标题",
                severity="高风险",
                review_type="类型A",
                source_locations=["第一章"],
                source_excerpts=["正式摘录"],
                risk_judgment=["正式判断"],
                legal_basis=["正式依据"],
                rectification=["正式建议"],
            )
        ],
        metadata={
            "pending_review_items": [{"title": "待补证项", "review_type": "资格条件", "topic": "qualification"}],
            "excluded_risks": [{"title": "已剔除项"}],
        },
    )

    final_output = build_v2_final_output(
        "sample.docx",
        baseline,
        V2StageArtifact(name="structure", metadata={}),
        [],
        comparison=artifact,
    )

    assert [item["title"] for item in final_output["formal_risks"]] == ["正式风险标题"]
    assert final_output["summary"]["high_risk_titles"] == ["正式风险标题"]
    assert final_output["summary"]["manual_review_titles"] == ["待补证项"]
    assert [item["title"] for item in final_output["excluded_risks"]] == ["已剔除项"]


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
    assert default_plan.per_topic_timeout > 0
    assert default_plan.per_topic_max_tokens > 0
    assert default_plan.allow_degrade_on_error is True


def test_build_evidence_map_includes_scoring_main_section_and_score_table() -> None:
    text = """
第六章 评分办法
采用综合评分法，技术分40分，商务分20分，价格分30分。

附表1 综合评分表
评审因素、分值构成和打分档次详见本表。

第七章 投标须知
递交时间、澄清程序和开标安排按本章执行。
""".strip()
    structure = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
        use_llm=False,
    )
    evidence = build_evidence_map("sample.docx", structure, topic_mode="slim", topic_keys=["scoring"])
    scoring_bundle = evidence.metadata["topic_evidence_bundles"]["scoring"]
    scoring_titles = [section["title"] for section in scoring_bundle["sections"]]
    assert "第六章 评分办法" in scoring_titles
    assert "附表1 综合评分表" in scoring_titles
    assert scoring_bundle["primary_section_ids"]
    assert evidence.metadata["topic_coverages"]["scoring"]["covered_modules"]


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
    assert all(topic.metadata["topic_execution_plan"]["per_topic_timeout"] == 90 for topic in topics)


def test_run_topic_reviews_degrades_when_topic_call_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    text = """
第一章 评分办法
综合评分法，技术评分 40 分，商务评分 20 分。
""".strip()
    structure = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
        use_llm=False,
    )
    evidence = build_evidence_map("sample.docx", structure, topic_mode="slim", topic_keys=["scoring"])

    def fake_call_chat_completion(**_: object) -> dict:
        raise TimeoutError("topic timeout")

    monkeypatch.setattr("app.pipelines.v2.topic_review.call_chat_completion", fake_call_chat_completion)

    topics = run_topic_reviews(
        document_name="sample.docx",
        evidence=evidence,
        settings=ReviewSettings(),
        topic_mode="slim",
        topic_keys=["scoring"],
    )
    assert len(topics) == 1
    assert topics[0].need_manual_review is True
    assert topics[0].metadata["degraded"] is True
    assert topics[0].metadata["degrade_reason"] == "topic_call_failed"
    assert "专题调用失败" in topics[0].summary
    assert topics[0].metadata["selected_sections"]
    assert "degraded_to_manual_review" in topics[0].metadata["failure_reasons"]
    assert "risk_degraded_to_manual_review" in topics[0].metadata["failure_reasons"]


def test_run_topic_reviews_degrades_when_response_extract_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    text = """
第一章 评分办法
综合评分法，技术评分 40 分，商务评分 20 分。
""".strip()
    structure = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
        use_llm=False,
    )
    evidence = build_evidence_map("sample.docx", structure, topic_mode="slim", topic_keys=["scoring"])

    def fake_call_chat_completion(**_: object) -> dict:
        return {"choices": [{"message": {"content": "{\"summary\":\"ok\"}"}}]}

    def fake_extract_response_text(_: object) -> str:
        raise ValueError("bad response payload")

    monkeypatch.setattr("app.pipelines.v2.topic_review.call_chat_completion", fake_call_chat_completion)
    monkeypatch.setattr("app.pipelines.v2.topic_review.extract_response_text", fake_extract_response_text)

    topics = run_topic_reviews(
        document_name="sample.docx",
        evidence=evidence,
        settings=ReviewSettings(),
        topic_mode="slim",
        topic_keys=["scoring"],
    )
    assert len(topics) == 1
    assert topics[0].need_manual_review is True
    assert topics[0].metadata["degraded"] is True
    assert topics[0].metadata["degrade_reason"] == "topic_response_parse_failed"
    assert "专题响应解析失败" in topics[0].summary


def test_run_topic_reviews_degrades_when_postprocess_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    text = """
第一章 技术标准
本项目采购内容为操场跑道维护材料，但要求按塑料薄膜和薄片透水率试验方法出具检测报告。
""".strip()
    structure = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
        use_llm=False,
    )
    evidence = build_evidence_map("sample.docx", structure, topic_mode="slim", topic_keys=["technical_standard"])

    def fake_call_chat_completion(**_: object) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "{"
                            "\"summary\": \"技术标准专题完成。\", "
                            "\"need_manual_review\": false, "
                            "\"coverage_note\": \"已覆盖技术标准条款。\", "
                            "\"missing_evidence\": [\"未发现\"], "
                            "\"risk_points\": []"
                            "}"
                        )
                    }
                }
            ]
        }

    def fake_postprocess(*args, **kwargs):
        raise RuntimeError("postprocess exploded")

    monkeypatch.setattr("app.pipelines.v2.topic_review.call_chat_completion", fake_call_chat_completion)
    monkeypatch.setattr("app.pipelines.v2.topic_review._postprocess_topic_payload", fake_postprocess)

    topics = run_topic_reviews(
        document_name="sample.docx",
        evidence=evidence,
        settings=ReviewSettings(),
        topic_mode="slim",
        topic_keys=["technical_standard"],
    )
    assert len(topics) == 1
    assert topics[0].need_manual_review is True
    assert topics[0].metadata["degraded"] is True
    assert topics[0].metadata["degrade_reason"] == "topic_postprocess_failed"
    assert "专题后处理失败" in topics[0].summary
    assert topics[0].raw_output


def test_run_topic_reviews_scoring_postprocess_adds_quantization_risk(monkeypatch: pytest.MonkeyPatch) -> None:
    text = """
第一章 评分办法
技术方案优得40分，良得30分，一般得20分。演示效果优得10分，良得6分，一般得3分，由评委综合打分。
""".strip()
    structure = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
        use_llm=False,
    )
    evidence = build_evidence_map("sample.docx", structure, topic_mode="slim", topic_keys=["scoring"])

    def fake_call_chat_completion(**_: object) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "{"
                            "\"summary\": \"评分办法专题完成。\", "
                            "\"need_manual_review\": false, "
                            "\"coverage_note\": \"已覆盖评分条款。\", "
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
        topic_keys=["scoring"],
    )
    assert len(topics) == 1
    assert topics[0].topic == "scoring"
    assert topics[0].risk_points
    assert topics[0].risk_points[0].title == "评分档次缺少量化口径"
    assert topics[0].risk_points[0].review_type == "评分标准不明确"
    assert "risk_not_extracted" in topics[0].metadata["failure_reasons"]


def test_run_topic_reviews_qualification_postprocess_recovers_local_service_risk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = """
第一章 资格条件
投标人须具备独立法人资格，并在本市设有常设服务机构，否则资格审查不通过。
""".strip()
    structure = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
        use_llm=False,
    )
    evidence = build_evidence_map("sample.docx", structure, topic_mode="slim", topic_keys=["qualification"])

    def fake_call_chat_completion(**_: object) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "{"
                            "\"summary\": \"资格条件专题完成。\", "
                            "\"need_manual_review\": false, "
                            "\"coverage_note\": \"已覆盖资格条款。\", "
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
        topic_keys=["qualification"],
    )
    assert len(topics) == 1
    assert "设立常设服务机构的资格限制" in [risk.title for risk in topics[0].risk_points]
    assert "risk_not_extracted" in topics[0].metadata["failure_reasons"]


def test_run_topic_reviews_contract_postprocess_recovers_payment_risks(monkeypatch: pytest.MonkeyPatch) -> None:
    text = """
第一章 商务条款
项目终验合格且财政资金到位后90个工作日内支付剩余合同价款。
""".strip()
    structure = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
        use_llm=False,
    )
    evidence = build_evidence_map("sample.docx", structure, topic_mode="slim", topic_keys=["contract_payment"])

    def fake_call_chat_completion(**_: object) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "{"
                            "\"summary\": \"付款履约专题完成。\", "
                            "\"need_manual_review\": false, "
                            "\"coverage_note\": \"已覆盖付款条款。\", "
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
        topic_keys=["contract_payment"],
    )
    assert len(topics) == 1
    titles = [risk.title for risk in topics[0].risk_points]
    assert "付款节点与财政资金到位挂钩" in titles
    assert "付款安排以验收裁量为前置条件" in titles
    assert "付款节点明显偏后" in titles
    assert "risk_not_extracted" in topics[0].metadata["failure_reasons"]


def test_run_topic_reviews_marks_partial_and_shared_failure_reasons(monkeypatch: pytest.MonkeyPatch) -> None:
    text = """
第一章 商务条款
项目终验合格且财政资金到位后90个工作日内支付尾款。
""".strip()
    structure = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
        use_llm=False,
    )
    evidence = build_evidence_map("sample.docx", structure, topic_mode="enhanced", topic_keys=["contract_payment"])

    def fake_call_chat_completion(**_: object) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "{"
                            "\"summary\": \"付款履约专题完成。\", "
                            "\"need_manual_review\": false, "
                            "\"coverage_note\": \"已覆盖付款节点条款。\", "
                            "\"missing_evidence\": [\"未发现\"], "
                            "\"risk_points\": ["
                            "{"
                            "\"title\": \"付款节点与财政资金到位挂钩\", "
                            "\"severity\": \"高风险\", "
                            "\"review_type\": \"商务条款失衡\", "
                            "\"source_location\": \"第一章 商务条款\", "
                            "\"source_excerpt\": \"财政资金到位后支付尾款。\", "
                            "\"risk_judgment\": [\"付款以前置资金条件为前提。\"], "
                            "\"legal_basis\": [\"需人工复核\"], "
                            "\"rectification\": [\"删除财政资金到位前提。\"]"
                            "}"
                            "]"
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
        topic_mode="enhanced",
        topic_keys=["contract_payment"],
    )
    reasons = topics[0].metadata["failure_reasons"]
    assert "risk_not_extracted" in reasons
    assert "topic_triggered_but_partial_miss" in reasons


def test_run_topic_reviews_marks_degraded_manual_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    text = """
第一章 评分说明
按优良中差分档评分，具体量化标准详见缺失附表。
""".strip()
    structure = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
        use_llm=False,
    )
    evidence = build_evidence_map("sample.docx", structure, topic_mode="enhanced", topic_keys=["scoring"])

    def fake_call_chat_completion(**_: object) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "{"
                            "\"summary\": \"评分办法专题需人工复核。\", "
                            "\"need_manual_review\": true, "
                            "\"coverage_note\": \"仅覆盖分档描述。\", "
                            "\"missing_evidence\": [\"缺少完整评分附表。\"], "
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
        topic_mode="enhanced",
        topic_keys=["scoring"],
    )
    reasons = topics[0].metadata["failure_reasons"]
    assert "degraded_to_manual_review" in reasons
    assert "risk_degraded_to_manual_review" in reasons


def test_run_topic_reviews_records_topic_failure_reasons(monkeypatch: pytest.MonkeyPatch) -> None:
    text = """
第一章 评分办法
综合评分法，技术评分 40 分，商务评分 20 分。
""".strip()
    structure = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
        use_llm=False,
    )
    evidence = build_evidence_map("sample.docx", structure, topic_mode="slim", topic_keys=["scoring"])

    def fake_call_chat_completion(**_: object) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "{"
                            "\"summary\": \"评分办法专题完成。\", "
                            "\"need_manual_review\": true, "
                            "\"coverage_note\": \"证据不足。\", "
                            "\"missing_evidence\": [\"缺少量化评分细则\"], "
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
        topic_keys=["scoring"],
    )
    assert len(topics) == 1
    assert "missing_evidence" in topics[0].metadata["failure_reasons"]
    assert "degraded_to_manual_review" in topics[0].metadata["failure_reasons"]


def test_run_topic_reviews_tightens_manual_review_when_explicit_risk_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = """
第一章 评分办法
技术方案优得40分，良得30分，一般得20分。
""".strip()
    structure = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
        use_llm=False,
    )
    evidence = build_evidence_map("sample.docx", structure, topic_mode="slim", topic_keys=["scoring"])

    def fake_call_chat_completion(**_: object) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "{"
                            "\"summary\": \"评分办法专题完成。\", "
                            "\"need_manual_review\": true, "
                            "\"coverage_note\": \"已覆盖评分条款。\", "
                            "\"missing_evidence\": [\"未发现\"], "
                            "\"risk_points\": [{"
                            "\"title\": \"评分档次缺少量化口径\", "
                            "\"severity\": \"中风险\", "
                            "\"review_type\": \"评分标准不明确\", "
                            "\"source_location\": \"第一章 评分办法\", "
                            "\"source_excerpt\": \"技术方案优得40分，良得30分，一般得20分。\", "
                            "\"risk_judgment\": [\"评分档次缺少量化口径。\"], "
                            "\"legal_basis\": [\"需人工复核\"], "
                            "\"rectification\": [\"补充各档次量化标准。\"]"
                            "}]"
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
        topic_keys=["scoring"],
    )
    assert len(topics) == 1
    assert topics[0].risk_points[0].title == "评分档次缺少量化口径"
    assert topics[0].need_manual_review is False
    assert topics[0].metadata["missing_evidence"] == ["未发现"]
    assert "degraded_to_manual_review" not in topics[0].metadata["failure_reasons"]


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


def test_build_evidence_map_prioritizes_technical_parameter_section_for_foreign_standard_refs() -> None:
    text = """
第一章 采购政策
本项目不接受投标人选用进口产品参与投标。

第二章 商务要求
（一）售后服务要求
供应商须提供售后服务承诺，并按相关标准开展培训。

（二）其他商务要求
设备到货后按招标人要求组织验收，检测标准按采购人通知执行。

第三章 技术要求
1.规格及技术参数
1.14 电磁影响：符合 BS EN 61000、GB/T 17626 及 EN55011 标准。

第四章 合同条款
付款方式：验收合格后支付合同款。

第五章 验收要求
设备验收按合同约定执行。
""".strip()
    structure = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
        use_llm=False,
    )

    evidence = build_evidence_map("sample.docx", structure, topic_mode="slim", topic_keys=["technical_standard"])
    bundle = evidence.metadata["topic_evidence_bundles"]["technical_standard"]
    selected_titles = [section["title"] for section in bundle["sections"]]
    primary_ids = set(bundle["primary_section_ids"])
    primary_titles = [section["title"] for section in bundle["sections"] if f"{section['start_line']}-{section['end_line']}" in primary_ids]

    assert "1.规格及技术参数" in selected_titles
    assert "1.规格及技术参数" in primary_titles
    assert "（二）其他商务要求" not in primary_titles
    assert any("外标命中" in " ".join(item["reasons"]) for item in bundle["metadata"]["primary_scores"])


def test_run_topic_reviews_relaxes_technical_standard_manual_review_when_primary_standard_evidence_is_strong(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = """
第一章 采购政策
本项目不接受投标人选用进口产品参与投标。

第三章 技术要求
1.规格及技术参数
1.14 电磁影响：符合 BS EN 61000、GB/T 17626 及 EN55011 标准。
""".strip()
    structure = build_structure_map(
        input_path=__import__("pathlib").Path("sample.docx"),
        extracted_text=text,
        settings=ReviewSettings(),
        use_llm=False,
    )
    evidence = build_evidence_map("sample.docx", structure, topic_mode="enhanced", topic_keys=["technical_standard"])

    def fake_call_chat_completion(**_: object) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "{"
                            "\"summary\": \"技术标准专题需人工复核。\", "
                            "\"need_manual_review\": true, "
                            "\"coverage_note\": \"已看到技术参数章节，但未找到完整认证和验收材料。\", "
                            "\"missing_evidence\": ["
                            "\"验收标准章节中关于检测报告的具体要求\", "
                            "\"产品认证证书（如CE、CCC等）的具体要求\""
                            "], "
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
        topic_mode="enhanced",
        topic_keys=["technical_standard"],
    )
    assert len(topics) == 1
    topic = topics[0]
    assert topic.topic == "technical_standard"
    assert topic.need_manual_review is False
    assert topic.metadata["missing_evidence"] == ["未发现"]
    assert "missing_evidence" not in topic.metadata["failure_reasons"]
    assert "degraded_to_manual_review" not in topic.metadata["failure_reasons"]
    assert "risk_degraded_to_manual_review" not in topic.metadata["failure_reasons"]
    assert topic.metadata["structured_signals"]["foreign_standard_refs"] == ["BS EN 61000", "EN55011"]
