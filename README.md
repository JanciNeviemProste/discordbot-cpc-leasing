# Synapse Drive Bot

**Discord bot pre drive.sk — flipper napíše `/leasing`, vyplní formulár, lead ide na Telegram Kristiánovi (finančák) a zároveň sa zapíše do Google Sheetu pre Petra (majiteľ).**

Klient: **Peťo Švikruha (drive.sk)** · Stack: **Python 3.11 + discord.py 2.4 + Telegram Bot API + Google Sheets**

Žiadna databáza (evidencia je Google Sheet). Žiadne status buttony. Žiadny scraper. Minimal flow.

---

## TL;DR

```bash
git clone <repo>
cd synapse-drive-bot
python -m venv .venv
.venv\Scripts\activate            # Win   (alebo: source .venv/bin/activate)
pip install -r requirements.txt
Copy-Item .env.example .env       # vyplň hodnoty (zoznam nižšie)
python -m scripts.preflight       # voliteľné: over Discord + Telegram creds
python -m src.bot
```

V Discorde: `/leasing` → potvrď GDPR → vyplň formulár → Kristián má Telegram správu + riadok pribudne v Google Sheete.

---

## Cieľový flow

1. Flipper je v dedikovanom kanáli (napr. `#leasing`) a napíše `/leasing`
2. Bot pošle **ephemerálnu** GDPR výzvu s tlačidlom *„Mám súhlas, pokračovať"*
3. Po kliku sa otvorí **modal** s 5 povinnými poľami:
   - Meno a priezvisko klienta
   - Email (validácia)
   - Telefón (SK/CZ validácia)
   - Cena auta
   - Link na auto (URL inzerátu)
4. Po odoslaní bot:
   - pošle **Telegram správu Kristiánovi** (finančák) — kritická cesta
   - zapíše **riadok do Google Sheetu** pre Petra (majiteľ) — evidencia, best-effort
5. Flipper dostane ephemerálne `✅ Odoslané Kristiánovi`

> Google Sheet je voliteľný: ak `GOOGLE_SHEET_ID` nie je nastavený, zápis sa preskočí a beží len Telegram.

---

## Setup

### 1. Discord bot

1. <https://discord.com/developers/applications> → **New Application**
2. **Bot** → Reset Token → ulož ako `DISCORD_TOKEN`
3. **OAuth2 → URL Generator**: scopes `bot` + `applications.commands`, permission `Send Messages` + `Use Slash Commands`
4. Otvor URL, pridaj bota na server drive.sk
5. **Server ID** (developer mode → Copy Server ID) → `DISCORD_GUILD_ID`
6. (Voliteľné) ID kanála kde `/leasing` má fungovať → `DISCORD_LEASING_CHANNEL_ID`. Ak prázdne, command pôjde všade.

### 2. Telegram bot

1. V Telegrame nájdi **@BotFather** → pošli `/newbot`
2. Daj botovi meno (napr. `drive.sk leasing bot`) a username — musí končiť na `bot` (napr. `drive_sk_leasing_bot`)
3. BotFather vráti token v tvare `123456789:AAFxxx...` → ulož ako `TELEGRAM_BOT_TOKEN`
4. **Kristián** otvorí `t.me/<bot_username>` (napr. `t.me/drive_sk_leasing_bot`) a klikne **Start**
   - Alternatíva: vytvor group chat, pridaj tam Kristiána aj bota
5. **Získaj chat ID:**
   - V browseri otvor `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - Nájdi `"chat":{"id":<číslo>,...}` — to je `TELEGRAM_CHAT_ID`
   - DM = kladné číslo (`987654321`), group = záporné (`-100123456789`)
6. Ak `getUpdates` vráti prázdny `result: []`, Kristián ešte botu nenapísal — over že klikol Start, potom refresh

### 3. Google Sheets (evidencia pre Petra)

Bot zapisuje každý lead ako nový riadok cez **service account** (žiadny OAuth login).

1. <https://console.cloud.google.com> → vytvor (alebo vyber) projekt
2. **APIs & Services → Library** → zapni **Google Sheets API**
3. **APIs & Services → Credentials → Create Credentials → Service account** → daj meno (napr. `drive-bot`) → Create
4. Pri service accounte: **Keys → Add Key → Create new key → JSON** → stiahne sa súbor
5. Premenuj ho na `google-service-account.json` a daj do priečinka `secrets/` v projekte (je v `.gitignore`)
6. Otvor ten JSON, nájdi `"client_email": "...@...iam.gserviceaccount.com"` — **skopíruj ten email**
7. Vytvor (alebo otvor) cieľový Google Sheet → **Share** → vlož ten email → rola **Editor** → Send
8. Z URL Sheetu skopíruj **Sheet ID** (časť medzi `/d/` a `/edit`) → `GOOGLE_SHEET_ID`

Hlavičku (Dátum, Meno, Email, Telefón, Cena, Link, Flipper) zapíše bot sám pri prvom leade, ak je list prázdny.

### 4. `.env`

Vytvor zo šablóny:

```powershell
Copy-Item .env.example .env
```

Premenné:

```
DISCORD_TOKEN=
DISCORD_GUILD_ID=
DISCORD_LEASING_CHANNEL_ID=        # voliteľné — kanál kde /leasing funguje
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=                  # chat ID Kristiána (DM) alebo group
GOOGLE_SHEET_ID=                   # voliteľné — ak prázdne, beží len Telegram
GOOGLE_SERVICE_ACCOUNT_FILE=secrets/google-service-account.json
LOG_LEVEL=INFO
ENVIRONMENT=production
```

### 5. Preflight (voliteľné, odporúčané)

```powershell
.venv\Scripts\python -m scripts.preflight
```

Overí Discord token + Telegram + (ak je nastavený) Google Sheet bez spustenia bota. Cieľ: `3/3 PASS` (alebo `2/2` ak Sheet nepoužívaš).

### 6. Spustenie

```powershell
.venv\Scripts\python -m src.bot
```

Mal by si vidieť `bot.commands_synced` a `bot.ready`. V Discorde napíš `/leasing`.

---

## Súborová štruktúra

```
synapse-drive-bot/
├── README.md
├── SIMPLIFY-PROMPT.md       ← pôvodná špec (SUPERSEDED Telegram swapom)
├── requirements.txt
├── .env.example
├── src/
│   ├── bot.py               ← entry point
│   ├── config.py            ← Pydantic settings
│   ├── cogs/leads.py        ← /leasing + submit pipeline
│   ├── modals/lead_modal.py ← 5-field form
│   ├── views/gdpr_view.py   ← GDPR consent button
│   ├── services/
│   │   ├── telegram.py      ← Telegram Bot API klient (Kristián)
│   │   ├── sheets.py        ← Google Sheets evidencia (Peter)
│   │   └── validators.py    ← phone/email/cena/url
│   └── utils/logger.py      ← structlog setup
├── scripts/
│   └── preflight.py         ← credential validator
└── tests/
    ├── test_basic.py        ← validátor testy
    └── test_preflight.py    ← preflight unit testy
```

---

## Troubleshooting

| Problém | Riešenie |
|---|---|
| Slash command sa nezobrazí | Sync je per-guild, po reštarte trvá ~1 min |
| `401 Unauthorized` z `/sendMessage` | Token je zlý — BotFather → `/token` na regeneráciu |
| `chat not found` | Kristián botu nenapísal `/start`, alebo zlý `TELEGRAM_CHAT_ID`. Refresh cez `getUpdates` |
| Markdown sa zobrazí ako text (`\*hviezdičky\*`) | Chýba escapovanie MarkdownV2 — over že máš najnovšiu `_escape_markdown_v2()` |
| Group chat ID prestal fungovať | Group prešiel na supergroup — znova `getUpdates`, nové ID (zvyčajne `-100...`) |
| `Forbidden: bot was blocked by the user` | Kristián botu zablokoval. Nech ho odblokuje a znova `/start` |
| Sheets: `prístup zamietnutý (403)` | Sheet nie je zdieľaný so service-account emailom — Share → email z `client_email` → Editor |
| Sheets: `sheet sa nenašiel` | Zlý `GOOGLE_SHEET_ID` — je to časť URL medzi `/d/` a `/edit` |
| Sheets: `súbor neexistuje` | JSON kľúč nie je na ceste z `GOOGLE_SERVICE_ACCOUNT_FILE` (default `secrets/`) |
| Lead prišiel Kristiánovi, ale nie do Sheetu | Bot to oznámi flipperovi (`⚠️ Zápis do evidencie zlyhal`). Pozri logy `leads.sheets_failed` |

---

## Licencia & ownership

Postavené: **Synapse Studio** (Ján Stas) pre **drive.sk** (Peter Švikruha).
