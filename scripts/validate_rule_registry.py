from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.governance.rule_registry import validate_rule_directory, validate_rule_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate rule registry YAML files.")
    parser.add_argument(
        "paths",
        nargs="*",
        default=["rules/registry"],
        help="Rule YAML file or directory to validate.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    results = []
    for raw_path in args.paths:
        path = Path(raw_path)
        if path.is_dir():
            results.extend(validate_rule_directory(path))
        else:
            results.append(validate_rule_file(path))

    failed = False
    for result in results:
        if result.ok:
            print(f"OK {result.path}")
            continue
        failed = True
        print(f"FAIL {result.path}")
        for error in result.errors:
            print(f"  - {error}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
