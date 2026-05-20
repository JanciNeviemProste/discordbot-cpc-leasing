# SIMPLIFY-PROMPT.md — Zjednodušenie Synapse Drive Bot

> Inštrukcie pre Claude Code. Prečítaj celé, potom začni. Pýtaj sa ak niečo nie je jasné.

## Cieľ

Existujúci skeleton je príliš komplexný. Zjednoduš ho na **minimálnu verziu**: flipper napíše príkaz, potvrdí GDPR, vyplní formulár, údaje sa pošlú Kristiánovi na WhatsApp. Nič viac.

**Žiadna databáza. Žiadne Google Sheets. Žiadne status buttony. Žiadny car parser. Žiadne embed karty v kanáli.**

## Cieľový flow (presne toto, nič navyše)

1. Flipper je v dedikovanom kanáli (napr. `#leasing`) a napíše `/leasing`
2. Bot pošle **ephemerálnu** správu s GDPR textom + tlačidlom *„Mám súhlas, pokračovať"*
3. Po kliku sa otvorí **modal formulár** s poľami:
   - Meno a priezvisko klienta (povinné)
   - Telefón klienta (povinné, validácia SK/CZ)
   - Email klienta (povinné, validácia)
   - Auto — link alebo popis (povinné, voľný text)
   - Poznámka (voliteľné)
4. Po odoslaní bot:
   - Pošle **WhatsApp správu Kristiánovi** s týmito údajmi (cez Meta Cloud API template)
   - Pošle flipperovi **ephemerálne potvrdenie** („✅ Odoslané Kristiánovi")
5. Hotovo.

## Čo ZACHOVAJ z existujúceho skeletonu

- `src/bot.py` — ale zjednoduš (viď nižšie)
- `src/config.py` — ale vyhoď nepotrebné premenné (viď nižšie)
- `src/services/whatsapp.py` — **bez zmeny**, funguje
- `src/services/validators.py` — **bez zmeny** (telefón, email validácia)
- `src/utils/logger.py` — **bez zmeny**
- `src/modals/lead_modal.py` — zachovaj, ale vyhoď car parser volanie (viď nižšie)
- `src/views/gdpr_view.py` — zachovaj, len uprav aby otváral nový modal
- `requirements.txt`, `.gitignore` — zachovaj (môžeš vyhodiť supabase, beautifulsoup4, lxml z requirements)

## Čo ZMAŽ úplne

- `src/database.py`
- `src/services/car_parser.py`
- `src/views/lead_view.py` (status buttony)
- `src/utils/embeds.py`
- `src/utils/gdpr.py` (maskovanie už netreba — dáta idú len Kristiánovi)
- `supabase/` celý priečinok (schema.sql)
- `tests/test_basic.py` — prepíš len na testy validátorov (vyhoď testy maskovania)

## Čo ZMEŇ

### `src/config.py`

Vyhoď tieto premenné (už nepotrebné):
- `supabase_url`, `supabase_service_key`
- `discord_leads_channel_id` → premenuj na `discord_leasing_channel_id` (kanál kde `/leasing` funguje; voliteľné obmedzenie)
- `discord_kristian_user_id` → **vyhoď** (Kristiána už nepingujeme v Discorde, len WhatsApp)
- `discord_admin_role_id` → **vyhoď**
- `car_parser_timeout` → **vyhoč**

Finálne premenné v `.env`:
```
DISCORD_TOKEN=
DISCORD_GUILD_ID=
DISCORD_LEASING_CHANNEL_ID=        # voliteľné — kanál kde /leasing funguje
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_RECIPIENT_NUMBER=         # Kristiánovo WA číslo bez +
WHATSAPP_TEMPLATE_NAME=novy_lead
WHATSAPP_TEMPLATE_LANG=sk
WHATSAPP_API_VERSION=v21.0
LOG_LEVEL=INFO
ENVIRONMENT=production
```
Aktualizuj aj `.env.example`.

### `src/cogs/leads.py`

Prepíš na minimum:
- Príkaz `/leasing` (premenuj z `/novy-zaujemca`)
- Ak je nastavený `DISCORD_LEASING_CHANNEL_ID`, povoľ príkaz len v tom kanáli (inak ephemerálne odmietni: „Tento príkaz funguje len v #leasing")
- Vyhoď `/moje-leady` a `/lead-info` (potrebovali databázu)
- `process_lead_submission()` zjednoduš: žiadny DB insert, žiadny embed do kanála. Len:
  1. Zlož popis auta z formulára (text ako ho flipper zadal)
  2. Pošli WhatsApp Kristiánovi cez `whatsapp.send_lead_notification(...)`
  3. Pošli flipperovi ephemerálne potvrdenie (vrátane info či WA prešiel alebo zlyhal)

### `src/modals/lead_modal.py`

- Premenuj title na „Žiadosť o leasing — drive.sk"
- Vyhoď import a volanie `fetch_car_data` (car parser). Pole „Auto" ostáva, ale berie sa ako čistý text (link aj popis pošleme Kristiánovi tak ako sú).
- Validácia telefónu a emailu **ostáva**.

### `src/bot.py`

- Vyhoď `self.add_view(LeadStatusView())` (žiadne persistent views už nie sú)
- Vyhoď import `LeadStatusView`
- Zvyšok (WhatsApp client init, cog load, command sync, graceful shutdown) ostáva

### `src/services/whatsapp.py`

Bez zmeny v logike. Len over že template `novy_lead` má 5 parametrov v poradí:
1. meno klienta
2. telefón klienta
3. auto (text)
4. meno flippera
5. (pôvodne Discord link) → **zmeň na poznámku** alebo prázdne, lebo Discord link už nedáva zmysel

Uprav `send_lead_notification` signatúru: namiesto `discord_message_url` daj `note` (poznámka z formulára, alebo „-" ak prázdna). Aktualizuj aj template popis v docstringu.

## Nová WhatsApp template (pre Janči-ho na schválenie v Meta)

Name: `novy_lead`, Category: Utility, Language: Slovak

```
🚗 *Nová žiadosť o leasing — drive.sk*

Klient: {{1}}
Telefón: {{2}}
Auto: {{3}}
Flipper: {{4}}
Poznámka: {{5}}
```

## Akceptačné kritériá (otestuj na konci)

```
[ ] python -c "from src.bot import SynapseDriveBot"   # importy fungujú
[ ] python -c "from src.config import get_settings; get_settings()"  # config validný
[ ] pytest tests/ -v                                   # validátor testy passujú
[ ] V Discorde /leasing otvorí GDPR výzvu
[ ] Klik na tlačidlo otvorí formulár
[ ] Vyplnenie + odoslanie → WhatsApp príde na test číslo
[ ] Flipper dostane ephemerálne potvrdenie
[ ] Neplatný telefón/email → ephemerálna chyba, formulár sa neodošle
[ ] Žiadne referencie na database/supabase/car_parser/embeds nezostali v kóde (grep)
```

## Štýl (dodržuj)

- UI v slovenčine, kód a komentáre v angličtine
- Type hints všade, `from __future__ import annotations`
- Logy cez structlog so structured fields, nie f-stringy
- Žiadne `print()`, žiadny silent `except: pass`
- WhatsApp chyba nezablokuje flow — len ju oznám flipperovi v potvrdení

## Na záver

Aktualizuj `README.md` aby zodpovedal zjednodušenej verzii (vyhoď sekcie o Supabase, status workflow, car parser). Nechaj sekciu o WhatsApp Cloud API setupe — tá je stále kľúčová.
