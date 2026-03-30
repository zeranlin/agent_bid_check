from __future__ import annotations

import argparse
import sys
import urllib.error
from pathlib import Path

from app.config import ReviewSettings
from app.pipelines.v1.assembler import save_review_artifacts
from app.pipelines.v1.service import review_document


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="提取招标文件文本并调用 OpenAI 兼容接口生成合规审查 Markdown。"
    )
    parser.add_argument("input_file", help="输入文件路径，支持 .docx/.txt/.md")
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="输出 Markdown 路径，例如 result.md",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="OpenAI 兼容接口地址，默认读取 LLM_BASE_URL 或使用示例地址",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="模型名，默认读取 LLM_MODEL 或 qwen3.5-27b",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="接口密钥，默认读取 LLM_API_KEY 或示例值",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="采样温度，默认 0.0",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=6400,
        help="生成最大 token 数，默认 6400",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="接口超时时间（秒），默认 1800",
    )
    parser.add_argument(
        "--prompt-file",
        help="自定义用户提示词文件；不传则使用内置审查提示词",
    )
    parser.add_argument(
        "--system-prompt-file",
        help="自定义 system prompt 文件；不传则使用内置 system prompt",
    )
    parser.add_argument(
        "--save-extracted",
        help="保存提取后的正文文本到指定路径，便于核查",
    )
    parser.add_argument(
        "--save-request-json",
        help="保存请求体 JSON 到指定路径",
    )
    parser.add_argument(
        "--save-raw-response",
        help="保存原始接口响应 JSON 到指定路径",
    )
    parser.add_argument(
        "--save-raw-markdown",
        help="保存模型原始 Markdown 到指定路径",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input_file).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()

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
    if args.system_prompt_file:
        settings.system_prompt = Path(args.system_prompt_file).read_text(encoding="utf-8")
    if args.prompt_file:
        settings.user_prompt = Path(args.prompt_file).read_text(encoding="utf-8")

    try:
        artifacts = review_document(input_path, settings)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP error {exc.code}: {body}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"LLM request failed: {exc}", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_review_artifacts(
        artifacts,
        output_markdown=output_path,
        output_raw_markdown=Path(args.save_raw_markdown).expanduser().resolve() if args.save_raw_markdown else None,
        extracted_path=Path(args.save_extracted).expanduser().resolve() if args.save_extracted else None,
        request_json_path=Path(args.save_request_json).expanduser().resolve() if args.save_request_json else None,
        response_json_path=Path(args.save_raw_response).expanduser().resolve() if args.save_raw_response else None,
    )
    print(f"Saved review result to: {output_path}")
    return 0
