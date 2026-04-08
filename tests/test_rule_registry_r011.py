from __future__ import annotations

import json
from pathlib import Path

from app.governance.rule_registry import load_rule_file, validate_rule_file


ROOT = Path(__file__).resolve().parents[1]


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


def test_r011_rule_file_exists_and_validates() -> None:
    path = ROOT / "rules" / "registry" / "R-011.yaml"
    assert path.exists()
    result = validate_rule_file(path)
    assert result.ok, result.errors


def test_r011_rule_refs_exist_and_align() -> None:
    r011 = load_rule_file(ROOT / "rules" / "registry" / "R-011.yaml")
    assert r011["rule_id"] == "R-011"
    assert r011["output"]["formal_title"] == "要求提供资质证照原件或电子证照纸质件，存在材料提交边界设置不当风险"
    assert r011["tests"]["unit"]
    assert r011["samples"]["positive"]
    assert r011["samples"]["negative"]
    assert r011["samples"]["replay"]

    for path in _iter_ref_paths(r011["samples"]) + _iter_ref_paths(r011["tests"]) + _iter_ref_paths(r011["task_refs"]):
        assert path.exists(), f"missing mapped path: {path}"


def test_r011_sample_refs_point_to_r011_assets() -> None:
    payloads = []
    for name in ("positive-01.json", "negative-01.json", "replay-01.json"):
        path = ROOT / "data" / "examples" / "rules" / "R-011" / name
        payload = json.loads(path.read_text(encoding="utf-8"))
        payloads.append(payload)
        assert payload["rule_id"] == "R-011"

    positive, negative, replay = payloads
    assert positive["sample_id"] == "regression_original_or_paper_certificate_submission_positive_013"
    assert negative["sample_id"] == "regression_original_or_paper_certificate_submission_negative_post_award_013"
    assert replay["sample_id"] == "regression_original_or_paper_certificate_submission_positive_013"
