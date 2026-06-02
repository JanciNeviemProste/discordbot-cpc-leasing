"""GDPR confirmation view — krok pred otvorením modalu.

Discord modal nemá checkbox, takže používame medzikrok: bot pošle
ephemeral message s buttonom, flipper potvrdí, až potom sa otvorí modal.
Toto má aj právny benefit — máme explicitný klik na "mám súhlas".
"""
from __future__ import annotations

import discord

from src.modals.lead_modal import LeadModal
from src.products import Product


class GDPRConsentView(discord.ui.View):
    """Ephemeral view pre potvrdenie GDPR súhlasu (pre konkrétny produkt)."""

    def __init__(self, product: Product) -> None:
        super().__init__(timeout=120)  # 2 min na klik
        self.product = product

    @discord.ui.button(
        label="Mám súhlas, pokračovať",
        style=discord.ButtonStyle.success,
        emoji="✅",
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.send_modal(LeadModal(self.product))

    @discord.ui.button(
        label="Zrušiť",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.edit_message(
            content="❌ Zrušené. Pre novú žiadosť použi príkaz znova.",
            view=None,
        )
