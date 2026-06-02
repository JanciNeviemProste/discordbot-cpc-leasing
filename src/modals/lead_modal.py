"""Lead modal — formulár, ktorý sa otvorí flipperovi po GDPR potvrdení.

Discord modal limit: 5 text inputov. Všetky polia povinné:
1. Meno a priezvisko klienta (single line)
2. Email (single line)
3. Telefón (single line)
4. Cena (single line)
5. Link na auto (single line)
"""
from __future__ import annotations

import discord

from src.services.validators import (
    is_url,
    is_valid_email,
    is_valid_phone,
    looks_like_price,
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

    client_email = discord.ui.TextInput(
        label="Email klienta",
        placeholder="jan.novak@gmail.com",
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

    price = discord.ui.TextInput(
        label="Cena auta",
        placeholder="napr. 12 500 €",
        required=True,
        max_length=30,
        style=discord.TextStyle.short,
    )

    car_link = discord.ui.TextInput(
        label="Link na auto",
        placeholder="https://www.autobazar.eu/...",
        required=True,
        max_length=500,
        style=discord.TextStyle.short,
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

        price_raw = self.price.value.strip()
        if not looks_like_price(price_raw):
            await interaction.response.send_message(
                f"❌ Neplatná cena: `{price_raw}`\n"
                "Zadaj sumu, napr. `12 500 €` alebo `12500`.",
                ephemeral=True,
            )
            return

        car_link_raw = self.car_link.value.strip()
        if not is_url(car_link_raw):
            await interaction.response.send_message(
                f"❌ Neplatný link na auto: `{car_link_raw}`\n"
                "Vlož celú URL inzerátu (začína `https://` alebo `www.`).",
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
                price=price_raw,
                car_link=car_link_raw,
            )
        except Exception as e:  # noqa: BLE001
            log.exception("modal.submit_failed", error=str(e))
            await interaction.followup.send(
                f"❌ Nastala chyba pri spracovaní žiadosti: `{e}`\n"
                "Skús to znova, alebo kontaktuj admina.",
                ephemeral=True,
            )
