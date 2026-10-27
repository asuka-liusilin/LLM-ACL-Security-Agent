"""运行配置（全部来自环境变量，绝不写入前端）。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

# 依次尝试加载根目录与 backend 目录下的 .env（后者优先覆盖）
for candidate in (PROJECT_ROOT / ".env", BACKEND_DIR / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=True)


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


@dataclass(frozen=True)
class Settings:
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout: float = 30.0
    step_delay: float = 0.18
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def api_mode_available(self) -> bool:
        return bool(self.llm_api_key)

    def mask_key(self) -> str:
        if not self.llm_api_key:
            return ""
        key = self.llm_api_key
        return f"{key[:4]}***{key[-4:]}" if len(key) > 8 else "***"


def load_settings() -> Settings:
    return Settings(
        llm_api_key=_env("LLM_API_KEY"),
        llm_base_url=_env("LLM_BASE_URL", "https://api.openai.com/v1") or "https://api.openai.com/v1",
        llm_model=_env("LLM_MODEL", "gpt-4o-mini") or "gpt-4o-mini",
        llm_timeout=float(_env("LLM_TIMEOUT", "30") or 30),
        step_delay=float(_env("AGENT_STEP_DELAY", "0.18") or 0.18),
        cors_origins=_env("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"),
    )


settings = load_settings()
