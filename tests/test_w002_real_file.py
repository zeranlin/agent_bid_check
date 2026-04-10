from __future__ import annotations

import json
from pathlib import Path

from app.common.file_extract import extract_text
from app.common.markdown_utils import parse_review_markdown
from app.common.schemas import RiskPoint
from app.config import ReviewSettings
from app.pipelines.v2.assembler import assemble_v2_report
from app.pipelines.v2.assembler import build_v2_final_output
from app.pipelines.v2.compare import compare_review_artifacts, comparison_to_json
from app.pipelines.v2.evidence import build_evidence_map
from app.pipelines.v2.schemas import TopicReviewArtifact, V2StageArtifact
from app.pipelines.v2.structure import build_structure_map
from app.pipelines.v2.topic_review import (
    CN_STANDARD_REF_RE,
    FOREIGN_STANDARD_REF_RE,
    GB_NON_T_REF_RE,
    _build_structured_signals,
)
from app.pipelines.v2.topics import get_topic_definition
from app.web.v2_app import build_review_view, build_review_view_from_final_output


REAL_FILE = Path("data/uploads/v2/20260401-124322-9d7d80-SZDL2025000495-A.docx")
R008_REAL_FILE = Path("data/uploads/v2/20260330-205046-b7fabf-SZDL2025000495-A-0323.docx")
R004_REAL_FILE = Path("data/uploads/v2/20260330-205046-b7fabf-SZDL2025000495-A-0323.docx")
REAL_0330_SOURCE_FILE = Path("/Users/linzeran/code/2026-zn/test_target/zf/埋点测试案例和结果/[SZDL2025000495-A-0330]柴油发电机组及相关配套机电设备采购及安装项目.docx")
W005_SOURCE_RUN = Path("data/results/v2/20260402-100336-szdl2025000495a-mature-review/topic_reviews")
W006_SOURCE_RUN = Path("data/results/v2/20260402-120909-w005f-default-entry-rerun/topic_reviews")
G005_SOURCE_RUN = Path("data/results/v2/20260402-g004-feedback-loop-rerun/topic_reviews")
CURRENT_REAL_RUN = Path("data/results/v2/20260403-diesel-rerun/topic_reviews")
W007_SOURCE_RESULT = Path("data/results/v2/20260407-140828-232a1471")
REAL_0330_RESULT = Path("data/results/v2/20260408-szdl0330-verify")


def _build_settings() -> ReviewSettings:
    return ReviewSettings()


def _build_topics_for_file(real_file: Path) -> tuple[V2StageArtifact, V2StageArtifact, list[TopicReviewArtifact]]:
    text = extract_text(real_file)
    structure = build_structure_map(real_file, text, _build_settings(), use_llm=False)
    evidence = build_evidence_map(real_file.name, structure, topic_mode="mature")
    topics: list[TopicReviewArtifact] = []
    for topic_key in ("policy", "scoring", "technical_standard", "acceptance"):
        bundle = evidence.metadata["topic_evidence_bundles"][topic_key]
        sections = [section for section in bundle.get("sections", []) if isinstance(section, dict)]
        signal_sections = sections
        if topic_key == "technical_standard":
            primary_ids = {str(item).strip() for item in bundle.get("primary_section_ids", []) if str(item).strip()}
            primary_sections = [
                section
                for section in sections
                if f"{section.get('start_line', 0)}-{section.get('end_line', 0)}" in primary_ids
            ]
            supplemental_sections = []
            for section in sections:
                section_id = f"{section.get('start_line', 0)}-{section.get('end_line', 0)}"
                if section_id in primary_ids:
                    continue
                text_blob = "\n".join(
                    [
                        str(section.get("title", "")).strip(),
                        str(section.get("excerpt", "")).strip(),
                        str(section.get("body", "")).strip(),
                    ]
                )
                if FOREIGN_STANDARD_REF_RE.search(text_blob) or CN_STANDARD_REF_RE.search(text_blob) or GB_NON_T_REF_RE.search(text_blob):
                    supplemental_sections.append(section)
            signal_sections = primary_sections + supplemental_sections[:2]
        structured_signals = _build_structured_signals(type("Definition", (), {"key": topic_key})(), signal_sections)
        topics.append(
            TopicReviewArtifact(
                topic=topic_key,
                summary=f"{topic_key} real-file replay",
                risk_points=[],
                need_manual_review=False,
                coverage_note="真实文件回放测试",
                metadata={
                    "selected_sections": [
                        {
                            "title": section.get("title", ""),
                            "start_line": section.get("start_line"),
                            "end_line": section.get("end_line"),
                            "module": section.get("module", ""),
                        }
                        for section in sections
                    ],
                    "missing_evidence": ["未发现"],
                    "structured_signals": structured_signals,
                },
            )
        )
    baseline = V2StageArtifact(
        name="baseline",
        content=f"# 招标文件合规审查结果\n\n审查对象：`{real_file.name}`\n",
    )
    return structure, evidence, [topic for topic in topics]


def _build_real_file_topics() -> tuple[V2StageArtifact, V2StageArtifact, list[TopicReviewArtifact]]:
    return _build_topics_for_file(REAL_FILE)


def _build_r008_real_file_topics() -> tuple[V2StageArtifact, V2StageArtifact, list[TopicReviewArtifact]]:
    return _build_topics_for_file(R008_REAL_FILE)


def _build_r004_real_file_topics() -> tuple[V2StageArtifact, V2StageArtifact, list[TopicReviewArtifact]]:
    return _build_topics_for_file(R004_REAL_FILE)


def _build_real_file_replay_topics() -> tuple[V2StageArtifact, V2StageArtifact, list[TopicReviewArtifact]]:
    text = extract_text(REAL_FILE)
    structure = build_structure_map(REAL_FILE, text, _build_settings(), use_llm=False)
    evidence = build_evidence_map(REAL_FILE.name, structure, topic_mode="mature")
    source_run = Path("data/results/v2/20260401-173633-92447616/topic_reviews")
    topics: list[TopicReviewArtifact] = []
    for path in sorted(source_run.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        topic_key = payload.get("topic", path.stem)
        definition = get_topic_definition(topic_key)
        bundle = evidence.metadata["topic_evidence_bundles"][topic_key]
        sections = [section for section in bundle.get("sections", []) if isinstance(section, dict)]
        metadata = {
            **dict(payload.get("metadata", {}) or {}),
            "selected_sections": [
                {
                    "title": section.get("title", ""),
                    "start_line": section.get("start_line"),
                    "end_line": section.get("end_line"),
                    "module": section.get("module", ""),
                }
                for section in sections
            ],
            "structured_signals": _build_structured_signals(definition, sections),
            "evidence_bundle": bundle,
            "topic_coverage": evidence.metadata["topic_coverages"][topic_key],
        }
        topics.append(
            TopicReviewArtifact(
                topic=topic_key,
                summary=payload.get("summary", ""),
                risk_points=[RiskPoint(**risk) for risk in payload.get("risk_points", [])],
                need_manual_review=payload.get("need_manual_review", False),
                coverage_note=payload.get("coverage_note", ""),
                metadata=metadata,
            )
        )
    return structure, evidence, topics


def _build_w005_source_topics() -> tuple[V2StageArtifact, V2StageArtifact, list[TopicReviewArtifact]]:
    text = extract_text(REAL_FILE)
    structure = build_structure_map(REAL_FILE, text, _build_settings(), use_llm=False)
    evidence = build_evidence_map(REAL_FILE.name, structure, topic_mode="mature")
    bundles = evidence.metadata["topic_evidence_bundles"]
    coverages = evidence.metadata["topic_coverages"]
    topics: list[TopicReviewArtifact] = []
    evidence_aliases = {
        "qualification": ["qualification"],
        "scoring": ["scoring"],
        "technical": ["technical_standard"],
        "contract": ["contract_payment", "acceptance"],
    }
    for path in sorted(W005_SOURCE_RUN.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        topic_key = payload.get("topic", path.stem)
        bundle_sections: list[dict] = []
        topic_coverage = {}
        for alias_key in evidence_aliases.get(topic_key, [topic_key]):
            bundle = bundles.get(alias_key, {})
            bundle_sections.extend(bundle.get("sections", []))
            if not topic_coverage and alias_key in coverages:
                topic_coverage = coverages.get(alias_key, {})
        selected_sections = [
            {
                "title": section.get("title", ""),
                "start_line": section.get("start_line"),
                "end_line": section.get("end_line"),
                "module": section.get("module", ""),
            }
            for section in bundle_sections
            if isinstance(section, dict)
        ]
        metadata = {
            **dict(payload.get("metadata", {}) or {}),
            "selected_sections": selected_sections,
            "evidence_bundle": {"sections": bundle_sections},
            "topic_coverage": topic_coverage,
        }
        topics.append(
            TopicReviewArtifact(
                topic=topic_key,
                summary=payload.get("summary", ""),
                risk_points=[RiskPoint(**risk) for risk in payload.get("risk_points", [])],
                need_manual_review=payload.get("need_manual_review", False),
                coverage_note=payload.get("coverage_note", ""),
                metadata=metadata,
            )
        )
    for synthetic_topic_key in ("policy",):
        bundle = bundles.get(synthetic_topic_key, {})
        coverage = coverages.get(synthetic_topic_key, {})
        sections = bundle.get("sections", [])
        topics.append(
            TopicReviewArtifact(
                topic=synthetic_topic_key,
                summary=f"{synthetic_topic_key} synthetic replay",
                risk_points=[],
                need_manual_review=False,
                coverage_note="真实文件当前结构召回补充",
                metadata={
                    "selected_sections": [
                        {
                            "title": section.get("title", ""),
                            "start_line": section.get("start_line"),
                            "end_line": section.get("end_line"),
                            "module": section.get("module", ""),
                        }
                        for section in sections
                        if isinstance(section, dict)
                    ],
                    "missing_evidence": ["未发现"],
                    "evidence_bundle": bundle,
                    "topic_coverage": coverage,
                },
            )
        )
    baseline = V2StageArtifact(
        name="baseline",
        content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_FILE.name}`\n",
    )
    return structure, evidence, topics


def _build_w006_source_topics() -> tuple[V2StageArtifact, V2StageArtifact, list[TopicReviewArtifact]]:
    text = extract_text(REAL_FILE)
    structure = build_structure_map(REAL_FILE, text, _build_settings(), use_llm=False)
    evidence = build_evidence_map(REAL_FILE.name, structure, topic_mode="mature")
    topics: list[TopicReviewArtifact] = []
    for path in sorted(W006_SOURCE_RUN.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        topics.append(
            TopicReviewArtifact(
                topic=payload.get("topic", path.stem),
                summary=payload.get("summary", ""),
                risk_points=[RiskPoint(**risk) for risk in payload.get("risk_points", [])],
                need_manual_review=payload.get("need_manual_review", False),
                coverage_note=payload.get("coverage_note", ""),
                metadata=dict(payload.get("metadata", {}) or {}),
            )
        )
    baseline = V2StageArtifact(
        name="baseline",
        content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_FILE.name}`\n",
    )
    return structure, evidence, topics


def _build_feedback_source_topics(source_run: Path) -> tuple[V2StageArtifact, V2StageArtifact, list[TopicReviewArtifact]]:
    text = extract_text(REAL_FILE)
    structure = build_structure_map(REAL_FILE, text, _build_settings(), use_llm=False)
    evidence = build_evidence_map(REAL_FILE.name, structure, topic_mode="mature")
    bundles = evidence.metadata["topic_evidence_bundles"]
    coverages = evidence.metadata["topic_coverages"]
    topics: list[TopicReviewArtifact] = []
    evidence_aliases = {
        "qualification": ["qualification"],
        "scoring": ["scoring"],
        "technical": ["technical_standard"],
        "contract": ["contract_payment", "acceptance"],
    }
    for path in sorted(source_run.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        topic_key = payload.get("topic", path.stem)
        bundle_sections: list[dict] = []
        topic_coverage = {}
        for alias_key in evidence_aliases.get(topic_key, [topic_key]):
            bundle = bundles.get(alias_key, {})
            bundle_sections.extend(bundle.get("sections", []))
            if not topic_coverage and alias_key in coverages:
                topic_coverage = coverages.get(alias_key, {})
        metadata = {
            **dict(payload.get("metadata", {}) or {}),
            "selected_sections": [
                {
                    "title": section.get("title", ""),
                    "start_line": section.get("start_line"),
                    "end_line": section.get("end_line"),
                    "module": section.get("module", ""),
                }
                for section in bundle_sections
                if isinstance(section, dict)
            ],
            "evidence_bundle": {"sections": bundle_sections},
            "topic_coverage": topic_coverage,
        }
        topics.append(
            TopicReviewArtifact(
                topic=topic_key,
                summary=payload.get("summary", ""),
                risk_points=[RiskPoint(**risk) for risk in payload.get("risk_points", [])],
                need_manual_review=payload.get("need_manual_review", False),
                coverage_note=payload.get("coverage_note", ""),
                metadata=metadata,
            )
        )
    return structure, evidence, topics


def _build_current_real_run_topics() -> tuple[V2StageArtifact, V2StageArtifact, list[TopicReviewArtifact]]:
    return _build_feedback_source_topics(CURRENT_REAL_RUN)


def _build_topics_from_result_run(result_dir: Path) -> tuple[Path, V2StageArtifact, V2StageArtifact, list[TopicReviewArtifact]]:
    meta_path = result_dir / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        saved_file = Path("data/uploads/v2") / str(meta["saved_filename"])
    else:
        candidate_uploads = sorted(Path("data/uploads/v2").glob("*SZDL2025000495-A-0330.docx"))
        if not candidate_uploads:
            raise FileNotFoundError(f"missing meta.json and no fallback upload found for {result_dir}")
        saved_file = candidate_uploads[-1]
    source_run = result_dir / "topic_reviews"
    baseline_path = result_dir / "baseline_review.md"
    text = extract_text(saved_file)
    structure = build_structure_map(saved_file, text, _build_settings(), use_llm=False)
    evidence = build_evidence_map(saved_file.name, structure, topic_mode="mature")
    bundles = evidence.metadata["topic_evidence_bundles"]
    coverages = evidence.metadata["topic_coverages"]
    topics: list[TopicReviewArtifact] = []
    for path in sorted(source_run.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        topic_key = payload.get("topic", path.stem)
        bundle = bundles.get(topic_key, {})
        sections = [section for section in bundle.get("sections", []) if isinstance(section, dict)]
        metadata = {
            **dict(payload.get("metadata", {}) or {}),
            "selected_sections": [
                {
                    "title": section.get("title", ""),
                    "start_line": section.get("start_line"),
                    "end_line": section.get("end_line"),
                    "module": section.get("module", ""),
                }
                for section in sections
            ],
            "evidence_bundle": bundle,
            "topic_coverage": coverages.get(topic_key, {}),
        }
        topics.append(
            TopicReviewArtifact(
                topic=topic_key,
                summary=payload.get("summary", ""),
                risk_points=[RiskPoint(**risk) for risk in payload.get("risk_points", [])],
                need_manual_review=payload.get("need_manual_review", False),
                coverage_note=payload.get("coverage_note", ""),
                metadata=metadata,
            )
        )
    baseline_content = (
        baseline_path.read_text(encoding="utf-8")
        if baseline_path.exists()
        else f"# 招标文件合规审查结果\n\n审查对象：`{saved_file.name}`\n"
    )
    baseline = V2StageArtifact(name="baseline", content=baseline_content)
    return saved_file, structure, baseline, topics


def _build_0330_result_topics() -> tuple[Path, V2StageArtifact, V2StageArtifact, list[TopicReviewArtifact]]:
    return _build_topics_from_result_run(REAL_0330_RESULT)


def _build_0330_source_topics() -> tuple[V2StageArtifact, V2StageArtifact, list[TopicReviewArtifact]]:
    return _build_topics_for_file(REAL_0330_SOURCE_FILE)


def test_w002_real_file_compare_matrix_is_complete() -> None:
    structure, evidence, topics = _build_real_file_topics()
    comparison = compare_review_artifacts(REAL_FILE.name, V2StageArtifact(name="baseline", content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_FILE.name}`\n"), topics)
    codes = comparison.metadata["comparison_failure_reason_codes"]
    assert "policy_technical_inconsistency" in codes
    assert "star_marker_missing_for_mandatory_standard" in codes
    assert "acceptance_plan_in_scoring_forbidden" in codes
    assert "specific_brand_or_supplier_in_scoring_forbidden" in codes
    assert "acceptance_testing_cost_shifted_to_bidder" in codes
    assert "payment_terms_in_scoring_forbidden" not in codes
    assert "gifts_or_unrelated_goods_in_scoring_forbidden" not in codes

    scoring_topic = next(topic for topic in topics if topic.topic == "scoring")
    scoring_titles = [section["title"] for section in scoring_topic.metadata["selected_sections"]]
    assert "二、评审标准：" in scoring_titles

    technical_topic = next(topic for topic in topics if topic.topic == "technical_standard")
    technical_sections = [section["title"] for section in technical_topic.metadata["selected_sections"]]
    assert "（5） ▲排量： ≥50L" in technical_sections
    assert technical_topic.metadata["structured_signals"]["contains_gb_non_t"] is True

    titles = [cluster.title for cluster in comparison.clusters]
    assert "拒绝进口 vs 外标/国外部件引用矛盾风险" in titles
    assert "强制性标准条款未按评审规则标注★，可能导致实质性响应边界不清" in titles
    assert "将项目验收方案纳入评审因素，违反评审规则合规性要求" in titles
    assert "以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险" in titles
    assert "验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险" in titles


def test_w002_real_file_web_titles_follow_comparison_titles() -> None:
    structure, evidence, topics = _build_real_file_topics()
    baseline = V2StageArtifact(name="baseline", content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_FILE.name}`\n")
    comparison = compare_review_artifacts(REAL_FILE.name, baseline, topics)
    report_markdown = assemble_v2_report(REAL_FILE.name, baseline, structure, topics, comparison=comparison)
    comparison_dict = json.loads(comparison_to_json(comparison))
    review_view = build_review_view(parse_review_markdown(report_markdown), comparison_dict)
    card_titles = [card["title"] for card in review_view["all_cards"]]
    assert "将项目验收方案纳入评审因素，违反评审规则合规性要求" in card_titles
    assert "将付款方式纳入评审因素，违反评审规则合规性要求" not in card_titles
    assert "评分项中要求赠送非项目物资，存在明显不当加分和评审合规风险" not in card_titles


def test_w004_real_file_refinement_separates_formal_pending_and_excluded() -> None:
    structure, evidence, replay_topics = _build_real_file_replay_topics()
    baseline = V2StageArtifact(name="baseline", content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_FILE.name}`\n")
    comparison = compare_review_artifacts(REAL_FILE.name, baseline, replay_topics)
    formal_titles = [cluster.title for cluster in comparison.clusters]

    assert "技术标准引用与采购政策口径不一致，存在潜在倾向性和理解冲突" in formal_titles
    assert "评分档次缺少量化口径，主观分值裁量空间过大" in formal_titles
    assert "具体资格条件内容缺失，无法判断是否存在排斥性条款" in formal_titles
    assert "废标条件及最终解释权条款证据缺失" in formal_titles
    assert "关键合同条款数值缺失，导致付款与履约责任无法评估" in formal_titles
    assert "中小企业扶持政策落实条款缺失关键执行参数" in formal_titles
    assert comparison.metadata["pending_review_items"] == []
    assert comparison.metadata["excluded_risks"] == []


def test_w005_real_file_full_run_topics_are_refined_to_target_matrix() -> None:
    structure, evidence, replay_topics = _build_w005_source_topics()
    baseline = V2StageArtifact(name="baseline", content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_FILE.name}`\n")
    comparison = compare_review_artifacts(REAL_FILE.name, baseline, replay_topics)

    formal_titles = [cluster.title for cluster in comparison.clusters]

    assert "技术标准引用与采购政策口径不一致，存在潜在倾向性和理解冲突" in formal_titles
    assert "强制性标准条款未按评审规则标注★，可能导致实质性响应边界不清" in formal_titles
    assert "验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险" in formal_titles
    assert comparison.metadata["pending_review_items"] == []
    assert comparison.metadata["excluded_risks"] == []


def test_w006_real_file_output_is_layered_correctly() -> None:
    structure, evidence, replay_topics = _build_w006_source_topics()
    baseline = V2StageArtifact(name="baseline", content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_FILE.name}`\n")
    comparison = compare_review_artifacts(REAL_FILE.name, baseline, replay_topics)

    formal_titles = [cluster.title for cluster in comparison.clusters]
    pending_titles = [item["title"] for item in comparison.metadata["pending_review_items"]]
    excluded_titles = [item["title"] for item in comparison.metadata["excluded_risks"]]

    for title in [
        "付款条款关键数据缺失，无法评估公平性与节点衔接",
        "合同验收时点条款留白，验收流程缺乏明确的可操作性",
        "履约保证金金额及退还期限未明确",
        "验收期限留白，影响付款节点触发",
        "质量保证金及违约责任条款缺失",
        "标准编号与名称引用混乱且缺失版本信息",
        "燃油标准引用可能涉及废止或滞后版本",
        "澄清截止时间未明确填写",
        "采购标的所属行业未明确，影响中小企业声明函填写",
        "人员社保证明要求存在特殊豁免，需防范虚假人员风险",
        "电子投标文件容量限制可能增加投标负担",
    ]:
        assert title not in formal_titles

    for title in [
        "具体资格条款缺失，无法判断是否存在排斥性要求",
        "关键人员配置及业绩要求证据缺失，需人工复核",
        "政策导向章节内容缺失，无法确认节能环保等政策落实情况",
        "缺失检测报告及认证要求的具体规定",
        "三体系认证设置高分值，需评估与项目履约的关联性",
        "业绩评分内容与采购标的履约能力关联度存疑",
    ]:
        assert title in pending_titles

    for title in [
        "付款条款关键数据缺失，无法评估公平性与节点衔接",
        "合同验收时点条款留白，验收流程缺乏明确的可操作性",
        "履约保证金金额及退还期限未明确",
        "验收期限留白，影响付款节点触发",
        "质量保证金及违约责任条款缺失",
        "澄清截止时间未明确填写",
        "采购标的所属行业未明确，影响中小企业声明函填写",
        "人员社保证明要求存在特殊豁免，需防范虚假人员风险",
        "电子投标文件容量限制可能增加投标负担",
    ]:
        assert title in excluded_titles


def test_w006_final_markdown_summary_uses_layered_results_only() -> None:
    structure, evidence, replay_topics = _build_w006_source_topics()
    baseline = V2StageArtifact(name="baseline", content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_FILE.name}`\n")
    comparison = compare_review_artifacts(REAL_FILE.name, baseline, replay_topics)
    report_markdown = assemble_v2_report(REAL_FILE.name, baseline, structure, replay_topics, comparison=comparison)

    pending_section = report_markdown.split("## 待补证复核项", 1)[1].split("## 综合判断", 1)[0]
    summary_section = report_markdown.split("## 综合判断", 1)[1]

    for title in [
        "付款条款关键数据缺失，无法评估公平性与节点衔接",
        "履约保证金金额及退还期限未明确",
        "验收期限留白，影响付款节点触发",
        "澄清截止时间未明确填写",
        "采购标的所属行业未明确，影响中小企业声明函填写",
        "人员社保证明要求存在特殊豁免，需防范虚假人员风险",
        "电子投标文件容量限制可能增加投标负担",
        "qualification:",
        "performance_staff:",
        "contract_payment:",
    ]:
        assert title not in summary_section

    for title in [
        "三体系认证设置高分值，需评估与项目履约的关联性",
        "具体资格条款缺失，无法判断是否存在排斥性要求",
        "政策导向章节内容缺失，无法确认节能环保等政策落实情况",
    ]:
        assert title in pending_section
        assert title in summary_section

    assert "拒绝进口 vs 外标/国外部件引用矛盾风险" in summary_section


def test_w004_current_real_run_collapses_variant_titles_and_layers_results() -> None:
    structure, evidence, replay_topics = _build_current_real_run_topics()
    baseline = V2StageArtifact(name="baseline", content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_FILE.name}`\n")
    comparison = compare_review_artifacts(REAL_FILE.name, baseline, replay_topics)

    formal_titles = [cluster.title for cluster in comparison.clusters]
    pending_titles = [item["title"] for item in comparison.metadata["pending_review_items"]]
    excluded_titles = [item["title"] for item in comparison.metadata["excluded_risks"]]

    assert "拒绝进口 vs 外标/国外部件引用矛盾风险" in formal_titles
    assert "以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险" in formal_titles
    assert "评分描述量化口径不足，存在评审一致性风险" in formal_titles
    assert "验收标准来源表述不清，容易引发验收依据理解歧义" in formal_titles

    for title in [
        "三体系认证及特定产品证书设置高分值，存在排斥潜在投标人风险",
        "中小企业声明函填写指引中未明确‘采购标的所属行业’",
        "尾款支付节点滞后，资金占用风险高",
        "评分标准中“制造商发电机组资质证书”要求特定认证，具有明显倾向性",
        "业绩评分项时间范围表述存在逻辑矛盾",
        "商务条款中“设备安装要求”设定特定资质和人员经验，可能构成不合理限制",
        "政策导向章节内容缺失，无法确认节能环保及进口产品政策落实情况",
        "社保证明要求存在特殊豁免条款，需防范规避监管风险",
        "评分标准中“拟安排的项目负责人情况”设置学历、职称及经验累计得分，可能构成以不合理条件限制竞争",
        "预付款比例偏低且支付条件模糊",
        "中小企业声明函填写指引中关于‘不重复享受’的表述需结合具体评审办法确认",
        "电子投标文件容量限制需关注",
        "评分标准中“供应商同类项目业绩情况”时间范围设定过短，可能限制竞争",
    ]:
        assert title not in formal_titles

    for title in [
        "关键人员配置及业绩要求信息缺失，无法判断合理性",
        "具体资格条款缺失，无法判断是否存在排斥性要求",
        "废标条件及最终解释权条款证据缺失",
        "缺失检测报告及认证要求的具体规定",
        "政策导向章节内容缺失，无法确认节能环保及进口产品政策落实情况",
    ]:
        assert title in pending_titles

    for title in [
        "中小企业声明函填写指引中未明确‘采购标的所属行业’",
        "尾款支付节点滞后，资金占用风险高",
        "预付款比例偏低且支付条件模糊",
        "社保证明要求存在特殊豁免条款，需防范规避监管风险",
        "中小企业声明函填写指引中关于‘不重复享受’的表述需结合具体评审办法确认",
        "电子投标文件容量限制需关注",
        "关键条款缺失：履约保证金、违约责任等未明确",
    ]:
        assert title in excluded_titles

    assert len(formal_titles) <= 12


def test_g004_real_file_import_consistency_includes_foreign_component_evidence() -> None:
    structure, evidence, topics = _build_real_file_topics()
    baseline = V2StageArtifact(name="baseline", content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_FILE.name}`\n")
    comparison = compare_review_artifacts(REAL_FILE.name, baseline, topics)
    cluster = next(
        item for item in comparison.clusters if item.title == "拒绝进口 vs 外标/国外部件引用矛盾风险"
    )
    assert any("部件/验收条款" in location for location in cluster.source_locations)
    assert any("原产地证明" in excerpt for excerpt in cluster.source_excerpts)


def test_g004_real_file_turnkey_payment_risk_is_excluded_when_payment_chain_is_complete() -> None:
    text = extract_text(REAL_FILE)
    structure = build_structure_map(REAL_FILE, text, _build_settings(), use_llm=False)
    evidence = build_evidence_map(REAL_FILE.name, structure, topic_mode="mature")
    bundle = evidence.metadata["topic_evidence_bundles"]["contract_payment"]
    sections = [section for section in bundle.get("sections", []) if isinstance(section, dict)]
    contract_topic = TopicReviewArtifact(
        topic="contract_payment",
        summary="付款专题真实文件回放",
        risk_points=[],
        need_manual_review=False,
        coverage_note="已覆盖付款链路。",
        metadata={
            "selected_sections": [
                {
                    "title": section.get("title", ""),
                    "start_line": section.get("start_line"),
                    "end_line": section.get("end_line"),
                    "module": section.get("module", ""),
                }
                for section in sections
            ],
            "missing_evidence": ["未发现"],
            "structured_signals": _build_structured_signals(get_topic_definition("contract_payment"), sections),
            "evidence_bundle": bundle,
        },
    )
    baseline = V2StageArtifact(
        name="baseline",
        content="""
# 招标文件合规审查结果

审查对象：`sample.docx`

## 风险点1：商务条款中“交钥匙”项目要求与付款方式存在潜在风险

- 问题定性：低风险
- 审查类型：商务条款失衡
- 原文位置：第三章 用户需求书 -> 五、商务要求 -> 2.基本要求 & 3.付款方式
- 原文摘录：本项目为交钥匙项目，投标总价包含所有费用。
- 风险判断：
  - 交钥匙项目与付款安排可能存在失衡。
- 法律/政策依据：
  - 需人工复核
- 整改建议：
  - 结合付款链路进一步复核。
""".strip(),
    )
    comparison = compare_review_artifacts(REAL_FILE.name, baseline, [contract_topic])
    formal_titles = [cluster.title for cluster in comparison.clusters]
    pending_titles = [item["title"] for item in comparison.metadata["pending_review_items"]]
    excluded = next(
        item for item in comparison.metadata["excluded_risks"] if item["title"] == "商务条款中“交钥匙”项目要求与付款方式存在潜在风险"
    )
    assert "商务条款中“交钥匙”项目要求与付款方式存在潜在风险" not in formal_titles
    assert "商务条款中“交钥匙”项目要求与付款方式存在潜在风险" not in pending_titles
    assert "完整付款链路" in excluded["reason"]


def test_g005_real_file_moves_qualification_missing_and_policy_missing_to_pending() -> None:
    structure, evidence, replay_topics = _build_feedback_source_topics(G005_SOURCE_RUN)
    baseline = V2StageArtifact(name="baseline", content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_FILE.name}`\n")
    comparison = compare_review_artifacts(REAL_FILE.name, baseline, replay_topics)

    formal_titles = [cluster.title for cluster in comparison.clusters]
    pending_titles = [item["title"] for item in comparison.metadata["pending_review_items"]]

    assert "投标人资格要求内容缺失，无法判断是否存在排斥性条款" not in formal_titles
    assert "政策导向章节内容缺失，无法全面审查其他政策落实情况" not in formal_titles
    assert "投标人资格要求内容缺失，无法判断是否存在排斥性条款" in pending_titles
    assert "政策导向章节内容缺失，无法全面审查其他政策落实情况" in pending_titles


def test_w007_real_file_template_placeholder_risks_do_not_enter_formal() -> None:
    saved_file, structure, baseline, topics = _build_topics_from_result_run(W007_SOURCE_RESULT)
    comparison = compare_review_artifacts(saved_file.name, baseline, topics)

    template_tokens = ["甲方收到乙方自测报告后", "检测通过后", "整改通知后"]
    formal_titles = [
        cluster.title
        for cluster in comparison.clusters
        if any(token in " ".join(cluster.source_excerpts) for token in template_tokens)
    ]
    assert formal_titles == []

    excluded_matches = [
        item
        for item in comparison.metadata["excluded_risks"]
        if any(token in str(item.get("source_excerpt", "")) for token in template_tokens)
    ]
    pending_matches = [
        item
        for item in comparison.metadata["pending_review_items"]
        if any(token in str(item.get("source_excerpt", "")) for token in template_tokens)
    ]
    assert excluded_matches or pending_matches
    for item in excluded_matches:
        assert "模板中的时限占位符" in str(item.get("reason", ""))

    final_output = build_v2_final_output(saved_file.name, baseline, structure, topics, comparison=comparison)
    assert not any(
        any(token in str(item.get("source_excerpt", "")) for token in template_tokens)
        for item in final_output["formal_risks"]
    )


def test_r008_real_file_replay_hits_gifts_non_project_goods_risk() -> None:
    structure, evidence, topics = _build_r008_real_file_topics()
    baseline = V2StageArtifact(name="baseline", content=f"# 招标文件合规审查结果\n\n审查对象：`{R008_REAL_FILE.name}`\n")
    comparison = compare_review_artifacts(R008_REAL_FILE.name, baseline, topics)

    codes = comparison.metadata["comparison_failure_reason_codes"]
    assert "gifts_or_unrelated_goods_in_scoring_forbidden" in codes

    scoring_topic = next(topic for topic in topics if topic.topic == "scoring")
    scoring_titles = [section["title"] for section in scoring_topic.metadata["selected_sections"]]
    assert "（一） 评分内容" in scoring_titles
    assert scoring_topic.metadata["structured_signals"]["scoring_contains_gifts_or_unrelated_goods"] is True
    assert scoring_topic.metadata["structured_signals"]["gifts_or_goods_linked_to_score"] is True
    assert any("赠送台式电脑" in item for item in scoring_topic.metadata["structured_signals"]["gifts_or_goods_scoring_sentences"])

    titles = [cluster.title for cluster in comparison.clusters]
    assert "评分项中要求赠送非项目物资，存在明显不当加分和评审合规风险" in titles

    cluster = next(item for item in comparison.clusters if item.title == "评分项中要求赠送非项目物资，存在明显不当加分和评审合规风险")
    assert any("评分条款" in location for location in cluster.source_locations)
    assert any("赠送台式电脑、打印机各1套" in excerpt for excerpt in cluster.source_excerpts)

    report_markdown = assemble_v2_report(R008_REAL_FILE.name, baseline, structure, topics, comparison=comparison)
    assert "评分项中要求赠送非项目物资，存在明显不当加分和评审合规风险" in report_markdown
    assert "删除赠送台式电脑、打印机、办公设备等与项目采购无关物资的加分条件。" in report_markdown


def test_r004_real_file_replay_hits_payment_terms_in_scoring_risk() -> None:
    structure, evidence, topics = _build_r004_real_file_topics()
    baseline = V2StageArtifact(name="baseline", content=f"# 招标文件合规审查结果\n\n审查对象：`{R004_REAL_FILE.name}`\n")
    comparison = compare_review_artifacts(R004_REAL_FILE.name, baseline, topics)

    codes = comparison.metadata["comparison_failure_reason_codes"]
    assert "payment_terms_in_scoring_forbidden" in codes

    scoring_topic = next(topic for topic in topics if topic.topic == "scoring")
    assert scoring_topic.metadata["structured_signals"]["scoring_contains_payment_terms"] is True
    assert scoring_topic.metadata["structured_signals"]["payment_terms_linked_to_score"] is True
    assert any("付款周期短于招标文件要求" in item for item in scoring_topic.metadata["structured_signals"]["payment_terms_scoring_sentences"])
    assert any("预付款比例更有利于采购人资金安排" in item for item in scoring_topic.metadata["structured_signals"]["payment_terms_scoring_sentences"])

    titles = [cluster.title for cluster in comparison.clusters]
    assert "将付款方式纳入评审因素，违反评审规则合规性要求" in titles

    cluster = next(item for item in comparison.clusters if item.title == "将付款方式纳入评审因素，违反评审规则合规性要求")
    assert any("评分条款" in location for location in cluster.source_locations)
    assert any("付款周期短于招标文件要求" in excerpt for excerpt in cluster.source_excerpts)
    assert any("预付款比例更有利于采购人资金安排" in excerpt for excerpt in cluster.source_excerpts)

    report_markdown = assemble_v2_report(R004_REAL_FILE.name, baseline, structure, topics, comparison=comparison)
    assert "将付款方式纳入评审因素，违反评审规则合规性要求" in report_markdown
    assert "将付款周期、预付款比例等内容从评分因素中删除。" in report_markdown


def test_0330_real_file_output_is_deduped_and_downgraded() -> None:
    saved_file, structure, baseline, topics = _build_0330_result_topics()
    comparison = compare_review_artifacts(saved_file.name, baseline, topics)

    formal_titles = [cluster.title for cluster in comparison.clusters]
    pending_titles = [item["title"] for item in comparison.metadata["pending_review_items"]]
    excluded_titles = [item["title"] for item in comparison.metadata["excluded_risks"]]

    assert "业绩评分限定特定行政区域，存在地域排斥风险" in formal_titles
    assert "业绩要求限定特定行政区域，排斥外地供应商" not in formal_titles
    assert "业绩评分限定特定行政区域，存在地域歧视和排斥潜在投标人风险" not in formal_titles

    assert "验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险" in formal_titles
    assert "将验收阶段检测费用笼统计入投标总价，存在合规风险" not in formal_titles

    assert "项目负责人评分项设置过高且累计分值不合理，存在重复评价和倾向性风险" in formal_titles
    assert "人员评分中学历、职称及证书要求分值过高，可能构成过高门槛" not in formal_titles
    assert "项目负责人学历及职称要求过高，可能构成不合理限制" not in formal_titles
    assert "项目负责人评分项分值畸高且设置不合理，存在重复评价和倾向性风险" not in formal_titles

    assert "履约保证金比例严重超标" in formal_titles
    assert "履约保证金比例过高，增加供应商负担" not in formal_titles

    assert "技术参数中指定特定生产日期，具有明显排他性和倾向性" in formal_titles

    assert "评分描述量化口径不足，存在评审一致性风险" in formal_titles
    assert "评分表达采用定性分档或分点+分档组合，但量化标准、计算方式或判定边界说明不清，存在评审口径不一致风险" not in formal_titles
    assert "评分标准主观性过强，缺乏量化依据，易导致评审不公" not in formal_titles

    assert "以特定认证及特定发证机构作为评分条件，存在倾向性评分和限制竞争风险" in formal_titles
    assert "评分标准中限定特定认证机构，限制竞争" not in formal_titles

    assert "拒绝进口 vs 外标/国外部件引用矛盾风险" in formal_titles
    assert "非进口项目中出现国外标准/国外部件相关表述，存在采购政策口径、技术标准口径、验收口径不一致风险" not in formal_titles
    assert "燃油标准引用非国标且可能失效" not in formal_titles
    assert "燃油标准引用可能涉及废止版本" not in formal_titles

    assert "踏勘现场作为资格性审查条件，违反通用条款" in formal_titles

    assert "节能环保产品政策条款缺失" not in formal_titles
    assert "节能环保产品政策条款缺失" in pending_titles

    for title in [
        "企业证书（三体系）评分分值设置过高，存在排斥中小企业风险",
        "澄清/修改事项截止时间未明确填写",
        "评分标准中“诚信情况”查询渠道及扣分标准表述不清",
        "验收主体表述笼统，未明确‘相关人员’的具体构成及职责",
        "社保缴纳证明要求存在例外情形，需关注执行一致性",
    ]:
        assert title not in formal_titles

    assert "综合实力评分中体系认证要求设置不合理，存在‘全有或全无’风险" not in formal_titles
    assert "认证项权重偏高且与履约关联不足，存在倾向性评分风险" in formal_titles

    assert "采购文件澄清截止时间未明确填写" not in pending_titles
    assert "采购文件澄清截止时间未明确填写" in excluded_titles
    assert "进口产品禁止条款表述过于绝对，未预留法定例外" not in formal_titles
    assert "验收时点约定缺失，导致验收流程不可操作" not in formal_titles
    assert "验收时点约定缺失，导致验收流程不可操作" in excluded_titles


def test_0330_real_file_wording_does_not_conflict_with_project_context() -> None:
    saved_file, structure, baseline, topics = _build_0330_result_topics()
    comparison = compare_review_artifacts(saved_file.name, baseline, topics)
    judgment_text = "\n".join(
        "\n".join(cluster.risk_judgment)
        for cluster in comparison.clusters
    )
    assert "若本项目并非专门针对柴油发电机组采购" not in judgment_text
    assert "若标的为通用服务或设备" not in judgment_text


def test_0330_real_file_wording_is_tightened_for_risks_1_5_10() -> None:
    saved_file, structure, baseline, topics = _build_0330_result_topics()
    comparison = compare_review_artifacts(saved_file.name, baseline, topics)
    clusters = {cluster.title: cluster for cluster in comparison.clusters}

    import_cluster = clusters["拒绝进口 vs 外标/国外部件引用矛盾风险"]
    assert import_cluster.risk_judgment[0] == "文件一方面明确不接受进口产品，另一方面又在技术标准、部件或验收口径中引入外标/国外部件表述，容易造成供应商对可投范围和验收依据理解冲突。"
    assert any("标准版本、编号或格式问题仅能作为该主风险的补充佐证，不应盖过主风险本身。" == item for item in import_cluster.risk_judgment)
    assert not any("GB 252 标准已多次更新" in item for item in import_cluster.risk_judgment)

    acceptance_cluster = clusters["验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险"]
    assert acceptance_cluster.risk_judgment == [
        "同一组条款将检测、相关部门验收等费用笼统纳入投标总价，问题核心应收敛为费用边界不清和潜在转嫁风险。",
        "当前条款未区分履约自检、试运行成本与验收阶段第三方/法定检测费用，容易引发费用承担边界争议。",
        "若其中包含项目验收所需专项检测、第三方检测或法定检测事项，则存在将验收检测费用转嫁给中标人的潜在风险。",
    ]

    scoring_cluster = clusters["评分描述量化口径不足，存在评审一致性风险"]
    assert scoring_cluster.risk_judgment == [
        "该评分项同时使用分点覆盖和档次评价表达，但量化口径、计算关系和判定边界说明仍不够清晰，容易影响评审一致性。",
        "评分标准仍以“清晰”“较清晰”“模糊”“操作性强”等定性描述为主，缺少可直接对照的量化判定标准。",
        "不同档次之间分值差距较大，但缺少清晰的区分依据，容易影响评审一致性和结果稳定性。",
    ]
    assert not any("自由裁量权过大" in item for item in scoring_cluster.risk_judgment)


def test_0330_source_file_does_not_contain_gifts_clause_or_hit_gifts_risk() -> None:
    text = extract_text(REAL_0330_SOURCE_FILE)
    for needle in ["赠送", "台式电脑", "打印机", "值班室", "各1套"]:
        assert needle not in text

    structure, evidence, topics = _build_0330_source_topics()
    baseline = V2StageArtifact(name="baseline", content=f"# 招标文件合规审查结果\n\n审查对象：`{REAL_0330_SOURCE_FILE.name}`\n")
    comparison = compare_review_artifacts(REAL_0330_SOURCE_FILE.name, baseline, topics)

    scoring_topic = next(topic for topic in topics if topic.topic == "scoring")
    assert scoring_topic.metadata["structured_signals"]["scoring_contains_gifts_or_unrelated_goods"] is False
    assert scoring_topic.metadata["structured_signals"]["gifts_or_goods_linked_to_score"] is False
    assert scoring_topic.metadata["structured_signals"]["gifts_or_goods_scoring_sentences"] == []
    assert all(
        cluster.title != "评分项中要求赠送非项目物资，存在明显不当加分和评审合规风险"
        for cluster in comparison.clusters
    )


def test_0330_real_file_standard_rule_formal_risk_does_not_carry_manual_marker() -> None:
    saved_file, structure, baseline, topics = _build_0330_result_topics()
    comparison = compare_review_artifacts(saved_file.name, baseline, topics)

    cluster = next(
        item for item in comparison.clusters if item.title == "将项目验收方案纳入评审因素，违反评审规则合规性要求"
    )
    assert cluster.need_manual_review is False
    assert "compare_rule" in cluster.source_rules
    assert "需人工复核" not in cluster.legal_basis

    final_output = build_v2_final_output(saved_file.name, baseline, structure, topics, comparison=comparison)
    formal_risk = next(
        item for item in final_output["formal_risks"] if item["title"] == "将项目验收方案纳入评审因素，违反评审规则合规性要求"
    )
    assert "需人工复核" not in formal_risk["legal_basis"]

    review_view = build_review_view_from_final_output(final_output, json.loads(comparison_to_json(comparison)))
    card = next(item for item in review_view["all_cards"] if item["title"] == "将项目验收方案纳入评审因素，违反评审规则合规性要求")
    assert card["manual_reasons"] == []
    assert "需人工复核" not in card["legal_basis"]
