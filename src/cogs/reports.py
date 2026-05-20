"""Reports cog — mesačné PDF reporty pre flipperov.

Dva entry-pointy:
1. `@tasks.loop` denný — beží každých 24h; na 1. dni v mesiaci pošle report za
   predchádzajúci mesiac všetkým flipperom, ktorí v tom mesiaci pridali aspoň
   1 lead.
2. `/generate-report` slash command — admin/Kristián môže manuálne re-spustiť
   (napr. ak DM zlyhal, alebo chce report v inom okamihu).

DM zlyhanie sa logne ako `reports.dm_failed` — admin to vidí, môže re-runnúť
manuálne s targetom konkrétneho flippera.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

import discord
from discord import app_commands
from discord.ext import commands, tasks

from src.config import get_settings
from src.database import Database
from src.services.pdf_report import build_monthly_report_pdf
from src.services.report_stats import (
    MonthlyStats,
    compute_monthly_stats,
    format_period_sk,
    previous_month_range,
    should_run_today,
)
from src.utils.logger import get_logger

log = get_logger(__name__)


class ReportsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = Database()
        # Pamätáme si, či sme dnes už bežali — aby loop nestrelil 2× ak sa náhodou
        # spustí viackrát počas dňa (napr. reštart bota o 23:59 → 00:01)
        self._last_run_date: str | None = None
        self.daily_check.start()

    def cog_unload(self) -> None:
        self.daily_check.cancel()

    # ============================================================
    # Daily loop — kontrola či je prvý v mesiaci
    # ============================================================
    @tasks.loop(hours=24)
    async def daily_check(self) -> None:
        today = datetime.now(timezone.utc)
        today_key = today.strftime("%Y-%m-%d")

        if self._last_run_date == today_key:
            return  # už sme dnes bežali

        if not should_run_today(today):
            return

        self._last_run_date = today_key
        log.info("reports.monthly_run.start", date=today_key)
        await self._run_monthly_for_all_flippers(today)

    @daily_check.before_loop
    async def _wait_until_ready(self) -> None:
        await self.bot.wait_until_ready()

    # ============================================================
    # Hlavná pipeline — pre všetkých alebo pre jedného flippera
    # ============================================================
    async def _run_monthly_for_all_flippers(self, today: datetime) -> None:
        start, end = previous_month_range(today)
        flippers = self.db.get_distinct_flippers_in_range(start=start, end=end)
        log.info("reports.flippers_found", count=len(flippers), period=format_period_sk(start, end))

        sent = 0
        failed = 0
        for f in flippers:
            try:
                ok = await self._send_report_for_flipper(
                    flipper_discord_id=f["id"],
                    flipper_name=f["name"],
                    start=start,
                    end=end,
                )
                if ok:
                    sent += 1
                else:
                    failed += 1
            except Exception as e:  # noqa: BLE001
                log.exception("reports.flipper_failed", flipper_id=f["id"], error=str(e))
                failed += 1

        log.info("reports.monthly_run.done", sent=sent, failed=failed)

    async def _send_report_for_flipper(
        self,
        *,
        flipper_discord_id: str,
        flipper_name: str,
        start: datetime,
        end: datetime,
    ) -> bool:
        """Vybuduj report a pošli DM. Vracia True ak DM prešlo."""
        leads = self.db.get_leads_for_flipper_in_range(
            flipper_discord_id, start=start, end=end
        )
        stats = compute_monthly_stats(
            flipper_discord_id=flipper_discord_id,
            flipper_name=flipper_name,
            leads=leads,
            period_start=start,
            period_end=end,
        )
        pdf_bytes = build_monthly_report_pdf(stats)
        return await self._dm_pdf(stats, pdf_bytes)

    async def _dm_pdf(self, stats: MonthlyStats, pdf_bytes: bytes) -> bool:
        """Pošle PDF ako Discord DM. False ak DM zlyhalo (Forbidden / NotFound)."""
        try:
            user = self.bot.get_user(int(stats.flipper_discord_id)) or await self.bot.fetch_user(
                int(stats.flipper_discord_id)
            )
        except (discord.NotFound, discord.HTTPException) as e:
            log.warning(
                "reports.user_fetch_failed",
                flipper_id=stats.flipper_discord_id,
                error=str(e),
            )
            return False

        period = format_period_sk(stats.period_start, stats.period_end)
        filename = (
            f"drive_report_{stats.period_start.year}_{stats.period_start.month:02d}.pdf"
        )
        message = (
            f"📊 **Mesačný report — {period}**\n"
            f"Tvoje stats za {period}: **{stats.total}** lead(ov) celkom.\n"
            f"Detaily v priloženom PDF."
        )

        try:
            await user.send(
                content=message,
                file=discord.File(BytesIO(pdf_bytes), filename=filename),
            )
            log.info(
                "reports.dm_sent",
                flipper_id=stats.flipper_discord_id,
                period=period,
                total=stats.total,
            )
            return True
        except discord.Forbidden:
            log.warning(
                "reports.dm_failed",
                flipper_id=stats.flipper_discord_id,
                reason="DMs disabled or bot blocked",
            )
            return False
        except discord.HTTPException as e:
            log.warning(
                "reports.dm_failed",
                flipper_id=stats.flipper_discord_id,
                error=str(e),
            )
            return False

    # ============================================================
    # /generate-report  (admin only)
    # ============================================================
    @app_commands.command(
        name="generate-report",
        description="[ADMIN] Manuálne vygeneruj a pošli mesačný report",
    )
    @app_commands.describe(
        target="Konkrétny flipper (default: všetci s leadmi v minulom mesiaci)",
    )
    async def generate_report(
        self,
        interaction: discord.Interaction,
        target: discord.User | None = None,
    ) -> None:
        if not _is_admin(interaction):
            await interaction.response.send_message(
                "🔒 Len pre adminov a Kristiána.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        today = datetime.now(timezone.utc)
        start, end = previous_month_range(today)
        period = format_period_sk(start, end)

        if target is None:
            await self._run_monthly_for_all_flippers(today)
            await interaction.followup.send(
                f"✅ Reporty za **{period}** boli rozposlané. "
                "Detaily v logoch (`reports.monthly_run.done`).",
                ephemeral=True,
            )
            return

        # Single target
        ok = await self._send_report_for_flipper(
            flipper_discord_id=str(target.id),
            flipper_name=target.display_name,
            start=start,
            end=end,
        )
        status = "✅ poslané" if ok else "⚠️ DM zlyhalo (flipper má zablokované DMs?)"
        await interaction.followup.send(
            f"{status} pre {target.mention} — report za **{period}**.",
            ephemeral=True,
        )


def _is_admin(interaction: discord.Interaction) -> bool:
    settings = get_settings()
    if interaction.user.id == settings.discord_kristian_user_id:
        return True
    if isinstance(interaction.user, discord.Member):
        return any(r.id == settings.discord_admin_role_id for r in interaction.user.roles)
    return False


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReportsCog(bot))
