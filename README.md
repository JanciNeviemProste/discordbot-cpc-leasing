# Synapse Drive Bot

**Discord bot pre drive.sk komunitu — flipper zadá lead, Kristián dostane WhatsApp + Discord notifikáciu s buttonmi na update statusu.**

Klient: **Peťo Švikruha (drive.sk)** · Stack: **Python 3.11 + discord.py 2.4 + Supabase + WhatsApp Cloud API**

> **Nový tu?** Začni s [`SETUP.md`](SETUP.md) — click-by-click runbook od prázdneho stroja po beziaceho bota.

---

## TL;DR

```bash
git clone <repo>
cd synapse-drive-bot
python -m venv .venv && source .venv/bin/activate   # alebo .venv\Scripts\activate na Win
pip install -r requirements.txt
cp .env.example .env                                  # vyplň hodnoty
# Spusti supabase/schema.sql v Supabase SQL Editor
python -m src.bot
```

V Discorde: `/novy-zaujemca` → potvrď GDPR → vyplň formulár → lead je v DB, v kanáli a Kristián má WhatsApp ping.

---

## Architektúra

```
┌──────────────┐    /novy-zaujemca    ┌─────────────────┐
│   Flipper    ├─────────────────────►│  Discord Bot    │
│  (Discord)   │  + GDPR + Modal      │  (Python)       │
└──────────────┘                      └────────┬────────┘
                                               │
                          ┌────────────────────┼────────────────────┐
                          │                    │                    │
                          ▼                    ▼                    ▼
                 ┌────────────────┐  ┌──────────────────┐  ┌──────────────────┐
                 │   Supabase     │  │ #leady-kristian  │  │ WhatsApp Cloud   │
                 │  (Postgres)    │  │   embed + buttony│  │  API (Meta)      │
                 └────────────────┘  └──────────────────┘  └──────────────────┘
                                               │                    │
                                               └────────┬───────────┘
                                                        ▼
                                                 ┌─────────────┐
                                                 │  Kristián   │
                                                 │  (Discord +│
                                                 │   WhatsApp) │
                                                 └─────────────┘
```

### Tok dát (happy path)

1. **Flipper** zadá `/novy-zaujemca` v ľubovoľnom kanáli
2. Bot pošle **ephemerálnu GDPR výzvu** s buttonom *„Mám súhlas, pokračovať"*
3. Po kliku sa otvorí **modal** s 5 poľami (meno, telefón, email, auto, poznámka)
4. **Validácia** (SK/CZ telefón, email) na klientovi cez modal
5. Ak je „auto" URL, bot **scrapne** značku/model/rok/cenu/km/VIN
6. **Insert** do Supabase (`leads` tabuľka) s flipper Discord ID
7. **Post embed** do `#leady-kristian` s 4 statusovými buttonmi (perzistentné)
8. **Update DB** s Discord message ID
9. **WhatsApp template notifikácia** Kristiánovi (`novy_lead` template)
10. **Confirm** flipperovi ephemerálnou správou

### Status workflow

`new` → `contacted` → `approved` → `sold` *(alebo `rejected` kedykoľvek)*

Klik na button v Discorde:
- Permission check (Kristián alebo admin role)
- Update DB (trigger automaticky loguje do `lead_status_history`)
- Edit embed (farba + label sa zmení)
- DM notifikácia flipperovi

---

## Setup krok za krokom

### 1. Discord bot

1. Choď na <https://discord.com/developers/applications>
2. **New Application** → názov *„Synapse Drive Bot"*
3. **Bot** v ľavom menu → **Reset Token** → ulož ako `DISCORD_TOKEN`
4. Zapni **MESSAGE CONTENT INTENT** (síce nepoužívame, ale niektoré veci ho chcú) a **SERVER MEMBERS INTENT** (role check)
5. **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Send Messages`, `Embed Links`, `Use Slash Commands`, `Read Message History`
6. Otvor vygenerovanú URL, pridaj bota na Discord server drive.sk
7. Skopíruj **Server ID** (developer mode → klik na server → Copy Server ID) ako `DISCORD_GUILD_ID`
8. Vytvor kanál `#leady-kristian` (privátny, len pre Kristiána + adminov), skopíruj ID → `DISCORD_LEADS_CHANNEL_ID`
9. Kristiánovo user ID → `DISCORD_KRISTIAN_USER_ID`
10. Vytvor rolu `Admin` (alebo použi existujúcu), ID → `DISCORD_ADMIN_ROLE_ID`

### 2. Supabase

1. <https://supabase.com/dashboard> → **New project** *„synapse-drive-bot"*
2. Free tier postačí pre prvý rok (8GB DB, 50k MAU)
3. **Project Settings → API**:
   - `Project URL` → `SUPABASE_URL`
   - `service_role` key (NIE anon!) → `SUPABASE_SERVICE_KEY`
4. **SQL Editor → New query** → paste obsah `supabase/schema.sql` → **Run**
5. Over: `SELECT * FROM leads LIMIT 1;` (prázdny result = OK)

### 3. WhatsApp Cloud API (najdôležitejšie — bez tohto WA notifikácie nefungujú)

#### 3a. Meta Business setup

1. <https://business.facebook.com/> → vytvor **Business Manager** pre drive.sk (ak ešte nemá)
2. <https://developers.facebook.com/> → **My Apps → Create App** → typ **Business**
3. V appke: **Add Product → WhatsApp → Set up**
4. WhatsApp dá **test phone number** (zadarmo, dočasné). Pre produkciu pridaj reálne číslo:
   - **WhatsApp Manager → Phone Numbers → Add Phone Number**
   - Vyhradené číslo (môže byť firemné, NESMIE byť aktívne v normálnej WhatsApp aplikácii — treba ho najprv odhlásiť/zmazať z WA)
   - Verifikácia cez SMS/voice

#### 3b. Získanie credentials

V Meta App → **WhatsApp → API Setup**:
- `Phone number ID` → `WHATSAPP_PHONE_NUMBER_ID`
- **Access Token**: temporary token funguje 24h. Pre produkciu vygeneruj **System User Token**:
  1. <https://business.facebook.com/settings/system-users>
  2. **Add** → názov *„drive-bot"* → role *Admin*
  3. **Generate New Token** → vyber svoju App, scope `whatsapp_business_messaging` + `whatsapp_business_management`
  4. Token NIKDY neexpiruje → `WHATSAPP_ACCESS_TOKEN`

#### 3c. Vytvor template (KRITICKÉ)

WhatsApp Cloud API **nepovoľuje** posielať ľubovoľné správy z bota klientovi. Prvá správa musí byť **schválený template**.

1. **WhatsApp Manager → Message Templates → Create Template**
2. **Category**: `Utility` (transakčné, schvaľujú rýchlo)
3. **Name**: `novy_lead`
4. **Language**: Slovak
5. **Body**:

```
🚗 *Nový lead — drive.sk*

Klient: {{1}}
Telefón: {{2}}
Auto: {{3}}
Flipper: {{4}}

Otvor v Discorde: {{5}}
```

6. **Samples** (Meta to chce na review):
   - {{1}}: `Ján N.`
   - {{2}}: `+421905123456`
   - {{3}}: `Audi A4 2019 nafta`
   - {{4}}: `Tomáš H.`
   - {{5}}: `https://discord.com/channels/123/456/789`

7. **Submit** → Meta zvyčajne schváli do 1-24h. Status uvidíš v WhatsApp Manager.

#### 3d. Kristiánovo číslo

`WHATSAPP_RECIPIENT_NUMBER=421905XXXXXX` (BEZ `+`, BEZ medzier)

> **Dôležité:** Kristián musí mať aktívny WhatsApp na tom čísle. Pri prvej správe ho WA požiada o súhlas s prijímaním business správ (jednorazovo).

### 4. Konfigurácia

```bash
cp .env.example .env
# vyplň všetkých 11 premenných
```

Skontroluj že máš všetko správne:

```bash
python -c "from src.config import get_settings; s = get_settings(); print('OK', s.discord_guild_id, s.whatsapp_api_url)"
```

---

## Spustenie

### Lokálne (development)

```bash
python -m src.bot
```

Mal by si vidieť:

```
{"event": "bot.commands_synced", "count": 3, ...}
{"event": "bot.ready", "username": "Synapse Drive Bot", ...}
```

V Discorde napíš `/novy-zaujemca` — bot by mal odpovedať.

### Cybrancee (production)

drive.sk bot beží na rovnakom hostingu ako CPC bot (~$1.87/mes Python plan).

1. Cybrancee panel → **Create Server → Python**
2. **Upload files** alebo cez Git: push repo, pull v paneli
3. **Environment variables**: vlož všetky z `.env`
4. **Startup command**: `python -m src.bot`
5. **Restart on file change**: OFF (manual restart deploy flow)
6. **Auto-restart**: ON (recovery z crashov)

---

## Discord commands

| Command | Kto | Popis |
|---|---|---|
| `/novy-zaujemca` | Hociktorý flipper | Otvorí GDPR výzvu → modal → uloží lead |
| `/moje-leady` | Hociktorý flipper | Posledných 20 vlastných leadov + štatistika |
| `/lead-info <id>` | Kristián / admin | Detail leadu s **plnými** údajmi (NIE maskovanými) |

---

## Bezpečnosť & GDPR

- **Plné údaje len v Supabase**, šifrované at-rest (Postgres default)
- **Discord embed = vždy maskované** (`+421 9** *** 456`, `j***@gmail.com`)
- Plné údaje vidí Kristián cez:
  1. WhatsApp template (telefón un-masked — potrebuje volať)
  2. `/lead-info <uuid>` ephemerálne v Discorde
  3. (Budúci) web admin s Supabase auth
- **GDPR consent** explicitne kliknutý + timestamped pred otvorením formulára
- Flipperov Discord ID slúži ako atribúcia (pre províziu) + audit
- Status zmeny logované v `lead_status_history` (audit log)

---

## Troubleshooting

| Problém | Riešenie |
|---|---|
| Bot sa pripojí ale slash commands sa nezobrazia | Sync je per-guild, môže trvať 1-2 min. Reštart bota = re-sync |
| `WhatsApp error 131030: phone number not allowed` | Recipient nemá WhatsApp alebo nesúhlasil s prijímaním |
| `WhatsApp error 132001: template name does not exist` | Template ešte nie je schválený, alebo nesprávny `WHATSAPP_TEMPLATE_NAME` |
| `WhatsApp error 100: invalid parameter` | Template parameter má newline/tab/`>4 spaces` — `_sanitize()` to rieši |
| Car parser vráti prázdne | Stránka má anti-bot ochranu (Cloudflare). Niektoré weby treba neskôr riešiť cez Playwright |
| Buttons nefungujú po reštarte | `LeadStatusView()` musí byť zaregistrovaný cez `bot.add_view()` v `setup_hook` — je |
| Supabase 401 Unauthorized | Použil si `anon` key namiesto `service_role` |

---

## Roadmap (post-MVP)

1. **Web admin** — Next.js stránka s Supabase auth, tabuľka všetkých leadov, filter, export CSV (~1 deň práce)
2. **Provízny tracker** — na `status=sold` automaticky vypočítaj podiel pre flippera podľa rules tabuľky
3. **Mesačné PDF reporty** — cron job, pošle každému flipperovi jeho stats + provízie
4. **Telegram backup notification** — ak WA zlyhá, pošle Telegram (Janči má bota na to)
5. **Playwright car parser** — pre stránky s anti-bot (alza, bazos.sk)
6. **Lead deduplication** — alert ak rovnaké tel/email už v DB
7. **Auto-tagging cez AI** — Claude API klasifikuje (rozpočet klienta, urgentnosť, kvalita leadu)

---

## Súborová štruktúra

```
synapse-drive-bot/
├── README.md                  ← si tu
├── PROMPT.md                  ← inštrukcie pre Claude Code
├── requirements.txt
├── .env.example
├── .gitignore
├── supabase/
│   └── schema.sql             ← jednorazový SQL setup
├── src/
│   ├── bot.py                 ← entry point (python -m src.bot)
│   ├── config.py              ← Pydantic settings z .env
│   ├── database.py            ← Supabase wrapper
│   ├── cogs/
│   │   └── leads.py           ← slash commands + main pipeline
│   ├── modals/
│   │   └── lead_modal.py      ← formulár (5 polí)
│   ├── views/
│   │   ├── gdpr_view.py       ← GDPR consent button
│   │   └── lead_view.py       ← status buttony (persistent)
│   ├── services/
│   │   ├── whatsapp.py        ← Meta Cloud API klient
│   │   ├── car_parser.py      ← URL scraper (5 SK/CZ/DE stránok)
│   │   └── validators.py      ← phone/email/VIN regex
│   └── utils/
│       ├── embeds.py          ← embed buildery
│       ├── gdpr.py            ← maskovanie údajov
│       └── logger.py          ← structlog setup
└── tests/
    └── test_basic.py          ← pytest pre validátori + masking
```

---

## Licencia & ownership

Postavené: **Synapse Studio** (Ján Stas) pre **drive.sk** (Peter Švikruha).
Maintenance retainer: viď zmluvu.

Otázky? Discord `@Synapse` alebo email.
