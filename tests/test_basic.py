"""Unit testy validátorov a GDPR maskovania."""
from __future__ import annotations

import pytest

from src.services.validators import (
    is_valid_email,
    is_valid_phone,
    is_valid_vin,
    normalize_phone,
)
from src.utils.gdpr import mask_email, mask_name, mask_phone


# ============================================================
# Validators
# ============================================================
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


# ============================================================
# GDPR masking
# ============================================================
def test_mask_phone_keeps_prefix_and_last3() -> None:
    masked = mask_phone("+421905123456")
    assert masked.startswith("+421")
    assert masked.endswith("456")
    assert "905" not in masked  # middle masked


def test_mask_email_preserves_domain() -> None:
    assert mask_email("jan.novak@gmail.com") == "j********@gmail.com"


def test_mask_email_short_local() -> None:
    assert mask_email("a@gmail.com") == "a@gmail.com"


def test_mask_name() -> None:
    assert mask_name("Ján Novák") == "Ján N."
    assert mask_name("Ján Karol Novák") == "Ján N."
    assert mask_name("Ján") == "Ján"
