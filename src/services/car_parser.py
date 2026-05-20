"""Car listing parser — extrahuje značku, model, rok, cenu, km, VIN z URL.

Stratégia:
1. Stiahni HTML cez httpx (rešpektuj timeout)
2. Skús JSON-LD structured data (najuniverzálnejšie — väčšina seriózných stránok ho má)
3. Fallback na site-specific selectors podľa domény
4. Vráť LeadCarData (všetky polia voliteľné, len čo sa podarilo nájsť)

Podporované domény (best-effort, HTML sa môže meniť):
- autobazar.eu, autobazar.sk
- mobile.de
- autoscout24.de, autoscout24.sk
- autoplus.sk
- sauto.cz, tipcars.com
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from src.config import get_settings
from src.utils.logger import get_logger

log = get_logger(__name__)

USER_AGENTS = [
    # Chrome / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36",
    # Firefox / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) "
    "Gecko/20100101 Firefox/128.0",
    # Safari / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.6 Safari/605.1.15",
]

# Stavové kódy / signály ktoré indikujú anti-bot blokáciu — vtedy retry s iným UA
_BLOCK_STATUS_CODES = {403, 429, 503}
_CLOUDFLARE_MARKERS = ("just a moment", "cf-ray", "cf-mitigated", "attention required")


@dataclass
class LeadCarData:
    url: str
    make: str | None = None
    model: str | None = None
    year: int | None = None
    price: float | None = None
    fuel: str | None = None
    km: int | None = None
    vin: str | None = None
    raw_title: str | None = None
    # UI-only warning (nepersistuje sa do DB cez to_dict)
    parse_warning: str | None = None

    @property
    def is_empty(self) -> bool:
        """True ak parser nezistil žiadne použiteľné polia (raw_title sa neráta)."""
        return not any([self.make, self.model, self.year, self.price, self.km, self.fuel, self.vin])

    def to_dict(self) -> dict[str, Any]:
        return {
            "car_url": self.url,
            "car_make": self.make,
            "car_model": self.model,
            "car_year": self.year,
            "car_price": self.price,
            "car_fuel": self.fuel,
            "car_km": self.km,
            "car_vin": self.vin,
        }


async def fetch_car_data(url: str) -> LeadCarData:
    """Hlavný entry point. Nikdy neraise-uje — vždy vráti LeadCarData
    (môže byť prázdny, ak parsing zlyhal). Pri anti-bot blokácii retryuje s iným UA."""
    settings = get_settings()
    result = LeadCarData(url=url)

    html = await _fetch_with_retries(url, timeout=settings.car_parser_timeout, result=result)
    if html is None:
        # parse_warning už nastavený v _fetch_with_retries
        return result

    soup = BeautifulSoup(html, "lxml")

    # 1) JSON-LD ako prvý pokus
    _parse_jsonld(soup, result)

    # 2) site-specific dopĺňanie chýbajúcich polí
    domain = urlparse(url).netloc.lower().replace("www.", "")
    parser_fn = SITE_PARSERS.get(domain)
    if parser_fn:
        try:
            parser_fn(soup, result)
        except Exception as e:  # noqa: BLE001
            log.warning("car_parser.site_parser_failed", domain=domain, error=str(e))

    # 3) Generic title fallback
    if not result.raw_title:
        title_tag = soup.find("title")
        if title_tag:
            result.raw_title = title_tag.text.strip()

    # 4) Empty-result warning — fetch prešiel, ale neextrahovali sme nič užitočné
    if result.is_empty:
        result.parse_warning = (
            "Z URL sa nepodarilo vytiahnuť údaje o aute. "
            "Lead je uložený s linkom — over a doplň ručne (cez `/lead-info`)."
        )

    log.info("car_parser.parsed", url=url, data=result.to_dict(), warning=result.parse_warning)
    return result


async def _fetch_with_retries(
    url: str, *, timeout: float, result: LeadCarData
) -> str | None:
    """Stiahni HTML, retry s iným User-Agentom pri 403/429/503 alebo Cloudflare markeri.
    Pri zlyhaní nastav result.parse_warning a vráť None."""
    last_error: str | None = None
    for attempt, ua in enumerate(USER_AGENTS, start=1):
        try:
            async with httpx.AsyncClient(
                headers={
                    "User-Agent": ua,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "sk,cs,en;q=0.8",
                },
                timeout=timeout,
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
        except httpx.TimeoutException:
            last_error = "timeout"
            log.warning("car_parser.timeout", url=url, attempt=attempt)
            continue
        except httpx.HTTPError as e:
            last_error = f"http_error: {e.__class__.__name__}"
            log.warning("car_parser.http_error", url=url, attempt=attempt, error=str(e))
            continue

        if resp.status_code in _BLOCK_STATUS_CODES or _looks_like_cloudflare(resp):
            last_error = f"blocked_{resp.status_code}"
            log.warning(
                "car_parser.blocked",
                url=url,
                attempt=attempt,
                status=resp.status_code,
                cf_ray=resp.headers.get("cf-ray"),
            )
            continue

        if resp.status_code >= 400:
            last_error = f"http_{resp.status_code}"
            log.warning("car_parser.bad_status", url=url, status=resp.status_code)
            # 404/410 nemá zmysel retry-ovať — iný UA to nezmení
            if resp.status_code in (404, 410):
                break
            continue

        return resp.text

    # Všetky pokusy zlyhali — nastav warning podľa typu chyby
    if last_error and last_error.startswith("blocked_"):
        result.parse_warning = (
            "Stránka blokuje automatické sťahovanie (pravdepodobne Cloudflare). "
            "Lead je uložený s linkom — otvor URL ručne a doplň údaje cez `/lead-info`."
        )
    elif last_error == "timeout":
        result.parse_warning = (
            "Stránka neodpovedala v časovom limite. "
            "Lead je uložený s linkom — over manuálne."
        )
    else:
        result.parse_warning = (
            f"Nepodarilo sa stiahnuť stránku ({last_error or 'unknown'}). "
            "Lead je uložený s linkom — over manuálne."
        )
    return None


def _looks_like_cloudflare(resp: httpx.Response) -> bool:
    """Heuristika — Cloudflare challenge page má cf-ray/cf-mitigated header
    alebo body obsahuje 'Just a moment'."""
    if resp.headers.get("cf-mitigated") == "challenge":
        return True
    if resp.status_code == 200:
        # Niektoré CF challenge stránky vracajú 200 s HTML challengom
        body_snippet = resp.text[:2048].lower() if resp.text else ""
        return any(marker in body_snippet for marker in _CLOUDFLARE_MARKERS)
    return False


# ============================================================
# JSON-LD generic parser
# ============================================================
def _parse_jsonld(soup: BeautifulSoup, result: LeadCarData) -> None:
    """Hľadá schema.org/Car alebo Product/Vehicle markup."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue

        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            type_ = item.get("@type", "")
            if isinstance(type_, list):
                type_ = type_[0] if type_ else ""

            if type_ in ("Car", "Vehicle", "Product"):
                result.make = result.make or _get_str(item, "brand", "name") or _get_str(item, "manufacturer")
                result.model = result.model or _get_str(item, "model")
                result.year = result.year or _get_int(item, "vehicleModelDate") or _get_int(item, "productionDate")
                result.km = result.km or _get_int(item, "mileageFromOdometer", "value")
                result.fuel = result.fuel or _get_str(item, "fuelType")
                result.vin = result.vin or _get_str(item, "vehicleIdentificationNumber")

                offers = item.get("offers", {})
                if isinstance(offers, list) and offers:
                    offers = offers[0]
                if isinstance(offers, dict):
                    price = offers.get("price")
                    if price and not result.price:
                        try:
                            result.price = float(str(price).replace(",", "."))
                        except (ValueError, TypeError):
                            pass

                result.raw_title = result.raw_title or _get_str(item, "name")


def _get_str(d: dict[str, Any], *keys: str) -> str | None:
    cur: Any = d
    for k in keys:
        if isinstance(cur, dict):
            cur = cur.get(k)
        else:
            return None
    if isinstance(cur, dict):
        cur = cur.get("name") or cur.get("@value")
    return str(cur) if cur else None


def _get_int(d: dict[str, Any], *keys: str) -> int | None:
    v = _get_str(d, *keys)
    if v is None:
        return None
    digits = re.sub(r"[^\d]", "", v)
    return int(digits) if digits else None


# ============================================================
# Site-specific parsers (fallback ak JSON-LD chýba/nestačí)
# ============================================================
def _parse_autobazar_eu(soup: BeautifulSoup, result: LeadCarData) -> None:
    # Title typu "Audi A4 Avant 2.0 TDI ..."
    h1 = soup.find("h1")
    if h1 and not result.raw_title:
        result.raw_title = h1.get_text(strip=True)

    # Cena
    price_tag = soup.select_one('[class*="price"], [data-price]')
    if price_tag and not result.price:
        result.price = _extract_price(price_tag.get_text())

    # Tabuľka parametrov — autobazar.eu používa <dt>/<dd> alebo <li>
    for row in soup.select("li, tr, .param"):
        text = row.get_text(" ", strip=True).lower()
        if "rok" in text and not result.year:
            result.year = _extract_year(text)
        if ("km" in text or "najazden" in text) and not result.km:
            result.km = _extract_km(text)
        if "palivo" in text and not result.fuel:
            result.fuel = _extract_fuel(text)


def _parse_mobile_de(soup: BeautifulSoup, result: LeadCarData) -> None:
    h1 = soup.find("h1")
    if h1 and not result.raw_title:
        result.raw_title = h1.get_text(strip=True)

    price_tag = soup.select_one('[data-testid="prime-price"], .price-block, .h3.u-text-bold')
    if price_tag and not result.price:
        result.price = _extract_price(price_tag.get_text())


def _parse_autoscout24(soup: BeautifulSoup, result: LeadCarData) -> None:
    h1 = soup.find("h1")
    if h1 and not result.raw_title:
        result.raw_title = h1.get_text(strip=True)

    price_tag = soup.select_one('[class*="PriceInfo"], [data-testid="price"]')
    if price_tag and not result.price:
        result.price = _extract_price(price_tag.get_text())


def _parse_autoplus(soup: BeautifulSoup, result: LeadCarData) -> None:
    h1 = soup.find("h1")
    if h1 and not result.raw_title:
        result.raw_title = h1.get_text(strip=True)


def _parse_sauto_cz(soup: BeautifulSoup, result: LeadCarData) -> None:
    h1 = soup.find("h1")
    if h1 and not result.raw_title:
        result.raw_title = h1.get_text(strip=True)


def _parse_tipcars(soup: BeautifulSoup, result: LeadCarData) -> None:
    h1 = soup.find("h1")
    if h1 and not result.raw_title:
        result.raw_title = h1.get_text(strip=True)


SITE_PARSERS = {
    "autobazar.eu": _parse_autobazar_eu,
    "autobazar.sk": _parse_autobazar_eu,
    "mobile.de": _parse_mobile_de,
    "suchen.mobile.de": _parse_mobile_de,
    "autoscout24.de": _parse_autoscout24,
    "autoscout24.sk": _parse_autoscout24,
    "autoscout24.com": _parse_autoscout24,
    "autoplus.sk": _parse_autoplus,
    "sauto.cz": _parse_sauto_cz,
    "tipcars.com": _parse_tipcars,
}


# ============================================================
# Helpers
# ============================================================
def _extract_price(text: str) -> float | None:
    """Vytiahne číslo z 'cena 12 999 € / 12.999 EUR / 12,999 $'."""
    cleaned = re.sub(r"[^\d,.\s]", "", text)
    cleaned = cleaned.replace(" ", "").replace(",", ".")
    parts = cleaned.split(".")
    if len(parts) > 2:
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        val = float(cleaned)
        return val if 100 < val < 10_000_000 else None
    except ValueError:
        return None


def _extract_year(text: str) -> int | None:
    m = re.search(r"\b(19|20)\d{2}\b", text)
    if m:
        y = int(m.group(0))
        if 1980 <= y <= 2030:
            return y
    return None


def _extract_km(text: str) -> int | None:
    m = re.search(r"(\d{1,3}(?:[\s.,]\d{3})*)\s*km", text)
    if m:
        return int(re.sub(r"[^\d]", "", m.group(1)))
    return None


def _extract_fuel(text: str) -> str | None:
    fuels = {
        "benzín": "Benzín",
        "benzin": "Benzín",
        "nafta": "Diesel",
        "diesel": "Diesel",
        "hybrid": "Hybrid",
        "elektr": "Elektro",
        "lpg": "LPG",
        "cng": "CNG",
    }
    t = text.lower()
    for k, v in fuels.items():
        if k in t:
            return v
    return None
