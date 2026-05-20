"""Unit testy compute_commission. Pure funkcia, žiadne mocky."""
from __future__ import annotations

import pytest

from src.services.commission import compute_commission


@pytest.mark.parametrize("price,rate,expected_amount", [
    (10000.0, 0.03, 300.00),
    (12500.0, 0.03, 375.00),
    (12500.0, 0.03, 375.00),
    (1.0, 0.5, 0.50),
    (1000000.0, 0.001, 1000.00),
])
def test_compute_normal_path(price: float, rate: float, expected_amount: float) -> None:
    rate_used, amount = compute_commission(car_price=price, rate=rate, fallback=0.0)
    assert rate_used == rate
    assert amount == expected_amount


@pytest.mark.parametrize("price", [None, 0, 0.0, -100.0])
def test_compute_uses_fallback_when_no_price(price: float | None) -> None:
    rate_used, amount = compute_commission(car_price=price, rate=0.03, fallback=50.0)
    assert rate_used == 0.0, "fallback path → rate=0 ako signál že sa nepoužil car_price"
    assert amount == 50.0


def test_compute_fallback_zero() -> None:
    rate_used, amount = compute_commission(car_price=None, rate=0.03, fallback=0.0)
    assert rate_used == 0.0
    assert amount == 0.0


def test_compute_rate_zero_results_in_zero_amount() -> None:
    # Edge case: ak Peter dodá pravidlá kde určitá kategória dostane 0 % — funguje
    rate_used, amount = compute_commission(car_price=10000.0, rate=0.0, fallback=99.0)
    # car_price > 0, ide normálnym path-om → rate ostáva 0, amount = 0
    assert rate_used == 0.0
    assert amount == 0.0


def test_compute_fallback_rounding() -> None:
    # Použijeme hodnotu mimo bank-rounding midpoint aby test bol stabilný
    rate_used, amount = compute_commission(car_price=None, rate=0.03, fallback=50.006)
    assert amount == 50.01
