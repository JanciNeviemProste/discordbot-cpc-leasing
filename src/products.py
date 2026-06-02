"""Register produktov — jeden zdroj pravdy pre príkazy, polia formulárov,
Telegram správu a mapovanie do spoločného Google Sheetu.

Čisté dáta (žiadny discord import), nech sa to dá ľahko testovať.
"""
from __future__ import annotations

from dataclasses import dataclass

# Cieľové generické stĺpce v spoločnom hárku, do ktorých sa extra polia mapujú.
COLUMN_PREDMET = "predmet"
COLUMN_SUMA = "suma"
COLUMN_DOPLNOK = "doplnok"
_VALID_COLUMNS = {COLUMN_PREDMET, COLUMN_SUMA, COLUMN_DOPLNOK}


@dataclass(frozen=True)
class ExtraField:
    """Produktovo-špecifické pole formulára (okrem fixných Meno/Email/Telefón)."""

    key: str
    label: str
    placeholder: str
    column: str                       # kam v Sheete: predmet | suma | doplnok
    paragraph: bool = False           # viacriadkový input
    validator: str | None = None      # "price" | "url" | None
    required: bool = True


@dataclass(frozen=True)
class Product:
    key: str
    command: str
    typ: str                          # hodnota v stĺpci Typ produktu + titulok Telegramu
    emoji: str
    extras: list[ExtraField]          # presne 2 (Discord modal: 3 fixné + 2 = 5)


PRODUCTS: dict[str, Product] = {
    "leasing": Product(
        key="leasing", command="leasing", typ="Leasing", emoji="🚗",
        extras=[
            ExtraField("cena", "Cena", "napr. 12 500 €", COLUMN_SUMA, validator="price"),
            ExtraField("car_link", "Link na auto", "https://www.autobazar.eu/...",
                       COLUMN_PREDMET, validator="url"),
        ],
    ),
    "pzp": Product(
        key="pzp", command="pzp", typ="PZP", emoji="🚗",
        extras=[
            ExtraField("vozidlo", "Vozidlo (značka, model, rok)",
                       "napr. Škoda Octavia 2018", COLUMN_PREDMET),
            ExtraField("ecv", "EČV / ŠPZ", "napr. BA123AB", COLUMN_DOPLNOK),
        ],
    ),
    "kasko": Product(
        key="kasko", command="kasko", typ="Kasko", emoji="🚗",
        extras=[
            ExtraField("vozidlo", "Vozidlo (značka, model, rok)",
                       "napr. Škoda Octavia 2018", COLUMN_PREDMET),
            ExtraField("hodnota", "Hodnota vozidla (€)", "napr. 15 000 €",
                       COLUMN_SUMA, validator="price"),
        ],
    ),
    "ine": Product(
        key="ine", command="ine", typ="Iné", emoji="📋",
        extras=[
            ExtraField("popis", "Čo klient potrebuje", "stručný popis požiadavky",
                       COLUMN_PREDMET, paragraph=True),
            ExtraField("poznamka", "Poznámka", "voliteľné", COLUMN_DOPLNOK,
                       paragraph=True, required=False),
        ],
    ),
}

# Poradie produktov (Typ produktu dropdown v Sheete).
PRODUCT_TYP_OPTIONS = [p.typ for p in PRODUCTS.values()]
