"""Unit testy pre build_dedup_warning."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.utils.embeds import build_dedup_warning


def _match(
    *,
    lead_id: str = "abcd1234-5678-90ab-cdef-000000000000",
    status: str = "new",
    flipper: str = "flipper_jano",
    age_days: int = 0,
) -> dict:
    return {
        "id": lead_id,
        "status": status,
        "flipper_discord_name": flipper,
        "created_at": (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat(),
    }


def test_empty_matches_returns_empty_string() -> None:
    assert build_dedup_warning([]) == ""


def test_single_match_format() -> None:
    out = build_dedup_warning([_match(status="sold", flipper="jano", age_days=14)])
    assert "1 podobné leady" in out
    assert "💰" in out
    assert "Predaný" in out
    assert "jano" in out
    assert "pred 14d" in out
    assert "abcd1234" in out  # skrátený lead_id (prvých 8)


def test_today_shows_dnes() -> None:
    out = build_dedup_warning([_match(age_days=0)])
    assert "dnes" in out


def test_max_show_truncates_with_remaining_count() -> None:
    matches = [
        _match(lead_id=f"id-{i:08d}-xxxx-xxxx-xxxx-xxxxxxxxxxxx", age_days=i)
        for i in range(5)
    ]
    out = build_dedup_warning(matches, max_show=3)
    # Header hovorí 5
    assert "5 podobné leady" in out
    # Ukáže prvé 3
    assert out.count("•") == 3
    # Spomenie zvyšok
    assert "ešte 2" in out


def test_unknown_status_falls_back_to_new() -> None:
    out = build_dedup_warning([_match(status="bizarre_status")])
    # Fallback meta je 'new' (Nový / 🆕)
    assert "🆕" in out
    assert "Nový" in out


def test_missing_flipper_name_shows_dash() -> None:
    m = _match()
    m["flipper_discord_name"] = None
    out = build_dedup_warning([m])
    assert "—" in out


def test_no_pii_leaked() -> None:
    """Warning nesmie obsahovať phone ani email — len lead_id, status, flipper, vek."""
    matches = [_match()]
    # Pridáme do dictu PII, ktoré build_dedup_warning má ignorovať
    matches[0]["client_phone"] = "+421999888777"
    matches[0]["client_email"] = "tajny@example.com"
    out = build_dedup_warning(matches)
    assert "+421999888777" not in out
    assert "tajny@example.com" not in out
