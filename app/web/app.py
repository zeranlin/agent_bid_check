from __future__ import annotations
"""V1 Web application for the single-pass review workflow."""

import html
import json
import re
import secrets
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, render_template, request, send_file, url_for
from markupsafe import Markup
from werkzeug.utils import secure_filename

from app.config import WEB_CONFIG_PATH, WEB_RESULTS_DIR, WEB_UPLOADS_DIR, ReviewSettings, ensure_data_dirs, load_web_settings, save_web_settings
from app.pipelines.v1.assembler import save_review_artifacts
from app.pipelines.v1.service import review_document
from app.review.schema import ReviewReport
from app.web.job_store import append_job_text, create_job, get_job, update_job
from app.web.review_repository import build_result_payload, find_run_dir, list_recent_runs, load_result_by_run_id, make_run_dir


MODULE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = WEB_UPLOADS_DIR
RESULTS_DIR = WEB_RESULTS_DIR
ALLOWED_EXTENSIONS = {".docx", ".txt", ".md"}

INLINE_CODE_RE = re.compile(r"`([^`]+)`")
STRONG_RE = re.compile(r"\*\*(.+?)\*\*")
EM_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
INLINE_BULLET_RE = re.compile(r'(?<=[。；;"”])\s*-\s*(?=["“]?\d+[.、])')
STAGE_SEQUENCE = ["file_reading", "smart_review", "report_structuring"]
STAGE_TO_MESSAGE = {
    "file_reading": "系统正在阅读招标文件并整理文本结构。",
    "smart_review": "正在进行智能审查，逐项比对资格条件、评分办法与商务条款。",
    "report_structuring": "正在梳理审查报告，生成统一格式结果。",
}


def ensure_runtime_dirs() -> None:
    ensure_data_dirs()


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
            quote_text = stripped[1:].strip()
            paragraph.append(quote_text)
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
    normalized = INLINE_BULLET_RE.sub("\n- ", normalized)
    return normalized


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def load_config() -> dict[str, str]:
    return load_web_settings().to_form_dict()


def save_config(config: dict[str, str]) -> None:
    settings = ReviewSettings.from_dict(config)
    save_web_settings(settings)


def run_review_job(job_id: str, upload_path: Path, original_filename: str, form: dict[str, str]) -> None:
    try:
        settings = ReviewSettings.from_dict(form)

        def on_progress(stage: str, message: str) -> None:
            update_job(job_id, stage=stage, message=message, status="running")

        def on_stream_text(chunk: str) -> None:
            append_job_text(job_id, chunk)

        artifacts = review_document(
            upload_path,
            settings,
            progress_callback=on_progress,
            stream_callback=on_stream_text,
        )

        run_id, run_dir = make_run_dir()
        extracted_path = run_dir / "extracted.txt"
        request_json_path = run_dir / "request.json"
        response_json_path = run_dir / "response.json"
        output_md_path = run_dir / "review.md"
        raw_output_md_path = run_dir / "review_raw.md"
        meta_json_path = run_dir / "meta.json"

        save_review_artifacts(
            artifacts,
            output_markdown=output_md_path,
            output_raw_markdown=raw_output_md_path,
            extracted_path=extracted_path,
            request_json_path=request_json_path,
            response_json_path=response_json_path,
        )
        meta = {
            "run_id": run_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "original_filename": original_filename,
            "saved_filename": upload_path.name,
            "base_url": settings.base_url,
            "model": settings.model,
            "config_path": str(WEB_CONFIG_PATH),
        }
        meta_json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        update_job(
            job_id,
            status="completed",
            stage="completed",
            message="审查完成，正在跳转到结果页。",
            run_id=run_id,
            redirect_url=f"/review/history/{run_id}",
        )
    except Exception as exc:
        update_job(
            job_id,
            status="failed",
            stage="failed",
            message="审查失败，请查看错误信息。",
            error=str(exc),
        )


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

    @app.route("/", methods=["GET"])
    def index() -> str:
        return redirect(url_for("review_page"))

    @app.route("/config", methods=["GET", "POST"])
    def config_page() -> str:
        form = load_config()
        message = None
        error = None

        if request.method == "POST":
            form.update({k: request.form.get(k, v) for k, v in form.items()})
            try:
                ReviewSettings.from_dict(form)
                save_config(form)
                message = "配置已保存，审查工作台将使用这套参数。"
            except ValueError:
                error = "温度、最大输出 Token、超时必须是合法数字。"

        return render_template(
            "config.html",
            form=form,
            result=None,
            error=error,
            message=message,
            active_page="config",
        )

    @app.route("/review", methods=["GET"])
    def review_page() -> str:
        return render_template(
            "review.html",
            form=load_config(),
            result=None,
            history_runs=list_recent_runs(lambda run_id: url_for("review_history", run_id=run_id)),
            error=None,
            active_page="review",
        )

    @app.route("/review/history/<run_id>", methods=["GET"])
    def review_history(run_id: str) -> str:
        result = load_result_by_run_id(run_id, render_markdown)
        if result is None:
            return render_template(
                "review.html",
                form=load_config(),
                result=None,
                history_runs=list_recent_runs(lambda current_run_id: url_for("review_history", run_id=current_run_id)),
                error="未找到对应的历史审查记录。",
                active_page="review",
            )
        return render_template(
            "review.html",
            form=load_config(),
            result=result,
            history_runs=list_recent_runs(lambda current_run_id: url_for("review_history", run_id=current_run_id)),
            error=None,
            active_page="review",
        )

    @app.route("/review/run", methods=["POST"])
    def review() -> str:
        form = load_config()

        upload = request.files.get("tender_file")
        if not upload or not upload.filename:
            return render_template(
                "review.html",
                form=form,
                result=None,
                history_runs=list_recent_runs(lambda run_id: url_for("review_history", run_id=run_id)),
                error="请选择招标文件。",
                active_page="review",
            )
        if not allowed_file(upload.filename):
            return render_template(
                "review.html",
                form=form,
                result=None,
                history_runs=list_recent_runs(lambda run_id: url_for("review_history", run_id=run_id)),
                error="仅支持 .docx / .txt / .md 文件。",
                active_page="review",
            )

        filename = secure_filename(upload.filename) or "upload.docx"
        upload_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
        upload_path = UPLOADS_DIR / f"{upload_id}-{filename}"
        upload.save(upload_path)

        try:
            settings = ReviewSettings.from_dict(form)
            artifacts = review_document(upload_path, settings)

            run_id, run_dir = make_run_dir()
            extracted_path = run_dir / "extracted.txt"
            request_json_path = run_dir / "request.json"
            response_json_path = run_dir / "response.json"
            output_md_path = run_dir / "review.md"
            raw_output_md_path = run_dir / "review_raw.md"
            meta_json_path = run_dir / "meta.json"

            save_review_artifacts(
                artifacts,
                output_markdown=output_md_path,
                output_raw_markdown=raw_output_md_path,
                extracted_path=extracted_path,
                request_json_path=request_json_path,
                response_json_path=response_json_path,
            )
            meta = {
                "run_id": run_id,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "original_filename": upload.filename,
                "saved_filename": upload_path.name,
                "base_url": settings.base_url,
                "model": settings.model,
                "config_path": str(WEB_CONFIG_PATH),
            }
            meta_json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

            result = build_result_payload(run_id, upload.filename, artifacts.final_markdown, artifacts.raw_markdown, render_markdown)
            result["created_at"] = meta["created_at"]
            return render_template(
                "review.html",
                form=form,
                result=result,
                history_runs=list_recent_runs(lambda current_run_id: url_for("review_history", run_id=current_run_id)),
                error=None,
                active_page="review",
            )

        except Exception as exc:
            return render_template(
                "review.html",
                form=form,
                result=None,
                history_runs=list_recent_runs(lambda run_id: url_for("review_history", run_id=run_id)),
                error=str(exc),
                active_page="review",
            )

    @app.route("/review/start", methods=["POST"])
    def review_start() -> Response:
        form = load_config()
        upload = request.files.get("tender_file")
        if not upload or not upload.filename:
            return jsonify({"ok": False, "error": "请选择招标文件。"}), 400
        if not allowed_file(upload.filename):
            return jsonify({"ok": False, "error": "仅支持 .docx / .txt / .md 文件。"}), 400

        filename = secure_filename(upload.filename) or "upload.docx"
        upload_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
        upload_path = UPLOADS_DIR / f"{upload_id}-{filename}"
        upload.save(upload_path)

        job_id = f"job-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(4)}"
        create_job(job_id, upload.filename, STAGE_TO_MESSAGE["file_reading"])
        worker = threading.Thread(
            target=run_review_job,
            args=(job_id, upload_path, upload.filename, form),
            daemon=True,
        )
        worker.start()
        return jsonify(
            {
                "ok": True,
                "job_id": job_id,
                "status_url": url_for("review_status", job_id=job_id),
                "started_at": get_job(job_id)["started_at"],
                "stage": "file_reading",
                "message": STAGE_TO_MESSAGE["file_reading"],
            }
        )

    @app.route("/review/status/<job_id>", methods=["GET"])
    def review_status(job_id: str) -> Response:
        job = get_job(job_id)
        if not job:
            return jsonify({"ok": False, "error": "未找到对应的审查任务。"}), 404
        return jsonify({"ok": True, **job})

    @app.route("/download/<run_id>/<kind>", methods=["GET"])
    def download_file(run_id: str, kind: str) -> Response:
        run_dir = find_run_dir(run_id)
        mapping = {
            "review": ("review.md", "text/markdown; charset=utf-8"),
            "review_raw": ("review_raw.md", "text/markdown; charset=utf-8"),
            "request": ("request.json", "application/json"),
            "response": ("response.json", "application/json"),
            "extracted": ("extracted.txt", "text/plain; charset=utf-8"),
        }
        if run_dir is None or kind not in mapping:
            return redirect(url_for("index"))
        filename, mimetype = mapping[kind]
        target = run_dir / filename
        if not target.exists():
            return redirect(url_for("index"))
        return send_file(
            target,
            mimetype=mimetype,
            as_attachment=True,
            download_name=f"{run_id}-{filename}",
        )

    return app


app = create_app()
