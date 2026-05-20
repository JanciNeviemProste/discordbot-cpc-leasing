# Synapse Drive Bot

**Discord bot pre drive.sk — flipper napíše `/leasing`, vyplní formulár, údaje klienta sa pošlú na WhatsApp finančnému poradcovi Kristiánovi.**

Klient: **Peťo Švikruha (drive.sk)** · Stack: **Python 3.11 + discord.py 2.4 + WhatsApp Cloud API**

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
python -m scripts.preflight       # voliteľné: over Discord + WhatsApp creds
python -m src.bot
```

V Discorde: `/leasing` → potvrď GDPR → vyplň formulár → Kristián má WhatsApp.

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
4. Po odoslaní bot pošle **WhatsApp Kristiánovi** cez schválený template `novy_lead`
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

### 2. WhatsApp Cloud API

1. <https://business.facebook.com/> → Business Manager pre drive.sk
2. <https://developers.facebook.com/> → **Create App** typ **Business** → **Add Product → WhatsApp**
3. **WhatsApp → API Setup**:
   - `Phone number ID` → `WHATSAPP_PHONE_NUMBER_ID`
   - Pre produkciu vygeneruj **System User Token** (nikdy neexpiruje) cez <https://business.facebook.com/settings/system-users>, scope `whatsapp_business_messaging` + `whatsapp_business_management` → `WHATSAPP_ACCESS_TOKEN`
4. Kristiánovo číslo (bez `+`, bez medzier) → `WHATSAPP_RECIPIENT_NUMBER`

#### Template `novy_lead` (KRITICKÉ — pred prvým spustením)

WhatsApp nepovolí poslať custom text bez 24h conversation window. Prvá správa **musí ísť cez schválený template**.

V **WhatsApp Manager → Message Templates → Create Template**:

- **Name**: `novy_lead`
- **Category**: `Utility`
- **Language**: Slovak
- **Body**:
  ```
  🚗 *Nová žiadosť o leasing — drive.sk*

  Klient: {{1}}
  Telefón: {{2}}
  Auto: {{3}}
  Flipper: {{4}}
  Poznámka: {{5}}
  ```
- **Samples** (Meta to chce na review):
  - {{1}}: `Ján Novák`
  - {{2}}: `+421905123456`
  - {{3}}: `Audi A4 2019 nafta 150k km 12500€`
  - {{4}}: `Tomáš H.`
  - {{5}}: `volať po 17:00`

Submit → Meta zvyčajne schváli do 1–24 h.

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
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_RECIPIENT_NUMBER=         # Kristiánovo WA číslo bez +
WHATSAPP_TEMPLATE_NAME=novy_lead
WHATSAPP_TEMPLATE_LANG=sk
WHATSAPP_API_VERSION=v21.0
LOG_LEVEL=INFO
ENVIRONMENT=production
```

### 4. Preflight (voliteľné, odporúčané)

```powershell
.venv\Scripts\python -m scripts.preflight
```

Overí Discord token + WhatsApp credentials bez spustenia bota. Cieľ: `2/2 PASS`.

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
├── SIMPLIFY-PROMPT.md       ← špec tejto verzie
├── requirements.txt
├── .env.example
├── src/
│   ├── bot.py               ← entry point
│   ├── config.py            ← Pydantic settings
│   ├── cogs/leads.py        ← /leasing + submit pipeline
│   ├── modals/lead_modal.py ← 5-field form
│   ├── views/gdpr_view.py   ← GDPR consent button
│   ├── services/
│   │   ├── whatsapp.py      ← Meta Cloud API klient
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
| `WhatsApp error 131030` | Recipient nemá WhatsApp alebo nesúhlasil s business správami |
| `WhatsApp error 132001` | Template ešte nie je schválený alebo nesprávny `WHATSAPP_TEMPLATE_NAME` |
| `WhatsApp error 100: invalid parameter` | Template parameter má newline/tab — `_sanitize()` to rieši, over že prejde |
| Access token 401 po 24h | Použil si temporary token, vygeneruj System User Token (permanent) |

---

## Licencia & ownership

Postavené: **Synapse Studio** (Ján Stas) pre **drive.sk** (Peter Švikruha).
