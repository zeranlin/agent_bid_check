from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from app.common.file_extract import extract_text
from app.common.schemas import RiskPoint
from app.config import ReviewSettings

from .compare import compare_review_artifacts
from .evidence import build_evidence_map
from .final_snapshot import build_v2_final_snapshot, render_v2_markdown_from_snapshot
from .output_governance import govern_comparison_artifact
from .problem_layer import build_problem_layer
from .risk_admission import admit_problem_result
from .schemas import TopicReviewArtifact, V2ReviewArtifacts, V2StageArtifact
from .service import save_review_artifacts_v2
from .structure import build_structure_map


def load_real_replay_baseline_suite(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path).expanduser().resolve()
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("real replay baseline suite must be a mapping")
    documents = payload.get("documents", [])
    if not isinstance(documents, list) or not documents:
        raise ValueError("real replay baseline suite must define non-empty documents")
    normalized = deepcopy(payload)
    normalized["_config_path"] = str(path)
    return normalized


def load_real_replay_matrix_suite(config_path: str | Path) -> dict[str, Any]:
    suite = load_real_replay_baseline_suite(config_path)
    for document in suite["documents"]:
        if not str(document.get("document_domain", "")).strip():
            raise ValueError(f"replay matrix document missing document_domain: {document.get('document_id', '<unknown>')}")
    return suite


def _resolve_path(raw_path: str, config_path: str | None = None) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path.resolve()
    if config_path:
        return (Path(config_path).resolve().parent / path).resolve()
    return path.resolve()


def _load_seed_topics(seed_result_dir: Path, source_file: Path, topic_mode: str) -> tuple[V2StageArtifact, V2StageArtifact, list[TopicReviewArtifact]]:
    baseline_path = seed_result_dir / "baseline_review.md"
    source_run = seed_result_dir / "topic_reviews"
    text = extract_text(source_file)
    structure = build_structure_map(source_file, text, ReviewSettings(), use_llm=False)
    evidence = build_evidence_map(source_file.name, structure, topic_mode=topic_mode)
    bundles = evidence.metadata.get("topic_evidence_bundles", {})
    coverages = evidence.metadata.get("topic_coverages", {})
    topics: list[TopicReviewArtifact] = []
    if source_run.exists():
        for path in sorted(source_run.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            topic_key = payload.get("topic", path.stem)
            bundle = bundles.get(topic_key, {})
            sections = [section for section in bundle.get("sections", []) if isinstance(section, dict)]
            metadata = {
                **dict(payload.get("metadata", {}) or {}),
                "selected_sections": [
                    {
                        "title": section.get("title", ""),
                        "start_line": section.get("start_line"),
                        "end_line": section.get("end_line"),
                        "module": section.get("module", ""),
                    }
                    for section in sections
                ],
                "evidence_bundle": bundle,
                "topic_coverage": coverages.get(topic_key, {}),
            }
            topics.append(
                TopicReviewArtifact(
                    topic=topic_key,
                    summary=payload.get("summary", ""),
                    risk_points=[RiskPoint(**risk) for risk in payload.get("risk_points", [])],
                    need_manual_review=payload.get("need_manual_review", False),
                    coverage_note=payload.get("coverage_note", ""),
                    metadata=metadata,
                )
            )
    baseline = V2StageArtifact(
        name="baseline",
        content=baseline_path.read_text(encoding="utf-8")
        if baseline_path.exists()
        else f"# 招标文件合规审查结果\n\n审查对象：`{source_file.name}`\n",
    )
    return baseline, structure, topics


def _match_assertion(item: dict[str, Any], assertion: dict[str, Any]) -> bool:
    if assertion.get("title") and str(item.get("title", "")).strip() != str(assertion.get("title", "")).strip():
        return False
    if assertion.get("family_key") and str(item.get("family_key", "")).strip() != str(assertion.get("family_key", "")).strip():
        return False
    if assertion.get("problem_kind") and str(item.get("problem_kind", "")).strip() != str(assertion.get("problem_kind", "")).strip():
        return False
    if assertion.get("conflict_type") and str(item.get("conflict_type", "")).strip() != str(assertion.get("conflict_type", "")).strip():
        return False
    return True


def _find_layers(snapshot: dict[str, Any], assertion: dict[str, Any]) -> list[str]:
    final_risks = snapshot.get("final_risks", {}) if isinstance(snapshot, dict) else {}
    matched_layers: list[str] = []
    for layer in ("formal_risks", "pending_review_items", "excluded_risks"):
        items = final_risks.get(layer, []) if isinstance(final_risks, dict) else []
        if any(_match_assertion(item, assertion) for item in items if isinstance(item, dict)):
            matched_layers.append(layer)
    return matched_layers


def _build_assertion_record(snapshot: dict[str, Any], assertion: dict[str, Any], expected_layer: str | None) -> dict[str, Any]:
    actual_layers = _find_layers(snapshot, assertion)
    if expected_layer == "reported":
        matched = any(layer in {"formal_risks", "pending_review_items"} for layer in actual_layers)
    else:
        matched = expected_layer in actual_layers if expected_layer else not any(
            layer in {"formal_risks", "pending_review_items"} for layer in actual_layers
        )
    return {
        "assertion_id": assertion.get("id", ""),
        "assertion": dict(assertion),
        "expected_layer": expected_layer or "not_reported",
        "actual_layers": actual_layers,
        "matched": matched,
    }


def evaluate_replay_assertions(snapshot: dict[str, Any], assertions: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    should_report = [_build_assertion_record(snapshot, item, "reported") for item in assertions.get("should_report", [])]
    should_pending = [_build_assertion_record(snapshot, item, "pending_review_items") for item in assertions.get("should_pending", [])]
    should_not_report = [_build_assertion_record(snapshot, item, None) for item in assertions.get("should_not_report", [])]

    mismatched_layers: list[dict[str, Any]] = []
    for record in should_pending:
        if record["actual_layers"] and record["expected_layer"] not in record["actual_layers"]:
            mismatched_layers.append(
                {
                    "assertion_id": record["assertion_id"],
                    "expected_layer": record["expected_layer"],
                    "actual_layers": record["actual_layers"],
                }
            )
    summary = {
        "missing_should_report": [
            record["assertion_id"]
            for record in should_report
            if not any(layer in {"formal_risks", "pending_review_items"} for layer in record["actual_layers"])
        ],
        "unexpected_reported": [record["assertion_id"] for record in should_not_report if "formal_risks" in record["actual_layers"]],
        "missing_should_pending": [record["assertion_id"] for record in should_pending if "pending_review_items" not in record["actual_layers"]],
        "unexpected_pending": [record["assertion_id"] for record in should_not_report if "pending_review_items" in record["actual_layers"]],
        "mismatched_layers": mismatched_layers,
        "formal_count": len(snapshot.get("final_risks", {}).get("formal_risks", [])),
        "pending_count": len(snapshot.get("final_risks", {}).get("pending_review_items", [])),
        "excluded_count": len(snapshot.get("final_risks", {}).get("excluded_risks", [])),
    }
    summary["passed"] = not any(
        summary[key]
        for key in (
            "missing_should_report",
            "unexpected_reported",
            "missing_should_pending",
            "unexpected_pending",
            "mismatched_layers",
        )
    )
    assertion_payload = {
        "should_report": should_report,
        "should_pending": should_pending,
        "should_not_report": should_not_report,
    }
    return assertion_payload, summary


def _titles_from_assertion_records(records: list[dict[str, Any]], predicate) -> list[str]:
    titles: list[str] = []
    for record in records:
        if predicate(record):
            title = str(record.get("assertion", {}).get("title", "")).strip()
            if title:
                titles.append(title)
    return titles


def _build_matrix_diff_summary(assertion_payload: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    del summary
    return {
        "missing_should_report_titles": _titles_from_assertion_records(
            assertion_payload.get("should_report", []),
            lambda item: not any(layer in {"formal_risks", "pending_review_items"} for layer in item.get("actual_layers", [])),
        ),
        "unexpected_reported_titles": _titles_from_assertion_records(
            assertion_payload.get("should_not_report", []),
            lambda item: "formal_risks" in item.get("actual_layers", []),
        ),
        "missing_should_pending_titles": _titles_from_assertion_records(
            assertion_payload.get("should_pending", []),
            lambda item: "pending_review_items" not in item.get("actual_layers", []),
        ),
        "unexpected_pending_titles": _titles_from_assertion_records(
            assertion_payload.get("should_not_report", []),
            lambda item: "pending_review_items" in item.get("actual_layers", []),
        ),
    }


def _resolve_output_dir(
    document_config: dict[str, Any],
    output_root: str | Path | None = None,
    *,
    config_path: str | None = None,
) -> Path:
    configured = _resolve_path(str(document_config["result_dir"]), config_path)
    if output_root is None:
        return configured
    return Path(output_root).resolve() / configured.name


def _build_replay_artifacts(document_config: dict[str, Any], suite: dict[str, Any]) -> tuple[V2ReviewArtifacts, dict[str, Any], dict[str, Any], dict[str, Any]]:
    config_path = suite.get("_config_path")
    source_file = _resolve_path(str(document_config["file_path"]), config_path)
    seed_result_dir = _resolve_path(str(document_config["seed_result_dir"]), config_path)
    topic_mode = str(document_config.get("topic_mode", "mature") or "mature")
    baseline, structure, topics = _load_seed_topics(seed_result_dir, source_file, topic_mode)
    text = extract_text(source_file)
    evidence = build_evidence_map(source_file.name, structure, topic_mode=topic_mode)
    comparison = compare_review_artifacts(source_file.name, baseline, topics)
    governance = govern_comparison_artifact(source_file.name, comparison)
    problems = build_problem_layer(source_file.name, governance)
    admission = admit_problem_result(source_file.name, comparison, problems, governance)
    snapshot = build_v2_final_snapshot(
        source_file.name,
        baseline,
        structure,
        topics,
        comparison=comparison,
        governance=governance,
        problems=problems,
        admission=admission,
    )
    artifacts = V2ReviewArtifacts(
        extracted_text=text,
        baseline=baseline,
        structure=structure,
        topics=topics,
        final_markdown=render_v2_markdown_from_snapshot(snapshot),
        final_snapshot=snapshot,
        evidence=evidence,
        comparison=comparison,
        governance=governance,
        problems=problems,
        admission=admission,
    )
    return artifacts, snapshot, comparison.to_dict(), admission.to_dict()


def run_real_replay_baseline(
    suite: dict[str, Any],
    *,
    document_id: str,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    document_config = next(item for item in suite["documents"] if item["document_id"] == document_id)
    output_dir = _resolve_output_dir(document_config, output_root, config_path=suite.get("_config_path"))
    artifacts, snapshot, _, _ = _build_replay_artifacts(document_config, suite)
    save_review_artifacts_v2(artifacts, output_dir)
    assertion_payload, summary = evaluate_replay_assertions(snapshot, document_config.get("baseline_assertions", {}))
    summary.update(
        {
            "document_id": document_id,
            "document_name": document_config.get("document_name", ""),
            "notes": list(document_config.get("notes", []) or []),
            "result_dir": str(output_dir),
        }
    )
    (output_dir / "replay_assertions.json").write_text(
        json.dumps(
            {
                "document_id": document_id,
                "document_name": document_config.get("document_name", ""),
                "baseline_assertions": assertion_payload,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "replay_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def run_real_replay_baseline_batch(
    suite: dict[str, Any],
    *,
    document_ids: list[str] | None = None,
    output_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    target_ids = document_ids or [item["document_id"] for item in suite["documents"]]
    return [
        run_real_replay_baseline(suite, document_id=document_id, output_root=output_root)
        for document_id in target_ids
    ]


def run_real_replay_matrix(
    suite: dict[str, Any],
    *,
    document_id: str,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    document_config = next(item for item in suite["documents"] if item["document_id"] == document_id)
    output_dir = _resolve_output_dir(document_config, output_root, config_path=suite.get("_config_path"))
    artifacts, snapshot, _, admission = _build_replay_artifacts(document_config, suite)
    save_review_artifacts_v2(artifacts, output_dir)
    assertion_payload, summary = evaluate_replay_assertions(snapshot, document_config.get("baseline_assertions", {}))
    input_summary = admission.get("input_summary", {}) if isinstance(admission, dict) else {}
    domain_context = input_summary.get("domain_context", {}) if isinstance(input_summary, dict) else {}
    domain_policy = input_summary.get("domain_policy", {}) if isinstance(input_summary, dict) else {}
    budget_policy = input_summary.get("budget_policy", {}) if isinstance(input_summary, dict) else {}
    summary.update(
        {
            "document_id": document_id,
            "document_name": document_config.get("document_name", ""),
            "document_domain": domain_context.get("document_domain", ""),
            "expected_document_domain": document_config.get("document_domain", ""),
            "domain_drift": str(domain_context.get("document_domain", "")).strip()
            != str(document_config.get("document_domain", "")).strip(),
            "domain_policy_id": domain_policy.get("policy_id", ""),
            "budget_policy_id": budget_policy.get("policy_id", ""),
            "excluded_internal_count": len(admission.get("excluded_risks", [])) if isinstance(admission, dict) else 0,
            "diff_summary": _build_matrix_diff_summary(assertion_payload, summary),
            "notes": list(document_config.get("notes", []) or []),
            "result_dir": str(output_dir),
        }
    )
    summary["passed"] = bool(summary["passed"]) and not summary["domain_drift"]
    (output_dir / "replay_assertions.json").write_text(
        json.dumps(
            {
                "document_id": document_id,
                "document_name": document_config.get("document_name", ""),
                "document_domain": document_config.get("document_domain", ""),
                "baseline_assertions": assertion_payload,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "replay_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def run_real_replay_matrix_batch(
    suite: dict[str, Any],
    *,
    document_ids: list[str] | None = None,
    output_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    target_ids = document_ids or [item["document_id"] for item in suite["documents"]]
    return [run_real_replay_matrix(suite, document_id=document_id, output_root=output_root) for document_id in target_ids]
