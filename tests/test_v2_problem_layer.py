from __future__ import annotations

import json
from pathlib import Path

from app.pipelines.v2.output_governance import govern_comparison_artifact
from app.pipelines.v2.problem_layer import build_problem_layer
from app.pipelines.v2.problem_layer.models import Problem
from app.pipelines.v2.risk_admission import admit_problem_result
from app.pipelines.v2.schemas import ComparisonArtifact, MergedRiskCluster

from tests.test_v2_risk_admission import _build_sample_comparison


def _load_comparison_artifact(path: str | Path) -> ComparisonArtifact:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return ComparisonArtifact(
        signatures=[],
        clusters=[MergedRiskCluster(**item) for item in payload.get("clusters", [])],
        conflicts=list(payload.get("conflicts", [])),
        coverage_summary=dict(payload.get("coverage_summary", {})),
        comparison_summary=dict(payload.get("comparison_summary", {})),
        baseline_only_risks=list(payload.get("baseline_only_risks", [])),
        topic_only_risks=list(payload.get("topic_only_risks", [])),
        missing_topic_coverage=list(payload.get("missing_topic_coverage", [])),
        manual_review_items=list(payload.get("manual_review_items", [])),
        coverage_gaps=list(payload.get("coverage_gaps", [])),
        metadata=dict(payload.get("metadata", {})),
    )


def _build_pb2_certification_bundle_comparison() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="pb2-cert-main",
                title="以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险",
                severity="高风险",
                review_type="评分因素合规性 / 限定特定认证或发证机构",
                source_locations=["评标信息 -> 综合实力部分 -> 供应商认证情况"],
                source_excerpts=[
                    "要求提供有效的认证证书扫描件，且认证机构必须为 CQC 中国质量认证中心；投标人每具备一项体系认证证书得 35 分。"
                ],
                risk_judgment=["主风险应保留。"],
                legal_basis=["不得限定特定认证机构。"],
                rectification=["删除特定认证机构限定。"],
                topics=["scoring"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="pb2-cert-support",
                title="认证项权重偏高且与履约关联不足，存在倾向性评分风险",
                severity="中风险",
                review_type="评分项合规性审查",
                source_locations=["评标信息 -> 综合实力部分 -> 供应商认证情况"],
                source_excerpts=[
                    "投标人每具备一项体系认证证书得 35 分，具备三项证书得 100 分，未提供得 0 分。"
                ],
                risk_judgment=["这是同一组认证评分证据中的权重侧佐证。"],
                legal_basis=["认证项权重不宜畸高。"],
                rectification=["压缩认证项分值。"],
                topics=["scoring"],
                source_rules=["topic"],
            ),
        ]
    )


def _build_pb2_no_over_merge_comparison() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="pb2-sample",
                title="样品制作要求具有排他性及泄露信息风险",
                severity="高风险",
                review_type="技术参数倾向性/限制竞争",
                source_locations=["样品要求第3、4点"],
                source_excerpts=["不得出现样品图样，标识等可能泄露投标人样品的任何信息，否则按无效投标处理。"],
                risk_judgment=["样品要求过细。"],
                legal_basis=["样品要求不得形成不合理门槛。"],
                rectification=["压缩样品要求。"],
                topics=["samples_demo"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="pb2-acceptance",
                title="验收标准引用‘厂家验收标准’导致依据模糊",
                severity="中风险",
                review_type="验收标准明确性审查",
                source_locations=["验收条款9.1"],
                source_excerpts=["所有货物按厂家验收标准、招标文件、投标文件及中标人在投标文件中所提供的样品要求等有关内容进行验收。"],
                risk_judgment=["样品被纳入验收依据，但与样品门槛属于不同问题。"],
                legal_basis=["验收标准应统一明确。"],
                rectification=["删除厂家标准并固化验收标准。"],
                topics=["acceptance"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="pb2-commercial",
                title="商务条款中采购人单方调整权过大且结算方式不明",
                severity="中风险",
                review_type="商务条款失衡",
                source_locations=["商务要求8.3、13.3"],
                source_excerpts=["采购人有权细微调整且中标价不变，偏离超过5%按面积比例换算。"],
                risk_judgment=["采购人单方变更权过大。"],
                legal_basis=["不得背离合同实质性内容。"],
                rectification=["补充双方协商和价格调整机制。"],
                topics=["contract"],
                source_rules=["baseline"],
            ),
            MergedRiskCluster(
                cluster_id="pb2-supervision",
                title="验收条款中“驻厂检查”及“终止合同”条件过于严苛",
                severity="中风险",
                review_type="商务条款失衡/验收条款",
                source_locations=["验收条款10.4"],
                source_excerpts=["采购人可对生产全过程驻厂检查，发现未按工艺生产可终止合同。"],
                risk_judgment=["监督与解除条件失衡。"],
                legal_basis=["违约处理应与过错程度相当。"],
                rectification=["压缩监督范围并增加整改程序。"],
                topics=["acceptance"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="pb2-technical",
                title="技术参数中尺寸公差及工艺要求过于具体，存在指向性嫌疑",
                severity="中风险",
                review_type="技术参数倾向性",
                source_locations=["技术参数A"],
                source_excerpts=["尺寸公差±5mm，拉手规格123*28*22mm。"],
                risk_judgment=["参数过细。"],
                legal_basis=["不得以过细参数指向特定产品。"],
                rectification=["放宽非关键参数。"],
                topics=["technical"],
                source_rules=["topic"],
            ),
        ]
    )


def _build_pb3_cross_topic_family_merge_comparison() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="pb3-import-tech",
                title="拒绝进口 vs 外标/国外部件引用矛盾风险",
                severity="中风险",
                review_type="技术标准一致性审查",
                source_locations=["技术条款：1.规格及技术参数"],
                source_excerpts=["外标引用：符合 BS EN 61000 GB/T 17626 及 EN55011 标准。"],
                risk_judgment=["技术标准侧已识别进口口径与外标引用冲突。"],
                legal_basis=["技术标准引用应与采购政策口径一致。"],
                rectification=["补充说明等效标准。"],
                topics=["technical_standard"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="pb3-import-policy",
                title="非进口项目中出现国外标准和国外部件要求，存在政策适用矛盾",
                severity="中风险",
                review_type="采购政策一致性审查",
                source_locations=["采购包信息：是否允许进口产品"],
                source_excerpts=["采购包明确不允许进口产品，但技术条款又出现国外标准/国外部件表述。"],
                risk_judgment=["政策口径侧也命中了同一业务问题。"],
                legal_basis=["采购政策与技术要求应保持一致。"],
                rectification=["统一进口政策与技术标准口径。"],
                topics=["policy"],
                source_rules=["topic"],
            ),
        ]
    )


def _build_ax1_brand_bias_comparison() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="ax1-brand-base",
                title="技术参数中指定特定品牌，具有明显排他性",
                severity="高风险",
                review_type="技术参数倾向性",
                source_locations=["样品要求 ⑤品牌"],
                source_excerpts=["⑤品牌:Aokang"],
                risk_judgment=["同一证据直接点名品牌。"],
                legal_basis=["不得指定特定品牌。"],
                rectification=["删除品牌指定。"],
                topics=["baseline"],
                source_rules=["baseline"],
            ),
            MergedRiskCluster(
                cluster_id="ax1-brand-tech",
                title="样品要求中指定品牌，可能隐含排他性检测标准",
                severity="高风险",
                review_type="技术规格与品牌倾向审查",
                source_locations=["样品要求 ⑤品牌"],
                source_excerpts=["⑤品牌:Aokang"],
                risk_judgment=["品牌指定与技术标准侧相邻命中。"],
                legal_basis=["不得隐含排他性品牌要求。"],
                rectification=["删除品牌指向。"],
                topics=["technical_standard"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="ax1-brand-score",
                title="样品要求中指定特定品牌，存在限定特定供应商和倾向性评分风险",
                severity="高风险",
                review_type="合规性审查",
                source_locations=["样品要求 ⑤品牌"],
                source_excerpts=["⑤品牌:Aokang"],
                risk_judgment=["同一品牌问题在评分专题再次命中。"],
                legal_basis=["不得限定特定供应商。"],
                rectification=["删除品牌限定。"],
                topics=["scoring"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="ax1-brand-sample",
                title="样品要求中指定特定品牌，涉嫌排斥潜在投标人",
                severity="高风险",
                review_type="合规性审查",
                source_locations=["样品要求 ⑤品牌"],
                source_excerpts=["⑤品牌:Aokang"],
                risk_judgment=["同一品牌问题在样品专题再次命中。"],
                legal_basis=["不得形成样品门槛。"],
                rectification=["删除品牌要求。"],
                topics=["samples_demo"],
                source_rules=["topic"],
            ),
        ]
    )


def _build_ax1_sample_acceptance_comparison() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="ax1-sample-primary",
                title="样品评审规则设置不当，存在“未提供即无效”的过度严苛情形",
                severity="中风险",
                review_type="评审标准不合理",
                source_locations=["样品评审规则"],
                source_excerpts=["未按时提交样品或样品不全的，为无效投标。"],
                risk_judgment=["主问题应保留。"],
                legal_basis=["样品规则不得设置过度门槛。"],
                rectification=["改为扣分或符合性校验。"],
                topics=["baseline"],
                source_rules=["baseline"],
            ),
            MergedRiskCluster(
                cluster_id="ax1-sample-support",
                title="样品评审规则与最低评标价法逻辑可能存在冲突，需核实样品在评标中的具体作用",
                severity="中风险",
                review_type="逻辑一致性审查",
                source_locations=["样品评审规则"],
                source_excerpts=["评标方法为最低评标价法，但样品未提供可判无效。"],
                risk_judgment=["属于主问题的附属解释。"],
                legal_basis=["评审逻辑应一致。"],
                rectification=["明确样品在评标中的作用。"],
                topics=["scoring"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="ax1-sample-internal",
                title="样品要求中“不得体现供应商公司信息”与“样品作为验收样本”存在逻辑冲突",
                severity="低风险",
                review_type="技术参数/验收条款",
                source_locations=["样品与验收条款"],
                source_excerpts=["样品不得体现供应商信息；成交候选人的样品作为验收样本。"],
                risk_judgment=["更适合进入 internal trace。"],
                legal_basis=["样品与验收衔接需一致。"],
                rectification=["统一样品留存与验收说明。"],
                topics=["baseline"],
                source_rules=["baseline"],
            ),
        ]
    )


def _build_pb3_layer_conflict_comparison() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="pb3-cost-formal",
                title="验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险",
                severity="中风险",
                review_type="验收与检测费用边界审查",
                source_locations=["验收条款9.2"],
                source_excerpts=["检测结果如出现不合格的产品，检测费用由中标人支付。"],
                risk_judgment=["正文已明确将检测费用转嫁给中标人。"],
                legal_basis=["检测费用承担边界应明确且合理。"],
                rectification=["明确采购人、中标人各自承担范围。"],
                topics=["acceptance"],
                source_rules=["topic"],
            ),
        ],
        metadata={
            "pending_review_items": [
                {
                    "title": "验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险",
                    "severity": "需人工复核",
                    "review_type": "待补证复核",
                    "topic": "acceptance",
                    "source_location": "验收条款9.2",
                    "source_excerpt": "验收费用承担方式尚需结合全部验收条款进一步核实。",
                    "reason": "另一来源认为当前证据仍需补证。",
                }
            ]
        },
    )


def _build_pb4_acceptance_plan_conflict_comparison() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="pb4-acceptance-policy",
                title="评分规则明确不得将验收方案作为评审因素",
                severity="中风险",
                review_type="评分规则一致性审查",
                source_locations=["评分规则总则"],
                source_excerpts=["评审因素不得包含验收方案、付款方式等与评审无关内容。"],
                risk_judgment=["评分规则已明确禁止。"],
                legal_basis=["评审因素应与采购需求和履约相关。"],
                rectification=["保持评分规则与评分细则一致。"],
                topics=["policy"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="pb4-acceptance-scoring",
                title="将项目验收方案纳入评审因素，违反评审规则合规性要求",
                severity="高风险",
                review_type="评分因素合规性审查",
                source_locations=["评分细则：验收方案评分"],
                source_excerpts=["验收方案优的得满分。"],
                risk_judgment=["评分细则实际按验收方案打分。"],
                legal_basis=["评审因素应与采购需求和履约相关。"],
                rectification=["删除与验收方案直接挂钩的评分条件。"],
                topics=["scoring"],
                source_rules=["compare_rule:R-003"],
            ),
        ]
    )


def _build_pb4_payment_conflict_comparison() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="pb4-payment-policy",
                title="评分规则明确不得将付款方式作为评审因素",
                severity="中风险",
                review_type="评分规则一致性审查",
                source_locations=["评分规则总则"],
                source_excerpts=["付款周期、预付款比例等交易条件不得作为评分因素。"],
                risk_judgment=["评分规则已明确禁止。"],
                legal_basis=["评分因素不得与履约无关。"],
                rectification=["保持评分规则与评分细则一致。"],
                topics=["policy"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="pb4-payment-scoring",
                title="评分项按付款周期加分，存在以付款方式作为评审因素的风险",
                severity="中风险",
                review_type="评分因素合规性审查",
                source_locations=["评分细则：商务响应"],
                source_excerpts=["付款周期越短得分越高，预付款比例越高加分越多。"],
                risk_judgment=["评分细则实际按付款方式加分。"],
                legal_basis=["评分因素不得与履约无关。"],
                rectification=["删除付款条件评分。"],
                topics=["scoring"],
                source_rules=["topic"],
            ),
        ]
    )


def _build_pb4_non_conflict_cross_topic_comparison() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="pb4-nonconf-policy",
                title="评分规则要求技术参数中的实质性要求以“★”标示",
                severity="中风险",
                review_type="评分规则一致性审查",
                source_locations=["评分规则总则"],
                source_excerpts=["技术参数中的实质性要求应以“★”标示。"],
                risk_judgment=["规则说明了标示方式。"],
                legal_basis=["应保证评审规则清晰。"],
                rectification=["保持规则说明与正文一致。"],
                topics=["policy"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="pb4-nonconf-tech",
                title="技术参数过细且特征化，存在指向性风险",
                severity="中风险",
                review_type="技术参数倾向性",
                source_locations=["技术参数A"],
                source_excerpts=["尺寸公差±5mm，拉手规格123*28*22mm。"],
                risk_judgment=["参数过细。"],
                legal_basis=["不得以过细参数指向特定产品。"],
                rectification=["放宽非关键参数。"],
                topics=["technical"],
                source_rules=["topic"],
            ),
        ]
    )


def test_build_problem_layer_creates_problem_objects_from_governed_candidates() -> None:
    comparison = _build_sample_comparison()
    governance = govern_comparison_artifact("sample.docx", comparison)

    problem_result = build_problem_layer("sample.docx", governance)

    assert problem_result.problems
    first = problem_result.problems[0]
    assert isinstance(first, Problem)
    assert first.problem_id
    assert first.canonical_title
    assert first.family_key
    assert first.primary_candidate.identity.rule_id
    assert isinstance(first.supporting_candidates, list)
    assert isinstance(first.evidence_ids, list)
    assert isinstance(first.topic_sources, list)
    assert isinstance(first.rule_ids, list)
    assert isinstance(first.trace, dict)


def test_problem_id_is_stable_and_repeatable() -> None:
    comparison = _build_sample_comparison()
    governance = govern_comparison_artifact("sample.docx", comparison)

    first = build_problem_layer("sample.docx", governance)
    second = build_problem_layer("sample.docx", governance)

    assert [item.problem_id for item in first.problems] == [item.problem_id for item in second.problems]


def test_problem_layer_keeps_candidate_and_trace_backreferences() -> None:
    comparison = _build_sample_comparison()
    governance = govern_comparison_artifact("sample.docx", comparison)

    problem_result = build_problem_layer("sample.docx", governance)
    first = problem_result.problems[0]

    assert first.trace["source_candidate_titles"]
    assert first.trace["source_governed_rule_ids"]
    assert "problem_id_seed" in first.trace


def test_problem_layer_merges_cross_family_certification_bundle_into_single_problem() -> None:
    comparison = _build_pb2_certification_bundle_comparison()
    governance = govern_comparison_artifact("sample.docx", comparison)

    assert len(governance.governed_candidates) == 2

    problem_result = build_problem_layer("sample.docx", governance)

    assert len(problem_result.problems) == 1
    first = problem_result.problems[0]
    assert first.canonical_title == "以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险"
    assert [item.decision.canonical_title for item in first.supporting_candidates] == ["认证项权重偏高且与履约关联不足，存在倾向性评分风险"]
    assert sorted(first.rule_ids) == sorted(
        [
            "topic::certification_scoring_bundle",
            "topic::cert_weight",
        ]
    )
    assert first.trace["problem_merge_reason"]
    assert first.trace["absorbed_supporting_titles"] == ["认证项权重偏高且与履约关联不足，存在倾向性评分风险"]


def test_problem_layer_preserves_absorbed_trace_into_admission_candidate() -> None:
    comparison = _build_pb2_certification_bundle_comparison()
    governance = govern_comparison_artifact("sample.docx", comparison)
    problem_result = build_problem_layer("sample.docx", governance)

    admission = admit_problem_result("sample.docx", comparison, problem_result, governance)

    assert len(admission.formal_risks) == 1
    formal = admission.formal_risks[0]
    assert formal.extras["problem_supporting_candidate_titles"] == ["认证项权重偏高且与履约关联不足，存在倾向性评分风险"]
    assert sorted(formal.extras["problem_rule_ids"]) == sorted(["topic::certification_scoring_bundle", "topic::cert_weight"])
    assert formal.extras["problem_trace"]["problem_merge_reason"]


def test_problem_layer_does_not_over_merge_distinct_sample_acceptance_and_commercial_issues() -> None:
    comparison = _build_pb2_no_over_merge_comparison()
    governance = govern_comparison_artifact("sample.docx", comparison)

    problem_result = build_problem_layer("sample.docx", governance)
    titles = [item.canonical_title for item in problem_result.problems]

    assert len(problem_result.problems) == 5
    assert "样品要求过细且评审规则失衡，存在样品门槛风险" in titles
    assert "验收标准引用“厂家验收标准”及“样品”，存在模糊表述和单方裁量风险" in titles
    assert "商务条款中采购人单方变更权过大且结算方式不明" in titles
    assert "履约监督与解除条件失衡" in titles
    assert "技术参数过细且特征化，存在指向性风险" in titles


def test_problem_layer_merges_cross_topic_hits_into_one_problem_with_trace() -> None:
    comparison = _build_pb3_cross_topic_family_merge_comparison()
    governance = govern_comparison_artifact("sample.docx", comparison)

    problem_result = build_problem_layer("sample.docx", governance)

    assert len(governance.governed_candidates) == 1
    assert len(problem_result.problems) == 1
    problem = problem_result.problems[0]
    assert sorted(problem.merged_topic_sources) == ["policy", "technical_standard"]
    assert problem.trace["cross_topic_merge_reason"]
    assert sorted(problem.merged_family_keys) == ["import_consistency"]


def test_problem_layer_records_layer_conflict_inputs_and_single_final_resolution() -> None:
    comparison = _build_pb3_layer_conflict_comparison()
    governance = govern_comparison_artifact("sample.docx", comparison)
    problems = build_problem_layer("sample.docx", governance)

    assert len(problems.problems) == 1
    problem = problems.problems[0]
    assert sorted(item["source_bucket"] for item in problem.layer_conflict_inputs) == ["formal_risks", "pending_review_items"]

    admission = admit_problem_result("sample.docx", comparison, problems, governance)

    assert [item.title for item in admission.formal_risks] == ["验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险"]
    assert admission.pending_review_items == []
    assert admission.excluded_risks == []
    assert problem.final_problem_resolution["target_layer"] == "formal_risks"
    assert problem.trace["final_problem_resolution"]["winner_input_bucket"] == "formal_risks"
    formal = admission.formal_risks[0]
    assert formal.extras["final_problem_resolution"]["target_layer"] == "formal_risks"
    assert sorted(item["source_bucket"] for item in formal.extras["problem_trace"]["layer_conflict_inputs"]) == [
        "formal_risks",
        "pending_review_items",
    ]


def test_problem_layer_dedupes_acceptance_testing_cost_user_visible_outputs_with_trace() -> None:
    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="acceptance-cost-formal",
                title="验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险",
                severity="高风险",
                review_type="商务条款审查",
                source_locations=["商务条款：报价要求"],
                source_excerpts=["投标总价应包含项目验收、检测及相关部门验收等全部费用。"],
                risk_judgment=["正文已出现验收检测费用计入投标人承担范围。"],
                legal_basis=["不得将应由采购人承担的法定职责费用转嫁供应商。"],
                rectification=["明确验收检测费用承担边界。"],
                topics=["contract_payment"],
                source_rules=["compare_rule:R-COST"],
            ),
            MergedRiskCluster(
                cluster_id="acceptance-cost-pending",
                title="将验收产生的检测费用计入投标人承担范围，存在需求条款合规风险",
                severity="中风险",
                review_type="需求条款审查",
                source_locations=["采购需求：验收要求"],
                source_excerpts=["验收、检测等费用由中标人承担。"],
                risk_judgment=["这是同一家族中的附属需求侧描述。"],
                legal_basis=["采购需求不得转嫁不合理费用负担。"],
                rectification=["删除由投标人承担验收检测费用的表述。"],
                topics=["acceptance"],
                source_rules=["topic"],
            ),
        ],
        metadata={
            "pending_review_items": [
                {
                    "title": "将验收产生的检测费用计入投标人承担范围，存在需求条款合规风险",
                    "severity": "需人工复核",
                    "review_type": "需求条款审查",
                    "topic": "验收条款",
                    "source_location": "采购需求：验收要求",
                    "source_excerpt": "验收、检测等费用由中标人承担。",
                    "reason": "当前为待补证复核输出。",
                }
            ]
        },
    )
    governance = govern_comparison_artifact("fuzhou-school-dorm.docx", comparison)

    problem_result = build_problem_layer("fuzhou-school-dorm.docx", governance)

    assert len(problem_result.problems) == 1
    first = problem_result.problems[0]
    assert first.canonical_title == "验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险"
    assert [item.decision.canonical_title for item in first.supporting_candidates] == [
        "将验收产生的检测费用计入投标人承担范围，存在需求条款合规风险"
    ]
    assert first.trace["user_visible_dedupe_reason"] == "family_visible_output_absorbed_by_primary"
    assert first.trace["absorbed_user_visible_items"] == [
        {
            "title": "将验收产生的检测费用计入投标人承担范围，存在需求条款合规风险",
            "source_bucket": "pending_review_items",
            "absorbed_by": "验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险",
            "hidden_reason": "same_family_absorbed_by_formal_primary",
        }
    ]


def test_problem_layer_governs_brand_bias_family_into_single_primary_visible_problem() -> None:
    comparison = _build_ax1_brand_bias_comparison()
    governance = govern_comparison_artifact("quanzhou.docx", comparison)

    problem_result = build_problem_layer("quanzhou.docx", governance)

    assert len(problem_result.problems) == 1
    first = problem_result.problems[0]
    assert first.family_key == "brand_bias"
    assert first.canonical_title == "疑似限定或倾向特定品牌/供应商"
    assert len(first.supporting_candidates) == 3
    assert len(first.trace["supporting_problem_ids"]) == 3
    assert first.trace["primary_visible_problem_id"]
    assert first.trace["family_visible_output_absorbed_by_primary"] is True
    assert first.trace["primary_selection_reason"]
    assert len(first.trace["absorbed_problem_ids"]) == 3
    absorbed_titles = [item["title"] for item in first.trace["absorbed_user_visible_items"]]
    assert absorbed_titles == [
        "样品要求中指定品牌，可能隐含排他性检测标准",
        "样品要求中指定特定品牌，存在限定特定供应商和倾向性评分风险",
        "样品要求中指定特定品牌，涉嫌排斥潜在投标人",
    ]
    assert all(item["hidden_reason"] == "supporting_hidden_under_family_primary" for item in first.trace["absorbed_user_visible_items"])
    assert all(item["source_bucket"] == "formal_risks" for item in first.trace["absorbed_user_visible_items"])


def test_problem_layer_governs_sample_acceptance_family_with_supporting_and_internal_trace() -> None:
    comparison = _build_ax1_sample_acceptance_comparison()
    governance = govern_comparison_artifact("quanzhou.docx", comparison)

    problem_result = build_problem_layer("quanzhou.docx", governance)

    assert len(problem_result.problems) == 1
    first = problem_result.problems[0]
    assert first.family_key == "sample_acceptance_gate"
    assert first.canonical_title == "将样品要求/验收方案不当作为评审或履约门槛"
    assert [item.decision.canonical_title for item in first.supporting_candidates] == [
        "样品评审规则与最低评标价法逻辑可能存在冲突，需核实样品在评标中的具体作用"
    ]
    assert first.trace["primary_visible_problem_id"]
    assert len(first.trace["supporting_problem_ids"]) == 1
    assert len(first.trace["internal_trace_only_problem_ids"]) == 1
    assert len(first.trace["absorbed_problem_ids"]) == 2
    assert first.trace["family_visible_output_absorbed_by_primary"] is True
    assert first.trace["internal_trace_only_items"] == [
        {
            "problem_id": first.trace["internal_trace_only_problem_ids"][0],
            "title": "样品要求中“不得体现供应商公司信息”与“样品作为验收样本”存在逻辑冲突",
            "source_bucket": "formal_risks",
            "prior_bucket": "formal_risks",
            "absorbed_by": "将样品要求/验收方案不当作为评审或履约门槛",
            "absorbed_by_problem_id": first.problem_id,
            "hidden_reason": "internal_trace_only_under_family_primary",
            "visibility": "internal_trace_only",
        }
    ]


def test_problem_layer_replay_gate_collapses_quanzhou_brand_bias_user_visible_outputs() -> None:
    comparison_path = Path("data/results/v2/20260412-092839-quanzhou-runreview/comparison.json")
    comparison = _load_comparison_artifact(comparison_path)
    governance = govern_comparison_artifact("quanzhou.docx", comparison)

    problem_result = build_problem_layer("quanzhou.docx", governance)

    brand_problems = [item for item in problem_result.problems if item.family_key == "brand_bias"]
    assert len(brand_problems) == 1
    brand_problem = brand_problems[0]
    assert brand_problem.canonical_title == "疑似限定或倾向特定品牌/供应商"
    assert len(brand_problem.supporting_candidates) >= 1
    assert brand_problem.trace["family_governance_config_id"]


def test_problem_layer_builds_import_consistency_conflict_problem() -> None:
    comparison = _build_pb3_cross_topic_family_merge_comparison()
    governance = govern_comparison_artifact("sample.docx", comparison)

    base_result = build_problem_layer("sample.docx", governance, enable_conflicts=False)
    conflict_result = build_problem_layer("sample.docx", governance, enable_conflicts=True)

    assert len(base_result.problems) == 1
    assert len(conflict_result.problems) == 1
    conflict_problem = conflict_result.problems[0]
    assert conflict_problem.problem_kind == "conflict"
    assert conflict_problem.conflict_type == "import_consistency_conflict"
    assert conflict_problem.left_side["topic"] == "policy"
    assert conflict_problem.right_side["topic"] == "technical_standard"
    assert "why_conflict" in conflict_problem.conflict_reason
    assert len(conflict_problem.conflict_evidence_links) == 2


def test_problem_layer_builds_acceptance_plan_scoring_conflict_problem() -> None:
    comparison = _build_pb4_acceptance_plan_conflict_comparison()
    governance = govern_comparison_artifact("sample.docx", comparison)

    result = build_problem_layer("sample.docx", governance)

    assert len(result.problems) == 1
    conflict_problem = result.problems[0]
    assert conflict_problem.problem_kind == "conflict"
    assert conflict_problem.conflict_type == "acceptance_plan_scoring_conflict"
    assert conflict_problem.left_side["problem_id"]
    assert conflict_problem.right_side["problem_id"]
    assert conflict_problem.left_side["topic"] == "policy"
    assert conflict_problem.right_side["topic"] == "scoring"


def test_problem_layer_builds_payment_scoring_conflict_problem() -> None:
    comparison = _build_pb4_payment_conflict_comparison()
    governance = govern_comparison_artifact("sample.docx", comparison)

    result = build_problem_layer("sample.docx", governance)

    assert len(result.problems) == 1
    conflict_problem = result.problems[0]
    assert conflict_problem.problem_kind == "conflict"
    assert conflict_problem.conflict_type == "payment_scoring_conflict"
    assert conflict_problem.left_side["topic"] == "policy"
    assert conflict_problem.right_side["topic"] == "scoring"


def test_problem_layer_does_not_misclassify_non_conflict_cross_topic_hits_as_conflict() -> None:
    comparison = _build_pb4_non_conflict_cross_topic_comparison()
    governance = govern_comparison_artifact("sample.docx", comparison)

    result = build_problem_layer("sample.docx", governance)

    assert len(result.problems) == 2
    assert all(item.problem_kind == "standard" for item in result.problems)
