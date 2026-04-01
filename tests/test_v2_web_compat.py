from __future__ import annotations

import io
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
