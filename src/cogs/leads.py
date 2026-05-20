"""Leads cog — slash commands a hlavná business logika.

Commands:
- /novy-zaujemca   → otvorí GDPR confirmation → modal → submit pipeline
- /moje-leady      → flipper si pozrie svoje leady (za posledných 30 dní)
- /lead-info       → admin/Kristián pozrie detail leadu podľa ID (plné údaje)
"""
from __future__ import annotations

from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from src.config import get_settings
from src.database import Database
from src.services.whatsapp import WhatsAppClient
from src.utils.embeds import (
    build_compact_lead_summary,
    build_dedup_warning,
    build_lead_embed,
)
from src.utils.gdpr import mask_name
from src.utils.logger import get_logger
from src.views.gdpr_view import GDPRConsentView
from src.views.lead_view import LeadStatusView

log = get_logger(__name__)


class LeadsCog(commands.Cog):
    def __init__(self, bot: commands.Bot, whatsapp: WhatsAppClient) -> None:
        self.bot = bot
        self.whatsapp = whatsapp
        self.db = Database()

    # ============================================================
    # /novy-zaujemca
    # ============================================================
    @app_commands.command(
        name="novy-zaujemca",
        description="Pridaj nového zaujemcu o auto a leasing",
    )
    async def new_lead(self, interaction: discord.Interaction) -> None:
        gdpr_text = (
            "📋 **GDPR potvrdenie**\n\n"
            "Potvrdzujem, že:\n"
            "• Mám od klienta výslovný súhlas na poskytnutie jeho údajov\n"
            "• Klient bol informovaný, že údaje budú zdieľané s finančným "
            "poradcom (Kristián Valovič) za účelom prípravy leasingu/poistky\n"
            "• Klient bol oboznámený so spracovaním osobných údajov firmou drive.sk\n\n"
            "_Po potvrdení sa otvorí formulár._"
        )
        await interaction.response.send_message(
            content=gdpr_text,
            view=GDPRConsentView(),
            ephemeral=True,
        )

    # ============================================================
    # /moje-leady
    # ============================================================
    @app_commands.command(
        name="moje-leady",
        description="Zobraz moje leady za posledných 30 dní",
    )
    async def my_leads(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        leads = self.db.get_leads_by_flipper(str(interaction.user.id), limit=20)

        if not leads:
            await interaction.followup.send(
                "Zatiaľ nemáš žiadne leady. Použi `/novy-zaujemca` na pridanie.",
                ephemeral=True,
            )
            return

        lines = [build_compact_lead_summary(l) for l in leads]
        stats = _count_by_status(leads)
        total_commission = sum(float(l.get("commission_amount") or 0) for l in leads)
        stats_line = (
            f"📊 Spolu: **{len(leads)}** · "
            f"📞 {stats['contacted']} · "
            f"✅ {stats['approved']} · "
            f"💰 {stats['sold']} · "
            f"❌ {stats['rejected']} · "
            f"💸 **{total_commission:.0f} €**"
        )

        message = f"**Tvoje leady ({len(leads)})**\n{stats_line}\n\n" + "\n".join(lines)
        await interaction.followup.send(message[:1900], ephemeral=True)

    # ============================================================
    # /lead-info (admin only — plné údaje)
    # ============================================================
    @app_commands.command(
        name="lead-info",
        description="[ADMIN] Detail leadu podľa ID — plné údaje",
    )
    @app_commands.describe(lead_id="UUID leadu (z embedu / DB)")
    async def lead_info(
        self, interaction: discord.Interaction, lead_id: str
    ) -> None:
        settings = get_settings()
        is_authorized = (
            interaction.user.id == settings.discord_kristian_user_id
            or (
                isinstance(interaction.user, discord.Member)
                and any(
                    r.id == settings.discord_admin_role_id
                    for r in interaction.user.roles
                )
            )
        )
        if not is_authorized:
            await interaction.response.send_message(
                "🔒 Len pre adminov a Kristiána.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        lead = self.db.get_lead(lead_id.strip())
        if not lead:
            await interaction.followup.send(
                f"❌ Lead `{lead_id}` neexistuje.", ephemeral=True
            )
            return

        embed = build_lead_embed(lead, masked=False)
        await interaction.followup.send(embed=embed, ephemeral=True)


def _count_by_status(leads: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"new": 0, "contacted": 0, "approved": 0, "rejected": 0, "sold": 0}
    for l in leads:
        s = l.get("status", "new")
        counts[s] = counts.get(s, 0) + 1
    return counts


# ============================================================
# Pipeline: spracovanie submit-u z modalu
# ============================================================
async def process_lead_submission(
    *,
    interaction: discord.Interaction,
    client_name: str,
    client_phone: str,
    client_email: str,
    car_data: dict[str, Any],
    note: str | None,
    parse_warning: str | None = None,
) -> None:
    """Zavolané z LeadModal.on_submit. Robí:
    1. Insert do DB
    2. Post embed do #leady-kristian (s buttonmi)
    3. Attach Discord message ID do DB
    4. Pošli WhatsApp Kristiánovi
    5. Confirm flipperovi
    """
    settings = get_settings()
    bot = interaction.client
    db = Database()

    # Whatsapp client — fetch z bot context (init v bot.py)
    whatsapp: WhatsAppClient = bot.whatsapp_client  # type: ignore[attr-defined]

    # ---- 0) Dedup check (soft warn, nikdy neblokuje insert) ----
    dedup_warning: str | None = None
    try:
        matches = db.find_duplicate_leads(phone=client_phone, email=client_email)
        if matches:
            dedup_warning = build_dedup_warning(matches)
            log.info("leads.dedup_match", count=len(matches), phone=client_phone[-3:])
    except Exception as e:  # noqa: BLE001
        log.warning("leads.dedup_check_failed", error=str(e))

    # ---- 1) DB insert ----
    lead_payload = {
        "client_name": client_name,
        "client_phone": client_phone,
        "client_email": client_email,
        "flipper_discord_id": str(interaction.user.id),
        "flipper_discord_name": interaction.user.display_name,
        "gdpr_consent": True,
        "notes": note,
        **car_data,
    }
    lead = db.create_lead(lead_payload)
    lead_id = lead["id"]

    # ---- 2) Post embed do kanála ----
    channel = bot.get_channel(settings.discord_leads_channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(settings.discord_leads_channel_id)
        except discord.NotFound:
            log.error("leads.channel_not_found", channel_id=settings.discord_leads_channel_id)
            await interaction.followup.send(
                "❌ Lead bol uložený, ale leadový kanál nie je nakonfigurovaný. "
                "Kontaktuj admina.",
                ephemeral=True,
            )
            return

    if not isinstance(channel, (discord.TextChannel, discord.Thread)):
        await interaction.followup.send(
            "❌ Lead bol uložený, ale leadový kanál má nepodporovaný typ.",
            ephemeral=True,
        )
        return

    embed = build_lead_embed(lead, masked=True)
    if dedup_warning:
        embed.add_field(name="⚠️ Možný duplikát", value=dedup_warning, inline=False)
    view = LeadStatusView(lead_id=lead_id)

    ping_content = f"<@{settings.discord_kristian_user_id}> nový lead 👇"
    try:
        message = await channel.send(content=ping_content, embed=embed, view=view)
    except discord.HTTPException as e:
        log.exception("leads.channel_send_failed", error=str(e))
        await interaction.followup.send(
            f"❌ Chyba pri postovaní do kanála: `{e}`. Lead je uložený v DB.",
            ephemeral=True,
        )
        return

    # ---- 3) Update DB s Discord message ID ----
    db.attach_discord_message(
        lead_id=lead_id,
        channel_id=str(channel.id),
        message_id=str(message.id),
    )

    # ---- 4) WhatsApp notifikácia ----
    car_desc = _format_car_for_whatsapp(lead)
    discord_msg_url = (
        f"https://discord.com/channels/"
        f"{interaction.guild_id}/{channel.id}/{message.id}"
    )
    wa_result = await whatsapp.send_lead_notification(
        client_name=mask_name(client_name),  # WA prijíma masked name (telefón mu stačí)
        client_phone=client_phone,
        car_description=car_desc,
        flipper_name=interaction.user.display_name,
        discord_message_url=discord_msg_url,
    )
    db.attach_whatsapp_result(
        lead_id=lead_id,
        sent=wa_result.success,
        message_id=wa_result.message_id,
        error=wa_result.error,
    )

    # ---- 5) Confirm flipperovi ----
    wa_status = "✅ aj na WhatsApp" if wa_result.success else f"⚠️ WhatsApp zlyhal: {wa_result.error}"
    confirmation = (
        f"✅ **Lead uložený a poslaný Kristiánovi** ({wa_status})\n"
        f"ID: `{lead_id}`\n"
        f"Postnuté v <#{channel.id}>"
    )
    if parse_warning:
        confirmation += f"\n\n⚠️ **Auto parsing:** {parse_warning}"
    if dedup_warning:
        confirmation += f"\n\n⚠️ **Možný duplikát:**\n{dedup_warning}"
    await interaction.followup.send(confirmation, ephemeral=True)


def _format_car_for_whatsapp(lead: dict[str, Any]) -> str:
    """Kompaktný popis auta pre WhatsApp template parameter."""
    parts = [lead.get("car_make"), lead.get("car_model")]
    name = " ".join(str(p) for p in parts if p).strip()
    if not name:
        name = (lead.get("car_raw_description") or "")[:50] or "auto"

    extras = []
    if lead.get("car_year"):
        extras.append(str(lead["car_year"]))
    if lead.get("car_km"):
        extras.append(f"{lead['car_km']:,} km".replace(",", " "))
    if lead.get("car_price"):
        extras.append(f"{lead['car_price']:.0f} €")

    if extras:
        return f"{name} ({', '.join(extras)})"
    return name


async def setup(bot: commands.Bot) -> None:
    """Cog loader — `bot.whatsapp_client` musí byť nastavený PRED `load_extension`."""
    whatsapp = getattr(bot, "whatsapp_client", None)
    if whatsapp is None:
        raise RuntimeError(
            "bot.whatsapp_client nebol nastavený. Inicializuj v bot.py pred load_extension."
        )
    await bot.add_cog(LeadsCog(bot, whatsapp))
