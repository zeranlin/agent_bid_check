from __future__ import annotations

from pathlib import Path

from app.pipelines.v2.feedback_attribution import (
    attribute_feedback_batch,
    attribute_feedback_record,
    load_feedback_attribution_registry,
)


ROOT = Path(__file__).resolve().parents[1]


def _snapshot_with_conflict(*, include_conflict_fields: bool = True) -> dict:
    item = {
        "problem_id": "problem-conflict-001",
        "title": "拒绝进口 vs 外标/国外部件引用矛盾风险",
        "family_key": "import_consistency",
        "problem_kind": "conflict",
        "conflict_type": "import_consistency_conflict",
        "evidence_ids": ["ev-1", "ev-2"],
        "source_locations": ["第1章", "第3章"],
        "final_problem_resolution": {"target_layer": "formal_risks"},
    }
    if include_conflict_fields:
        item.update(
            {
                "left_side": {"problem_id": "problem-left"},
                "right_side": {"problem_id": "problem-right"},
                "conflict_reason": {"why_conflict": "政策口径与技术条款冲突"},
                "conflict_evidence_links": [{"left_evidence_id": "ev-1", "right_evidence_id": "ev-2"}],
            }
        )
    return {
        "final_risks": {
            "formal_risks": [item],
            "pending_review_items": [],
            "excluded_risks": [],
        },
        "problem_trace_summary": [
            {
                "problem_id": "problem-conflict-001",
                "title": "拒绝进口 vs 外标/国外部件引用矛盾风险",
                "family_key": "import_consistency",
                "problem_kind": "conflict",
                "conflict_type": "import_consistency_conflict",
                "left_side": {"problem_id": "problem-left"},
                "right_side": {"problem_id": "problem-right"},
                "conflict_reason": {"why_conflict": "政策口径与技术条款冲突"},
            }
        ],
    }


def test_attribute_feedback_record_maps_template_misreport_to_evidence_layer() -> None:
    decision = attribute_feedback_record(
        {
            "feedback_id": "FB-GR2-001",
            "feedback_type": "误报",
            "feedback_title": "模板/留白被误报 formal",
            "expected_behavior": "模板条款不应作为正文硬证据进入正式风险",
            "actual_behavior": "模板留白条款进入 formal",
            "signals": ["template_clause_as_body", "placeholder_clause_as_body"],
        }
    )

    assert decision["root_cause_layer"] == "evidence_layer"
    assert decision["suggested_task_type"] == "证据层补强任务"
    assert decision["disposition"] == "新建整改任务"


def test_attribute_feedback_record_maps_overmerge_to_problem_layer() -> None:
    decision = attribute_feedback_record(
        {
            "feedback_id": "FB-GR2-002",
            "feedback_type": "标题错误",
            "feedback_title": "样品/验收/商务问题误并",
            "expected_behavior": "相邻但独立的问题应拆分保留",
            "actual_behavior": "样品、验收、商务被误收成一个问题",
            "signals": ["wrong_merge", "cross_topic_overmerge"],
        }
    )

    assert decision["root_cause_layer"] == "problem_layer"
    assert decision["suggested_task_type"] == "问题层归并整改任务"


def test_attribute_feedback_record_maps_layer_mismatch_to_risk_admission() -> None:
    decision = attribute_feedback_record(
        {
            "feedback_id": "FB-GR2-003",
            "feedback_type": "层级错误",
            "feedback_title": "待补证项被抬入 formal",
            "expected_behavior": "证据不足项应进入 pending",
            "actual_behavior": "结果进入 formal",
            "expected_layer": "pending_review_items",
            "actual_layer": "formal_risks",
        }
    )

    assert decision["root_cause_layer"] == "risk_admission"
    assert decision["suggested_task_type"] == "准入层门禁整改任务"


def test_attribute_feedback_record_maps_conflict_render_gap_to_publish_layer() -> None:
    decision = attribute_feedback_record(
        {
            "feedback_id": "FB-GR2-004",
            "feedback_type": "展示错误",
            "feedback_title": "Web 缺少 conflict 左右证据",
            "expected_behavior": "冲突问题应展示 left/right/conflict_reason",
            "actual_behavior": "页面只有标题，没有冲突结构化信息",
            "problem_id": "problem-conflict-001",
        },
        final_snapshot=_snapshot_with_conflict(include_conflict_fields=False),
    )

    assert decision["root_cause_layer"] == "publish_layer"
    assert decision["suggested_task_type"] == "发布层渲染修复任务"


def test_attribute_feedback_record_maps_missing_rule_coverage_to_rule_layer() -> None:
    decision = attribute_feedback_record(
        {
            "feedback_id": "FB-GR2-005",
            "feedback_type": "漏报",
            "feedback_title": "赠送风险漏报",
            "expected_behavior": "赠送非项目物资评分应被识别并输出",
            "actual_behavior": "当前结果未报出",
            "signals": ["rule_missing", "registry_gap"],
            "expected_rule_id": "R-008",
        },
        final_snapshot={"final_risks": {"formal_risks": [], "pending_review_items": [], "excluded_risks": []}},
    )

    assert decision["root_cause_layer"] == "rule_layer"
    assert decision["disposition"] == "标记为规则补充"
    assert decision["suggested_task_type"] == "规则纳管补充任务"


def test_attribute_feedback_record_has_unknown_fallback() -> None:
    decision = attribute_feedback_record(
        {
            "feedback_id": "FB-GR2-006",
            "feedback_type": "追溯缺失",
            "feedback_title": "客户称结果不对但未提供定位",
            "expected_behavior": "需要能回看具体问题对象",
            "actual_behavior": "仅收到笼统投诉",
        }
    )

    assert decision["root_cause_layer"] == "unknown"
    assert decision["disposition"] == "并入已有任务"
    assert decision["suggested_task_type"] == "人工复核分诊任务"


def test_attribute_feedback_batch_does_not_default_everything_to_rule_layer() -> None:
    tracker = load_feedback_attribution_registry(ROOT / "docs" / "trackers" / "v2-feedback-attribution-ledger.yaml")

    decisions = attribute_feedback_batch(tracker)
    layers = {item["root_cause_layer"] for item in decisions}

    assert {"evidence_layer", "problem_layer", "risk_admission", "publish_layer", "rule_layer", "unknown"}.issubset(layers)
    assert len([item for item in decisions if item["root_cause_layer"] == "rule_layer"]) < len(decisions)


def test_feedback_attribution_tracker_contains_required_fields_and_samples() -> None:
    tracker = load_feedback_attribution_registry(ROOT / "docs" / "trackers" / "v2-feedback-attribution-ledger.yaml")

    assert tracker["ledger_id"] == "V2-FEEDBACK-ATTRIBUTION-001"
    assert tracker["single_source"] == "docs/trackers"
    assert len(tracker["feedback_cases"]) >= 6
    assert "root_cause_layer" in tracker["fields_definition"]
    assert "disposition" in tracker["fields_definition"]
    assert "suggested_task_type" in tracker["fields_definition"]
