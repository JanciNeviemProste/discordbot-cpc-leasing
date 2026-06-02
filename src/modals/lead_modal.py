"""Lead modal — generický formulár riadený produktom (Leasing/PZP/Kasko/Iné).

Vždy 3 fixné polia (Meno a priezvisko, Email, Telefón) + 2 produktovo-špecifické
z `product.extras` (Discord modal limit = 5). Pri neplatnom vstupe sa lead
neodošle — flipper dostane chybu + tlačidlo „Opraviť" (predvyplnený formulár).
"""
from __future__ import annotations

import discord

from src.products import Product
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

# Kľúče fixných polí.
_F_NAME = "client_name"
_F_EMAIL = "client_email"
_F_PHONE = "client_phone"


class LeadModal(discord.ui.Modal):
    """Formulár pre flippera, polia podľa zvoleného produktu."""

    def __init__(self, product: Product, *, defaults: dict[str, str] | None = None) -> None:
        super().__init__(title=f"Žiadosť: {product.typ} — drive.sk")
        self.product = product
        self._inputs: dict[str, discord.ui.TextInput] = {}
        defaults = defaults or {}

        def add(key: str, **kwargs: object) -> None:
            ti = discord.ui.TextInput(default=defaults.get(key) or None, **kwargs)  # type: ignore[arg-type]
            self._inputs[key] = ti
            self.add_item(ti)

        add(_F_NAME, label="Meno a priezvisko klienta",
            placeholder="napr. Ján Novák", required=True, max_length=100,
            style=discord.TextStyle.short)
        add(_F_EMAIL, label="Email klienta",
            placeholder="jan.novak@gmail.com", required=True, max_length=100,
            style=discord.TextStyle.short)
        add(_F_PHONE, label="Telefón klienta",
            placeholder="+421 905 123 456", required=True,
            min_length=9, max_length=20, style=discord.TextStyle.short)

        for ef in product.extras:
            if ef.validator == "url":
                max_len = 500
            elif ef.paragraph:
                max_len = 500
            else:
                max_len = 100
            add(ef.key, label=ef.label, placeholder=ef.placeholder,
                required=ef.required, max_length=max_len,
                style=discord.TextStyle.paragraph if ef.paragraph
                else discord.TextStyle.short)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        from src.cogs.leads import process_lead_submission
        from src.views.lead_fix_view import LeadFixView

        values = {k: ti.value.strip() for k, ti in self._inputs.items()}

        async def reject(message: str) -> None:
            await interaction.response.send_message(
                message, view=LeadFixView(self.product, values), ephemeral=True
            )

        email = values[_F_EMAIL].lower()
        if not is_valid_email(email):
            await reject(
                f"❌ Neplatný email: `{email}`\n"
                "_Klikni „Opraviť údaje“ nižšie a oprav email._"
            )
            return

        phone_raw = values[_F_PHONE]
        phone_normalized = normalize_phone(phone_raw)
        if not is_valid_phone(phone_normalized):
            await reject(
                f"❌ Neplatný telefón: `{phone_raw}`\n"
                "Akceptovaný formát: `+421 905 123 456` alebo `0905 123 456`\n"
                "_Klikni „Opraviť údaje“ nižšie a doplň správne číslo._"
            )
            return

        for ef in self.product.extras:
            val = values[ef.key]
            if ef.validator == "price" and not looks_like_price(val):
                await reject(
                    f"❌ Neplatná suma v poli „{ef.label}“: `{val}`\n"
                    "Zadaj sumu, napr. `12 500 €` alebo `12500`.\n"
                    "_Klikni „Opraviť údaje“ nižšie._"
                )
                return
            if ef.validator == "url" and not is_url(val):
                await reject(
                    f"❌ Neplatný link v poli „{ef.label}“: `{val}`\n"
                    "Vlož celú URL inzerátu (začína `https://` alebo `www.`).\n"
                    "_Klikni „Opraviť údaje“ nižšie._"
                )
                return

        await interaction.response.defer(ephemeral=True, thinking=True)

        extras_out = {ef.key: values[ef.key] for ef in self.product.extras}
        try:
            await process_lead_submission(
                interaction=interaction,
                product=self.product,
                client_name=values[_F_NAME],
                client_email=email,
                client_phone=format_phone_pretty(phone_normalized),
                extras=extras_out,
            )
        except Exception as e:  # noqa: BLE001
            log.exception("modal.submit_failed", error=str(e))
            await interaction.followup.send(
                f"❌ Nastala chyba pri spracovaní žiadosti: `{e}`\n"
                "Skús to znova, alebo kontaktuj admina.",
                ephemeral=True,
            )
