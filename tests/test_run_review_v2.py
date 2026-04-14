from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from app.pipelines.v2.schemas import V2ReviewArtifacts, V2StageArtifact

import scripts.run_review_v2 as run_review_v2


QUANZHOU_LIVE_FILE = Path("/Users/linzeran/code/2026-zn/test_target/泉州/操场跑道、篮球场、小操场维护项目招标文件1.docx")
DIESEL_LIVE_FILE = Path("/Users/linzeran/code/2026-zn/test_target/zf/埋点测试案例和结果/[SZDL2025000495-A-0330]柴油发电机组及相关配套机电设备采购及安装项目.docx")
FUJIAN_LIVE_FILE = Path("/Users/linzeran/code/2026-zn/test_target/福建/（埋点）福建省食品药品质量检验研究院2023年物业管理服务采购.docx")


def _build_dummy_artifacts() -> V2ReviewArtifacts:
    stage = V2StageArtifact(name="dummy", content="")
    stage.metadata = {}
    return V2ReviewArtifacts(
        extracted_text="dummy",
        baseline=stage,
        structure=stage,
        topics=[],
        final_markdown="# dummy",
        evidence=stage,
        evidence_layer=None,
        comparison=None,
    )


def test_parse_args_defaults_to_mature(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_review_v2.py", "sample.docx", "-o", "data/results/v2/demo-run"],
    )
    args = run_review_v2.parse_args()
    assert args.topic_mode == "mature"


def test_main_uses_mature_topic_mode_by_default(monkeypatch, tmp_path: Path) -> None:
    input_file = tmp_path / "sample.docx"
    input_file.write_text("dummy", encoding="utf-8")
    output_dir = tmp_path / "out"
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        sys,
        "argv",
        ["run_review_v2.py", str(input_file), "-o", str(output_dir)],
    )

    monkeypatch.setattr(run_review_v2.ReviewSettings, "from_env", staticmethod(lambda: run_review_v2.ReviewSettings()))

    def fake_review_document_v2(input_path, settings, progress_callback=None, stream_callback=None, topic_mode="default", topic_keys=None):
        captured["input_path"] = input_path
        captured["topic_mode"] = topic_mode
        return _build_dummy_artifacts()

    def fake_save_review_artifacts_v2(artifacts, save_dir):
        captured["output_dir"] = save_dir

    monkeypatch.setattr(run_review_v2, "review_document_v2", fake_review_document_v2)
    monkeypatch.setattr(run_review_v2, "save_review_artifacts_v2", fake_save_review_artifacts_v2)

    exit_code = run_review_v2.main()

    assert exit_code == 0
    assert captured["input_path"] == input_file.resolve()
    assert captured["output_dir"] == output_dir.resolve()
    assert captured["topic_mode"] == "mature"


def test_live_quanzhou_review_min_002_promotes_only_two_pending_titles_to_formal(tmp_path: Path) -> None:
    if os.getenv("RUN_LIVE_REVIEW_TESTS") != "1":
        pytest.skip("set RUN_LIVE_REVIEW_TESTS=1 to execute live review against the real Quanzhou document")
    if not QUANZHOU_LIVE_FILE.exists():
        pytest.skip(f"missing live file: {QUANZHOU_LIVE_FILE}")

    artifacts = run_review_v2.review_document_v2(
        QUANZHOU_LIVE_FILE,
        run_review_v2.ReviewSettings.from_env(),
        topic_mode="mature",
    )
    snapshot = artifacts.final_snapshot or {}
    final_risks = snapshot.get("final_risks", {})
    formal_titles = {item.get("title") for item in final_risks.get("formal_risks", [])}
    pending_titles = {item.get("title") for item in final_risks.get("pending_review_items", [])}
    assert len(formal_titles) == 6

    assert {
        "强制性标准条款未按评审规则标注★，可能导致实质性响应边界不清",
        "验收检测及相关部门验收费用表述笼统，存在费用边界不清和潜在转嫁风险",
        "疑似限定或倾向特定品牌/供应商",
        "将样品要求/验收方案不当作为评审或履约门槛",
        "合同支付条款存在严重逻辑矛盾，付款比例总和超过100%",
        "引用已废止标准且未明确替代版本",
    } <= formal_titles
    assert "远程开标逾期解密后果表述需进一步确认" in pending_titles
    assert "验收流程、主体及不合格处理机制表述模糊，缺乏可操作性" in pending_titles
    assert "合同支付条款存在严重逻辑矛盾，付款比例总和超过100%" not in pending_titles
    assert "引用已废止标准且未明确替代版本" not in pending_titles


def test_live_diesel_review_min_003_fixes_titles_and_promotes_two_formal_items() -> None:
    if os.getenv("RUN_LIVE_REVIEW_TESTS") != "1":
        pytest.skip("set RUN_LIVE_REVIEW_TESTS=1 to execute live review against the real Diesel document")
    if not DIESEL_LIVE_FILE.exists():
        pytest.skip(f"missing live file: {DIESEL_LIVE_FILE}")

    artifacts = run_review_v2.review_document_v2(
        DIESEL_LIVE_FILE,
        run_review_v2.ReviewSettings.from_env(),
        topic_mode="mature",
    )
    snapshot = artifacts.final_snapshot or {}
    final_risks = snapshot.get("final_risks", {})
    formal_titles = {item.get("title") for item in final_risks.get("formal_risks", [])}
    pending_titles = {item.get("title") for item in final_risks.get("pending_review_items", [])}
    excluded_titles = {item.get("title") for item in final_risks.get("excluded_risks", [])}
    formal_items = {item.get("title"): item for item in final_risks.get("formal_risks", [])}

    assert "项目负责人评分设置存在形式歧视、职称分值偏高及重复评价风险" in formal_titles
    assert "项目负责人评分项设置过高且累计分值不合理，存在重复评价和倾向性风险" not in formal_titles

    assert "要求现场技术人员必须为制造商原厂工程师，存在排斥代理商风险" in formal_titles
    assert "要求现场技术人员必须为制造商原厂工程师，存在排斥代理商风险" not in pending_titles

    assert "技术参数中指定特定生产日期，具有明显排他性和倾向性" in formal_titles
    assert "生产日期必须是 2025 年" in "".join(formal_items["技术参数中指定特定生产日期，具有明显排他性和倾向性"].get("source_excerpts", []))

    assert "节能环保产品政策条款缺失" not in formal_titles
    assert "节能环保产品政策条款缺失" not in pending_titles
    assert "检测报告及认证资质要求缺失，验收依据不足" not in formal_titles
    assert "检测报告及认证资质要求缺失，验收依据不足" not in pending_titles
    assert "检测报告及认证资质要求缺失，验收依据不足" not in excluded_titles


def test_live_fujian_review_min_001_recovers_core_visible_items_and_legacy_projection() -> None:
    if os.getenv("RUN_LIVE_REVIEW_TESTS") != "1":
        pytest.skip("set RUN_LIVE_REVIEW_TESTS=1 to execute live review against the real Fujian document")
    if not FUJIAN_LIVE_FILE.exists():
        pytest.skip(f"missing live file: {FUJIAN_LIVE_FILE}")

    artifacts = run_review_v2.review_document_v2(
        FUJIAN_LIVE_FILE,
        run_review_v2.ReviewSettings.from_env(),
        topic_mode="mature",
    )
    snapshot = artifacts.final_snapshot or {}
    final_output = artifacts.final_output or {}
    final_risks = snapshot.get("final_risks", {})
    formal_titles = {item.get("title") for item in final_risks.get("formal_risks", [])}
    pending_titles = {item.get("title") for item in final_risks.get("pending_review_items", [])}

    assert all(item.get("severity") in {"高风险", "中风险", "低风险"} for item in final_risks.get("formal_risks", []))
    assert {
        "评分标准中设置特定品牌倾向性条款",
        "技术参数中人员配置要求存在性别、年龄等歧视性条款",
        "评分标准中设置与履约能力关联度不高的企业荣誉及特定荣誉加分",
        "商务条款中关于“无犯罪证明”的提交时限及无效投标处理存在法律风险",
        "评分标准中“信息化软件服务能力”要求著作权人为投标人，可能限制竞争",
        "技术参数中关于“实验服清洗服务”的设备品牌指定风险",
    } <= formal_titles
    assert pending_titles == {
        "远程开标逾期解密后果表述需进一步确认",
        "评分标准中人员配置要求存在重复计分及特定证书倾向性",
    }
    assert final_output.get("summary_counts")
    assert len(final_output.get("review_items", [])) == len(formal_titles) + len(pending_titles)
