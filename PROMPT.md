# PROMPT.md — Inštrukcie pre Claude Code

> Tento dokument je hand-off pre Claude Code agenta, ktorý bude pokračovať v tomto projekte. Prečítaj celý pred prvou akciou.

---

## 1. Kontext projektu

**Synapse Drive Bot** je Discord bot pre slovenského klienta **Peter Švikruha (drive.sk)** — firma flipuje autá zo zahraničia a má komunitu flipperov. Bot rieši leadový workflow medzi flippermi a finančným poradcom Kristiánom Valovičom (leasingy + poistky).

**Use case v jednej vete:** *flipper zadá v Discorde údaje klienta a auta → bot uloží do Supabase, postne embed s buttonmi do privátneho kanála a pošle Kristiánovi WhatsApp ping.*

Sesterský projekt: **synapse-cpc-bot-v2** (CarProfitClub Discord bot) — rovnaký klient, iný use case (parsing dealer emailov). Štýl kódu a deployment majú byť konzistentné.

---

## 2. Stav projektu (current state)

### ✅ Hotové (skeleton + core logika)

- Project structure (modulárna, `src/cogs`, `src/views`, `src/services`, `src/utils`)
- Pydantic-based config (`src/config.py`) — všetky env vars validované na štarte
- Structured logging cez `structlog` (`src/utils/logger.py`)
- Supabase schéma (`supabase/schema.sql`) + migrations (`supabase/migrations/00{1,2,3}_*.sql`)
- Supabase wrapper (`src/database.py`)
- WhatsApp Cloud API klient (`src/services/whatsapp.py`) — template aj free-form
- Car URL parser (`src/services/car_parser.py`) — JSON-LD generic + site-specific pre 6 stránok
- Validators (phone SK/CZ, email, VIN) + GDPR masking
- Embed buildery (masked / unmasked variants)
- GDPR consent view + Lead modal + persistent status buttons
- Hlavný cog so slash commands (`/novy-zaujemca`, `/moje-leady`, `/lead-info`)
- Bot entry point s graceful shutdown
- 66 unit testov (validátori, masking, parser, dedup, monthly stats, commission)

### ✅ Hotové (feature TODO 3-7)

- **TODO 3 — Car parser hardening** ✅
  Retry s rotáciou User-Agent (Chrome/Firefox/Safari) pri 403/429/503, Cloudflare detekcia (cf-mitigated header + "Just a moment" body), 404/410 sa neretry-uje. `LeadCarData.parse_warning` UI-only pole sa propaguje cez modal → pipeline → ephemerálna potvrdenka flipperovi (`⚠️ Auto parsing: ...`). `tests/test_car_parser.py` (10 testov).

- **TODO 4 — Web admin** ✅
  Samostatný sibling repo `../synapse-drive-admin/` (Next.js 15 + TypeScript + Tailwind + `@supabase/ssr`). Magic-link auth cez Supabase + email allowlist (`ALLOWED_EMAILS` env). Stránka `/` = leady tabuľka s filtrami (status, flipper, date range) a pagináciou 25/page. `pnpm typecheck` + `pnpm build` ✅. RLS policy v `supabase/migrations/002_admin_read_access.sql`.

- **TODO 5 — Provízny modul** ✅ *(placeholder pravidlo)*
  3 nové stĺpce na `leads` (`commission_amount`, `commission_rate`, `commission_calculated_at`). `src/services/commission.py:compute_commission()` = jediný entry-point na prepísanie pravidiel keď Peter dodá reálne. Aktuálne placeholder: % z `car_price` (default 3 %, `COMMISSION_DEFAULT_RATE` env). Volá sa v `lead_view._handle_status_change` pri sold; flipper dostane DM so sumou; `/moje-leady` ukáže total; mesačný PDF report má riadok "Provízia za mesiac". `tests/test_commission.py` (9 testov).

- **TODO 6 — Dedup alert** ✅
  `Database.find_duplicate_leads(phone, email)` cez `.or_()` Postgrest query, indexy na phone+email v `supabase/migrations/001_dedup_indexes.sql`. Soft warning (nikdy neblokuje insert) na 2 miestach: extra embed field `⚠️ Možný duplikát` v `#leady-kristian` + flipperova ephemerálna potvrdenka. `build_dedup_warning()` zobrazí top 3 zhody (skrátený lead_id, status emoji, flipper, vek v dňoch) bez PII. `tests/test_dedup.py` (7 testov vrátane no-PII guarantee).

- **TODO 7 — Mesačné PDF reporty** ✅
  ReportLab A4 PDF cez `src/services/pdf_report.py`; `src/services/report_stats.py` pure funkcie (period range, status breakdown, total commission). `ReportsCog` s `@tasks.loop(hours=24)` — fires na 1. v mesiaci pre všetkých aktívnych flipperov za predchádzajúci mesiac (DM s PDF prilohou). Slash command `/generate-report [target]` pre adminov (manuálny re-send / single flipper). `tests/test_report_stats.py` (12 testov + PDF smoke).

### ⚠️ TODO (zostávajúce)

1. **Manuálne otestovať full flow** na test Discord serveri (Janči pripraví test guild). Plán fáz 0→3 viď `~/.claude/plans/re-taj-prompt-md-*.md` (Fáza 0 lokálne prostredie už hotová: 66 testov ✅, importy ✅). Zostávajú Fázy 1-3: setup Discord/Supabase/WhatsApp credentials → spustenie bota → E2E checklist.
2. **WhatsApp template aprooval** — Meta to musí schváliť, deploy nemôže produkčne fungovať bez schválenia (viď README sekcia 3c). Manuálna úloha pre Janči-ho, žiadny kód.

---

## 3. Konvencie ktoré DODRŽIAVAJ

### Štýl

- **Slovak** v UI (modal labels, embed text, buttony, ephemerálne správy, logy USER-facing)
- **English** v kóde (variable names, comments, docstrings, log event keys)
- Type hints **všade** (`from __future__ import annotations` na vrchu súborov)
- `ruff` formátovanie (default config); line length 100
- Docstring na každom verejnom module a funkcii so side-effectom
- Loguj cez `structlog` s **structured fields**, nie f-stringy: `log.info("event.name", key=val)` NIE `log.info(f"...")`

### Štruktúra

- **Cogs** = slash commands a high-level pipeline
- **Modals** = Discord modal triedy (formuláre)
- **Views** = Discord ui.View triedy (buttony, select menus)
- **Services** = externé API klienti (WhatsApp, scraper, future Stripe atď.) — žiadny Discord-špecifický kód tu
- **Utils** = pure-function helpery (maskovanie, embed buildery, logger)
- **database.py** = jediný miesto kde voláš Supabase priamo

### Async

- discord.py je async-first
- `supabase-py` je **synchronný** — to je OK, operácie sú rýchle. Pri väčšom scale prepíš na `asyncpg`
- HTTP volania (`httpx.AsyncClient`) **vždy** async

### Error handling

- Nikdy nesilent-catchuj `except Exception: pass`. Vždy logni.
- User-facing chyby = ephemerálna správa s konkrétnym hlásením (nie len „chyba")
- DB chyby = log + ephemerálna správa + ak lead je už v DB, oznám lead ID
- WhatsApp chyby = nezablokuj submission, lead je už v DB; len ulož chybu do `whatsapp_error` poľa a inform-ni flippera

### Bezpečnosť

- **Service role key** sa nikdy nedostane ku klientovi (front-end / public artefakt). Bot beží server-side, OK.
- **Plné osobné údaje (telefón, email)** NIKDY do verejných kanálov. Embed default `masked=True`.
- Logy NESMÚ obsahovať plný telefón ani email — pri logovaní vždy mask alebo len lead_id.

---

## 4. Príklad pridania novej funkcie (referenčný workflow)

**Task:** Pridať príkaz `/lead-edit <id>` ktorý umožní Kristiánovi opraviť údaje leadu (preklep v emaili napr.).

### Postup

1. **Otvor `src/cogs/leads.py`** — pridaj nový `@app_commands.command` do `LeadsCog`
2. **Permission check** — len Kristián alebo admin (vzor: viď `lead_info`)
3. **Modal** — vytvor nový modal v `src/modals/lead_edit_modal.py` (separátny súbor, čistejšie)
4. **DB metóda** — pridaj `update_lead_fields()` do `src/database.py`
5. **Audit log** — manuálne pridaj záznam do `lead_status_history` s `note="Edited fields: ..."`
6. **Test** — pridaj test do `tests/`
7. **README** — update tabuľky commands

### Anti-patterny ktoré NEROB

- Nepridávaj logiku do `bot.py`. To je len entry point.
- Nepridávaj DB volania priamo do views/modalov. Vždy cez `Database()` z `database.py`.
- Nepoužívaj global state (premenné na module-level). Inject cez bot context alebo init.
- Nehard-coduj IDs, channely, role. Všetko cez `get_settings()`.

---

## 5. Testovanie

### Lokálne pred commit

```bash
pip install -r requirements.txt
pytest tests/ -v
python -c "from src.config import get_settings; get_settings()"   # validuje .env
python -m src.bot   # ak máš test guild a test .env
```

### Test guild setup

Janči má test Discord server `synapse-test`. Použi tam:
- `DISCORD_GUILD_ID` = test guild ID
- `DISCORD_LEADS_CHANNEL_ID` = `#test-leady`
- `DISCORD_KRISTIAN_USER_ID` = Jančiho user ID (zastupuje Kristiána)

WhatsApp test: Meta dáva default test phone number ktorý môžeš použiť bez schvaľovania templatu (5 cieľových čísel max).

---

## 6. Deployment

**Cybrancee Python plan ~$1.87/mes.** Konkrétne kroky v README.md sekcia *„Spustenie → Cybrancee (production)"*.

### Pre deploy:

1. `git push` → repo
2. Cybrancee panel → **Pull from Git** alebo upload zip
3. Env vars → **Environment Variables** v paneli (NIE commitnutý `.env` súbor)
4. Restart server
5. Skontroluj logy: `bot.ready` event sa musí objaviť do 30s

### Po deploy verifikácia:

```
✅ Bot je online v Discorde
✅ /novy-zaujemca otvorí GDPR výzvu
✅ Modal submit uloží do Supabase (skontroluj `SELECT count(*) FROM leads`)
✅ Embed sa zobrazí v #leady-kristian s 4 buttonmi
✅ WhatsApp ping prišiel Kristiánovi
✅ Klik na button zmení status v DB a embed sa updatne
✅ Reštart bota → buttony stále fungujú (persistent view)
```

---

## 7. Spoluprác Janči ↔ Claude Code

### Janči (človek) zabezpečí:

- Meta Business setup + WhatsApp template approval
- Discord bot creation + permissions
- Supabase projekt + schema run
- Cybrancee deploy + env vars
- Cred sharing cez 1Password / Bitwarden (nikdy do gitu)

### Claude Code (ty) urobí:

- Implementuj TODO funkcie z bodu 2 (po Janči-ho schválení priority)
- Pri každej zmene aktualizuj README ak sa mení správanie
- Pri pridaní novej tabuľky/stĺpca vytvor SQL migráciu v `supabase/migrations/NNN_*.sql`
- Pri pridaní novej env var aktualizuj `.env.example` AJ `src/config.py`

### Komunikácia

- Janči robí code review v PR. Pýtaj sa **predtým** ako začneš robiť veľkú featúru (>200 LOC).
- Krátke správy v Slovak. Technické komentáre v kóde English.
- Žiadny vendor lock-in bez schválenia (napr. nezavádzaj Redis ak nie je nutný — má svoju vlastnú zložitosť).

---

## 8. Časté problémy a riešenia

### „discord.NotFound: 10062 Unknown Interaction"

Modal/interaction tokeny expirujú za 15 min. Ak parsing trvá dlho, **defer** interakciu hneď na začiatku (`await interaction.response.defer(thinking=True)`).

### Car parser dostáva 403/Cloudflare

Pridaj retry s rôznym User-Agentom, alebo prejdi na Playwright pre konkrétnu doménu. Nedeleguj na všetky weby — len tie najdôležitejšie (autobazar.eu, mobile.de).

### Supabase RLS blokuje insert

Service role bypasses RLS. Ak používaš anon key (chyba!), insert zlyhá. Skontroluj `SUPABASE_SERVICE_KEY` v `.env`.

### WhatsApp `131047: re-engagement message`

24h service window vypršal. Ak chceš poslať free-form správu, najprv pošli template, počkaj kým Kristián odpíše, potom môžeš ľubovoľnú správu po dobu 24h.

### Persistent view po reštarte nereaguje

`bot.add_view(LeadStatusView())` musí byť volaný v `setup_hook` **pred** `bot.start()`. View musí mať `timeout=None` a custom_id každého buttonu.

---

## 9. Zoznam súborov + ich účel (rýchla referencia)

| Súbor | Účel | Treba upraviť pri |
|---|---|---|
| `src/bot.py` | Entry point, bot init, persistent view registration | Nový cog / nová persistent view |
| `src/config.py` | Pydantic settings z `.env` | Nová env var |
| `src/database.py` | Všetky Supabase volania | Nová tabuľka / query |
| `src/cogs/leads.py` | Slash commands + main pipeline | Nový command / zmena business logiky |
| `src/modals/lead_modal.py` | Lead submission formulár | Pridanie/zmena polí (max 5!) |
| `src/views/gdpr_view.py` | GDPR consent button | Zmena GDPR znenia |
| `src/views/lead_view.py` | Status buttony (persistent) | Pridanie nového statusu |
| `src/services/whatsapp.py` | Meta Cloud API klient | Iný template / nové typ správy |
| `src/services/car_parser.py` | URL scraping | Nová doména / fix selectorov |
| `src/services/validators.py` | Phone/email/VIN regex | Nový typ vstupu |
| `src/utils/embeds.py` | Discord embed buildery | Nový dizajn karty / status |
| `src/utils/gdpr.py` | Maskovanie | Nový typ údaja na masking |
| `src/utils/logger.py` | Structlog config | Zmena log formatu |
| `supabase/schema.sql` | DB setup (jednorazový) | Nová tabuľka — VYTVOR MIGRÁCIU namiesto úpravy! |

---

## 10. Quick health-check pre Claude Code

Pred prvým commitom over že:

```bash
[ ] python -c "from src.bot import SynapseDriveBot"     # importy fungujú
[ ] python -c "from src.config import get_settings; get_settings()"   # config validný
[ ] pytest tests/ -v                                     # testy passujú
[ ] ruff check src/                                      # lint clean (ak používaš ruff)
[ ] grep -r "TODO" src/                                  # žiadne forgotten TODOs
[ ] grep -r "print(" src/                                # nepoužívaš print, len log
```

---

**Good luck. Pri otázkach ping Janči-ho na Discorde alebo cez Claude Code.**
