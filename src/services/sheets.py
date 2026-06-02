"""Google Sheets evidencia leadov — trvalý záznam pre Petra (majiteľa).

Jeden spoločný hárok pre všetky typy (Leasing/PZP/Kasko/Iné); produktovo-
špecifické polia sa mapujú do generických stĺpcov Predmet/Suma/Doplnok.
gspread je synchrónny, blocking volania wrapujeme do `asyncio.to_thread`.
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
from src.products import (
    COLUMN_DOPLNOK,
    COLUMN_PREDMET,
    COLUMN_SUMA,
    PRODUCT_TYP_OPTIONS,
    Product,
)
from src.utils.logger import get_logger

log = get_logger(__name__)

# Sheets API scope — len spreadsheets, nič viac.
_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Spoločná hlavička (10 stĺpcov A–J).
_HEADER = [
    "Dátum",                    # A
    "Meno a priezvisko",        # B
    "Email",                    # C
    "Telefón",                  # D
    "Typ produktu",             # E — dropdown
    "Predmet (auto/vozidlo)",   # F
    "Cena / hodnota",           # G
    "Doplnok (EČV/pozn.)",      # H
    "Flipper",                  # I
    "Stav",                     # J — dropdown, default "Nový lead"
]
_LAST_COL = "J"

_STAV_OPTIONS = ["Nový lead", "Kontaktovaný", "V procese", "Schválený", "Neschválený"]

_TZ = ZoneInfo("Europe/Bratislava")


def _sheet_safe(value: str) -> str:
    """Bunky začínajúce na = + - @ Google Sheets berie ako vzorec (a padne na
    #ERROR). Apostrof na začiatku vynúti text — Sheets ho nezobrazí."""
    if value and value[0] in "=+-@":
        return "'" + value
    return value


def build_row(
    product: Product,
    timestamp: str,
    client_name: str,
    client_email: str,
    client_phone: str,
    extras: dict[str, str],
    flipper_name: str,
) -> list[str]:
    """Zostav riadok podľa _HEADER. Extra polia produktu sa mapujú do
    generických stĺpcov (predmet/suma/doplnok); Typ produktu = product.typ;
    Stav default 'Nový lead'."""
    buckets = {COLUMN_PREDMET: "", COLUMN_SUMA: "", COLUMN_DOPLNOK: ""}
    for ef in product.extras:
        buckets[ef.column] = extras.get(ef.key, "")
    return [
        timestamp,
        client_name,
        client_email,
        client_phone,
        product.typ,
        buckets[COLUMN_PREDMET],
        buckets[COLUMN_SUMA],
        buckets[COLUMN_DOPLNOK],
        flipper_name,
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
        product: Product,
        *,
        client_name: str,
        client_email: str,
        client_phone: str,
        extras: dict[str, str],
        flipper_name: str,
    ) -> SheetsResult:
        """Pridaj lead ako nový riadok. Best-effort — chyba nezablokuje flow."""
        timestamp = datetime.now(_TZ).strftime("%Y-%m-%d %H:%M")
        row = build_row(
            product, timestamp, client_name, client_email, client_phone,
            extras, flipper_name,
        )
        try:
            await asyncio.to_thread(self._append_row_blocking, row)
        except Exception as e:  # noqa: BLE001
            log.error("sheets.append_failed", error=str(e))
            return SheetsResult(success=False, error=str(e))

        log.info("sheets.appended", typ=product.typ)
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
        self._ensure_formatting(worksheet)
        self._worksheet = worksheet
        return worksheet

    def _ensure_header(self, worksheet: Any) -> None:
        """Zaisti, že hlavička presne sedí s _HEADER.

        - prázdny list → zapíš hlavičku
        - iná hlavička → prepíš riadok 1 (kvôli zmene schémy)
        """
        first_row = worksheet.row_values(1)
        if not first_row:
            worksheet.append_row(_HEADER, value_input_option="USER_ENTERED")
        elif first_row != _HEADER:
            worksheet.update([_HEADER], "A1", value_input_option="USER_ENTERED")

    def _ensure_dropdowns(self, worksheet: Any) -> None:
        """Dropdowny: Typ produktu (E) a Stav (J). Best-effort."""
        try:
            worksheet.add_validation(
                "E2:E1000", ValidationConditionType.one_of_list,
                PRODUCT_TYP_OPTIONS, strict=True, showCustomUi=True,
            )
            worksheet.add_validation(
                "J2:J1000", ValidationConditionType.one_of_list,
                _STAV_OPTIONS, strict=True, showCustomUi=True,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("sheets.validation_failed", error=str(e))

    def _ensure_formatting(self, worksheet: Any) -> None:
        """Vycentrovať tabuľku + tučná zafixovaná hlavička. Best-effort."""
        try:
            worksheet.format(
                f"A1:{_LAST_COL}1",
                {"textFormat": {"bold": True}, "horizontalAlignment": "CENTER"},
            )
            worksheet.format(
                f"A2:{_LAST_COL}1000",
                {"horizontalAlignment": "CENTER"},
            )
            worksheet.freeze(rows=1)
        except Exception as e:  # noqa: BLE001
            log.warning("sheets.formatting_failed", error=str(e))
