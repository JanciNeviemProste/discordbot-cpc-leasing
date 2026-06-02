"""Unit testy pre LeadModal — predvyplnenie polí pri oprave.

discord.py Modal/View sa inštanciuje len v bežiacom event loope, preto async.
"""
from __future__ import annotations

import pytest

from src.modals.lead_modal import LeadModal


@pytest.mark.asyncio
async def test_modal_prefill_sets_defaults() -> None:
    d = {
        "client_name": "Ján Novák",
        "client_email": "jan@gmail.com",
        "client_phone": "+421905123456",
        "price": "12 500 €",
        "car_link": "https://autobazar.eu/123",
    }
    m = LeadModal(defaults=d)
    assert m.client_name.default == "Ján Novák"
    assert m.client_email.default == "jan@gmail.com"
    assert m.client_phone.default == "+421905123456"
    assert m.price.default == "12 500 €"
    assert m.car_link.default == "https://autobazar.eu/123"


@pytest.mark.asyncio
async def test_modal_without_defaults_has_no_prefill() -> None:
    m = LeadModal()
    assert m.client_name.default is None
    assert m.client_phone.default is None


@pytest.mark.asyncio
async def test_modal_empty_string_default_becomes_none() -> None:
    m = LeadModal(defaults={"client_name": "", "client_phone": "+421905123456"})
    assert m.client_name.default is None      # prázdne → None (žiadne predvyplnenie)
    assert m.client_phone.default == "+421905123456"
