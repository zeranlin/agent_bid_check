from __future__ import annotations

import json
from pathlib import Path

from app.common.eval_dataset import load_eval_manifest, resolve_v2_eval_sample_path


def test_load_eval_manifest_and_resolve_stage_paths() -> None:
    manifest_path = Path("data/eval/v2_manifest.json")
    manifest = load_eval_manifest(manifest_path)
    assert manifest["version"] == "v2"
    assert "baseline" in manifest["stages"]
    assert resolve_v2_eval_sample_path("baseline", manifest_path=manifest_path).name == "v2_baseline_eval_samples.json"
    assert resolve_v2_eval_sample_path("compare", manifest_path=manifest_path).name == "v2_compare_eval_samples.json"


def test_eval_labels_are_initialized_with_json_arrays() -> None:
    for path in (
        Path("data/eval/v2_labels/v2_baseline_eval_samples.json"),
        Path("data/eval/v2_labels/v2_structure_eval_samples.json"),
        Path("data/eval/v2_labels/v2_topic_eval_samples.json"),
        Path("data/eval/v2_labels/v2_compare_eval_samples.json"),
        Path("data/eval/v2_labels/v2_regression_eval_samples.json"),
    ):
        assert isinstance(json.loads(path.read_text(encoding="utf-8")), list)
