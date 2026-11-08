Overdracht WPL — template (bijgewerkt 8 nov 2026)
Voor Claude (mentor), Cline (uitvoerder via de DeepSeek-API), Opus in VS Code (controleur) en GitHub Copilot Chat (beperkt). Lokale, niet-gecommitte werkkopie. HYPOTHESE = niet bewezen; BEWIJS = door de gebruiker of de code bevestigd. Alleen namen/hashes/statussen — geen geheimen.

1. Stand (8 nov 2026)
Draait: WPL Den Haag op Render + Neon, /health 200. Reserveren via het formulier en via n8n (AI). Mail via Resend vanaf reserveringen@waroengpadang.nl.
Laatst afgerond: nieuwe huisstijl, fase 1–7 (PR #22–#28, gemerged 7 nov). Door de gebruiker op de telefoon gecontroleerd: alles ziet er goed uit. Tailwind is weg; de workflow "Dagelijks opschonen (AVG)" draait groen.
Uitgesteld: achtergrondfoto (fase 8 punt 2–4 van het huisstijlplan) — zie §6. Tot die tijd toont de site een warme donkere gloed; dat is de bedoelde standaard, geen fout.
Volgende punt: config per restaurant afmaken (logo, kleuren, mailteksten) — zie §6.
Wacht op de gebruiker: bevestiging van de tafelcombinaties en van 68 stoelen tegenover max_gasten_tegelijk = 69 (stap 4).
Tests: python -m unittest discover -s tests → 253 tests, OK (skipped=6). De 6 overgeslagen tests zijn Postgres-tests; die draaien in CI (postgres-tests) of lokaal met TEST_POSTGRES_URL.
2. Rollen en werkafspraken
Gebruiker: software developer in opleiding, basiskennis, bouwt een eigen AI Agency. Nederlands, Windows, VS Code, Git Bash als standaardterminal.
Claude = mentor in code, architectuur en prompts. Legt uit waarom, benoemt afwegingen, is eerlijk over onduidelijk/onveilig/waarschijnlijk fout, controleert claims van tools, scheidt HYPOTHESE van BEWIJS, verzint geen commando's/instellingen/menunamen (verwijst naar documentatie), stelt max. één vraag per keer, antwoordt in het Nederlands, erkent eigen fouten direct.
Cline = uitvoerder (auto-approve UIT); alles wat Cline leest gaat naar DeepSeek. Copilot alleen met een goede reden.
Werkwijze met fasenplannen (sinds 29 okt):
Claude maakt per onderwerp een fasenplan, getest op een kopie (ook op Postgres), met per fase: branch-commando's (Git Bash), de Cline-prompt, de exacte inhoud van nieuwe/gewijzigde bestanden, extra controlepunten voor Opus, het verwachte aantal tests en acties voor/na de merge.
Cline voert één fase uit; Opus in VS Code controleert de fase en geeft GO of NO-GO; de gebruiker doet alle git (branch, commit, push, PR, merge) zelf.
Pas na een merge op main en een groene Render-deploy begint de volgende fase.
Promptopbouw (één prompt per stap): Context → Taak (commando's in codeblok, per commando de shell: Git Bash of PowerShell) → Rapporteer alleen → Beperkingen → Wat je mij meldt. Hangt een stap af van een eerdere uitkomst, zeg dat en geef een invulplek.
Harde regels: prompts standaard alleen-lezen; wijzigen/committen/pushen/verwijderen of een echte DB-verbinding alleen met expliciet akkoord en een precieze reikwijdte. Nooit force-push, historie herschrijven, git branch -D, of Alembic-/Neon-acties zonder expliciete opdracht. Geheimen (keys, wachtwoorden, connection strings, tokens, inhoud van .env/.flaskenv/mcp.json/.neon) nooit tonen, kopiëren of laten uitlezen — alleen aantallen, bestandsnamen, variabelenamen, ja/nee of fouttypes. Geheimenscans tonen alleen een teller. Nieuwe wachtwoorden/keys: zelf genereren in de eigen terminal, nooit in een chat plakken. Commit-/pushprompts: eerst controles, dan akkoord, dan uitvoeren.
Alle git-commando's (ook alleen-lezen) draait de gebruiker zelf in Git Bash.
Repo-bestanden gebruiken CRLF; bestaande regeleinden behouden.
3. Project en architectuur
Repo C:\Codes\WPL, privé op GitHub (kevino-pro). main beschermd: PR verplicht, check CI / unit-tests verplicht, geen force-push. CI draait ook postgres-tests (HYPOTHESE: niet als verplichte check ingesteld; controleren in Settings → Branches).
Stack: Flask (Application Factory + Blueprints web, api, beheer), SQLAlchemy Core 2.0, Pydantic v2, Alembic. AI: Anthropic Claude Haiku 4.5 met retry. Hosting: Render (gunicorn, 2 workers, gratis plan, geen Shell) + Neon Postgres; SQLite lokaal.
Doel: een template voor andere restaurants. Besluit (28 okt): één installatie per restaurant/vestiging — eigen Render-service, eigen Neon-database, eigen restaurantbestand. Geen gedeelde multi-tenant app.
Restaurantbestand: restaurants/<naam>.toml, gekozen met RESTAURANT_CONFIG; in productie (APP_ENV=production) fail-closed. Secties:
[reserveringen]: tijdzone, slot_minuten, zitduur_minuten, max_gasten_tegelijk, max_personen_per_boeking, min_minuten_vooraf, max_dagen_vooruit, sluitingsdagen, [reserveringen.openingstijden] (laatste starttijd per dag).
[plattegrond]: raster (kolommen × rijen), tafels, combinaties, elementen.
[privacy]: verantwoordelijke, adres, optioneel kvk, bijgewerkt, verwerkers (naam, doel, locatie). Verplicht in productie.
[huisstijl]: accentkleur (#rrggbb, standaard #d9a441), ondertitel (max. 80 tekens), optioneel achtergrond (pad onder static/, jpg/jpeg/png/webp). Een opgegeven foto die niet bestaat laat de app niet starten.
In [reserveringen] sinds de huisstijl ook: knop_minuten (30; veelvoud van slot_minuten) en diner_vanaf ("16:00", grens tussen de kopjes Lunch en Diner).
restaurants/voorbeeld.toml is het sjabloon voor een nieuw restaurant.
Vestigingen WPL:
Den Haag = restaurants/wpl.toml: Schoolstraat 35, 2511 AW; ma dicht, di–zo 12:00–21:00 (laatste reservering 19:30); zitduur 90 min; 69 gasten tegelijk; max 8 per online boeking; 22 tafels, raster 19×10.
Amsterdam: later als restaurants/wpl-amsterdam.toml met een eigen installatie; gegevens volgen.
Routes: /, /reservering, /beschikbaarheid (vrije tijden per dag, rate limit 120/10 min), /bevestiging, /bevestiging/agenda.ics, /annuleren/<id>, /privacy, /health, /login, /logout, /overzicht, /verwijder/<id>, /plattegrond, /plattegrond/toewijzen (personeel), POST /api/v1/ai-reservering (n8n, header X-API-Key), POST /beheer/opschonen (GitHub Actions, header X-Beheer-Key; 404 zonder geldige BEHEER_API_KEY).
Reserveringsregels (server-side): openingstijden, slots, capaciteit = max gasten tegelijk over de zitduur, max groepsgrootte. Dubbele boeking (zelfde datum+tijd én zelfde e-mail, telefoon of naam, genormaliseerd) → 409. Telefoon: 9–15 cijfers; cijfers, spaties, streepjes en een voorloop-+.
Database (Alembic): baseline ba7cbc14b3a2, daarna c3f1a7d2e9b4 (tabel tafeltoewijzingen). Migraties draaien in het Render-build-command (alembic upgrade head), init-db erbuiten.
Beheercommando's (allemaal met --productie-guard behalve init-db): flask create-admin, flask purge-retention, flask dubbele-reserveringen (alleen lezen), flask resend-mail <id>, flask init-db (lokaal hulpmiddel).
Geplande jobs (GitHub Actions): keep-alive.yml (houdt Render wakker), opschonen.yml (elke nacht 03:17 UTC; verwijdert reserveringen ouder dan RETENTIE_DAGEN_AVG = 60 dagen), render-deployment-health.yml (controleert de deploy na een push naar main), ci.yml.
4. Wat is af
Afgeronde onderdelen sinds 28 okt zijn "afgerond volgens gebruiker" en daarna in de code op main teruggezien (6 nov): bestanden, routes, migratie en workflows bestaan.

Datum	Onderdeel	Belangrijkste wijzigingen	Fasenplan
okt	Live gaan (stap A–E)	Sleutelrotatie, Alembic-baseline, Render + Neon, admin Kevin, mailtest, n8n-keten, Resend (PR #6), resend-mail-guard en APP_ENV (PR #8), domein waroengpadang.nl verified	—
28 okt	Review + besluit template	XSS in overzicht.html, purge op Postgres, ANTHROPIC_MODEL gevonden; besluit één installatie per restaurant	
WPL reserveringssysteem: stand van zaken en verbeterpunten
29–31 okt	Stap 1–2	Fixes uit de review, APP_ENV, PR's t/m #9	
Fasenplan voor Cline: stap 1 en 2
4 nov	Stap 3: reserveringsregels	Restaurantbestand + RESTAURANT_CONFIG, openingstijden, zitduur, capaciteit, tijdzone voor de AI-prompt	
Fasenplan voor Cline: stap 3 reserveringsregels
5 nov	Dubbele boekingen + telefoon	409 bij dubbel, telefoon- en naamcontrole, flask dubbele-reserveringen	
Fasenplan voor Cline: Fasdubbele boekingen en telefoonnummers
5 nov	Stap 4: plattegrond personeel	Tafels in TOML, tabel tafeltoewijzingen, /plattegrond + toewijzen	
Fasenplan voor Cline: stap 4 plattegrond voor personeel
6 nov	Privacy + automatisch opschonen	/beheer/opschonen, opschonen.yml, [privacy] in TOML, nieuwe privacyverklaring	
Fasenplan voor Cline: privacy en automatisch opschonen
7 nov	Nieuwe huisstijl	[huisstijl] in TOML, eigen huisstijl.css, layouts basis.html en personeel.html, /beschikbaarheid, formulier met tijdknoppen, bevestiging met agenda, overzicht per dag, plattegrond in nieuwe stijl, Tailwind weg (PR #22–#28)	
Fasenplan voor Cline: nieuwe huisstijl
De open punten van 31 okt (afzender in de testmail, oude stash, in de chat gebruikte testadressen/keys vervangen) zijn afgerond (bevestigd door de gebruiker, 6 nov).

5. Instellingen (alleen NAMEN)
Render (Environment):

Verplicht: SECRET_KEY, API_KEY (of legacy WEBHOOK_API_KEY), DATABASE_URL (gepoold), APP_ENV=production, RESTAURANT_CONFIG.
Build/migratie: MIGRATION_DATABASE_URL (direct, nooit -pooler), ALLOW_PROD_MIGRATE (exact 1).
AI: ANTHROPIC_API_KEY, optioneel ANTHROPIC_MODEL.
Mail: RESEND_API_KEY, VERZENDER_EMAIL; SMTP als fallback zonder Resend: SMTP_SERVER, SMTP_PORT, VERZENDER_WACHTWOORD.
Opschonen: BEHEER_API_KEY (min. 32 tekens; zelfde waarde als het GitHub-secret).
Restaurant en weergave: APP_BASE_URL (https), RESTAURANT_NAAM, RESTAURANT_EMAIL, RESTAURANT_TELEFOON. Kleur, foto en ondertitel staan in [huisstijl] van het restaurantbestand.
Optioneel/default: RETENTIE_DAGEN_AVG (60), TRUSTED_PROXY_COUNT (1), SESSION_COOKIE_SECURE (aan).
Alleen lokaal: ADMIN_INITIAL_PASSWORD (init-db), FLASK_DEBUG, ALLOW_PROD_DB_LOCAL (run.py).
GitHub (Settings → Secrets and variables → Actions):

Variables: RENDER_HEALTH_URL, RENDER_APP_URL (zonder /health), RENDER_SERVICE_ID.
Secrets: RENDER_API_KEY, BEHEER_API_KEY.
Let op: DATABASE_URL valt stil terug op SQLite als hij ontbreekt — controleer de host vóór create-admin of een ander productiecommando.

6. Roadmap
Config per restaurant afmaken (volgende): kleur, foto en ondertitel staan sinds de nieuwe huisstijl in [huisstijl]; naam, e-mail en telefoon staan nog als Render-variabelen en de mailtekst in de code. De template-kit en Amsterdam leunen hierop.
Achtergrondfoto (uitgesteld, fase 8 punt 2–4 van het huisstijlplan):
Kies een sfeerfoto van het restaurant waarvan WPL de rechten heeft (geen afbeelding van internet), liggend, ongeveer 1600 pixels breed, WebP of JPG onder 300 KB (bijv. via squoosh.app).
Zet hem in static/restaurants/wpl/achtergrond.webp (map bestaat nog niet; zelf aanmaken).
Zet in restaurants/wpl.toml onder [huisstijl]: achtergrond = "restaurants/wpl/achtergrond.webp".
Branch feat/achtergrondfoto, tests draaien (test_restaurantbestanden_zijn_geldig controleert dat de foto bestaat), commit, PR, merge; daarna op de telefoon kijken.
Template-kit: render.yaml, export van de n8n-workflow, onboardingchecklist voor een nieuw restaurant (TOML invullen, Render + Neon aanmaken, variabelen, GitHub-variabelen/secrets, admin, mailtest).
Installatie Amsterdam: restaurants/wpl-amsterdam.toml + eigen Render-service en Neon-database.
Open vragen voor de gebruiker:

Stap 4: kloppen de tafelcombinaties (1a–1e, 3ab, 5ab, 6ab, 7ab, 10ab)? En 68 stoelen tegenover max_gasten_tegelijk = 69?
Privacy: de locaties van Render, Neon en n8n staan als "Europese Unie" in wpl.toml; bevestigen in hun dashboards als dat nog niet gebeurd is.
DeepSeek: Cline stuurt alles wat het leest naar DeepSeek. Laat Cline nooit echte klantgegevens lezen (database, exports, logs).
Bewust niet nu: IP-scrubbing, Swagger/APIFlask, Celery+Redis, smallere Neon-key, een UNIQUE-index tegen dubbele boekingen.

7. Lessen (voorkom herhaling)
Vermeld bij elk commando de shell. In Git Bash: grep -c -i -E "...", geen PowerShell.
Zoek in code met git ls-files '*.py' | xargs grep ..., niet met grep -r over de hele map (de venv en Python/ tellen anders mee). Controleer eerst het aantal bestanden.
Een teller zegt hoeveel regels matchen, niet wat er staat; een 0 kan een kapotte pipe zijn. Controleer met een patroon waarvan je weet dat het moet matchen.
Gebruik git --no-pager; voeg altijd de telpipe toe aan geheimenscans.
Een tool kan iets verzinnen (Cline voegde ooit "Render Shell" toe aan de README). Beoordeel diffs zelf in de editor.
Tools kunnen elkaar tegenspreken (bij API_KEY/WEBHOOK_API_KEY gebeurde dat); laat de gebruiker de bronregel zelf lezen.
Controleer eerst, verwijder daarna. Na een gewone merge werkt git branch -d; bij squash/rebase niet blind -D.
git fetch origin --prune ruimt verouderde remote-verwijzingen op; controleer met git ls-remote --heads origin <branch>.
Een 200/201 van de API bewijst geen mailverzending of opslag; inbox, Render-log en /overzicht zijn het bewijs.
Controleer de database-host vóór create-admin (echo van alleen het type). Een account in de verkeerde database lijkt te werken maar is onvindbaar voor de app.
In PowerShell: een URL via Get-Clipboard zetten, niet typen; het &-teken breekt het commando.
Testuitslag: gebruik ... 2>&1 | grep -E "^Ran|^OK|FAILED". Met tail -3 valt de regel "Ran N tests" weg. Een ResourceWarning: unclosed database is geen fout.
GitHub Actions: een secret hoort onder de tab Secrets van Actions (Repository secrets), een variable onder de tab Variables. Codespaces/Dependabot-secrets en environment-secrets ziet een gewone workflow niet. Na een wijziging een nieuwe run starten via "Run workflow".
Tests lezen verwachte waarden (naam, adres, datum) uit de config in plaats van ze vast in de test te zetten; anders breekt een test zodra het restaurantbestand wordt aangepast.
Een privacyverklaring belooft alleen wat de code doet; daarom kwam het automatisch opschonen vóór de tekst.
Bijlage. Herbruikbare alleen-lezen commando's (Git Bash)
Draai vanuit de repo-root; gebruik git --no-pager en bij geheimenscans altijd een teller-pipe.

git --no-pager status -sb
git --no-pager branch -a -vv
git --no-pager log --oneline -8 main
git ls-files '*.py' | wc -l                       # eerst: hoeveel bestanden tellen mee?
git ls-files '*.py' | xargs grep -n -E "PATROON"   # zoek alleen in tracked .py-bestanden
grep -c -i -E "PATROON" bestand                    # telregel (een 0 kan een kapotte pipe zijn)
python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"