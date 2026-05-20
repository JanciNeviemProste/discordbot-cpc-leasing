"""Supabase wrapper — všetky DB operácie cez tento modul.

supabase-py je synchronný (postgrest-py je sync). Pre Discord bot to nie
je problém — operácie sú rýchle a robíme ich raz za interakciu. Ak by
si chcel plne async, prepíš na asyncpg priamo.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from supabase import Client, create_client

from src.config import get_settings
from src.utils.logger import get_logger

log = get_logger(__name__)


class Database:
    def __init__(self) -> None:
        settings = get_settings()
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_key,
        )

    # ---------- Leads ----------
    def create_lead(self, data: dict[str, Any]) -> dict[str, Any]:
        """Insert nového leadu. Vracia kompletný row vrátane id."""
        # GDPR timestamp ak nebol setnutý
        if data.get("gdpr_consent") and not data.get("gdpr_consent_at"):
            data["gdpr_consent_at"] = datetime.now(timezone.utc).isoformat()

        resp = self.client.table("leads").insert(data).execute()
        if not resp.data:
            raise RuntimeError(f"Failed to insert lead: {resp}")
        log.info("db.lead_created", lead_id=resp.data[0]["id"])
        return resp.data[0]

    def get_lead(self, lead_id: str) -> dict[str, Any] | None:
        resp = (
            self.client.table("leads")
            .select("*")
            .eq("id", lead_id)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None

    def update_lead_status(
        self,
        lead_id: str,
        new_status: str,
        changed_by_discord_id: str,
        changed_by_name: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Update status. Trigger v DB automaticky pridá do lead_status_history."""
        payload = {
            "status": new_status,
            "status_updated_at": datetime.now(timezone.utc).isoformat(),
            "status_updated_by": changed_by_name or changed_by_discord_id,
            "status_note": note,
        }
        resp = (
            self.client.table("leads")
            .update(payload)
            .eq("id", lead_id)
            .execute()
        )
        if not resp.data:
            raise RuntimeError(f"Failed to update lead {lead_id}")
        log.info(
            "db.lead_status_updated",
            lead_id=lead_id,
            new_status=new_status,
            by=changed_by_name,
        )
        return resp.data[0]

    def attach_discord_message(
        self, lead_id: str, channel_id: str, message_id: str
    ) -> None:
        self.client.table("leads").update({
            "discord_channel_id": channel_id,
            "discord_message_id": message_id,
        }).eq("id", lead_id).execute()

    def attach_commission(
        self, lead_id: str, *, amount: float, rate: float
    ) -> None:
        """Uloží computed provízu na lead. Volá _handle_status_change pri prechode
        na status='sold'. Amount aj rate sa zapisujú vždy (aj 0/0) — vďaka tomu
        commission_calculated_at označuje, že výpočet bežal."""
        self.client.table("leads").update({
            "commission_amount": amount,
            "commission_rate": rate,
            "commission_calculated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", lead_id).execute()
        log.info("db.commission_attached", lead_id=lead_id, amount=amount, rate=rate)

    def attach_whatsapp_result(
        self,
        lead_id: str,
        sent: bool,
        message_id: str | None = None,
        error: str | None = None,
    ) -> None:
        payload = {
            "whatsapp_sent": sent,
            "whatsapp_sent_at": datetime.now(timezone.utc).isoformat() if sent else None,
            "whatsapp_message_id": message_id,
            "whatsapp_error": error,
        }
        self.client.table("leads").update(payload).eq("id", lead_id).execute()

    def get_leads_by_flipper(
        self, flipper_discord_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        resp = (
            self.client.table("leads")
            .select("*")
            .eq("flipper_discord_id", flipper_discord_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []

    def find_duplicate_leads(
        self, *, phone: str, email: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Vráti leady kde sa zhoduje client_phone ALEBO client_email.
        Predpoklady: phone už normalizovaný (+421...), email už lowercased — robí to modal.
        Zoradené od najnovších. Používa sa v process_lead_submission pre soft dedup warning."""
        resp = (
            self.client.table("leads")
            .select(
                "id, client_phone, client_email, status, "
                "flipper_discord_id, flipper_discord_name, created_at"
            )
            .or_(f"client_phone.eq.{phone},client_email.eq.{email}")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data or []

    def get_leads_for_flipper_in_range(
        self,
        flipper_discord_id: str,
        *,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        """Vráti leady jedného flippera vytvorené v rozsahu [start, end).
        Používa sa pre mesačný report."""
        resp = (
            self.client.table("leads")
            .select("id, status, created_at, car_make, car_model, commission_amount")
            .eq("flipper_discord_id", flipper_discord_id)
            .gte("created_at", start.isoformat())
            .lt("created_at", end.isoformat())
            .execute()
        )
        return resp.data or []

    def get_distinct_flippers_in_range(
        self, *, start: datetime, end: datetime
    ) -> list[dict[str, str]]:
        """Vráti zoznam (id, name) všetkých flipperov, ktorí pridali aspoň jeden lead
        v období [start, end). Used by ReportsCog na zistenie pre koho generovať report."""
        resp = (
            self.client.table("leads")
            .select("flipper_discord_id, flipper_discord_name")
            .gte("created_at", start.isoformat())
            .lt("created_at", end.isoformat())
            .execute()
        )
        # Deduplikácia v Pythone — supabase-py nevie DISTINCT priamo
        seen: dict[str, str] = {}
        for row in resp.data or []:
            fid = row["flipper_discord_id"]
            if fid not in seen:
                seen[fid] = row["flipper_discord_name"]
        return [{"id": fid, "name": name} for fid, name in seen.items()]

    def get_lead_by_message(self, message_id: str) -> dict[str, Any] | None:
        resp = (
            self.client.table("leads")
            .select("*")
            .eq("discord_message_id", message_id)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
