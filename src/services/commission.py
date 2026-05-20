"""Výpočet provízie pre flippera pri prechode lead-u na status='sold'.

ENTRY POINT pre prepísanie pravidiel: keď Peter dodá reálne pravidlá, prepíš
JEDINE túto funkciu (alebo prepoj na tier-tabuľku). DB schema (commission_amount,
commission_rate) je generická a netreba ju meniť.

Aktuálne placeholder pravidlo: % z car_price (rate konfigurovateľný cez
COMMISSION_DEFAULT_RATE env var, default 3 %).
"""
from __future__ import annotations


def compute_commission(
    *, car_price: float | None, rate: float, fallback: float
) -> tuple[float, float]:
    """Vráti (rate_použitý, amount) v EUR.

    Args:
        car_price: cena auta z leadu (môže byť None ak parser zlyhal a Kristián
            cenu nedoplnil ručne).
        rate: zlomková sadzba (napr. 0.03 = 3 %). Z `settings.commission_default_rate`.
        fallback: suma použitá ak car_price nie je k dispozícii. Default 0 — Kristián
            potom vidí 0 € v DM a vie že má doplniť cenu manuálne.

    Returns:
        (rate_used, amount). `rate_used == 0` keď sa použil fallback path — znak že
        výpočet nebol opretý o car_price.
    """
    if car_price is None or car_price <= 0:
        return (0.0, round(fallback, 2))
    return (rate, round(car_price * rate, 2))
