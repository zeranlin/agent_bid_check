#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.pipelines.v2.replay_baseline import load_real_replay_baseline_suite, run_real_replay_baseline, run_real_replay_baseline_batch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行真实文件 replay 基线。")
    parser.add_argument(
        "--config",
        default="docs/trackers/v2-real-replay-baselines.yaml",
        help="replay 基线配置路径",
    )
    parser.add_argument("--document-id", help="只跑单个 document_id；不传则批量跑全部")
    parser.add_argument("--output-root", help="覆盖输出根目录，默认使用配置内 result_dir")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    suite = load_real_replay_baseline_suite(args.config)
    if args.document_id:
        results = [run_real_replay_baseline(suite, document_id=args.document_id, output_root=args.output_root)]
    else:
        results = run_real_replay_baseline_batch(suite, output_root=args.output_root)
    print(json.dumps({"suite_id": suite["suite_id"], "results": results}, ensure_ascii=False, indent=2))
    return 0 if all(
        not result["missing_should_report"]
        and not result["unexpected_reported"]
        and not result["missing_should_pending"]
        and not result["unexpected_pending"]
        and not result["mismatched_layers"]
        for result in results
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
