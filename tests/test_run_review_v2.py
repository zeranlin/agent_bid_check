from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from app.pipelines.v2.schemas import V2ReviewArtifacts, V2StageArtifact

import scripts.run_review_v2 as run_review_v2


QUANZHOU_LIVE_FILE = Path("/Users/linzeran/code/2026-zn/test_target/泉州/操场跑道、篮球场、小操场维护项目招标文件1.docx")


def _build_dummy_artifacts() -> V2ReviewArtifacts:
    stage = V2StageArtifact(name="dummy", content="")
    stage.metadata = {}
    return V2ReviewArtifacts(
        extracted_text="dummy",
        baseline=stage,
        structure=stage,
        topics=[],
        final_markdown="# dummy",
        evidence=stage,
        evidence_layer=None,
        comparison=None,
    )


def test_parse_args_defaults_to_mature(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_review_v2.py", "sample.docx", "-o", "data/results/v2/demo-run"],
    )
    args = run_review_v2.parse_args()
    assert args.topic_mode == "mature"


def test_main_uses_mature_topic_mode_by_default(monkeypatch, tmp_path: Path) -> None:
    input_file = tmp_path / "sample.docx"
    input_file.write_text("dummy", encoding="utf-8")
    output_dir = tmp_path / "out"
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        sys,
        "argv",
        ["run_review_v2.py", str(input_file), "-o", str(output_dir)],
    )

    monkeypatch.setattr(run_review_v2.ReviewSettings, "from_env", staticmethod(lambda: run_review_v2.ReviewSettings()))

    def fake_review_document_v2(input_path, settings, progress_callback=None, stream_callback=None, topic_mode="default", topic_keys=None):
        captured["input_path"] = input_path
        captured["topic_mode"] = topic_mode
        return _build_dummy_artifacts()

    def fake_save_review_artifacts_v2(artifacts, save_dir):
        captured["output_dir"] = save_dir

    monkeypatch.setattr(run_review_v2, "review_document_v2", fake_review_document_v2)
    monkeypatch.setattr(run_review_v2, "save_review_artifacts_v2", fake_save_review_artifacts_v2)

    exit_code = run_review_v2.main()

    assert exit_code == 0
    assert captured["input_path"] == input_file.resolve()
    assert captured["output_dir"] == output_dir.resolve()
    assert captured["topic_mode"] == "mature"


def test_live_quanzhou_review_min_002_promotes_only_two_pending_titles_to_formal(tmp_path: Path) -> None:
    if os.getenv("RUN_LIVE_REVIEW_TESTS") != "1":
        pytest.skip("set RUN_LIVE_REVIEW_TESTS=1 to execute live review against the real Quanzhou document")
    if not QUANZHOU_LIVE_FILE.exists():
        pytest.skip(f"missing live file: {QUANZHOU_LIVE_FILE}")

    artifacts = run_review_v2.review_document_v2(
        QUANZHOU_LIVE_FILE,
        run_review_v2.ReviewSettings.from_env(),
        topic_mode="mature",
    )
    snapshot = artifacts.final_snapshot or {}
    final_risks = snapshot.get("final_risks", {})
    formal_titles = {item.get("title") for item in final_risks.get("formal_risks", [])}
    pending_titles = {item.get("title") for item in final_risks.get("pending_review_items", [])}
    assert len(formal_titles) == 6

    assert {
        "强制性标准条款未按评审规则标注★，可能导致实质性响应边界不清",
        "验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险",
        "疑似限定或倾向特定品牌/供应商",
        "将样品要求/验收方案不当作为评审或履约门槛",
        "合同支付条款存在严重逻辑矛盾，付款比例总和超过100%",
        "引用已废止标准且未明确替代版本",
    } <= formal_titles
    assert "远程开标逾期解密后果表述需进一步确认" in pending_titles
    assert "验收流程、主体及不合格处理机制表述模糊，缺乏可操作性" in pending_titles
    assert "合同支付条款存在严重逻辑矛盾，付款比例总和超过100%" not in pending_titles
    assert "引用已废止标准且未明确替代版本" not in pending_titles
