from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.governance.rule_registry import (
    ValidationResult,
    collect_formal_admission_signals,
    load_registry_rules,
    validate_ax_governance_files,
    validate_candidate_directory,
    validate_formal_admission_sources,
    validate_rule_directory,
    validate_rule_file,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate rule registry YAML files.")
    parser.add_argument(
        "--candidate-root",
        default=None,
        help="Candidate governance root to validate, for example rules/candidates.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=[],
        help="Rule YAML file or directory to validate.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    target_paths = list(args.paths) if args.paths else ([] if args.candidate_root else ["rules/registry"])

    results = []
    signals: list[str] = []
    if args.candidate_root:
        results.append(validate_candidate_directory(args.candidate_root))
    results.extend(validate_ax_governance_files())

    for raw_path in target_paths:
        path = Path(raw_path)
        if path.is_dir():
            results.extend(validate_rule_directory(path))
            if path.as_posix().endswith("rules/registry"):
                governance_path = ROOT / "rules" / "governance" / "formal_admission_registry.yaml"
                supplemental_payload = {}
                if governance_path.exists():
                    supplemental_payload = yaml.safe_load(governance_path.read_text(encoding="utf-8")) or {}
                errors = validate_formal_admission_sources(load_registry_rules(path), supplemental_payload)
                signals.extend(collect_formal_admission_signals(load_registry_rules(path), supplemental_payload))
                if errors:
                    results.append(ValidationResult(path=governance_path, errors=errors))
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
    for signal in signals:
        print(f"SIGNAL {signal}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
