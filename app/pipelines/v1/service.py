from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.common.artifacts import ReviewArtifacts
from app.common.core import build_prompt, maybe_disable_qwen_thinking
from app.common.file_extract import extract_document_text
from app.common.llm_client import call_chat_completion, call_chat_completion_stream, extract_response_text
from app.common.markdown_utils import normalize_review_markdown
from app.config import ReviewSettings

from .assembler import build_request_payload


def review_document(
    input_path: Path,
    settings: ReviewSettings,
    progress_callback: Callable[[str, str], None] | None = None,
    stream_callback: Callable[[str], None] | None = None,
) -> ReviewArtifacts:
    if progress_callback:
        progress_callback("file_reading", "系统正在阅读招标文件并整理文本结构。")
    extracted = extract_document_text(input_path)
    if not extracted.strip():
        raise ValueError("No text extracted from input file.")

    user_prompt = build_prompt(extracted, settings.user_prompt)
    user_prompt = maybe_disable_qwen_thinking(user_prompt, settings.model)
    request_payload = build_request_payload(settings, user_prompt)
    if progress_callback:
        progress_callback("smart_review", "正在进行智能审查，逐项比对资格条件、评分办法与商务条款。")
    try:
        response = call_chat_completion_stream(
            base_url=settings.base_url,
            model=settings.model,
            api_key=settings.api_key,
            system_prompt=settings.system_prompt,
            user_prompt=user_prompt,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            timeout=settings.timeout,
            on_text=stream_callback,
        )
    except Exception:
        response = call_chat_completion(
            base_url=settings.base_url,
            model=settings.model,
            api_key=settings.api_key,
            system_prompt=settings.system_prompt,
            user_prompt=user_prompt,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            timeout=settings.timeout,
        )
    content = extract_response_text(response)
    if not content:
        message = response.get("choices", [{}])[0].get("message", {})
        reasoning = message.get("reasoning")
        if reasoning and not message.get("content"):
            raise RuntimeError("模型返回了 reasoning 但没有 content。当前服务可能仍在启用思考模式。")
        raise RuntimeError("接口返回格式异常，未提取到正文内容。")

    if progress_callback:
        progress_callback("report_structuring", "正在梳理审查报告，生成统一格式结果。")
    final_markdown = normalize_review_markdown(content, input_path.name)
    return ReviewArtifacts(
        extracted_text=extracted,
        request_payload=request_payload,
        response_payload=response,
        raw_markdown=content,
        final_markdown=final_markdown,
    )
