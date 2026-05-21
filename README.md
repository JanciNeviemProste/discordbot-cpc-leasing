# Synapse Drive Bot

**Discord bot pre drive.sk — flipper napíše `/leasing`, vyplní formulár, údaje klienta sa pošlú na Telegram finančnému poradcovi Kristiánovi.**

Klient: **Peťo Švikruha (drive.sk)** · Stack: **Python 3.11 + discord.py 2.4 + Telegram Bot API**

Žiadna databáza. Žiadne status buttony. Žiadny scraper. Minimal flow.

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

V Discorde: `/leasing` → potvrď GDPR → vyplň formulár → Kristián má Telegram správu.

---

## Cieľový flow

1. Flipper je v dedikovanom kanáli (napr. `#leasing`) a napíše `/leasing`
2. Bot pošle **ephemerálnu** GDPR výzvu s tlačidlom *„Mám súhlas, pokračovať"*
3. Po kliku sa otvorí **modal** s 5 poľami:
   - Meno a priezvisko klienta
   - Telefón (SK/CZ validácia)
   - Email (validácia)
   - Auto — link na inzerát alebo voľný popis
   - Poznámka (voliteľné)
4. Po odoslaní bot pošle **Telegram správu Kristiánovi** s formátovaným zhrnutím
5. Flipper dostane ephemerálne `✅ Odoslané Kristiánovi`

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

### 3. `.env`

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
LOG_LEVEL=INFO
ENVIRONMENT=production
```

### 4. Preflight (voliteľné, odporúčané)

```powershell
.venv\Scripts\python -m scripts.preflight
```

Overí Discord token + Telegram credentials bez spustenia bota. Cieľ: `2/2 PASS`.

### 5. Spustenie

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
│   │   ├── telegram.py      ← Telegram Bot API klient
│   │   └── validators.py    ← phone/email
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

---

## Licencia & ownership

Postavené: **Synapse Studio** (Ján Stas) pre **drive.sk** (Peter Švikruha).
