"""Runtime configuration loaded from environment / .env."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

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

    openai_image_model: str = "gpt-image-1"
    openai_image_quality: Literal["low", "medium", "high", "auto"] = "medium"
    openai_image_output_format: Literal["png", "jpeg", "webp"] = "png"
    openai_image_background: Literal["opaque", "auto"] = "opaque"
    openai_image_moderation: Literal["auto", "low"] = "auto"
    openai_image_candidate_count: int = Field(
        default=2,
        ge=1,
        le=10,
        description="How many hero-image candidates to request before picking one.",
    )
    openai_image_ranker_model: str = "gpt-4.1-mini"


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
