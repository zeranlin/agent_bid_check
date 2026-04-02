from __future__ import annotations

import json
from pathlib import Path

from app.governance.rule_registry import load_rule_file, validate_rule_file


ROOT = Path(__file__).resolve().parents[1]
RULE_IDS = [f"R-00{i}" for i in range(1, 8)]


def _iter_ref_paths(values: object) -> list[Path]:
    paths: list[Path] = []
    if isinstance(values, list):
        for item in values:
            if isinstance(item, str):
                paths.append(ROOT / item)
    elif isinstance(values, dict):
        for item in values.values():
            paths.extend(_iter_ref_paths(item))
    return paths


def test_first_batch_rule_files_exist_and_validate() -> None:
    for rule_id in RULE_IDS:
        path = ROOT / "rules" / "registry" / f"{rule_id}.yaml"
        assert path.exists(), f"missing {path}"
        result = validate_rule_file(path)
        assert result.ok, f"{rule_id} validation errors: {result.errors}"


def test_first_batch_rule_status_matches_tracker_expectation() -> None:
    for rule_id in RULE_IDS:
        payload = load_rule_file(ROOT / "rules" / "registry" / f"{rule_id}.yaml")
        assert payload["status"] == "active"


def test_first_batch_rule_sample_refs_exist_and_cover_positive_negative_replay() -> None:
    for rule_id in RULE_IDS:
        payload = load_rule_file(ROOT / "rules" / "registry" / f"{rule_id}.yaml")
        samples = payload["samples"]
        assert samples["positive"], f"{rule_id} missing positive sample refs"
        assert samples["negative"], f"{rule_id} missing negative sample refs"
        assert samples["replay"], f"{rule_id} missing replay sample refs"
        for path in _iter_ref_paths(samples):
            assert path.exists(), f"missing sample ref: {path}"
            sample_payload = json.loads(path.read_text(encoding="utf-8"))
            assert sample_payload["rule_id"] == rule_id


def test_first_batch_rule_test_and_task_refs_exist() -> None:
    for rule_id in RULE_IDS:
        payload = load_rule_file(ROOT / "rules" / "registry" / f"{rule_id}.yaml")
        tests = _iter_ref_paths(payload["tests"])
        task_refs = _iter_ref_paths(payload["task_refs"])
        assert tests, f"{rule_id} missing tests refs"
        assert task_refs, f"{rule_id} missing task refs"
        for path in tests + task_refs:
            assert path.exists(), f"missing mapped path: {path}"
