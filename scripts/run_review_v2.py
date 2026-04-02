#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import ReviewSettings
from app.pipelines.v2.service import review_document_v2, save_review_artifacts_v2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行 V2 三层招标文件合规审查。")
    parser.add_argument("input_file", help="输入文件路径，支持 .docx/.txt/.md")
    parser.add_argument("-o", "--output-dir", required=True, help="输出目录，例如 data/results/v2/demo-run")
    parser.add_argument("--topic-mode", default="mature", choices=["slim", "default", "enhanced", "mature"])
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=6400)
    parser.add_argument("--timeout", type=int, default=1800)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input_file).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    settings = ReviewSettings.from_env()
    if args.base_url:
        settings.base_url = args.base_url
    if args.model:
        settings.model = args.model
    if args.api_key:
        settings.api_key = args.api_key
    settings.temperature = args.temperature
    settings.max_tokens = args.max_tokens
    settings.timeout = args.timeout

    try:
        artifacts = review_document_v2(input_path, settings, topic_mode=args.topic_mode)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP error {exc.code}: {body}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"V2 review failed: {exc}", file=sys.stderr)
        return 1

    save_review_artifacts_v2(artifacts, output_dir)
    print(f"Saved V2 review result to: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
