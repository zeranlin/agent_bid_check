from app.config import ReviewSettings


def test_review_settings_from_dict_converts_numeric_fields() -> None:
    settings = ReviewSettings.from_dict(
        {
            "base_url": "http://example.com/v1",
            "model": "demo",
            "api_key": "k",
            "temperature": "0.3",
            "max_tokens": "1024",
            "timeout": "1800",
            "system_prompt": "s",
            "user_prompt": "u",
        }
    )
    assert settings.base_url == "http://example.com/v1"
    assert settings.temperature == 0.3
    assert settings.max_tokens == 1024
    assert settings.timeout == 1800


def test_review_settings_to_form_dict_returns_strings() -> None:
    settings = ReviewSettings()
    form = settings.to_form_dict()
    assert isinstance(form["temperature"], str)
    assert isinstance(form["max_tokens"], str)
    assert isinstance(form["timeout"], str)
