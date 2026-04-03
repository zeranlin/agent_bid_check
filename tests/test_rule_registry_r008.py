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


def test_r008_rule_file_exists_and_validates() -> None:
    path = ROOT / "rules" / "registry" / "R-008.yaml"
    assert path.exists()
    result = validate_rule_file(path)
    assert result.ok, result.errors


def test_r008_rule_refs_exist_and_align_to_registry_boundary() -> None:
    r008 = load_rule_file(ROOT / "rules" / "registry" / "R-008.yaml")
    r005 = load_rule_file(ROOT / "rules" / "registry" / "R-005.yaml")

    assert r008["rule_id"] == "R-008"
    assert r008["boundary_relation"]["parent_rule"] == "R-005"
    assert "R-008" in r005["boundary_relation"]["child_rules"]
    assert r008["output"]["formal_title"] == "评分项中要求赠送非项目物资，存在明显不当加分和评审合规风险"
    assert r008["tests"]["unit"]
    assert r008["samples"]["positive"]
    assert r008["samples"]["negative"]
    assert r008["samples"]["replay"]

    for path in _iter_ref_paths(r008["samples"]) + _iter_ref_paths(r008["tests"]) + _iter_ref_paths(r008["task_refs"]):
        assert path.exists(), f"missing mapped path: {path}"


def test_r008_sample_refs_point_to_r008_assets() -> None:
    payloads = []
    for name in ("positive-01.json", "negative-01.json", "replay-01.json"):
        path = ROOT / "data" / "examples" / "rules" / "R-008" / name
        payload = json.loads(path.read_text(encoding="utf-8"))
        payloads.append(payload)
        assert payload["rule_id"] == "R-008"

    positive, negative, replay = payloads
    assert positive["sample_id"] == "regression_scoring_gifts_positive_008"
    assert negative["sample_id"] == "regression_scoring_gifts_negative_necessary_accessories_008"
    assert replay["expected_result"] == "hit"
    assert replay["reference_result_dir"] == "data/results/v2/20260403-r008-real-replay"
