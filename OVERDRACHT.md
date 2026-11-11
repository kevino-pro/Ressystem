Overdracht WPL — template (bijgewerkt 11 nov 2026)
Voor Claude (mentor), Cline (uitvoerder via de DeepSeek-API), Opus of Sonnet in VS Code (controleur; de plannen van 11 nov gebruiken Sonnet) en GitHub Copilot Chat (beperkt). Lokale, niet-gecommitte werkkopie. HYPOTHESE = niet bewezen; BEWIJS = door de gebruiker of de code bevestigd. Alleen namen/hashes/statussen — geen geheimen.

1. Stand (11 nov 2026)
Draait: WPL Den Haag op Render + Neon, /health 200. Reserveren via het formulier en via n8n (AI). Mail via Resend vanaf reserveringen@waroengpadang.nl.
Laatst afgerond (11 nov): fasenplan personeelspagina's, fase 1–4: menu op de telefoon (PR #57), reserveringsoverzicht compacter op de telefoon (PR #58), plattegrond op de telefoon met tijdenstrook en tafelknoppen (PR #59), invoerformulier met minder velden vooraf en een ruimtezin via /reservering/ruimte (PR #60). Alles voor telefoons staat in @media (max-width: 700px); tablet en pc blijven zoals ze waren.
Daarvoor (10–11 nov): fasenplan reserveringspagina versimpelen, fase 1–4: compact formulier (PR #53), dagstrook Vandaag/Morgen/Andere dag (PR #54), privacyzin in plaats van vinkje (PR #55), wijzigpagina in dezelfde stijl (PR #56); deel 9 wijzigen door de gast tot 2 uur van tevoren (PR #49) en de wijzigingsmail met markering "Gewijzigd door de gast" (PR #50); deel 10 cijfers: dagtellingen bij het opschonen (PR #51) en de pagina /cijfers (PR #52). Daarmee is het wensenplan van de eigenaar (10 delen) helemaal af.
Eerder (10 nov): deel 1 zitduur 1 uur en groepen tot 15 (PR #30); deel 2 opmerking, kinderstoelen en allergieën (PR #31–#32); deel 3 accounts personeel, fase 1–3 (PR #33–#35); deel 4 reserveren door personeel: telefonisch (PR #36) en binnenloper, samen met de fix voor de annuleer-omweg (PR #37, zie §6); deel 5 gearriveerd en no-show (PR #38); deel 6 talen EN/NL/ID: gastpagina's (PR #39), mails (PR #40), personeelspagina's (PR #41), privacyverklaring (PR #42, #44); deel 7 herinneringsmail de dag voor het bezoek: mail en route (PR #43), planning om 10:00, overzicht en privacytekst (PR #45); deel 8 zoeken op naam of telefoonnummer (PR #46).
Daarvoor: nieuwe huisstijl, fase 1–7 (PR #22–#28, gemerged 7 nov). Door de gebruiker op de telefoon gecontroleerd: alles ziet er goed uit. Tailwind is weg; de workflow "Dagelijks opschonen (AVG)" draait groen.
Uitgesteld: achtergrondfoto (fase 8 punt 2–4 van het huisstijlplan) — zie §6. Tot die tijd toont de site een warme donkere gloed; dat is de bedoelde standaard, geen fout.
Volgende punt: config per restaurant afmaken (logo, kleuren, mailteksten) — zie §6.
Wacht op de gebruiker: bevestiging van de tafelcombinaties en van 68 stoelen tegenover max_gasten_tegelijk = 69 (stap 4).
Tests: volgens het fasenplan 650 tests na PR #60 (nulmeting 614 op 3375575, +36). In de code staan 650 testfuncties (geteld op 11 nov); een testrun op main na PR #60 is nog niet door Claude gezien. Draai zelf: python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED". De 6 overgeslagen tests zijn Postgres-tests; die draaien in CI (postgres-tests) of lokaal met TEST_POSTGRES_URL.
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
Stack: Flask (Application Factory + Blueprints web, api, beheer, accounts, account, invoeren, cijfers), SQLAlchemy Core 2.0, Pydantic v2, Alembic. AI: Anthropic Claude Haiku 4.5 met retry. Hosting: Render (gunicorn, 2 workers, gratis plan, geen Shell) + Neon Postgres; SQLite lokaal.
Doel: een template voor andere restaurants. Besluit (28 okt): één installatie per restaurant/vestiging — eigen Render-service, eigen Neon-database, eigen restaurantbestand. Geen gedeelde multi-tenant app.
Restaurantbestand: restaurants/<naam>.toml, gekozen met RESTAURANT_CONFIG; in productie (APP_ENV=production) fail-closed. Secties:
[reserveringen]: tijdzone, slot_minuten, zitduur_minuten, max_gasten_tegelijk, max_personen_per_boeking, min_minuten_vooraf, max_dagen_vooruit, sluitingsdagen, [reserveringen.openingstijden] (laatste starttijd per dag).
[plattegrond]: raster (kolommen × rijen), tafels, combinaties, elementen.
[privacy]: verantwoordelijke, adres, optioneel kvk, bijgewerkt, verwerkers (naam, doel, locatie). Verplicht in productie.
[huisstijl]: accentkleur (#rrggbb, standaard #d9a441), ondertitel (max. 80 tekens), optioneel achtergrond (pad onder static/, jpg/jpeg/png/webp). Een opgegeven foto die niet bestaat laat de app niet starten.
[herinnering] (deel 7, optioneel): uur (0–23, standaard 10; tijdzone van het restaurant). Onbekende sleutels laten de app niet starten. Zonder de sectie gaan er geen herinneringen uit. wpl.toml en voorbeeld.toml: uur = 10.
[talen] (deel 6, optioneel): beschikbaar (lijst uit en, nl, id; geen dubbele) en standaard (moet in beschikbaar staan). Zonder [talen] is alles Nederlands en is er geen taalkiezer. wpl.toml: beschikbaar = ["en", "nl", "id"], standaard = "en". Volgorde van de taal per verzoek: ingelogd personeel de taal van het account (als het restaurant die aanbiedt), anders de cookie taal, dan Accept-Language van de browser, dan de standaard.
In [reserveringen] sinds de huisstijl ook: knop_minuten (30; veelvoud van slot_minuten) en diner_vanaf ("16:00", grens tussen de kopjes Lunch en Diner).
Sinds deel 9 ook: wijzigen_minuten_vooraf (optioneel; wpl.toml en voorbeeld.toml: 120). Tot zoveel minuten voor de begintijd mag de gast zelf wijzigen; daarna alleen annuleren of bellen.
Sinds deel 2 ook: kinderstoelen (aantal in het restaurant, 0 = het formulier vraagt er niet naar; online geteld over de zitduur) en vraag_allergieen (true/false). Allergieën worden alleen bewaard met een apart vinkje (artikel 9 AVG), zijn alleen voor personeel zichtbaar, staan niet in mail of agenda en worden in de nacht na het bezoek gewist. De privacyverklaring past zich aan beide aan. Elke reservering kan ook een opmerking hebben (max. 300 tekens).
restaurants/voorbeeld.toml is het sjabloon voor een nieuw restaurant.
Vertalingen (deel 6): de teksten in code en templates zijn Nederlands; vertalingen/en.toml en vertalingen/id.toml zetten elke Nederlandse zin om ("Nederlandse zin" = "vertaling"). app/taal.py laadt ze bij het starten en weigert lege vertalingen en afwijkende {plaatshouders}. In templates: t("...") voor gewone tekst, th("...") voor een zin met een link of nadruk (alleen Markup uit een {% set %}-blok blijft HTML; al het andere wordt ge-escaped); in plattegrond.html heet de vertaalfunctie binnen de tafellus _t. Foutklassen houden .bericht in het Nederlands (logs, CLI) en geven de gast .vertaald(). Tijden blijven 24-uurs; de datum "laatst bijgewerkt" in de privacyverklaring blijft dd-mm-jjjj. tests/test_vertalingen.py controleert dat elke zin uit code, templates en de verwerkers in restaurants/*.toml in beide bestanden staat: een nieuw restaurantbestand met eigen verwerkerszinnen vraagt dus ook nieuwe vertalingen.
Vestigingen WPL:
Den Haag = restaurants/wpl.toml: Schoolstraat 35, 2511 AW; ma dicht, di–zo 12:00–21:00 (laatste reservering 20:00); zitduur 60 min; 69 gasten tegelijk; max 15 per online boeking (grotere groepen bellen en bestellen vooraf); 2 kinderstoelen; vraagt naar allergieën; 22 tafels, raster 19×10. De tests gebruiken tests/restaurant_vast.toml (de oude waarden: 90 min, max 8, 19:30); tests/test_wpl_regels.py test de echte waarden van wpl.toml.
Amsterdam: later als restaurants/wpl-amsterdam.toml met een eigen installatie; gegevens volgen.
Routes: /, /reservering, /beschikbaarheid (vrije tijden per dag, rate limit 120/10 min), /bevestiging, /bevestiging/agenda.ics, /annuleren/<id> (pagina "Wijzig of annuleer"; dit blijft de link in de mails), POST /wijzigen/<id> (gast wijzigt dag, tijd of aantal; GET stuurt terug naar /annuleren/<id>; rate limit 20/10 min), /privacy, /taal/<code> (GET, zonder CSRF: zet de cookie taal, HttpOnly, SameSite=Lax, een jaar; bij ingelogd personeel ook personeel.taal; onbekende code zet niets; ?terug= alleen een pad op deze site zonder stuurtekens, anders /), /health, /login, /logout, /overzicht, /zoeken (GET ?q=; alle personeel; zoekt op naam of telefoonnummer in de reserveringen van vandaag en later, minstens 2 tekens, hoogstens 50 resultaten; zoekterm ingekort tot 100 tekens, alleen in Python vergeleken, niet gelogd; geen reservering-id in de pagina), /plattegrond, /plattegrond/toewijzen, /account (eigen wachtwoord; alle personeel), /reservering/nieuw (GET en POST; alle personeel; telefonische reservering, met ?bron=binnenloper een binnenloper op nu), GET /reservering/ruimte (?datum=&tijd=&aantal=[&kinderstoelen=]; alle personeel; JSON met de ruimtezin voor het invoerformulier, bewaart niets; rate limit 120/10 min), /cijfers (?week=JJJJ-MM-DD; alleen beheerder; alleen aantallen, geen namen), POST /aankomst (status gearriveerd/no-show/terug naar verwacht; alle personeel; met datum + kenmerk, nooit het id), /verwijder/<id> en /accounts (alleen beheerder), POST /api/v1/ai-reservering (n8n, header X-API-Key), POST /beheer/opschonen en POST /beheer/herinneringen (GitHub Actions, header X-Beheer-Key; 404 zonder geldige BEHEER_API_KEY; rate limit samen 10 per uur).
Personeelsrollen (app/toegang.py): beheerder mag alles, ook reserveringen verwijderen en op /accounts accounts aanmaken, aan- en uitzetten en een nieuw wachtwoord instellen. Medewerker mag /overzicht en /plattegrond bekijken, tafels toewijzen, reserveringen invoeren (/reservering/nieuw), gearriveerd/no-show zetten en op /account het eigen wachtwoord wijzigen; niet verwijderen en geen accounts beheren. Rol en actief worden bij elk verzoek uit de database gelezen: een uitgezet account of een nieuw wachtwoord logt direct uit, ook op een telefoon die nog ingelogd is. Accounts worden uitgezet, nooit verwijderd; er blijft altijd minstens één actieve beheerder. Gebruikersnaam 3–30 tekens (kleine letters, cijfers, punt, streepje, underscore), wachtwoord 12–128 tekens.
Reserveringsregels (server-side): openingstijden, slots, capaciteit = max gasten tegelijk over de zitduur, max groepsgrootte. Dubbele boeking (zelfde datum+tijd én zelfde e-mail of telefoonnummer, genormaliseerd; de naam telt niet mee, en een leeg e-mailadres of telefoonnummer telt nooit als gelijk) → 409. Telefoon: 9–15 cijfers; cijfers, spaties, streepjes en een voorloop-+.
Reserveringen door personeel (deel 4, app/routes/invoeren.py, /reservering/nieuw): e-mail niet verplicht (alleen met e-mail gaat er een bevestigingsmail), tot 200 personen, ook buiten de online regels. Capaciteit wordt niet afgedwongen (verwerk_reservering met max_capaciteit=None); bij een dichte dag, meer dan max_gasten_tegelijk of te weinig kinderstoelen volgt eerst een waarschuwing en pas na "Toch opslaan" wordt opgeslagen. Datum in het verleden, telefonisch zonder telefoonnummer of allergieën zonder toestemming → 400; dubbel → 409. Binnenloper: datum vandaag en tijd nu (afgerond op 5 min), naam (standaard "Binnenloper") en telefoon niet verplicht; na opslaan naar de plattegrond op dat moment. Knop "+ Binnenloper" alleen bij vandaag, in het overzicht en op de plattegrond.
Kolom bron in reserveringen (deel 4): online (formulier; standaard, ook voor bestaande reserveringen), ai (n8n/AI-route), telefoon en binnenloper (personeel); BRONNEN in app/database.py. Kolom ingevoerd_door: gebruikersnaam van het personeelsaccount (uit de sessie, nooit uit het formulier). Overzicht en plattegrond tonen de bron.
Kolom status in reserveringen (deel 5): verwacht (standaard, ook voor bestaande reserveringen), gearriveerd of no_show; STATUSSEN en zet_status in app/database.py. Het personeel zet de status via POST /aankomst (knoppen "Is er", "Niet gekomen", "Ongedaan maken" in het overzicht): gearriveerd en no_show niet voor een dag in de toekomst, no_show vandaag pas vanaf de begintijd, terug naar verwacht altijd. Een no-show telt niet mee voor bezetting, kinderstoelen, drukte, tafels, piek en gastentellers; op de plattegrond staat hij apart onder "Niet gekomen". Na gearriveerd of no_show kan de gast niet meer online annuleren (/annuleren/<id> geeft 409).
Kolom taal in reserveringen (deel 6 fase 2): en, nl of id, standaard 'nl' (ook voor bestaande reserveringen en de AI-route). Online reserveren slaat de taal van het verzoek op; het personeel kiest hem in /reservering/nieuw (alleen de beschikbare talen; anders de standaard). De bevestigingsmail en flask resend-mail gebruiken deze taal; de mail blijft platte tekst.
Kolom taal in personeel (deel 6 fase 3): en, nl of id, standaard 'nl' (bestaande accounts blijven Nederlands). De personeelspagina's volgen deze taal; wijzigen via de taalkiezer (/taal/<code>).
Herinneringsmail (deel 7, app/herinnering.py): de dag voor het bezoek, platte tekst in de taal uit reserveringen.taal, met datum, tijd, aantal, adres uit [privacy], de annuleerlink en het telefoonnummer; geen allergieën of opmerking. Alleen voor reserveringen van morgen met status verwacht, een e-mailadres, nog zonder herinnering en niet vandaag aangemaakt. Kolom reserveringen.herinnering_verstuurd (DateTime, leeg = nog niet verstuurd) wordt vóór het versturen gezet (claim_herinnering) en bij een mislukte mail teruggezet; zo krijgt niemand er twee (uitzondering: een time-out nadat Resend de mail al aannam). POST /beheer/herinneringen verstuurt vanaf het uur in [herinnering] (daarvoor "te_vroeg"), hoogstens 20 per aanroep met 0,6 s pauze, en geeft verstuurd, mislukt en resterend terug. Het overzicht toont "Herinnering verstuurd"; de privacyverklaring noemt de herinnering als [herinnering] bestaat.
Zoeken (deel 8): /zoeken in de balk van het overzicht; zie Routes.
Wijzigen door de gast (deel 9): via de link in de bevestigingsmail (/annuleren/<id>, pagina "Wijzig of annuleer") kan de gast dag, tijd en aantal wijzigen met dezelfde regels als bij reserveren, alleen met status verwacht, niet boven max_personen_per_boeking en tot wijzigen_minuten_vooraf voor de huidige begintijd; anders 409. /beschikbaarheid?behalve=<id> telt de eigen reservering niet mee. Bij een wijziging vervallen de tafeltoewijzingen, wordt de herinnering teruggezet als de datum verandert en wordt kolom gewijzigd_op gezet; de gast krijgt een wijzigingsmail en het overzicht toont "Gewijzigd door de gast".
Cijfers (deel 10, app/cijfers.py, app/routes/cijfers.py): gasten per dag en week, drukste tijden per half uur (gemiddeld over open dagen), per bron en het aandeel no-shows. Omdat reserveringen na 60 dagen worden verwijderd, bewaart het opschonen eerst per dag en bron alleen aantallen in tabel dagtellingen (_bewaar_dagtellingen in app/database.py, in dezelfde transactie, elke reservering één keer). Oudere weken komen daaruit. Knop Cijfers in het personeelsmenu, alleen voor de beheerder.
Telefoonweergave personeel (11 nov): op een telefoon (tot 700 px) toont het menu alleen Reserveringen en Plattegrond, de rest onder de knop Menu; het overzicht is compacter (telefoonnummer om op te tikken, e-mailadres alleen op een breed scherm, klasse alleen-breed); de plattegrond heeft een tijdenstrook en tafelknoppen in een vaste balk onderaan en schuift niet meer zijwaarts; het invoerformulier vraagt eerst Naam, Telefoon, Personen, Tijd en Datum (de rest onder Meer gegevens; bij een binnenloper alleen Personen, Tijd en Datum) en toont tijdens het invullen of er plek is (oranje als het niet past). Bewust niet veranderd: Cijfers, Medewerkers, Mijn account, de loginpagina en de tekening van de plattegrond.
Reserveringspagina gasten (10–11 nov): aantal personen als keuzelijst, kinderstoel/allergie/opmerking in een uitklapblok, vaste balk onderaan met de keuze en de knop (uit tot er een tijd is gekozen), meldingen per veld, dagstrook (een dag zonder boekbare tijd staat dicht), link Personeel in de voet, privacy als zin met link in plaats van vinkje (het vinkje voor allergie-toestemming blijft). De 17 tijdknoppen en de kopjes Lunch en Diner blijven.
Database (Alembic): baseline ba7cbc14b3a2, daarna c3f1a7d2e9b4 (tabel tafeltoewijzingen), e5b9c1d3a7f2 (opmerking, kinderstoelen, allergieen) en a8d3f5b2c7e1 (personeel: rol en actief; bestaande accounts werden beheerder), c4e7a1f9d2b6 (reserveringen: bron en ingevoerd_door) f2a6c8e4b1d7 (reserveringen: status, standaard 'verwacht'), a3c9e5f1b7d4 (reserveringen: taal, standaard 'nl') b8e2d4f6a1c9 (personeel: taal, standaard 'nl') c6f3a9d1e8b5 (reserveringen: herinnering_verstuurd), d7a2e4c9f3b1 (reserveringen: gewijzigd_op) en e8b3f1a6c2d9 (tabel dagtellingen: datum + bron, met reserveringen, gasten en no_shows). Head = e8b3f1a6c2d9. Migraties draaien in het Render-build-command (alembic upgrade head), init-db erbuiten.
Beheercommando's (allemaal met --productie-guard behalve init-db): flask create-admin [--rol beheerder|medewerker] (standaard beheerder; noodoptie, normaal via /accounts), flask purge-retention, flask dubbele-reserveringen (alleen lezen), flask resend-mail <id>, flask herinneringen [--uitvoeren] (zonder vlag alleen tellen; met vlag versturen zonder op het uur te wachten; exitcode 1 als er iets mislukt), flask init-db (lokaal hulpmiddel).
Geplande jobs (GitHub Actions): keep-alive.yml (houdt Render wakker), opschonen.yml (elke nacht 03:17 UTC; verwijdert reserveringen ouder dan RETENTIE_DAGEN_AVG = 60 dagen en wist de allergieën van reserveringen van voor vandaag; bewaart eerst de dagtellingen), herinneringen.yml (08:00 en 09:00 UTC, zodat het in winter- en zomertijd 10:00 in Nederland is; roept /beheer/herinneringen hoogstens 5 keer aan zolang er iets resteert; faalt als er een mail mislukt, zodat GitHub een melding stuurt), render-deployment-health.yml (controleert de deploy na een push naar main), ci.yml.
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
10 nov	Deel 1: zitduur en groepen	Zitduur 60 min, laatste reservering 20:00, online tot 15 personen, tests/restaurant_vast.toml + test_wpl_regels.py (PR #30)	
10 nov	Deel 2: extra wensen	Opmerking en kinderstoelen (migratie e5b9c1d3a7f2, PR #31); allergieën met apart vinkje, gewist na het bezoek, privacyverklaring bijgewerkt (PR #32)	
10 nov	Accounts personeel (deel 3, fase 1–3)	Rollen beheerder en medewerker, migratie a8d3f5b2c7e1, pagina /accounts (PR #33–#34), pagina /account voor het eigen wachtwoord (fase 3), create-admin --rol	
Fasenplan voor Cline: accounts personeel
10 nov	Reserveren door personeel (deel 4, fase 1–2)	/reservering/nieuw, kolom bron en ingevoerd_door, migratie c4e7a1f9d2b6 (PR #36); binnenloper en het kenmerk (HMAC) op de plattegrond (PR #37)	
10 nov	Gearriveerd en no-show (deel 5)	Kolom status, migratie f2a6c8e4b1d7, POST /aankomst, no-shows tellen niet mee, annuleren na aankomst geeft 409 (PR #38)	
10 nov	Talen EN/NL/ID (deel 6, fase 1–4)	[talen], app/taal.py, vertalingen/, /taal/<code>, gastpagina's (PR #39), mails + reserveringen.taal, migratie a3c9e5f1b7d4 (PR #40), personeelspagina's + personeel.taal, migratie b8e2d4f6a1c9 (PR #41), privacyverklaring (PR #42, #44)	
10 nov	Herinneringsmail (deel 7, fase 1–2)	[herinnering], app/herinnering.py, kolom herinnering_verstuurd, migratie c6f3a9d1e8b5, POST /beheer/herinneringen, flask herinneringen (PR #43); herinneringen.yml om 10:00, "Herinnering verstuurd" in het overzicht, zin in de privacyverklaring (PR #45)	
10 nov	Zoeken (deel 8)	/zoeken op naam of telefoonnummer, vandaag en later, haal_reserveringen_vanaf (PR #46)	
10 nov	Wijzigen door de gast (deel 9, fase 1–2)	POST /wijzigen/<id>, wijzigen_minuten_vooraf, kolom gewijzigd_op, migratie d7a2e4c9f3b1 (PR #49); wijzigingsmail en "Gewijzigd door de gast" (PR #50)	
10 nov	Cijfers (deel 10, fase 1–2)	Tabel dagtellingen, migratie e8b3f1a6c2d9 (PR #51); pagina /cijfers voor de beheerder (PR #52)	
10–11 nov	Reserveringspagina versimpelen (fase 1–4)	Compact formulier (PR #53), dagstrook (PR #54), privacyzin (PR #55), wijzigpagina in dezelfde stijl (PR #56)	
Fasenplan voor Cline: reserveringspagina versimpelen
11 nov	Personeelspagina's (fase 1–4)	Menu op telefoon (PR #57), overzicht op telefoon (PR #58), plattegrond op telefoon (PR #59), invoerformulier + /reservering/ruimte (PR #60); 614 → 650 tests	
Fasenplan voor Cline: personeelspagina's
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
Annuleer-omweg (gevonden en opgelost 10 nov, gemerged met PR #37): het reserverings-id is ook de annuleerlink van de gast (/annuleren/<id>, zonder inlog). De plattegrond toonde dat id, zodat een medewerker toch kon verwijderen. Nu staat op de plattegrond alleen een kenmerk (HMAC met SECRET_KEY, functie _kenmerk in web.py) en stuurt /plattegrond/toewijzen datum + kenmerk in plaats van reservering_id. Annuleerlinks in al verstuurde mails blijven werken; geen migratie. Let op: een SECRET_KEY-rotatie verandert de kenmerken (alleen een open plattegrond moet dan herladen), en na de deploy moet een al geopende plattegrond één keer herladen. Sinds de merge kunnen medewerkers een account krijgen.
Opruimen in de repo (gezien op main 164190c, 11 nov): "Fasenplan voor Cline personeel.md", "Fasenplan voor Cline reserveringspagina.md" en ontwerp/reserveren-voorbeeld.html zijn met PR #59 in main gekomen (en in PR #60 gewijzigd). Planbestanden horen in C:\Codes\WPL-plan\. Voorstel: verplaatsen met git mv naar buiten de repo via een eigen branch (bijv. chore/planbestanden-eruit) en ontwerp/ en "Fasenplan*" in .gitignore.
.neon (gecontroleerd 11 nov): bevat alleen orgId, projectId en branch van Neon, geen wachtwoord, key of connection string (geheimenscan: 0). Geen geheim, wel interne ID's; mag blijven of kan in .gitignore met git rm --cached .neon.
Kan hierna (uit de plannen van 10–11 nov, nog niet ingepland): de grondslag in de privacyverklaring noemen; een bericht "dag vol, eerstvolgende plek: ..."; Engelse teksten laten nalezen door een moedertaalspreker; de vaste balk onderaan op een echte iPhone (Safari, met schermtoetsenbord) controleren — dat is een HYPOTHESE, niet getest.
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
Gebruik het commitblok uit het fasenplan (git add van alleen de fasebestanden) in plaats van git add -A met de uitvoer van git status als commitbericht; zo kwamen planbestanden en ontwerp/ in main (commits 973a695 en 8475e56) en zeggen de commitberichten niets.
Bijlage. Herbruikbare alleen-lezen commando's (Git Bash)
Draai vanuit de repo-root; gebruik git --no-pager en bij geheimenscans altijd een teller-pipe.

git --no-pager status -sb
git --no-pager branch -a -vv
git --no-pager log --oneline -8 main
git ls-files '*.py' | wc -l                       # eerst: hoeveel bestanden tellen mee?
git ls-files '*.py' | xargs grep -n -E "PATROON"   # zoek alleen in tracked .py-bestanden
grep -c -i -E "PATROON" bestand                    # telregel (een 0 kan een kapotte pipe zijn)
python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"