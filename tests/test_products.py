"""Unit testy pre register produktov."""
from __future__ import annotations

from src.products import _VALID_COLUMNS, PRODUCTS


def test_four_products() -> None:
    assert set(PRODUCTS) == {"leasing", "pzp", "kasko", "ine"}


def test_each_product_has_two_extras() -> None:
    for p in PRODUCTS.values():
        assert len(p.extras) == 2, f"{p.key} musí mať presne 2 extra polia (Discord limit 5)"


def test_extra_columns_valid() -> None:
    for p in PRODUCTS.values():
        for ef in p.extras:
            assert ef.column in _VALID_COLUMNS


def test_commands_unique_and_match_key() -> None:
    cmds = [p.command for p in PRODUCTS.values()]
    assert len(cmds) == len(set(cmds))
    for key, p in PRODUCTS.items():
        assert p.command == key


def test_typ_labels() -> None:
    assert PRODUCTS["leasing"].typ == "Leasing"
    assert PRODUCTS["pzp"].typ == "PZP"
    assert PRODUCTS["kasko"].typ == "Kasko"
    assert PRODUCTS["ine"].typ == "Iné"
