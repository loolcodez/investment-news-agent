from __future__ import annotations

import os
from pathlib import Path
from typing import List

import yaml
from pydantic import BaseModel, Field, HttpUrl, ValidationError


class FeedConfig(BaseModel):
    name: str
    url: HttpUrl
    enabled: bool = True


class LimitsConfig(BaseModel):
    max_items_per_run: int = Field(default=40, ge=1, le=500)
    min_keyword_hits: int = Field(default=1, ge=0, le=5)
    fallback_keep: int = Field(default=5, ge=0, le=50)
    request_timeout_seconds: int = Field(default=30, ge=5, le=120)


class ReportingConfig(BaseModel):
    archive: bool = True


class OpenAISettings(BaseModel):
    model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    temperature: float = Field(default_factory=lambda: float(os.getenv("OPENAI_TEMPERATURE", "0.2")))
    max_retries: int = Field(default_factory=lambda: int(os.getenv("OPENAI_MAX_RETRIES", "2")), ge=0, le=5)
    timeout_seconds: int = Field(default_factory=lambda: int(os.getenv("OPENAI_TIMEOUT", "45")), ge=5, le=120)


class AppConfig(BaseModel):
    watchlist: List[str]
    themes: List[str]
    rss_feeds: List[FeedConfig]
    limits: LimitsConfig = LimitsConfig()
    reporting: ReportingConfig = ReportingConfig()
    openai: OpenAISettings = OpenAISettings()

    @property
    def enabled_feeds(self) -> List[FeedConfig]:
        return [feed for feed in self.rss_feeds if feed.enabled]


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    """Load YAML config into validated AppConfig."""

    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text()) or {}

    try:
        return AppConfig(**raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid configuration: {exc}")
