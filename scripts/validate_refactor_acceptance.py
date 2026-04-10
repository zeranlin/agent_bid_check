#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.pipelines.v2.refactor_acceptance import build_refactor_acceptance_summary


def main() -> int:
    summary = build_refactor_acceptance_summary(PROJECT_ROOT)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
