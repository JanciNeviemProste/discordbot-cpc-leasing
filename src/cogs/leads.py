"""Leads cog — minimal flow.

Command:
- /leasing → otvorí GDPR prompt → modal → pošle Telegram správu Kristiánovi
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from src.config import get_settings
from src.services.telegram import TelegramClient
from src.utils.logger import get_logger
from src.views.gdpr_view import GDPRConsentView

log = get_logger(__name__)


class LeadsCog(commands.Cog):
    def __init__(self, bot: commands.Bot, telegram: TelegramClient) -> None:
        self.bot = bot
        self.telegram = telegram

    @app_commands.command(
        name="leasing",
        description="Vytvoriť žiadosť o leasing pre klienta",
    )
    async def leasing(self, interaction: discord.Interaction) -> None:
        settings = get_settings()
        if (
            settings.discord_leasing_channel_id is not None
            and interaction.channel_id != settings.discord_leasing_channel_id
        ):
            await interaction.response.send_message(
                f"Tento príkaz funguje len v <#{settings.discord_leasing_channel_id}>.",
                ephemeral=True,
            )
            return

        gdpr_text = (
            "📋 **GDPR potvrdenie**\n\n"
            "Potvrdzujem, že:\n"
            "• Mám od klienta výslovný súhlas na poskytnutie jeho údajov\n"
            "• Klient bol informovaný, že údaje budú zdieľané s finančným "
            "poradcom (Kristián Valovič) za účelom prípravy leasingu/poistky\n"
            "• Klient bol oboznámený so spracovaním osobných údajov firmou drive.sk\n\n"
            "_Po potvrdení sa otvorí formulár._"
        )
        await interaction.response.send_message(
            content=gdpr_text,
            view=GDPRConsentView(),
            ephemeral=True,
        )


async def process_lead_submission(
    *,
    interaction: discord.Interaction,
    client_name: str,
    client_phone: str,
    client_email: str,
    car_description: str,
    note: str,
) -> None:
    """Volane z LeadModal.on_submit. Pošle Telegram správu Kristiánovi a
    confirmuje flipperovi. Žiadna DB, žiadny embed do kanála."""
    bot = interaction.client
    telegram: TelegramClient = bot.telegram_client  # type: ignore[attr-defined]

    log.info(
        "leads.submission",
        flipper_id=str(interaction.user.id),
        flipper_name=interaction.user.display_name,
        client_email_domain=client_email.split("@", 1)[-1] if "@" in client_email else "?",
    )

    tg_result = await telegram.send_lead_notification(
        client_name=client_name,
        client_phone=client_phone,
        client_email=client_email,
        car_description=car_description,
        flipper_name=interaction.user.display_name,
        note=note,
    )

    if tg_result.success:
        await interaction.followup.send(
            "✅ **Odoslané Kristiánovi.** Vďaka!",
            ephemeral=True,
        )
        return

    log.error("leads.telegram_failed", error=tg_result.error)
    await interaction.followup.send(
        f"⚠️ **Telegram zlyhal:** `{tg_result.error}`\n"
        f"Údaje klienta sa Kristiánovi neodoslali — daj vedieť adminovi.",
        ephemeral=True,
    )


async def setup(bot: commands.Bot) -> None:
    """Cog loader — `bot.telegram_client` musí byť nastavený PRED `load_extension`."""
    telegram = getattr(bot, "telegram_client", None)
    if telegram is None:
        raise RuntimeError(
            "bot.telegram_client nebol nastavený. Inicializuj v bot.py pred load_extension."
        )
    await bot.add_cog(LeadsCog(bot, telegram))
