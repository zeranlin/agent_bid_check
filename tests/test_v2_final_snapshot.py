from __future__ import annotations

import json
from pathlib import Path

from app.common.schemas import RiskPoint
from app.pipelines.v2.final_snapshot import (
    build_v2_final_snapshot,
    project_final_output_from_snapshot,
    render_v2_markdown_from_snapshot,
)
from app.pipelines.v2.output_governance import govern_comparison_artifact
from app.pipelines.v2.problem_layer import build_problem_layer
from app.pipelines.v2.risk_admission import admit_problem_result
from app.pipelines.v2.schemas import ComparisonArtifact, MergedRiskCluster, TopicReviewArtifact, V2ReviewArtifacts, V2StageArtifact
from app.pipelines.v2.service import save_review_artifacts_v2
from app.web.v2_app import create_app, list_recent_runs, load_result_by_run_id


def _build_standard_comparison() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="cluster-1",
                title="将项目验收方案纳入评审因素，违反评审规则合规性要求",
                severity="高风险",
                review_type="评分因素合规性审查",
                source_locations=["评分条款：第二章 评审标准"],
                source_excerpts=["验收方案优的得满分。"],
                risk_judgment=["验收方案被直接作为评分条件。"],
                legal_basis=["评审因素应与采购需求和合同履约相关。"],
                rectification=["删除与验收方案直接挂钩的评分条件。"],
                topics=["scoring"],
                source_rules=["compare_rule:R-003"],
            )
        ],
        metadata={
            "pending_review_items": [
                {
                    "title": "节能环保产品政策条款缺失",
                    "severity": "需人工复核",
                    "review_type": "政策条款复核",
                    "topic": "政策条款",
                    "source_location": "政策章节",
                    "source_excerpt": "未见明确节能环保政策落实条款。",
                    "reason": "当前仅能确认政策章节召回不足，先转待补证。",
                }
            ]
        },
    )


def _build_conflict_comparison() -> ComparisonArtifact:
    return ComparisonArtifact(
        clusters=[
            MergedRiskCluster(
                cluster_id="acceptance-policy",
                title="评分规则明确不得将验收方案作为评审因素",
                severity="中风险",
                review_type="评分规则一致性审查",
                source_locations=["评分规则总则"],
                source_excerpts=["评审因素不得包含验收方案、付款方式等与评审无关内容。"],
                risk_judgment=["评分规则已明确禁止。"],
                legal_basis=["评审因素应与采购需求和履约相关。"],
                rectification=["保持评分规则与评分细则一致。"],
                topics=["policy"],
                source_rules=["topic"],
            ),
            MergedRiskCluster(
                cluster_id="acceptance-scoring",
                title="将项目验收方案纳入评审因素，违反评审规则合规性要求",
                severity="高风险",
                review_type="评分因素合规性审查",
                source_locations=["评分细则：验收方案评分"],
                source_excerpts=["验收方案优的得满分。"],
                risk_judgment=["评分细则实际按验收方案打分。"],
                legal_basis=["评审因素应与采购需求和履约相关。"],
                rectification=["删除与验收方案直接挂钩的评分条件。"],
                topics=["scoring"],
                source_rules=["compare_rule:R-003"],
            ),
        ]
    )


def _build_pipeline_artifacts(document_name: str, comparison: ComparisonArtifact) -> tuple[
    V2StageArtifact,
    V2StageArtifact,
    list[TopicReviewArtifact],
    object,
    object,
    object,
]:
    baseline = V2StageArtifact(name="baseline", content=f"# 招标文件合规审查结果\n\n审查对象：`{document_name}`\n")
    structure = V2StageArtifact(
        name="structure",
        metadata={
            "section_count": 6,
            "evidence_bundle_count": 3,
            "evidence_object_count": 5,
        },
    )
    topics = [
        TopicReviewArtifact(
            topic="scoring",
            summary="评分专题",
            risk_points=[
                RiskPoint(
                    title="旧专题标题",
                    severity="高风险",
                    review_type="旧专题输出",
                    source_location="旧位置",
                    source_excerpt="旧摘录",
                    risk_judgment=["旧判断"],
                    legal_basis=["旧依据"],
                    rectification=["旧建议"],
                )
            ],
            metadata={"selected_sections": [{"title": "评分条款"}]},
        ),
        TopicReviewArtifact(topic="policy", summary="政策专题", risk_points=[], metadata={"selected_sections": [{"title": "政策条款"}]}),
    ]
    governance = govern_comparison_artifact(document_name, comparison)
    problems = build_problem_layer(document_name, governance)
    admission = admit_problem_result(document_name, comparison, problems, governance)
    return baseline, structure, topics, governance, problems, admission


def test_build_v2_final_snapshot_keeps_standard_and_conflict_problem_fields() -> None:
    standard_baseline, standard_structure, standard_topics, standard_governance, standard_problems, standard_admission = _build_pipeline_artifacts(
        "standard.docx",
        _build_standard_comparison(),
    )
    conflict_baseline, conflict_structure, conflict_topics, conflict_governance, conflict_problems, conflict_admission = _build_pipeline_artifacts(
        "conflict.docx",
        _build_conflict_comparison(),
    )

    standard_snapshot = build_v2_final_snapshot(
        "standard.docx",
        standard_baseline,
        standard_structure,
        standard_topics,
        comparison=_build_standard_comparison(),
        governance=standard_governance,
        problems=standard_problems,
        admission=standard_admission,
        generated_at="2026-04-10T10:00:00",
    )
    conflict_snapshot = build_v2_final_snapshot(
        "conflict.docx",
        conflict_baseline,
        conflict_structure,
        conflict_topics,
        comparison=_build_conflict_comparison(),
        governance=conflict_governance,
        problems=conflict_problems,
        admission=conflict_admission,
        generated_at="2026-04-10T10:05:00",
    )

    standard_item = standard_snapshot["final_risks"]["formal_risks"][0]
    assert standard_snapshot["snapshot_version"]
    assert standard_snapshot["run_metadata"]["document_name"] == "standard.docx"
    assert standard_item["problem_id"]
    assert standard_item["problem_kind"] == "standard"
    assert standard_item["evidence_ids"] == standard_item["evidence_ids"]
    assert standard_item["rule_ids"]
    assert standard_item["source_locations"]
    assert standard_item["source_excerpts"]
    assert isinstance(standard_item["final_problem_resolution"], dict)

    conflict_item = conflict_snapshot["final_risks"]["formal_risks"][0]
    assert conflict_item["problem_kind"] == "conflict"
    assert conflict_item["conflict_type"] == "acceptance_plan_scoring_conflict"
    assert conflict_item["left_side"]["problem_id"]
    assert conflict_item["right_side"]["problem_id"]
    assert conflict_item["conflict_reason"]["why_conflict"]
    assert len(conflict_item["conflict_evidence_links"]) == 2


def test_project_final_output_from_snapshot_blocks_legacy_bypass_fields() -> None:
    baseline, structure, topics, governance, problems, admission = _build_pipeline_artifacts(
        "standard.docx",
        _build_standard_comparison(),
    )
    snapshot = build_v2_final_snapshot(
        "standard.docx",
        baseline,
        structure,
        topics,
        comparison=_build_standard_comparison(),
        governance=governance,
        problems=problems,
        admission=admission,
        generated_at="2026-04-10T10:10:00",
    )

    final_output = project_final_output_from_snapshot(snapshot)
    risk_item = final_output["formal_risks"][0]

    assert risk_item["title"] == "将项目验收方案纳入评审因素，违反评审规则合规性要求"
    assert "problem_trace" not in risk_item
    assert "compare_source_bucket" not in risk_item
    assert final_output["summary"]["high_risk_titles"] == ["将项目验收方案纳入评审因素，违反评审规则合规性要求"]


def test_render_v2_markdown_from_snapshot_uses_snapshot_as_single_source() -> None:
    baseline, structure, topics, governance, problems, admission = _build_pipeline_artifacts(
        "standard.docx",
        _build_standard_comparison(),
    )
    snapshot = build_v2_final_snapshot(
        "standard.docx",
        baseline,
        structure,
        topics,
        comparison=_build_standard_comparison(),
        governance=governance,
        problems=problems,
        admission=admission,
        generated_at="2026-04-10T10:20:00",
    )

    markdown = render_v2_markdown_from_snapshot(snapshot)

    assert "## 风险点1：将项目验收方案纳入评审因素，违反评审规则合规性要求" in markdown
    assert "旧专题标题" not in markdown
    assert "## 主要依据汇总" in markdown


def test_render_v2_markdown_from_snapshot_renders_excluded_summary_without_promoting_to_main_list() -> None:
    baseline, structure, topics, governance, problems, admission = _build_pipeline_artifacts(
        "standard.docx",
        _build_standard_comparison(),
    )
    snapshot = build_v2_final_snapshot(
        "standard.docx",
        baseline,
        structure,
        topics,
        comparison=_build_standard_comparison(),
        governance=governance,
        problems=problems,
        admission=admission,
        generated_at="2026-04-10T10:20:00",
    )
    snapshot["final_risks"]["excluded_risks"] = [
        {
            "title": "政策依据引用不完整，存在表述截断风险",
            "admission_reason": "弱提示型问题已被 pending gate 拦截，不进入用户可见待补证列表。",
        }
    ]
    snapshot["summary"]["excluded_count"] = 1
    snapshot["summary"]["excluded_titles"] = ["政策依据引用不完整，存在表述截断风险"]

    markdown = render_v2_markdown_from_snapshot(snapshot)

    assert "## 已排除项摘要" in markdown
    assert "- 已排除数量：1" in markdown
    assert "### 复核项1：政策依据引用不完整，存在表述截断风险" not in markdown
    assert "政策依据引用不完整，存在表述截断风险" in markdown


def test_build_v2_final_snapshot_hides_missing_user_visible_evidence_items_from_all_user_visible_layers() -> None:
    baseline, structure, topics, governance, problems, admission = _build_pipeline_artifacts(
        "standard.docx",
        _build_standard_comparison(),
    )
    admission.excluded_risks = [
        admission.excluded_risks[0] if admission.excluded_risks else None,
    ]
    admission.excluded_risks = [item for item in admission.excluded_risks if item is not None]
    if not admission.excluded_risks:
        from app.pipelines.v2.risk_admission.schemas import AdmissionCandidate, AdmissionDecision

        hidden = AdmissionCandidate(
            rule_id="topic::missing-visible",
            risk_family="missing-visible",
            title="违约责任及质保期条款缺失",
            review_type="商务条款审查",
            severity="中风险",
            evidence_kind="unknown",
            source_type="topic_inference",
            source_locations=["未在当前证据片段中找到"],
            source_excerpts=["无"],
            extras={},
        )
        admission.excluded_risks = [hidden]
        admission.decisions[hidden.rule_id] = AdmissionDecision(
            target_layer="excluded_risks",
            admission_reason="当前问题缺少有效原文位置或摘录，仅保留内部 trace，不再作为对外待补证项展示。",
            evidence_kind="unknown",
            source_type="topic_inference",
            pending_gate_reason_code="missing_user_visible_evidence",
            pending_gate_reason="当前问题缺少有效原文位置或摘录，仅保留内部 trace，不再作为对外待补证项展示。",
        )
    else:
        hidden = admission.excluded_risks[0]
        hidden.title = "违约责任及质保期条款缺失"
        hidden.source_locations = ["未在当前证据片段中找到"]
        hidden.source_excerpts = ["无"]
        admission.decisions[hidden.rule_id].pending_gate_reason_code = "missing_user_visible_evidence"
        admission.decisions[hidden.rule_id].pending_gate_reason = "当前问题缺少有效原文位置或摘录，仅保留内部 trace，不再作为对外待补证项展示。"
        admission.decisions[hidden.rule_id].admission_reason = "当前问题缺少有效原文位置或摘录，仅保留内部 trace，不再作为对外待补证项展示。"

    snapshot = build_v2_final_snapshot(
        "standard.docx",
        baseline,
        structure,
        topics,
        comparison=_build_standard_comparison(),
        governance=governance,
        problems=problems,
        admission=admission,
        generated_at="2026-04-10T10:21:00",
    )
    markdown = render_v2_markdown_from_snapshot(snapshot)
    final_output = project_final_output_from_snapshot(snapshot)

    assert "违约责任及质保期条款缺失" not in {item["title"] for item in snapshot["final_risks"]["excluded_risks"]}
    assert "违约责任及质保期条款缺失" not in snapshot["summary"]["excluded_titles"]
    assert "违约责任及质保期条款缺失" not in markdown
    assert "违约责任及质保期条款缺失" not in {item["title"] for item in final_output["excluded_risks"]}


def test_save_review_artifacts_v2_writes_final_snapshot_and_derived_output(tmp_path: Path) -> None:
    comparison = _build_standard_comparison()
    baseline, structure, topics, governance, problems, admission = _build_pipeline_artifacts("standard.docx", comparison)
    snapshot = build_v2_final_snapshot(
        "standard.docx",
        baseline,
        structure,
        topics,
        comparison=comparison,
        governance=governance,
        problems=problems,
        admission=admission,
        generated_at="2026-04-10T10:30:00",
    )
    artifacts = V2ReviewArtifacts(
        extracted_text="正文",
        baseline=baseline,
        structure=structure,
        topics=topics,
        final_markdown=render_v2_markdown_from_snapshot(snapshot),
        comparison=comparison,
        governance=governance,
        problems=problems,
        admission=admission,
    )

    save_review_artifacts_v2(artifacts, tmp_path)

    saved_snapshot = json.loads((tmp_path / "final_snapshot.json").read_text(encoding="utf-8"))
    saved_output = json.loads((tmp_path / "final_output.json").read_text(encoding="utf-8"))
    assert saved_snapshot["snapshot_version"]
    assert saved_output["formal_risks"][0]["title"] == saved_snapshot["final_risks"]["formal_risks"][0]["title"]
    assert (tmp_path / "final_review.md").read_text(encoding="utf-8").startswith("# 招标文件合规审查结果")


def test_load_result_by_run_id_and_history_prefer_final_snapshot(tmp_path: Path, monkeypatch) -> None:
    comparison = _build_conflict_comparison()
    baseline, structure, topics, governance, problems, admission = _build_pipeline_artifacts("conflict.docx", comparison)
    snapshot = build_v2_final_snapshot(
        "conflict.docx",
        baseline,
        structure,
        topics,
        comparison=comparison,
        governance=governance,
        problems=problems,
        admission=admission,
        generated_at="2026-04-10T10:40:00",
    )

    run_dir = tmp_path / "snapshot-run"
    run_dir.mkdir()
    (run_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": "snapshot-run",
                "created_at": "2026-04-10T10:40:00",
                "original_filename": "conflict.docx",
                "topic_mode": "mature",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "final_snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "final_output.json").write_text(
        json.dumps(
            {
                "formal_risks": [
                    {
                        "title": "旧旁路标题",
                        "severity": "高风险",
                        "review_type": "旧类型",
                        "source_location": "旧位置",
                        "source_excerpt": "旧摘录",
                        "risk_judgment": ["旧判断"],
                        "legal_basis": ["旧依据"],
                        "rectification": ["旧建议"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_dir / "review.md").write_text("# 旧报告\n\n## 风险点1：旧旁路标题\n", encoding="utf-8")
    (run_dir / "final_review.md").write_text("# 旧终稿\n\n## 风险点1：旧旁路标题\n", encoding="utf-8")
    (run_dir / "comparison.json").write_text(json.dumps(comparison.to_dict(), ensure_ascii=False), encoding="utf-8")
    (run_dir / "v2_overview.json").write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr("app.web.v2_app.find_run_dir", lambda run_id: run_dir if run_id == "snapshot-run" else None)
    monkeypatch.setattr("app.web.v2_app.iter_result_roots", lambda: [tmp_path], raising=False)

    app = create_app()
    with app.test_request_context():
        result = load_result_by_run_id("snapshot-run")
        runs = list_recent_runs()

    assert result is not None
    assert result["review_view"]["all_cards"][0]["title"] == "评分规则禁止将验收方案作为评审因素，但评分项实际纳入验收方案"
    assert result["final_output"]["formal_risks"][0]["title"] == "评分规则禁止将验收方案作为评审因素，但评分项实际纳入验收方案"
    assert result["review_final_markdown"] == render_v2_markdown_from_snapshot(snapshot)
    assert runs[0]["high"] == 1
    assert runs[0]["view_url"].endswith("/review-plus/history/snapshot-run")
