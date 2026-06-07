"""SYNAPSE DRIVE BOT — entry point.

Spustenie:  python -m src.bot
"""
from __future__ import annotations

import asyncio
import signal

import discord
from discord.ext import commands

from src.config import get_settings
from src.services.sheets import SheetsClient
from src.services.telegram import TelegramClient
from src.utils.logger import get_logger, setup_logging
from src.views.lead_panel_view import LeadPanelView


class SynapseDriveBot(commands.Bot):
    """Custom bot s lifecycle hookmi pre Telegram client."""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = False  # nepoužívame text commands, len slash

        super().__init__(
            command_prefix="!",  # nepoužité, ale required
            intents=intents,
            help_command=None,
        )

        self.settings = get_settings()
        self.log = get_logger("bot")
        self.telegram_client: TelegramClient | None = None
        self.sheets_client: SheetsClient | None = None

    async def setup_hook(self) -> None:
        """Zavolané pri štarte. Init resources + register cogs + sync commands."""
        self.log.info("bot.setup_hook.start")

        # Telegram client init
        self.telegram_client = TelegramClient()

        # Google Sheets evidencia — len ak je nakonfigurovaný sheet
        if self.settings.google_sheet_id:
            self.sheets_client = SheetsClient()
            self.log.info("bot.sheets_enabled")
        else:
            self.log.info("bot.sheets_disabled", reason="GOOGLE_SHEET_ID prázdne")

        # Persistentný tlačidlový panel — znova zaregistruj view podľa custom_id,
        # aby staré tlačidlo v kanáli fungovalo aj po reštarte bota.
        self.add_view(LeadPanelView())

        # Cogs
        await self.load_extension("src.cogs.leads")
        await self.load_extension("src.cogs.monthly_report")

        # Sync slash commands na guild (rýchle, na rozdiel od global)
        guild = discord.Object(id=self.settings.discord_guild_id)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        self.log.info(
            "bot.commands_synced",
            count=len(synced),
            commands=[c.name for c in synced],
        )

    async def on_ready(self) -> None:
        assert self.user is not None
        self.log.info(
            "bot.ready",
            username=self.user.name,
            user_id=self.user.id,
            guilds=len(self.guilds),
        )
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="leady pre Kristiána",
            )
        )

    async def close(self) -> None:
        self.log.info("bot.shutdown.start")
        if self.telegram_client is not None:
            await self.telegram_client.close()
        await super().close()
        self.log.info("bot.shutdown.complete")


async def main() -> None:
    setup_logging()
    log = get_logger("main")
    settings = get_settings()

    bot = SynapseDriveBot()

    # Graceful shutdown na SIGTERM (dôležité pre Cybrancee)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(bot.close()))
        except NotImplementedError:
            # Windows — signal handlery nefungujú, ale Ctrl+C ich aj tak nepotrebuje
            pass

    try:
        log.info("main.starting", env=settings.environment)
        await bot.start(settings.discord_token)
    except KeyboardInterrupt:
        log.info("main.keyboard_interrupt")
    finally:
        if not bot.is_closed():
            await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
