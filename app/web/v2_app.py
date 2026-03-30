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
    candidate = WEB_V2_RESULTS_DIR / run_id
    return candidate if candidate.exists() else None


def load_config() -> dict[str, str]:
    settings = load_web_settings(WEB_V2_CONFIG_PATH)
    if settings.system_prompt != ReviewSettings.from_env().system_prompt or settings.user_prompt != ReviewSettings.from_env().user_prompt:
        settings.system_prompt = ReviewSettings.from_env().system_prompt
        settings.user_prompt = ReviewSettings.from_env().user_prompt
        save_web_settings(settings, WEB_V2_CONFIG_PATH)
    return settings.to_form_dict()


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
            }
        )
    sections = [
        {"severity": severity, "count": len(grouped[severity]), "cards": grouped[severity]}
        for severity in SEVERITY_ORDER
        if grouped[severity]
    ]
    return {
        "summary_counts": summary_counts,
        "type_items": sorted(type_counts.items(), key=lambda item: (-item[1], item[0])),
        "sections": sections,
        "total": len(report.risk_points),
    }


def load_result_by_run_id(run_id: str) -> dict | None:
    run_dir = find_run_dir(run_id)
    if run_dir is None:
        return None
    meta_path = run_dir / "meta.json"
    review_path = run_dir / "review.md"
    overview_path = run_dir / "v2_overview.json"
    topic_dir = run_dir / "topic_reviews"
    if not meta_path.exists() or not review_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    final_markdown = review_path.read_text(encoding="utf-8")
    overview = {}
    if overview_path.exists():
        try:
            overview = json.loads(overview_path.read_text(encoding="utf-8"))
        except Exception:
            overview = {}
    topics: list[dict] = []
    if topic_dir.exists():
        for path in sorted(topic_dir.glob("*.json")):
            try:
                topics.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
    report = parse_review_markdown(final_markdown)
    return {
        "run_id": run_id,
        "created_at": meta.get("created_at", ""),
        "original_filename": meta.get("original_filename", run_id),
        "review_final_markdown": final_markdown,
        "review_html": Markup(render_markdown(final_markdown)),
        "review_view": build_review_view(report),
        "overview": overview,
        "topics": topics,
        "downloads": {
            "review": url_for("download_v2_file", run_id=run_id, kind="review"),
            "extracted": url_for("download_v2_file", run_id=run_id, kind="extracted"),
            "baseline": url_for("download_v2_file", run_id=run_id, kind="baseline"),
            "document_map": url_for("download_v2_file", run_id=run_id, kind="document_map"),
            "overview": url_for("download_v2_file", run_id=run_id, kind="overview"),
        },
    }


def list_recent_runs(limit: int = 12) -> list[dict]:
    ensure_runtime_dirs()
    runs: list[dict] = []
    for run_dir in WEB_V2_RESULTS_DIR.iterdir():
        if not run_dir.is_dir():
            continue
        result = load_result_by_run_id(run_dir.name)
        if not result:
            continue
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
                "view_url": url_for("review_v2_history", run_id=result["run_id"]),
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


def run_review_job(job_id: str, upload_path: Path, original_filename: str, form: dict[str, str]) -> None:
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
        }
        (run_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        update_job(
            job_id,
            status="completed",
            stage="completed",
            message=STAGE_TO_MESSAGE["completed"],
            run_id=run_id,
            redirect_url=f"/review-v2/history/{run_id}",
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

    @app.route("/review-v2", methods=["GET"])
    def review_v2_page() -> str:
        return render_template(
            "review_v2.html",
            result=None,
            history_runs=list_recent_runs(),
            error=None,
            active_page="review_v2",
            current_run_id=None,
        )

    @app.route("/review-v2/history/<run_id>", methods=["GET"])
    def review_v2_history(run_id: str) -> str:
        result = load_result_by_run_id(run_id)
        return render_template(
            "review_v2.html",
            result=result,
            history_runs=list_recent_runs(),
            error=None if result else "未找到对应的 V2 审查记录。",
            active_page="review_v2",
            current_run_id=run_id,
        )

    @app.route("/review-v2/start", methods=["POST"])
    def review_v2_start() -> Response:
        upload = request.files.get("tender_file")  # type: ignore[name-defined]
        if not upload or not upload.filename:
            return jsonify({"ok": False, "error": "请选择招标文件。"}), 400
        if not allowed_file(upload.filename):
            return jsonify({"ok": False, "error": "仅支持 .docx / .txt / .md 文件。"}), 400
        upload_path = _save_upload(upload)
        job_id = f"job-v2-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(4)}"
        create_job(job_id, upload.filename)
        worker = threading.Thread(
            target=run_review_job,
            args=(job_id, upload_path, upload.filename, load_config()),
            daemon=True,
        )
        worker.start()
        return jsonify(
            {
                "ok": True,
                "job_id": job_id,
                "status_url": url_for("review_v2_status", job_id=job_id),
                "started_at": get_job(job_id)["started_at"],
                "stage": "file_reading",
                "message": STAGE_TO_MESSAGE["file_reading"],
            }
        )

    @app.route("/review-v2/status/<job_id>", methods=["GET"])
    def review_v2_status(job_id: str) -> Response:
        job = get_job(job_id)
        if not job:
            return jsonify({"ok": False, "error": "未找到对应的 V2 审查任务。"}), 404
        return jsonify({"ok": True, **job})

    @app.route("/review-v2/download/<run_id>/<kind>", methods=["GET"])
    def download_v2_file(run_id: str, kind: str) -> Response:
        run_dir = find_run_dir(run_id)
        mapping = {
            "review": ("review.md", "text/markdown; charset=utf-8"),
            "extracted": ("extracted_text.md", "text/plain; charset=utf-8"),
            "baseline": ("baseline_review.md", "text/markdown; charset=utf-8"),
            "document_map": ("document_map.json", "application/json"),
            "overview": ("v2_overview.json", "application/json"),
        }
        if run_dir is None or kind not in mapping:
            return redirect(url_for("review_v2_page"))
        filename, mimetype = mapping[kind]
        target = run_dir / filename
        if not target.exists():
            return redirect(url_for("review_v2_page"))
        return send_file(target, mimetype=mimetype, as_attachment=True, download_name=f"{run_id}-{filename}")

    return app
app = create_app()
