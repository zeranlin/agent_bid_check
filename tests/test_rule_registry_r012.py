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


def test_r012_rule_file_exists_and_validates() -> None:
    path = ROOT / "rules" / "registry" / "R-012.yaml"
    assert path.exists()
    result = validate_rule_file(path)
    assert result.ok, result.errors


def test_r012_rule_refs_exist_and_align() -> None:
    r012 = load_rule_file(ROOT / "rules" / "registry" / "R-012.yaml")
    assert r012["rule_id"] == "R-012"
    assert r012["output"]["formal_title"] == "以供应商主体身份或地域条件设置准入门槛，存在限制竞争风险"
    assert r012["tests"]["unit"]
    assert r012["samples"]["positive"]
    assert r012["samples"]["negative"]
    assert r012["samples"]["replay"]

    for path in _iter_ref_paths(r012["samples"]) + _iter_ref_paths(r012["tests"]) + _iter_ref_paths(r012["task_refs"]):
        assert path.exists(), f"missing mapped path: {path}"


def test_r012_sample_refs_point_to_r012_assets() -> None:
    payloads = []
    for name in ("positive-01.json", "negative-01.json", "replay-01.json"):
        path = ROOT / "data" / "examples" / "rules" / "R-012" / name
        payload = json.loads(path.read_text(encoding="utf-8"))
        payloads.append(payload)
        assert payload["rule_id"] == "R-012"

    positive, negative, replay = payloads
    assert positive["sample_id"] == "regression_supplier_identity_or_region_positive_014"
    assert negative["sample_id"] == "regression_supplier_identity_or_region_negative_post_award_service_014"
    assert replay["sample_id"] == "regression_supplier_identity_or_region_positive_014"
