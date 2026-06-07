"""Stály tlačidlový panel — trvalá správa v kanáli s tlačidlom, ktoré
otvorí žiadosť o leasing bez nutnosti písať `/leasing`.

View je **persistentné** (`timeout=None` + `custom_id`). Discord si po reštarte
views nepamätá, takže `bot.add_view(LeadPanelView())` v `setup_hook` ho musí
znova zaregistrovať — vďaka stabilnému `custom_id` ostane staré tlačidlo funkčné.
"""
from __future__ import annotations

import discord

from src.views.gdpr_view import send_consent_prompt


class LeadPanelView(discord.ui.View):
    """Persistentný view s jediným tlačidlom na spustenie žiadosti o leasing."""

    def __init__(self) -> None:
        super().__init__(timeout=None)  # persistentné — nikdy nevyprší

    @discord.ui.button(
        label="Mám záujem o leasing",
        style=discord.ButtonStyle.success,
        emoji="📝",
        custom_id="lead_panel:open",  # stabilné ID nutné pre persistenciu
    )
    async def open_form(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        # Rovnaká cesta ako /leasing: GDPR súhlas → modal.
        await send_consent_prompt(interaction)
