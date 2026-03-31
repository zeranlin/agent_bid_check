from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.common.eval_dataset import DEFAULT_EVAL_ROOT
from app.config import PROJECT_ROOT as APP_PROJECT_ROOT
from scripts.eval_v2_all import build_markdown_report as build_all_markdown_report
from scripts.eval_v2_all import build_overall_summary, run_compare_stage, run_regression_stage, run_structure_stage, run_topics_stage
from scripts.eval_v2_all import write_outputs as write_all_outputs
from scripts.eval_v2_regression import build_summary as build_regression_summary
from scripts.eval_v2_regression import collect_outputs, evaluate_sample as evaluate_regression_sample, load_samples as load_regression_samples
from scripts.eval_v2_regression import resolve_v2_eval_sample_path, write_outputs as write_regression_outputs


DEFAULT_BATCH_ROOT = APP_PROJECT_ROOT / "data" / "eval_runs" / "v2"


def build_run_label(now: datetime | None = None) -> str:
    current = now or datetime.now()
    return current.strftime("%Y%m%d-%H%M%S")


def run_fixed_batch(dataset_root: Path | None, output_root: Path, run_label: str) -> dict:
    run_dir = output_root / run_label
    regression_dir = run_dir / "regression"
    all_dir = run_dir / "all"

    regression_sample_path = resolve_v2_eval_sample_path("regression", dataset_root=dataset_root)
    regression_results = [evaluate_regression_sample(sample) for sample in load_regression_samples(regression_sample_path)]
    regression_summary = build_regression_summary(regression_results, regression_sample_path)
    regression_outputs = collect_outputs(regression_results)
    write_regression_outputs(regression_dir, regression_summary, regression_outputs)

    stage_results = [
        run_structure_stage(dataset_root),
        run_topics_stage(dataset_root),
        run_compare_stage(dataset_root),
        run_regression_stage(dataset_root),
    ]
    all_summary = build_overall_summary(stage_results, dataset_root)
    write_all_outputs(all_dir, all_summary)

    batch_summary = {
        "run_label": run_label,
        "dataset_root": str(dataset_root or DEFAULT_EVAL_ROOT),
        "run_dir": str(run_dir),
        "commands": [
            f"python scripts/eval_v2_regression.py --dataset-root {dataset_root or DEFAULT_EVAL_ROOT}",
            f"python scripts/eval_v2_all.py --dataset-root {dataset_root or DEFAULT_EVAL_ROOT}",
        ],
        "artifacts": {
            "regression_dir": str(regression_dir),
            "all_dir": str(all_dir),
            "regression_summary": str(regression_dir / "regression_summary.json"),
            "all_summary": str(all_dir / "v2_all_eval.json"),
        },
        "regression": {
            "structure_hit_rate": regression_summary.get("structure_hit_rate", 0.0),
            "topic_coverage_hit_rate": regression_summary.get("topic_coverage_hit_rate", 0.0),
            "risk_hit_rate": regression_summary.get("risk_hit_rate", 0.0),
            "miss_rate": regression_summary.get("miss_rate", 0.0),
        },
        "overall": {
            "quality_gate_status": all_summary.get("quality_gate_status", "failed"),
            "gate_blocker_count": all_summary.get("gate_blocker_count", 0),
        },
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "batch_summary.json").write_text(json.dumps(batch_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "batch_summary.md").write_text(build_batch_markdown(batch_summary, all_summary), encoding="utf-8")
    return batch_summary


def build_batch_markdown(batch_summary: dict, all_summary: dict) -> str:
    lines = [
        "# V2 固定回归跑批结果",
        "",
        f"- 跑批编号：`{batch_summary['run_label']}`",
        f"- 数据集目录：`{batch_summary['dataset_root']}`",
        f"- 输出目录：`{batch_summary['run_dir']}`",
        f"- 质量门禁：`{batch_summary['overall']['quality_gate_status']}`",
        f"- 阻塞项数量：`{batch_summary['overall']['gate_blocker_count']}`",
        "",
        "## 固定执行命令",
        "",
    ]
    lines.extend([f"- `{command}`" for command in batch_summary.get("commands", [])])
    lines.extend(
        [
            "",
            "## 回归关键指标",
            "",
            f"- `structure_hit_rate`：`{float(batch_summary['regression']['structure_hit_rate']):.2%}`",
            f"- `topic_coverage_hit_rate`：`{float(batch_summary['regression']['topic_coverage_hit_rate']):.2%}`",
            f"- `risk_hit_rate`：`{float(batch_summary['regression']['risk_hit_rate']):.2%}`",
            f"- `miss_rate`：`{float(batch_summary['regression']['miss_rate']):.2%}`",
            "",
            "## 总评估摘要",
            "",
        ]
    )
    lines.extend(build_all_markdown_report(all_summary).splitlines())
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="固定执行 V2 regression 与 all 评估，并归档结果。")
    parser.add_argument("--dataset-root", type=Path, default=None, help=f"固定评估数据集目录，默认 {DEFAULT_EVAL_ROOT}")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_BATCH_ROOT, help="跑批结果根目录")
    parser.add_argument("--run-label", type=str, default="", help="跑批编号，默认自动生成时间戳")
    parser.add_argument("--json", action="store_true", help="仅输出跑批摘要 JSON")
    args = parser.parse_args()

    run_label = args.run_label.strip() or build_run_label()
    batch_summary = run_fixed_batch(args.dataset_root, args.output_root, run_label)
    if args.json:
        print(json.dumps(batch_summary, ensure_ascii=False, indent=2))
    else:
        print((Path(batch_summary["run_dir"]) / "batch_summary.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
