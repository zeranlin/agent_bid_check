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


def test_r010_rule_file_exists_and_validates() -> None:
    path = ROOT / "rules" / "registry" / "R-010.yaml"
    assert path.exists()
    result = validate_rule_file(path)
    assert result.ok, result.errors


def test_r010_rule_refs_exist_and_align() -> None:
    r010 = load_rule_file(ROOT / "rules" / "registry" / "R-010.yaml")
    assert r010["rule_id"] == "R-010"
    assert r010["output"]["formal_title"] == "将已取消或非强制资质资格认证作为评审因素，存在评分设置不合规风险"
    assert r010["tests"]["unit"]
    assert r010["samples"]["positive"]
    assert r010["samples"]["negative"]
    assert r010["samples"]["replay"]

    for path in _iter_ref_paths(r010["samples"]) + _iter_ref_paths(r010["tests"]) + _iter_ref_paths(r010["task_refs"]):
        assert path.exists(), f"missing mapped path: {path}"


def test_r010_sample_refs_point_to_r010_assets() -> None:
    payloads = []
    for name in ("positive-01.json", "negative-01.json", "replay-01.json"):
        path = ROOT / "data" / "examples" / "rules" / "R-010" / name
        payload = json.loads(path.read_text(encoding="utf-8"))
        payloads.append(payload)
        assert payload["rule_id"] == "R-010"

    positive, negative, replay = payloads
    assert positive["sample_id"] == "regression_scoring_cancelled_or_non_mandatory_positive_012"
    assert negative["sample_id"] == "regression_scoring_cancelled_or_non_mandatory_negative_qualification_only_012"
    assert replay["sample_id"] == "regression_scoring_cancelled_or_non_mandatory_positive_012"
