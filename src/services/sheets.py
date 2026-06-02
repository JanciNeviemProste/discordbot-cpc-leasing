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
from gspread.utils import ValidationConditionType

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
    "Typ produktu",  # stĺpec H — dropdown, vyberá sa ručne v Sheete
    "Stav",          # stĺpec I — dropdown, default "Nový lead"
]

# Možnosti pre dropdowny v Sheete.
_PRODUKT_OPTIONS = ["Leasing", "PZP", "Kasko"]
_STAV_OPTIONS = ["Nový lead", "Kontaktovaný", "V procese", "Schválený", "Neschválený"]

_TZ = ZoneInfo("Europe/Bratislava")


def _sheet_safe(value: str) -> str:
    """Bunky začínajúce na = + - @ Google Sheets berie ako vzorec (a padne na
    #ERROR). Apostrof na začiatku vynúti text — Sheets ho nezobrazí."""
    if value and value[0] in "=+-@":
        return "'" + value
    return value


def _build_row(
    timestamp: str,
    client_name: str,
    client_email: str,
    client_phone: str,
    price: str,
    car_link: str,
    flipper_name: str,
) -> list[str]:
    """Zostav riadok v poradí podľa _HEADER. Typ produktu prázdny (vyberie sa
    v Sheete), Stav predvyplnený na prvú možnosť ('Nový lead')."""
    return [
        timestamp,
        client_name,
        client_email,
        client_phone,
        price,
        car_link,
        flipper_name,
        "",
        _STAV_OPTIONS[0],
    ]


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
        row = _build_row(
            timestamp,
            client_name,
            client_email,
            client_phone,
            price,
            car_link,
            flipper_name,
        )
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
        safe_row = [_sheet_safe(c) for c in row]
        ws.append_row(safe_row, value_input_option="USER_ENTERED")

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
        self._ensure_dropdowns(worksheet)
        self._worksheet = worksheet
        return worksheet

    def _ensure_header(self, worksheet: Any) -> None:
        """Zaisti, že hlavička sedí s _HEADER.

        - prázdny list → zapíš hlavičku
        - staršia (kratšia) hlavička → rozšír na aktuálnu (napr. 7 → 9 stĺpcov)
        - inak nechaj tak (neprepisujeme prípadné úpravy)
        """
        first_row = worksheet.row_values(1)
        if not first_row:
            worksheet.append_row(_HEADER, value_input_option="USER_ENTERED")
        elif len(first_row) < len(_HEADER):
            worksheet.update(
                [_HEADER], "A1", value_input_option="USER_ENTERED"
            )

    def _ensure_dropdowns(self, worksheet: Any) -> None:
        """Nastav dropdown validáciu na stĺpce Typ produktu (H) a Stav (I).
        Best-effort — zlyhanie nezablokuje zápis leadov."""
        try:
            worksheet.add_validation(
                "H2:H1000", ValidationConditionType.one_of_list,
                _PRODUKT_OPTIONS, strict=True, showCustomUi=True,
            )
            worksheet.add_validation(
                "I2:I1000", ValidationConditionType.one_of_list,
                _STAV_OPTIONS, strict=True, showCustomUi=True,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("sheets.validation_failed", error=str(e))
