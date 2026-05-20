"""WhatsApp Cloud API integrácia (Meta Graph API).

Posiela template-based notifikácie Kristiánovi. Free tier: 1000 service
conversations / mes. Pri 30 leadoch/mes je to zadarmo.

Template setup (raz, v Meta Business Manager → WhatsApp Manager → Templates):
- Name: novy_lead
- Category: UTILITY  (transactional, schvaľuje sa rýchlo)
- Language: Slovak (sk)
- Body:
    🚗 *Nový lead — drive.sk*

    Klient: {{1}}
    Telefón: {{2}}
    Auto: {{3}}
    Flipper: {{4}}

    Otvor v Discorde: {{5}}

Parametre v poradí:
1. masked client name
2. phone (un-masked — Kristián potrebuje volať)
3. car description (značka model rok)
4. flipper meno
5. Discord message link
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from src.config import get_settings
from src.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class WhatsAppResult:
    success: bool
    message_id: str | None = None
    error: str | None = None
    raw_response: dict[str, Any] | None = None


class WhatsAppClient:
    """Async klient na Meta Graph API. Reuse cez singleton (init v bot.py)."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = httpx.AsyncClient(
            timeout=15.0,
            headers={
                "Authorization": f"Bearer {self.settings.whatsapp_access_token}",
                "Content-Type": "application/json",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def send_lead_notification(
        self,
        *,
        client_name: str,
        client_phone: str,
        car_description: str,
        flipper_name: str,
        discord_message_url: str,
    ) -> WhatsAppResult:
        """Pošli template notifikáciu o novom leade."""

        # Meta nepovoľuje URL s parametermi v body texte template-u —
        # button URL je v poriadku, ale my použijeme URL ako text parameter.
        # Niektoré znaky (newline, tab, > 4 medzery za sebou) sú zakázané v
        # template parametroch → sanitize.
        params = [
            _sanitize(client_name),
            _sanitize(client_phone),
            _sanitize(car_description),
            _sanitize(flipper_name),
            _sanitize(discord_message_url),
        ]

        payload = {
            "messaging_product": "whatsapp",
            "to": self.settings.whatsapp_recipient_number,
            "type": "template",
            "template": {
                "name": self.settings.whatsapp_template_name,
                "language": {"code": self.settings.whatsapp_template_lang},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": p} for p in params],
                    }
                ],
            },
        }

        return await self._post(payload)

    async def send_text(self, text: str) -> WhatsAppResult:
        """Free-form text — funguje LEN v 24h service window (po tom, čo
        Kristián poslal akúkoľvek správu botu v posledných 24h).
        Pre prvý kontakt vždy použi template."""
        payload = {
            "messaging_product": "whatsapp",
            "to": self.settings.whatsapp_recipient_number,
            "type": "text",
            "text": {"body": text},
        }
        return await self._post(payload)

    async def _post(self, payload: dict[str, Any]) -> WhatsAppResult:
        try:
            resp = await self._client.post(self.settings.whatsapp_api_url, json=payload)
        except httpx.RequestError as e:
            log.error("whatsapp.network_error", error=str(e))
            return WhatsAppResult(success=False, error=f"network: {e}")

        try:
            data = resp.json()
        except ValueError:
            data = {"raw": resp.text}

        if resp.status_code >= 400:
            err = data.get("error", {})
            log.error(
                "whatsapp.api_error",
                status=resp.status_code,
                error_code=err.get("code"),
                error_message=err.get("message"),
                error_details=err.get("error_data"),
            )
            return WhatsAppResult(
                success=False,
                error=f"{err.get('code', resp.status_code)}: {err.get('message', 'unknown')}",
                raw_response=data,
            )

        msg_id = None
        if "messages" in data and data["messages"]:
            msg_id = data["messages"][0].get("id")

        log.info("whatsapp.sent", message_id=msg_id)
        return WhatsAppResult(success=True, message_id=msg_id, raw_response=data)


def _sanitize(text: str) -> str:
    """Meta nepovoľuje newliny, taby a viac ako 4 medzery v template params."""
    if not text:
        return "-"
    cleaned = text.replace("\n", " ").replace("\t", " ").replace("\r", " ")
    # zbaľ viacero medzier do jednej
    while "  " in cleaned:
        cleaned = cleaned.replace("  ", " ")
    return cleaned.strip()[:1024]  # safety limit
