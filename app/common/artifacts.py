from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReviewArtifacts:
    extracted_text: str
    request_payload: dict
    response_payload: dict
    raw_markdown: str
    final_markdown: str

