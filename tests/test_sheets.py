"""Unit testy pre src/services/sheets.py — mapovanie riadku + sheet-safe."""
from __future__ import annotations

from src.products import PRODUCTS
from src.services.sheets import _HEADER, _sheet_safe, build_row

_TS = "2026-06-03 10:00"


def _row(product_key: str, extras: dict[str, str]) -> list[str]:
    return build_row(
        PRODUCTS[product_key], _TS, "Ján Novák", "jan@gmail.com",
        "+421 948 000 000", extras, "Janci",
    )


def test_row_length_matches_header() -> None:
    row = _row("leasing", {"cena": "12 500 €", "car_link": "https://x.sk"})
    assert len(row) == len(_HEADER)


def test_common_columns() -> None:
    row = _row("pzp", {"vozidlo": "Škoda Octavia 2018", "ecv": "BA123AB"})
    assert row[0] == _TS
    assert row[1] == "Ján Novák"
    assert row[2] == "jan@gmail.com"
    assert row[3] == "+421 948 000 000"
    assert row[4] == "PZP"            # Typ produktu = product.typ
    assert row[-2] == "Janci"         # Flipper
    assert row[-1] == "Nový lead"     # Stav default


def test_leasing_mapping() -> None:
    # Predmet=link (F, idx5), Cena/hodnota=cena (G, idx6), Doplnok prázdny (H, idx7)
    row = _row("leasing", {"cena": "12 500 €", "car_link": "https://autobazar.eu/1"})
    assert row[5] == "https://autobazar.eu/1"
    assert row[6] == "12 500 €"
    assert row[7] == ""


def test_pzp_mapping() -> None:
    # Predmet=vozidlo, Suma prázdna, Doplnok=EČV
    row = _row("pzp", {"vozidlo": "Škoda Octavia 2018", "ecv": "BA123AB"})
    assert row[5] == "Škoda Octavia 2018"
    assert row[6] == ""
    assert row[7] == "BA123AB"


def test_kasko_mapping() -> None:
    # Predmet=vozidlo, Suma=hodnota, Doplnok prázdny
    row = _row("kasko", {"vozidlo": "BMW 320d 2020", "hodnota": "15 000 €"})
    assert row[5] == "BMW 320d 2020"
    assert row[6] == "15 000 €"
    assert row[7] == ""


def test_ine_mapping() -> None:
    # Predmet=popis, Suma prázdna, Doplnok=poznámka
    row = _row("ine", {"popis": "investičné poistenie", "poznamka": "volať večer"})
    assert row[5] == "investičné poistenie"
    assert row[6] == ""
    assert row[7] == "volať večer"


def test_sheet_safe_guards_phone_plus() -> None:
    assert _sheet_safe("+421 948 000 000") == "'+421 948 000 000"


def test_sheet_safe_leaves_normal_values() -> None:
    assert _sheet_safe("https://autobazar.eu/123") == "https://autobazar.eu/123"
    assert _sheet_safe("12 500 €") == "12 500 €"
    assert _sheet_safe("Nový lead") == "Nový lead"
    assert _sheet_safe("") == ""
