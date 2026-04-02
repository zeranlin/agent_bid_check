from __future__ import annotations

import html
import json
import re
import secrets
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, render_template, request, send_file, url_for
from markupsafe import Markup
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.common.markdown_utils import parse_review_markdown
from app.config import (
    LEGACY_WEB_RESULTS_DIR,
    WEB_V2_CONFIG_PATH,
    WEB_V2_JOBS_DIR,
    WEB_V2_RESULTS_DIR,
    WEB_V2_UPLOADS_DIR,
    ReviewSettings,
    ensure_data_dirs,
    load_web_settings,
    save_web_settings,
)
from app.pipelines.v2.service import review_document_v2, save_review_artifacts_v2


SEVERITY_ORDER = ["高风险", "中风险", "低风险", "需人工复核"]
TOPIC_LABELS = {
    "qualification": "资格条件",
    "performance_staff": "业绩与人员",
    "scoring": "评分办法",
    "samples_demo": "样品演示答辩",
    "technical_bias": "技术倾向性",
    "technical_standard": "技术标准与检测",
    "contract_payment": "付款与履约",
    "acceptance": "验收条款",
    "procedure": "程序条款",
    "policy": "政策条款",
    "technical": "技术细节",
    "contract": "合同履约",
    "baseline": "全文直审",
}
TOPIC_MODE_LABELS = {
    "slim": "精简专题",
    "default": "兼容专题",
    "enhanced": "增强专题",
    "mature": "成熟专题",
}
STAGE_TO_MESSAGE = {
    "file_reading": "系统正在阅读招标文件并提取正文。",
    "baseline_review": "正在执行第一层全文直审，优先识别通用合规风险。",
    "structure_analysis": "正在执行第二层结构增强，识别章节与模块归属。",
    "topic_review": "正在执行第三层专题深审，核查标准、评分与商务细节。",
    "report_structuring": "正在合并三层结果并生成统一审查报告。",
    "completed": "V2 审查完成，正在展示结果。",
}

MODULE_DIR = Path(__file__).resolve().parent
JOB_LOCK = threading.Lock()
V2_JOBS: dict[str, dict] = {}
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
STRONG_RE = re.compile(r"\*\*(.+?)\*\*")
EM_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
LINK_RE = re.compile(r"\[(.+?)\]\((https?://[^\s)]+)\)")
INLINE_BULLET_RE = re.compile(r'(?<=[。；;"”])\s*-\s*(?=["“]?\d+[.、])')


def ensure_runtime_dirs() -> None:
    ensure_data_dirs()
    if not WEB_V2_CONFIG_PATH.exists():
        save_web_settings(ReviewSettings.from_env(), WEB_V2_CONFIG_PATH)


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in {".docx", ".txt", ".md"}


def render_inline_md(text: str) -> str:
    escaped = html.escape(text)
    escaped = INLINE_CODE_RE.sub(r"<code>\1</code>", escaped)
    escaped = STRONG_RE.sub(r"<strong>\1</strong>", escaped)
    escaped = EM_RE.sub(r"<em>\1</em>", escaped)
    escaped = LINK_RE.sub(r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', escaped)
    return escaped


def is_table_separator(line: str) -> bool:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    if not cells:
        return False
    return all(cell and set(cell) <= {"-", ":"} for cell in cells)


def render_markdown(md: str) -> str:
    lines = md.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    in_ul = False
    in_ol = False
    in_blockquote = False
    in_code = False
    in_table = False
    table_rows: list[list[str]] = []
    paragraph: list[str] = []

    def close_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            text = " ".join(part.strip() for part in paragraph if part.strip())
            if text:
                out.append(f"<p>{render_inline_md(text)}</p>")
        paragraph = []

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    def close_blockquote() -> None:
        nonlocal in_blockquote
        if in_blockquote:
            close_paragraph()
            out.append("</blockquote>")
            in_blockquote = False

    def close_table() -> None:
        nonlocal in_table, table_rows
        if not in_table or not table_rows:
            in_table = False
            table_rows = []
            return
        header = table_rows[0]
        body = table_rows[1:]
        out.append("<table>")
        out.append("<thead><tr>" + "".join(f"<th>{render_inline_md(c)}</th>" for c in header) + "</tr></thead>")
        if body:
            out.append("<tbody>")
            for row in body:
                out.append("<tr>" + "".join(f"<td>{render_inline_md(c)}</td>" for c in row) + "</tr>")
            out.append("</tbody>")
        out.append("</table>")
        in_table = False
        table_rows = []

    for line in lines:
        stripped = line.strip()

        if in_code:
            if stripped.startswith("```"):
                out.append("</code></pre>")
                in_code = False
            else:
                out.append(html.escape(line))
            continue

        if stripped.startswith("```"):
            close_paragraph()
            close_lists()
            close_blockquote()
            close_table()
            out.append("<pre><code>")
            in_code = True
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            close_paragraph()
            close_lists()
            close_blockquote()
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if in_table:
                if is_table_separator(stripped):
                    continue
                table_rows.append(cells)
            else:
                in_table = True
                table_rows = [cells]
            continue
        else:
            close_table()

        if not stripped:
            close_paragraph()
            close_lists()
            close_blockquote()
            continue

        if stripped == "---":
            close_paragraph()
            close_lists()
            close_blockquote()
            out.append("<hr>")
            continue

        if stripped.startswith(">"):
            close_paragraph()
            close_lists()
            if not in_blockquote:
                out.append("<blockquote>")
                in_blockquote = True
            paragraph.append(stripped[1:].strip())
            continue
        else:
            close_blockquote()

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading_match:
            close_paragraph()
            close_lists()
            level = len(heading_match.group(1))
            out.append(f"<h{level}>{render_inline_md(heading_match.group(2))}</h{level}>")
            continue

        ul_match = re.match(r"^[-*]\s+(.*)$", stripped)
        if ul_match:
            close_paragraph()
            if in_ol:
                out.append("</ol>")
                in_ol = False
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{render_inline_md(ul_match.group(1))}</li>")
            continue

        ol_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if ol_match:
            close_paragraph()
            if in_ul:
                out.append("</ul>")
                in_ul = False
            if not in_ol:
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{render_inline_md(ol_match.group(1))}</li>")
            continue

        paragraph.append(stripped)

    close_paragraph()
    close_lists()
    close_blockquote()
    close_table()
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out)


def preprocess_field_markdown(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return normalized
    return INLINE_BULLET_RE.sub("\n- ", normalized)


def job_status_path(job_id: str) -> Path:
    return WEB_V2_JOBS_DIR / f"{job_id}.json"


def persist_job(job: dict) -> None:
    job_status_path(str(job["job_id"])).write_text(
        json.dumps(job, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_job_from_disk(job_id: str) -> dict | None:
    path = job_status_path(job_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def create_job(job_id: str, filename: str) -> None:
    with JOB_LOCK:
        V2_JOBS[job_id] = {
            "job_id": job_id,
            "filename": filename,
            "status": "running",
            "stage": "file_reading",
            "message": STAGE_TO_MESSAGE["file_reading"],
            "started_at": __import__("time").time(),
            "partial_text": "",
            "run_id": None,
            "redirect_url": None,
            "error": None,
        }
        persist_job(V2_JOBS[job_id])


def update_job(job_id: str, **updates: object) -> None:
    with JOB_LOCK:
        job = V2_JOBS.get(job_id) or load_job_from_disk(job_id)
        if not job:
            return
        V2_JOBS[job_id] = job
        job.update(updates)
        persist_job(job)


def get_job(job_id: str) -> dict | None:
    with JOB_LOCK:
        job = V2_JOBS.get(job_id)
        if job:
            return dict(job)
    disk = load_job_from_disk(job_id)
    if disk:
        with JOB_LOCK:
            V2_JOBS[job_id] = disk
        return dict(disk)
    return None


def append_job_text(job_id: str, chunk: str, keep_lines: int = 30) -> None:
    if not chunk:
        return
    with JOB_LOCK:
        job = V2_JOBS.get(job_id) or load_job_from_disk(job_id)
        if not job:
            return
        V2_JOBS[job_id] = job
        current = str(job.get("partial_text", ""))
        combined = current + chunk
        lines = combined.splitlines()
        job["partial_text"] = "\n".join(lines[-keep_lines:])
        persist_job(job)


def make_run_dir() -> tuple[str, Path]:
    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(4)}"
    run_dir = WEB_V2_RESULTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_id, run_dir


def find_run_dir(run_id: str) -> Path | None:
    roots = [WEB_V2_RESULTS_DIR]
    if LEGACY_WEB_RESULTS_DIR != WEB_V2_RESULTS_DIR:
        roots.append(LEGACY_WEB_RESULTS_DIR)
    for root in roots:
        candidate = root / run_id
        if candidate.exists():
            return candidate
    return None


def load_config() -> dict[str, str]:
    settings = load_web_settings(WEB_V2_CONFIG_PATH)
    if settings.system_prompt != ReviewSettings.from_env().system_prompt or settings.user_prompt != ReviewSettings.from_env().user_prompt:
        settings.system_prompt = ReviewSettings.from_env().system_prompt
        settings.user_prompt = ReviewSettings.from_env().user_prompt
        save_web_settings(settings, WEB_V2_CONFIG_PATH)
    return settings.to_form_dict()


def _normalize_compare_key(title: str, review_type: str) -> str:
    return re.sub(r"\s+", "", f"{title}|{review_type}").lower()


def build_review_view(report, comparison: dict | None = None) -> dict:
    summary_counts = {key: 0 for key in SEVERITY_ORDER}
    type_counts: dict[str, int] = {}
    grouped = {key: [] for key in SEVERITY_ORDER}
    cluster_map: dict[str, dict] = {}
    if isinstance(comparison, dict):
        for cluster in comparison.get("clusters", []) or []:
            if not isinstance(cluster, dict):
                continue
            key = _normalize_compare_key(str(cluster.get("title", "")), str(cluster.get("review_type", "")))
            cluster_map[key] = cluster
    all_cards: list[dict] = []
    for index, risk in enumerate(report.risk_points, start=1):
        severity = risk.severity if risk.severity in grouped else "需人工复核"
        summary_counts[severity] += 1
        review_type = risk.review_type.strip() or "未分类"
        type_counts[review_type] = type_counts.get(review_type, 0) + 1
        cluster = cluster_map.get(_normalize_compare_key(risk.title, review_type), {})
        source_tags = [str(item) for item in cluster.get("source_rules", []) if str(item).strip()]
        source_topics = [str(item) for item in cluster.get("topics", []) if str(item).strip() and str(item).strip() != "baseline"]
        is_standard_compare = "compare_rule" in source_tags
        manual_reasons = []
        if cluster.get("need_manual_review"):
            manual_reasons.extend([str(item) for item in cluster.get("conflict_notes", []) if str(item).strip()])
        if severity == "需人工复核" and not manual_reasons:
            manual_reasons.append("当前风险点仍建议人工复核。")
        card = {
            "index": index,
            "title": risk.title,
            "severity": severity,
            "severity_class": severity.replace("风险", "") if severity != "需人工复核" else "manual",
            "review_type": review_type,
            "source_location": risk.source_location,
            "source_excerpt": risk.source_excerpt,
            "risk_judgment": risk.risk_judgment,
            "legal_basis": risk.legal_basis,
            "rectification": risk.rectification,
            "source_tags": source_tags,
            "source_topics": [TOPIC_LABELS.get(item, item) for item in source_topics],
            "conflict_notes": [str(item) for item in cluster.get("conflict_notes", []) if str(item).strip()],
            "manual_reasons": manual_reasons,
            "is_standard_compare": is_standard_compare,
            "judgment_preview": (risk.risk_judgment[0] if risk.risk_judgment else "需人工复核"),
            "source_location_preview": (risk.source_location or "未发现").splitlines()[0][:48],
        }
        grouped[severity].append(card)
        all_cards.append(card)
    sections = [
        {"severity": severity, "count": len(grouped[severity]), "cards": grouped[severity]}
        for severity in SEVERITY_ORDER
        if grouped[severity]
    ]
    severity_rank = {severity: index for index, severity in enumerate(SEVERITY_ORDER)}
    all_cards.sort(
        key=lambda item: (
            severity_rank.get(item["severity"], len(SEVERITY_ORDER)),
            not bool(item["is_standard_compare"]),
            item["index"],
        )
    )
    return {
        "summary_counts": summary_counts,
        "type_items": sorted(type_counts.items(), key=lambda item: (-item[1], item[0])),
        "sections": sections,
        "total": len(report.risk_points),
        "all_cards": all_cards,
    }


def build_review_view_from_final_output(final_output: dict, comparison: dict | None = None) -> dict:
    if not isinstance(final_output, dict):
        return build_review_view(parse_review_markdown(""), comparison)

    summary_counts = {key: 0 for key in SEVERITY_ORDER}
    type_counts: dict[str, int] = {}
    grouped = {key: [] for key in SEVERITY_ORDER}
    cluster_map: dict[str, dict] = {}
    if isinstance(comparison, dict):
        for cluster in comparison.get("clusters", []) or []:
            if not isinstance(cluster, dict):
                continue
            key = _normalize_compare_key(str(cluster.get("title", "")), str(cluster.get("review_type", "")))
            cluster_map[key] = cluster

    all_cards: list[dict] = []
    for index, risk in enumerate(final_output.get("formal_risks", []) or [], start=1):
        if not isinstance(risk, dict):
            continue
        severity = str(risk.get("severity", "")).strip()
        severity = severity if severity in grouped else "需人工复核"
        summary_counts[severity] += 1
        review_type = str(risk.get("review_type", "")).strip() or "未分类"
        type_counts[review_type] = type_counts.get(review_type, 0) + 1
        title = str(risk.get("title", "")).strip() or f"风险点{index}"
        cluster = cluster_map.get(_normalize_compare_key(title, review_type), {})
        source_tags = [str(item) for item in cluster.get("source_rules", []) if str(item).strip()]
        source_topics = [str(item) for item in cluster.get("topics", []) if str(item).strip() and str(item).strip() != "baseline"]
        is_standard_compare = "compare_rule" in source_tags
        conflict_notes = [str(item) for item in cluster.get("conflict_notes", []) if str(item).strip()]
        manual_reasons: list[str] = []
        if cluster.get("need_manual_review"):
            manual_reasons.extend(conflict_notes)
        if severity == "需人工复核" and not manual_reasons:
            manual_reasons.append("当前风险点仍建议人工复核。")
        risk_judgment = [str(item) for item in risk.get("risk_judgment", []) if str(item).strip()]
        legal_basis = [str(item) for item in risk.get("legal_basis", []) if str(item).strip()]
        rectification = [str(item) for item in risk.get("rectification", []) if str(item).strip()]
        card = {
            "index": index,
            "title": title,
            "severity": severity,
            "severity_class": severity.replace("风险", "") if severity != "需人工复核" else "manual",
            "review_type": review_type,
            "source_location": str(risk.get("source_location", "")).strip() or "未发现",
            "source_excerpt": str(risk.get("source_excerpt", "")).strip() or "未发现",
            "risk_judgment": risk_judgment,
            "legal_basis": legal_basis,
            "rectification": rectification,
            "source_tags": source_tags,
            "source_topics": [TOPIC_LABELS.get(item, item) for item in source_topics],
            "conflict_notes": conflict_notes,
            "manual_reasons": manual_reasons,
            "is_standard_compare": is_standard_compare,
            "judgment_preview": (risk_judgment[0] if risk_judgment else "需人工复核"),
            "source_location_preview": (str(risk.get("source_location", "")).strip() or "未发现").splitlines()[0][:48],
        }
        grouped[severity].append(card)
        all_cards.append(card)

    sections = [
        {"severity": severity, "count": len(grouped[severity]), "cards": grouped[severity]}
        for severity in SEVERITY_ORDER
        if grouped[severity]
    ]
    severity_rank = {severity: index for index, severity in enumerate(SEVERITY_ORDER)}
    all_cards.sort(
        key=lambda item: (
            severity_rank.get(item["severity"], len(SEVERITY_ORDER)),
            not bool(item["is_standard_compare"]),
            item["index"],
        )
    )
    return {
        "summary_counts": summary_counts,
        "type_items": sorted(type_counts.items(), key=lambda item: (-item[1], item[0])),
        "sections": sections,
        "total": len(all_cards),
        "all_cards": all_cards,
    }


def build_comparison_view(comparison: dict) -> dict:
    if not isinstance(comparison, dict) or not any(
        key in comparison
        for key in (
            "clusters",
            "conflicts",
            "coverage_gaps",
            "baseline_only_risks",
            "topic_only_risks",
            "manual_review_items",
            "comparison_summary",
            "coverage_summary",
        )
    ):
        return {
            "available": False,
            "summary": {},
            "conflicts": [],
            "coverage_gaps": [],
            "baseline_only": [],
            "topic_only": [],
            "manual_review_items": [],
        }
    return {
        "available": True,
        "summary": {
            "cluster_count": int(comparison.get("coverage_summary", {}).get("cluster_count", 0) or 0),
            "conflict_count": len(comparison.get("conflicts", []) or []),
            "duplicate_reduction": int(comparison.get("comparison_summary", {}).get("duplicate_reduction", 0) or 0),
            "manual_review_count": int(comparison.get("comparison_summary", {}).get("manual_review_count", 0) or 0),
        },
        "conflicts": [
            {
                **item,
                "topic_labels": [TOPIC_LABELS.get(topic, topic) for topic in (item.get("topics", []) or [])],
            }
            for item in (comparison.get("conflicts", []) or [])
            if isinstance(item, dict)
        ],
        "coverage_gaps": comparison.get("coverage_gaps", []) or [],
        "baseline_only": comparison.get("baseline_only_risks", []) or [],
        "topic_only": [
            {
                **item,
                "topic_label": TOPIC_LABELS.get(str(item.get("topic", "")), str(item.get("topic", ""))),
            }
            for item in (comparison.get("topic_only_risks", []) or [])
            if isinstance(item, dict)
        ],
        "manual_review_items": comparison.get("manual_review_items", []) or [],
    }


def build_topic_view(topics: list[dict], overview: dict | None = None) -> list[dict]:
    overview = overview if isinstance(overview, dict) else {}
    overview_topics: dict[str, dict] = {}
    for item in overview.get("topics", []) or []:
        if isinstance(item, dict) and str(item.get("topic", "")).strip():
            overview_topics[str(item.get("topic", "")).strip()] = item

    normalized: list[dict] = []
    for topic in topics:
        if not isinstance(topic, dict):
            continue
        topic_key = str(topic.get("topic", "")).strip()
        if not topic_key:
            continue
        metadata = topic.get("metadata", {}) if isinstance(topic.get("metadata", {}), dict) else {}
        overview_item = overview_topics.get(topic_key, {})
        missing_evidence = [
            str(item).strip()
            for item in (metadata.get("missing_evidence", []) or topic.get("missing_evidence", []) or [])
            if str(item).strip() and str(item).strip() != "未发现"
        ]
        selected_sections = metadata.get("selected_sections", []) if isinstance(metadata.get("selected_sections", []), list) else []
        topic_coverage = metadata.get("topic_coverage", {}) if isinstance(metadata.get("topic_coverage", {}), dict) else {}
        covered_modules = [str(item).strip() for item in (topic_coverage.get("covered_modules", []) or []) if str(item).strip()]
        missing_modules = [str(item).strip() for item in (topic_coverage.get("missing_modules", []) or []) if str(item).strip()]
        normalized.append(
            {
                "topic": topic_key,
                "topic_label": TOPIC_LABELS.get(topic_key, topic_key),
                "summary": str(topic.get("summary", "")).strip() or str(overview_item.get("summary", "")).strip() or "未发现",
                "coverage_note": str(topic.get("coverage_note", "")).strip()
                or str(overview_item.get("coverage_note", "")).strip()
                or "未发现",
                "risk_points": topic.get("risk_points", []) if isinstance(topic.get("risk_points", []), list) else [],
                "risk_count": len(topic.get("risk_points", []) if isinstance(topic.get("risk_points", []), list) else [])
                or int(overview_item.get("risk_count", 0) or 0),
                "need_manual_review": bool(topic.get("need_manual_review", False) or overview_item.get("need_manual_review", False)),
                "missing_evidence": missing_evidence,
                "selected_section_count": len(selected_sections),
                "covered_modules": covered_modules,
                "missing_modules": missing_modules,
            }
        )

    if normalized:
        return normalized

    for topic_key, item in overview_topics.items():
        normalized.append(
            {
                "topic": topic_key,
                "topic_label": TOPIC_LABELS.get(topic_key, topic_key),
                "summary": str(item.get("summary", "")).strip() or "未发现",
                "coverage_note": str(item.get("coverage_note", "")).strip() or "未发现",
                "risk_points": [],
                "risk_count": int(item.get("risk_count", 0) or 0),
                "need_manual_review": bool(item.get("need_manual_review", False)),
                "missing_evidence": [],
                "selected_section_count": 0,
                "covered_modules": [],
                "missing_modules": [],
            }
        )
    return normalized


def load_result_by_run_id(run_id: str) -> dict | None:
    run_dir = find_run_dir(run_id)
    if run_dir is None:
        return None
    meta_path = run_dir / "meta.json"
    review_path = run_dir / "review.md"
    overview_path = run_dir / "v2_overview.json"
    comparison_path = run_dir / "comparison.json"
    final_output_path = run_dir / "final_output.json"
    topic_dir = run_dir / "topic_reviews"
    if not review_path.exists():
        return None
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    final_markdown = review_path.read_text(encoding="utf-8")
    overview = {}
    if overview_path.exists():
        try:
            overview = json.loads(overview_path.read_text(encoding="utf-8"))
        except Exception:
            overview = {}
    comparison = {}
    if comparison_path.exists():
        try:
            comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
        except Exception:
            comparison = {}
    final_output = {}
    if final_output_path.exists():
        try:
            final_output = json.loads(final_output_path.read_text(encoding="utf-8"))
        except Exception:
            final_output = {}
    topics: list[dict] = []
    if topic_dir.exists():
        for path in sorted(topic_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    payload["topic_label"] = TOPIC_LABELS.get(str(payload.get("topic", "")), str(payload.get("topic", "")))
                topics.append(payload)
            except Exception:
                continue
    topic_view = build_topic_view(topics, overview)
    report = parse_review_markdown(final_markdown)
    review_view = build_review_view_from_final_output(final_output, comparison) if final_output else build_review_view(report, comparison)
    return {
        "run_id": run_id,
        "created_at": meta.get("created_at", ""),
        "original_filename": meta.get("original_filename", run_id),
        "review_final_markdown": final_markdown,
        "review_html": Markup(render_markdown(final_markdown)),
        "review_view": review_view,
        "overview": overview,
        "comparison": comparison,
        "final_output": final_output,
        "comparison_view": build_comparison_view(comparison),
        "topics": topics,
        "topic_view": topic_view,
        "topic_mode": str(meta.get("topic_mode", "mature")),
        "topic_mode_label": TOPIC_MODE_LABELS.get(
            str(meta.get("topic_mode", "mature")),
            str(meta.get("topic_mode", "mature")),
        ),
        "downloads": {
            "review": url_for("download_plus_file", run_id=run_id, kind="review"),
            "extracted": url_for("download_plus_file", run_id=run_id, kind="extracted"),
            "baseline": url_for("download_plus_file", run_id=run_id, kind="baseline"),
            "document_map": url_for("download_plus_file", run_id=run_id, kind="document_map"),
            "evidence_map": url_for("download_plus_file", run_id=run_id, kind="evidence_map"),
            "comparison": url_for("download_plus_file", run_id=run_id, kind="comparison"),
            "overview": url_for("download_plus_file", run_id=run_id, kind="overview"),
        },
    }


def list_recent_runs(limit: int = 12) -> list[dict]:
    ensure_runtime_dirs()
    runs: list[dict] = []
    roots = [WEB_V2_RESULTS_DIR]
    if LEGACY_WEB_RESULTS_DIR != WEB_V2_RESULTS_DIR:
        roots.append(LEGACY_WEB_RESULTS_DIR)
    seen_run_ids: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for run_dir in root.iterdir():
            if not run_dir.is_dir():
                continue
            result = load_result_by_run_id(run_dir.name)
            if not result or result["run_id"] in seen_run_ids:
                continue
            seen_run_ids.add(result["run_id"])
            counts = result["review_view"]["summary_counts"]
            runs.append(
                {
                    "run_id": result["run_id"],
                    "created_at": result["created_at"],
                    "original_filename": result["original_filename"],
                    "total": result["review_view"]["total"],
                    "high": counts["高风险"],
                    "medium": counts["中风险"],
                    "low": counts["低风险"],
                    "manual": counts["需人工复核"],
                    "topic_mode": result.get("topic_mode", "mature"),
                    "topic_mode_label": result.get("topic_mode_label", TOPIC_MODE_LABELS["mature"]),
                    "view_url": url_for("review_plus_history", run_id=result["run_id"]),
                }
            )
    runs.sort(key=lambda item: (item.get("created_at", ""), item.get("run_id", "")), reverse=True)
    return runs[:limit]


def _save_upload(upload: FileStorage) -> Path:
    filename = secure_filename(upload.filename or "upload.docx") or "upload.docx"
    upload_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
    upload_path = WEB_V2_UPLOADS_DIR / f"{upload_id}-{filename}"
    upload.save(upload_path)
    return upload_path


def run_review_job(
    job_id: str,
    upload_path: Path,
    original_filename: str,
    form: dict[str, str],
    topic_mode: str = "mature",
) -> None:
    try:
        settings = ReviewSettings.from_dict(form)

        def on_progress(stage: str, message: str) -> None:
            update_job(job_id, stage=stage, message=message)

        def on_stream_text(chunk: str) -> None:
            append_job_text(job_id, chunk)

        artifacts = review_document_v2(
            input_path=upload_path,
            settings=settings,
            progress_callback=on_progress,
            stream_callback=on_stream_text,
            topic_mode=topic_mode,
        )

        run_id, run_dir = make_run_dir()
        save_review_artifacts_v2(artifacts, run_dir)
        meta = {
            "run_id": run_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "original_filename": original_filename,
            "saved_filename": upload_path.name,
            "base_url": settings.base_url,
            "model": settings.model,
            "config_path": str(WEB_V2_CONFIG_PATH),
            "pipeline": "v2",
            "topic_mode": topic_mode,
        }
        (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        update_job(
            job_id,
            status="completed",
            stage="completed",
            message=STAGE_TO_MESSAGE["completed"],
            run_id=run_id,
            redirect_url=f"/review-plus/history/{run_id}",
        )
    except Exception as exc:
        update_job(job_id, status="failed", error=str(exc), message=str(exc))


def create_app() -> Flask:
    ensure_runtime_dirs()
    app = Flask(
        __name__,
        template_folder=str(MODULE_DIR / "templates"),
        static_folder=str(MODULE_DIR / "static"),
    )
    app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

    @app.template_filter("inline_md")
    def inline_md_filter(text: str) -> Markup:
        return Markup(render_inline_md(text or ""))

    @app.template_filter("field_md")
    def field_md_filter(text: str) -> Markup:
        return Markup(render_markdown(preprocess_field_markdown(text or "")))

    @app.route("/review-plus", methods=["GET"])
    def review_plus_page() -> str:
        return render_template(
            "review_v2_simple.html",
            result=None,
            history_runs=list_recent_runs(),
            error=None,
            active_page="review_plus",
            current_run_id=None,
        )

    @app.route("/review-plus/history/<run_id>", methods=["GET"])
    def review_plus_history(run_id: str) -> str:
        result = load_result_by_run_id(run_id)
        return render_template(
            "review_v2_simple.html",
            result=result,
            history_runs=list_recent_runs(),
            error=None if result else "未找到对应的 V2 审查记录。",
            active_page="review_plus",
            current_run_id=run_id,
        )

    @app.route("/review-max", methods=["GET"])
    def review_max_page() -> str:
        return render_template(
            "review_v2.html",
            result=None,
            history_runs=list_recent_runs(),
            error=None,
            active_page="review_max",
            current_run_id=None,
        )

    @app.route("/review-max/history/<run_id>", methods=["GET"])
    def review_max_history(run_id: str) -> str:
        result = load_result_by_run_id(run_id)
        return render_template(
            "review_v2.html",
            result=result,
            history_runs=list_recent_runs(),
            error=None if result else "未找到对应的 V2 审查记录。",
            active_page="review_max",
            current_run_id=run_id,
        )

    @app.route("/review-plus/start", methods=["POST"])
    def review_plus_start() -> Response:
        upload = request.files.get("tender_file")  # type: ignore[name-defined]
        if not upload or not upload.filename:
            return jsonify({"ok": False, "error": "请选择招标文件。"}), 400
        if not allowed_file(upload.filename):
            return jsonify({"ok": False, "error": "仅支持 .docx / .txt / .md 文件。"}), 400
        topic_mode = str(request.form.get("topic_mode", "mature") or "mature").strip().lower()
        if topic_mode not in TOPIC_MODE_LABELS:
            topic_mode = "mature"
        upload_path = _save_upload(upload)
        job_id = f"job-v2-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(4)}"
        create_job(job_id, upload.filename)
        worker = threading.Thread(
            target=run_review_job,
            args=(job_id, upload_path, upload.filename, load_config(), topic_mode),
            daemon=True,
        )
        worker.start()
        return jsonify(
            {
                "ok": True,
                "job_id": job_id,
                "status_url": url_for("review_plus_status", job_id=job_id),
                "started_at": get_job(job_id)["started_at"],
                "stage": "file_reading",
                "message": STAGE_TO_MESSAGE["file_reading"],
                "topic_mode": topic_mode,
                "topic_mode_label": TOPIC_MODE_LABELS.get(topic_mode, topic_mode),
            }
        )

    @app.route("/review-plus/status/<job_id>", methods=["GET"])
    def review_plus_status(job_id: str) -> Response:
        job = get_job(job_id)
        if not job:
            return jsonify({"ok": False, "error": "未找到对应的 V2 审查任务。"}), 404
        return jsonify({"ok": True, **job})

    @app.route("/review-plus/download/<run_id>/<kind>", methods=["GET"])
    def download_plus_file(run_id: str, kind: str) -> Response:
        run_dir = find_run_dir(run_id)
        mapping = {
            "review": ("review.md", "text/markdown; charset=utf-8"),
            "extracted": ("extracted_text.md", "text/plain; charset=utf-8"),
            "baseline": ("baseline_review.md", "text/markdown; charset=utf-8"),
            "document_map": ("document_map.json", "application/json"),
            "evidence_map": ("evidence_map.json", "application/json"),
            "comparison": ("comparison.json", "application/json"),
            "overview": ("v2_overview.json", "application/json"),
        }
        if run_dir is None or kind not in mapping:
            return redirect(url_for("review_plus_page"))
        filename, mimetype = mapping[kind]
        target = run_dir / filename
        if not target.exists():
            return redirect(url_for("review_plus_page"))
        return send_file(target, mimetype=mimetype, as_attachment=True, download_name=f"{run_id}-{filename}")

    @app.route("/review-v2", methods=["GET"])
    def review_v2_page_legacy() -> Response:
        return redirect(url_for("review_plus_page"), code=302)

    @app.route("/review-v2/history/<run_id>", methods=["GET"])
    def review_v2_history_legacy(run_id: str) -> Response:
        return redirect(url_for("review_plus_history", run_id=run_id), code=302)

    @app.route("/review-v2/full", methods=["GET"])
    def review_v2_full_page_legacy() -> Response:
        return redirect(url_for("review_max_page"), code=302)

    @app.route("/review-v2/full/history/<run_id>", methods=["GET"])
    def review_v2_full_history_legacy(run_id: str) -> Response:
        return redirect(url_for("review_max_history", run_id=run_id), code=302)

    @app.route("/review-v2/start", methods=["POST"])
    def review_v2_start_legacy() -> Response:
        return review_plus_start()

    @app.route("/review-v2/status/<job_id>", methods=["GET"])
    def review_v2_status_legacy(job_id: str) -> Response:
        return review_plus_status(job_id)

    @app.route("/review-v2/download/<run_id>/<kind>", methods=["GET"])
    def download_v2_file_legacy(run_id: str, kind: str) -> Response:
        return download_plus_file(run_id, kind)

    return app
app = create_app()
