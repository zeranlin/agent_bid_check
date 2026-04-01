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
    assert cluster.review_type == "评分因素合规性 / 评审规则设置合法性"
    assert cluster.source_locations == ["评审规则：第一章 评审规则；评分条款：第六章 评分办法"]
    assert "项目验收移交衔接方案" in cluster.source_excerpts[0]
    assert "最高得30分" in cluster.source_excerpts[0]
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
        item for item in comparison.clusters if item.title == "将赠送额外商品作为评分条件，违反评审规则合规性要求"
    )
    assert cluster.severity == "高风险"
    assert cluster.review_type == "评分因素合规性 / 不当附加交易条件"
    assert "赠送台式电脑" in cluster.source_excerpts[0]
    assert "得100分" in cluster.source_excerpts[0]
    assert comparison.metadata["failure_reason_codes"] == ["gifts_or_unrelated_goods_in_scoring_forbidden"]
    report = assemble_v2_report("sample.docx", baseline, V2StageArtifact(name="structure", metadata={}), topics, comparison)
    assert "将赠送额外商品作为评分条件，违反评审规则合规性要求" in report
    assert "问题定性：高风险" in report
    assert "删除“赠送台式电脑、打印机”等与采购无关的附加商品要求。" in report


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
    assert all(cluster.title != "将赠送额外商品作为评分条件，违反评审规则合规性要求" for cluster in comparison.clusters)


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
    assert all(cluster.title != "将赠送额外商品作为评分条件，违反评审规则合规性要求" for cluster in comparison.clusters)


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
        item for item in comparison.clusters if item.title == "将赠送额外商品作为评分条件，违反评审规则合规性要求"
    )
    assert "值班室办公设备配置" in cluster.source_excerpts[0]
    assert "会议保障等综合服务内容" in cluster.source_excerpts[0]
    assert comparison.metadata["failure_reason_codes"] == ["gifts_or_unrelated_goods_in_scoring_forbidden"]


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
        if item.title == "技术标准引用与采购政策口径不一致，存在潜在倾向性和理解冲突"
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
