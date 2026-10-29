# Overdracht WPL — deel 2 (bijgewerkt 6 okt 2026)

> Voor **Claude** (mentor), **Cline** (uitvoerder via de DeepSeek-API) en **GitHub Copilot Chat** (beperkt).
> Lokale, **niet-gecommitte** werkkopie. Alles wat als HYPOTHESE staat is niet bewezen; BEWIJS = door de gebruiker of de code bevestigd.
> Alleen namen/hashes/statussen — geen geheimen.

## 1. Rollen en werkafspraken
- **Gebruiker:** software developer in opleiding, basiskennis, bouwt een eigen AI Agency. Nederlands, Windows, VS Code, **Git Bash** als standaardterminal.
- **Claude = mentor** in code, architectuur en prompts. Legt uit waarom, benoemt afwegingen, is eerlijk over onduidelijk/onveilig/waarschijnlijk fout, controleert claims van tools, scheidt HYPOTHESE van BEWIJS, verzint geen commando's/instellingen/menunamen (verwijst naar documentatie), stelt max. één vraag per keer, antwoordt in het Nederlands, erkent eigen fouten direct.
- **Cline = uitvoerder** (auto-approve UIT); **alles wat Cline leest gaat naar DeepSeek.** **Copilot** alleen met een goede reden.
- **Promptopbouw (één prompt per stap):** Context → Taak (commando's in codeblok, **per commando de shell**: Git Bash of PowerShell) → Rapporteer alleen → Beperkingen. Sluit af met "Wat je mij meldt"; hangt een stap af van een eerdere uitkomst, zeg dat en geef een invulplek.
- **Harde regels:** prompts standaard alleen-lezen; wijzigen/committen/pushen/verwijderen of een echte DB-verbinding alleen met expliciet akkoord en een precieze reikwijdte. Nooit force-push, historie herschrijven, `git branch -D`, of Alembic-/Neon-acties zonder expliciete opdracht. Geheimen (keys, wachtwoorden, connection strings, tokens, inhoud van `.env`/`.flaskenv`/`mcp.json`) nooit tonen, kopiëren of laten uitlezen — alleen aantallen, bestandsnamen, variabelenamen, ja/nee of fouttypes. Geheimenscans tonen alleen een teller. Nieuwe wachtwoorden/keys: handmatig, buiten tools. Commit-/pushprompts: eerst controles, dan akkoord, dan uitvoeren.
- **Alle alleen-lezen git-commando's draait de gebruiker zelf in Git Bash.**

## 2. Project
- Repo `C:\Codes\WPL`, privé op GitHub.
- Stack: Flask (Application Factory + Blueprints), SQLAlchemy Core 2.0, Pydantic v2, Alembic. AI: Anthropic Claude Haiku 4.5 met retry. Hosting: Render (gunicorn, 2 workers) + Neon Postgres; SQLite lokaal.
- n8n roept `POST /api/v1/ai-reservering` aan met header `X-API-Key`.
- Beheercommando's: `flask create-admin`, `flask purge-retention` én `flask resend-mail <reservering_id>` — alle drie **met** `--productie`-guard; plus `flask init-db` (lokaal hulpmiddel).

## 3. Wat is af
- Sleutelrotatie Anthropic en Neon; git-historie gecontroleerd; Alembic-baseline op Neon.
- `main` beschermd (PR verplicht, `CI / unit-tests`, geen force-push).
- Health-logging met tests; README bijgewerkt (create-admin, purge-retention).
- PR #1 gemerged; PR #2 was een lege merge.
- Render-service draait, `/health` geeft 200, `verify-render` groen, `RENDER_API_KEY` vervangen en de oude ingetrokken.
- Auth op webhook- en web-routes geaudit (fail-closed, rate limits).
- **A3 besloten:** Alembic in het build-command, `init-db` erbuiten.
- Variabelen-inventaris code vs. Render gedaan (§4, bijlage C); create-admin en mailgedrag uitgezocht in de code (§4).

**De harde streep staat.** Alles buiten sectie 5 hoort bij het volgende project.
**Bewust niet nu:** IP-scrubbing, retentie-automatisering, Swagger/APIFlask, Celery+Redis, smallere Neon-key, README-gat voor optionele variabelen.

## 4. Bevindingen (BEWIJS uit code of gebruiker, tenzij anders vermeld)

### Variabelen (23 `.py`-bestanden via `git ls-files`, 26 namen)
- **BEWIJS (bevestigd door de gebruiker, 6 okt):** in Render staan `ALLOW_PROD_MIGRATE`, `ANTHROPIC_API_KEY`, `DATABASE_URL`, `MIGRATION_DATABASE_URL`, `SECRET_KEY` en `API_KEY`.
- **Niet in Render:** `APP_BASE_URL`, `VERZENDER_EMAIL`, `VERZENDER_WACHTWOORD`, `SMTP_SERVER`, `SMTP_PORT`, `TRUSTED_PROXY_COUNT`, `RETENTIE_DAGEN_AVG`, `RESTAURANT_*`, `ANTHROPIC_MODEL`, `MAX_*`.
- **`API_KEY` heeft voorrang:** `config.py:49-50` zet `API_KEY = os.getenv('API_KEY') or os.getenv('WEBHOOK_API_KEY')` en daarna `WEBHOOK_API_KEY = API_KEY`. De app start niet zonder minstens één van de twee → roteren op `API_KEY`.
- **Defaults:** `APP_BASE_URL` = localhost (moet in Render), `SMTP_SERVER` = gmail-host, `SMTP_PORT` = 587, `TRUSTED_PROXY_COUNT` = 1, `SESSION_COOKIE_SECURE` = aan, `FLASK_DEBUG` = uit, `RETENTIE_DAGEN_AVG` = 60 (getal, `config.py:38`).
- **Mailsimulatie** (`[MAIL_SIMULATIE]`) staat aan als `VERZENDER_EMAIL` de placeholder is **of** `VERZENDER_WACHTWOORD` leeg. Voor echte mail zijn `VERZENDER_EMAIL` + `VERZENDER_WACHTWOORD` genoeg; of de provider een app-wachtwoord eist staat in de providerdocumentatie (niet nagezocht).
- `ADMIN_INITIAL_PASSWORD` wordt alleen door `flask init-db` gelezen → niet in Render.
- `ALLOW_PROD_DB_LOCAL` staat alleen onder `if __name__ == '__main__'` in `run.py`; raakt `flask create-admin` en gunicorn niet.

### create-admin (BEWIJS, deze sessie in de code)
- Verbinding via `DATABASE_URL` (gepoold); `--productie` is alleen een bevestigingsvlag en schakelt **niet** naar `MIGRATION_DATABASE_URL`.
- Guard **weigert alleen** (geen bevestigingsvraag): niet-SQLite + geen vlag → `ClickException`.
- Wachtwoord alleen interactief (verborgen, met bevestiging), **min. 12 tekens**; leest `ADMIN_INITIAL_PASSWORD` **niet**. Gebruikersnaam = optie, default `admin`.
- Bestaand account: **geen overschrijven**; meldt "bestaat al" en stopt met exitcode 1.
- Geen `FLASK_APP` en geen `.flaskenv`; Flask vindt `wsgi.py` via auto-detectie. Caveat: `.env` is niet geopend en kan toch een `FLASK_APP` bevatten.

### Mail (BEWIJS, deze sessie in de code)
- **Triggers:** `POST /reservering` en `POST /api/v1/ai-reservering` (asynchroon) + `flask resend-mail` (synchroon).
- De gastmail gaat naar het **`email`-veld uit het verzoek**; afzender is `VERZENDER_EMAIL`.
- De reservering is **al gecommit vóór** het versturen; een SMTP-fout wordt alleen gelogd → **een 200 van de API bewijst geen mailverzending.**
- `resend-mail` controleert alleen of de reservering bestaat; nog steeds **geen SMTP-check**. **Besloten (6 okt):** krijgt een `--productie`-guard — code nog niet gewijzigd (aparte sessie).
- `RESTAURANT_NAAM` heeft een placeholder-default die in **onderwerp én body** van de gastmail komt; `RESTAURANT_EMAIL`, `RESTAURANT_TELEFOON` en `RESTAURANT_TAGLINE` staan alleen in web-templates.

### Risico (uit eigen checklist, nog niet in de code bevestigd)
- Ontbreekt `DATABASE_URL` in de shell, dan valt de app stil terug op SQLite → je maakt de admin lokaal in plaats van in Neon.

## 5. Plan voor wat nog openstaat

**Besluiten van de gebruiker:** één Render-sessie (met `API_KEY` erin), mailwachtwoord nu al zetten, geen aparte rotatiesessie meer. Het oude blok "stap 5/6 vlak voor de end-to-end test" vervalt.

**Stap A — Voorbereiding (handmatig, nog niet in Render)**
- Nieuw mailwachtwoord bij de provider (app-wachtwoord? zie providerdocumentatie), opslaan in de wachtwoordmanager.
- Nieuwe `API_KEY` laten genereren (lang, zonder spaties/aanhalingstekens — gaat in een header).

**Stap B — Eén Render-sessie (handmatig)**
- Neon-wachtwoord resetten (Neon-documentatie); nieuwe gepoolde én directe URL opslaan.
- In Render zetten: `DATABASE_URL` (gepoold), `MIGRATION_DATABASE_URL` (direct, nooit `-pooler`), `APP_BASE_URL` (https), `VERZENDER_EMAIL`, `VERZENDER_WACHTWOORD`, `RESTAURANT_NAAM` (+ de andere drie `RESTAURANT_*`), nieuwe `API_KEY`.
- Check in de Render-documentatie of meerdere variabelen in één keer opslaan één deploy geeft; wacht anders op de laatste deploy.
- `/health` in de browser. Daarna dezelfde `API_KEY` in n8n (header `X-API-Key`).
- Oude lokale kopieën vervangen (niet openen in een tool).
- Uitkomst: 200 → door naar C. Build faalt → waarschijnlijk `MIGRATION_DATABASE_URL`. Build ok maar `/health` 5xx → waarschijnlijk `DATABASE_URL`. Meld alleen status/fouttype.

**Stap C — Admin-account in productie (handmatig, pas na groene `/health`)**
- Nieuwe Git Bash in `C:\Codes\WPL`; virtuele omgeving activeren.
- `read -rs DATABASE_URL` → `export DATABASE_URL` (nieuwe gepoolde URL).
- Controle (print alleen één woord): `case "$DATABASE_URL" in postgres*) echo postgres;; "") echo leeg;; *) echo anders;; esac`
- Alleen bij `postgres`: `create-admin --productie` volgens README. Wachtwoord min. 12 tekens, meteen in de wachtwoordmanager.
- `unset DATABASE_URL`, terminal sluiten, inloggen op `/overzicht`.
- Uitkomst: `leeg`/`anders` → stoppen en stap B herhalen. "Bestaat al" → proberen in te loggen. Inloggen mislukt terwijl het commando slaagde → waarschijnlijk op SQLite gelopen.

**Stap D — Mailtest (handmatig)**
- Reserveer via het formulier op de Render-URL, naam begint met "TEST", eigen mailadres.
- Controleer: mail in inbox/spam, afzender klopt, restaurantnaam in onderwerp + tekst, annuleerlink begint met de https-URL van Render.
- Annuleerlink gebruiken (ruimt de testreservering waarschijnlijk op — aanname).
- In het Render-log alleen zoeken naar `[MAIL_SIMULATIE]` of het SMTP-fouttype.
- Uitkomst: geen mail + `[MAIL_SIMULATIE]` → variabelen niet goed in Render. Geen mail + SMTP-fout → noteer type (auth/time-out/verbinding). Localhost-link → `APP_BASE_URL` fout. Placeholder-naam → `RESTAURANT_NAAM` ontbreekt.

**Stap E — End-to-end met n8n:** één testrestaurant (n8n → API → AI → database → mail) met eigen mailadres. Mentor schrijft de prompt na een geslaagde stap D.

**Stap F — Privacy (AVG-minimum):** bewaartermijn + privacyverklaring; hier hoort `RETENTIE_DAGEN_AVG`. Neem mee dat Cline alles naar DeepSeek stuurt: controleer het DeepSeek-gegevensbeleid zodra er echte klantgegevens in de buurt komen.

**Besloten (6 okt):** `resend-mail` krijgt een `--productie`-guard (advies mentor gevolgd; een mailcommando hoort niet zonder waarschuwing een echte productie-gast te mailen). Implementatie in een aparte sessie: branch `fix/resend-mail-productie-guard` + PR — `_guard(productie)` vóór `get_db()`, net als bij `create-admin`/`purge-retention`; guard-test in `tests/test_cli_beheer.py`; README-sectie erbij.

**Optioneel, klein:** `DATABASE_URL` in productie laten crashen i.p.v. stil terugvallen op SQLite (alleen samen met de resend-mail-guard als de code toch wordt aangeraakt). Controleren of `keep-alive.yml` nog groen draait.

**Handmatige controles:**
- Settings Sync sluit `mcp.json` buiten — **afgerond** (bevestigd, 6 okt).
- Oude Anthropic-key verwijderd — **afgerond** (bevestigd, 6 okt).

**Stopcriteria:** rode check op `main` (vooral `CI / unit-tests`), een echte waarde in een diff of log, of een commando dat om iets anders vraagt dan afgesproken → stop en meld alleen het type.

## 6. Voortgang
Ongeveer **75%**. Wat overblijft: stap B t/m E (één dag werk), de privacytekst, plus één kleine codewijziging (de `resend-mail`-guard). **Stap C, D en E kunnen nog verrassingen geven.**

## 7. Lessen (voorkom herhaling)
- Vermeld bij elk commando de shell. In Git Bash: `grep -c -i -E "..."`, geen PowerShell.
- Zoek in code met `git ls-files '*.py' | xargs grep ...`, niet met `grep -r` over de hele map (de eerste zoekopdracht nam 143 namen uit de venv mee — fout in de prompt, niet van de gebruiker). Controleer eerst het aantal bestanden.
- Een teller zegt hoeveel regels matchen, niet wat er staat; een 0 kan een kapotte pipe zijn. Controleer met een patroon waarvan je weet dat het moet matchen.
- Gebruik `git --no-pager`; voeg altijd de telpipe toe aan geheimenscans.
- Een tool kan iets verzinnen (Cline voegde ooit "Render Shell" toe aan de README). Beoordeel diffs zelf in de editor.
- Tools kunnen elkaar tegenspreken (bij `API_KEY`/`WEBHOOK_API_KEY` gebeurde dat); laat de gebruiker de bronregel zelf lezen.
- Controleer eerst, verwijder daarna. Na een gewone merge werkt `git branch -d`; bij squash/rebase niet blind `-D`.
- `git fetch origin --prune` ruimt verouderde remote-verwijzingen op; controleer met `git ls-remote --heads origin <branch>`.
- Een 200 van de API bewijst geen mailverzending; inbox en Render-log zijn het bewijs.

## Bijlage A. Geverifieerde git-stand (alleen-lezen)
- `main` = `origin/main` = `be9ed46` — "Merge pull request #1 from kevino-pro/fix/health-observability".
- Enige branch: `main` (lokaal + remote). De feature-branch bestaat niet meer.
- Werkboom schoon (`git status -sb` → `## main...origin/main`).
- `main`-historie (top): `be9ed46`, `e09b98e`, `5741c65`, `ea0c960`, `e37575b`, `af669bc`, `c230318`, …
- `be9ed46` en `5310880` bestaan lokaal.
- Tool-artefacten in de object-store: refs `refs/agents/<uuid>/checkpoints/turn/*` en `refs/cline/checkpoints/…`, plus enkele dangling commits (`git fsck`). Worden niet gepusht (git pusht standaard alleen `refs/heads` + tags). Ruis, geen actie nodig.

## Bijlage B. Verificatie-tabel (§5, historie)
| # | Punt | Status | Bewijs / volgende actie |
| --- | --- | --- | --- |
| 5.1 | Bestaat er een Render-service? | **JA — draait** | Render-service draait; `/health` geeft HTTP 200. |
| 5.2 | Welke check rood bij `be9ed46` + falende stap | **OPGELOST — groen** | Oorzaak: `RENDER_API_KEY`. Key vervangen en de oude ingetrokken; `verify-render` is nu groen. |
| 5.3 | PR #2 / commit `5310880` | **BEWEZEN** | Merge-commit; ouders `e09b98e` (branch) + `be9ed46` (main); boom `b53c9b8…` identiek aan `be9ed46`; `git diff 5310880 main` leeg → merge van `main` in de branch **zonder nieuwe inhoud**. Nu dangling (niet in `origin/main`). |
| 5.4 | Trigger `render-deployment-health.yml` | **BEWEZEN** | `on:` = `push` met `branches: [main]` in **elke** versie (`318027e`, `e37575b`, `af669bc`, `main`, `HEAD`). Geen `pull_request`-trigger. Draaide dus op de **push naar `main`**, niet op de feature-branch. Open: hoe de gebruiker het op de branch zag. |
| 5.5 | Settings Sync (`mcp.json` niet meesynchroniseren) | **AFGEROND** | `mcp.json` uitgesloten van Settings Sync (bevestigd, 6 okt). |
| 5.6 | Oude Anthropic-key verwijderd | **AFGEROND** | Anthropic- en Neon-key geroteerd, oude keys ingetrokken. |

## Bijlage C. Namenlijst omgevingsvariabelen (alleen NAMEN)
Verplicht bij app-start (anders `RuntimeError`, `app/__init__.py:25-28`):
- `SECRET_KEY`
- `API_KEY` **of** `WEBHOOK_API_KEY` (één van de twee; `WEBHOOK_API_KEY` = legacy alias, `app/config.py:49-50`)

Databaselaag:
- `DATABASE_URL` — **valt stil terug op `sqlite:///reserveringen.db`** als hij ontbreekt (`app/config.py:45-48`); let op deze verborgen faalmodus in productie.
- `MIGRATION_DATABASE_URL`, `ALLOW_PROD_MIGRATE` — alleen voor Alembic tijdens de build (`migrations/env.py:26,46`; pooler-host wordt geweigerd; `ALLOW_PROD_MIGRATE` moet exact `1` zijn).

AI:
- `ANTHROPIC_API_KEY` (verplicht voor de AI-functie, `app/services/ai_service.py:37-39`)
- `ANTHROPIC_MODEL` (optioneel, default in `app/config.py:15`)

Overige app-config (optioneel/default):
- `ADMIN_INITIAL_PASSWORD`, `RETENTIE_DAGEN_AVG`
- `MAX_CAPACITEIT_PER_SLOT`, `MAX_PERSONEN_PER_BOEKING`
- `RESTAURANT_NAAM`, `RESTAURANT_TAGLINE`, `RESTAURANT_EMAIL`, `RESTAURANT_TELEFOON`, `PRIMARY_COLOR`, `APP_BASE_URL`
- `SESSION_COOKIE_SECURE`, `TRUSTED_PROXY_COUNT`
- `SMTP_SERVER`, `SMTP_PORT`, `VERZENDER_EMAIL`, `VERZENDER_WACHTWOORD`

Alleen lokaal/CLI: `FLASK_DEBUG` (`run.py:19`).

Documentatiegat (geen blokkade): README noemt `MAX_CAPACITEIT_PER_SLOT`, `MAX_PERSONEN_PER_BOEKING`, `RESTAURANT_*`, `PRIMARY_COLOR`, `APP_BASE_URL`, `SESSION_COOKIE_SECURE`, `TRUSTED_PROXY_COUNT`, `ANTHROPIC_MODEL` niet.

## Bijlage D. Herbruikbare alleen-lezen commando's (Git Bash)
Draai vanuit de repo-root; gebruik `git --no-pager` en bij geheimenscans altijd een teller-pipe.
```
git --no-pager status -sb
git --no-pager branch -a -vv
git --no-pager log --oneline -8 main
git --no-pager for-each-ref --format='%(refname) %(objectname:short)'
git --no-pager diff --stat 5310880 main
git ls-files '*.py' | wc -l                       # eerst: hoeveel bestanden tellen mee?
git ls-files '*.py' | xargs grep -n -E "PATROON"   # zoek alleen in tracked .py-bestanden
grep -c -i -E "PATROON" bestand                    # telregel (een 0 kan een kapotte pipe zijn)
```


