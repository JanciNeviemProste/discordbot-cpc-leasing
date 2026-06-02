"""Google Sheets evidencia leadov — trvalý záznam pre Petra (majiteľa).

Každý lead sa zapíše ako nový riadok. gspread je synchrónny, takže
blocking volania wrapujeme do `asyncio.to_thread`, aby nezablokovali
discord.py event loop.

Setup:
- Google Cloud → vytvor service account → stiahni JSON kľúč
- ulož kľúč ako secrets/google-service-account.json (gitignored)
- zdieľaj cieľový Sheet so service-account emailom ako Editor
- skopíruj Sheet ID z URL → GOOGLE_SHEET_ID
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import gspread
from google.oauth2.service_account import Credentials

from src.config import get_settings
from src.utils.logger import get_logger

log = get_logger(__name__)

# Sheets API scope — len spreadsheets, nič viac.
_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Hlavička, ktorú Peter uvidí. Poradie = poradie hodnôt v riadku nižšie.
_HEADER = [
    "Dátum",
    "Meno a priezvisko",
    "Email",
    "Telefón",
    "Cena",
    "Link na auto",
    "Flipper",
]

_TZ = ZoneInfo("Europe/Bratislava")


@dataclass
class SheetsResult:
    success: bool
    error: str | None = None


class SheetsClient:
    """Klient na zápis leadov do Google Sheetu. Worksheet handle je lazy +
    cachovaný — autentifikácia prebehne až pri prvom zápise."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._worksheet: Any | None = None

    async def append_lead(
        self,
        *,
        client_name: str,
        client_email: str,
        client_phone: str,
        price: str,
        car_link: str,
        flipper_name: str,
    ) -> SheetsResult:
        """Pridaj lead ako nový riadok. Best-effort — chyba nezablokuje flow."""
        timestamp = datetime.now(_TZ).strftime("%Y-%m-%d %H:%M")
        row = [
            timestamp,
            client_name,
            client_email,
            client_phone,
            price,
            car_link,
            flipper_name,
        ]
        try:
            await asyncio.to_thread(self._append_row_blocking, row)
        except Exception as e:  # noqa: BLE001
            log.error("sheets.append_failed", error=str(e))
            return SheetsResult(success=False, error=str(e))

        log.info("sheets.appended")
        return SheetsResult(success=True)

    # ---- blocking interné (bežia v thread executore) ----

    def _append_row_blocking(self, row: list[str]) -> None:
        ws = self._get_worksheet()
        ws.append_row(row, value_input_option="USER_ENTERED")

    def _get_worksheet(self) -> Any:
        if self._worksheet is not None:
            return self._worksheet

        creds = Credentials.from_service_account_file(
            self.settings.google_service_account_file,
            scopes=_SCOPES,
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(self.settings.google_sheet_id)
        worksheet = spreadsheet.sheet1
        self._ensure_header(worksheet)
        self._worksheet = worksheet
        return worksheet

    def _ensure_header(self, worksheet: Any) -> None:
        """Ak je list prázdny, zapíš hlavičku. Existujúcu neprepisujeme."""
        first_row = worksheet.row_values(1)
        if not first_row:
            worksheet.append_row(_HEADER, value_input_option="USER_ENTERED")
