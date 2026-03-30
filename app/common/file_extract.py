from __future__ import annotations

from pathlib import Path

from app.common.core import extract_text


def extract_document_text(input_path: Path) -> str:
    """Thin wrapper for future pipeline-specific extraction strategies."""
    return extract_text(input_path)
