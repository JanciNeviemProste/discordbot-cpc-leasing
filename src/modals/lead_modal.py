"""Lead modal — formulár, ktorý sa otvorí flipperovi po GDPR potvrdení.

Discord modal limit: 5 text inputov:
1. Meno klienta (single line)
2. Telefón (single line)
3. Email (single line)
4. Auto: URL alebo popis (multi-line)
5. Poznámka (multi-line, voliteľné)
"""
from __future__ import annotations

import discord

from src.services.validators import (
    is_valid_email,
    is_valid_phone,
    normalize_phone,
)
from src.utils.logger import get_logger

log = get_logger(__name__)


class LeadModal(discord.ui.Modal, title="Žiadosť o leasing — drive.sk"):
    """Formulár pre flippera."""

    client_name = discord.ui.TextInput(
        label="Meno a priezvisko klienta",
        placeholder="napr. Ján Novák",
        required=True,
        max_length=100,
        style=discord.TextStyle.short,
    )

    client_phone = discord.ui.TextInput(
        label="Telefón klienta",
        placeholder="+421 905 123 456",
        required=True,
        max_length=20,
        style=discord.TextStyle.short,
    )

    client_email = discord.ui.TextInput(
        label="Email klienta",
        placeholder="jan.novak@gmail.com",
        required=True,
        max_length=100,
        style=discord.TextStyle.short,
    )

    car_info = discord.ui.TextInput(
        label="Auto (link na inzerát alebo popis)",
        placeholder="https://www.autobazar.eu/... alebo: Audi A4 2019 nafta 150k km 12500€",
        required=True,
        max_length=500,
        style=discord.TextStyle.paragraph,
    )

    note = discord.ui.TextInput(
        label="Poznámka (voliteľné)",
        placeholder="napr. volať po 17:00, klient má hotovosť 5000€, ...",
        required=False,
        max_length=500,
        style=discord.TextStyle.paragraph,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handler — validuje a deleguje na pipeline v leads cog-u."""
        from src.cogs.leads import process_lead_submission

        phone_raw = self.client_phone.value.strip()
        phone_normalized = normalize_phone(phone_raw)
        if not is_valid_phone(phone_normalized):
            await interaction.response.send_message(
                f"❌ Neplatný telefón: `{phone_raw}`\n"
                "Akceptovaný formát: `+421 905 123 456` alebo `0905 123 456`",
                ephemeral=True,
            )
            return

        email = self.client_email.value.strip().lower()
        if not is_valid_email(email):
            await interaction.response.send_message(
                f"❌ Neplatný email: `{email}`",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            await process_lead_submission(
                interaction=interaction,
                client_name=self.client_name.value.strip(),
                client_phone=phone_normalized,
                client_email=email,
                car_description=self.car_info.value.strip(),
                note=self.note.value.strip() if self.note.value else "-",
            )
        except Exception as e:  # noqa: BLE001
            log.exception("modal.submit_failed", error=str(e))
            await interaction.followup.send(
                f"❌ Nastala chyba pri spracovaní žiadosti: `{e}`\n"
                "Skús to znova, alebo kontaktuj admina.",
                ephemeral=True,
            )
