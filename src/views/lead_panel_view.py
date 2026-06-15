"""Stály tlačidlový panel — trvalá správa v kanáli s tlačidlom, ktoré
otvorí žiadosť o leasing bez nutnosti písať `/leasing`.

View je **persistentné** (`timeout=None` + `custom_id`). Discord si po reštarte
views nepamätá, takže `bot.add_view(LeadPanelView())` v `setup_hook` ho musí
znova zaregistrovať — vďaka stabilnému `custom_id` ostane staré tlačidlo funkčné.
"""
from __future__ import annotations

import discord

from src.modals.splatka_modal import SplatkaModal
from src.views.gdpr_view import send_consent_prompt


class LeadPanelView(discord.ui.View):
    """Persistentný view: žiadosť o leasing + orientačná kalkulačka splátky."""

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

    @discord.ui.button(
        label="Spočítať orientačnú splátku",
        style=discord.ButtonStyle.secondary,
        emoji="🧮",
        custom_id="lead_panel:calc",  # stabilné ID nutné pre persistenciu
    )
    async def open_calculator(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        # Bez GDPR — kalkulačka nepracuje s osobnými údajmi.
        await interaction.response.send_modal(SplatkaModal())
