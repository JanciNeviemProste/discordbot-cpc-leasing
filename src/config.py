"""Centralizovaná konfigurácia načítaná z prostredia (.env)."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Všetky env vars validované cez Pydantic. Pádne na štarte ak chýbajú."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Discord ----
    discord_token: str = Field(..., min_length=20)
    discord_guild_id: int
    discord_leasing_channel_id: int | None = None

    # ---- Telegram ----
    telegram_bot_token: str = Field(..., min_length=20)
    telegram_chat_id: str

    # ---- App ----
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    environment: Literal["development", "production"] = "production"


@lru_cache
def get_settings() -> Settings:
    """Cached singleton — volaj cez get_settings() všade."""
    return Settings()  # type: ignore[call-arg]
