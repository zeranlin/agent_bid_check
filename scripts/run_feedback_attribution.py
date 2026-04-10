#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.pipelines.v2.feedback_attribution import attribute_feedback_batch, load_feedback_attribution_registry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行反馈分层归因。")
    parser.add_argument(
        "--config",
        default="docs/trackers/v2-feedback-attribution-ledger.yaml",
        help="反馈归因配置路径",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tracker = load_feedback_attribution_registry(args.config)
    decisions = attribute_feedback_batch(tracker)
    print(json.dumps({"ledger_id": tracker["ledger_id"], "decisions": decisions}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
