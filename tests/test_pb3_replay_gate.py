from __future__ import annotations

import json
from pathlib import Path

from app.common.file_extract import extract_text
from app.pipelines.v2.output_governance import govern_comparison_artifact
from app.pipelines.v2.problem_layer import build_problem_layer
from app.pipelines.v2.risk_admission import admit_problem_result
from app.pipelines.v2.schemas import ComparisonArtifact, MergedRiskCluster


DIESEL_FILE = Path("data/uploads/v2/20260401-124322-9d7d80-SZDL2025000495-A.docx")
FUZHOU_FILE = Path("/Users/linzeran/code/2026-zn/test_target/福建/（埋点）福州一中高中部12号及13号楼学生宿舍家具采购.docx")


def test_pb3_diesel_replay_merges_cross_topic_duplicate_and_resolves_single_layer(tmp_path: Path) -> None:
    text = extract_text(DIESEL_FILE)
    assert "EN55011" in text
    assert "进口" in text

    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="pb3-diesel-tech",
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
    problems = build_problem_layer(DIESEL_FILE.name, governance)
    admission = admit_problem_result(DIESEL_FILE.name, comparison, problems, governance)

    out = tmp_path / "pb3-diesel-replay"
    out.mkdir(parents=True, exist_ok=True)
    (out / "pb3_summary.json").write_text(
        json.dumps(
            {
                "candidate_count": len(governance.governed_candidates),
                "problem_count": len(problems.problems),
                "formal_count": len(admission.formal_risks),
                "pending_count": len(admission.pending_review_items),
                "excluded_count": len(admission.excluded_risks),
                "merged_topic_sources": problems.problems[0].merged_topic_sources,
                "layer_conflict_inputs": problems.problems[0].layer_conflict_inputs,
                "final_problem_resolution": problems.problems[0].final_problem_resolution,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    assert len(governance.governed_candidates) == 1
    assert len(problems.problems) == 1
    assert [item.title for item in admission.formal_risks] == ["非进口项目要求与外标/国外部件引用存在一致性冲突"]
    assert admission.pending_review_items == []
    assert sorted(problems.problems[0].merged_topic_sources) == ["policy", "technical_standard"]


def test_pb3_fuzhou_replay_keeps_neighboring_issues_separate(tmp_path: Path) -> None:
    text = extract_text(FUZHOU_FILE)
    assert "厂家验收标准" in text
    assert "驻厂检查" in text

    comparison = ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="pb3-sample",
                title="样品制作要求具有排他性及泄露信息风险",
                severity="高风险",
                review_type="技术参数倾向性/限制竞争",
                source_locations=["样品要求第3、4点"],
                source_excerpts=["不得出现样品图样，标识等可能泄露投标人样品的任何信息，否则按无效投标处理；样品需提前组装并一次性送达。"],
                risk_judgment=["样品要求过细。"],
                legal_basis=["样品要求不得形成不合理门槛。"],
                rectification=["压缩样品要求。"],
                topics=["sample"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="pb3-acceptance",
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
                cluster_id="pb3-commercial",
                title="商务条款中采购人单方调整权过大且结算方式不明",
                severity="中风险",
                review_type="商务条款失衡",
                source_locations=["商务要求8.3、13.3"],
                source_excerpts=["采购人有权细微调整且中标价不变，偏离超过5%按面积比例换算。"],
                risk_judgment=["采购人单方变更权过大。"],
                legal_basis=["不得背离合同实质性内容。"],
                rectification=["补充双方协商和价格调整机制。"],
                topics=["commercial"],
                source_rules=["baseline"],
            ),
            MergedRiskCluster(
                cluster_id="pb3-supervision",
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
        ]
    )

    governance = govern_comparison_artifact(FUZHOU_FILE.name, comparison)
    problems = build_problem_layer(FUZHOU_FILE.name, governance)
    admission = admit_problem_result(FUZHOU_FILE.name, comparison, problems, governance)

    out = tmp_path / "pb3-fuzhou-replay"
    out.mkdir(parents=True, exist_ok=True)
    (out / "pb3_summary.json").write_text(
        json.dumps(
            {
                "candidate_count": len(governance.governed_candidates),
                "problem_count": len(problems.problems),
                "formal_titles": [item.title for item in admission.formal_risks],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    assert len(governance.governed_candidates) == 4
    assert len(problems.problems) == 4
    assert {item.canonical_title for item in problems.problems} == {
        "样品要求过细且评审规则失衡，存在样品门槛风险",
        "验收标准引用“厂家验收标准”及“样品”，存在模糊表述和单方裁量风险",
        "商务条款中采购人单方变更权过大且结算方式不明",
        "履约监督与解除条件失衡",
    }
