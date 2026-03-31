from __future__ import annotations

import json
from pathlib import Path

from app.config import PROJECT_ROOT as APP_PROJECT_ROOT


DEFAULT_EVAL_ROOT = APP_PROJECT_ROOT / "data" / "eval"
DEFAULT_V2_MANIFEST = DEFAULT_EVAL_ROOT / "v2_manifest.json"
V2_STAGE_FILENAMES = {
    "baseline": "v2_baseline_eval_samples.json",
    "structure": "v2_structure_eval_samples.json",
    "topics": "v2_topic_eval_samples.json",
    "compare": "v2_compare_eval_samples.json",
    "regression": "v2_regression_eval_samples.json",
}


def load_eval_manifest(manifest_path: Path | None = None) -> dict:
    target = manifest_path or DEFAULT_V2_MANIFEST
    if not target.exists():
        return {}
    data = json.loads(target.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def resolve_v2_eval_sample_path(
    stage: str,
    *,
    samples_path: Path | None = None,
    dataset_root: Path | None = None,
    manifest_path: Path | None = None,
) -> Path:
    if samples_path is not None:
        return samples_path

    manifest = load_eval_manifest(manifest_path)
    stages = manifest.get("stages", {}) if isinstance(manifest.get("stages", {}), dict) else {}
    stage_payload = stages.get(stage, {}) if isinstance(stages, dict) else {}
    labels_file = str(stage_payload.get("labels_file", "")).strip()
    if labels_file:
        base = (manifest_path or DEFAULT_V2_MANIFEST).parent
        return (base / labels_file).resolve()

    root = dataset_root or DEFAULT_EVAL_ROOT
    return root / "v2_labels" / V2_STAGE_FILENAMES[stage]
