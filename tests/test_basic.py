"""Unit testy validátorov."""
from __future__ import annotations

import pytest

from src.services.validators import (
    format_phone_pretty,
    is_url,
    is_valid_email,
    is_valid_phone,
    is_valid_vin,
    looks_like_price,
    normalize_phone,
)


@pytest.mark.parametrize("phone", [
    "+421 905 123 456",
    "+421905123456",
    "+420 723 456 789",
    "0905 123 456",
    "0905123456",
])
def test_phone_valid(phone: str) -> None:
    normalized = normalize_phone(phone)
    assert is_valid_phone(normalized), f"Expected {phone} → {normalized} to be valid"


@pytest.mark.parametrize("phone", [
    "",
    "abc",
    "123",
    "+999 123 456 789",
    "00000",
])
def test_phone_invalid(phone: str) -> None:
    assert not is_valid_phone(phone)


def test_normalize_short_sk_number() -> None:
    assert normalize_phone("0905 123 456") == "+421905123456"


@pytest.mark.parametrize("email,expected", [
    ("test@example.com", True),
    ("a.b+c@x.co.uk", True),
    ("noatsign.com", False),
    ("missing@domain", False),
    ("", False),
])
def test_email_validation(email: str, expected: bool) -> None:
    assert is_valid_email(email) is expected


def test_vin_validation() -> None:
    assert is_valid_vin("WAUZZZ8K1AA000001")
    assert not is_valid_vin("WAUIO8K1AA000001")  # contains I, O
    assert not is_valid_vin("TOO_SHORT")


@pytest.mark.parametrize("price,expected", [
    ("12500", True),
    ("12 500 €", True),
    ("12.5k", True),
    ("", False),
    ("zadarmo", False),
    ("€", False),
])
def test_looks_like_price(price: str, expected: bool) -> None:
    assert looks_like_price(price) is expected


@pytest.mark.parametrize("normalized,expected", [
    ("+421948000000", "+421 948 000 000"),
    ("+421905123456", "+421 905 123 456"),
    ("+420723456789", "+420 723 456 789"),
    ("12345", "12345"),               # fallback — neznámy tvar, nezmenené
    ("+421 948 000 000", "+421 948 000 000"),  # už s medzerami → fallback (nie 9 číslic)
])
def test_format_phone_pretty(normalized: str, expected: str) -> None:
    assert format_phone_pretty(normalized) == expected


def test_normalize_then_format_roundtrip() -> None:
    assert format_phone_pretty(normalize_phone("0948 000 000")) == "+421 948 000 000"


@pytest.mark.parametrize("link,expected", [
    ("https://www.autobazar.eu/inzerat/123", True),
    ("http://bazos.sk/auto", True),
    ("www.autobazar.eu", True),
    ("Audi A4 2019", False),
    ("", False),
])
def test_is_url(link: str, expected: bool) -> None:
    assert is_url(link) is expected
