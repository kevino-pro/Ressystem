# Fasenplan voor Cline: stap 1 en 2

Oct 29, 2026 · @Kevin Ochtman

Vijf fasen met code (0 t/m 4) en één handmatige fase (5), gebaseerd op het [plan voor stap 1 en 2](https://claude.ai/artifact/H1TYR5YqSUBwMmuES6woo8). Alle wijzigingen hieronder heb ik vooraf op een kopie van je code uitgeprobeerd: 51 tests groen op SQLite, en de nieuwe Postgres-tests groen op Postgres 16. Je code op je laptop is niet aangeraakt en staat nog op `main` (`be9ed46`).

## Zo werkt elke fase

Elke fase loopt in dezelfde vier stappen. Cline wijzigt alleen bestanden en draait tests; alle git-commando's doe jij zelf in Git Bash, zoals je werkafspraken voorschrijven.

1. **Jij (Git Bash):** branch maken vanaf een bijgewerkte `main`.
2. **Cline:** de prompt van die fase plakken. Auto-approve blijft uit; keur elke bestandswijziging en elk commando apart goed.
3. **Opus in VS Code:** de controleprompt hieronder plakken, met de extra controlepunten van die fase erachter. Opus geeft GO of NO-GO.
4. **Jij (Git Bash):** alleen bij GO committen, pushen, PR openen, wachten op groene CI, mergen, wachten op groene `verify-render`. Dan pas de volgende fase.

**Bij NO-GO:** geef Opus' bevindingen terug aan Cline in dezelfde chat ("Opus vond: …, los alleen dit op"), en laat Opus daarna opnieuw controleren. Na twee keer NO-GO: stop en vraag het mij of Opus om de fix zelf te schrijven.

**Regels voor alle fasen:**

- Cline opent nooit `.env`, `.neon`, `.vscode/`, `*.db` of iets onder `venv/`, `Python/` en `node_modules/`. Alles wat Cline leest gaat naar DeepSeek.
- Je bestanden gebruiken Windows-regeleinden (CRLF). Laat Cline die zo houden; een diff waarin een heel bestand verandert, is bijna altijd een regeleinde-probleem.
- Cline wijzigt alleen de bestanden die de fase noemt. Een extra bestand in `git status` is een NO-GO.

### Controleprompt voor Opus (elke fase)

```text
Context: Ik werk aan de Flask-app in C:\Codes\WPL. Cline heeft zojuist fase <N> uitgevoerd
volgens een vast plan. Jij bent de controleur; je wijzigt zelf niets.

Taak (alleen lezen):
1. Draai in Git Bash: git --no-pager status -sb  en  git --no-pager diff --stat
   en  git --no-pager diff
2. Lees de gewijzigde en nieuwe bestanden volledig.
3. Draai in Git Bash: python -m unittest discover -s tests -v
4. Controleer de algemene punten hieronder en de extra punten van deze fase.

Algemene punten:
- Alleen de bestanden uit de fase zijn gewijzigd of nieuw; geen andere.
- Geen hele-bestand-diffs door regeleinden (CRLF moet CRLF blijven).
- Geen geheimen, echte URL's, wachtwoorden of klantgegevens in de diff.
- Alle tests slagen; het aantal tests is gestegen met het verwachte aantal.
- Code past bij de stijl van het project (Nederlandse namen, bestaande patronen
  zoals _guard en de TestConfig-klassen).
- Niets aan wat de fase niet vraagt (geen extra refactors, geen nieuwe packages).

Rapporteer alleen: GO of NO-GO, dan per punt OK of een concrete bevinding met
bestand:regel. Geen codevoorstellen tenzij bij NO-GO, en dan de kleinste fix.

Beperkingen: niets wijzigen, niets committen, .env/.neon/*.db niet openen,
geen databaseverbinding buiten de tests.

Extra punten voor deze fase:
<plak hier de controlepunten van de fase>
```

## Fase 0: nulmeting (alleen lezen)

Doel: vastleggen dat alles groen is vóór de eerste wijziging, zodat een rode test later aan een fase toe te wijzen is. Verwacht: **41 tests, OK**.

**Jij (Git Bash):**

```bash
cd /c/Codes/WPL
git --no-pager status -sb      # verwacht: ## main...origin/main, alleen ?? OVERDRACHT.md
git pull
```

**Cline-prompt:**

```text
Context: Flask-app in C:\Codes\WPL, virtuele omgeving in venv/. Dit is een nulmeting
voordat er code verandert.

Taak (alleen lezen, Git Bash):
  source venv/Scripts/activate
  python --version
  python -m unittest discover -s tests -v

Rapporteer alleen: de Python-versie, het aantal tests, en OK of de namen van
falende tests met het fouttype.

Beperkingen: geen bestanden wijzigen of aanmaken, geen git-commando's, .env/.neon/*.db
niet openen, geen pip install.

Wat je mij meldt: Python-versie, aantal tests, OK/FAILED.
```

**Opus:** niet nodig voor fase 0. Meldt Cline iets anders dan 41 tests OK, stop dan en meld het mij eerst.

## Fase 1: XSS in het overzicht en uitlogknop

Resultaat: een gastnaam kan geen JavaScript meer uitvoeren in het personeelsoverzicht, en personeel kan uitloggen. Verwacht na afloop: **43 tests, OK**. Bestanden: `templates/overzicht.html`, `app/routes/web.py`, nieuw `tests/test_overzicht_xss.py`.

**Jij (Git Bash):**

```bash
git switch main && git pull
git switch -c fix/xss-overzicht
```

**Cline-prompt:**

````text
Context: Flask-app in C:\Codes\WPL. In templates/overzicht.html staat de gastnaam
({{ r.naam }}) binnen een JavaScript-string in een onsubmit-attribuut. Jinja escapet ' naar
&#39;, maar de browser decodeert dat terug, dus een naam als x'+(code)+' voert code uit
(stored XSS). Daarnaast is er geen uitlogknop; de route /logout bestaat wel (GET).

Taak:
1. templates/overzicht.html: vervang in het verwijder-formulier de regel met
   onsubmit="return confirm('Weet je zeker ... {{ r.naam }} wilt verwijderen?');"
   door deze twee regels (zelfde inspringing):
     data-bericht="Weet je zeker dat je deze reservering van {{ r.naam }} wilt verwijderen?"
     onsubmit="return confirm(this.dataset.bericht);"
2. templates/overzicht.html: vervang bovenaan het losse <a href="/">...Terug naar
   reserveringsformulier</a>-element door:
     <div class="flex items-center gap-4">
         <a href="/" class="inline-flex items-center text-xs font-medium text-slate-600 hover:text-slate-900 transition">
             ← Terug naar reserveringsformulier
         </a>
         <form action="/logout" method="POST" class="inline">
             <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
             <button type="submit" class="text-xs font-medium text-red-600 hover:text-red-800 transition">Uitloggen</button>
         </form>
     </div>
3. app/routes/web.py: verander @web_bp.route('/logout') in
   @web_bp.route('/logout', methods=['POST']). Verder niets in dit bestand.
4. Maak tests/test_overzicht_xss.py met exact de inhoud uit het blok hieronder.
5. Git Bash: python -m unittest discover -s tests -v

Inhoud tests/test_overzicht_xss.py:
```python
import re
import unittest

from app import create_app
from app.config import Config
from app.database import get_db, metadata, reserveringen, verwerk_reservering
from app.security import reset_rate_limits

KWAADAARDIGE_NAAM = "x'+(window.GEHACKT=1)+'"


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    CSRF_ENABLED = False


class OverzichtXssTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)
        with self.app.app_context():
            conn = get_db()
            metadata.create_all(conn)
            conn.commit()
            with conn.begin():
                conn.execute(reserveringen.delete())
            verwerk_reservering(conn, 10, KWAADAARDIGE_NAAM, "a@example.com", "0612345678",
                                "2030-01-01", "19:00", 2)
        self.client = self.app.test_client()
        with self.client.session_transaction() as sessie:
            sessie["ingelogd"] = True

    def test_naam_staat_niet_in_javascript(self):
        html = self.client.get("/overzicht").get_data(as_text=True)
        handlers = re.findall(r'onsubmit="([^"]*)"', html)
        self.assertTrue(handlers)
        for handler in handlers:
            self.assertEqual(handler, "return confirm(this.dataset.bericht);")
        self.assertNotIn("GEHACKT=1)+'", html)  # de ruwe ' mag nergens onge-escaped staan

    def test_uitloggen_alleen_via_post(self):
        self.assertEqual(self.client.get("/logout").status_code, 405)
        antwoord = self.client.post("/logout")
        self.assertEqual(antwoord.status_code, 302)
        with self.client.session_transaction() as sessie:
            self.assertNotIn("ingelogd", sessie)


if __name__ == "__main__":
    unittest.main()
```

Rapporteer alleen: welke bestanden je wijzigde of aanmaakte, en de testuitslag
(aantal, OK/FAILED).

Beperkingen: alleen deze drie bestanden; behoud CRLF-regeleinden; geen git-commando's;
.env/.neon/*.db niet openen; geen nieuwe packages; geen andere verbeteringen.

Wat je mij meldt: gewijzigde bestanden + testuitslag (verwacht 43 tests, OK).
````

**Extra controlepunten voor Opus:**

```text
- In overzicht.html komt r.naam alleen nog voor in tekst en in data-bericht, nergens
  binnen een onsubmit/onclick of <script>.
- Het verwijder-formulier heeft nog steeds het csrf_token-veld.
- De uitlogknop is een POST-formulier met csrf_token; web.py staat alleen POST toe op /logout.
- Er linkt nergens anders nog een <a href="/logout"> (zoek in templates/).
- Test test_naam_staat_niet_in_javascript faalt als je de oude onsubmit-regel terugzet
  (redeneer dit na; niet echt terugzetten).
```

## Fase 2: retentie-opschoning op Postgres

Resultaat: `purge-retention` werkt ook op Neon, en CI test voortaan op een echte Postgres. Verwacht lokaal: **46 tests, OK (skipped=3)**; de drie Postgres-tests draaien alleen in CI. Bestanden: `app/database.py`, `.github/workflows/ci.yml`, nieuw `tests/test_postgres.py`.

**Jij (Git Bash):**

```bash
git switch main && git pull
git switch -c fix/retentie-postgres
```

**Cline-prompt:**

````text
Context: Flask-app in C:\Codes\WPL. In app/database.py vergelijkt _retentiegrens() de
Text-kolom `datum` met een SQL-timestamp. Op Postgres geeft dat
"operator does not exist: text < timestamp without time zone", dus purge-retention werkt
niet in productie. Oplossing: de grensdatum in Python uitrekenen als 'YYYY-MM-DD'-tekst.

Taak:
1. app/database.py: voeg bovenaan, direct onder `import secrets`, toe:
     from datetime import date, timedelta
2. app/database.py: vervang de hele functie _retentiegrens(conn) door:
     def _retentiegrens():
         """
         Grensdatum voor de bewaartermijn (RETENTIE_DAGEN_AVG) als 'YYYY-MM-DD'-tekst.
         `datum` is een Text-kolom; tekst-met-tekst vergelijken werkt op SQLite en Postgres gelijk,
         en ISO-datums sorteren als tekst in de juiste volgorde.
         """
         retentie_dagen = int(current_app.config['RETENTIE_DAGEN_AVG'])
         return (date.today() - timedelta(days=retentie_dagen)).isoformat()
3. app/database.py: verander in schonen_oude_reserveringen() en in
   tel_of_schoon_oude_reserveringen() de aanroep `_retentiegrens(conn)` in `_retentiegrens()`.
   Verwijder in schonen_oude_reserveringen() de docstring-regel over dialect-specifieke SQL.
   Laat de import van `text` staan (die wordt nog gebruikt voor de advisory lock).
4. .github/workflows/ci.yml: voeg onder `jobs:` een tweede job toe, na unit-tests:

  postgres-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_HOST_AUTH_METHOD: trust
          POSTGRES_DB: wpl_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10
    env:
      TEST_POSTGRES_URL: postgresql://postgres@localhost:5432/wpl_test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - name: Install dependencies
        run: python -m pip install -r requirements.txt
      - name: Run Postgres tests
        run: python -m unittest tests.test_postgres -v

5. Maak tests/test_postgres.py met exact de inhoud uit het blok hieronder.
6. Git Bash: python -m unittest discover -s tests -v

Inhoud tests/test_postgres.py:
```python
"""
Tests die een echte Postgres nodig hebben. Ze draaien alleen als TEST_POSTGRES_URL is gezet
(in CI de job `postgres-tests`); lokaal worden ze overgeslagen.
"""
import os
import unittest
from datetime import date, timedelta

from sqlalchemy import func, insert, select

import app.database as database
from app import create_app
from app.config import Config
from app.database import CapaciteitVolFout, get_db, metadata, reserveringen, verwerk_reservering

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")


class PostgresConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = POSTGRES_URL or "postgresql://niet-gebruikt/db"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    RETENTIE_DAGEN_AVG = 60


@unittest.skipUnless(POSTGRES_URL, "TEST_POSTGRES_URL niet gezet")
class PostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # De engine is proces-breed; een eerdere test kan al een SQLite-engine hebben gemaakt.
        cls._vorige_engine = database._engine
        database._engine = None
        cls.app = create_app(PostgresConfig)

    @classmethod
    def tearDownClass(cls):
        database._engine.dispose()
        database._engine = cls._vorige_engine

    def setUp(self):
        with self.app.app_context():
            conn = get_db()
            metadata.create_all(conn)
            conn.commit()
            with conn.begin():
                conn.execute(reserveringen.delete())
        self.runner = self.app.test_cli_runner()

    def _voeg_toe(self, rid, dagen_geleden):
        datum = (date.today() - timedelta(days=dagen_geleden)).isoformat()
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=rid, naam="N", email="a@example.com", telefoon="0612345678",
                    datum=datum, tijd="18:00", aantal=1))

    def _ids(self):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                return sorted(r[0] for r in conn.execute(select(reserveringen.c.id)))

    def test_purge_telt_op_postgres(self):
        self._voeg_toe("oud", 100)
        self._voeg_toe("nieuw", 1)
        result = self.runner.invoke(args=["purge-retention", "--productie"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("1 reservering", result.output)
        self.assertEqual(self._ids(), ["nieuw", "oud"])

    def test_purge_verwijdert_alleen_oude_op_postgres(self):
        self._voeg_toe("oud", 100)
        self._voeg_toe("nieuw", 1)
        result = self.runner.invoke(args=["purge-retention", "--uitvoeren", "--productie"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self._ids(), ["nieuw"])

    def test_capaciteit_met_advisory_lock(self):
        with self.app.app_context():
            conn = get_db()
            verwerk_reservering(conn, 4, "Jan", "a@example.com", "0612345678", "2030-01-01", "19:00", 3)
            with self.assertRaises(CapaciteitVolFout):
                verwerk_reservering(conn, 4, "Piet", "b@example.com", "0612345678", "2030-01-01", "19:00", 2)
            with conn.begin():
                totaal = conn.execute(select(func.sum(reserveringen.c.aantal))).scalar()
        self.assertEqual(totaal, 3)


if __name__ == "__main__":
    unittest.main()
```

Rapporteer alleen: gewijzigde/nieuwe bestanden en de testuitslag.

Beperkingen: alleen deze drie bestanden; behoud CRLF; geen git-commando's; geen echte
databaseverbinding (de Postgres-tests worden lokaal overgeslagen, dat is de bedoeling);
.env/.neon/*.db niet openen; geen nieuwe packages.

Wat je mij meldt: gewijzigde bestanden + testuitslag (verwacht 46 tests, OK, skipped=3).
````

**Extra controlepunten voor Opus:**

```text
- _retentiegrens() bevat geen SQL en geen dialect-check meer; beide aanroepers zijn aangepast.
- `text` is nog geïmporteerd en wordt gebruikt in verwerk_reservering.
- ci.yml: de bestaande job unit-tests is ongewijzigd; de nieuwe job heeft geen wachtwoord
  of geheim (trust-auth op een wegwerpcontainer) en draait alleen tests.test_postgres.
- YAML-inspringing klopt (postgres-tests op hetzelfde niveau als unit-tests).
- Lokaal: precies 3 skipped tests met reden "TEST_POSTGRES_URL niet gezet".
```

**Na de merge (jij, GitHub):** zodra `CI / postgres-tests` één keer groen is, voeg hem toe als verplichte check in Settings > Rules > Rulesets, naast `CI / unit-tests`.

## Fase 3: ANTHROPIC\_MODEL in Config

Resultaat: de variabele `ANTHROPIC_MODEL` in Render werkt echt, en de standaardmodelnaam staat nog maar op één plek. Verwacht: **48 tests, OK (skipped=3)**. Bestanden: `app/config.py`, `app/services/ai_service.py`, nieuw `tests/test_anthropic_model_config.py`.

**Jij (Git Bash):**

```bash
git switch main && git pull
git switch -c fix/anthropic-model-config
```

**Cline-prompt:**

````text
Context: Flask-app in C:\Codes\WPL. In app/config.py staat ANTHROPIC_MODEL buiten de klasse
Config, dus app.config kent hem niet en ai_service.py valt altijd terug op de hardcoded
modelnaam. De omgevingsvariabele ANTHROPIC_MODEL wordt daardoor genegeerd.

Taak:
1. app/config.py: verwijder bovenaan het blok
     # --- AI SERVICEMODELS ---
     ANTHROPIC_MODEL = os.getenv('ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001')
   (inclusief de lege regel erna).
2. app/config.py: voeg binnen class Config, direct vóór het kopje
   "# 3. BEVEILIGING & DATABASE", dit blok toe (zelfde stijl als de andere kopjes):
     # ==========================================
     # 2b. AI
     # ==========================================
     ANTHROPIC_MODEL = os.getenv('ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001')
3. app/services/ai_service.py: vervang
     model_naam = current_app.config.get('ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001')
   door
     model_naam = current_app.config['ANTHROPIC_MODEL']
4. Maak tests/test_anthropic_model_config.py met exact de inhoud hieronder.
5. Git Bash: python -m unittest discover -s tests -v

Inhoud tests/test_anthropic_model_config.py:
```python
import os
import unittest
from unittest import mock

from app import create_app
from app.config import Config
from app.services import ai_service


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    ANTHROPIC_MODEL = "test-model"


class AnthropicModelConfigTests(unittest.TestCase):
    def test_config_kent_anthropic_model(self):
        self.assertTrue(Config.ANTHROPIC_MODEL)

    def test_ai_service_gebruikt_model_uit_config(self):
        app = create_app(TestConfig)
        nep_client = mock.Mock()
        nep_client.messages.create.return_value = mock.Mock(content=[])
        with app.app_context(), \
                mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "dummy"}), \
                mock.patch.object(ai_service.anthropic, "Anthropic", return_value=nep_client):
            with self.assertRaises(ValueError):  # lege respons -> geen tool_use
                ai_service.verwerk_tekst_met_anthropic("Tafel voor twee morgen om 19:00")
        self.assertEqual(nep_client.messages.create.call_args.kwargs["model"], "test-model")


if __name__ == "__main__":
    unittest.main()
```

Rapporteer alleen: gewijzigde/nieuwe bestanden en de testuitslag.

Beperkingen: alleen deze drie bestanden; behoud CRLF; geen git-commando's; geen echte
Anthropic-aanroep (de test mockt de client); .env niet openen; geen nieuwe packages.

Wat je mij meldt: gewijzigde bestanden + testuitslag (verwacht 48 tests, OK, skipped=3).
````

**Extra controlepunten voor Opus:**

```text
- In de hele app (git ls-files '*.py' | xargs grep -n ANTHROPIC_MODEL) staat de modelnaam
  'claude-haiku-4-5-20251001' nog maar op één plek: app/config.py binnen class Config.
- `import os` in config.py is nog nodig en staat er nog.
- De test gebruikt een dummy-key via mock.patch.dict en roept Anthropic niet echt aan.
- Bestaande tests in test_anthropic_resilience.py zijn ongewijzigd en slagen.
```

## Fase 4: resend-mail-guard en APP\_ENV

Resultaat: `resend-mail` mailt geen productiegast zonder `--productie`, en met `APP_ENV=production` start de app niet meer stil op SQLite. Verwacht: **51 tests, OK (skipped=3)**. Bestanden: `app/__init__.py`, `app/config.py`, `tests/test_cli_beheer.py`, `README.md`.

**Jij (Git Bash):**

```bash
git switch main && git pull
git switch -c fix/resend-mail-productie-guard
```

**Cline-prompt:**

```text
Context: Flask-app in C:\Codes\WPL. Twee besluiten uit OVERDRACHT.md uitvoeren:
(a) `flask resend-mail` krijgt dezelfde --productie-guard als create-admin en purge-retention;
(b) als APP_ENV=production en DATABASE_URL ontbreekt, weigert de app te starten in plaats van
stil terug te vallen op SQLite.

Taak:
1. app/config.py: vervang in class Config de regel
     DATABASE_URL = os.getenv('DATABASE_URL')
   door deze vier regels (de if-not-DATABASE_URL-fallback eronder blijft ongewijzigd):
     # 'production' op Render: dan weigert de app te starten zonder echte DATABASE_URL.
     APP_ENV = os.getenv('APP_ENV', 'development').strip().lower()
     DATABASE_URL = os.getenv('DATABASE_URL')
     DATABASE_URL_IS_DEFAULT = not DATABASE_URL
2. app/__init__.py: voeg in create_app() direct na de RuntimeError over API_KEY/WEBHOOK_API_KEY
   (en vóór init_db_pool) toe:
     if app.config.get('APP_ENV') == 'production' and app.config.get('DATABASE_URL_IS_DEFAULT'):
         raise RuntimeError("APP_ENV=production maar DATABASE_URL ontbreekt; de app valt niet terug op SQLite.")
3. app/__init__.py: maak van het resend-mail-commando:
     @app.cli.command('resend-mail')
     @click.argument('reservering_id')
     @click.option('--productie', is_flag=True, help='Bevestig bewust een niet-SQLite database.')
     def resend_mail_command(reservering_id, productie):
         """(docstring ongewijzigd)"""
         _guard(productie)
         conn = get_db()
         ... (rest ongewijzigd)
4. tests/test_cli_beheer.py:
   a. Voeg bovenaan direct onder `import unittest` toe: from unittest import mock
   b. In test_guard_blokkeert_niet_sqlite_voor_verbinding: verander
        for args in (["create-admin"], ["purge-retention"]):
      in
        for args in (["create-admin"], ["purge-retention"], ["resend-mail", "abc123"]):
   c. Voeg in class BeheerCliTests, direct vóór test_purge_zonder_uitvoeren_wijzigt_niets, toe:

    def test_resend_mail_zonder_productie_verstuurt_niets(self):
        self.app.config["DATABASE_URL"] = "postgresql://gebruiker:geheim@host.example/db"
        with mock.patch("app.stuur_bevestigingsmail_sync") as verstuur:
            result = self.runner.invoke(args=["resend-mail", "abc123"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("--productie", result.output)
        verstuur.assert_not_called()

   d. Voeg een nieuwe klasse toe, VÓÓR het blok `if __name__ == "__main__":` onderaan:

class AppEnvTests(unittest.TestCase):
    def test_productie_zonder_database_url_start_niet(self):
        class ProductieZonderDb(TestConfig):
            APP_ENV = "production"
            DATABASE_URL_IS_DEFAULT = True
        with self.assertRaises(RuntimeError):
            create_app(ProductieZonderDb)

    def test_productie_met_database_url_start_wel(self):
        class ProductieMetDb(TestConfig):
            APP_ENV = "production"
            DATABASE_URL_IS_DEFAULT = False
        create_app(ProductieMetDb)

5. README.md, sectie "## Beheercommando's":
   a. Verander "De app kent twee handmatige beheercommando's" in "De app kent vier handmatige
      beheercommando's".
   b. Voeg na de sectie over purge-retention twee subsecties toe in dezelfde opmaak:
      ### `flask resend-mail`
      - Aanroep: `flask resend-mail <reservering_id> [--productie]`
      - Verstuurt de bevestigingsmail opnieuw (na een [MAIL_FAILED]-logregel).
      - `--productie`: verplicht op elke niet-SQLite database; zonder vlag weigert het commando
        voordat er verbinding wordt gemaakt of gemaild.
      ### `flask init-db`
      - Alleen een lokaal hulpmiddel; maakt het schema en de admin met ADMIN_INITIAL_PASSWORD.
        Productie gebruikt Alembic.
   c. Voeg in de lijst Render Environment Variables een regel toe:
      - `APP_ENV`: `production`. De app weigert dan te starten als `DATABASE_URL` ontbreekt.
6. Git Bash: python -m unittest discover -s tests -v

Rapporteer alleen: gewijzigde bestanden en de testuitslag.

Beperkingen: alleen deze vier bestanden; behoud CRLF; geen git-commando's; .env niet openen
en ook geen APP_ENV in .env of .env.example zetten; geen nieuwe packages.

Wat je mij meldt: gewijzigde bestanden + testuitslag (verwacht 51 tests, OK, skipped=3).
```

**Extra controlepunten voor Opus:**

```text
- _guard(productie) staat als eerste regel in resend_mail_command, vóór get_db().
- De APP_ENV-check staat vóór init_db_pool(app) en gebruikt DATABASE_URL_IS_DEFAULT,
  niet app.config['DATABASE_URL'] (die is al met de SQLite-default gevuld).
- Zonder APP_ENV (lokaal, CI) verandert er niets aan het gedrag.
- De nieuwe tests in test_cli_beheer.py tonen geen 'geheim' of 'host.example' in de output.
- AppEnvTests staat vóór het if __name__ == "__main__"-blok.
- README: vier commando's beschreven, APP_ENV bij de Render-variabelen; verder niets herschreven.
```

**Na de merge:** de code is klaar. Zet `APP_ENV` pas in fase 5 in Render, samen met de andere variabelen.

## Fase 5: Render-sessie en eindcontrole (geen Cline)

Deze fase doe je zelf, omdat hij vol zit met wachtwoorden, connection strings en de API-key. Cline en Opus krijgen alleen statussen en fouttypes te zien, nooit waarden. Volg stap 2b A t/m E uit het [plan voor stap 1 en 2](https://claude.ai/artifact/H1TYR5YqSUBwMmuES6woo8); daar staan `APP_ENV=production`, het opruimen van `ALLOW_PROD_MIGRATE` en de controle `flask purge-retention --productie` al in.

**Opus-eindcontrole** (na stap E, plak je eigen uitkomsten in):

```text
Context: WPL is uitgerold na fase 1 t/m 4 en een handmatige Render-sessie. Ik geef je alleen
uitkomsten, geen geheimen. Jij controleert of fase 5 compleet is; je wijzigt niets.

Mijn uitkomsten (vul in, alleen status/fouttype):
- /health: <200 / anders>
- Render deployment health op main: <groen / rood>
- CI / unit-tests en CI / postgres-tests verplicht in de ruleset: <ja / nee>
- ALLOW_PROD_MIGRATE nog als vaste Render-variabele: <ja / nee>
- create-admin --productie: <aangemaakt / bestaat al / fout: type>
- purge-retention --productie (tellen): <getal / fout: type>
- Testmail: <ontvangen / niet>, restaurantnaam goed: <ja / nee>, annuleerlink https: <ja / nee>
- n8n-test: <in overzicht met juiste datum / fout>, mail: <ja / nee>, geannuleerd: <ja / nee>

Taak (alleen lezen): vergelijk dit met de afvinklijst van stap 2 en lees README.md.
Rapporteer alleen: KLAAR of NIET KLAAR, per punt OK of wat er ontbreekt, en of README
en OVERDRACHT.md nog iets missen.

Beperkingen: niets wijzigen; .env, .neon en *.db niet openen; geen databaseverbinding.
```

**Afsluiten (Cline, optioneel):** laat Cline daarna `OVERDRACHT.md` bijwerken met alleen jouw uitkomsten en de nieuwe variabele `APP_ENV`. Geef in die prompt de uitkomsten letterlijk mee en verbied Cline andere bestanden te openen.

Na fase 5 is stap 1 en 2 af en kun je verder met stap 3: de reserveringsregels aan de serverkant.
