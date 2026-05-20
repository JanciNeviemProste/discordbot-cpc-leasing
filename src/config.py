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
    discord_leads_channel_id: int
    discord_kristian_user_id: int
    discord_admin_role_id: int

    # ---- Supabase ----
    supabase_url: str
    supabase_service_key: str

    # ---- WhatsApp Cloud API ----
    whatsapp_phone_number_id: str
    whatsapp_access_token: str
    whatsapp_recipient_number: str
    whatsapp_template_name: str = "novy_lead"
    whatsapp_template_lang: str = "sk"
    whatsapp_api_version: str = "v21.0"

    # ---- App ----
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    environment: Literal["development", "production"] = "production"
    car_parser_timeout: int = 10

    # ---- Provízie ----
    # Placeholder pravidlo (% z car_price) kým Peter nedodá reálne pravidlá.
    # Mení sa jediným edit-om: src/services/commission.py:compute_commission.
    commission_default_rate: float = 0.03  # 3 %
    commission_fallback_amount: float = 0.0  # ak car_price chýba

    @property
    def whatsapp_api_url(self) -> str:
        return (
            f"https://graph.facebook.com/{self.whatsapp_api_version}"
            f"/{self.whatsapp_phone_number_id}/messages"
        )


@lru_cache
def get_settings() -> Settings:
    """Cached singleton — volaj cez get_settings() všade."""
    return Settings()  # type: ignore[call-arg]
