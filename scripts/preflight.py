"""Pre-flight credential validator pre synapse-drive-bot.

Spustenie:
    .venv\\Scripts\\python -m scripts.preflight

Overí 2 externé creds bez spustenia bota:
- Discord bot token  (GET /users/@me)
- Telegram Bot API   (GET /getMe + GET /getChat)

Plus lokálne sanity checky (chat_id format).

Exit 0 ak všetky network checky PASS; 1 inak.
"""
from __future__ import annotations

import asyncio
import re
import sys
from dataclasses import dataclass

import httpx

# Windows defaultný cp1250 nedokáže emoji; force UTF-8
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ANSI farby — žiadne extra deps
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str
    fix_hint: str | None = None


async def check_discord(token: str) -> CheckResult:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://discord.com/api/v10/users/@me",
                headers={"Authorization": f"Bot {token}"},
            )
    except httpx.HTTPError as e:
        return CheckResult(
            "Discord", False, f"network error: {e.__class__.__name__}",
            "skontroluj internet alebo discord.com/api dostupnosť",
        )

    if resp.status_code == 200:
        data = resp.json()
        return CheckResult(
            "Discord", True,
            f"bot @{data.get('username')} (id {data.get('id')})",
        )
    if resp.status_code == 401:
        return CheckResult(
            "Discord", False, "401 Unauthorized",
            "Token invalid / regenerovaný. discord.com/developers/applications "
            "→ Bot → Reset Token",
        )
    return CheckResult(
        "Discord", False, f"HTTP {resp.status_code}",
        f"neočakávaný response: {resp.text[:200]}",
    )


async def check_telegram(bot_token: str, chat_id: str) -> CheckResult:
    """getMe overí token, getChat overí že bot vie poslať do chat_id."""
    base = f"https://api.telegram.org/bot{bot_token}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            me = await client.get(f"{base}/getMe")
    except httpx.HTTPError as e:
        return CheckResult(
            "Telegram", False, f"network error: {e.__class__.__name__}",
            "api.telegram.org nedostupné",
        )

    if me.status_code == 401 or me.status_code == 404:
        return CheckResult(
            "Telegram", False, f"getMe HTTP {me.status_code}",
            "Token invalid. BotFather (@BotFather v Telegrame) → /token na regeneráciu",
        )

    try:
        me_data = me.json()
    except ValueError:
        me_data = {}

    if me.status_code != 200 or not me_data.get("ok", False):
        return CheckResult(
            "Telegram", False, f"getMe HTTP {me.status_code}",
            f"response: {me.text[:200]}",
        )

    bot_username = me_data.get("result", {}).get("username", "?")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            chat = await client.get(f"{base}/getChat", params={"chat_id": chat_id})
    except httpx.HTTPError as e:
        return CheckResult(
            "Telegram", False, f"getChat network error: {e.__class__.__name__}",
            "api.telegram.org nedostupné počas getChat",
        )

    try:
        chat_data = chat.json()
    except ValueError:
        chat_data = {}

    if chat.status_code == 200 and chat_data.get("ok", False):
        result = chat_data.get("result", {})
        chat_type = result.get("type", "?")
        chat_label = (
            result.get("username")
            or result.get("title")
            or result.get("first_name")
            or "?"
        )
        return CheckResult(
            "Telegram", True,
            f"bot @{bot_username} → chat type={chat_type}, name='{chat_label}'",
        )

    description = chat_data.get("description", chat.text[:200] if chat.text else "")
    if "chat not found" in description.lower():
        return CheckResult(
            "Telegram", False, f"chat not found pre chat_id='{chat_id}'",
            "Kristián botu ešte nenapísal /start (DM), alebo zlý TELEGRAM_CHAT_ID. "
            f"Over cez https://api.telegram.org/bot<TOKEN>/getUpdates",
        )

    return CheckResult(
        "Telegram", False, f"getChat HTTP {chat.status_code}",
        f"response: {description}",
    )


def _local_sanity_checks(settings) -> list[CheckResult]:  # type: ignore[no-untyped-def]
    """Lacné lokálne checky — neprdneme na network ak je niečo evidentne zle."""
    results: list[CheckResult] = []

    # Chat ID: buď numerické (kladné DM / záporné group), alebo @username
    chat_id = settings.telegram_chat_id
    if not re.fullmatch(r"(@[A-Za-z0-9_]{5,}|-?\d+)", chat_id):
        results.append(CheckResult(
            "TELEGRAM_CHAT_ID", False,
            f"'{chat_id}' nie je validné chat ID",
            "Musí byť buď číslo (DM = kladné, group = záporné, často '-100...'), "
            "alebo @channel_username. Zisti cez "
            "https://api.telegram.org/bot<TOKEN>/getUpdates",
        ))

    return results


def _print_result(r: CheckResult) -> None:
    if r.passed:
        print(f"  {GREEN}✅ {r.name:<10}{RESET} {r.detail}")
    else:
        print(f"  {RED}❌ {r.name:<10}{RESET} {BOLD}{r.detail}{RESET}")
        if r.fix_hint:
            for line in r.fix_hint.splitlines():
                print(f"     {DIM}Fix:{RESET} {line}")


async def _amain() -> int:
    # Lazy import — ak Pydantic validation padne, povieme presne čo chýba
    try:
        from src.config import get_settings
        settings = get_settings()
    except Exception as e:  # noqa: BLE001
        print(f"{RED}{BOLD}❌ Config validation failed{RESET}")
        print(f"   {e}")
        print(f"\n   {DIM}Tip:{RESET} prešli si .env, alebo Copy-Item .env.example .env "
              "a vyplň hodnoty")
        return 1

    print(f"\n{BOLD}🔍 Preflight — synapse-drive-bot{RESET}\n")

    # Lokálne checky — sync, lacné
    local_results = _local_sanity_checks(settings)
    for r in local_results:
        _print_result(r)

    # Network checky — paralelne
    results = await asyncio.gather(
        check_discord(settings.discord_token),
        check_telegram(settings.telegram_bot_token, settings.telegram_chat_id),
    )
    for r in results:
        _print_result(r)

    network_pass = sum(1 for r in results if r.passed)
    local_fail = sum(1 for r in local_results if not r.passed)

    print(f"\n  {DIM}─────────────────────────────────────────{RESET}")
    if network_pass == 2 and local_fail == 0:
        print(f"  {GREEN}{BOLD}✓ {network_pass}/2 PASS{RESET} — môžeš spustiť: "
              f"{BOLD}.venv\\Scripts\\python -m src.bot{RESET}\n")
        return 0
    else:
        msg = f"{network_pass}/2 network PASS"
        if local_fail:
            msg += f", {local_fail} lokálnych chýb"
        print(f"  {YELLOW}{BOLD}{msg}{RESET} — oprav vyššie a spusti znova\n")
        return 1


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    sys.exit(main())
