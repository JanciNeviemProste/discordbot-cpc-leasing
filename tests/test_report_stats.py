"""Unit testy pre mesačné reporty — stats compute, period range, PDF smoke."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.services.pdf_report import build_monthly_report_pdf
from src.services.report_stats import (
    STATUS_ORDER,
    compute_monthly_stats,
    format_period_sk,
    previous_month_range,
    should_run_today,
)


# ============================================================
# previous_month_range
# ============================================================
def test_previous_month_range_mid_year() -> None:
    today = datetime(2026, 5, 20, tzinfo=timezone.utc)
    start, end = previous_month_range(today)
    assert start == datetime(2026, 4, 1, tzinfo=timezone.utc)
    assert end == datetime(2026, 5, 1, tzinfo=timezone.utc)


def test_previous_month_range_january_wraps_to_previous_year() -> None:
    today = datetime(2026, 1, 1, tzinfo=timezone.utc)
    start, end = previous_month_range(today)
    assert start == datetime(2025, 12, 1, tzinfo=timezone.utc)
    assert end == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_previous_month_range_naive_datetime_treated_as_utc() -> None:
    today = datetime(2026, 3, 15)  # naive
    start, end = previous_month_range(today)
    assert start == datetime(2026, 2, 1, tzinfo=timezone.utc)
    assert end == datetime(2026, 3, 1, tzinfo=timezone.utc)


# ============================================================
# should_run_today
# ============================================================
@pytest.mark.parametrize("day,expected", [(1, True), (2, False), (15, False), (31, False)])
def test_should_run_today(day: int, expected: bool) -> None:
    assert should_run_today(datetime(2026, 5, day, tzinfo=timezone.utc)) is expected


# ============================================================
# compute_monthly_stats
# ============================================================
def _lead(status: str) -> dict:
    return {"status": status}


def test_compute_stats_empty_leads_returns_zero_totals() -> None:
    stats = compute_monthly_stats(
        flipper_discord_id="123",
        flipper_name="jano",
        leads=[],
        period_start=datetime(2026, 4, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    assert stats.total == 0
    assert all(stats.by_status[s] == 0 for s in STATUS_ORDER)
    assert stats.total_commission == 0.0


def test_compute_stats_counts_status_breakdown() -> None:
    leads = [
        _lead("new"), _lead("new"),
        _lead("contacted"),
        _lead("sold"), _lead("sold"), _lead("sold"),
        _lead("rejected"),
    ]
    stats = compute_monthly_stats(
        flipper_discord_id="123",
        flipper_name="jano",
        leads=leads,
        period_start=datetime(2026, 4, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    assert stats.total == 7
    assert stats.by_status["new"] == 2
    assert stats.by_status["contacted"] == 1
    assert stats.by_status["sold"] == 3
    assert stats.by_status["rejected"] == 1
    assert stats.by_status["approved"] == 0


def test_compute_stats_sums_commission_across_leads() -> None:
    leads = [
        {"status": "sold", "commission_amount": 300.00},
        {"status": "sold", "commission_amount": 450.50},
        {"status": "new", "commission_amount": None},  # nezapočítava
        {"status": "rejected", "commission_amount": 0},  # nezapočítava
    ]
    stats = compute_monthly_stats(
        flipper_discord_id="123",
        flipper_name="jano",
        leads=leads,
        period_start=datetime(2026, 4, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    assert stats.total_commission == 750.50


def test_compute_stats_commission_accepts_string_numeric() -> None:
    # Supabase NUMERIC sa môže vrátiť ako string (postgrest serializácia)
    leads = [{"status": "sold", "commission_amount": "123.45"}]
    stats = compute_monthly_stats(
        flipper_discord_id="123",
        flipper_name="jano",
        leads=leads,
        period_start=datetime(2026, 4, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    assert stats.total_commission == 123.45


def test_compute_stats_ignores_unknown_status() -> None:
    leads = [_lead("new"), _lead("bizarre"), _lead("sold")]
    stats = compute_monthly_stats(
        flipper_discord_id="123",
        flipper_name="jano",
        leads=leads,
        period_start=datetime(2026, 4, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    # total ráta všetky leady (vrátane bizarre), ale by_status len známe
    assert stats.total == 3
    assert sum(stats.by_status.values()) == 2


# ============================================================
# format_period_sk
# ============================================================
def test_format_period_sk_returns_slovak_month_name() -> None:
    out = format_period_sk(
        datetime(2026, 4, 1, tzinfo=timezone.utc),
        datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    assert out == "apríl 2026"


def test_format_period_sk_handles_december() -> None:
    out = format_period_sk(
        datetime(2025, 12, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert out == "december 2025"


# ============================================================
# PDF builder smoke test
# ============================================================
def test_pdf_builder_returns_pdf_bytes() -> None:
    stats = compute_monthly_stats(
        flipper_discord_id="123",
        flipper_name="jano flipper",
        leads=[_lead("new"), _lead("sold")],
        period_start=datetime(2026, 4, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    pdf = build_monthly_report_pdf(stats)
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF"), "musí byť validný PDF header"
    assert len(pdf) > 500, "PDF má byť aspoň pár stoviek bajtov"


def test_pdf_builder_handles_zero_leads() -> None:
    stats = compute_monthly_stats(
        flipper_discord_id="123",
        flipper_name="jano",
        leads=[],
        period_start=datetime(2026, 4, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    pdf = build_monthly_report_pdf(stats)
    assert pdf.startswith(b"%PDF")
