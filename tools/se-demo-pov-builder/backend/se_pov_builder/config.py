"""Application settings, read from SEPB_* environment variables.

Defaults are deliberately conservative: loopback binding, no LLM, mock adapters only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[2]

LLM_PROVIDERS = ("none", "ollama", "openai_compatible")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(f"SEPB_{name}", default).strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name, "")
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    database_url: str = ""
    content_dir: Path = TOOL_ROOT
    host: str = "127.0.0.1"
    port: int = 8000
    api_token: str = ""
    cors_origins: list[str] = field(default_factory=list)
    allow_sample_data: bool = True
    adapter_mode: str = "mock"
    frontend_dist: Path | None = None
    log_level: str = "INFO"
    llm_provider: str = "none"
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: str = ""
    llm_timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> Settings:
        data_dir = Path(_env("DATA_DIR", str(TOOL_ROOT / "data")))
        dist = _env("FRONTEND_DIST")
        origins = _env("CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
        settings = cls(
            database_url=_env("DATABASE_URL") or f"sqlite:///{data_dir / 'sepb.db'}",
            content_dir=Path(_env("CONTENT_DIR", str(TOOL_ROOT))),
            host=_env("HOST", "127.0.0.1"),
            port=int(_env("PORT", "8000")),
            api_token=_env("API_TOKEN"),
            cors_origins=[o.strip() for o in origins.split(",") if o.strip()],
            allow_sample_data=_env_bool("ALLOW_SAMPLE_DATA", True),
            adapter_mode=_env("ADAPTER_MODE", "mock").lower(),
            frontend_dist=Path(dist) if dist else None,
            log_level=_env("LOG_LEVEL", "INFO").upper(),
            llm_provider=_env("LLM_PROVIDER", "none").lower(),
            llm_base_url=_env("LLM_BASE_URL"),
            llm_model=_env("LLM_MODEL"),
            llm_api_key=_env("LLM_API_KEY"),
            llm_timeout_seconds=float(_env("LLM_TIMEOUT_SECONDS", "60")),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.adapter_mode != "mock":
            raise ValueError(
                "SEPB_ADAPTER_MODE must be 'mock'. Live adapters are not implemented; they "
                "will be added only after verification against official documentation."
            )
        if self.llm_provider not in LLM_PROVIDERS:
            raise ValueError(f"SEPB_LLM_PROVIDER must be one of {', '.join(LLM_PROVIDERS)}")
        if self.llm_provider != "none" and not (self.llm_base_url and self.llm_model):
            raise ValueError("SEPB_LLM_BASE_URL and SEPB_LLM_MODEL are required when an LLM is enabled")
