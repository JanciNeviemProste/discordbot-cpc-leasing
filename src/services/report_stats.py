"""Pure funkcie pre výpočet stats z leadov + výpočet mesačného rozsahu.

Žiadne side-effects, žiadny DB / Discord IO — to robí ReportsCog. Sem patrí
len matematika, aby sa to dalo testovať bez mockovania.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

# Status order pre zobrazenie v reporte (logická sequence ako klient prechádza pipeline)
STATUS_ORDER = ["new", "contacted", "approved", "rejected", "sold"]

STATUS_LABELS_SK = {
    "new": "Nový",
    "contacted": "Kontaktovaný",
    "approved": "Schválený leasing",
    "rejected": "Zamietnutý",
    "sold": "Predaný",
}


@dataclass
class MonthlyStats:
    flipper_discord_id: str
    flipper_name: str
    period_start: datetime  # inclusive, UTC
    period_end: datetime    # exclusive, UTC
    total: int
    by_status: dict[str, int]  # každý status z STATUS_ORDER má kľúč (môže byť 0)
    total_commission: float  # EUR, sum cez všetky predané leady v období


def previous_month_range(today: datetime) -> tuple[datetime, datetime]:
    """Pre dnešný dátum vráti (start, end) predchádzajúceho mesiaca v UTC.

    start = 1. deň predchádzajúceho mesiaca 00:00 UTC (inclusive)
    end   = 1. deň aktuálneho mesiaca 00:00 UTC (exclusive)
    """
    today_utc = today.astimezone(timezone.utc) if today.tzinfo else today.replace(tzinfo=timezone.utc)
    end = today_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if end.month == 1:
        start = end.replace(year=end.year - 1, month=12)
    else:
        start = end.replace(month=end.month - 1)
    return start, end


def should_run_today(today: datetime) -> bool:
    """True iba na 1. dni v mesiaci — vtedy posielame report za predchádzajúci mesiac."""
    return today.day == 1


def compute_monthly_stats(
    *,
    flipper_discord_id: str,
    flipper_name: str,
    leads: list[dict[str, Any]],
    period_start: datetime,
    period_end: datetime,
) -> MonthlyStats:
    """Spočíta total + status breakdown. `leads` musia byť už filtrované podľa flippera
    a obdobia — táto funkcia len agreguje. Status mimo STATUS_ORDER ignoruje."""
    by_status = {s: 0 for s in STATUS_ORDER}
    total_commission = 0.0
    for lead in leads:
        status = lead.get("status")
        if status in by_status:
            by_status[status] += 1
        # commission_amount je NUMERIC v DB → môže prísť ako float, str alebo None
        commission = lead.get("commission_amount")
        if commission:
            total_commission += float(commission)
    return MonthlyStats(
        flipper_discord_id=flipper_discord_id,
        flipper_name=flipper_name,
        period_start=period_start,
        period_end=period_end,
        total=len(leads),
        by_status=by_status,
        total_commission=round(total_commission, 2),
    )


def format_period_sk(start: datetime, end: datetime) -> str:
    """Slovak human-readable rozsah pre PDF titulok / DM správu.
    Príklad: 'apríl 2026'."""
    months_sk = [
        "január", "február", "marec", "apríl", "máj", "jún",
        "júl", "august", "september", "október", "november", "december",
    ]
    # period_start je 1. deň target mesiaca
    return f"{months_sk[start.month - 1]} {start.year}"
