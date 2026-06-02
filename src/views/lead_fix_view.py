"""Opravný view — zobrazí sa keď validácia formulára zlyhá.

Discord nedovolí znova otvoriť modal priamo z modal-submit interakcie, preto
flipperovi pošleme ephemerálnu správu s tlačidlom; klik naň je komponentová
interakcia, z ktorej už modal otvoriť smieme (predvyplnený pôvodnými hodnotami).
"""
from __future__ import annotations

import discord

from src.modals.lead_modal import LeadModal
from src.products import Product


class LeadFixView(discord.ui.View):
    """Tlačidlo na znovuotvorenie predvyplneného formulára po chybe validácie."""

    def __init__(self, product: Product, defaults: dict[str, str]) -> None:
        super().__init__(timeout=300)  # 5 min na opravu
        self.product = product
        self.defaults = defaults

    @discord.ui.button(
        label="Opraviť údaje",
        style=discord.ButtonStyle.primary,
        emoji="✏️",
    )
    async def fix(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.send_modal(
            LeadModal(self.product, defaults=self.defaults)
        )
