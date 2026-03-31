from __future__ import annotations

import json
from pathlib import Path

from app.web.v2_app import build_comparison_view, build_topic_view, create_app, load_result_by_run_id


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
