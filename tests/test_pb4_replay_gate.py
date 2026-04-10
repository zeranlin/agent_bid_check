from __future__ import annotations

import json
from pathlib import Path

from app.common.file_extract import extract_text
from app.pipelines.v2.output_governance import govern_comparison_artifact
from app.pipelines.v2.problem_layer import build_problem_layer
from app.pipelines.v2.risk_admission import admit_problem_result
from app.pipelines.v2.schemas import ComparisonArtifact, MergedRiskCluster


DIESEL_FILE = Path("data/uploads/v2/20260401-124322-9d7d80-SZDL2025000495-A.docx")


def test_pb4_diesel_replay_outputs_single_import_conflict_problem(tmp_path: Path) -> None:
    text = extract_text(DIESEL_FILE)
    assert "EN55011" in text

    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="pb4-diesel-tech",
                title="拒绝进口 vs 外标/国外部件引用矛盾风险",
                severity="中风险",
                review_type="技术标准一致性审查",
                source_locations=["技术条款：1.规格及技术参数"],
                source_excerpts=["符合 BS EN 61000 GB/T 17626 及 EN55011 标准。"],
                risk_judgment=["技术标准专题命中了进口口径与外标引用冲突。"],
                legal_basis=["技术标准引用应与采购政策口径一致。"],
                rectification=["补充说明等效标准。"],
                topics=["technical_standard"],
                source_rules=["topic"],
            )
        ],
        metadata={
            "pending_review_items": [
                {
                    "title": "非进口项目中出现国外标准和国外部件要求，存在政策适用矛盾",
                    "severity": "需人工复核",
                    "review_type": "采购政策一致性复核",
                    "topic": "policy",
                    "source_location": "采购包信息：是否允许进口产品",
                    "source_excerpt": "采购包明确不允许进口产品，但技术条款又出现国外标准/国外部件表述。",
                    "reason": "政策专题从另一侧命中了同一问题，先作为待补证输入。",
                }
            ]
        },
    )

    governance = govern_comparison_artifact(DIESEL_FILE.name, comparison)
    before_problems = build_problem_layer(DIESEL_FILE.name, governance, enable_conflicts=False)
    after_problems = build_problem_layer(DIESEL_FILE.name, governance, enable_conflicts=True)
    admission = admit_problem_result(DIESEL_FILE.name, comparison, after_problems, governance)

    output_dir = tmp_path / "pb4-diesel-replay"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "pb4_summary.json").write_text(
        json.dumps(
            {
                "candidate_count": len(governance.governed_candidates),
                "problem_count_before_conflict": len(before_problems.problems),
                "problem_count_after_conflict": len(after_problems.problems),
                "formal_titles_after_admission": [item.title for item in admission.formal_risks],
                "conflict_problem_kind": after_problems.problems[0].problem_kind,
                "conflict_type": after_problems.problems[0].conflict_type,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    assert len(before_problems.problems) == 1
    assert len(after_problems.problems) == 1
    assert after_problems.problems[0].problem_kind == "conflict"
    assert after_problems.problems[0].conflict_type == "import_consistency_conflict"
    assert [item.title for item in admission.formal_risks] == ["非进口项目要求与外标/国外部件引用存在一致性冲突"]


def test_pb4_constructed_scoring_replay_outputs_conflict_problems_without_false_positive(tmp_path: Path) -> None:
    comparison = ComparisonArtifact(
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

    governance = govern_comparison_artifact("constructed-scoring.docx", comparison)
    before_problems = build_problem_layer("constructed-scoring.docx", governance, enable_conflicts=False)
    after_problems = build_problem_layer("constructed-scoring.docx", governance, enable_conflicts=True)
    admission = admit_problem_result("constructed-scoring.docx", comparison, after_problems, governance)

    output_dir = tmp_path / "pb4-constructed-scoring-replay"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "pb4_summary.json").write_text(
        json.dumps(
            {
                "candidate_count": len(governance.governed_candidates),
                "problem_count_before_conflict": len(before_problems.problems),
                "problem_count_after_conflict": len(after_problems.problems),
                "formal_titles_after_admission": [item.title for item in admission.formal_risks],
                "problem_kinds": {item.canonical_title: item.problem_kind for item in after_problems.problems},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    conflict_types = {item.conflict_type for item in after_problems.problems if item.problem_kind == "conflict"}
    standard_titles = {item.canonical_title for item in after_problems.problems if item.problem_kind == "standard"}

    assert len(before_problems.problems) == 6
    assert len(after_problems.problems) == 4
    assert conflict_types == {"acceptance_plan_scoring_conflict", "payment_scoring_conflict"}
    assert "评分规则要求技术参数中的实质性要求以“★”标示" in standard_titles
    assert "技术参数过细且特征化，存在指向性风险" in standard_titles
