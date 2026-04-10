from __future__ import annotations

import json
from pathlib import Path

from app.common.file_extract import extract_text
from app.config import ReviewSettings
from app.pipelines.v2.evidence import build_evidence_map
from app.pipelines.v2.evidence_layer.pipeline import build_evidence_layer
from app.pipelines.v2.structure import build_structure_map


REAL_FILE = Path("data/uploads/v2/20260401-124322-9d7d80-SZDL2025000495-A.docx")
FUZHOU_REAL_FILE = Path("/Users/linzeran/code/2026-zn/test_target/福建/（埋点）福州一中高中部12号及13号楼学生宿舍家具采购.docx")


def test_ep1_diesel_replay_builds_evidence_layer_without_breaking_topic_inputs(tmp_path: Path) -> None:
    text = extract_text(REAL_FILE)
    structure = build_structure_map(REAL_FILE, text, ReviewSettings(), use_llm=False)
    evidence_map = build_evidence_map(REAL_FILE.name, structure, topic_mode="mature")
    evidence_layer = build_evidence_layer(REAL_FILE.name, structure, evidence_map)

    output_dir = tmp_path / "ep1-diesel-replay"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "evidence_layer.json").write_text(
        json.dumps(evidence_layer.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    assert evidence_layer.evidences
    assert evidence_layer.topic_inputs["technical_standard"].evidence_ids
    assert evidence_layer.topic_inputs["scoring"].sections
    assert (output_dir / "evidence_layer.json").exists()


def test_ep2_replay_classifies_real_file_source_kinds_and_keeps_output_stable() -> None:
    real_files = [REAL_FILE, FUZHOU_REAL_FILE]

    for real_file in real_files:
        text = extract_text(real_file)
        structure = build_structure_map(real_file, text, ReviewSettings(), use_llm=False)
        evidence_map = build_evidence_map(real_file.name, structure, topic_mode="mature")
        evidence_layer = build_evidence_layer(real_file.name, structure, evidence_map)

        evidences = evidence_layer.evidences
        assert evidences
        assert all(item.source_kind for item in evidences)
        assert all("source_kind_trace" in item.metadata for item in evidences)

    diesel_text = extract_text(REAL_FILE)
    diesel_structure = build_structure_map(REAL_FILE, diesel_text, ReviewSettings(), use_llm=False)
    diesel_evidence = build_evidence_map(REAL_FILE.name, diesel_structure, topic_mode="mature")
    diesel_layer = build_evidence_layer(REAL_FILE.name, diesel_structure, diesel_evidence)
    diesel_pairs = {(item.metadata.get("section_title", ""), item.source_kind) for item in diesel_layer.evidences}
    assert ("九、制造商发电机组资质证书 （格式自拟）", "template_clause") in diesel_pairs
    assert any(item.source_kind == "form_clause" for item in diesel_layer.evidences)

    fuzhou_text = extract_text(FUZHOU_REAL_FILE)
    fuzhou_structure = build_structure_map(FUZHOU_REAL_FILE, fuzhou_text, ReviewSettings(), use_llm=False)
    fuzhou_evidence = build_evidence_map(FUZHOU_REAL_FILE.name, fuzhou_structure, topic_mode="mature")
    fuzhou_layer = build_evidence_layer(FUZHOU_REAL_FILE.name, fuzhou_structure, fuzhou_evidence)
    fuzhou_pairs = {(item.metadata.get("section_title", ""), item.source_kind) for item in fuzhou_layer.evidences}
    assert (
        "（2）履约验收时间：计划于何时验收/供应商提出验收申请之日起_______日内组织验收",
        "placeholder_clause",
    ) in fuzhou_pairs
    assert ("资格承诺函", "attachment_clause") in fuzhou_pairs
    assert ("（二）样品要求", "sample_clause") in fuzhou_pairs
    assert any(item.source_kind == "contract_template" for item in fuzhou_layer.evidences)
