from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from app.common.core import DEFAULT_SYSTEM_PROMPT, DEFAULT_USER_PROMPT


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
EXAMPLES_DIR = DATA_DIR / "examples"
RUNS_DIR = DATA_DIR / "runs"
CONFIG_DIR = DATA_DIR / "config"
RESULTS_DIR = DATA_DIR / "results"
UPLOADS_DIR = DATA_DIR / "uploads"
JOBS_DIR = DATA_DIR / "jobs"
WEB_UPLOADS_DIR = UPLOADS_DIR / "v1"
WEB_RESULTS_DIR = RESULTS_DIR / "v1"
WEB_JOBS_DIR = JOBS_DIR / "v1"
WEB_CONFIG_PATH = CONFIG_DIR / "review_v1.json"
WEB_V2_UPLOADS_DIR = UPLOADS_DIR / "v2"
WEB_V2_RESULTS_DIR = RESULTS_DIR / "v2"
WEB_V2_JOBS_DIR = JOBS_DIR / "v2"
WEB_V2_CONFIG_PATH = CONFIG_DIR / "review_v2.json"
LEGACY_WEB_RUNS_DIR = DATA_DIR / "web_runs"
LEGACY_WEB_UPLOADS_DIR = LEGACY_WEB_RUNS_DIR / "uploads"
LEGACY_WEB_RESULTS_DIR = LEGACY_WEB_RUNS_DIR / "results"
LEGACY_WEB_JOBS_DIR = LEGACY_WEB_RUNS_DIR / "jobs"
LEGACY_WEB_CONFIG_PATH = LEGACY_WEB_RUNS_DIR / "review_config.json"


@dataclass
class ReviewSettings:
    base_url: str = "http://112.111.54.86:10011/v1"
    model: str = "qwen3.5-27b"
    api_key: str = "121212"
    temperature: float = 0.0
    max_tokens: int = 6400
    timeout: int = 1800
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    user_prompt: str = DEFAULT_USER_PROMPT

    @classmethod
    def from_env(cls) -> "ReviewSettings":
        settings = cls()
        settings.base_url = os.getenv("LLM_BASE_URL", settings.base_url)
        settings.model = os.getenv("LLM_MODEL", settings.model)
        settings.api_key = os.getenv("LLM_API_KEY", settings.api_key)
        return settings

    @classmethod
    def from_dict(cls, data: dict) -> "ReviewSettings":
        base = cls.from_env()
        return cls(
            base_url=str(data.get("base_url", base.base_url)),
            model=str(data.get("model", base.model)),
            api_key=str(data.get("api_key", base.api_key)),
            temperature=float(data.get("temperature", base.temperature)),
            max_tokens=int(data.get("max_tokens", base.max_tokens)),
            timeout=int(data.get("timeout", base.timeout)),
            system_prompt=str(data.get("system_prompt", base.system_prompt)),
            user_prompt=str(data.get("user_prompt", base.user_prompt)),
        )

    def to_form_dict(self) -> dict[str, str]:
        return {
            "base_url": self.base_url,
            "model": self.model,
            "api_key": self.api_key,
            "temperature": str(self.temperature),
            "max_tokens": str(self.max_tokens),
            "timeout": str(self.timeout),
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
        }

    def to_json_dict(self) -> dict[str, str]:
        return self.to_form_dict()


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    WEB_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    WEB_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    WEB_JOBS_DIR.mkdir(parents=True, exist_ok=True)
    WEB_V2_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    WEB_V2_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    WEB_V2_JOBS_DIR.mkdir(parents=True, exist_ok=True)
    LEGACY_WEB_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    LEGACY_WEB_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    LEGACY_WEB_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    LEGACY_WEB_JOBS_DIR.mkdir(parents=True, exist_ok=True)


def load_web_settings(path: Path = WEB_CONFIG_PATH) -> ReviewSettings:
    ensure_data_dirs()
    if not path.exists():
        legacy_path = LEGACY_WEB_CONFIG_PATH if path == WEB_CONFIG_PATH else None
        if legacy_path and legacy_path.exists():
            path = legacy_path
        else:
            return ReviewSettings.from_env()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ReviewSettings.from_env()
    if not isinstance(data, dict):
        return ReviewSettings.from_env()
    return ReviewSettings.from_dict(data)


def save_web_settings(settings: ReviewSettings, path: Path = WEB_CONFIG_PATH) -> None:
    ensure_data_dirs()
    path.write_text(json.dumps(settings.to_json_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
