"""Unit testy pre scripts/preflight.py — mockuje httpx.AsyncClient.get."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest

from scripts.preflight import (
    check_discord,
    check_whatsapp,
)


def _resp(status_code: int, body: str = "", json_data: dict | None = None) -> httpx.Response:
    if json_data is not None:
        import json
        body = json.dumps(json_data)
    return httpx.Response(
        status_code=status_code,
        text=body,
        request=httpx.Request("GET", "https://example.com"),
    )


def _patch_get(response: httpx.Response | Exception) -> Any:
    async def fake_get(self: Any, url: str, **kwargs: Any) -> httpx.Response:
        if isinstance(response, Exception):
            raise response
        return response

    return patch.object(httpx.AsyncClient, "get", new=fake_get)


# ============================================================
# Discord
# ============================================================
@pytest.mark.asyncio
async def test_discord_200_passes_with_username() -> None:
    with _patch_get(_resp(200, json_data={"username": "synapse-drive-test", "id": "123"})):
        r = await check_discord("xxxtokenxxx")
    assert r.passed
    assert "synapse-drive-test" in r.detail
    assert "123" in r.detail


@pytest.mark.asyncio
async def test_discord_401_fails_with_fix_hint() -> None:
    with _patch_get(_resp(401)):
        r = await check_discord("badtoken")
    assert not r.passed
    assert "401" in r.detail
    assert r.fix_hint and "Reset Token" in r.fix_hint


@pytest.mark.asyncio
async def test_discord_network_error_fails_cleanly() -> None:
    with _patch_get(httpx.ConnectError("dns")):
        r = await check_discord("token")
    assert not r.passed
    assert "network" in r.detail.lower()


# ============================================================
# WhatsApp
# ============================================================
@pytest.mark.asyncio
async def test_whatsapp_200_passes_with_phone_in_output() -> None:
    with _patch_get(_resp(200, json_data={
        "display_phone_number": "+1 555-123-4567",
        "verified_name": "Drive Test",
    })):
        r = await check_whatsapp("phone_id_123", "token", "v21.0")
    assert r.passed
    assert "555" in r.detail or "1 555" in r.detail
    assert "Drive Test" in r.detail


@pytest.mark.asyncio
async def test_whatsapp_401_hints_at_token_expiry() -> None:
    with _patch_get(_resp(401)):
        r = await check_whatsapp("phone_id", "expired_token", "v21.0")
    assert not r.passed
    assert r.fix_hint and "token" in r.fix_hint.lower()


@pytest.mark.asyncio
async def test_whatsapp_code_100_hints_at_phone_id() -> None:
    body = '{"error":{"code":100,"message":"Unsupported get request"}}'
    with _patch_get(_resp(400, body)):
        r = await check_whatsapp("bad_phone_id", "token", "v21.0")
    assert not r.passed
    assert r.fix_hint and "Phone number ID" in r.fix_hint
