"""Unit testy pre src/services/sheets.py — čistá logika budovania riadku."""
from __future__ import annotations

from src.services.sheets import _HEADER, _STAV_OPTIONS, _build_row, _sheet_safe


def test_build_row_matches_header_length() -> None:
    row = _build_row(
        "2026-06-02 21:00", "Ján Novák", "jan@gmail.com", "+421905123456",
        "12 500 €", "https://autobazar.eu/123", "Janci",
    )
    assert len(row) == len(_HEADER)


def test_build_row_field_order() -> None:
    row = _build_row(
        "2026-06-02 21:00", "Ján Novák", "jan@gmail.com", "+421905123456",
        "12 500 €", "https://autobazar.eu/123", "Janci",
    )
    assert row[:7] == [
        "2026-06-02 21:00",
        "Ján Novák",
        "jan@gmail.com",
        "+421905123456",
        "12 500 €",
        "https://autobazar.eu/123",
        "Janci",
    ]


def test_build_row_defaults() -> None:
    row = _build_row("t", "n", "e", "p", "c", "l", "f")
    assert row[-2] == ""              # Typ produktu — prázdny, vyberie sa v Sheete
    assert row[-1] == "Nový lead"     # Stav — default prvá možnosť
    assert row[-1] == _STAV_OPTIONS[0]


def test_sheet_safe_guards_phone_plus() -> None:
    # +421... by Sheets bral ako vzorec → apostrof vynúti text
    assert _sheet_safe("+421 948 000 000") == "'+421 948 000 000"


def test_sheet_safe_leaves_normal_values() -> None:
    assert _sheet_safe("https://autobazar.eu/123") == "https://autobazar.eu/123"
    assert _sheet_safe("12 500 €") == "12 500 €"
    assert _sheet_safe("2026-06-03 00:15") == "2026-06-03 00:15"
    assert _sheet_safe("Nový lead") == "Nový lead"
    assert _sheet_safe("") == ""
