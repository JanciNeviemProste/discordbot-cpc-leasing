"""Unit testy pre src/services/cofidis_calc.py — výpočet orientačnej splátky."""
from __future__ import annotations

import pytest

from src.services.cofidis_calc import (
    CalcError,
    base_rate,
    compute_installment,
    format_eur,
    format_pct,
    parse_amount,
    parse_months,
)


def test_matches_excel_example() -> None:
    # Autoritatívna kontrola vzorca: príklad z Calculator_COFIDIS_2026.xlsx.
    # cena 10000, akontácia 1000, 96 mes., sadzba 7,35 %, poistenie Basic → 137,49 €/mes.
    r = compute_installment(10000, 96, deposit=1000, rate=0.0735, insurance="Basic")
    assert r.monthly == 137.49
    assert r.loan_amount == 9000
    assert r.fee_eur == 180.0
    assert r.base_rate == 0.0735


def test_default_path_fixed_rate() -> None:
    # Hlavná cesta kalkulačky: cena + vlastné zdroje (10 %) + mesiace,
    # fixná sadzba 8,85 %, bez poistenia.
    r = compute_installment(10000, 96, deposit=1000)
    assert r.loan_amount == 9000.0
    assert r.fee_eur == 180.0
    assert r.base_rate == 0.0885
    assert r.monthly == 140.32


def test_default_path_shorter_term() -> None:
    r = compute_installment(12500, 72, deposit=1250)
    assert r.base_rate == 0.0885
    assert r.monthly == 214.06


@pytest.mark.parametrize(
    "months,expected",
    [
        (12, 0.072), (47, 0.072),
        (48, 0.072), (59, 0.072),
        (60, 0.0725), (71, 0.0725),
        (72, 0.0725), (83, 0.0725),
        (84, 0.0735), (96, 0.0735),
    ],
)
def test_base_rate_2026_buckets(months: int, expected: float) -> None:
    assert base_rate(months, 2026) == expected


def test_base_rate_older_car_is_higher() -> None:
    # Staršie auto = vyššia sadzba (stĺpec 2017 v tabuľke).
    assert base_rate(48, 2017) == 0.0885


@pytest.mark.parametrize(
    "text,expected",
    [
        ("12 500 €", 12500.0),
        ("12500", 12500.0),
        ("12.500", 12500.0),
        ("12 500,50", 12500.5),
        ("1 234,5", 1234.5),
        ("€9000", 9000.0),
        ("1.234.567", 1234567.0),
    ],
)
def test_parse_amount(text: str, expected: float) -> None:
    assert parse_amount(text) == expected


@pytest.mark.parametrize("bad", ["neviem", "", "   ", None])
def test_parse_amount_garbage_raises(bad: str | None) -> None:
    with pytest.raises(CalcError):
        parse_amount(bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("text,expected", [("72", 72), ("72 mes.", 72), ("96", 96)])
def test_parse_months(text: str, expected: int) -> None:
    assert parse_months(text) == expected


def test_parse_months_empty_raises() -> None:
    with pytest.raises(CalcError):
        parse_months("")


@pytest.mark.parametrize("months", [0, 6, 11, 97, 120])
def test_months_out_of_range_raises(months: int) -> None:
    with pytest.raises(CalcError):
        compute_installment(10000, months)


def test_parse_months_zero_then_compute_rejects() -> None:
    # "0" sa naparsuje na 0, ale compute_installment ho odmietne (mimo 12–96).
    assert parse_months("0") == 0
    with pytest.raises(CalcError):
        compute_installment(10000, parse_months("0"))


def test_min_loan_raises() -> None:
    # Akontácia 80 € = 10 % z 800 € (prejde cez 10 % pravidlo), ale úver 720 € < 1000 €.
    with pytest.raises(CalcError):
        compute_installment(800, 48, deposit=80)


def test_deposit_too_high_raises() -> None:
    with pytest.raises(CalcError):
        compute_installment(10000, 48, deposit=10000)


def test_deposit_below_10pct_raises() -> None:
    # 999 € < 10 % z 10000 € (1000 €) → chyba.
    with pytest.raises(CalcError):
        compute_installment(10000, 48, deposit=999)


def test_deposit_exactly_10pct_ok() -> None:
    # Presne 10 % prejde a použije sa fixná sadzba 8,85 %.
    r = compute_installment(10000, 48, deposit=1000)
    assert r.loan_amount == 9000.0
    assert r.base_rate == 0.0885


def test_long_term_old_car_not_available() -> None:
    # 84–96 mes. pre auto z 2014 nie je v tabuľke povolené (sadzba = None).
    with pytest.raises(CalcError):
        base_rate(96, 2014)


def test_format_eur() -> None:
    assert format_eur(1234.5) == "1 234,50 €"
    assert format_eur(189) == "189,00 €"
    assert format_eur(0) == "0,00 €"


def test_format_pct() -> None:
    assert format_pct(0.0735) == "7,35 %"
    assert format_pct(0.072) == "7,20 %"
