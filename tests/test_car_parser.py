"""Unit testy car_parser hardening — retry, Cloudflare detekcia, empty result, warnings."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.services import car_parser
from src.services.car_parser import LeadCarData, fetch_car_data


@dataclass
class _StubSettings:
    car_parser_timeout: int = 5


@pytest.fixture(autouse=True)
def _stub_settings() -> Any:
    """Vyhne sa nutnosti reálneho .env pri importe car_parser."""
    with patch.object(car_parser, "get_settings", return_value=_StubSettings()):
        yield


def _make_response(status_code: int, text: str = "", headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        text=text,
        headers=headers or {},
        request=httpx.Request("GET", "https://example.com"),
    )


def _patch_client_with_responses(responses: list[Any]) -> Any:
    """Vráti context manager, ktorý zmení httpx.AsyncClient tak, aby .get()
    vracal postupne `responses` (môžu byť Response alebo Exception)."""
    call_counter = {"i": 0}

    async def fake_get(self: Any, url: str, **kwargs: Any) -> httpx.Response:
        i = call_counter["i"]
        call_counter["i"] += 1
        item = responses[i] if i < len(responses) else responses[-1]
        if isinstance(item, Exception):
            raise item
        return item

    return patch.object(httpx.AsyncClient, "get", new=fake_get), call_counter


# ============================================================
# LeadCarData.is_empty
# ============================================================
def test_is_empty_true_when_no_fields() -> None:
    assert LeadCarData(url="x").is_empty


def test_is_empty_false_when_make_set() -> None:
    assert not LeadCarData(url="x", make="Audi").is_empty


def test_is_empty_ignores_raw_title() -> None:
    # raw_title sám o sebe nestačí — to je len <title> tagu, nie štruktúrované dáta
    assert LeadCarData(url="x", raw_title="Audi A4").is_empty


# ============================================================
# Happy path
# ============================================================
@pytest.mark.asyncio
async def test_fetch_success_with_jsonld() -> None:
    html = """
    <html><head><title>Audi A4 2019</title>
    <script type="application/ld+json">
    {"@type": "Car", "name": "Audi A4 2019",
     "brand": {"name": "Audi"}, "model": "A4",
     "vehicleModelDate": "2019",
     "offers": {"price": "12500"}}
    </script>
    </head><body></body></html>
    """
    patcher, _ = _patch_client_with_responses([_make_response(200, html)])
    with patcher:
        result = await fetch_car_data("https://example.com/auto")

    assert result.make == "Audi"
    assert result.model == "A4"
    assert result.year == 2019
    assert result.price == 12500.0
    assert result.parse_warning is None


# ============================================================
# Retry s rôznym UA pri 403
# ============================================================
@pytest.mark.asyncio
async def test_retry_on_403_succeeds_on_second_ua() -> None:
    html_ok = """<html><head>
    <script type="application/ld+json">{"@type":"Car","brand":{"name":"BMW"},"model":"X5"}</script>
    </head></html>"""
    patcher, counter = _patch_client_with_responses([
        _make_response(403),
        _make_response(200, html_ok),
    ])
    with patcher:
        result = await fetch_car_data("https://example.com/auto")

    assert counter["i"] == 2, "mal urobiť retry"
    assert result.make == "BMW"
    assert result.parse_warning is None


@pytest.mark.asyncio
async def test_all_retries_blocked_sets_cloudflare_warning() -> None:
    patcher, counter = _patch_client_with_responses([
        _make_response(403),
        _make_response(429),
        _make_response(503),
    ])
    with patcher:
        result = await fetch_car_data("https://example.com/auto")

    assert counter["i"] == 3, "mal vyskúšať všetky 3 UA"
    assert result.parse_warning is not None
    assert "blokuje" in result.parse_warning.lower() or "cloudflare" in result.parse_warning.lower()


# ============================================================
# Cloudflare detekcia cez body
# ============================================================
@pytest.mark.asyncio
async def test_cloudflare_challenge_in_200_body_triggers_retry() -> None:
    cf_html = "<html><body>Just a moment...</body></html>"
    ok_html = """<html><head>
    <script type="application/ld+json">{"@type":"Car","brand":{"name":"VW"},"model":"Golf"}</script>
    </head></html>"""
    patcher, counter = _patch_client_with_responses([
        _make_response(200, cf_html),
        _make_response(200, ok_html),
    ])
    with patcher:
        result = await fetch_car_data("https://example.com/auto")

    assert counter["i"] == 2
    assert result.make == "VW"


# ============================================================
# 404 — nemá zmysel retry-ovať
# ============================================================
@pytest.mark.asyncio
async def test_404_does_not_retry() -> None:
    patcher, counter = _patch_client_with_responses([
        _make_response(404),
        _make_response(200, "<html></html>"),  # ak by aj retry-oval, dostal by ok
    ])
    with patcher:
        result = await fetch_car_data("https://example.com/auto")

    assert counter["i"] == 1, "404 sa nemá retry-ovať"
    assert result.parse_warning is not None
    assert "http_404" in result.parse_warning or "404" in result.parse_warning


# ============================================================
# Timeout warning
# ============================================================
@pytest.mark.asyncio
async def test_timeout_sets_timeout_warning() -> None:
    patcher, _ = _patch_client_with_responses([
        httpx.TimeoutException("timed out"),
        httpx.TimeoutException("timed out"),
        httpx.TimeoutException("timed out"),
    ])
    with patcher:
        result = await fetch_car_data("https://example.com/auto")

    assert result.parse_warning is not None
    assert "limit" in result.parse_warning.lower() or "neodpoved" in result.parse_warning.lower()


# ============================================================
# Empty-result warning — fetch OK, ale parser nič nenašiel
# ============================================================
@pytest.mark.asyncio
async def test_empty_html_sets_empty_warning() -> None:
    patcher, _ = _patch_client_with_responses([
        _make_response(200, "<html><head><title>Nejaký nadpis</title></head><body></body></html>")
    ])
    with patcher:
        result = await fetch_car_data("https://example.com/auto")

    # raw_title sa naplní, ale štruktúrované dáta chýbajú
    assert result.is_empty
    assert result.parse_warning is not None
    assert "nepodarilo" in result.parse_warning.lower()
