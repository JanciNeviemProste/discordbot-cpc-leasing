"""Discord embed buildery pre lead karty."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import discord

from src.utils.gdpr import mask_email, mask_name, mask_phone

# Status → farba + emoji + Slovak label
STATUS_META: dict[str, dict[str, Any]] = {
    "new": {
        "color": discord.Color.blue(),
        "emoji": "🆕",
        "label": "Nový",
    },
    "contacted": {
        "color": discord.Color.gold(),
        "emoji": "📞",
        "label": "Kontaktovaný",
    },
    "approved": {
        "color": discord.Color.green(),
        "emoji": "✅",
        "label": "Schválený leasing",
    },
    "rejected": {
        "color": discord.Color.red(),
        "emoji": "❌",
        "label": "Zamietnutý",
    },
    "sold": {
        "color": discord.Color.purple(),
        "emoji": "💰",
        "label": "Predaný",
    },
}


def _status_meta(status: str) -> dict[str, Any]:
    return STATUS_META.get(status, STATUS_META["new"])


def build_lead_embed(lead: dict[str, Any], *, masked: bool = True) -> discord.Embed:
    """Embed pre Discord. Default masked=True (osobné údaje skryté).
    masked=False len pre DM Kristiánovi alebo private kanál ak treba.
    """
    meta = _status_meta(lead["status"])

    if masked:
        client_display = (
            f"{mask_name(lead['client_name'])}\n"
            f"📞 {mask_phone(lead['client_phone'])}\n"
            f"✉️ {mask_email(lead['client_email'])}"
        )
        title = f"{meta['emoji']} Nový lead"
    else:
        client_display = (
            f"{lead['client_name']}\n"
            f"📞 {lead['client_phone']}\n"
            f"✉️ {lead['client_email']}"
        )
        title = f"{meta['emoji']} Nový lead (plné údaje)"

    embed = discord.Embed(
        title=title,
        color=meta["color"],
        timestamp=_parse_dt(lead.get("created_at")),
    )

    embed.add_field(name="👤 Klient", value=client_display, inline=True)
    embed.add_field(name="🚗 Auto", value=_format_car(lead), inline=True)
    embed.add_field(
        name="📊 Status",
        value=f"**{meta['label']}**",
        inline=True,
    )

    embed.add_field(
        name="🧑‍💼 Flipper",
        value=f"<@{lead['flipper_discord_id']}>",
        inline=True,
    )

    embed.set_footer(text=f"Lead ID: {lead['id']}")
    return embed


def _format_car(lead: dict[str, Any]) -> str:
    parts = []
    title_parts = [
        str(lead.get("car_make") or "").strip(),
        str(lead.get("car_model") or "").strip(),
    ]
    title = " ".join(p for p in title_parts if p)
    if title:
        parts.append(f"**{title}**")
    elif lead.get("car_raw_description"):
        parts.append(f"**{lead['car_raw_description'][:80]}**")

    details = []
    if lead.get("car_year"):
        details.append(f"📅 {lead['car_year']}")
    if lead.get("car_km"):
        details.append(f"🛣️ {lead['car_km']:,} km".replace(",", " "))
    if lead.get("car_fuel"):
        details.append(f"⛽ {lead['car_fuel']}")
    if lead.get("car_price"):
        details.append(f"💶 {lead['car_price']:,.0f} €".replace(",", " "))
    if details:
        parts.append(" · ".join(details))

    if lead.get("car_url"):
        parts.append(f"[Otvoriť inzerát]({lead['car_url']})")

    return "\n".join(parts) if parts else "_(bez údajov)_"


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def build_dedup_warning(matches: list[dict[str, Any]], *, max_show: int = 3) -> str:
    """Formátuje zoznam duplikátov pre embed field aj ephemerálnu správu.

    Bez PII — len skrátený lead_id, status emoji+label, flipper meno, vek v dňoch.
    Ak je matches viac ako max_show, doplní '... a ešte X ďalších'.
    """
    if not matches:
        return ""

    now = datetime.now(timezone.utc)
    lines = [f"**Našli sa {len(matches)} podobné leady** (rovnaký tel/email):"]
    for m in matches[:max_show]:
        meta = _status_meta(m.get("status", "new"))
        created = _parse_dt(m.get("created_at"))
        age_days = max(0, (now - created).days)
        age_str = "dnes" if age_days == 0 else f"pred {age_days}d"
        lead_id_short = str(m.get("id", ""))[:8]
        flipper = m.get("flipper_discord_name") or "—"
        lines.append(
            f"• {meta['emoji']} `{lead_id_short}` · {flipper} · {age_str} · {meta['label']}"
        )

    remaining = len(matches) - max_show
    if remaining > 0:
        lines.append(f"_… a ešte {remaining} ďalších_")
    return "\n".join(lines)


def build_compact_lead_summary(lead: dict[str, Any]) -> str:
    """Krátky súhrn pre WhatsApp / DM / `/moje-leady` list."""
    meta = _status_meta(lead["status"])
    car = " ".join(
        p for p in [lead.get("car_make"), lead.get("car_model"), str(lead.get("car_year") or "")]
        if p
    ).strip() or (lead.get("car_raw_description") or "—")[:50]
    return f"{meta['emoji']} **{car}** — {meta['label']}"
