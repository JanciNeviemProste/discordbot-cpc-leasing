"""Unit testy pre src/services/sheets.py — čistá logika budovania riadku."""
from __future__ import annotations

from src.services.sheets import _HEADER, _STAV_OPTIONS, _build_row


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
