from __future__ import annotations

from app.common.schemas import RiskPoint
from app.pipelines.v2.assembler import assemble_v2_report
from app.pipelines.v2.compare import _compact_sentences, compare_review_artifacts
from app.pipelines.v2.schemas import ComparisonArtifact, MergedRiskCluster, TopicReviewArtifact, V2StageArtifact


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


def test_compact_sentences_removes_progressive_overlapping_fragments() -> None:
    sentences = [
        "（一）评分内容：柴油发电机组制造商的投标的柴油发电机组，具备以下认证的：1.具备有效期内省级标准协会颁发的省级采用国际标准产品确认证书和采用国际标准产品标志证书的，每具备一项得40分，具备两项得80分，本小项最高得80分",
        "（一）评分内容：柴油发电机组制造商的投标的柴油发电机组，具备以下认证的：1.具备有效期内省级标准协会颁发的省级采用国际标准产品确认证书和采用国际标准产品标志证书的，每具备一项得40分，具备两项得80分，本小项最高得80分。2.具备CNAS中国认可产品标志证书的，得20分，本小项最高得20分",
        "（一）评分内容：柴油发电机组制造商的投标的柴油发电机组，具备以下认证的：1.具备有效期内省级标准协会颁发的省级采用国际标准产品确认证书和采用国际标准产品标志证书的，每具备一项得40分，具备两项得80分，本小项最高得80分。2.具备CNAS中国认可产品标志证书的，得20分，本小项最高得20分。以上累计最高得分为100分",
    ]

    result = _compact_sentences(sentences, limit=3)

    assert result == [
        "（一）评分内容：柴油发电机组制造商的投标的柴油发电机组，具备以下认证的：1.具备有效期内省级标准协会颁发的省级采用国际标准产品确认证书和采用国际标准产品标志证书的，每具备一项得40分，具备两项得80分，本小项最高得80分。2.具备CNAS中国认可产品标志证书的，得20分，本小项最高得20分。以上累计最高得分为100分"
    ]


def test_assemble_v2_report_summary_uses_final_layered_results_only() -> None:
    baseline = V2StageArtifact(
        name="baseline",
        content="""
# 招标文件合规审查结果

审查对象：`sample.docx`

## 综合判断

- 高风险问题：
  - 付款条款关键数据缺失，无法评估公平性与节点衔接
- 中风险问题：
  - 澄清截止时间未明确填写
- 需人工复核事项：
  - qualification: 资格条件全文未完整召回
  - performance_staff: 关键人员证据缺失
""".strip(),
    )
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="cluster-1",
                title="非进口项目中出现国外标准/国外部件相关表述，存在采购政策口径、技术标准口径、验收口径不一致风险",
                severity="高风险",
                review_type="采购政策/技术标准/验收口径一致性审查",
                source_locations=["政策条款：二、申请人的资格要求", "技术条款：1.规格及技术参数"],
                source_excerpts=["政策口径：不接受投标人选用进口产品", "外标引用：符合 BS EN 61000 及 EN55011 标准"],
                risk_judgment=["存在口径不一致风险。"],
                legal_basis=["需人工复核"],
                rectification=["补充等效标准说明。"],
                topics=["policy", "technical_standard"],
            )
        ],
        metadata={
            "pending_review_items": [
                {
                    "title": "具体资格条款缺失，无法判断是否存在排斥性要求",
                    "review_type": "资格条件",
                    "topic": "qualification",
                    "source_location": "资格要求章节",
                    "source_excerpt": "资格条件内容未完整展开",
                    "reason": "当前仅召回到摘要级证据，需补充全文条款后复核。",
                }
            ],
            "excluded_risks": [
                {"title": "付款条款关键数据缺失，无法评估公平性与节点衔接"},
                {"title": "澄清截止时间未明确填写"},
            ],
        },
    )

    report = assemble_v2_report("sample.docx", baseline, V2StageArtifact(name="structure", metadata={}), [], comparison)
    summary_section = report.split("## 综合判断", 1)[1]

    assert "付款条款关键数据缺失，无法评估公平性与节点衔接" not in summary_section
    assert "澄清截止时间未明确填写" not in summary_section
    assert "qualification:" not in summary_section
    assert "performance_staff:" not in summary_section
    assert "非进口项目中出现国外标准/国外部件相关表述，存在采购政策口径、技术标准口径、验收口径不一致风险" in summary_section
    assert "具体资格条款缺失，无法判断是否存在排斥性要求" in report
    assert "- 需人工复核事项：" in summary_section


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
    assert "非进口项目中出现国外标准/国外部件相关表述，存在采购政策口径、技术标准口径、验收口径不一致风险" in titles
    assert comparison.metadata["failure_reason_codes"] == ["policy_technical_inconsistency"]
    assert comparison.metadata["comparison_failure_reason_codes"] == ["policy_technical_inconsistency"]


def test_compare_review_artifacts_adds_star_marker_missing_risk() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖评审规则。",
            metadata={
                "selected_sections": [{"title": "评审规则合理性"}],
                "missing_evidence": [],
                "structured_signals": {
                    "star_required_for_gb_non_t": True,
                    "star_required_for_mandatory_standard": True,
                    "star_rule_sections": [{"title": "评审规则合理性"}],
                    "star_rule_sentences": ["评审规则合理性-含有GB（不含GB/T）或国家强制性标准的描述中需含有★号。"],
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
                "selected_sections": [{"title": "1.规格及技术参数"}],
                "missing_evidence": [],
                "structured_signals": {
                    "standard_clause_flags": [
                        {
                            "title": "1.规格及技术参数",
                            "section_id": "20-24",
                            "clause_text": "（7）燃油标准，采用0号轻柴油，符合 GB252 或 BS2869 标准。",
                            "contains_gb_non_t": True,
                            "contains_gbt": False,
                            "contains_mandatory_standard": False,
                            "has_star_marker": False,
                        }
                    ]
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    titles = [cluster.title for cluster in comparison.clusters]
    assert "强制性标准条款未按评审规则标注★，可能导致实质性响应边界不清" in titles
    assert comparison.metadata["failure_reason_codes"] == ["star_marker_missing_for_mandatory_standard"]
    report = assemble_v2_report("sample.docx", baseline, V2StageArtifact(name="structure", metadata={}), topics, comparison)
    assert "强制性标准条款未按评审规则标注★，可能导致实质性响应边界不清" in report
    assert "问题定性：中风险" in report
    assert "审查类型：评审规则一致性 / 实质性条款标识完整性" in report
    assert "若该条款属于实质性要求，应在条款前明确加注 ★。" in report


def test_compare_review_artifacts_does_not_add_star_marker_risk_for_gbt_or_starred_clause() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖评审规则。",
            metadata={
                "selected_sections": [{"title": "评审规则合理性"}],
                "missing_evidence": [],
                "structured_signals": {
                    "star_required_for_gb_non_t": True,
                    "star_required_for_mandatory_standard": True,
                    "star_rule_sections": [{"title": "评审规则合理性"}],
                    "star_rule_sentences": ["评审规则合理性-含有GB（不含GB/T）或国家强制性标准的描述中需含有★号。"],
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
                "selected_sections": [{"title": "1.规格及技术参数"}],
                "missing_evidence": [],
                "structured_signals": {
                    "standard_clause_flags": [
                        {
                            "title": "1.规格及技术参数",
                            "section_id": "20-24",
                            "clause_text": "电磁兼容性能应满足 GB/T 17626 标准。",
                            "contains_gb_non_t": False,
                            "contains_gbt": True,
                            "contains_mandatory_standard": False,
                            "has_star_marker": False,
                        },
                        {
                            "title": "1.规格及技术参数",
                            "section_id": "25-27",
                            "clause_text": "★（7）燃油标准，采用0号轻柴油，符合 GB252 标准。",
                            "contains_gb_non_t": True,
                            "contains_gbt": False,
                            "contains_mandatory_standard": False,
                            "has_star_marker": True,
                        },
                    ]
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    assert comparison.metadata["failure_reason_codes"] == []
    assert all(cluster.title != "强制性标准条款未按评审规则标注★，可能导致实质性响应边界不清" for cluster in comparison.clusters)


def test_compare_review_artifacts_adds_acceptance_plan_in_scoring_risk() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖评分规则。",
            metadata={
                "selected_sections": [{"title": "第六章 评分办法"}],
                "missing_evidence": [],
                "structured_signals": {
                    "acceptance_plan_forbidden_in_scoring": True,
                    "acceptance_plan_rule_sections": [{"title": "第一章 评审规则", "section_id": "1-5"}],
                    "acceptance_plan_rule_sentences": ["评审规则合规性-不得将项目验收方案作为评审因素。"],
                    "scoring_contains_acceptance_plan": True,
                    "acceptance_plan_scoring_sections": [{"title": "第六章 评分办法", "section_id": "20-30"}],
                    "acceptance_plan_scoring_sentences": [
                        "评审内容：投标人针对本项目提供施工组织方案、项目验收移交衔接方案及安全保障措施。",
                        "评审标准：方案每体现1点加10分，最高得30分。"
                    ],
                    "acceptance_plan_linked_to_score": True,
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    cluster = next(
        item for item in comparison.clusters if item.title == "将项目验收方案纳入评审因素，违反评审规则合规性要求"
    )
    assert cluster.severity == "中高风险"
    assert cluster.need_manual_review is False
    assert cluster.review_type == "评分因素合规性 / 评审规则设置合法性"
    assert cluster.source_locations == ["评审规则：第一章 评审规则；评分条款：第六章 评分办法"]
    assert "项目验收移交衔接方案" in cluster.source_excerpts[0]
    assert "最高得30分" in cluster.source_excerpts[0]
    assert "需人工复核" not in cluster.legal_basis
    assert comparison.metadata["failure_reason_codes"] == ["acceptance_plan_in_scoring_forbidden"]
    report = assemble_v2_report("sample.docx", baseline, V2StageArtifact(name="structure", metadata={}), topics, comparison)
    assert "将项目验收方案纳入评审因素，违反评审规则合规性要求" in report
    assert "问题定性：中高风险" in report
    assert "将验收方案、验收资料移交安排从评分因素中删除。" in report


def test_compare_review_artifacts_does_not_add_acceptance_plan_risk_for_non_scoring_acceptance_clause() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖评分规则。",
            metadata={
                "selected_sections": [{"title": "第六章 评分办法"}],
                "missing_evidence": [],
                "structured_signals": {
                    "acceptance_plan_forbidden_in_scoring": True,
                    "acceptance_plan_rule_sections": [{"title": "第一章 评审规则", "section_id": "1-5"}],
                    "acceptance_plan_rule_sentences": ["评审规则合规性-不得将项目验收方案作为评审因素。"],
                    "scoring_contains_acceptance_plan": False,
                    "acceptance_plan_scoring_sections": [],
                    "acceptance_plan_scoring_sentences": ["评分标准：仅对施工组织方案、安全保障措施评分，最高得30分。"],
                    "acceptance_plan_linked_to_score": False,
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    assert comparison.metadata["failure_reason_codes"] == []
    assert all(cluster.title != "将项目验收方案纳入评审因素，违反评审规则合规性要求" for cluster in comparison.clusters)


def test_compare_review_artifacts_adds_acceptance_plan_risk_for_strong_business_expression() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖评分规则。",
            metadata={
                "selected_sections": [{"title": "第六章 评分办法"}],
                "missing_evidence": [],
                "structured_signals": {
                    "acceptance_plan_forbidden_in_scoring": True,
                    "acceptance_plan_rule_sections": [{"title": "第一章 评审规则", "section_id": "1-5"}],
                    "acceptance_plan_rule_sentences": ["评审规则合规性-不得将项目验收方案作为评审因素。"],
                    "scoring_contains_acceptance_plan": True,
                    "acceptance_plan_scoring_sections": [{"title": "第六章 评分办法", "section_id": "20-42"}],
                    "acceptance_plan_scoring_sentences": [
                        "评审内容：投标人提供的安装、检测、项目验收方案及培训计划。",
                        "提供项目验收方案设计、验收标准及验收流程安排。",
                        "验收资料准备节点明确、流程衔接合理，能体现项目验收组织能力，评价为优得60分；评价为良得30分；评价为中得10分；评价为差，不得分。"
                    ],
                    "acceptance_plan_linked_to_score": True,
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    cluster = next(
        item for item in comparison.clusters if item.title == "将项目验收方案纳入评审因素，违反评审规则合规性要求"
    )
    assert "项目验收方案设计" in cluster.source_excerpts[0]
    assert "验收标准" in cluster.source_excerpts[0]
    assert "验收流程安排" in cluster.source_excerpts[0]
    assert "项目验收组织能力" in cluster.source_excerpts[0]
    assert "评价为优得60分" in cluster.source_excerpts[0]
    assert comparison.metadata["failure_reason_codes"] == ["acceptance_plan_in_scoring_forbidden"]


def test_compare_review_artifacts_adds_payment_terms_in_scoring_risk() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖评分规则。",
            metadata={
                "selected_sections": [{"title": "第六章 评分办法"}],
                "missing_evidence": [],
                "structured_signals": {
                    "payment_terms_forbidden_in_scoring": True,
                    "payment_terms_rule_sections": [{"title": "第一章 评审规则", "section_id": "1-5"}],
                    "payment_terms_rule_sentences": ["评审规则合规性-不得将付款方式作为评审因素。"],
                    "scoring_contains_payment_terms": True,
                    "payment_terms_scoring_sections": [{"title": "第六章 评分办法", "section_id": "20-34"}],
                    "payment_terms_scoring_sentences": [
                        "评分标准：全部满足要求的得80分。",
                        "付款周期短于招标文件要求或预付款比例更有利于采购人资金安排的，每项加10分，最高加20分。"
                    ],
                    "payment_terms_linked_to_score": True,
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    cluster = next(
        item for item in comparison.clusters if item.title == "将付款方式纳入评审因素，违反评审规则合规性要求"
    )
    assert cluster.severity == "中高风险"
    assert cluster.review_type == "评分因素合规性 / 商务评分规则合法性"
    assert "付款周期短于招标文件要求" in cluster.source_excerpts[0]
    assert "预付款比例更有利于采购人资金安排" in cluster.source_excerpts[0]
    assert "每项加10分" in cluster.source_excerpts[0]
    assert comparison.metadata["failure_reason_codes"] == ["payment_terms_in_scoring_forbidden"]
    report = assemble_v2_report("sample.docx", baseline, V2StageArtifact(name="structure", metadata={}), topics, comparison)
    assert "将付款方式纳入评审因素，违反评审规则合规性要求" in report
    assert "问题定性：中高风险" in report
    assert "将付款周期、预付款比例等内容从评分因素中删除。" in report


def test_compare_review_artifacts_does_not_add_payment_terms_risk_for_contract_payment_only() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖评分规则。",
            metadata={
                "selected_sections": [{"title": "第六章 评分办法"}],
                "missing_evidence": [],
                "structured_signals": {
                    "payment_terms_forbidden_in_scoring": True,
                    "payment_terms_rule_sections": [{"title": "第一章 评审规则", "section_id": "1-5"}],
                    "payment_terms_rule_sentences": ["评审规则合规性-不得将付款方式作为评审因素。"],
                    "scoring_contains_payment_terms": False,
                    "payment_terms_scoring_sections": [],
                    "payment_terms_scoring_sentences": ["评分标准：仅对履约能力、交付保障进行评分，最高得100分。"],
                    "payment_terms_linked_to_score": False,
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    assert comparison.metadata["failure_reason_codes"] == []
    assert all(cluster.title != "将付款方式纳入评审因素，违反评审规则合规性要求" for cluster in comparison.clusters)


def test_compare_review_artifacts_adds_gifts_or_unrelated_goods_risk() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖评分规则。",
            metadata={
                "selected_sections": [{"title": "第六章 评分办法"}],
                "missing_evidence": [],
                "structured_signals": {
                    "gifts_or_unrelated_goods_forbidden_in_scoring": True,
                    "gifts_or_goods_rule_sections": [{"title": "第一章 评审规则", "section_id": "1-5"}],
                    "gifts_or_goods_rule_sentences": ["评审规则合规性-不得要求提供赠品、回扣或者与采购无关的其他商品、服务。"],
                    "scoring_contains_gifts_or_unrelated_goods": True,
                    "gifts_or_goods_scoring_sections": [{"title": "第六章 评分办法", "section_id": "20-34"}],
                    "gifts_or_goods_scoring_sentences": [
                        "额外向采购人值班室赠送台式电脑、打印机各1套的，得100分。",
                        "仅承诺1.5小时（90分钟）内到达现场处理问题的，得50分；其他情况不得分。"
                    ],
                    "gifts_or_goods_linked_to_score": True,
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    cluster = next(
        item for item in comparison.clusters if item.title == "评分项中要求赠送非项目物资，存在明显不当加分和评审合规风险"
    )
    assert cluster.severity == "高风险"
    assert cluster.review_type == "评分因素合规性 / 赠送非项目物资评分"
    assert "赠送台式电脑" in cluster.source_excerpts[0]
    assert "得100分" in cluster.source_excerpts[0]
    assert comparison.metadata["failure_reason_codes"] == ["gifts_or_unrelated_goods_in_scoring_forbidden"]
    report = assemble_v2_report("sample.docx", baseline, V2StageArtifact(name="structure", metadata={}), topics, comparison)
    assert "评分项中要求赠送非项目物资，存在明显不当加分和评审合规风险" in report
    assert "问题定性：高风险" in report
    assert "删除赠送台式电脑、打印机、办公设备等与项目采购无关物资的加分条件。" in report


def test_compare_review_artifacts_does_not_add_gifts_risk_for_service_response_only() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖评分规则。",
            metadata={
                "selected_sections": [{"title": "第六章 评分办法"}],
                "missing_evidence": [],
                "structured_signals": {
                    "gifts_or_unrelated_goods_forbidden_in_scoring": True,
                    "gifts_or_goods_rule_sections": [{"title": "第一章 评审规则", "section_id": "1-5"}],
                    "gifts_or_goods_rule_sentences": ["评审规则合规性-不得要求提供赠品、回扣或者与采购无关的其他商品、服务。"],
                    "scoring_contains_gifts_or_unrelated_goods": False,
                    "gifts_or_goods_scoring_sections": [],
                    "gifts_or_goods_scoring_sentences": ["承诺1小时内到达现场处理问题的，得100分。"],
                    "gifts_or_goods_linked_to_score": False,
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    assert comparison.metadata["failure_reason_codes"] == []
    assert all(cluster.title != "评分项中要求赠送非项目物资，存在明显不当加分和评审合规风险" for cluster in comparison.clusters)


def test_compare_review_artifacts_does_not_add_gifts_risk_for_procurement_subject_goods() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖评分规则。",
            metadata={
                "selected_sections": [{"title": "第六章 评分办法"}],
                "missing_evidence": [],
                "structured_signals": {
                    "gifts_or_unrelated_goods_forbidden_in_scoring": True,
                    "gifts_or_goods_rule_sections": [{"title": "第一章 评审规则", "section_id": "1-5"}],
                    "gifts_or_goods_rule_sentences": ["评审规则合规性-不得要求提供赠品、回扣或者与采购无关的其他商品、服务。"],
                    "scoring_contains_gifts_or_unrelated_goods": False,
                    "gifts_or_goods_scoring_sections": [],
                    "gifts_or_goods_scoring_sentences": ["本项目采购标的包括台式电脑、打印机及配套安装服务。评审标准：完全满足技术参数要求的得100分。"],
                    "gifts_or_goods_linked_to_score": False,
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    assert comparison.metadata["failure_reason_codes"] == []
    assert all(cluster.title != "评分项中要求赠送非项目物资，存在明显不当加分和评审合规风险" for cluster in comparison.clusters)


def test_compare_review_artifacts_adds_gifts_risk_for_hidden_related_service_bundle() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖评分规则。",
            metadata={
                "selected_sections": [{"title": "第六章 评分办法"}],
                "missing_evidence": [],
                "structured_signals": {
                    "gifts_or_unrelated_goods_forbidden_in_scoring": True,
                    "gifts_or_goods_rule_sections": [{"title": "第一章 评审规则", "section_id": "1-5"}],
                    "gifts_or_goods_rule_sentences": ["评审规则合规性-不得要求提供赠品、回扣或者与采购无关的其他商品、服务。"],
                    "scoring_contains_gifts_or_unrelated_goods": True,
                    "gifts_or_goods_scoring_sections": [{"title": "第六章 评分办法", "section_id": "20-34"}],
                    "gifts_or_goods_scoring_sentences": [
                        "提供投标人承担过类似项目的销售安装业绩，且在项目履约中包含值班室办公设备配置或会议保障等综合服务内容的，每提供1个业绩得20分。",
                        "其它情况不得分，本项最高得100分。"
                    ],
                    "gifts_or_goods_linked_to_score": True,
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    cluster = next(
        item for item in comparison.clusters if item.title == "评分项中要求赠送非项目物资，存在明显不当加分和评审合规风险"
    )
    assert "值班室办公设备配置" in cluster.source_excerpts[0]
    assert "会议保障等综合服务内容" in cluster.source_excerpts[0]
    assert comparison.metadata["failure_reason_codes"] == ["gifts_or_unrelated_goods_in_scoring_forbidden"]


def test_compare_review_artifacts_does_not_add_gifts_risk_for_necessary_accessories() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖评分规则。",
            metadata={
                "selected_sections": [{"title": "第六章 评分办法"}],
                "missing_evidence": [],
                "structured_signals": {
                    "gifts_or_unrelated_goods_forbidden_in_scoring": True,
                    "gifts_or_goods_rule_sections": [{"title": "第一章 评审规则", "section_id": "1-5"}],
                    "gifts_or_goods_rule_sentences": ["评审规则合规性-不得要求提供赠品、回扣或者与采购无关的其他商品、服务。"],
                    "scoring_contains_gifts_or_unrelated_goods": False,
                    "gifts_or_goods_scoring_sections": [],
                    "gifts_or_goods_scoring_sentences": ["承诺无偿提供安装辅材、调试辅材和随机附件的，得20分。"],
                    "gifts_or_goods_linked_to_score": False,
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    assert comparison.metadata["failure_reason_codes"] == []
    assert all(cluster.title != "评分项中要求赠送非项目物资，存在明显不当加分和评审合规风险" for cluster in comparison.clusters)


def test_compare_review_artifacts_adds_specific_cert_or_supplier_risk() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖评分规则。",
            metadata={
                "selected_sections": [{"title": "第六章 评分办法"}],
                "missing_evidence": [],
                "structured_signals": {
                    "specific_brand_or_supplier_forbidden_in_scoring": True,
                    "specific_brand_or_supplier_rule_sections": [{"title": "第一章 评审规则", "section_id": "1-5"}],
                    "specific_brand_or_supplier_rule_sentences": ["评审规则合理性-不得限定或者指定特定的专利、商标、品牌或者供应商。"],
                    "scoring_contains_specific_cert_or_supplier_signal": True,
                    "specific_cert_or_supplier_scoring_sections": [{"title": "第六章 评分办法", "section_id": "20-38"}],
                    "specific_cert_or_supplier_evidence": [
                        "柴油发电机组制造商的投标的柴油发电机组，具备以下认证的。",
                        "具备有效期内省级标准协会颁发的省级采用国际标准产品确认证书和采用国际标准产品标志证书的，每具备一项得40分。",
                        "具备CNAS中国认可产品标志证书的，得20分，以上累计最高得分为100分。"
                    ],
                    "specific_cert_or_supplier_score_linked": True,
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    cluster = next(item for item in comparison.clusters if item.title == "以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险")
    assert cluster.severity == "高风险"
    assert cluster.review_type == "评分因素合规性 / 限定特定认证或发证机构"
    assert "制造商" in cluster.source_excerpts[0]
    assert "CNAS中国认可产品标志证书" in cluster.source_excerpts[0]
    assert comparison.metadata["failure_reason_codes"] == ["specific_brand_or_supplier_in_scoring_forbidden"]


def test_compare_review_artifacts_does_not_add_specific_cert_or_supplier_risk_for_generic_proof() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖评分规则。",
            metadata={
                "selected_sections": [{"title": "第六章 评分办法"}],
                "missing_evidence": [],
                "structured_signals": {
                    "specific_brand_or_supplier_forbidden_in_scoring": True,
                    "specific_brand_or_supplier_rule_sections": [{"title": "第一章 评审规则", "section_id": "1-5"}],
                    "specific_brand_or_supplier_rule_sentences": ["评审规则合理性-不得限定或者指定特定的专利、商标、品牌或者供应商。"],
                    "scoring_contains_specific_cert_or_supplier_signal": False,
                    "specific_cert_or_supplier_scoring_sections": [],
                    "specific_cert_or_supplier_evidence": ["评分标准：投标产品提供合格证、检验报告及国家规定的法定资质证明材料的，视为满足基本要求。"],
                    "specific_cert_or_supplier_score_linked": False,
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    assert comparison.metadata["failure_reason_codes"] == []
    assert all(cluster.title != "以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险" for cluster in comparison.clusters)


def test_compare_review_artifacts_adds_acceptance_testing_cost_shift_risk() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="acceptance",
            summary="验收专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖验收条款。",
            metadata={
                "selected_sections": [{"title": "第五章 验收与交付要求"}],
                "missing_evidence": [],
                "structured_signals": {
                    "acceptance_testing_cost_forbidden_to_bidder": True,
                    "acceptance_testing_cost_rule_sections": [{"title": "第一章 需求合规规则", "section_id": "1-4"}],
                    "acceptance_testing_cost_rule_sentences": ["需求合规性-不得要求中标人承担验收产生的检测费用。"],
                    "demand_contains_acceptance_testing_cost_signal": True,
                    "acceptance_testing_cost_sections": [{"title": "第五章 验收与交付要求", "section_id": "20-34"}],
                    "acceptance_testing_cost_evidence": [
                        "投标人的投标总价包括检测、相关部门验收、验收合格之前等所有含税费用。",
                        "投标人应自行计入系统正常、合法、安全运行及使用所必需的一切费用。"
                    ],
                    "acceptance_testing_cost_shifted_to_bidder": True,
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    cluster = next(item for item in comparison.clusters if item.title == "验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险")
    assert cluster.severity == "中风险"
    assert cluster.review_type == "需求合规性 / 验收费用边界审查"
    assert "相关部门验收" in cluster.source_excerpts[0]
    assert comparison.metadata["failure_reason_codes"] == ["acceptance_testing_cost_shifted_to_bidder"]


def test_compare_review_artifacts_adds_cancelled_or_non_mandatory_qualification_gate_risk() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="qualification",
            summary="资格条件专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖资格条件。",
            metadata={
                "selected_sections": [{"title": "第二章 投标人资格要求"}],
                "missing_evidence": [],
                "structured_signals": {
                    "qualification_requirement_present": True,
                    "qualification_requirement_sections": [{"title": "第二章 投标人资格要求", "section_id": "10-18"}],
                    "qualification_requirement_sentences": ["投标人资格要求：投标人须具备省级主管部门已明令取消的行业资质证书。"],
                    "cancelled_or_non_mandatory_qualification_signal": True,
                    "cancelled_or_non_mandatory_qualification_sections": [{"title": "第二章 投标人资格要求", "section_id": "10-18"}],
                    "cancelled_or_non_mandatory_qualification_sentences": ["投标人须具备省级主管部门已明令取消的行业资质证书。"],
                    "cancelled_or_non_mandatory_qualification_used_as_gate": True,
                    "cancelled_or_non_mandatory_qualification_gate_sections": [{"title": "第二章 投标人资格要求", "section_id": "10-18"}],
                    "cancelled_or_non_mandatory_qualification_gate_sentences": ["未提供上述资质证书的，资格审查不通过。"],
                    "cancelled_or_non_mandatory_qualification_prohibition_context": False,
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    cluster = next(
        item
        for item in comparison.clusters
        if item.title == "将已取消或非强制资质资格作为资格条件，存在设置不当准入门槛风险"
    )
    assert cluster.severity == "高风险"
    assert cluster.review_type == "资格条件合规性 / 不当准入门槛"
    assert "已明令取消" in cluster.source_excerpts[0]
    assert comparison.metadata["failure_reason_codes"] == ["cancelled_or_non_mandatory_qualification_as_gate"]


def test_compare_review_artifacts_adds_cancelled_or_non_mandatory_credential_in_scoring_risk() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖评分办法。",
            metadata={
                "selected_sections": [{"title": "第六章 评分办法"}],
                "missing_evidence": [],
                "structured_signals": {
                    "scoring_requirement_present": True,
                    "scoring_requirement_sections": [{"title": "第六章 评分办法", "section_id": "18-28"}],
                    "scoring_requirement_sentences": ["评分内容：投标人具备国务院已明令取消的资质、资格、认证的，每项加5分，最高加15分。"],
                    "cancelled_or_non_mandatory_scoring_credential_signal": True,
                    "cancelled_or_non_mandatory_scoring_credential_sections": [{"title": "第六章 评分办法", "section_id": "18-28"}],
                    "cancelled_or_non_mandatory_scoring_credential_sentences": ["投标人具备国务院已明令取消的资质、资格、认证的，每项加5分，最高加15分。"],
                    "cancelled_or_non_mandatory_scoring_credential_linked_to_score": True,
                    "cancelled_or_non_mandatory_scoring_credential_linked_sections": [{"title": "第六章 评分办法", "section_id": "18-28"}],
                    "cancelled_or_non_mandatory_scoring_credential_linked_sentences": [
                        "评分内容：投标人具备国务院已明令取消的资质、资格、认证的，每项加5分，最高加15分。",
                        "评审委员会按得分情况进行档次评价。",
                    ],
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    cluster = next(
        item
        for item in comparison.clusters
        if item.title == "将已取消或非强制资质资格认证作为评审因素，存在评分设置不合规风险"
    )
    assert cluster.severity == "高风险"
    assert cluster.review_type == "评分因素合规性 / 不当评分门槛"
    assert "已明令取消" in cluster.source_excerpts[0]
    assert comparison.metadata["failure_reason_codes"] == ["cancelled_or_non_mandatory_credential_in_scoring"]


def test_compare_review_artifacts_prioritizes_standard_titles_over_generic_same_class_titles() -> None:
    baseline = V2StageArtifact(
        name="baseline",
        content="""
# 招标文件合规审查结果

审查对象：`sample.docx`

## 风险点1：评分标准中“安装、检测、验收、培训计划”存在主观性描述且分值逻辑错误

- 问题定性：中风险
- 审查类型：评分因素不相关/评分标准不明确
- 原文位置：第六章 评分办法
- 原文摘录：安装、检测、验收、培训计划，评价为优得60分。
- 风险判断：
  - 评分逻辑存在主观性。
- 法律/政策依据：
  - 需人工复核
- 整改建议：
  - 补充量化口径。
""".strip(),
    )
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题完成。",
            risk_points=[
                RiskPoint(
                    title="制造商资质证书评分项指向特定认证，具有排他性",
                    severity="高风险",
                    review_type="评分项合规性审查",
                    source_location="第六章 评分办法",
                    source_excerpt="省级标准协会颁发证书每具备一项得40分。",
                    risk_judgment=["评分项指向特定认证。"],
                    legal_basis=["需人工复核"],
                    rectification=["删除特定认证评分。"],
                )
            ],
            need_manual_review=False,
            coverage_note="已覆盖评分规则。",
            metadata={
                "selected_sections": [{"title": "第六章 评分办法"}],
                "missing_evidence": [],
                "structured_signals": {
                    "acceptance_plan_forbidden_in_scoring": True,
                    "acceptance_plan_rule_sections": [{"title": "第一章 评审规则", "section_id": "1-5"}],
                    "acceptance_plan_rule_sentences": ["评审规则合规性-不得将项目验收方案作为评审因素。"],
                    "scoring_contains_acceptance_plan": True,
                    "acceptance_plan_scoring_sections": [{"title": "第六章 评分办法", "section_id": "20-42"}],
                    "acceptance_plan_scoring_sentences": ["安装、检测、验收、培训计划，评价为优得60分。"],
                    "acceptance_plan_linked_to_score": True,
                    "specific_brand_or_supplier_forbidden_in_scoring": True,
                    "specific_brand_or_supplier_rule_sections": [{"title": "第一章 评审规则", "section_id": "1-5"}],
                    "specific_brand_or_supplier_rule_sentences": ["评审规则合理性-不得限定或者指定特定的专利、商标、品牌或者供应商。"],
                    "scoring_contains_specific_cert_or_supplier_signal": True,
                    "specific_cert_or_supplier_scoring_sections": [{"title": "第六章 评分办法", "section_id": "50-56"}],
                    "specific_cert_or_supplier_evidence": ["省级标准协会颁发证书每具备一项得40分。"],
                    "specific_cert_or_supplier_score_linked": True,
                },
            },
        ),
        TopicReviewArtifact(
            topic="acceptance",
            summary="验收专题完成。",
            risk_points=[
                RiskPoint(
                    title="将验收产生的检测费用笼统计入投标人承担范围，存在需求条款合规风险",
                    severity="高风险",
                    review_type="需求条款合规性",
                    source_location="第五章 验收与交付要求",
                    source_excerpt="交钥匙项目总价包括检测、相关部门验收等一切费用。",
                    risk_judgment=["检测费用被笼统计入。"],
                    legal_basis=["需人工复核"],
                    rectification=["区分验收检测费用。"],
                )
            ],
            need_manual_review=False,
            coverage_note="已覆盖验收条款。",
            metadata={
                "selected_sections": [{"title": "第五章 验收与交付要求"}],
                "missing_evidence": [],
                "structured_signals": {
                    "acceptance_testing_cost_forbidden_to_bidder": True,
                    "acceptance_testing_cost_rule_sections": [{"title": "第一章 需求合规规则", "section_id": "1-4"}],
                    "acceptance_testing_cost_rule_sentences": ["需求合规性-不得要求中标人承担验收产生的检测费用。"],
                    "demand_contains_acceptance_testing_cost_signal": True,
                    "acceptance_testing_cost_sections": [{"title": "第五章 验收与交付要求", "section_id": "20-34"}],
                    "acceptance_testing_cost_evidence": ["交钥匙项目总价包括检测、相关部门验收等一切费用。"],
                    "acceptance_testing_cost_shifted_to_bidder": True,
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    titles = [cluster.title for cluster in comparison.clusters]
    assert titles[:3] == [
        "将项目验收方案纳入评审因素，违反评审规则合规性要求",
        "以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险",
        "验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险",
    ]
    assert titles.count("以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险") == 1
    assert "评分标准中“安装、检测、验收、培训计划”存在主观性描述且分值逻辑错误" not in titles
    assert "制造商资质证书评分项指向特定认证，具有排他性" not in titles
    assert "将验收产生的检测费用笼统计入投标人承担范围，存在需求条款合规风险" not in titles
    assert "将验收产生的检测费用及相关部门验收费用笼统计入投标人承担范围，存在需求条款合规风险" not in titles


def test_compare_review_artifacts_does_not_add_acceptance_testing_cost_shift_risk_for_selfcheck() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="acceptance",
            summary="验收专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖验收条款。",
            metadata={
                "selected_sections": [{"title": "第五章 验收与交付要求"}],
                "missing_evidence": [],
                "structured_signals": {
                    "acceptance_testing_cost_forbidden_to_bidder": True,
                    "acceptance_testing_cost_rule_sections": [{"title": "第一章 需求合规规则", "section_id": "1-4"}],
                    "acceptance_testing_cost_rule_sentences": ["需求合规性-不得要求中标人承担验收产生的检测费用。"],
                    "demand_contains_acceptance_testing_cost_signal": False,
                    "acceptance_testing_cost_sections": [],
                    "acceptance_testing_cost_evidence": [
                        "供应商负责安装、调试、试运行及出厂检验、自检工作，采购验收阶段检测由采购人依法另行委托。"
                    ],
                    "acceptance_testing_cost_shifted_to_bidder": False,
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    assert comparison.metadata["failure_reason_codes"] == []
    assert all(cluster.title != "验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险" for cluster in comparison.clusters)


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


def test_compare_review_artifacts_prefers_signal_matched_locations_and_compact_excerpts() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="policy",
            summary="政策专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖政策条款。",
            metadata={
                "selected_sections": [
                    {"title": "第一章 招标公告"},
                    {"title": "二、申请人的资格要求"},
                    {"title": "投标须知"},
                ],
                "missing_evidence": [],
                "structured_signals": {
                    "import_policy": "reject_import",
                    "import_policy_reject_phrases": ["不接受投标人选用进口产品参与投标"],
                    "import_policy_accept_phrases": [],
                    "import_policy_sections": [{"title": "二、申请人的资格要求"}],
                    "import_policy_sentences": ["不接受投标人选用进口产品参与投标。"],
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
                "selected_sections": [
                    {"title": "投标技术响应"},
                    {"title": "1.规格及技术参数"},
                    {"title": "招标技术要求"},
                ],
                "missing_evidence": [],
                "structured_signals": {
                    "foreign_standard_refs": ["BS EN 61000", "EN55011"],
                    "cn_standard_refs": ["GB/T 17626"],
                    "has_equivalent_standard_clause": False,
                    "standard_system_mix": "mixed_cn_foreign",
                    "foreign_standard_sections": [{"title": "1.规格及技术参数"}],
                    "foreign_standard_sentences": ["1.14 电磁影响：符合 BS EN 61000、GB/T 17626 及 EN55011 标准。"],
                    "cn_standard_sections": [{"title": "1.规格及技术参数"}],
                    "cn_standard_sentences": ["1.14 电磁影响：符合 BS EN 61000、GB/T 17626 及 EN55011 标准。"],
                },
            },
        ),
    ]
    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    cluster = comparison.clusters[0]

    assert cluster.source_locations == ["政策条款：二、申请人的资格要求；技术条款：1.规格及技术参数"]
    assert "招标公告" not in cluster.source_locations[0]
    assert "投标技术响应" not in cluster.source_locations[0]
    assert cluster.source_excerpts == [
        "政策口径：不接受投标人选用进口产品参与投标\n\n外标引用：1.14 电磁影响：符合 BS EN 61000、GB/T 17626 及 EN55011 标准。\n\n国标/行标：1.14 电磁影响：符合 BS EN 61000、GB/T 17626 及 EN55011 标准。"
    ]


def test_compare_review_artifacts_prefers_policy_topic_locations_over_qualification_and_procedure() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="qualification",
            summary="资格专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖资格条款。",
            metadata={
                "selected_sections": [{"title": "5.2 投标人资格要求"}],
                "missing_evidence": [],
                "structured_signals": {
                    "import_policy": "reject_import",
                    "import_policy_reject_phrases": ["不接受投标人选用进口产品"],
                    "import_policy_sections": [{"title": "5.2 投标人资格要求"}],
                    "import_policy_sentences": ["不接受投标人选用进口产品"],
                },
            },
        ),
        TopicReviewArtifact(
            topic="procedure",
            summary="程序专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖程序条款。",
            metadata={
                "selected_sections": [{"title": "六、其他补充事宜"}],
                "missing_evidence": [],
                "structured_signals": {
                    "import_policy": "reject_import",
                    "import_policy_reject_phrases": ["不接受投标人选用进口产品"],
                    "import_policy_sections": [{"title": "六、其他补充事宜"}],
                    "import_policy_sentences": ["不接受投标人选用进口产品"],
                },
            },
        ),
        TopicReviewArtifact(
            topic="policy",
            summary="政策专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖政策条款。",
            metadata={
                "selected_sections": [{"title": "二、申请人的资格要求"}],
                "missing_evidence": [],
                "structured_signals": {
                    "import_policy": "reject_import",
                    "import_policy_reject_phrases": ["不接受投标人选用进口产品"],
                    "import_policy_sections": [{"title": "二、申请人的资格要求"}],
                    "import_policy_sentences": ["不接受投标人选用进口产品"],
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
                "selected_sections": [{"title": "1.规格及技术参数"}],
                "missing_evidence": [],
                "structured_signals": {
                    "foreign_standard_refs": ["BS EN 61000"],
                    "cn_standard_refs": ["GB/T 17626"],
                    "has_equivalent_standard_clause": False,
                    "foreign_standard_sections": [{"title": "1.规格及技术参数"}],
                    "foreign_standard_sentences": ["1.14 电磁影响：符合 BS EN 61000、GB/T 17626 标准。"],
                    "cn_standard_sections": [{"title": "1.规格及技术参数"}],
                    "cn_standard_sentences": ["1.14 电磁影响：符合 BS EN 61000、GB/T 17626 标准。"],
                },
            },
        ),
    ]
    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    cluster = next(
        item
        for item in comparison.clusters
        if item.title == "非进口项目中出现国外标准/国外部件相关表述，存在采购政策口径、技术标准口径、验收口径不一致风险"
    )
    assert cluster.source_locations == ["政策条款：二、申请人的资格要求；技术条款：1.规格及技术参数"]


def test_compare_review_artifacts_adds_star_marker_missing_risk() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖评审规则。",
            metadata={
                "selected_sections": [{"title": "第一章 评审规则"}],
                "missing_evidence": [],
                "structured_signals": {
                    "star_required_for_gb_non_t": True,
                    "star_required_for_mandatory_standard": True,
                    "star_rule_sections": [{"title": "第一章 评审规则", "section_id": "1-5"}],
                    "star_rule_sentences": ["评审规则合理性-含有GB（不含GB/T）或国家强制性标准的描述中需含有★号"],
                },
            },
        ),
        TopicReviewArtifact(
            topic="technical_standard",
            summary="技术标准专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖技术条款。",
            metadata={
                "selected_sections": [{"title": "第三章 技术要求"}],
                "missing_evidence": [],
                "structured_signals": {
                    "standard_clause_flags": [
                        {
                            "section_id": "10-12",
                            "title": "第三章 技术要求",
                            "clause_text": "（7）燃油标准，采用0号轻柴油，符合 GB252 或 BS2869 标准。",
                            "contains_gb_non_t": True,
                            "contains_gbt": False,
                            "contains_mandatory_standard": False,
                            "has_star_marker": False,
                        }
                    ]
                },
            },
        ),
    ]
    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    cluster = next(
        item
        for item in comparison.clusters
        if item.title == "强制性标准条款未按评审规则标注★，可能导致实质性响应边界不清"
    )
    assert cluster.severity == "中风险"
    assert cluster.review_type == "评审规则一致性 / 实质性条款标识完整性"
    assert cluster.source_locations == ["评审规则：第一章 评审规则；技术条款：第三章 技术要求"]
    assert "GB252" in cluster.source_excerpts[0]
    assert comparison.metadata["failure_reason_codes"] == ["star_marker_missing_for_mandatory_standard"]


def test_compare_review_artifacts_does_not_add_star_marker_risk_for_gbt_or_starred_clause() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖评审规则。",
            metadata={
                "selected_sections": [{"title": "第一章 评审规则"}],
                "missing_evidence": [],
                "structured_signals": {
                    "star_required_for_gb_non_t": True,
                    "star_required_for_mandatory_standard": True,
                    "star_rule_sections": [{"title": "第一章 评审规则", "section_id": "1-5"}],
                    "star_rule_sentences": ["评审规则合理性-含有GB（不含GB/T）或国家强制性标准的描述中需含有★号"],
                },
            },
        ),
        TopicReviewArtifact(
            topic="technical_standard",
            summary="技术标准专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖技术条款。",
            metadata={
                "selected_sections": [{"title": "第三章 技术要求"}],
                "missing_evidence": [],
                "structured_signals": {
                    "standard_clause_flags": [
                        {
                            "section_id": "10-12",
                            "title": "第三章 技术要求",
                            "clause_text": "电磁兼容性能应满足 GB/T 17626 标准。",
                            "contains_gb_non_t": False,
                            "contains_gbt": True,
                            "contains_mandatory_standard": False,
                            "has_star_marker": False,
                        },
                        {
                            "section_id": "13-15",
                            "title": "第三章 技术要求",
                            "clause_text": "★燃油标准，符合 GB252 标准。",
                            "contains_gb_non_t": True,
                            "contains_gbt": False,
                            "contains_mandatory_standard": False,
                            "has_star_marker": True,
                        },
                    ]
                },
            },
        ),
    ]
    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    titles = [cluster.title for cluster in comparison.clusters]
    assert "强制性标准条款未按评审规则标注★，可能导致实质性响应边界不清" not in titles


def test_compare_review_artifacts_excludes_policy_missing_risk_when_discount_and_eco_evidence_present() -> None:
    baseline = V2StageArtifact(
        name="baseline",
        content="""
# 招标文件合规审查结果

审查对象：`sample.docx`

## 风险点1：中小企业扶持政策落实条款缺失关键执行参数

- 问题定性：中风险
- 审查类型：政策适用完整性审查
- 原文位置：第二章 其他关键信息
- 原文摘录：未发现明确价格扣除比例。
- 风险判断：
  - 需人工复核
- 法律/政策依据：
  - 需人工复核
- 整改建议：
  - 补充价格扣除比例
""".strip(),
    )
    topics = [
        TopicReviewArtifact(
            topic="policy",
            summary="政策专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖政策条款。",
            metadata={
                "selected_sections": [{"title": "第二章 其他关键信息"}],
                "missing_evidence": [],
                "structured_signals": {
                    "policy_discount_present": True,
                    "policy_discount_sentences": ["投标总价给予10%的扣除。"],
                    "eco_policy_present": True,
                    "eco_policy_sentences": ["如涉及相关品目，应提供有效节能产品认证证书。"],
                },
            },
        )
    ]
    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    assert all(cluster.title != "中小企业扶持政策落实条款缺失关键执行参数" for cluster in comparison.clusters)
    assert any(item["title"] == "中小企业扶持政策落实条款缺失关键执行参数" for item in comparison.metadata["excluded_risks"])


def test_compare_review_artifacts_moves_evidence_gap_items_to_pending_review() -> None:
    baseline = V2StageArtifact(
        name="baseline",
        content="""
# 招标文件合规审查结果

审查对象：`sample.docx`

## 风险点1：具体资格条件内容缺失，无法判断是否存在排斥性条款

- 问题定性：需人工复核
- 审查类型：资格条件审查
- 原文位置：第五章 招标公告
- 原文摘录：详见招标公告。
- 风险判断：
  - 需补充资格条件全文
- 法律/政策依据：
  - 需人工复核
- 整改建议：
  - 补充公告全文
""".strip(),
    )
    topics = [
        TopicReviewArtifact(
            topic="qualification",
            summary="资格专题仍需人工复核。",
            risk_points=[],
            need_manual_review=True,
            coverage_note="资格条件未完整召回。",
            metadata={
                "selected_sections": [{"title": "5.2 投标人资格要求"}],
                "missing_evidence": ["招标公告中投标人资格要求全文"],
                "structured_signals": {},
            },
        )
    ]
    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    assert all(cluster.title != "具体资格条件内容缺失，无法判断是否存在排斥性条款" for cluster in comparison.clusters)
    assert any(item["title"] == "具体资格条件内容缺失，无法判断是否存在排斥性条款" for item in comparison.metadata["pending_review_items"])


def test_compare_review_artifacts_excludes_contract_template_risks() -> None:
    baseline = V2StageArtifact(
        name="baseline",
        content="""
# 招标文件合规审查结果

审查对象：`sample.docx`

## 风险点1：关键合同条款数值缺失，导致付款与履约责任无法评估

- 问题定性：高风险
- 审查类型：条款完整性审查
- 原文位置：第五章 合同条款及格式
- 原文摘录：仅供参考，付款比例留空。
- 风险判断：
  - 需人工复核
- 法律/政策依据：
  - 需人工复核
- 整改建议：
  - 补充具体比例
""".strip(),
    )
    comparison = compare_review_artifacts("sample.docx", baseline, [])
    assert comparison.clusters == []
    assert any(item["title"] == "关键合同条款数值缺失，导致付款与履约责任无法评估" for item in comparison.metadata["excluded_risks"])


def test_compare_review_artifacts_excludes_explicit_template_placeholder_risks() -> None:
    baseline = V2StageArtifact(
        name="baseline",
        content="""
# 招标文件合规审查结果

审查对象：`sample.docx`

## 风险点1：验收流程关键时间节点缺失，条款不可执行

- 问题定性：中风险
- 审查类型：完整性审查
- 原文位置：第三条（二）1
- 原文摘录：甲方收到乙方自测报告后         个工作日内，有权要求乙方配合甲方完成检测；检测通过后         个工作日内组织验收；收到甲方整改通知后个工作日内完成整改。
- 风险判断：
  - 验收节点留白。
- 法律/政策依据：
  - 需人工复核
- 整改建议：
  - 补齐时间节点。
""".strip(),
    )
    comparison = compare_review_artifacts("sample.docx", baseline, [])
    assert all(cluster.title != "验收流程关键时间节点缺失，条款不可执行" for cluster in comparison.clusters)
    excluded = next(
        item for item in comparison.metadata["excluded_risks"] if item["title"] == "验收流程关键时间节点缺失，条款不可执行"
    )
    assert "模板中的时限占位符" in excluded["reason"]


def test_compare_review_artifacts_moves_ambiguous_template_placeholder_to_pending() -> None:
    baseline = V2StageArtifact(
        name="baseline",
        content="""
# 招标文件合规审查结果

审查对象：`sample.docx`

## 风险点1：验收流程关键时间节点缺失，条款不可执行

- 问题定性：中风险
- 审查类型：完整性审查
- 原文位置：验收流程说明
- 原文摘录：检测通过后         个工作日内组织初验，整改后个工作日内完成复验。
- 风险判断：
  - 验收节点留白。
- 法律/政策依据：
  - 需人工复核
- 整改建议：
  - 补齐时间节点。
""".strip(),
    )
    comparison = compare_review_artifacts("sample.docx", baseline, [])
    assert all(cluster.title != "验收流程关键时间节点缺失，条款不可执行" for cluster in comparison.clusters)
    pending = next(
        item for item in comparison.metadata["pending_review_items"] if item["title"] == "验收流程关键时间节点缺失，条款不可执行"
    )
    assert "模板留白迹象" in pending["reason"]


def test_compare_review_artifacts_moves_new_qualification_missing_variant_to_pending() -> None:
    baseline = V2StageArtifact(
        name="baseline",
        content="""
# 招标文件合规审查结果

审查对象：`sample.docx`

## 风险点1：投标人资格要求内容缺失，无法判断是否存在排斥性条款

- 问题定性：需人工复核
- 审查类型：资格条件审查
- 原文位置：第 3369 - 3422 行
- 原文摘录：5.2 投标人资格要求 参加本项目的投标人应具备的资格条件详见本项目招标公告中“投标人资格要求”的内容。
- 风险判断：
  - 当前仅承接到公告引用，无法确认资格门槛。
- 法律/政策依据：
  - 需人工复核
- 整改建议：
  - 调取招标公告原文复核。
""".strip(),
    )
    comparison = compare_review_artifacts("sample.docx", baseline, [])
    assert all(cluster.title != "投标人资格要求内容缺失，无法判断是否存在排斥性条款" for cluster in comparison.clusters)
    pending = next(
        item for item in comparison.metadata["pending_review_items"] if item["title"] == "投标人资格要求内容缺失，无法判断是否存在排斥性条款"
    )
    assert pending["topic"] == "资格条件"
    assert "待补证复核" in pending["reason"]


def test_compare_review_artifacts_moves_new_policy_missing_variant_to_pending() -> None:
    baseline = V2StageArtifact(
        name="baseline",
        content="""
# 招标文件合规审查结果

审查对象：`sample.docx`

## 风险点1：政策导向章节内容缺失，无法全面审查其他政策落实情况

- 问题定性：需人工复核
- 审查类型：政策适用与落实
- 原文位置：证据3 第 3422 行
- 原文摘录：6． 政策导向 6.
- 风险判断：
  - 当前章节只有标题，正文未完整召回。
- 法律/政策依据：
  - 需人工复核
- 整改建议：
  - 补充完整条文后再审查。
""".strip(),
    )
    comparison = compare_review_artifacts("sample.docx", baseline, [])
    assert all(cluster.title != "政策导向章节内容缺失，无法全面审查其他政策落实情况" for cluster in comparison.clusters)
    pending = next(
        item for item in comparison.metadata["pending_review_items"] if item["title"] == "政策导向章节内容缺失，无法全面审查其他政策落实情况"
    )
    assert pending["topic"] in {"专题", "政策条款", "baseline"}
    assert "证据召回不足" in pending["reason"] or "待补证复核" in pending["reason"]


def test_compare_review_artifacts_enriches_import_consistency_with_foreign_component_evidence() -> None:
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果\n\n审查对象：`sample.docx`\n")
    topics = [
        TopicReviewArtifact(
            topic="policy",
            summary="政策专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖政策条款。",
            metadata={
                "selected_sections": [{"title": "二、申请人的资格要求"}],
                "missing_evidence": [],
                "structured_signals": {
                    "import_policy": "reject_import",
                    "import_policy_reject_phrases": ["不接受投标人选用进口产品参与投标"],
                    "import_policy_sections": [{"title": "二、申请人的资格要求", "section_id": "10-12"}],
                    "import_policy_sentences": ["不接受投标人选用进口产品参与投标。"],
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
                "selected_sections": [{"title": "1.规格及技术参数"}],
                "missing_evidence": [],
                "structured_signals": {
                    "foreign_standard_refs": ["BS EN 61000", "EN55011"],
                    "cn_standard_refs": ["GB/T 17626"],
                    "has_equivalent_standard_clause": False,
                    "foreign_standard_sections": [{"title": "1.规格及技术参数", "section_id": "50-66"}],
                    "foreign_standard_sentences": ["1.14 电磁影响：符合 BS EN 61000、GB/T 17626 及 EN55011 标准。"],
                    "cn_standard_sentences": ["1.14 电磁影响：符合 BS EN 61000、GB/T 17626 及 EN55011 标准。"],
                },
            },
        ),
        TopicReviewArtifact(
            topic="acceptance",
            summary="验收专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖部件与验收条款。",
            metadata={
                "selected_sections": [{"title": "五、商务要求"}],
                "missing_evidence": [],
                "structured_signals": {
                    "foreign_component_requirement_present": True,
                    "foreign_component_sections": [{"title": "五、商务要求", "section_id": "90-98"}],
                    "foreign_component_sentences": ["国外生产的部件必须有合法的进货渠道证明及原产地证明。"],
                },
            },
        ),
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    cluster = next(
        item for item in comparison.clusters if item.title == "非进口项目中出现国外标准/国外部件相关表述，存在采购政策口径、技术标准口径、验收口径不一致风险"
    )
    assert any("部件/验收条款：五、商务要求" in location for location in cluster.source_locations)
    assert any("原产地证明" in excerpt for excerpt in cluster.source_excerpts)
    assert any("原产地证明" in judgment for judgment in cluster.risk_judgment)


def test_compare_review_artifacts_excludes_turnkey_payment_risk_when_payment_chain_is_complete() -> None:
    baseline = V2StageArtifact(
        name="baseline",
        content="""
# 招标文件合规审查结果

审查对象：`sample.docx`

## 风险点1：商务条款中“交钥匙”项目要求与付款方式存在潜在风险

- 问题定性：低风险
- 审查类型：商务条款失衡
- 原文位置：第三章 用户需求书 -> 五、商务要求 -> 2.基本要求 & 3.付款方式
- 原文摘录：本项目为交钥匙项目，投标总价包含所有费用。
- 风险判断：
  - 交钥匙项目与付款安排可能存在失衡。
- 法律/政策依据：
  - 需人工复核
- 整改建议：
  - 结合付款链路进一步复核。
""".strip(),
    )
    topics = [
        TopicReviewArtifact(
            topic="contract_payment",
            summary="付款专题完成。",
            risk_points=[],
            need_manual_review=False,
            coverage_note="已覆盖付款链路。",
            metadata={
                "selected_sections": [{"title": "3.付款方式"}],
                "missing_evidence": [],
                "structured_signals": {
                    "payment_chain_complete": True,
                    "payment_chain_sections": [{"title": "3.付款方式", "section_id": "30-40"}],
                    "payment_chain_sentences": [
                        "双方合同签订后，支付合同总价30%。",
                        "全部货物送达采购人现场后，支付合同总价50%。",
                        "工程全部安装调试完成经采购人现场验收合格设备正常运行三个月后，支付合同总价20%。",
                    ],
                },
            },
        )
    ]

    comparison = compare_review_artifacts("sample.docx", baseline, topics)
    assert all(item["title"] != "商务条款中“交钥匙”项目要求与付款方式存在潜在风险" for item in comparison.metadata["pending_review_items"])
    excluded = next(
        item for item in comparison.metadata["excluded_risks"] if item["title"] == "商务条款中“交钥匙”项目要求与付款方式存在潜在风险"
    )
    assert "完整付款链路" in excluded["reason"]
    assert "支付合同总价30%" in excluded["reason"]
