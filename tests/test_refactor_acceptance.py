from __future__ import annotations

import json
from pathlib import Path

from app.pipelines.v2.refactor_acceptance import (
    REQUIRED_ACCEPTANCE_DOCS,
    REQUIRED_REPLAY_ARTIFACTS,
    REQUIRED_SCOPE_TASKS,
    build_refactor_acceptance_summary,
    parse_tracker_task_statuses,
    validate_replay_artifact_dir,
)


ROOT = Path(__file__).resolve().parents[1]


def test_parse_tracker_task_statuses_covers_refactor_scope_tasks() -> None:
    statuses = parse_tracker_task_statuses(ROOT / "docs" / "trackers" / "v2-remediation-tracker.md")

    for task_id in REQUIRED_SCOPE_TASKS:
        assert task_id in statuses
        assert statuses[task_id]["status"] in {"已通过", "已关闭"}


def test_validate_replay_artifact_dir_requires_standard_outputs(tmp_path: Path) -> None:
    replay_dir = tmp_path / "replay"
    replay_dir.mkdir()
    (replay_dir / "final_snapshot.json").write_text("{}", encoding="utf-8")

    result = validate_replay_artifact_dir(replay_dir)

    assert result["passed"] is False
    assert set(REQUIRED_REPLAY_ARTIFACTS) - set(result["present_artifacts"])
    assert result["missing_artifacts"]


def test_build_refactor_acceptance_summary_validates_docs_tracker_replays_and_conflict_snapshot() -> None:
    summary = build_refactor_acceptance_summary(ROOT)

    assert summary["overall_ready_for_closure"] is True
    assert summary["gate_passed"] is True
    assert summary["tracker_alignment"]["missing_tasks"] == []
    assert summary["tracker_alignment"]["invalid_status_tasks"] == []
    assert summary["tracker_alignment"]["artifact_missing_tasks"] == []
    assert summary["replay_alignment"]["missing_replays"] == []
    assert summary["replay_alignment"]["failing_replays"] == []
    assert summary["document_alignment"]["missing_docs"] == []
    assert summary["final_snapshot_alignment"]["conflict_snapshot_ok"] is True


def test_required_acceptance_docs_exist() -> None:
    for relative_path in REQUIRED_ACCEPTANCE_DOCS:
        assert (ROOT / relative_path).exists(), relative_path


def test_gr1_replay_summaries_are_all_green() -> None:
    for replay_name in ("gr1-diesel-baseline", "gr1-fujian-baseline", "gr1-fuzhou-baseline"):
        summary = json.loads((ROOT / "data" / "results" / "v2" / replay_name / "replay_summary.json").read_text(encoding="utf-8"))
        assert summary["passed"] is True

