from __future__ import annotations

import json
import secrets
from datetime import datetime
from pathlib import Path
from typing import Callable

from flask import url_for

from app.config import LEGACY_WEB_RESULTS_DIR, WEB_RESULTS_DIR
from app.common.markdown_utils import parse_review_markdown


SEVERITY_ORDER = ["高风险", "中风险", "低风险", "需人工复核"]


def summarize_text(text: str, limit: int = 92) -> str:
    normalized = " ".join((text or "").split())
    if not normalized:
        return "未发现"
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def make_run_dir(results_dir: Path = WEB_RESULTS_DIR) -> tuple[str, Path]:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_id = f"{timestamp}-{secrets.token_hex(4)}"
    run_dir = results_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_id, run_dir


def iter_result_roots() -> list[Path]:
    roots = [WEB_RESULTS_DIR]
    if LEGACY_WEB_RESULTS_DIR != WEB_RESULTS_DIR:
        roots.append(LEGACY_WEB_RESULTS_DIR)
    return roots


def find_run_dir(run_id: str) -> Path | None:
    for root in iter_result_roots():
        candidate = root / run_id
        if candidate.exists():
            return candidate
    return None


def build_review_view(report) -> dict:
    summary_counts = {key: 0 for key in SEVERITY_ORDER}
    type_counts: dict[str, int] = {}
    grouped = {key: [] for key in SEVERITY_ORDER}

    for index, risk in enumerate(report.risk_points, start=1):
        severity = risk.severity if risk.severity in grouped else "需人工复核"
        summary_counts[severity] += 1
        review_type = risk.review_type.strip() or "未分类"
        type_counts[review_type] = type_counts.get(review_type, 0) + 1
        grouped[severity].append(
            {
                "index": index,
                "title": risk.title,
                "severity": severity,
                "review_type": review_type,
                "source_location": risk.source_location,
                "source_excerpt": risk.source_excerpt,
                "risk_judgment": risk.risk_judgment,
                "legal_basis": risk.legal_basis,
                "rectification": risk.rectification,
                "source_location_preview": summarize_text(risk.source_location, 96),
                "source_excerpt_preview": summarize_text(risk.source_excerpt, 110),
                "judgment_preview": summarize_text((risk.risk_judgment or ["需人工复核"])[0], 104),
                "legal_basis_count": len(risk.legal_basis or []),
                "rectification_count": len(risk.rectification or []),
            }
        )

    sections = [
        {"severity": severity, "count": len(grouped[severity]), "cards": grouped[severity]}
        for severity in SEVERITY_ORDER
        if grouped[severity]
    ]
    all_cards = [card for severity in SEVERITY_ORDER for card in grouped[severity]]
    type_items = sorted(type_counts.items(), key=lambda item: (-item[1], item[0]))
    return {
        "summary_counts": summary_counts,
        "type_items": type_items,
        "sections": sections,
        "all_cards": all_cards,
        "total": len(report.risk_points),
    }


def build_result_payload(run_id: str, original_filename: str, final_markdown: str, raw_markdown: str, render_markdown: Callable[[str], str]) -> dict:
    review_view = build_review_view(parse_review_markdown(final_markdown))
    return {
        "run_id": run_id,
        "original_filename": original_filename,
        "review_markdown": raw_markdown,
        "review_html": render_markdown(final_markdown),
        "review_final_markdown": final_markdown,
        "review_view": review_view,
        "download_review": url_for("download_file", run_id=run_id, kind="review"),
        "download_review_raw": url_for("download_file", run_id=run_id, kind="review_raw"),
        "download_request": url_for("download_file", run_id=run_id, kind="request"),
        "download_response": url_for("download_file", run_id=run_id, kind="response"),
        "download_extracted": url_for("download_file", run_id=run_id, kind="extracted"),
    }


def load_result_by_run_id(run_id: str, render_markdown: Callable[[str], str]) -> dict | None:
    run_dir = find_run_dir(run_id)
    if run_dir is None:
        return None
    meta_path = run_dir / "meta.json"
    review_path = run_dir / "review.md"
    raw_path = run_dir / "review_raw.md"
    if not meta_path.exists() or not review_path.exists():
        return None

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    final_markdown = review_path.read_text(encoding="utf-8")
    raw_markdown = raw_path.read_text(encoding="utf-8") if raw_path.exists() else final_markdown
    original_filename = meta.get("original_filename") or run_id
    result = build_result_payload(run_id, original_filename, final_markdown, raw_markdown, render_markdown)
    result["created_at"] = meta.get("created_at", "")
    return result


def list_recent_runs(render_history_url: Callable[[str], str], limit: int = 12) -> list[dict]:
    runs: list[dict] = []
    seen_run_ids: set[str] = set()
    for root in iter_result_roots():
        if root.exists():
            run_dirs = [path for path in root.iterdir() if path.is_dir()]
        else:
            run_dirs = []
        for run_dir in run_dirs:
            meta_path = run_dir / "meta.json"
            review_path = run_dir / "review.md"
            if not meta_path.exists() or not review_path.exists():
                continue
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                run_id = meta.get("run_id", run_dir.name)
                if run_id in seen_run_ids:
                    continue
                report = parse_review_markdown(review_path.read_text(encoding="utf-8"))
                review_view = build_review_view(report)
            except Exception:
                continue
            seen_run_ids.add(run_id)
            runs.append(
                {
                    "run_id": run_id,
                    "created_at": meta.get("created_at", ""),
                    "original_filename": meta.get("original_filename", run_dir.name),
                    "total": review_view["total"],
                    "high": review_view["summary_counts"]["高风险"],
                    "medium": review_view["summary_counts"]["中风险"],
                    "low": review_view["summary_counts"]["低风险"],
                    "manual": review_view["summary_counts"]["需人工复核"],
                    "view_url": render_history_url(run_id),
                }
            )
    runs.sort(key=lambda item: (item.get("created_at", ""), item.get("run_id", "")), reverse=True)
    return runs[:limit]
