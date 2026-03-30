from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from app.config import WEB_JOBS_DIR


JOB_LOCK = threading.Lock()
REVIEW_JOBS: dict[str, dict] = {}


def job_status_path(job_id: str) -> Path:
    return WEB_JOBS_DIR / f"{job_id}.json"


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


def create_job(job_id: str, filename: str, initial_message: str) -> None:
    with JOB_LOCK:
        REVIEW_JOBS[job_id] = {
            "job_id": job_id,
            "filename": filename,
            "status": "running",
            "stage": "file_reading",
            "message": initial_message,
            "started_at": time.time(),
            "partial_text": "",
            "run_id": None,
            "redirect_url": None,
            "error": None,
        }
        persist_job(REVIEW_JOBS[job_id])


def update_job(job_id: str, **updates: object) -> None:
    with JOB_LOCK:
        job = REVIEW_JOBS.get(job_id)
        if not job:
            disk_job = load_job_from_disk(job_id)
            if not disk_job:
                return
            REVIEW_JOBS[job_id] = disk_job
            job = REVIEW_JOBS[job_id]
        job.update(updates)
        persist_job(job)


def get_job(job_id: str) -> dict | None:
    with JOB_LOCK:
        job = REVIEW_JOBS.get(job_id)
        if job:
            return dict(job)
    disk_job = load_job_from_disk(job_id)
    if disk_job:
        with JOB_LOCK:
            REVIEW_JOBS[job_id] = disk_job
        return dict(disk_job)
    return None


def append_job_text(job_id: str, chunk: str, keep_chars: int = 12000) -> None:
    if not chunk:
        return
    with JOB_LOCK:
        job = REVIEW_JOBS.get(job_id)
        if not job:
            disk_job = load_job_from_disk(job_id)
            if not disk_job:
                return
            REVIEW_JOBS[job_id] = disk_job
            job = REVIEW_JOBS[job_id]
        current = str(job.get("partial_text", ""))
        job["partial_text"] = (current + chunk)[-keep_chars:]
        persist_job(job)
