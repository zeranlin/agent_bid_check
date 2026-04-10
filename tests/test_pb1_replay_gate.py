from __future__ import annotations

import json
from pathlib import Path

from app.common.schemas import RiskPoint
from app.common.file_extract import extract_text
from app.config import ReviewSettings
from app.pipelines.v2.compare import compare_review_artifacts
from app.pipelines.v2.evidence import build_evidence_map
from app.pipelines.v2.evidence_layer.pipeline import build_evidence_layer
from app.pipelines.v2.output_governance import govern_comparison_artifact
from app.pipelines.v2.problem_layer import build_problem_layer
from app.pipelines.v2.risk_admission import admit_problem_result
from app.pipelines.v2.schemas import TopicReviewArtifact, V2StageArtifact
from app.pipelines.v2.structure import build_structure_map
from app.pipelines.v2.topic_review import _get_evidence_bundle


REAL_FILE = Path("data/uploads/v2/20260401-124322-9d7d80-SZDL2025000495-A.docx")


def test_pb1_diesel_replay_passes_through_problem_layer_without_formal_regression(tmp_path: Path) -> None:
    text = extract_text(REAL_FILE)
    structure = build_structure_map(REAL_FILE, text, ReviewSettings(), use_llm=False)
    evidence_map = build_evidence_map(REAL_FILE.name, structure, topic_mode="mature")
    evidence_layer = build_evidence_layer(REAL_FILE.name, structure, evidence_map)
    scoring_bundle = _get_evidence_bundle(evidence_layer, "scoring")
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="scoring",
            risk_points=[
                RiskPoint(
                    title="将项目验收方案纳入评审因素，违反评审规则合规性要求",
                    severity="高风险",
                    review_type="评分因素合规性审查",
                    source_location=scoring_bundle["sections"][0]["location"],
                    source_excerpt=scoring_bundle["sections"][0]["excerpt"],
                    risk_judgment=["验收方案被直接作为评分条件。"],
                    legal_basis=["评审因素应与采购需求和合同履约相关。"],
                    rectification=["删除与验收方案直接挂钩的评分条件。"],
                )
            ],
            metadata={
                "selected_sections": scoring_bundle["sections"],
                "selected_evidence_ids": scoring_bundle["evidence_ids"],
            },
        )
    ]
    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果")
    comparison = compare_review_artifacts(REAL_FILE.name, baseline, topics)
    governance = govern_comparison_artifact(REAL_FILE.name, comparison)
    problem_result = build_problem_layer(REAL_FILE.name, governance)
    admission = admit_problem_result(REAL_FILE.name, comparison, problem_result, governance)

    output_dir = tmp_path / "pb1-diesel-replay"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "problem_layer.json").write_text(
        json.dumps(problem_result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    assert problem_result.problems
    assert admission.input_summary["problem_summary"]["problem_count"] == len(problem_result.problems)
    assert (output_dir / "problem_layer.json").exists()
