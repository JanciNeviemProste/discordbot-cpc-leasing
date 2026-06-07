"""Unit testy pre LeadPanelView — persistentný tlačidlový panel.

discord.py View sa inštanciuje len v bežiacom event loope, preto async.
"""
from __future__ import annotations

import pytest

from src.views.lead_panel_view import LeadPanelView


@pytest.mark.asyncio
async def test_panel_is_persistent() -> None:
    # timeout=None → view nikdy nevyprší (nutné pre persistenciu po reštarte).
    assert LeadPanelView().timeout is None


@pytest.mark.asyncio
async def test_panel_button_has_stable_custom_id() -> None:
    # Bez stabilného custom_id by sa staré tlačidlo po reštarte „odpojilo".
    custom_ids = [c.custom_id for c in LeadPanelView().children]
    assert "lead_panel:open" in custom_ids
