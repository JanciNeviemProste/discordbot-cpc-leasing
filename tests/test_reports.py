"""Unit testy pre mesačnú štatistiku (src/services/reports.py)."""
from __future__ import annotations

from src.services.reports import compute_stats, format_report, month_label
from src.services.sheets import STAV_OPTIONS

# Riadok = spoločná hlavička: [Dátum, Meno, Email, Telefón, Cena, Link, Flipper, Typ, Stav]
def _row(datum: str, stav: str) -> list[str]:
    return [datum, "Klient", "e@x.sk", "+421 9", "1€", "url", "Flip", "", stav]


_ROWS = [
    _row("2026-05-03 10:00", "Nový lead"),
    _row("2026-05-10 11:00", "Nový lead"),
    _row("2026-05-15 09:00", "Schválený"),
    _row("2026-05-20 18:00", "Neschválený"),
    _row("2026-05-25 12:00", "V procese"),
    _row("2026-06-01 08:00", "Nový lead"),   # iný mesiac — nezapočíta sa
    _row("2026-05-28 12:00", ""),            # bez stavu → unknown
    ["2026-05-02 10:00"],                     # krátky riadok → ignoruj
]


def test_month_label() -> None:
    assert month_label(2026, 5) == "Máj 2026"
    assert month_label(2026, 1) == "Január 2026"
    assert month_label(2026, 12) == "December 2026"


def test_compute_stats_filters_month() -> None:
    s = compute_stats(_ROWS, 2026, 5, STAV_OPTIONS)
    assert s.total == 6  # 5 platných stavov + 1 bez stavu (jún a krátky riadok von)
    assert s.by_status["Nový lead"] == 2
    assert s.by_status["Schválený"] == 1
    assert s.by_status["Neschválený"] == 1
    assert s.by_status["V procese"] == 1
    assert s.by_status["Kontaktovaný"] == 0
    assert s.unknown == 1


def test_compute_stats_other_month_empty() -> None:
    s = compute_stats(_ROWS, 2026, 7, STAV_OPTIONS)
    assert s.total == 0
    assert all(v == 0 for v in s.by_status.values())


def test_format_report_contains_counts() -> None:
    s = compute_stats(_ROWS, 2026, 5, STAV_OPTIONS)
    text = format_report(s, month_label(2026, 5), "https://docs.google.com/x")
    assert "Máj 2026" in text
    assert "Spolu leadov: 6" in text
    assert "Nový lead: 2" in text
    assert "Schválený: 1" in text
    assert "https://docs.google.com/x" in text
