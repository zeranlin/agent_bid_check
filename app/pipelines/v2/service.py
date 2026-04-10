from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from app.common.file_extract import extract_document_text
from app.config import ReviewSettings

from .assembler import assemble_v2_report, build_v2_final_output, build_v2_overview
from .baseline import run_baseline_review
from .compare import compare_review_artifacts, comparison_to_json
from .evidence import build_evidence_map
from .output_governance import govern_comparison_artifact
from .risk_admission import admit_governance_result
from .schemas import V2ReviewArtifacts
from .structure import build_structure_map
from .topic_review import run_topic_reviews


def _emit_stage_banner(stream_callback: Callable[[str], None] | None, text: str) -> None:
    if stream_callback:
        stream_callback(f"\n\n[{text}]\n")


def review_document_v2(
    input_path: Path,
    settings: ReviewSettings,
    progress_callback: Callable[[str, str], None] | None = None,
    stream_callback: Callable[[str], None] | None = None,
    topic_mode: str = "default",
    topic_keys: tuple[str, ...] | list[str] | None = None,
) -> V2ReviewArtifacts:
    if progress_callback:
        progress_callback("file_reading", "系统正在阅读招标文件并提取正文。")
    extracted_text = extract_document_text(input_path)
    if not extracted_text.strip():
        raise ValueError("No text extracted from input file.")

    if progress_callback:
        progress_callback("baseline_review", "正在执行第一层全文直审，优先识别通用合规风险。")
    _emit_stage_banner(stream_callback, "第一层全文直审")
    baseline = run_baseline_review(
        input_path=input_path,
        settings=settings,
        progress_callback=None,
        stream_callback=stream_callback,
    )

    if progress_callback:
        progress_callback("structure_analysis", "正在执行第二层结构增强，识别章节与模块归属。")
    _emit_stage_banner(stream_callback, "第二层结构增强")
    structure = build_structure_map(
        input_path,
        extracted_text,
        settings,
        stream_callback=stream_callback,
    )
    evidence = build_evidence_map(input_path.name, structure, topic_mode=topic_mode, topic_keys=topic_keys)
    if structure.metadata is not None:
        structure.metadata["evidence_bundle_count"] = evidence.metadata.get("evidence_bundle_count", 0)

    if progress_callback:
        progress_callback("topic_review", "正在执行第三层专题深审，核查标准、评分与商务细节。")
    _emit_stage_banner(stream_callback, "第三层专题深审")
    topics = run_topic_reviews(
        document_name=input_path.name,
        evidence=evidence,
        settings=settings,
        topic_mode=topic_mode,
        topic_keys=topic_keys,
        stream_callback=stream_callback,
    )

    if progress_callback:
        progress_callback("report_structuring", "正在合并三层结果并生成统一审查报告。")
    comparison = compare_review_artifacts(input_path.name, baseline, topics)
    governance = govern_comparison_artifact(input_path.name, comparison)
    admission = admit_governance_result(input_path.name, comparison, governance)
    final_markdown = assemble_v2_report(
        input_path.name,
        baseline,
        structure,
        topics,
        comparison=comparison,
        governance=governance,
        admission=admission,
    )
    return V2ReviewArtifacts(
        extracted_text=extracted_text,
        baseline=baseline,
        structure=structure,
        topics=topics,
        final_markdown=final_markdown,
        evidence=evidence,
        comparison=comparison,
        governance=governance,
        admission=admission,
    )


def save_review_artifacts_v2(artifacts: V2ReviewArtifacts, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "extracted_text.md").write_text(artifacts.extracted_text, encoding="utf-8")
    (output_dir / "baseline_review.md").write_text(artifacts.baseline.content, encoding="utf-8")
    (output_dir / "document_map.json").write_text(artifacts.structure.content, encoding="utf-8")
    if artifacts.evidence is not None:
        (output_dir / "evidence_map.json").write_text(artifacts.evidence.content, encoding="utf-8")
    if artifacts.comparison is not None:
        (output_dir / "comparison.json").write_text(comparison_to_json(artifacts.comparison), encoding="utf-8")
        if artifacts.governance is not None:
            (output_dir / "governed_output.json").write_text(
                json.dumps(artifacts.governance.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        if artifacts.admission is not None:
            (output_dir / "risk_admission_output.json").write_text(
                json.dumps(artifacts.admission.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        (output_dir / "final_output.json").write_text(
            json.dumps(
                build_v2_final_output(
                    "",
                    artifacts.baseline,
                    artifacts.structure,
                    artifacts.topics,
                    comparison=artifacts.comparison,
                    governance=artifacts.governance,
                    admission=artifacts.admission,
                ),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    (output_dir / "review.md").write_text(artifacts.final_markdown, encoding="utf-8")
    (output_dir / "final_review.md").write_text(artifacts.final_markdown, encoding="utf-8")
    (output_dir / "v2_overview.json").write_text(
        json.dumps(build_v2_overview(artifacts.structure, artifacts.topics), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    topic_dir = output_dir / "topic_reviews"
    topic_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "review_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "baseline_raw.md").write_text(artifacts.baseline.raw_output, encoding="utf-8")
    (raw_dir / "structure_raw.json").write_text(artifacts.structure.raw_output, encoding="utf-8")
    if artifacts.evidence is not None:
        (raw_dir / "evidence_raw.json").write_text(artifacts.evidence.raw_output, encoding="utf-8")

    for topic in artifacts.topics:
        topic_payload = {
            "topic": topic.topic,
            "summary": topic.summary,
            "risk_points": [
                {
                    "title": risk.title,
                    "severity": risk.severity,
                    "review_type": risk.review_type,
                    "source_location": risk.source_location,
                    "source_excerpt": risk.source_excerpt,
                    "risk_judgment": risk.risk_judgment,
                    "legal_basis": risk.legal_basis,
                    "rectification": risk.rectification,
                }
                for risk in topic.risk_points
            ],
            "need_manual_review": topic.need_manual_review,
            "coverage_note": topic.coverage_note,
            "metadata": topic.metadata,
        }
        (topic_dir / f"{topic.topic}.json").write_text(
            json.dumps(topic_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (raw_dir / f"{topic.topic}_raw.md").write_text(topic.raw_output, encoding="utf-8")
