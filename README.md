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
- `API_KEY`: geheim voor de webhook-header `X-API-Key`; stel dezelfde waarde in n8n in. `WEBHOOK_API_KEY` blijft tijdelijk ondersteund als legacy alias.
- `ANTHROPIC_API_KEY`: Anthropic API key.
- `SECRET_KEY`: willekeurige, sterke Flask secret.
- `ADMIN_INITIAL_PASSWORD`: initieel adminwachtwoord.
- `FLASK_DEBUG`: `False`.
- SMTP-variabelen indien e-mailverzending is ingeschakeld: `SMTP_SERVER`, `SMTP_PORT`, `VERZENDER_EMAIL` en `VERZENDER_WACHTWOORD`.

Zet `ALLOW_PROD_MIGRATE` niet als permanente Render- of `.env`-variabele; de Build Command beperkt de opt-in tot het Alembic-commando. Gebruik op Render voor `MIGRATION_DATABASE_URL` altijd de directe URL. De `.env.example` bevat lokale SQLite-defaults; vervang de twee databasewaarden in Render door de passende Neon-URLs.

`flask init-db` is alleen een handmatig lokaal hulpprogramma. Productieschemawijzigingen verlopen uitsluitend via Alembic.

## CI, Render health en branch protection

De `CI`-workflow draait `unittest` bij pull requests naar `main`. De `Render deployment health`-workflow draait na pushes naar `main`, wacht op de Render-deploy voor exact die commit, faalt bij een mislukte deploy en vraagt daarna de health endpoint op.

Configureer in GitHub repository settings:

- Repository **Variables**: `RENDER_SERVICE_ID` en `RENDER_HEALTH_URL` (bijvoorbeeld `https://ressystem.onrender.com/health`).
- Repository **Secrets**: `RENDER_API_KEY` (Render API key met alleen de benodigde service-read toegang).
- Ga naar **Settings > Rules > Rulesets** en maak een actieve branch ruleset die alleen op `main` target. Vereis een pull request om te mergen, voeg `CI / unit-tests` toe als required status check, blokkeer force pushes en laat de bypass-lijst leeg. Dit is de server-side instelling die directe pushes blokkeert; een workflow alleen kan dat niet afdwingen.

De keep-alive workflow gebruikt dezelfde `RENDER_HEALTH_URL` repository variable. De deploy-check vereist de Render API key en service ID; zonder die configuratie faalt hij expliciet in plaats van een deployment stilzwijgend over te slaan.
