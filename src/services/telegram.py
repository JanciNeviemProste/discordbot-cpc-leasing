"""Telegram Bot API integrácia.

Posiela notifikácie Kristiánovi cez jediný endpoint `POST /sendMessage`.
Žiadne template approval, žiadne conversation window — bot môže poslať
správu kedykoľvek (Kristián len musí botu raz napísať /start, alebo
musí byť bot v group chate kde Kristián je).

Setup:
- Vytvor bota cez @BotFather (/newbot) → ulož token ako TELEGRAM_BOT_TOKEN
- Kristián napíše /start botu (DM), alebo pridaj bota do group chatu
- Cez https://api.telegram.org/bot<TOKEN>/getUpdates zisti chat.id
  → ulož ako TELEGRAM_CHAT_ID
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from src.config import get_settings
from src.products import Product
from src.utils.logger import get_logger

log = get_logger(__name__)

# Znaky ktoré musí MarkdownV2 escapovať podľa Telegram Bot API docs.
_MD_V2_SPECIALS = r"_*[]()~`>#+-=|{}.!"


@dataclass
class TelegramResult:
    success: bool
    message_id: int | None = None
    error: str | None = None
    raw_response: dict[str, Any] | None = None


class TelegramClient:
    """Async klient na Telegram Bot API. Reuse cez singleton (init v bot.py)."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = httpx.AsyncClient(timeout=15.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def send_lead_notification(
        self,
        product: Product,
        *,
        client_name: str,
        client_phone: str,
        client_email: str,
        extras: dict[str, str],
        flipper_name: str,
    ) -> TelegramResult:
        """Pošli formátovanú správu o novej žiadosti (podľa typu produktu)."""
        sheet_id = self.settings.google_sheet_id
        sheet_url = (
            f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
            if sheet_id
            else None
        )
        text = _format_message(
            product=product,
            client_name=client_name,
            client_phone=client_phone,
            client_email=client_email,
            extras=extras,
            flipper_name=flipper_name,
            sheet_url=sheet_url,
        )
        return await self._post(text)

    async def _post(self, text: str) -> TelegramResult:
        url = (
            f"https://api.telegram.org/bot{self.settings.telegram_bot_token}"
            f"/sendMessage"
        )
        payload = {
            "chat_id": self.settings.telegram_chat_id,
            "text": text,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": False,
        }

        try:
            resp = await self._client.post(url, json=payload)
        except httpx.RequestError as e:
            log.error("telegram.network_error", error=str(e))
            return TelegramResult(success=False, error=f"network: {e}")

        try:
            data = resp.json()
        except ValueError:
            data = {"raw": resp.text}

        if resp.status_code >= 400 or not data.get("ok", False):
            description = data.get("description", f"HTTP {resp.status_code}")
            error_code = data.get("error_code", resp.status_code)
            log.error(
                "telegram.api_error",
                status=resp.status_code,
                error_code=error_code,
                description=description,
            )
            return TelegramResult(
                success=False,
                error=f"{error_code}: {description}",
                raw_response=data,
            )

        result = data.get("result", {})
        msg_id = result.get("message_id")
        log.info("telegram.sent", message_id=msg_id)
        return TelegramResult(success=True, message_id=msg_id, raw_response=data)


def _escape_markdown_v2(text: str) -> str:
    """Escapuj všetky MarkdownV2 special znaky v user-supplied textoch.

    Bez tohto by `.` v emaile alebo `-` v aute pádne Telegram parsing.
    """
    if not text:
        return "\\-"
    out: list[str] = []
    for ch in text:
        if ch in _MD_V2_SPECIALS:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def _format_message(
    *,
    product: Product,
    client_name: str,
    client_phone: str,
    client_email: str,
    extras: dict[str, str],
    flipper_name: str,
    sheet_url: str | None = None,
) -> str:
    """Markdown správa pre Kristiána podľa typu produktu. Hviezdičky okolo
    nadpisu sú formátovanie, ostatné texty escapnuté. Ak je sheet_url, pridá
    inline link na tabuľku (URL Sheetu nemá `)` ani `\\`)."""
    e = _escape_markdown_v2
    lines = [
        f"{product.emoji} *Nová žiadosť o {e(product.typ)} — drive\\.sk*",
        "",
        f"👤 Klient: {e(client_name)}",
        f"📞 Telefón: {e(client_phone)}",
        f"✉️ Email: {e(client_email)}",
    ]
    for ef in product.extras:
        value = extras.get(ef.key, "").strip()
        if not value and not ef.required:
            continue  # prázdne voliteľné pole vynechaj
        lines.append(f"• {e(ef.label)}: {e(value)}")
    lines.append(f"👨‍💼 Flipper: {e(flipper_name)}")

    msg = "\n".join(lines)
    if sheet_url:
        msg += f"\n\n[📊 Otvoriť tabuľku leadov]({sheet_url})"
    return msg
