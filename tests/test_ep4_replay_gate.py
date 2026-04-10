from __future__ import annotations

from pathlib import Path

from app.common.file_extract import extract_text
from app.config import ReviewSettings
from app.pipelines.v2.evidence import build_evidence_map
from app.pipelines.v2.evidence_layer.pipeline import build_evidence_layer
from app.pipelines.v2.risk_admission.evidence_classifier import infer_evidence_support_signal
from app.pipelines.v2.structure import build_structure_map


DIESEL_REAL_FILE = Path("data/uploads/v2/20260401-124322-9d7d80-SZDL2025000495-A.docx")
FUZHOU_REAL_FILE = Path("/Users/linzeran/code/2026-zn/test_target/福建/（埋点）福州一中高中部12号及13号楼学生宿舍家具采购.docx")


def test_ep4_replay_classifies_clause_role_strength_and_hard_evidence_in_real_files() -> None:
    diesel_text = extract_text(DIESEL_REAL_FILE)
    diesel_structure = build_structure_map(DIESEL_REAL_FILE, diesel_text, ReviewSettings(), use_llm=False)
    diesel_evidence = build_evidence_map(DIESEL_REAL_FILE.name, diesel_structure, topic_mode="mature")
    diesel_layer = build_evidence_layer(DIESEL_REAL_FILE.name, diesel_structure, diesel_evidence)

    diesel_triplets = {
        (item.metadata.get("section_title", ""), item.clause_role, item.hard_evidence)
        for item in diesel_layer.evidences
    }
    assert ("5.2 投标人资格要求", "gate", True) in diesel_triplets
    assert ("付款方式", "commercial_obligation", True) in diesel_triplets
    assert ("1.规格及技术参数", "technical_requirement", True) in diesel_triplets

    fuzhou_text = extract_text(FUZHOU_REAL_FILE)
    fuzhou_structure = build_structure_map(FUZHOU_REAL_FILE, fuzhou_text, ReviewSettings(), use_llm=False)
    fuzhou_evidence = build_evidence_map(FUZHOU_REAL_FILE.name, fuzhou_structure, topic_mode="mature")
    fuzhou_layer = build_evidence_layer(FUZHOU_REAL_FILE.name, fuzhou_structure, fuzhou_evidence)

    fuzhou_triplets = {
        (item.metadata.get("section_title", ""), item.clause_role, item.hard_evidence)
        for item in fuzhou_layer.evidences
    }
    assert ("（二）样品要求", "supporting_material", False) in fuzhou_triplets
    assert ("（2）履约验收时间：计划于何时验收/供应商提出验收申请之日起_______日内组织验收", "acceptance_basis", False) in fuzhou_triplets
    assert ("资格承诺函", "supporting_material", False) in fuzhou_triplets


def test_ep4_admission_can_consume_evidence_layer_signals() -> None:
    section = {
        "title": "评分标准",
        "source_kind": "body_clause",
        "business_domain": "scoring",
        "clause_role": "scoring_factor",
        "evidence_strength": "strong",
        "hard_evidence": True,
    }

    signal = infer_evidence_support_signal(section)

    assert signal["admission_evidence_passed"] is True
    assert signal["admission_reason"] == "hard_evidence_available"
