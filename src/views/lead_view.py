"""Lead status buttons — persistent view (prežije reštart bota).

Custom IDs: `lead:status:{action}:{lead_id}` — Discord podporuje len
100-znakové custom_id, UUID + prefix sa pohodlne zmestí.

Permission check: button môže stlačiť LEN Kristián alebo admin role.
"""
from __future__ import annotations

import discord

from src.config import get_settings
from src.database import Database
from src.services.commission import compute_commission
from src.utils.embeds import build_lead_embed
from src.utils.logger import get_logger

log = get_logger(__name__)

STATUS_ACTIONS = {
    "contacted": ("📞 Kontaktovaný", discord.ButtonStyle.primary),
    "approved": ("✅ Schválený", discord.ButtonStyle.success),
    "rejected": ("❌ Zamietnutý", discord.ButtonStyle.danger),
    "sold": ("💰 Predaný", discord.ButtonStyle.secondary),
}


class LeadStatusView(discord.ui.View):
    """Persistent view — pri štarte bota sa zaregistruje s timeout=None."""

    def __init__(self, lead_id: str | None = None) -> None:
        super().__init__(timeout=None)

        # Pri inštanciácii pre konkrétny lead nastavíme custom_id s UUID.
        # Pri registrácii view-u na štarte (bez lead_id) sa použijú template-y.
        if lead_id is not None:
            for child in self.children:
                if isinstance(child, discord.ui.Button) and child.custom_id:
                    # Replace placeholder {lead_id} s reálnym UUID
                    child.custom_id = child.custom_id.replace("{lead_id}", lead_id)

    @discord.ui.button(
        label=STATUS_ACTIONS["contacted"][0],
        style=STATUS_ACTIONS["contacted"][1],
        custom_id="lead:status:contacted:{lead_id}",
    )
    async def btn_contacted(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await _handle_status_change(interaction, button, "contacted")

    @discord.ui.button(
        label=STATUS_ACTIONS["approved"][0],
        style=STATUS_ACTIONS["approved"][1],
        custom_id="lead:status:approved:{lead_id}",
    )
    async def btn_approved(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await _handle_status_change(interaction, button, "approved")

    @discord.ui.button(
        label=STATUS_ACTIONS["rejected"][0],
        style=STATUS_ACTIONS["rejected"][1],
        custom_id="lead:status:rejected:{lead_id}",
    )
    async def btn_rejected(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await _handle_status_change(interaction, button, "rejected")

    @discord.ui.button(
        label=STATUS_ACTIONS["sold"][0],
        style=STATUS_ACTIONS["sold"][1],
        custom_id="lead:status:sold:{lead_id}",
    )
    async def btn_sold(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await _handle_status_change(interaction, button, "sold")


async def _handle_status_change(
    interaction: discord.Interaction,
    button: discord.ui.Button,
    new_status: str,
) -> None:
    """Spoločná logika — permission check, DB update, edit embed, notify flipper."""
    settings = get_settings()
    user = interaction.user

    # ---- Permission check ----
    is_kristian = user.id == settings.discord_kristian_user_id
    is_admin = (
        isinstance(user, discord.Member)
        and any(r.id == settings.discord_admin_role_id for r in user.roles)
    )
    if not (is_kristian or is_admin):
        await interaction.response.send_message(
            "🔒 Tento button môže používať len Kristián alebo admin.",
            ephemeral=True,
        )
        return

    # ---- Extract lead_id z custom_id ----
    custom_id = button.custom_id or ""
    parts = custom_id.split(":")
    if len(parts) < 4:
        await interaction.response.send_message(
            "❌ Chyba: custom_id má neplatný formát.",
            ephemeral=True,
        )
        return
    lead_id = parts[3]

    # ---- DB update ----
    db = Database()
    try:
        lead = db.update_lead_status(
            lead_id=lead_id,
            new_status=new_status,
            changed_by_discord_id=str(user.id),
            changed_by_name=user.display_name,
        )
    except Exception as e:  # noqa: BLE001
        log.exception("lead_view.db_update_failed", lead_id=lead_id, error=str(e))
        await interaction.response.send_message(
            f"❌ Chyba pri updatovaní statusu: `{e}`",
            ephemeral=True,
        )
        return

    # ---- Commission compute (len pri sold) ----
    commission_amount = 0.0
    commission_rate = 0.0
    if new_status == "sold":
        try:
            commission_rate, commission_amount = compute_commission(
                car_price=lead.get("car_price"),
                rate=settings.commission_default_rate,
                fallback=settings.commission_fallback_amount,
            )
            db.attach_commission(
                lead_id, amount=commission_amount, rate=commission_rate
            )
            lead["commission_amount"] = commission_amount
            lead["commission_rate"] = commission_rate
        except Exception as e:  # noqa: BLE001
            log.exception("lead_view.commission_failed", lead_id=lead_id, error=str(e))

    # ---- Edit embed v origináli ----
    new_embed = build_lead_embed(lead, masked=True)
    new_view = LeadStatusView(lead_id=lead_id)

    try:
        await interaction.response.edit_message(embed=new_embed, view=new_view)
    except discord.HTTPException as e:
        log.warning("lead_view.edit_failed", error=str(e))

    # ---- Notify flipper ephemerálne v threade alebo cez DM ----
    flipper_id = int(lead["flipper_discord_id"])
    try:
        flipper = await interaction.client.fetch_user(flipper_id)
        status_label = {
            "contacted": "📞 Tvoj lead bol kontaktovaný",
            "approved": "✅ Tvoj lead má schválený leasing!",
            "rejected": "❌ Tvoj lead bol zamietnutý",
            "sold": "💰 Tvoj lead bol PREDANÝ — gratulujem!",
        }.get(new_status, "Status leadu sa zmenil")

        car_summary = " ".join(
            p for p in [lead.get("car_make"), lead.get("car_model")] if p
        ) or "—"

        message = (
            f"{status_label}\n"
            f"Auto: **{car_summary}**\n"
            f"Klient: {lead['client_name']}\n"
            f"Updatol: {user.display_name}"
        )
        if new_status == "sold":
            if commission_amount > 0 and commission_rate > 0:
                message += (
                    f"\n💸 **Tvoja provízia: {commission_amount:.2f} €** "
                    f"({commission_rate * 100:.1f} % z ceny)"
                )
            else:
                message += (
                    "\n💸 Provízia zatiaľ 0 € — Kristián doplní cenu auta "
                    "a prepočítame manuálne."
                )

        await flipper.send(message)
    except (discord.NotFound, discord.Forbidden) as e:
        log.info(
            "lead_view.flipper_dm_failed",
            flipper_id=flipper_id,
            error=str(e),
        )

    log.info(
        "lead_view.status_changed",
        lead_id=lead_id,
        new_status=new_status,
        by=user.display_name,
    )
