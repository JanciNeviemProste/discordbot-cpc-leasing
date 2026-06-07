"""GDPR confirmation view — krok pred otvorením modalu.

Discord modal nemá checkbox, takže používame medzikrok: bot pošle
ephemeral message s buttonom, flipper potvrdí, až potom sa otvorí modal.
Toto má aj právny benefit — máme explicitný klik na "mám súhlas".
"""
from __future__ import annotations

import discord

from src.modals.lead_modal import LeadModal

# Text GDPR výzvy — zdieľaný medzi /leasing príkazom a tlačidlovým panelom,
# aby bola výzva všade rovnaká.
GDPR_PROMPT = (
    "📋 **GDPR potvrdenie**\n\n"
    "Potvrdzujem, že:\n"
    "• Mám od klienta výslovný súhlas na poskytnutie jeho údajov\n"
    "• Klient bol informovaný, že údaje budú zdieľané s finančným "
    "poradcom (Kristián Valovič) za účelom prípravy leasingu/poistky\n"
    "• Klient bol oboznámený so spracovaním osobných údajov firmou drive.sk\n\n"
    "_Po potvrdení sa otvorí formulár._"
)


async def send_consent_prompt(interaction: discord.Interaction) -> None:
    """Pošle efemérnu GDPR výzvu + tlačidlo na potvrdenie. Spoločná cesta pre
    `/leasing` aj pre klik na tlačidlový panel — odtiaľ sa otvorí modal."""
    await interaction.response.send_message(
        content=GDPR_PROMPT,
        view=GDPRConsentView(),
        ephemeral=True,
    )


class GDPRConsentView(discord.ui.View):
    """Ephemeral view pre potvrdenie GDPR súhlasu."""

    def __init__(self) -> None:
        super().__init__(timeout=120)  # 2 min na klik

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
        # Otvor modal s formulárom
        await interaction.response.send_modal(LeadModal())

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
            content="❌ Zrušené. Pre novú žiadosť použi `/leasing` znova.",
            view=None,
        )
