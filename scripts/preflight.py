"""Pre-flight credential validator pre synapse-drive-bot.

Spustenie:
    .venv\\Scripts\\python -m scripts.preflight

Overí 2 externé creds bez spustenia bota:
- Discord bot token  (GET /users/@me)
- WhatsApp Cloud API  (GET /{phone_number_id})

Plus lokálne sanity checky (recipient number format).

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


async def check_whatsapp(phone_number_id: str, access_token: str, api_version: str) -> CheckResult:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"https://graph.facebook.com/{api_version}/{phone_number_id}",
                params={"fields": "display_phone_number,verified_name"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.HTTPError as e:
        return CheckResult(
            "WhatsApp", False, f"network error: {e.__class__.__name__}",
            "graph.facebook.com nedostupné",
        )

    if resp.status_code == 200:
        data = resp.json()
        return CheckResult(
            "WhatsApp", True,
            f"phone {data.get('display_phone_number', '?')}, "
            f"verified_name '{data.get('verified_name', '?')}'",
        )

    body = resp.text[:300] if resp.text else ""

    if resp.status_code == 401:
        return CheckResult(
            "WhatsApp", False, "401 Unauthorized",
            "Access token expiroval (Meta temp tokens žijú 24h) alebo invalid. "
            "developers.facebook.com → App → WhatsApp → API Setup",
        )
    if "OAuthException" in body or "code\":190" in body:
        return CheckResult(
            "WhatsApp", False, "OAuth error",
            f"token issue: {body}",
        )
    if "Unsupported get request" in body or "code\":100" in body:
        return CheckResult(
            "WhatsApp", False, f"HTTP {resp.status_code} — phone_number_id zlý?",
            "Over Phone number ID v Meta App → WhatsApp → API Setup",
        )
    return CheckResult(
        "WhatsApp", False, f"HTTP {resp.status_code}",
        f"response: {body}",
    )


def _local_sanity_checks(settings) -> list[CheckResult]:  # type: ignore[no-untyped-def]
    """Lacné lokálne checky — neprdneme na network ak je niečo evidentne zle."""
    results: list[CheckResult] = []

    # Recipient number: 10-15 digits, žiadny +
    recipient = settings.whatsapp_recipient_number
    if not re.fullmatch(r"\d{10,15}", recipient):
        results.append(CheckResult(
            "WHATSAPP_RECIPIENT_NUMBER", False,
            f"'{recipient}' nemá medzinárodný formát",
            "Bez '+', len číslice, 10-15 znakov. Príklad: 421905111222",
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
              "a vyplň hodnoty podľa SETUP.md sekcií 1-3")
        return 1

    print(f"\n{BOLD}🔍 Preflight — synapse-drive-bot{RESET}\n")

    # Lokálne checky — sync, lacné
    local_results = _local_sanity_checks(settings)
    for r in local_results:
        _print_result(r)

    # Network checky — paralelne
    results = await asyncio.gather(
        check_discord(settings.discord_token),
        check_whatsapp(
            settings.whatsapp_phone_number_id,
            settings.whatsapp_access_token,
            settings.whatsapp_api_version,
        ),
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
