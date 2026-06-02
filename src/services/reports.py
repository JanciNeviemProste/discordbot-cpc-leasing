"""Mesačná štatistika leadov — čisté funkcie (bez I/O, testovateľné).

Číta riadky z Google Sheetu (zoznam zoznamov hodnôt), počíta leady za daný
mesiac podľa stĺpca Dátum a rozpisuje ich podľa stĺpca Stav.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Indexy stĺpcov v spoločnej hlavičke (viď sheets._HEADER).
_COL_DATUM = 0   # "YYYY-MM-DD HH:MM"
_COL_STAV = 8    # stĺpec I (9. stĺpec)

SK_MESIACE = [
    "Január", "Február", "Marec", "Apríl", "Máj", "Jún",
    "Júl", "August", "September", "Október", "November", "December",
]


def month_label(year: int, month: int) -> str:
    """(2026, 5) → 'Máj 2026'."""
    return f"{SK_MESIACE[month - 1]} {year}"


@dataclass
class MonthStats:
    total: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    unknown: int = 0


def compute_stats(
    rows: list[list[str]],
    year: int,
    month: int,
    stav_options: list[str],
) -> MonthStats:
    """Spočítaj leady, ktorých Dátum spadá do roka/mesiaca, rozpísané po stave.

    Stav mimo `stav_options` (alebo prázdny) → `unknown`.
    """
    prefix = f"{year}-{month:02d}"
    stats = MonthStats(by_status={s: 0 for s in stav_options})

    for row in rows:
        if len(row) <= _COL_STAV:
            continue
        datum = row[_COL_DATUM].strip()
        if not datum.startswith(prefix):
            continue
        stats.total += 1
        stav = row[_COL_STAV].strip()
        if stav in stats.by_status:
            stats.by_status[stav] += 1
        else:
            stats.unknown += 1

    return stats


def format_report(stats: MonthStats, label: str, sheet_url: str | None = None) -> str:
    """Plain-text report pre Telegram (bez MarkdownV2 → netreba escapovať)."""
    lines = [
        f"📊 Mesačný report — {label}",
        "",
        f"Spolu leadov: {stats.total}",
    ]
    for stav, count in stats.by_status.items():
        lines.append(f"• {stav}: {count}")
    if stats.unknown:
        lines.append(f"• Bez stavu / iné: {stats.unknown}")
    if sheet_url:
        lines.append("")
        lines.append(f"📋 Tabuľka: {sheet_url}")
    return "\n".join(lines)
