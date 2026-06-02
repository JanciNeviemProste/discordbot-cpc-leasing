"""Mesačný report — 1. deň v mesiaci o 8:00 pošle Kristiánovi štatistiku
leadov za predošlý (uzavretý) mesiac.

Plánovač cez `discord.ext.tasks` (kontrola raz za hodinu). Stav (za ktorý
mesiac sa už poslalo) sa drží v `report_state.json` → odolné voči reštartu
aj catch-up, ak bol bot v deň 1 vypnutý.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from discord.ext import commands, tasks

from src.config import get_settings
from src.services.reports import compute_stats, format_report, month_label
from src.services.sheets import STAV_OPTIONS
from src.utils.logger import get_logger

log = get_logger(__name__)

_TZ = ZoneInfo("Europe/Bratislava")
_STATE_FILE = Path("report_state.json")
_REPORT_HOUR = 8  # posielame od 8:00 ráno


def _prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _load_state() -> dict[str, str]:
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _save_state(state: dict[str, str]) -> None:
    _STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


class MonthlyReportCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.monthly_check.start()

    def cog_unload(self) -> None:
        self.monthly_check.cancel()

    @tasks.loop(hours=1)
    async def monthly_check(self) -> None:
        try:
            await self._maybe_send()
        except Exception as e:  # noqa: BLE001
            log.exception("report.tick_failed", error=str(e))

    @monthly_check.before_loop
    async def _before(self) -> None:
        await self.bot.wait_until_ready()

    async def _maybe_send(self) -> None:
        sheets = getattr(self.bot, "sheets_client", None)
        if sheets is None:
            return

        now = datetime.now(_TZ)
        py, pm = _prev_month(now.year, now.month)
        period = f"{py}-{pm:02d}"

        state = _load_state()
        last = state.get("last_reported")

        if last is None:
            # Prvý beh — inicializuj bez odoslania (žiadny report v deň nasadenia).
            _save_state({"last_reported": period})
            log.info("report.initialized", period=period)
            return

        if last == period or now.hour < _REPORT_HOUR:
            return

        rows = await sheets.read_data_rows()
        stats = compute_stats(rows, py, pm, STAV_OPTIONS)

        settings = get_settings()
        sheet_url = (
            f"https://docs.google.com/spreadsheets/d/{settings.google_sheet_id}/edit"
            if settings.google_sheet_id
            else None
        )
        text = format_report(stats, month_label(py, pm), sheet_url)

        telegram = self.bot.telegram_client  # type: ignore[attr-defined]
        res = await telegram.send_message(text)
        if res.success:
            _save_state({"last_reported": period})
            log.info("report.sent", period=period, total=stats.total)
        else:
            log.error("report.send_failed", period=period, error=res.error)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MonthlyReportCog(bot))
