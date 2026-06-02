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
    format_phone_pretty,
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
        min_length=9,
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

    def __init__(self, *, defaults: dict[str, str] | None = None) -> None:
        super().__init__()
        if defaults:
            # Predvyplň polia pôvodnými hodnotami (po neúspešnej validácii),
            # aby flipper nemusel prepisovať všetko odznova.
            self.client_name.default = defaults.get("client_name") or None
            self.client_email.default = defaults.get("client_email") or None
            self.client_phone.default = defaults.get("client_phone") or None
            self.price.default = defaults.get("price") or None
            self.car_link.default = defaults.get("car_link") or None

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handler — validuje a deleguje na pipeline v leads cog-u."""
        from src.cogs.leads import process_lead_submission
        from src.views.lead_fix_view import LeadFixView

        # Pôvodné hodnoty na predvyplnenie pri prípadnej oprave.
        defaults = {
            "client_name": self.client_name.value.strip(),
            "client_email": self.client_email.value.strip(),
            "client_phone": self.client_phone.value.strip(),
            "price": self.price.value.strip(),
            "car_link": self.car_link.value.strip(),
        }

        async def reject(message: str) -> None:
            await interaction.response.send_message(
                message, view=LeadFixView(defaults), ephemeral=True
            )

        phone_raw = self.client_phone.value.strip()
        phone_normalized = normalize_phone(phone_raw)
        if not is_valid_phone(phone_normalized):
            await reject(
                f"❌ Neplatný telefón: `{phone_raw}`\n"
                "Akceptovaný formát: `+421 905 123 456` alebo `0905 123 456`\n"
                "_Klikni „Opraviť údaje“ nižšie a doplň správne číslo._"
            )
            return

        email = self.client_email.value.strip().lower()
        if not is_valid_email(email):
            await reject(
                f"❌ Neplatný email: `{email}`\n"
                "_Klikni „Opraviť údaje“ nižšie a oprav email._"
            )
            return

        price_raw = self.price.value.strip()
        if not looks_like_price(price_raw):
            await reject(
                f"❌ Neplatná cena: `{price_raw}`\n"
                "Zadaj sumu, napr. `12 500 €` alebo `12500`.\n"
                "_Klikni „Opraviť údaje“ nižšie._"
            )
            return

        car_link_raw = self.car_link.value.strip()
        if not is_url(car_link_raw):
            await reject(
                f"❌ Neplatný link na auto: `{car_link_raw}`\n"
                "Vlož celú URL inzerátu (začína `https://` alebo `www.`).\n"
                "_Klikni „Opraviť údaje“ nižšie._"
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            await process_lead_submission(
                interaction=interaction,
                client_name=self.client_name.value.strip(),
                client_phone=format_phone_pretty(phone_normalized),
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
