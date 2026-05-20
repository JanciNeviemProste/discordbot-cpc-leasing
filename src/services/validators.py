"""Validátori vstupných údajov (telefón, email, VIN)."""
from __future__ import annotations

import re

# SK: +421 9XX XXX XXX alebo 09XX XXX XXX
# CZ: +420 XXX XXX XXX alebo 0XXX XXX XXX (rare)
PHONE_PATTERN = re.compile(
    r"^(?:\+?(?:421|420)|0)\s?[1-9](?:[\s\-]?\d){8}$"
)

EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)

# VIN: 17 znakov, bez I, O, Q
VIN_PATTERN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


def normalize_phone(phone: str) -> str:
    """Odstráň medzery/pomlčky, doplň +421 ak chýba prefix."""
    cleaned = re.sub(r"[\s\-]", "", phone.strip())
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    elif cleaned.startswith("0") and len(cleaned) == 10:
        # 0905... → +421905...
        cleaned = "+421" + cleaned[1:]
    elif not cleaned.startswith("+"):
        # holé číslo bez prefixu, predpokladaj SK
        if len(cleaned) == 9:
            cleaned = "+421" + cleaned
    return cleaned


def is_valid_phone(phone: str) -> bool:
    if not phone:
        return False
    return bool(PHONE_PATTERN.match(phone.strip()))


def is_valid_email(email: str) -> bool:
    if not email:
        return False
    return bool(EMAIL_PATTERN.match(email.strip()))


def is_valid_vin(vin: str) -> bool:
    if not vin:
        return False
    return bool(VIN_PATTERN.match(vin.strip().upper()))


def is_url(text: str) -> bool:
    """Hrubá detekcia či input je URL alebo voľný text."""
    t = text.strip().lower()
    return t.startswith("http://") or t.startswith("https://") or t.startswith("www.")
