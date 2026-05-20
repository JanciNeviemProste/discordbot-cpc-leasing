"""GDPR maskovanie osobných údajov pre zobrazenie v Discord embedoch."""
from __future__ import annotations

import re


def mask_phone(phone: str) -> str:
    """+421 905 123 456  →  +421 9** *** 456

    Zachováva predvoľbu (+XXX X) a posledné 3 číslice, zvyšok maskuje.
    """
    if not phone:
        return ""

    digits = re.sub(r"\D", "", phone)
    if len(digits) < 6:
        return "*" * len(phone)

    if phone.strip().startswith("+"):
        prefix = "+" + digits[:3]
        rest = digits[3:]
    else:
        prefix = digits[:3]
        rest = digits[3:]

    last3 = rest[-3:]
    middle_count = len(rest) - 3
    masked_middle = ""
    chars_done = 0
    for i in range(middle_count):
        if chars_done == 1:
            masked_middle += " "
            chars_done = 0
        masked_middle += "*"
        chars_done += 1

    # Jednoduchšia, čitateľnejšia varianta:
    visible_first = rest[0] if rest else ""
    masked = "*" * max(0, middle_count - 1)
    formatted_masked = " ".join([masked[i : i + 3] for i in range(0, len(masked), 3)])

    return f"{prefix} {visible_first}{formatted_masked} {last3}".strip()


def mask_email(email: str) -> str:
    """jan.novak@gmail.com  →  j*****@gmail.com"""
    if not email or "@" not in email:
        return "*" * len(email) if email else ""

    local, domain = email.split("@", 1)
    if len(local) <= 1:
        masked_local = local
    else:
        masked_local = local[0] + "*" * (len(local) - 1)

    return f"{masked_local}@{domain}"


def mask_name(name: str) -> str:
    """Ján Novák  →  Ján N."""
    parts = name.strip().split()
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0]}."
