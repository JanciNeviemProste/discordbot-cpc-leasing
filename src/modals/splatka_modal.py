"""Modal kalkulačky — orientačná mesačná splátka úveru cez Cofidis.

Samostatná pomôcka (bez GDPR a bez osobných údajov): flipper zadá len cenu auta
a počet mesiacov, bot vráti ephemerálny odhad mesačnej splátky.

Predpoklady (podľa zadania): akontácia 0 €, bez poistenia, sadzba pre najnovšie
auto (2026). Výpočet je v `src/services/cofidis_calc.py`.
"""
from __future__ import annotations

import discord

from src.services.cofidis_calc import (
    CalcError,
    compute_installment,
    format_eur,
    format_pct,
    parse_amount,
    parse_months,
)
from src.utils.logger import get_logger

log = get_logger(__name__)

_DISCLAIMER = (
    "_Orientačné: akontácia 0 €, bez poistenia. Kalkulačka má len informatívny "
    "charakter — záväznú ponuku pripraví finančný poradca._"
)


class SplatkaModal(discord.ui.Modal, title="Orientačná mesačná splátka"):
    """Dve polia: cena vozidla + počet mesiacov."""

    cena = discord.ui.TextInput(
        label="Cena vozidla (€)",
        placeholder="napr. 12 500",
        required=True,
        max_length=20,
        style=discord.TextStyle.short,
    )

    pocet_mesiacov = discord.ui.TextInput(
        label="Počet mesiacov (12 – 96)",
        placeholder="napr. 72",
        required=True,
        max_length=4,
        style=discord.TextStyle.short,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            price = parse_amount(self.cena.value)
            months = parse_months(self.pocet_mesiacov.value)
            result = compute_installment(price, months)
        except CalcError as e:
            await interaction.response.send_message(
                f"❌ {e}\n"
                "_Skús to znova cez `/splatka` alebo tlačidlo "
                "„🧮 Spočítať orientačnú splátku“._",
                ephemeral=True,
            )
            return

        log.info("splatka.calc", months=result.months, monthly=result.monthly)

        message = (
            "🚗 **Orientačná mesačná splátka**\n\n"
            f"Cena vozidla:  **{format_eur(price)}**\n"
            f"Počet mesiacov:  **{result.months}**\n"
            f"Výška úveru:  {format_eur(result.loan_amount)}\n"
            f"Úroková sadzba:  {format_pct(result.base_rate)}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"➡️  **~ {format_eur(result.monthly)} / mes**\n\n"
            f"{_DISCLAIMER}"
        )
        await interaction.response.send_message(message, ephemeral=True)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        """Poistka pre *neočakávané* výnimky (nie CalcError) — inak by Discord
        flipperovi ukázal generické „The application did not respond"."""
        log.exception("splatka.modal_error", error=str(error))
        msg = "❌ Nastala neočakávaná chyba pri výpočte. Skús to znova."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
