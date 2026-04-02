from __future__ import annotations

import io
import json
from pathlib import Path

from app.common.markdown_utils import parse_review_markdown
from app.web.v2_app import build_comparison_view, build_review_view, build_topic_view, create_app, load_result_by_run_id


def test_build_comparison_view_marks_empty_payload_unavailable() -> None:
    view = build_comparison_view({})
    assert view["available"] is False
    assert view["baseline_only"] == []
    assert view["manual_review_items"] == []


def test_build_topic_view_falls_back_to_overview() -> None:
    topic_view = build_topic_view(
        [],
        {
            "topics": [
                {
                    "topic": "qualification",
                    "summary": "资格专题摘要",
                    "risk_count": 2,
                    "need_manual_review": True,
                    "coverage_note": "覆盖资格章节",
                }
            ]
        },
    )
    assert len(topic_view) == 1
    assert topic_view[0]["topic_label"] == "资格条件"
    assert topic_view[0]["risk_count"] == 2
    assert topic_view[0]["need_manual_review"] is True


def test_load_result_by_run_id_supports_legacy_overview_without_comparison(tmp_path: Path, monkeypatch) -> None:
    run_dir = tmp_path / "legacy-run"
    run_dir.mkdir()
    (run_dir / "review.md").write_text(
        "# 招标文件合规审查结果\n\n审查对象：`legacy.docx`\n\n说明：\n- 测试\n",
        encoding="utf-8",
    )
    (run_dir / "v2_overview.json").write_text(
        json.dumps(
            {
                "topics": [
                    {
                        "topic": "technical",
                        "summary": "技术专题摘要",
                        "risk_count": 1,
                        "need_manual_review": False,
                        "coverage_note": "覆盖技术章节",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("app.web.v2_app.find_run_dir", lambda run_id: run_dir if run_id == "legacy-run" else None)

    app = create_app()
    with app.test_request_context():
        result = load_result_by_run_id("legacy-run")

    assert result is not None
    assert result["comparison_view"]["available"] is False
    assert result["topic_view"][0]["topic_label"] == "技术细节"
    assert result["topic_view"][0]["risk_count"] == 1
    assert result["topic_mode"] == "mature"
    assert result["topic_mode_label"] == "成熟专题"


def test_review_plus_start_defaults_to_mature_mode(tmp_path: Path, monkeypatch) -> None:
    saved_path = tmp_path / "upload.docx"

    monkeypatch.setattr("app.web.v2_app._save_upload", lambda upload: saved_path)
    monkeypatch.setattr(
        "app.web.v2_app.load_config",
        lambda: {
            "base_url": "",
            "model": "",
            "api_key": "",
            "timeout": "1800",
            "temperature": "0",
            "max_tokens": "6400",
            "system_prompt": "",
            "user_prompt": "",
        },
    )

    captured: dict[str, object] = {}

    class DummyThread:
        def __init__(self, *, target, args, daemon):
            captured["args"] = args
            captured["daemon"] = daemon

        def start(self):
            captured["started"] = True

    monkeypatch.setattr("app.web.v2_app.threading.Thread", DummyThread)

    app = create_app()
    client = app.test_client()
    response = client.post(
        "/review-plus/start",
        data={"tender_file": (io.BytesIO(b"demo"), "sample.docx")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["topic_mode"] == "mature"
    assert payload["topic_mode_label"] == "成熟专题"
    assert captured["args"][-1] == "mature"


def test_review_plus_start_accepts_explicit_topic_mode(tmp_path: Path, monkeypatch) -> None:
    saved_path = tmp_path / "upload.docx"

    monkeypatch.setattr("app.web.v2_app._save_upload", lambda upload: saved_path)
    monkeypatch.setattr(
        "app.web.v2_app.load_config",
        lambda: {
            "base_url": "",
            "model": "",
            "api_key": "",
            "timeout": "1800",
            "temperature": "0",
            "max_tokens": "6400",
            "system_prompt": "",
            "user_prompt": "",
        },
    )

    captured: dict[str, object] = {}

    class DummyThread:
        def __init__(self, *, target, args, daemon):
            captured["args"] = args

        def start(self):
            captured["started"] = True

    monkeypatch.setattr("app.web.v2_app.threading.Thread", DummyThread)

    app = create_app()
    client = app.test_client()
    response = client.post(
        "/review-plus/start",
        data={"topic_mode": "default", "tender_file": (io.BytesIO(b"demo"), "sample.docx")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["topic_mode"] == "default"
    assert payload["topic_mode_label"] == "兼容专题"
    assert captured["args"][-1] == "default"


def test_build_review_view_prioritizes_standard_compare_cards() -> None:
    report = parse_review_markdown(
        """
# 招标文件合规审查结果

审查对象：`sample.docx`

## 风险点1：评分标准中“安装、检测、验收、培训计划”存在主观性描述且分值逻辑错误

- 问题定性：中风险
- 审查类型：评分因素不相关/评分标准不明确
- 原文位置：第六章 评分办法
- 原文摘录：安装、检测、验收、培训计划，评价为优得60分。
- 风险判断：
  - 需人工复核
- 法律/政策依据：
  - 需人工复核
- 整改建议：
  - 补充量化口径

## 风险点2：将项目验收方案纳入评审因素，违反评审规则合规性要求

- 问题定性：中风险
- 审查类型：评分因素合规性 / 评审规则设置合法性
- 原文位置：第六章 评分办法
- 原文摘录：安装、检测、验收、培训计划，评价为优得60分。
- 风险判断：
  - 需人工复核
- 法律/政策依据：
  - 需人工复核
- 整改建议：
  - 删除验收方案评分
""".strip()
    )
    comparison = {
        "clusters": [
            {
                "title": "将项目验收方案纳入评审因素，违反评审规则合规性要求",
                "review_type": "评分因素合规性 / 评审规则设置合法性",
                "source_rules": ["compare_rule"],
                "topics": ["cross_topic"],
                "conflict_notes": [],
                "need_manual_review": False,
            },
            {
                "title": "评分标准中“安装、检测、验收、培训计划”存在主观性描述且分值逻辑错误",
                "review_type": "评分因素不相关/评分标准不明确",
                "source_rules": ["baseline"],
                "topics": ["baseline"],
                "conflict_notes": [],
                "need_manual_review": False,
            },
        ]
    }

    view = build_review_view(report, comparison)
    assert view["all_cards"][0]["title"] == "将项目验收方案纳入评审因素，违反评审规则合规性要求"
    assert view["all_cards"][0]["is_standard_compare"] is True


def test_build_review_view_sorts_left_risk_list_by_severity_desc() -> None:
    report = parse_review_markdown(
        """
# 招标文件合规审查结果

审查对象：`sample.docx`

## 风险点1：中风险事项

- 问题定性：中风险
- 审查类型：类型A
- 原文位置：第一章
- 原文摘录：中风险内容。
- 风险判断：
  - 中风险判断
- 法律/政策依据：
  - 需人工复核
- 整改建议：
  - 建议A

## 风险点2：高风险事项

- 问题定性：高风险
- 审查类型：类型B
- 原文位置：第二章
- 原文摘录：高风险内容。
- 风险判断：
  - 高风险判断
- 法律/政策依据：
  - 需人工复核
- 整改建议：
  - 建议B

## 风险点3：低风险事项

- 问题定性：低风险
- 审查类型：类型C
- 原文位置：第三章
- 原文摘录：低风险内容。
- 风险判断：
  - 低风险判断
- 法律/政策依据：
  - 需人工复核
- 整改建议：
  - 建议C
""".strip()
    )
    view = build_review_view(report, comparison=None)
    assert [item["title"] for item in view["all_cards"][:3]] == ["高风险事项", "中风险事项", "低风险事项"]
