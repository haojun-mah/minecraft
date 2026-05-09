"""Runtime configuration loaded from environment / .env."""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"

    artifacts_dir: Path = Field(default=Path("./artifacts"))
    db_path: Path = Field(default=Path("./jobs.db"))

    openai_api_key: str | None = None
    gemini_api_key: str | None = None
    exa_api_key: str | None = None
    exa_num_results: int = 8
    exa_image_links_per_result: int = 3
    exa_cache_ttl_days: int = 7
    fal_key: str | None = None


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
