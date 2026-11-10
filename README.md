# Ressystem

Flask-reserveringssysteem met Alembic-schemabeheer en Neon PostgreSQL.

## Render deployment

Configureer de Render Web Service met:

- **Build Command:** `pip install -r requirements.txt && ALLOW_PROD_MIGRATE=1 alembic upgrade head`
- **Start Command:** `gunicorn wsgi:app`

De build voert Alembic eenmaal per deploy uit; Gunicorn-workers initialiseren het schema niet. Houd schemawijzigingen compatibel met de codeversie die tijdens een deploy nog actief kan zijn.

Stel deze Render Environment Variables in:

- `DATABASE_URL`: Neon pooled connection string; de host bevat `-pooler`. Alleen voor de runtime-app.
- `MIGRATION_DATABASE_URL`: Neon direct connection string; de host bevat geen `-pooler`. Alembic gebruikt deze tijdens de build.
- `APP_ENV`: `production`. De app weigert dan te starten als `DATABASE_URL` ontbreekt.
- `RESTAURANT_CONFIG`: pad naar het restaurantbestand, bijvoorbeeld `restaurants/wpl.toml`. Verplicht als `APP_ENV=production`.
- `API_KEY`: geheim voor de webhook-header `X-API-Key`; stel dezelfde waarde in n8n in. `WEBHOOK_API_KEY` blijft tijdelijk ondersteund als legacy alias.
- `ANTHROPIC_API_KEY`: Anthropic API key.
- `SECRET_KEY`: willekeurige, sterke Flask secret.
- `ADMIN_INITIAL_PASSWORD`: initieel adminwachtwoord.
- `FLASK_DEBUG`: `False`.
- SMTP-variabelen indien e-mailverzending is ingeschakeld: `SMTP_SERVER`, `SMTP_PORT`, `VERZENDER_EMAIL` en `VERZENDER_WACHTWOORD`.

Zet `ALLOW_PROD_MIGRATE` niet als permanente Render- of `.env`-variabele; de Build Command beperkt de opt-in tot het Alembic-commando. Gebruik op Render voor `MIGRATION_DATABASE_URL` altijd de directe URL. De `.env.example` bevat lokale SQLite-defaults; vervang de twee databasewaarden in Render door de passende Neon-URLs.

`flask init-db` is alleen een handmatig lokaal hulpprogramma. Productieschemawijzigingen verlopen uitsluitend via Alembic.

## Restaurantconfiguratie

Elke installatie leest zijn openingstijden en boekingsregels uit één TOML-bestand in
`restaurants/`. Welk bestand, bepaalt de omgevingsvariabele `RESTAURANT_CONFIG`
(bijvoorbeeld `restaurants/wpl.toml`). Zonder die variabele gebruikt de app
`restaurants/voorbeeld.toml`, maar met `APP_ENV=production` weigert de app dan te starten.

Voor een nieuw restaurant: kopieer `restaurants/voorbeeld.toml` naar `restaurants/<naam>.toml`,
pas de waarden aan en zet `RESTAURANT_CONFIG` in de Render-service van dat restaurant.

Alle velden staan onder `[reserveringen]`:

| Veld | Betekenis |
|---|---|
| `tijdzone` | Bijvoorbeeld `Europe/Amsterdam`. Bepaalt wat "vandaag" is, ook voor de AI. |
| `slot_minuten` | Stapgrootte van de tijden: 5, 10, 15, 20, 30 of 60. |
| `zitduur_minuten` | Hoe lang een reservering een tafel bezet (15 tot 480). |
| `max_gasten_tegelijk` | Hoeveel gasten er tegelijk mogen zitten, over de hele zitduur geteld. |
| `max_personen_per_boeking` | Grootste groep die online mag boeken (maximaal 20). |
| `min_minuten_vooraf` | Hoe kort van tevoren je nog mag boeken. |
| `max_dagen_vooruit` | Hoe ver vooruit je mag boeken. |
| `sluitingsdagen` | Losse datums waarop het restaurant dicht is, bijvoorbeeld `[2026-12-25, 2027-01-01]`. |
| `knop_minuten` | Optioneel. Om de hoeveel minuten het formulier een tijdknop toont (bijvoorbeeld 30). Een veelvoud van `slot_minuten`; zonder dit veld gelijk aan `slot_minuten`. |
| `diner_vanaf` | Optioneel. Vanaf deze tijd staan de tijdknoppen onder "Diner", ervoor onder "Lunch", bijvoorbeeld `"16:00"`. Zonder dit veld: geen kopjes. |
| `kinderstoelen` | Optioneel. Hoeveel kinderstoelen het restaurant heeft. Het formulier vraagt er dan naar, en online kan niemand meer kinderstoelen tegelijk reserveren dan er zijn. Zonder dit veld (of 0) vraagt het formulier er niet naar. |
| `[reserveringen.openingstijden]` | Per weekdag (`maandag` t/m `zondag`) een lijst vensters, bijvoorbeeld `dinsdag = [["17:00", "20:30"]]`. Een lege lijst of een ontbrekende dag betekent gesloten. Het venster geeft aan wanneer een reservering mag beginnen; de tweede tijd is dus de laatste begintijd, niet de sluitingstijd. Beide tijden moeten op een slotgrens vallen. |

De test `test_alle_restaurantbestanden_zijn_geldig` laadt in CI elk bestand in `restaurants/`,
dus een tikfout in een restaurantbestand maakt de build rood voordat het live gaat.

## Huisstijl

Elke installatie kan er anders uitzien. In het restaurantbestand staat een optionele sectie:

```toml
[huisstijl]
accentkleur = "#d9a441"                          # knoppen, gekozen tijden en de naam; alleen #rrggbb
ondertitel = "Schoolstraat 35, Den Haag"         # regel onder de naam
achtergrond = "restaurants/wpl/achtergrond.webp" # pad binnen static/; weglaten = warme donkere gloed
```

Zet de foto in `static/restaurants/<naam>/`. Gebruik WebP of JPG, ongeveer 1600 pixels breed en
onder de 300 KB; de site legt er zelf een donkere laag over zodat de tekst leesbaar blijft. Staat de
foto er niet, dan start de app niet en noemt hij het ontbrekende bestand. De opmaak zelf staat in
`static/css/huisstijl.css` en is voor elk restaurant gelijk.

## Plattegrond voor het personeel

Een restaurantbestand kan een sectie `[plattegrond]` hebben. Dan krijgt het personeel na inloggen een plattegrond waarop het reserveringen aan tafels kan toewijzen. Zonder die sectie werkt alles zoals voorheen en is er geen plattegrond. Gasten zien de plattegrond nooit.

- **Raster:** `kolommen` en `rijen` bepalen de grootte. Elke tafel en elk element staat op `kolom` en `rij` (vanaf 0, linksboven) met een `breedte` en `hoogte` in hokjes (standaard 1).
- **Tafels:** `nummer` (letters en cijfers, zoals het personeel het zegt), `stoelen` (1 tot 20) en optioneel `vorm = "rond"`.
- **Elementen:** vaste dingen zonder stoelen, zoals de bar, een paal of de ingang. Alleen voor de tekening.
- **Combinaties:** groepen tafels die vaak aan elkaar geschoven worden. Elke tafel mag in hoogstens één groep staan.
- **Controle:** tafels en elementen mogen niet overlappen of buiten het raster vallen. Een fout laat de app niet starten; de tests controleren elk bestand in `restaurants/`.

## Beheercommando's

De app kent vijf handmatige beheercommando's, aan te roepen via `flask <naam>`. Voer ze uit vanuit een terminal waar de databaseconfiguratie van de app is ingesteld.

### `flask create-admin`

Maakt een personeelsaccount aan.

- **Aanroep:** `flask create-admin [--gebruikersnaam <naam>] [--productie]`
- **`--gebruikersnaam`:** naam van het aan te maken account (standaard `admin`).
- **`--productie`:** bevestigt bewust een niet-SQLite database; zonder deze vlag weigert het commando op elke andere backend.
- **Wachtwoord:** het accountwachtwoord wordt alleen interactief opgevraagd, met verborgen invoer en bevestiging (minimaal 12 tekens). Geef het nooit mee als argument of via een omgevingsvariabele.
- **Gedrag:** bestaat de gebruikersnaam al, dan verandert er niets en stopt het commando met "bestaat al" (exitcode 1); een bestaand account wordt nooit overschreven.

### `flask purge-retention`

Telt of verwijdert reserveringen die buiten de bewaartermijn (`RETENTIE_DAGEN_AVG`) vallen.

- **Aanroep:** `flask purge-retention [--uitvoeren] [--productie]`
- **`--uitvoeren`:** verwijdert de gevonden reserveringen. Zonder deze vlag wordt er alleen geteld en verandert er niets.
- **`--productie`:** bevestigt bewust een niet-SQLite database; zonder deze vlag weigert het commando op elke andere backend. Let op: `--productie` maakt ook bij het alleen tellen een echte databaseverbinding.
- **Waarschuwing:** met `--uitvoeren` worden gegevens **definitief** verwijderd; deze actie is niet terug te draaien.

### Dagelijks automatisch opschonen

Een geplande taak in GitHub Actions (`.github/workflows/opschonen.yml`) roept elke nacht `POST /beheer/opschonen` aan. Die route doet hetzelfde als `flask purge-retention --uitvoeren`: reserveringen buiten de bewaartermijn worden definitief verwijderd, samen met hun tafeltoewijzingen.

- **Render:** zet `BEHEER_API_KEY` op een willekeurige waarde van minstens 32 tekens. Zonder (of met een kortere) sleutel bestaat de route niet (404).
- **GitHub:** zet dezelfde waarde als repository secret `BEHEER_API_KEY`, en het adres van de app (zonder `/health`) als repository variable `RENDER_APP_URL`.
- **Controle:** start de workflow een keer met de hand (Actions, "Dagelijks opschonen (AVG)", Run workflow). De uitvoer toont `{"status": "succes", "verwijderd": N}`.
- **Beveiliging:** de route gebruikt een eigen sleutel in de header `X-Beheer-Key`, los van de n8n-sleutel, en weigert na tien pogingen per uur.

### `flask dubbele-reserveringen`

Toont toekomstige reserveringen die dubbel lijken: zelfde datum en tijd, en hetzelfde e-mailadres of telefoonnummer. Alleen dezelfde naam telt niet als dubbel.

- **Aanroep:** `flask dubbele-reserveringen [--productie]`
- **Alleen lezen:** het commando verwijdert niets. Per reservering toont het het id, de voornaam, de eerste drie tekens van het e-mailadres en de aanmaaktijd.
- **`--productie`:** bevestigt bewust een niet-SQLite database; zonder deze vlag weigert het commando op elke andere backend.
- **Opruimen:** handmatig via het personeelsoverzicht. Houd per groep de oudste, want die gast heeft de bevestigingsmail met de annuleerlink.

### `flask resend-mail`

Verstuurt de bevestigingsmail opnieuw voor een bestaande reservering.

- **Aanroep:** `flask resend-mail <reservering_id> [--productie]`
- **Gebruik:** na een `[MAIL_FAILED]`-logregel, om dezelfde mail nog eens te proberen.
- **`--productie`:** verplicht op elke niet-SQLite database; zonder deze vlag weigert het commando voordat er verbinding wordt gemaakt of gemaild.

### `flask init-db`

- **Aanroep:** `flask init-db [--productie]`
- **Gebruik:** alleen een lokaal hulpmiddel; maakt het schema en de admin met `ADMIN_INITIAL_PASSWORD`. Productie gebruikt Alembic.

## CI, Render health en branch protection

De `CI`-workflow draait `unittest` bij pull requests naar `main`. De `Render deployment health`-workflow draait na pushes naar `main`, wacht op de Render-deploy voor exact die commit, faalt bij een mislukte deploy en vraagt daarna de health endpoint op.

Configureer in GitHub repository settings:

- Repository **Variables**: `RENDER_SERVICE_ID` en `RENDER_HEALTH_URL` (bijvoorbeeld `https://ressystem.onrender.com/health`).
- Repository **Secrets**: `RENDER_API_KEY` (Render API key met alleen de benodigde service-read toegang).
- Ga naar **Settings > Rules > Rulesets** en maak een actieve branch ruleset die alleen op `main` target. Vereis een pull request om te mergen, voeg `CI / unit-tests` toe als required status check, blokkeer force pushes en laat de bypass-lijst leeg. Dit is de server-side instelling die directe pushes blokkeert; een workflow alleen kan dat niet afdwingen.

De keep-alive workflow gebruikt dezelfde `RENDER_HEALTH_URL` repository variable. De deploy-check vereist de Render API key en service ID; zonder die configuratie faalt hij expliciet in plaats van een deployment stilzwijgend over te slaan. De deploy-check toont bij een afwijkende Render-API-respons de HTTP-status en de respons zelf: `401`/`403` betekent een ongeldige `RENDER_API_KEY`, `404` een ongeldige `RENDER_SERVICE_ID`.

Let op: GitHub voert `schedule`-crons best-effort uit en kan runs uren uitstellen. Reken er dus niet op dat de keep-alive workflow Neon permanent wakker houdt; Neon suspendt al na circa vijf minuten inactiviteit, dus een interval van tien minuten kan dat per definitie niet verhullen.

## Diagnose bij een storing

`GET /health` doet een echte `SELECT 1` en antwoordt met **503** (`{"status":"fout","bericht":"Database niet bereikbaar"}`) zodra die query een `OperationalError` geeft.

- **503 betekent niet dat `DATABASE_URL` ontbreekt.** Zonder `DATABASE_URL` valt `app/config.py` terug op `sqlite:///reserveringen.db`, maakt SQLite dat bestand zelf aan en antwoordt `/health` met **200**. Een 503 betekent dus dat `DATABASE_URL` wél is ingesteld, maar dat de verbinding wordt geweigerd: verkeerd of gereset wachtwoord, verkeerde host, of een verwijderde of gesuspendeerde Neon-branch.
- **De oorzaak staat in het Render-logboek.** De healthcheck logt bij een 503 de driverklasse en de SQLSTATE, en bewust **niet** de melding van de driver: die kan host, gebruikersnaam en een connectiestring bevatten. Zoek op `Healthcheck: database niet bereikbaar`. `28P01` betekent een onjuist wachtwoord, `3D000` een database die niet bestaat en `08006` een verbindingsfout.
- **Test een connectiestring nooit door de variabele te echoën.** Gebruik de Render Shell, waar `DATABASE_URL` al in de omgeving staat.

| Symptoom | Waarschijnlijke oorzaak |
| --- | --- |
| `/health` geeft 503, `/` geeft 200 | `DATABASE_URL` is ingesteld maar onbereikbaar (wachtwoord, host of branch) |
| Build faalt met `Migraties weigeren een pooler-host` | `MIGRATION_DATABASE_URL` ontbreekt, waardoor Alembic terugvalt op de gepoolde `DATABASE_URL` |
| Build faalt met `Database-URL ontbreekt` | Noch `MIGRATION_DATABASE_URL` noch `DATABASE_URL` is tijdens de build beschikbaar |
| `Render deployment health` faalt binnen enkele seconden | De Render API gaf een non-2xx; zie de gelogde HTTP-status en respons in de workflowstap |
