from __future__ import annotations

from app.common import core


def test_call_chat_completion_stream_falls_back_to_non_stream_for_qwen(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_call_chat_completion(**kwargs):
        captured.update(kwargs)
        return {"choices": [{"message": {"content": "OK"}}]}

    streamed: list[str] = []

    monkeypatch.setattr(core, "call_chat_completion", fake_call_chat_completion)

    response = core.call_chat_completion_stream(
        base_url="http://example.com/v1",
        model="qwen3.5-27b",
        api_key="token",
        system_prompt="system",
        user_prompt="user",
        temperature=0.0,
        max_tokens=128,
        timeout=30,
        on_text=streamed.append,
    )

    assert captured["base_url"] == "http://example.com/v1"
    assert captured["model"] == "qwen3.5-27b"
    assert response["choices"][0]["message"]["content"] == "OK"
    assert streamed == ["OK"]
