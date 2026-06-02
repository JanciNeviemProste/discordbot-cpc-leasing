"""Unit testy pre LeadModal — produktové polia + predvyplnenie (async, discord
Modal sa inštanciuje len v bežiacom event loope)."""
from __future__ import annotations

import pytest

from src.modals.lead_modal import LeadModal
from src.products import PRODUCTS


@pytest.mark.asyncio
async def test_leasing_modal_has_five_fields() -> None:
    m = LeadModal(PRODUCTS["leasing"])
    assert len(m.children) == 5  # 3 fixné + 2 extra
    assert set(m._inputs) == {"client_name", "client_email", "client_phone", "cena", "car_link"}


@pytest.mark.asyncio
async def test_pzp_modal_fields() -> None:
    m = LeadModal(PRODUCTS["pzp"])
    assert set(m._inputs) == {"client_name", "client_email", "client_phone", "vozidlo", "ecv"}


@pytest.mark.asyncio
async def test_ine_modal_fields() -> None:
    m = LeadModal(PRODUCTS["ine"])
    assert set(m._inputs) == {"client_name", "client_email", "client_phone", "popis", "poznamka"}


@pytest.mark.asyncio
async def test_prefill_sets_defaults() -> None:
    m = LeadModal(PRODUCTS["leasing"], defaults={
        "client_name": "Ján Novák", "client_phone": "+421905123456", "cena": "12 500 €",
    })
    assert m._inputs["client_name"].default == "Ján Novák"
    assert m._inputs["client_phone"].default == "+421905123456"
    assert m._inputs["cena"].default == "12 500 €"


@pytest.mark.asyncio
async def test_empty_default_becomes_none() -> None:
    m = LeadModal(PRODUCTS["leasing"], defaults={"client_name": ""})
    assert m._inputs["client_name"].default is None
