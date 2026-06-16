"""Výpočet orientačnej mesačnej splátky úveru cez Cofidis.

Vzorce a sadzby sú prevzaté 1:1 z `Calculator_COFIDIS_2026.xlsx` (skrytý hárok
`Calculation`). Overené na príklade z excelu:
    cena 10000, akontácia 1000, 96 mes., poistenie Basic → 137,49 €/mes.

Modul je čisto výpočtový (žiadny discord/IO) — len standard library, aby sa dal
jednoducho testovať a prípadne neskôr rozšíriť (akontácia, rok výroby, poistenie).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

# ── Konštanty produktu „SPECIAL" (z hárka Kalkulacka, riadok M16:P17) ──────────
COMMISSION = 500.0   # provízia (fixná, „not modifiable") — vstupuje do istiny
FEE_PCT = 0.02       # spracovateľský poplatok = 2 % z výšky úveru
MIN_LOAN = 1000.0    # min. výška úveru
MIN_MONTHS = 12
MAX_MONTHS = 96
FIXED_RATE = 0.0885       # fixná orientačná úroková sadzba (8,85 %)
MIN_DEPOSIT_PCT = 0.10    # min. vlastné zdroje = 10 % z ceny vozidla

# Roky výroby (stĺpce tabuľky sadzieb „2026 CFS", R17:AE17).
YEARS = [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015, 2014, 2013]

# Základná úroková sadzba podľa (doba splatnosti × rok výroby).
# Kľúč = horná hranica pásma mesiacov; hodnota = sadzba pre každý rok v `YEARS`.
# `None` = kombinácia nie je povolená (napr. 84–96 mes. pre auto staršie než 2016).
RATE_TABLE: dict[int, list[float | None]] = {
    47: [0.072, 0.072, 0.072, 0.072, 0.072, 0.075, 0.075, 0.075, 0.075, 0.0885, 0.0885, 0.0885, 0.0885, 0.0885],
    59: [0.072, 0.072, 0.072, 0.072, 0.072, 0.075, 0.075, 0.075, 0.075, 0.0885, 0.0885, 0.0885, 0.0885, 0.0885],
    71: [0.0725, 0.0725, 0.0725, 0.0725, 0.0725, 0.0755, 0.0755, 0.0755, 0.0755, 0.089, 0.089, 0.089, 0.089, 0.09],
    83: [0.0725, 0.0725, 0.0725, 0.0725, 0.0725, 0.0755, 0.0755, 0.0755, 0.0755, 0.089, 0.089, 0.09, 0.09, 0.0925],
    96: [0.0735, 0.0735, 0.0735, 0.0735, 0.0735, 0.076, 0.076, 0.076, 0.076, 0.0895, 0.0895, None, None, None],
}
_BUCKETS = (47, 59, 71, 83, 96)

# Balíky poistenia (J3:L6) — % z mesačnej splátky. „Bez" = bez poistenia.
INSURANCE_RATES = {
    "Bez": 0.0,
    "Light": 0.018,
    "Standard": 0.0499,
    "Senior": 0.0699,
    "Basic": 0.0333,
}


class CalcError(ValueError):
    """Chyba vstupu kalkulačky. Správa je formulovaná priamo pre flippera."""


@dataclass(frozen=True)
class Installment:
    """Výsledok výpočtu — orientačné hodnoty."""

    monthly: float       # orientačná mesačná splátka (€)
    loan_amount: float   # výška úveru = cena − akontácia (€)
    fee_eur: float       # spracovateľský poplatok (€)
    base_rate: float     # použitá základná úroková sadzba (napr. 0.0735)
    months: int


def _round2(x: float) -> float:
    """Zaokrúhli na 2 desatinné (half-up) — ako Excel ROUND."""
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _ceil2(x: float) -> float:
    """Zaokrúhli nahor na 2 desatinné — ako Excel ROUNDUP."""
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_CEILING))


def base_rate(months: int, year: int = 2026) -> float:
    """Základná úroková sadzba z tabuľky podľa doby splatnosti a roku výroby.

    Rok mimo tabuľky sa oreže na najbližší dostupný (najnovší/najstarší).
    """
    if year > YEARS[0]:
        year = YEARS[0]
    elif year < YEARS[-1]:
        year = YEARS[-1]
    col = YEARS.index(year)
    for upper in _BUCKETS:
        if months <= upper:
            rate = RATE_TABLE[upper][col]
            if rate is None:
                raise CalcError(
                    f"Pre auto z roku {year} nie je doba {months} mes. dostupná "
                    "(dlhšie doby sú len pre novšie autá)."
                )
            return rate
    raise CalcError(f"Doba {months} mes. je mimo rozsahu {MIN_MONTHS}–{MAX_MONTHS}.")


def compute_installment(
    price: float,
    months: int,
    *,
    deposit: float = 0.0,
    rate: float = FIXED_RATE,
    insurance: str = "Bez",
) -> Installment:
    """Orientačná mesačná splátka. Predvolene: fixná sadzba 8,85 %, bez poistenia.
    Vyžaduje vlastné zdroje (akontáciu) aspoň 10 % z ceny vozidla."""
    if months < MIN_MONTHS or months > MAX_MONTHS:
        raise CalcError(
            f"Počet mesiacov musí byť {MIN_MONTHS}–{MAX_MONTHS} (zadané: {months})."
        )
    if price <= 0:
        raise CalcError("Cena vozidla musí byť kladné číslo.")
    if deposit < 0 or deposit >= price:
        raise CalcError("Vlastné zdroje musia byť medzi 0 € a cenou vozidla.")

    min_deposit = _round2(price * MIN_DEPOSIT_PCT)
    if deposit < min_deposit:
        raise CalcError(
            f"Pri tomto leasingu potrebuješ aspoň 10 % vlastných zdrojov — pri cene "
            f"{format_eur(price)} je to minimálne {format_eur(min_deposit)} "
            f"(zadané: {format_eur(deposit)})."
        )

    financed = price - deposit
    if financed < MIN_LOAN:
        raise CalcError(f"Výška úveru musí byť aspoň {int(MIN_LOAN)} €.")

    fee_eur = _round2(financed * FEE_PCT)
    principal = financed + COMMISSION       # provízia zarátaná do istiny
    r = rate / 12
    pmt = _round2(principal * r / (1 - (1 + r) ** (-months)))   # anuita
    fee_month = _ceil2(fee_eur / months)
    base_instalment = pmt + fee_month
    ins_rate = INSURANCE_RATES.get(insurance, 0.0)
    ins_month = _round2(base_instalment * ins_rate) if ins_rate else 0.0
    monthly = _round2(pmt + fee_month + ins_month)

    return Installment(
        monthly=monthly,
        loan_amount=financed,
        fee_eur=fee_eur,
        base_rate=rate,
        months=months,
    )


def parse_amount(text: str) -> float:
    """Z textu („12 500 €", „12500", „12.500", „12 500,50") vytiahne sumu v €.

    Akceptuje medzery a oddeľovače tisícov (`.`/medzera) aj desatinnú čiarku/bodku.
    """
    s = re.sub(r"[^\d.,]", "", (text or "").strip())
    if not s:
        raise CalcError(f"Neviem prečítať sumu: `{text}`. Zadaj napr. `12 500`.")

    has_dot, has_comma = "." in s, "," in s
    if has_dot and has_comma:
        # Posledný výskyt je desatinný oddeľovač, ten druhý tisícový.
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        thou = "," if dec == "." else "."
        s = s.replace(thou, "").replace(dec, ".")
    elif has_comma:
        s = _resolve_single_sep(s, ",")
    elif has_dot:
        s = _resolve_single_sep(s, ".")

    try:
        return float(s)
    except ValueError as exc:
        raise CalcError(f"Neviem prečítať sumu: `{text}`.") from exc


def _resolve_single_sep(s: str, sep: str) -> str:
    """Jeden druh oddeľovača — rozhodne, či je desatinný alebo tisícový."""
    parts = s.split(sep)
    # Práve dve časti a po oddeľovači NIE sú 3 číslice → desatinné (12,5 / 12.50).
    if len(parts) == 2 and len(parts[1]) != 3:
        return s.replace(sep, ".")
    # Inak tisícový oddeľovač (12.500 / 1.234.567 / 12,000).
    return s.replace(sep, "")


def parse_months(text: str) -> int:
    """Z textu („72", „72 mes.") vytiahne počet mesiacov ako celé číslo."""
    digits = re.sub(r"[^\d]", "", (text or "").strip())
    if not digits:
        raise CalcError("Zadaj počet mesiacov ako číslo, napr. `72`.")
    return int(digits)


def format_eur(value: float) -> str:
    """1234.5 → „1 234,50 €" (medzera = tisíce, čiarka = desatiny)."""
    formatted = f"{value:,.2f}".replace(",", " ").replace(".", ",")
    return f"{formatted} €"


def format_pct(rate: float) -> str:
    """0.0735 → „7,35 %"."""
    return f"{rate * 100:.2f}".replace(".", ",") + " %"
