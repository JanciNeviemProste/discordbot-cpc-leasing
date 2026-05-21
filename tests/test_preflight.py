"""Unit testy pre scripts/preflight.py — mockuje httpx.AsyncClient.get."""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import httpx
import pytest

from scripts.preflight import (
    check_discord,
    check_telegram,
)


def _resp(status_code: int, body: str = "", json_data: dict | None = None) -> httpx.Response:
    if json_data is not None:
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


def _patch_get_sequence(responses: list[httpx.Response]) -> Any:
    """Vráti responses po jednom — getMe je prvý, getChat druhý."""
    state = {"i": 0}

    async def fake_get(self: Any, url: str, **kwargs: Any) -> httpx.Response:
        idx = state["i"]
        state["i"] += 1
        return responses[idx]

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
# Telegram
# ============================================================
@pytest.mark.asyncio
async def test_telegram_200_passes_with_chat_info() -> None:
    me = _resp(200, json_data={
        "ok": True,
        "result": {"username": "drive_sk_leasing_bot", "id": 1234567},
    })
    chat = _resp(200, json_data={
        "ok": True,
        "result": {"id": 987654321, "type": "private", "username": "kristian"},
    })
    with _patch_get_sequence([me, chat]):
        r = await check_telegram("123:abc", "987654321")
    assert r.passed
    assert "drive_sk_leasing_bot" in r.detail
    assert "private" in r.detail
    assert "kristian" in r.detail


@pytest.mark.asyncio
async def test_telegram_401_hints_at_token() -> None:
    with _patch_get(_resp(401)):
        r = await check_telegram("badtoken", "123")
    assert not r.passed
    assert r.fix_hint and "BotFather" in r.fix_hint


@pytest.mark.asyncio
async def test_telegram_chat_not_found_hints_at_start() -> None:
    me = _resp(200, json_data={
        "ok": True,
        "result": {"username": "bot", "id": 1},
    })
    chat = _resp(400, json_data={
        "ok": False,
        "error_code": 400,
        "description": "Bad Request: chat not found",
    })
    with _patch_get_sequence([me, chat]):
        r = await check_telegram("123:abc", "999")
    assert not r.passed
    assert "chat not found" in r.detail.lower()
    assert r.fix_hint and ("/start" in r.fix_hint or "getUpdates" in r.fix_hint)
