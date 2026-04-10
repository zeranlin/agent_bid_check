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


DIESEL_FILE = Path("data/uploads/v2/20260401-124322-9d7d80-SZDL2025000495-A.docx")


def _find_section(bundle: dict, keyword: str) -> dict:
    for section in bundle["sections"]:
        excerpt = str(section.get("excerpt", ""))
        if keyword in excerpt:
            return section
    raise AssertionError(f"missing replay section for keyword: {keyword}")


def test_pb2_diesel_replay_merges_certification_main_and_support_into_one_problem(tmp_path: Path) -> None:
    text = extract_text(DIESEL_FILE)
    structure = build_structure_map(DIESEL_FILE, text, ReviewSettings(), use_llm=False)
    evidence_map = build_evidence_map(DIESEL_FILE.name, structure, topic_mode="mature")
    evidence_layer = build_evidence_layer(DIESEL_FILE.name, structure, evidence_map)
    scoring_bundle = _get_evidence_bundle(evidence_layer, "scoring")
    cert_section = _find_section(scoring_bundle, "认证证书")

    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="scoring",
            risk_points=[
                RiskPoint(
                    title="以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险",
                    severity="高风险",
                    review_type="评分因素合规性 / 限定特定认证或发证机构",
                    source_location=cert_section["location"],
                    source_excerpt=cert_section["excerpt"],
                    risk_judgment=["主风险应保留。"],
                    legal_basis=["不得限定或者指定特定认证机构。"],
                    rectification=["删除特定认证机构限定。"],
                ),
                RiskPoint(
                    title="认证项权重偏高且与履约关联不足，存在倾向性评分风险",
                    severity="中风险",
                    review_type="评分项合规性审查",
                    source_location=cert_section["location"],
                    source_excerpt=cert_section["excerpt"],
                    risk_judgment=["这是同一组评分证据中的权重侧佐证。"],
                    legal_basis=["认证项权重不宜畸高。"],
                    rectification=["压缩认证项分值。"],
                ),
            ],
            metadata={
                "selected_sections": [cert_section],
                "selected_evidence_ids": scoring_bundle["evidence_ids"],
            },
        )
    ]

    baseline = V2StageArtifact(name="baseline", content="# 招标文件合规审查结果")
    comparison = compare_review_artifacts(DIESEL_FILE.name, baseline, topics)
    governance = govern_comparison_artifact(DIESEL_FILE.name, comparison)
    problem_result = build_problem_layer(DIESEL_FILE.name, governance)
    admission = admit_problem_result(DIESEL_FILE.name, comparison, problem_result, governance)

    output_dir = tmp_path / "pb2-diesel-replay"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "problem_layer.json").write_text(
        json.dumps(problem_result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "pb2_summary.json").write_text(
        json.dumps(
            {
                "candidate_count": len(governance.governed_candidates),
                "problem_count": len(problem_result.problems),
                "formal_titles": [item.title for item in admission.formal_risks],
                "supporting_titles": [
                    item.decision.canonical_title
                    for item in problem_result.problems[0].supporting_candidates
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    assert len(governance.governed_candidates) == 2
    assert len(problem_result.problems) == 1
    assert [item.title for item in admission.formal_risks] == ["以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险"]
    assert [item.decision.canonical_title for item in problem_result.problems[0].supporting_candidates] == [
        "认证项权重偏高且与履约关联不足，存在倾向性评分风险"
    ]
