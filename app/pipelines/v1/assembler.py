from __future__ import annotations

import json
from pathlib import Path

from app.common.artifacts import ReviewArtifacts
from app.common.core import save_text


def build_request_payload(settings, user_prompt: str) -> dict:
    payload = {
        "model": settings.model,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "messages": [
            {"role": "system", "content": settings.system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if "qwen" in settings.model.lower():
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    return payload


def save_review_artifacts(
    artifacts: ReviewArtifacts,
    *,
    output_markdown: Path | None = None,
    output_raw_markdown: Path | None = None,
    extracted_path: Path | None = None,
    request_json_path: Path | None = None,
    response_json_path: Path | None = None,
) -> None:
    if extracted_path:
        save_text(extracted_path, artifacts.extracted_text)
    if request_json_path:
        save_text(request_json_path, json.dumps(artifacts.request_payload, ensure_ascii=False, indent=2))
    if response_json_path:
        save_text(response_json_path, json.dumps(artifacts.response_payload, ensure_ascii=False, indent=2))
    if output_raw_markdown:
        save_text(output_raw_markdown, artifacts.raw_markdown)
    if output_markdown:
        save_text(output_markdown, artifacts.final_markdown)
