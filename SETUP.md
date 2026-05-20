# Setup — synapse-drive-bot

> **Sequential runbook.** Prejdi sekcie **0 → 7** v poradí. Pri každom kroku je checkbox. Po dokončení máš bota bežiaceho lokálne a celý E2E happy-path prejdený.
>
> Pre **referenciu** (architektúra, troubleshooting, deploy) viď [`README.md`](README.md). Tento súbor je akčný checklist.

---

## 0. Prerekvizity

- [ ] **Python 3.11+** — over: `python --version`
- [ ] **Git** — over: `git --version`
- [ ] **pnpm** (len ak budeš púšťať aj web admin) — `pnpm --version`
- [ ] Účet na: [Discord](https://discord.com), [Supabase](https://supabase.com), [Meta for Developers](https://developers.facebook.com)
- [ ] Vlastné WhatsApp číslo (slúži ako Kristiánovo test číslo)

---

## 1. Discord — bot + test guild

### 1a. Vytvor Discord application
- [ ] https://discord.com/developers/applications → **New Application**
- [ ] Názov: `synapse-drive-test` → **Create**

### 1b. Pridaj bota
- [ ] V ľavom menu: **Bot** → **Reset Token** → skopíruj token bokom (toto je `DISCORD_TOKEN`)
- [ ] Scrolluj nižšie na **Privileged Gateway Intents**:
  - [ ] zapni **SERVER MEMBERS INTENT**
  - (`MESSAGE CONTENT INTENT` netreba — bot používa len slash commands)

### 1c. OAuth URL + pozvi do test guildu
- [ ] **OAuth2 → URL Generator**
  - Scopes: ✔ `bot`, ✔ `applications.commands`
  - Bot Permissions: ✔ `Send Messages`, ✔ `Embed Links`, ✔ `Use Slash Commands`, ✔ `Manage Messages`
- [ ] Otvor vygenerovaný URL v prehliadači → vyber svoj test server → **Authorize**

### 1d. Skopíruj IDs (zapni Developer Mode)
- [ ] V Discord-e: **User Settings → Advanced → Developer Mode = ON**
- [ ] Pravý klik na server → **Copy Server ID** = `DISCORD_GUILD_ID`
- [ ] Vytvor (alebo otvor) kanál `#test-leady` → pravý klik → **Copy Channel ID** = `DISCORD_LEADS_CHANNEL_ID`
- [ ] Pravý klik na seba (v member listе) → **Copy User ID** = `DISCORD_KRISTIAN_USER_ID` (počas testovania zastupuješ Kristiána)
- [ ] V **Server Settings → Roles** vytvor rolu napr. `admin` → pravý klik na rolu → **Copy Role ID** = `DISCORD_ADMIN_ROLE_ID`

**↳ Mám:** `DISCORD_TOKEN`, `DISCORD_GUILD_ID`, `DISCORD_LEADS_CHANNEL_ID`, `DISCORD_KRISTIAN_USER_ID`, `DISCORD_ADMIN_ROLE_ID`

---

## 2. Supabase — DB + Auth

### 2a. Vytvor projekt
- [ ] https://supabase.com/dashboard → **New project**
- [ ] Name: `synapse-drive-test`, region: **EU (Frankfurt)**, plan: Free
- [ ] Počkaj ~2 min kým sa zinicializuje

### 2b. Skopíruj credentials
- [ ] **Project Settings → API**
  - **Project URL** = `SUPABASE_URL`
  - **service_role** secret (NIE `anon`! — `anon` má RLS, service_role obíde) = `SUPABASE_SERVICE_KEY`

### 2c. Spusti SQL súbory v poradí
V **SQL Editor → New query**, postupne (každý ako separátny query, spusti **Run**):

- [ ] `supabase/schema.sql` (base — tabuľky, indexy, triggery, RLS)
- [ ] `supabase/migrations/001_dedup_indexes.sql` (indexy phone+email)
- [ ] `supabase/migrations/002_admin_read_access.sql` (RLS pre web admin)
- [ ] `supabase/migrations/003_commission.sql` (provízne stĺpce)

Over: spusti
```sql
SELECT count(*) FROM leads;
```
musí vrátiť `0` bez chyby.

### 2d. Auth URL config (kvôli web admin-u)
Ak budeš púšťať aj `synapse-drive-admin`:
- [ ] **Authentication → URL Configuration**
  - **Site URL**: `http://localhost:3000`
  - **Redirect URLs**: pridaj `http://localhost:3000/auth/callback`
  - (neskôr pri Vercel deploy-i pridáš aj produkčný URL)

**↳ Mám:** `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`

---

## 3. WhatsApp Cloud API (test mode)

### 3a. Meta app
- [ ] https://developers.facebook.com → **My Apps → Create App → Business**
- [ ] Display name: `synapse-drive-test`
- [ ] App contact email: tvoj email → **Create app**

### 3b. WhatsApp product
- [ ] V dashboarde appky: **Add product → WhatsApp → Set up**
- [ ] V ľavom menu: **WhatsApp → API Setup**

### 3c. Skopíruj credentials
- [ ] **Temporary access token** (platí 24h — pre prvý test stačí, pre produkciu vygeneruj System User token) = `WHATSAPP_ACCESS_TOKEN`
- [ ] **Phone number ID** (Meta dodá test číslo zadarmo) = `WHATSAPP_PHONE_NUMBER_ID`

### 3d. Recipient + template
- [ ] V sekcii **To** → **Manage phone number list** → **Add phone number** → tvoje WhatsApp číslo (zastupuje Kristiána, max 5 v test móde) = `WHATSAPP_RECIPIENT_NUMBER` (v medzinárodnom formáte bez `+`, napr. `421905123456`)
- [ ] Skontroluj vo WhatsApp na svojom telefóne — Meta pošle 6-miestny verifikačný kód, zadaj ho
- [ ] **Template name:** kým Petrov `new_lead` template nie je aproved, použi default `hello_world` (Meta ho má pre-aproved na všetkých test appkách):
  - `WHATSAPP_TEMPLATE_NAME=hello_world`
  - `WHATSAPP_TEMPLATE_LANG=en_US` (default `hello_world` je len en_US; po aprooval-e `new_lead` zmeň späť na `sk`)

**Pozn.:** kód v `src/services/whatsapp.py` posiela template message s parametrami pre `new_lead`. S `hello_world` (ktorý nemá parametre) pôjde správa, ale s warningom v logoch — to je OK pre smoke test, **nie pre produkciu**.

**↳ Mám:** `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_RECIPIENT_NUMBER`, `WHATSAPP_TEMPLATE_NAME`, `WHATSAPP_TEMPLATE_LANG`

---

## 4. Lokálne prostredie + `.env`

### 4a. Virtual env + dependencies
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 4b. `.env` súbor
- [ ] `Copy-Item .env.example .env`
- [ ] Otvor `.env` v editore a vyplň hodnoty zo sekcií 1-3
- [ ] Voliteľné: `COMMISSION_DEFAULT_RATE=0.03`, `COMMISSION_FALLBACK_AMOUNT=0` (default 3 % z `car_price`)

### 4c. Validácia configu
```powershell
.venv\Scripts\python -c "from src.config import get_settings; get_settings(); print('OK')"
```
Musí vypísať `OK`. Ak `ValidationError`, prečítaj chybové hlásenie a doplň chýbajúce vars.

---

## 5. Smoke test + E2E checklist

### 5a. Unit testy
```powershell
.venv\Scripts\python -m pytest tests/ -v
```
Očakávané: **66 passed**.

### 5b. Spusti bota
```powershell
.venv\Scripts\python -m src.bot
```
V logoch sleduj:
- [ ] `bot.setup_hook.start` (do 5 s od štartu)
- [ ] `bot.commands_synced count=4` — slash commands sa zaregistrovali (4 commands: `/novy-zaujemca`, `/moje-leady`, `/lead-info`, `/generate-report`)
- [ ] `bot.ready` (do 30 s) — bot je online

Ak `bot.ready` neprišlo, viď [`README.md` → Troubleshooting](README.md#troubleshooting).

### 5c. Happy path (manuálne v Discorde)
- [ ] V `#test-leady` napíš `/novy-zaujemca` → otvorí sa **ephemerálna GDPR výzva**
- [ ] Klik na **Súhlasím** → otvorí sa **Lead modal** (5 polí)
- [ ] Vyplň testové dáta (telefón vo formáte `+421 905 111 222`, akýkoľvek email; do **Auto** dáj URL alebo popis, napr. `Audi A4 2019 nafta 12500€`) → **Submit**
- [ ] Lead embed sa **postne v `#test-leady`** so 4 status buttonmi (Kontaktovaný/Schválený/Zamietnutý/Predaný)
- [ ] Dostaneš **ephemerálne potvrdenie** s `Lead ID`
- [ ] V Supabase **Table Editor → leads** → vidíš nový riadok
- [ ] WhatsApp ping prišiel na tvoje číslo (`hello_world` template alebo `new_lead` ak je už aproved)

### 5d. Status zmena + audit
- [ ] Klik na **📞 Kontaktovaný** → embed sa updatne, status sa zmení na žltý
- [ ] V Supabase **Table Editor → lead_status_history** → pribudol riadok s `old_status=new, new_status=contacted`

### 5e. Persistent view test (kritické!)
- [ ] `Ctrl+C` v bot terminále → reštartuj: `.venv\Scripts\python -m src.bot`
- [ ] Po `bot.ready` klikni na ten istý button **na tej istej Discord správe** → musí stále fungovať
- [ ] Ak nie — viď `README.md → Troubleshooting → Persistent view`

### 5f. Provízia
- [ ] Klik na **💰 Predaný** → dostaneš **DM od bota** s textom:
  ```
  💰 Tvoj lead bol PREDANÝ — gratulujem!
  ...
  💸 Tvoja provízia: 375.00 € (3.0 % z ceny)
  ```
  (Pri `car_price=12500` × `0.03 = 375 €`. Ak ti parser nezachytil cenu, DM hlási `Provízia zatiaľ 0 €`.)
- [ ] V DB: `leads.commission_amount` = 375.00, `commission_rate` = 0.0300

### 5g. `/moje-leady`
- [ ] V Discorde: `/moje-leady` → ephemerálna správa so súhrnom (počty status-ov + total earned `💸 X €`)

✅ **Po tomto bode je TODO 1 (E2E test) PASS.**

---

## 6. Web admin (voliteľné, ďalší repo)

Ak chceš spustiť aj web admin (`synapse-drive-admin`):

1. `cd ..\synapse-drive-admin`
2. Postupuj podľa `synapse-drive-admin/README.md` sekcia **Setup (lokálne)**
3. Pripomienka:
   - `NEXT_PUBLIC_SUPABASE_URL` = rovnaký ako bot `SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` = **anon** key (NIE service_role!) z Supabase **Project Settings → API**
   - `ALLOWED_EMAILS` = tvoj email (čiarkami oddelené ak chceš pridať Kristiánov / Petrov)

---

## 7. Po-runtime + problémy

Pre známe problémy viď [`README.md → Troubleshooting`](README.md#troubleshooting), špecificky:

- **`discord.NotFound: 10062 Unknown Interaction`** — modal expiroval (15 min limit)
- **`Supabase: row violates row-level security policy`** — používaš anon key namiesto service_role
- **WhatsApp `131047: re-engagement message`** — 24h window expiroval, treba template message
- **Persistent view po reštarte nereaguje** — chyba v `bot.add_view()` registrácii

Ak narazíš na niečo iné: napíš na Discord / vlož `bot.log` výstup do issue.

---

## Mapping checklist — všetky env vars

Pre prehľad, takto vyzerá vyplnený `.env`:

```
# Discord (sekcia 1)
DISCORD_TOKEN=<bot token>
DISCORD_GUILD_ID=<test server ID>
DISCORD_LEADS_CHANNEL_ID=<#test-leady channel ID>
DISCORD_KRISTIAN_USER_ID=<tvoj Discord user ID>
DISCORD_ADMIN_ROLE_ID=<admin role ID>

# Supabase (sekcia 2)
SUPABASE_URL=https://<projekt>.supabase.co
SUPABASE_SERVICE_KEY=<service_role secret>

# WhatsApp (sekcia 3)
WHATSAPP_PHONE_NUMBER_ID=<Meta test phone ID>
WHATSAPP_ACCESS_TOKEN=<temp 24h token>
WHATSAPP_RECIPIENT_NUMBER=421905111222
WHATSAPP_TEMPLATE_NAME=hello_world
WHATSAPP_TEMPLATE_LANG=en_US

# Voliteľné — provízie (default 3 %)
COMMISSION_DEFAULT_RATE=0.03
COMMISSION_FALLBACK_AMOUNT=0
```
