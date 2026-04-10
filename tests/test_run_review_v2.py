from __future__ import annotations

import sys
from pathlib import Path

from app.pipelines.v2.schemas import V2ReviewArtifacts, V2StageArtifact

import scripts.run_review_v2 as run_review_v2


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
