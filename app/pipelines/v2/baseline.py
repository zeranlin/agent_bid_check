from __future__ import annotations

from pathlib import Path

from app.common.markdown_utils import normalize_review_markdown
from app.config import ReviewSettings
from app.review.service import review_document

from .schemas import V2StageArtifact


def run_baseline_review(
    input_path: Path,
    settings: ReviewSettings,
    progress_callback=None,
    stream_callback=None,
) -> V2StageArtifact:
    artifacts = review_document(
        input_path=input_path,
        settings=settings,
        progress_callback=progress_callback,
        stream_callback=stream_callback,
    )
    return V2StageArtifact(
        name="baseline",
        content=normalize_review_markdown(artifacts.final_markdown, input_path.name),
        raw_output=artifacts.raw_markdown,
        metadata={
            "request_payload": artifacts.request_payload,
            "response_payload": artifacts.response_payload,
        },
    )

