from __future__ import annotations

from app.common.schemas import RiskPoint
from app.pipelines.v2.assembler import assemble_v2_report
from app.pipelines.v2.compare import compare_review_artifacts
from app.pipelines.v2.schemas import TopicReviewArtifact, V2StageArtifact


def test_compare_review_artifacts_clusters_duplicate_risks() -> None:
    baseline = V2StageArtifact(
        name="baseline",
        content="""
# 招标文件合规审查结果

审查对象：`sample.docx`

说明：
- 本审查基于你提供的招标文件文本进行。

## 风险点1：标准名称与编号不一致

- 问题定性：中风险
- 审查类型：技术标准
- 原文位置：第三章 技术要求
- 原文摘录：满足人造草 GB36246-2018 标准
- 风险判断：
  - 标准名称与编号对应关系不清。
- 法律/政策依据：
  - 需人工复核
- 整改建议：
  - 核对标准全称并统一表述。
""".strip(),
    )
    topics = [
        TopicReviewArtifact(
            topic="technical",
            summary="技术专题完成。",
            risk_points=[
                RiskPoint(
                    title="标准名称与编号不一致",
                    severity="高风险",
                    review_type="技术标准",
                    source_location="第三章 技术要求",
                    source_excerpt="满足人造草 GB36246-2018 标准",
                    risk_judgment=["技术专题认为该标准存在明显错引。"],
                    legal_basis=["需人工复核"],
                    rectification=["统一标准名称和编号。"],
                )
            ],
            need_manual_review=False,
            coverage_note="已覆盖技术章节。",
            metadata={"selected_sections": [{"title": "第三章 技术要求"}], "missing_evidence": []},
        )
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    assert len(comparison.clusters) == 1
    cluster = comparison.clusters[0]
    assert cluster.severity == "高风险"
    assert "baseline" in cluster.topics
    assert "technical" in cluster.topics
    assert comparison.conflicts
    assert comparison.comparison_summary["duplicate_reduction"] == 1


def test_assemble_v2_report_prefers_comparison_clusters() -> None:
    baseline = V2StageArtifact(
        name="baseline",
        content="""
# 招标文件合规审查结果

审查对象：`sample.docx`

说明：
- 本审查基于你提供的招标文件文本进行。

## 风险点1：付款节点明显偏后

- 问题定性：中风险
- 审查类型：付款条款
- 原文位置：第四章 商务条款
- 原文摘录：验收合格后 15 个工作日内付款
- 风险判断：
  - 付款安排对供应商资金占压较大。
- 法律/政策依据：
  - 需人工复核
- 整改建议：
  - 优化付款节点和支付安排。
""".strip(),
    )
    topics = [
        TopicReviewArtifact(
            topic="contract",
            summary="合同专题完成。",
            risk_points=[
                RiskPoint(
                    title="付款节点明显偏后",
                    severity="中风险",
                    review_type="付款条款",
                    source_location="第四章 商务条款",
                    source_excerpt="验收合格后 15 个工作日内付款",
                    risk_judgment=["合同专题也识别到相同问题。"],
                    legal_basis=["需人工复核"],
                    rectification=["优化付款节点。"],
                )
            ],
            need_manual_review=False,
            coverage_note="已覆盖合同章节。",
            metadata={"selected_sections": [{"title": "第四章 商务条款"}], "missing_evidence": []},
        )
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    report = assemble_v2_report("sample.docx", baseline, V2StageArtifact(name="structure", metadata={}), topics, comparison)
    assert report.count("## 风险点") == 1
    assert "付款节点明显偏后" in report


def test_compare_review_artifacts_enriches_coverage_analysis() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题需人工复核。",
            risk_points=[],
            need_manual_review=True,
            coverage_note="评分章节较短。",
            metadata={
                "selected_sections": [],
                "missing_evidence": ["缺少量化评分细则"],
                "topic_coverage": {"missing_modules": ["scoring"]},
            },
        ),
        TopicReviewArtifact(
            topic="technical",
            summary="技术专题完成。",
            risk_points=[
                RiskPoint(
                    title="样品要求标准不明确",
                    severity="中风险",
                    review_type="样品要求",
                    source_location="第三章 技术要求",
                    source_excerpt="要求提供样品，但未说明评审标准",
                    risk_judgment=["样品要求缺少明确标准。"],
                    legal_basis=["需人工复核"],
                    rectification=["补充样品评审规则。"],
                )
            ],
            need_manual_review=False,
            coverage_note="已覆盖技术章节。",
            metadata={"selected_sections": [{"title": "第三章 技术要求"}], "missing_evidence": []},
        ),
    ]
    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    assert comparison.topic_only_risks
    assert comparison.coverage_gaps
    assert comparison.coverage_summary["coverage_gap_count"] >= 2
    assert comparison.manual_review_items


def test_compare_review_artifacts_adds_policy_technical_inconsistency_risk() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="policy",
            summary="政策专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖政策条款。",
            metadata={
                "selected_sections": [{"title": "第一章 政策条款"}],
                "missing_evidence": [],
                "structured_signals": {
                    "import_policy": "reject_import",
                    "import_policy_reject_phrases": ["不接受投标人选用进口产品参与投标"],
                    "import_policy_accept_phrases": [],
                },
            },
        ),
        TopicReviewArtifact(
            topic="technical_standard",
            summary="技术标准专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖技术标准条款。",
            metadata={
                "selected_sections": [{"title": "第二章 技术标准要求"}],
                "missing_evidence": [],
                "structured_signals": {
                    "foreign_standard_refs": ["BS EN 61000", "EN55011"],
                    "cn_standard_refs": [],
                    "has_equivalent_standard_clause": False,
                    "standard_system_mix": "foreign_only",
                },
            },
        ),
    ]
    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    titles = [cluster.title for cluster in comparison.clusters]
    assert "技术标准引用与采购政策口径不一致，存在潜在倾向性和理解冲突" in titles
    assert comparison.metadata["failure_reason_codes"] == ["policy_technical_inconsistency"]


def test_compare_review_artifacts_avoids_false_positive_when_equivalent_standard_is_allowed() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="policy",
            summary="政策专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖政策条款。",
            metadata={
                "selected_sections": [{"title": "第一章 政策条款"}],
                "missing_evidence": [],
                "structured_signals": {
                    "import_policy": "reject_import",
                    "import_policy_reject_phrases": ["不接受进口产品参与投标"],
                    "import_policy_accept_phrases": [],
                },
            },
        ),
        TopicReviewArtifact(
            topic="technical_standard",
            summary="技术标准专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖技术标准条款。",
            metadata={
                "selected_sections": [{"title": "第二章 技术标准要求"}],
                "missing_evidence": [],
                "structured_signals": {
                    "foreign_standard_refs": ["IEC 61000"],
                    "cn_standard_refs": ["GB/T 17626"],
                    "has_equivalent_standard_clause": True,
                    "standard_system_mix": "mixed_cn_foreign",
                },
            },
        ),
    ]
    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    assert not comparison.clusters
    assert comparison.metadata["failure_reason_codes"] == []
