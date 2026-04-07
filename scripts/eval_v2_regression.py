from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import PROJECT_ROOT as APP_PROJECT_ROOT
from app.common.eval_dataset import DEFAULT_EVAL_ROOT, resolve_v2_eval_sample_path
from app.pipelines.v2.regression import compare_risks, compare_structure, extract_actual_risks, extract_actual_structure, load_result_payload


DEFAULT_SAMPLE_PATH = APP_PROJECT_ROOT / "data" / "examples" / "v2_regression_eval_samples.json"
FAILURE_CODEBOOK = {
    "section_not_found": {
        "label": "必需章节未召回",
        "layer": "structure",
        "category": "recall_gap",
        "suggestion": "优先补章节切分与标题识别规则。",
    },
    "module_mismatch": {
        "label": "章节主模块识别错误",
        "layer": "structure",
        "category": "module_classification",
        "suggestion": "补模块关键词与主归属规则。",
    },
    "secondary_modules_missing": {
        "label": "章节次模块覆盖不足",
        "layer": "structure",
        "category": "module_coverage",
        "suggestion": "补共享模块与混合章节识别规则。",
    },
    "missing_titles": {
        "label": "专题缺少必需章节标题",
        "layer": "coverage",
        "category": "evidence_coverage",
        "suggestion": "补专题 coverage 的标题召回与证据映射。",
    },
    "missing_modules": {
        "label": "专题缺少必需模块覆盖",
        "layer": "coverage",
        "category": "evidence_coverage",
        "suggestion": "补专题 evidence bundle 的模块覆盖规则。",
    },
    "risk_not_extracted": {
        "label": "专题风险未抽取命中",
        "layer": "topic",
        "category": "risk_extraction",
        "suggestion": "补专题 prompt 或风险抽取规则。",
    },
    "manual_review_flag_mismatch": {
        "label": "人工复核判定与金标不一致",
        "layer": "topic",
        "category": "manual_review_boundary",
        "suggestion": "收紧明确风险与人工复核的边界。",
    },
    "false_positive_risk": {
        "label": "汇总层出现额外风险点",
        "layer": "compare",
        "category": "false_positive",
        "suggestion": "排查汇总去重与冲突裁决逻辑。",
    },
    "acceptance_plan_in_scoring_forbidden": {
        "label": "验收方案被违规纳入评分因素",
        "layer": "compare",
        "category": "rule_conflict",
        "suggestion": "补评分禁入项规则与评分条款交叉校验。",
    },
    "payment_terms_in_scoring_forbidden": {
        "label": "付款方式被违规纳入评分因素",
        "layer": "compare",
        "category": "rule_conflict",
        "suggestion": "补付款条款禁入评分规则与评分标准的交叉校验。",
    },
    "gifts_or_unrelated_goods_in_scoring_forbidden": {
        "label": "赠品或无关商品服务被违规纳入评分因素",
        "layer": "compare",
        "category": "rule_conflict",
        "suggestion": "补赠品/回扣/无关商品服务禁入评分规则与评分标准的交叉校验。",
    },
    "specific_brand_or_supplier_in_scoring_forbidden": {
        "label": "特定认证证书或制造商限定被违规纳入评分因素",
        "layer": "compare",
        "category": "rule_conflict",
        "suggestion": "补制造商限定、特定认证体系与评分标准的交叉校验。",
    },
    "acceptance_testing_cost_shifted_to_bidder": {
        "label": "验收检测费用被违规计入投标人承担范围",
        "layer": "compare",
        "category": "rule_conflict",
        "suggestion": "补验收检测费用禁转嫁规则与需求条款承担范围的交叉校验。",
    },
    "cancelled_or_non_mandatory_qualification_as_gate": {
        "label": "已取消或非强制资质资格被违规作为资格条件",
        "layer": "compare",
        "category": "rule_conflict",
        "suggestion": "补资格条件侧已取消或非强制资质资格禁入门槛规则与资格条款的交叉校验。",
    },
    "policy_technical_inconsistency": {
        "label": "采购政策与技术标准引用口径不一致",
        "layer": "compare",
        "category": "rule_conflict",
        "suggestion": "补政策口径与技术标准引用的一致性比对。",
    },
    "star_marker_missing_for_mandatory_standard": {
        "label": "强制性标准条款未按规则标注星号",
        "layer": "compare",
        "category": "rule_conflict",
        "suggestion": "补规则侧星号要求与正文条款标识的交叉校验。",
    },
    "unknown_reason": {
        "label": "未归类失败原因",
        "layer": "unknown",
        "category": "unknown",
        "suggestion": "需人工补充失败原因映射。",
    },
}


def load_samples(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("回归样本文件必须是数组。")
    return [item for item in data if isinstance(item, dict)]


def _split_reason_codes(reason: object) -> list[str]:
    text = str(reason or "").strip()
    if not text:
        return []
    return [item.strip() for item in text.split(",") if item.strip()]


def normalize_failure_code(code: object) -> str:
    normalized = str(code or "").strip()
    if not normalized:
        return "unknown_reason"
    return normalized if normalized in FAILURE_CODEBOOK else "unknown_reason"


def describe_failure_code(code: object) -> dict[str, str]:
    normalized = normalize_failure_code(code)
    meta = FAILURE_CODEBOOK.get(normalized, FAILURE_CODEBOOK["unknown_reason"])
    return {
        "code": normalized,
        "label": str(meta["label"]),
        "layer": str(meta["layer"]),
        "category": str(meta["category"]),
        "suggestion": str(meta["suggestion"]),
    }


def _build_failure_analysis(structure_result: dict, risk_result: dict) -> dict:
    structure_reasons: list[str] = []
    coverage_reasons: list[str] = []
    topic_reasons: list[str] = []
    compare_reasons: list[str] = []

    for item in structure_result.get("missed_sections", []):
        for reason in _split_reason_codes(item.get("reason")):
            structure_reasons.append(normalize_failure_code(reason))

    for item in structure_result.get("missed_topic_coverages", []):
        for reason in _split_reason_codes(item.get("reason")):
            coverage_reasons.append(normalize_failure_code(reason))

    if risk_result.get("missed_risks"):
        topic_reasons.append("risk_not_extracted")
    for item in risk_result.get("manual_review_gaps", []):
        for reason in _split_reason_codes(item.get("reason")):
            topic_reasons.append(normalize_failure_code(reason))
    if risk_result.get("false_positive_risks"):
        compare_reasons.append("false_positive_risk")

    structure_failed = bool(structure_result.get("missed_sections"))
    coverage_failed = bool(structure_result.get("missed_topic_coverages"))
    topic_failed = bool(risk_result.get("missed_risks") or risk_result.get("manual_review_gaps"))
    compare_failed = bool(risk_result.get("false_positive_risks"))

    layers = [
        {
            "layer": "structure",
            "label": "第一层：结构识别与章节召回",
            "failed": structure_failed,
            "reasons": sorted(set(structure_reasons)),
            "count": len(structure_result.get("missed_sections", [])),
        },
        {
            "layer": "coverage",
            "label": "第一层延伸：专题 coverage 召回",
            "failed": coverage_failed,
            "reasons": sorted(set(coverage_reasons)),
            "count": len(structure_result.get("missed_topic_coverages", [])),
        },
        {
            "layer": "topic",
            "label": "第二层：专题风险抽取",
            "failed": topic_failed,
            "reasons": sorted(set(topic_reasons)),
            "count": len(risk_result.get("missed_risks", [])) + len(risk_result.get("manual_review_gaps", [])),
        },
        {
            "layer": "compare",
            "label": "第三层：汇总与去重",
            "failed": compare_failed,
            "reasons": sorted(set(compare_reasons)),
            "count": len(risk_result.get("false_positive_risks", [])),
        },
    ]

    primary_blocker = "none"
    if structure_failed or coverage_failed:
        primary_blocker = "structure"
    elif topic_failed:
        primary_blocker = "topic"
    elif compare_failed:
        primary_blocker = "compare"

    cascaded_failure = primary_blocker == "structure" and (topic_failed or compare_failed)
    summary_parts: list[str] = []
    if primary_blocker == "structure":
        summary_parts.append("第一层主卡点")
    elif primary_blocker == "topic":
        summary_parts.append("第二层主卡点")
    elif primary_blocker == "compare":
        summary_parts.append("第三层主卡点")
    else:
        summary_parts.append("当前样本无显著失败")
    if cascaded_failure:
        summary_parts.append("并引发后续层级联失败")

    root_cause_codes = sorted(set(structure_reasons + coverage_reasons + topic_reasons + compare_reasons))

    return {
        "primary_blocker_layer": primary_blocker,
        "cascaded_failure": cascaded_failure,
        "root_causes": root_cause_codes,
        "root_cause_details": [describe_failure_code(code) for code in root_cause_codes],
        "layers": layers,
        "summary": "，".join(summary_parts),
    }


def evaluate_sample(sample: dict) -> dict:
    gold = sample.get("gold", {}) if isinstance(sample.get("gold", {}), dict) else {}
    system = sample.get("system", {}) if isinstance(sample.get("system", {}), dict) else {}
    gold_structure = gold.get("structure", {}) if isinstance(gold.get("structure", {}), dict) else {}
    gold_risks = [item for item in gold.get("risks", []) if isinstance(item, dict)] if isinstance(gold, dict) else []

    actual_sections, actual_bundles = extract_actual_structure(system)
    actual_risks = extract_actual_risks(system)

    structure_result = compare_structure(gold_structure, actual_sections, actual_bundles)
    risk_result = compare_risks(gold_risks, actual_risks)
    failure_analysis = _build_failure_analysis(structure_result, risk_result)
    breakpoint = sample.get("breakpoint", {}) if isinstance(sample.get("breakpoint", {}), dict) else {}
    comparison = system.get("comparison", {}) if isinstance(system.get("comparison", {}), dict) else {}
    comparison_metadata = comparison.get("metadata", {}) if isinstance(comparison.get("metadata", {}), dict) else {}
    raw_comparison_failure_reason_codes = comparison_metadata.get(
        "comparison_failure_reason_codes",
        comparison_metadata.get("failure_reason_codes", []),
    )
    comparison_failure_reason_codes = [
        str(item).strip()
        for item in raw_comparison_failure_reason_codes
        if str(item).strip()
    ] if isinstance(raw_comparison_failure_reason_codes, list) else []

    return {
        "sample_id": str(sample.get("sample_id", "sample")),
        "document_name": str(sample.get("document_name", "")),
        "breakpoint": {
            "current_failure_point": str(breakpoint.get("current_failure_point", "")).strip(),
            "recalled_sections": [str(item).strip() for item in breakpoint.get("recalled_sections", []) if str(item).strip()]
            if isinstance(breakpoint.get("recalled_sections", []), list)
            else [],
            "expected_topics": [str(item).strip() for item in breakpoint.get("expected_topics", []) if str(item).strip()]
            if isinstance(breakpoint.get("expected_topics", []), list)
            else [],
            "expected_risk_titles": [
                str(item).strip() for item in breakpoint.get("expected_risk_titles", []) if str(item).strip()
            ]
            if isinstance(breakpoint.get("expected_risk_titles", []), list)
            else [],
        },
        "structure_required_total": len([item for item in gold_structure.get("required_sections", []) if isinstance(item, dict)])
        if isinstance(gold_structure, dict)
        else 0,
        "structure_hit_count": len(structure_result["matched_sections"]),
        "structure_miss_count": len(structure_result["missed_sections"]),
        "topic_coverage_total": len([item for item in gold_structure.get("topic_coverages", []) if isinstance(item, dict)])
        if isinstance(gold_structure, dict)
        else 0,
        "topic_coverage_hit_count": len(structure_result["matched_topic_coverages"]),
        "topic_coverage_miss_count": len(structure_result["missed_topic_coverages"]),
        "gold_risk_total": len(gold_risks),
        "matched_risk_count": len(risk_result["matched_risks"]),
        "missed_risk_count": len(risk_result["missed_risks"]),
        "false_positive_risk_count": len(risk_result["false_positive_risks"]),
        "manual_review_gap_count": len(risk_result["manual_review_gaps"]),
        "failure_analysis": failure_analysis,
        "comparison_failure_reason_codes": comparison_failure_reason_codes,
        "structure": structure_result,
        "risks": risk_result,
    }


def build_summary(results: list[dict], sample_path: Path | None = None) -> dict:
    structure_required_total = sum(int(item.get("structure_required_total", 0)) for item in results)
    structure_hit_count = sum(int(item.get("structure_hit_count", 0)) for item in results)
    topic_coverage_total = sum(int(item.get("topic_coverage_total", 0)) for item in results)
    topic_coverage_hit_count = sum(int(item.get("topic_coverage_hit_count", 0)) for item in results)
    gold_risk_total = sum(int(item.get("gold_risk_total", 0)) for item in results)
    matched_risk_count = sum(int(item.get("matched_risk_count", 0)) for item in results)
    missed_risk_count = sum(int(item.get("missed_risk_count", 0)) for item in results)
    false_positive_risk_count = sum(int(item.get("false_positive_risk_count", 0)) for item in results)
    manual_review_gap_count = sum(int(item.get("manual_review_gap_count", 0)) for item in results)
    root_cause_summary: dict[str, int] = {}
    standardized_failure_summary: dict[str, dict[str, object]] = {}
    layer_failure_summary: dict[str, int] = {}
    comparison_failure_reason_summary: dict[str, int] = {}
    for item in results:
        failure_analysis = item.get("failure_analysis", {}) if isinstance(item.get("failure_analysis", {}), dict) else {}
        for reason in failure_analysis.get("root_causes", []):
            code = normalize_failure_code(reason)
            root_cause_summary[code] = root_cause_summary.get(code, 0) + 1
            meta = describe_failure_code(code)
            bucket = standardized_failure_summary.get(code)
            if not bucket:
                standardized_failure_summary[code] = {
                    **meta,
                    "count": 1,
                }
            else:
                bucket["count"] = int(bucket.get("count", 0)) + 1
        for layer in failure_analysis.get("layers", []):
            if not isinstance(layer, dict) or not layer.get("failed"):
                continue
            layer_name = str(layer.get("layer", "")).strip()
            if not layer_name:
                continue
            layer_failure_summary[layer_name] = layer_failure_summary.get(layer_name, 0) + 1
        for code in item.get("comparison_failure_reason_codes", []):
            normalized = str(code).strip()
            if normalized:
                comparison_failure_reason_summary[normalized] = comparison_failure_reason_summary.get(normalized, 0) + 1

    return {
        "sample_path": str(sample_path) if sample_path else "",
        "sample_count": len(results),
        "structure_required_total": structure_required_total,
        "structure_hit_count": structure_hit_count,
        "structure_hit_rate": (structure_hit_count / structure_required_total) if structure_required_total else 1.0,
        "structure_miss_count": max(structure_required_total - structure_hit_count, 0),
        "topic_coverage_total": topic_coverage_total,
        "topic_coverage_hit_count": topic_coverage_hit_count,
        "topic_coverage_hit_rate": (topic_coverage_hit_count / topic_coverage_total) if topic_coverage_total else 1.0,
        "topic_coverage_miss_count": max(topic_coverage_total - topic_coverage_hit_count, 0),
        "gold_risk_total": gold_risk_total,
        "matched_risk_count": matched_risk_count,
        "risk_hit_rate": (matched_risk_count / gold_risk_total) if gold_risk_total else 1.0,
        "missed_risk_count": missed_risk_count,
        "miss_rate": (missed_risk_count / gold_risk_total) if gold_risk_total else 0.0,
        "false_positive_risk_count": false_positive_risk_count,
        "manual_review_gap_count": manual_review_gap_count,
        "root_cause_summary": root_cause_summary,
        "standardized_failure_summary": standardized_failure_summary,
        "layer_failure_summary": layer_failure_summary,
        "comparison_failure_reason_summary": comparison_failure_reason_summary,
        "samples": results,
    }


def collect_outputs(results: list[dict]) -> dict[str, list[dict]]:
    matched_risks: list[dict] = []
    missed_risks: list[dict] = []
    false_positive_risks: list[dict] = []
    manual_review_gaps: list[dict] = []
    structure_gaps: list[dict] = []
    failure_analysis: list[dict] = []

    for item in results:
        sample_id = str(item.get("sample_id", "sample"))
        for matched in item.get("risks", {}).get("matched_risks", []):
            matched_risks.append({"sample_id": sample_id, **matched})
        for missed in item.get("risks", {}).get("missed_risks", []):
            missed_risks.append({"sample_id": sample_id, **missed})
        for fp in item.get("risks", {}).get("false_positive_risks", []):
            false_positive_risks.append({"sample_id": sample_id, **fp})
        for gap in item.get("risks", {}).get("manual_review_gaps", []):
            manual_review_gaps.append({"sample_id": sample_id, **gap})
        for gap in item.get("structure", {}).get("missed_sections", []):
            structure_gaps.append({"sample_id": sample_id, "type": "section", **gap})
        for gap in item.get("structure", {}).get("missed_topic_coverages", []):
            structure_gaps.append({"sample_id": sample_id, "type": "topic_coverage", **gap})
        analysis = item.get("failure_analysis", {})
        if isinstance(analysis, dict):
            failure_analysis.append({"sample_id": sample_id, **analysis})

    return {
        "matched_risks": matched_risks,
        "missed_risks": missed_risks,
        "false_positive_risks": false_positive_risks,
        "manual_review_gaps": manual_review_gaps,
        "structure_gaps": structure_gaps,
        "failure_analysis": failure_analysis,
    }


def build_markdown_report(summary: dict, outputs: dict[str, list[dict]]) -> str:
    lines = [
        "# V2 埋点回归失败报告",
        "",
        f"- 样本文件：`{summary.get('sample_path', '')}`",
        f"- 样本数：`{summary.get('sample_count', 0)}`",
        f"- 结构命中率：`{summary.get('structure_hit_count', 0)}/{summary.get('structure_required_total', 0)} = {float(summary.get('structure_hit_rate', 0.0)):.2%}`",
        f"- 专题覆盖命中率：`{summary.get('topic_coverage_hit_count', 0)}/{summary.get('topic_coverage_total', 0)} = {float(summary.get('topic_coverage_hit_rate', 0.0)):.2%}`",
        f"- 风险命中率：`{summary.get('matched_risk_count', 0)}/{summary.get('gold_risk_total', 0)} = {float(summary.get('risk_hit_rate', 0.0)):.2%}`",
        f"- 漏报率：`{summary.get('missed_risk_count', 0)}/{summary.get('gold_risk_total', 0)} = {float(summary.get('miss_rate', 0.0)):.2%}`",
        f"- 误报数：`{summary.get('false_positive_risk_count', 0)}`",
        f"- 人工复核差异数：`{summary.get('manual_review_gap_count', 0)}`",
        "",
        "## 根因汇总",
        "",
    ]
    if summary.get("standardized_failure_summary"):
        for code, item in sorted(summary["standardized_failure_summary"].items()):
            lines.extend(
                [
                    f"### {item['label']}",
                    "",
                    f"- 原因码：`{code}`",
                    f"- 所属层级：`{item['layer']}`",
                    f"- 分类：`{item['category']}`",
                    f"- 出现次数：`{item['count']}`",
                    f"- 建议修复方向：{item['suggestion']}",
                    "",
                ]
            )
    else:
        lines.extend(["- `未发现`", ""])

    lines.extend(["## 跨专题规则原因码", ""])
    if summary.get("comparison_failure_reason_summary"):
        for code, count in sorted(summary["comparison_failure_reason_summary"].items()):
            lines.append(f"- `{code}`：`{count}`")
        lines.append("")
    else:
        lines.extend(["- `未发现`", ""])

    lines.extend(["## 样本明细", ""])
    for sample in summary.get("samples", []):
        analysis = sample.get("failure_analysis", {}) if isinstance(sample.get("failure_analysis"), dict) else {}
        lines.extend(
            [
                f"### {sample.get('sample_id', 'sample')}",
                "",
                f"- 文档名称：`{sample.get('document_name', '')}`",
                f"- 主阻塞层：`{analysis.get('primary_blocker_layer', 'none')}`",
                f"- 失败摘要：{analysis.get('summary', '未发现')}",
                f"- 是否级联失败：`{analysis.get('cascaded_failure', False)}`",
            ]
        )
        breakpoint = sample.get("breakpoint", {}) if isinstance(sample.get("breakpoint"), dict) else {}
        if breakpoint:
            lines.extend(
                [
                    "#### 断点说明",
                    "",
                    f"- 当前失败点：`{breakpoint.get('current_failure_point', '未发现') or '未发现'}`",
                    f"- 已召回章节：`{breakpoint.get('recalled_sections', []) or '未发现'}`",
                    f"- 应命中专题：`{breakpoint.get('expected_topics', []) or '未发现'}`",
                    f"- 应命中风险：`{breakpoint.get('expected_risk_titles', []) or '未发现'}`",
                ]
            )
        if sample.get("comparison_failure_reason_codes"):
            lines.extend(
                [
                    "#### 跨专题规则原因码",
                    "",
                    f"- `{sample.get('comparison_failure_reason_codes', [])}`",
                ]
            )
        lines.extend(["", "#### 分层状态", ""])
        for layer in analysis.get("layers", []):
            if not isinstance(layer, dict):
                continue
            lines.append(
                f"- `{layer.get('label', layer.get('layer', 'unknown'))}`：failed=`{layer.get('failed', False)}`，count=`{layer.get('count', 0)}`，reasons=`{layer.get('reasons', [])}`"
            )
        lines.extend(["", "#### 根因与建议", ""])
        if analysis.get("root_cause_details"):
            for detail in analysis["root_cause_details"]:
                lines.append(
                    f"- `{detail.get('code', 'unknown_reason')}` / {detail.get('label', '未归类失败原因')}：{detail.get('suggestion', '需人工复核')}"
                )
        else:
            lines.append("- `未发现`")

        lines.extend(["", "#### 结构差异", ""])
        missed_sections = sample.get("structure", {}).get("missed_sections", [])
        missed_topic_coverages = sample.get("structure", {}).get("missed_topic_coverages", [])
        if missed_sections or missed_topic_coverages:
            for item in missed_sections:
                lines.append(
                    f"- 章节缺口：`{item.get('title', '未发现')}`，预期模块=`{item.get('expected_module', '未发现')}`，原因=`{item.get('reason', '未发现')}`"
                )
            for item in missed_topic_coverages:
                lines.append(
                    f"- coverage 缺口：topic=`{item.get('topic', 'unknown')}`，required_titles=`{item.get('required_titles', [])}`，required_modules=`{item.get('required_modules', [])}`，原因=`{item.get('reason', '未发现')}`"
                )
        else:
            lines.append("- `未发现`")

        lines.extend(["", "#### 风险差异", ""])
        missed_risks = sample.get("risks", {}).get("missed_risks", [])
        false_positive_risks = sample.get("risks", {}).get("false_positive_risks", [])
        manual_review_gaps = sample.get("risks", {}).get("manual_review_gaps", [])
        if missed_risks or false_positive_risks or manual_review_gaps:
            for item in missed_risks:
                lines.append(
                    f"- 漏报风险：`{item.get('title', '未发现')}`，类型=`{item.get('review_type', '未发现')}`，位置=`{item.get('source_location', '未发现')}`"
                )
            for item in false_positive_risks:
                lines.append(
                    f"- 误报风险：`{item.get('title', '未发现')}`，类型=`{item.get('review_type', '未发现')}`，位置=`{item.get('source_location', '未发现')}`"
                )
            for item in manual_review_gaps:
                lines.append(
                    f"- 人工复核差异：`{item.get('title', '未发现')}`，expected=`{item.get('expected_manual_review', False)}`，actual=`{item.get('actual_manual_review', False)}`，原因=`{item.get('reason', '未发现')}`"
                )
        else:
            lines.append("- `未发现`")
        lines.append("")

    lines.extend(["## 原始差异文件", ""])
    for key, items in outputs.items():
        lines.append(f"- `{key}`：`{len(items)}` 条")
    lines.append("")
    return "\n".join(lines)


def write_outputs(output_dir: Path, summary: dict, outputs: dict[str, list[dict]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "matched_risks.json").write_text(json.dumps(outputs["matched_risks"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "missed_risks.json").write_text(json.dumps(outputs["missed_risks"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "false_positive_risks.json").write_text(json.dumps(outputs["false_positive_risks"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "manual_review_gaps.json").write_text(json.dumps(outputs["manual_review_gaps"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "structure_gaps.json").write_text(json.dumps(outputs["structure_gaps"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "failure_analysis.json").write_text(json.dumps(outputs["failure_analysis"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "regression_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "regression_report.md").write_text(build_markdown_report(summary, outputs), encoding="utf-8")


def print_report(summary: dict, outputs: dict[str, list[dict]], *, as_markdown: bool = True) -> None:
    if as_markdown:
        print(build_markdown_report(summary, outputs))
        return

    print("V2 埋点回归评估结果")
    if summary.get("sample_path"):
        print(f"样本文件: {summary['sample_path']}")
    print(f"样本数: {summary['sample_count']}")
    print(
        f"结构命中率: {summary['structure_hit_count']}/{summary['structure_required_total']} = "
        f"{summary['structure_hit_rate']:.2%}"
    )
    print(
        f"专题覆盖命中率: {summary['topic_coverage_hit_count']}/{summary['topic_coverage_total']} = "
        f"{summary['topic_coverage_hit_rate']:.2%}"
    )
    print(
        f"风险命中率: {summary['matched_risk_count']}/{summary['gold_risk_total']} = "
        f"{summary['risk_hit_rate']:.2%}"
    )
    print(f"漏报数: {summary['missed_risk_count']}")
    print(f"误报数: {summary['false_positive_risk_count']}")
    print(f"人工复核差异数: {summary['manual_review_gap_count']}")
    if summary.get("layer_failure_summary"):
        print(f"分层失败分布: {summary['layer_failure_summary']}")
    if summary.get("root_cause_summary"):
        print(f"根因分布: {summary['root_cause_summary']}")
    if summary.get("standardized_failure_summary"):
        print(f"标准化失败类型: {summary['standardized_failure_summary']}")


def _evaluate_real_case(gold_path: Path, result_dir: Path) -> tuple[list[dict], Path]:
    gold_payload = json.loads(gold_path.read_text(encoding="utf-8"))
    if not isinstance(gold_payload, dict):
        raise ValueError("gold 文件必须是对象。")
    sample = {
        "sample_id": str(gold_payload.get("sample_id", result_dir.name)),
        "document_name": str(gold_payload.get("document_name", result_dir.name)),
        "gold": gold_payload.get("gold", {}),
        "system": load_result_payload(result_dir),
    }
    return [evaluate_sample(sample)], gold_path


def main() -> int:
    parser = argparse.ArgumentParser(description="对 V2 结构层、专题层、汇总层结果执行埋点回归比对。")
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLE_PATH, help="回归样本 JSON 路径")
    parser.add_argument("--dataset-root", type=Path, default=None, help=f"固定评估数据集目录，默认 {DEFAULT_EVAL_ROOT}")
    parser.add_argument("--gold", type=Path, help="单个真实案例的金标 JSON 路径")
    parser.add_argument("--result-dir", type=Path, help="单个真实案例的 V2 结果目录")
    parser.add_argument("--output-dir", type=Path, help="回归差异输出目录")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON 汇总结果")
    parser.add_argument("--text", action="store_true", help="输出精简文本摘要，默认输出 Markdown 报告")
    args = parser.parse_args()

    if args.gold and args.result_dir:
        results, summary_path = _evaluate_real_case(args.gold, args.result_dir)
    else:
        sample_path = resolve_v2_eval_sample_path("regression", samples_path=args.samples, dataset_root=args.dataset_root)
        results = [evaluate_sample(sample) for sample in load_samples(sample_path)]
        summary_path = sample_path

    summary = build_summary(results, summary_path)
    outputs = collect_outputs(results)

    if args.output_dir:
        write_outputs(args.output_dir, summary, outputs)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print_report(summary, outputs, as_markdown=not args.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
