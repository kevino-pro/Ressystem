# Fasenplan voor Cline: personeelsaccounts

Opgesteld 8 nov 2026 door Claude (Sonnet 5.5). Voor Cline (uitvoerder), Opus in VS Code (controleur) en de gebruiker (alle git-handelingen). Geen geheimen in dit bestand. HYPOTHESE = niet bewezen; BEWIJS = gezien in code of testuitslag.

## 1. Doel en besluiten

Nu kan alleen de eigenaar inloggen. Na dit plan kan een **beheerder** op de website accounts voor personeel aanmaken, aan- en uitzetten en een nieuw wachtwoord instellen, en kan iedereen zijn eigen wachtwoord wijzigen.

Besluiten (8 nov, akkoord van de gebruiker op de rollen):

- Twee rollen: `beheerder` (beheert accounts, ziet ook reserveringen en plattegrond) en `medewerker` (alleen reserveringen en plattegrond).
- Elke medewerker krijgt een eigen account. Accounts worden **uitgezet, nooit verwijderd**.
- Rol, `actief` en wachtwoord worden bij **elk verzoek** uit de database gelezen. Een uitgezet account of een nieuw wachtwoord werkt dus direct, ook op een telefoon die nog ingelogd is.
- Alle bestaande accounts worden bij de migratie beheerder (nu kan alleen de eigenaar inloggen).
- De migratie voegt ook de kolom `taal` toe (standaard `nl`), voor het Indonesisch-plan dat hierna komt. In dit plan wordt `taal` nergens gebruikt.

Wat in dit plan zit:

| Fase | Inhoud | Tests daarna |
|---|---|---|
| 1 | Migratie (rol, actief, taal), module `app/toegang.py`, login controleert `actief`, bestaande routes via `@login_vereist` | 274 |
| 2 | Pagina `/accounts` (alleen beheerder): lijst, nieuw account, aan/uit, nieuw wachtwoord instellen | 297 |
| 3 | Pagina `/account`: eigen wachtwoord wijzigen, eigen naam in het menu | 305 |

Wat er bewust **niet** in zit: rol van een bestaand account wijzigen, accounts verwijderen, "wachtwoord vergeten" per mail, tweestapsverificatie, een logboek van wie wat deed, "wijzig je wachtwoord bij de eerste login", de Indonesische vertaling.

Bekende grenzen (geen fout, wel weten):

- Twee beheerders die op exact hetzelfde moment elkaar uitzetten kunnen samen de laatste beheerder wegnemen (de controle draait niet onder een databaselock). Het noodcommando `flask create-admin --productie` blijft bestaan, nu met `--rol` (standaard `beheerder`).
- De limieten op pogingen (rate limits) tellen per proces; Render draait 2 workers.
- Direct na de eerste deploy (fase 1) moet iedereen **één keer opnieuw inloggen**: oude sessies hebben nog geen stempel (zie fase 1).

Getest op een kopie van `main` (463afd0) met SQLite, in drie stappen. **Niet getest op Postgres** (geen Postgres beschikbaar): de migratie gebruikt standaard `ADD COLUMN ... DEFAULT` en `UPDATE`, maar of ze op Neon draait is een HYPOTHESE tot de Render-build van fase 1 groen is. Naar mijn weten blijft bij een mislukte build de vorige deploy live; controleer dat in het Render-dashboard.

Modelkeuze: fase 1 en 2 (rechten, migratie, wachtwoorden) laat je door **Opus** controleren; fase 3 kan ook door Sonnet.

Volgorde: dit plan staat los van de bugfixes B1–B6, maar fase 1 verandert `verwijder_reservering` in `web.py` (ook B2). Wie als tweede merget, doet eerst `git merge main`.

## 2. Werkafspraken voor deze drie fasen

- Eén fase tegelijk. Pas na merge op `main` en een groene Render-deploy begint de volgende fase.
- Repo-bestanden gebruiken CRLF. De bestandsinhoud hieronder staat met gewone regeleinden (LF): schrijf nieuwe bestanden met CRLF en behoud bij bestaande bestanden hun regeleinden. Pas bestaande bestanden aan met de bewerk-tool per blok, niet met `git apply`.
- Cline wijzigt alleen wat het plan noemt, voert geen git uit en maakt geen verbinding met een echte database.
- Opus beoordeelt de diff zelf in de editor (niet op de samenvatting van Cline) en geeft GO of NO-GO.
- Testuitslag altijd met: `python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"`.

## Fase 1 — Rollen in de database en toegangscontrole

Geen nieuw scherm. Wel: de migratie, `app/toegang.py`, en de login en alle personeelsroutes gebruiken de nieuwe controle.

### Branch (Git Bash, door de gebruiker)

```bash
git checkout main
git pull origin main
git checkout -b feat/accounts-fase1
```

### Cline-prompt

```text
Context
Je werkt in C:\Codes\WPL (Flask-app voor reserveringen). Branch feat/accounts-fase1 is actief. Het fasenplan staat in "Fasenplan voor Cline accounts personeel.md"; lees alleen "Fase 1". Deze fase voegt rollen toe aan personeelsaccounts: kolommen rol, actief en taal (Alembic-migratie), een nieuwe module app/toegang.py en een nieuwe login-controle. Er komt nog geen scherm bij.

Taak
1. Maak de nieuwe bestanden precies zoals in "Fase 1 > Bestanden > Nieuwe bestanden".
2. Pas de bestaande bestanden aan zoals in "Fase 1 > Bestanden > Gewijzigde bestanden" (regels met - weg, regels met + erbij). Gebruik je bewerk-tool per blok, niet git apply. Behoud de regeleinden (CRLF) van bestaande bestanden; nieuwe bestanden ook met CRLF.
3. Draai in Git Bash, vanuit de repo-root, met de venv actief:
   python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"

Rapporteer alleen
Wat er gebeurt; verzin niets en verbeter niets.

Beperkingen
- Geen git-commando's (geen add, commit, push, branch).
- Geen echte databaseverbinding: gebruik geen DATABASE_URL, geen Neon, geen .env. De migratietests maken zelf een tijdelijk SQLite-bestand; dat is toegestaan.
- Lees of toon geen .env, .flaskenv, mcp.json of .neon.
- Wijzig geen andere bestanden en voeg niets toe dat niet in het plan staat. Bij twijfel stop je en vraagt het mij.

Wat je mij meldt
- Lijst van nieuwe en gewijzigde bestanden.
- De testuitslag (de regels Ran, OK of FAILED).
- Elke afwijking van het plan, met reden.
```

### Bestanden

#### Nieuwe bestanden (maak ze precies zo aan)

**`app/toegang.py`**

````python
"""
Toegang tot de personeelspagina's: wie is er ingelogd, mag die hier komen, en is het account nog actief.

De sessiecookie bevat alleen de gebruikersnaam en een stempel van het wachtwoord. Rol en `actief`
worden bij elk verzoek uit de database gelezen: een uitgezet account of een gewijzigd wachtwoord
werkt daardoor direct, ook op een telefoon die nog ingelogd is.
"""
import hashlib
import hmac
from functools import wraps

from flask import g, jsonify, redirect, session, url_for

from app.database import get_db, haal_personeel_op

MIN_WACHTWOORD_LENGTE = 12
MAX_WACHTWOORD_LENGTE = 128


def sessie_stempel(wachtwoord_hash):
    """Korte vingerafdruk van de wachtwoordhash; verandert het wachtwoord, dan vervalt de sessie."""
    return hashlib.sha256(wachtwoord_hash.encode('utf-8')).hexdigest()[:16]


def start_sessie(gebruiker):
    """Zet de sessie van een succesvol ingelogde gebruiker (een rij uit de tabel personeel)."""
    session.clear()
    session['ingelogd'] = True
    session['gebruiker'] = gebruiker['gebruikersnaam']
    session['stempel'] = sessie_stempel(gebruiker['wachtwoord_hash'])


def huidige_gebruiker():
    """
    De ingelogde, actieve gebruiker (een rij uit personeel) of None. Eén databasevraag per verzoek.
    Faalt dicht: een sessie zonder gebruikersnaam of stempel, een onbekend of uitgezet account of
    een stempel die niet meer klopt geeft None.
    """
    if 'gebruiker_geladen' in g:
        return g.gebruiker_geladen
    gebruiker = None
    naam = session.get('gebruiker')
    stempel = session.get('stempel')
    if session.get('ingelogd') and isinstance(naam, str) and isinstance(stempel, str):
        rij = haal_personeel_op(get_db(), naam)
        if (rij is not None and rij['actief']
                and hmac.compare_digest(stempel, sessie_stempel(rij['wachtwoord_hash']))):
            gebruiker = rij
    g.gebruiker_geladen = gebruiker
    return gebruiker


def _niet_ingelogd(json_response):
    session.clear()
    if json_response:
        return jsonify({"status": "fout", "bericht": "Je bent uitgelogd. Log opnieuw in."}), 401
    return redirect(url_for('web.login'))


def login_vereist(view=None, *, json_response=False):
    """Alleen voor ingelogd personeel. Te gebruiken als @login_vereist of @login_vereist(json_response=True)."""
    def decorator(functie):
        @wraps(functie)
        def wrapper(*args, **kwargs):
            if huidige_gebruiker() is None:
                return _niet_ingelogd(json_response)
            return functie(*args, **kwargs)
        return wrapper
    return decorator(view) if view is not None else decorator


def beheerder_vereist(view):
    """Alleen voor een ingelogde beheerder; een medewerker krijgt 403."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        gebruiker = huidige_gebruiker()
        if gebruiker is None:
            return _niet_ingelogd(False)
        if gebruiker['rol'] != 'beheerder':
            return "Geen toegang.", 403
        return view(*args, **kwargs)
    return wrapper
````

**`migrations/versions/d4a8b2c6f1e3_personeel_rol_actief_taal.py`**

````python
"""personeel: rol, actief en taal

Revision ID: d4a8b2c6f1e3
Revises: c3f1a7d2e9b4
Create Date: 2026-11-08 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a8b2c6f1e3'
down_revision: Union[str, Sequence[str], None] = 'c3f1a7d2e9b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Drie kolommen erbij; geen gegevens gaan verloren. Alle bestaande accounts worden beheerder:
    tot nu toe kon alleen de eigenaar inloggen. Nieuwe accounts zijn standaard medewerker.
    """
    op.add_column('personeel', sa.Column('rol', sa.Text(), nullable=False, server_default='medewerker'))
    op.add_column('personeel', sa.Column('actief', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('personeel', sa.Column('taal', sa.Text(), nullable=False, server_default='nl'))
    op.execute("UPDATE personeel SET rol = 'beheerder'")


def downgrade() -> None:
    """Verwijdert alleen de drie nieuwe kolommen."""
    op.drop_column('personeel', 'taal')
    op.drop_column('personeel', 'actief')
    op.drop_column('personeel', 'rol')
````

**`tests/hulp.py`**

````python
"""Hulpjes voor tests die als personeel ingelogd moeten zijn."""
from sqlalchemy import delete, func, insert
from werkzeug.security import generate_password_hash

from app.database import get_db, metadata, personeel
from app.toegang import sessie_stempel

WACHTWOORD = "testwachtwoord-123"
_HASH = generate_password_hash(WACHTWOORD)  # eenmalig: hashen is bewust traag


def zet_gebruiker(app, naam="tester", rol="beheerder", actief=True, wachtwoord_hash=None):
    """Maakt (of vervangt) een account in de database van `app`; geeft de wachtwoordhash terug."""
    wachtwoord_hash = wachtwoord_hash or _HASH
    with app.app_context():
        conn = get_db()
        metadata.create_all(conn)
        conn.commit()
        with conn.begin():
            conn.execute(delete(personeel).where(func.lower(personeel.c.gebruikersnaam) == naam.lower()))
            conn.execute(insert(personeel).values(
                gebruikersnaam=naam, wachtwoord_hash=wachtwoord_hash, rol=rol, actief=actief))
    return wachtwoord_hash


def log_in(app, client, naam="tester", rol="beheerder"):
    """Maakt een account aan en zet de sessie van `client` zoals /login dat doet."""
    wachtwoord_hash = zet_gebruiker(app, naam, rol)
    with client.session_transaction() as sessie:
        sessie["ingelogd"] = True
        sessie["gebruiker"] = naam
        sessie["stempel"] = sessie_stempel(wachtwoord_hash)
````

**`tests/test_toegang.py`**

````python
import unittest

from sqlalchemy import select, update

from app import create_app
from app.config import Config
from app.database import get_db, init_db, maak_gebruiker, metadata, personeel
from app.security import reset_rate_limits
from app.toegang import beheerder_vereist, login_vereist
from tests.hulp import WACHTWOORD, log_in, zet_gebruiker


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    ADMIN_INITIAL_PASSWORD = "test-admin-pw-123"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    CSRF_ENABLED = False
    RESTAURANT_CONFIG = "restaurants/wpl.toml"


class ToegangTestBasis(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)
        with self.app.app_context():
            conn = get_db()
            metadata.create_all(conn)
            conn.commit()
            with conn.begin():
                conn.execute(personeel.delete())

        @self.app.route("/_alleen-beheerder")
        @beheerder_vereist
        def alleen_beheerder():
            return "geheim", 200

        @self.app.route("/_alleen-ingelogd")
        @login_vereist
        def alleen_ingelogd():
            return "ok", 200

        self.client = self.app.test_client()

    def rij(self, naam):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                return conn.execute(select(personeel).where(personeel.c.gebruikersnaam == naam)).mappings().first()

    def wijzig(self, naam, **waarden):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(update(personeel).where(personeel.c.gebruikersnaam == naam).values(**waarden))


class LoginTests(ToegangTestBasis):
    def inloggen(self, naam, wachtwoord=WACHTWOORD):
        return self.client.post("/login", data={"gebruikersnaam": naam, "wachtwoord": wachtwoord})

    def test_medewerker_kan_inloggen(self):
        zet_gebruiker(self.app, "anna", rol="medewerker")
        antwoord = self.inloggen("anna")
        self.assertEqual(antwoord.status_code, 302)
        self.assertEqual(antwoord.headers["Location"], "/overzicht")
        with self.client.session_transaction() as sessie:
            self.assertEqual(sessie["gebruiker"], "anna")
            self.assertTrue(sessie["stempel"])
        self.assertEqual(self.client.get("/overzicht").status_code, 200)

    def test_uitgezet_account_kan_niet_inloggen(self):
        zet_gebruiker(self.app, "anna", actief=False)
        antwoord = self.inloggen("anna")
        self.assertEqual(antwoord.status_code, 200)
        self.assertIn("Ongeldige gebruikersnaam of wachtwoord", antwoord.get_data(as_text=True))
        with self.client.session_transaction() as sessie:
            self.assertNotIn("ingelogd", sessie)

    def test_fout_wachtwoord_en_onbekende_naam(self):
        zet_gebruiker(self.app, "anna")
        for naam, wachtwoord in (("anna", "fout"), ("nietbestaand", WACHTWOORD)):
            antwoord = self.inloggen(naam, wachtwoord)
            self.assertEqual(antwoord.status_code, 200)
            self.assertIn("Ongeldige gebruikersnaam of wachtwoord", antwoord.get_data(as_text=True))


class SessieControleTests(ToegangTestBasis):
    def test_zonder_sessie_naar_login(self):
        for pad in ("/overzicht", "/plattegrond", "/_alleen-ingelogd"):
            antwoord = self.client.get(pad)
            self.assertEqual(antwoord.status_code, 302, pad)
            self.assertTrue(antwoord.headers["Location"].endswith("/login"), pad)

    def test_json_route_geeft_401(self):
        antwoord = self.client.post("/plattegrond/toewijzen", json={"reservering_id": "x", "tafels": []})
        self.assertEqual(antwoord.status_code, 401)
        self.assertEqual(antwoord.get_json()["status"], "fout")

    def test_oude_sessie_zonder_gebruiker_of_stempel_geweigerd(self):
        zet_gebruiker(self.app, "tester")
        with self.client.session_transaction() as sessie:
            sessie["ingelogd"] = True
        self.assertEqual(self.client.get("/_alleen-ingelogd").status_code, 302)
        with self.client.session_transaction() as sessie:
            sessie["ingelogd"] = True
            sessie["gebruiker"] = "tester"
        self.assertEqual(self.client.get("/_alleen-ingelogd").status_code, 302)

    def test_sessie_van_onbekend_account_geweigerd(self):
        log_in(self.app, self.client)
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(personeel.delete())
        self.assertEqual(self.client.get("/_alleen-ingelogd").status_code, 302)

    def test_uitgezet_account_wordt_direct_buitengesloten(self):
        log_in(self.app, self.client, naam="anna", rol="medewerker")
        self.assertEqual(self.client.get("/_alleen-ingelogd").status_code, 200)
        self.wijzig("anna", actief=False)
        self.assertEqual(self.client.get("/_alleen-ingelogd").status_code, 302)
        with self.client.session_transaction() as sessie:
            self.assertNotIn("ingelogd", sessie)

    def test_gewijzigd_wachtwoord_beeindigt_oude_sessie(self):
        log_in(self.app, self.client, naam="anna", rol="medewerker")
        self.assertEqual(self.client.get("/_alleen-ingelogd").status_code, 200)
        self.wijzig("anna", wachtwoord_hash="een-ander-wachtwoord")
        self.assertEqual(self.client.get("/_alleen-ingelogd").status_code, 302)

    def test_rol_wordt_elke_keer_uit_de_database_gelezen(self):
        log_in(self.app, self.client, naam="anna", rol="beheerder")
        self.assertEqual(self.client.get("/_alleen-beheerder").status_code, 200)
        self.wijzig("anna", rol="medewerker")
        self.assertEqual(self.client.get("/_alleen-beheerder").status_code, 403)


class RechtenTests(ToegangTestBasis):
    def test_beheerder_komt_binnen(self):
        log_in(self.app, self.client, rol="beheerder")
        antwoord = self.client.get("/_alleen-beheerder")
        self.assertEqual(antwoord.status_code, 200)

    def test_medewerker_krijgt_403_maar_mag_wel_overzicht(self):
        log_in(self.app, self.client, naam="anna", rol="medewerker")
        self.assertEqual(self.client.get("/_alleen-beheerder").status_code, 403)
        self.assertEqual(self.client.get("/overzicht").status_code, 200)

    def test_niet_ingelogd_naar_login_bij_beheerderspagina(self):
        antwoord = self.client.get("/_alleen-beheerder")
        self.assertEqual(antwoord.status_code, 302)


class DatalaagTests(ToegangTestBasis):
    def maak(self, *args, **kwargs):
        with self.app.app_context():
            return maak_gebruiker(get_db(), *args, **kwargs)

    def test_standaardrol_is_medewerker(self):
        self.assertTrue(self.maak("anna", "een-lang-wachtwoord"))
        rij = self.rij("anna")
        self.assertEqual((rij["rol"], rij["actief"], rij["taal"]), ("medewerker", True, "nl"))

    def test_rol_beheerder_kan_worden_meegegeven(self):
        self.maak("chef", "een-lang-wachtwoord", rol="beheerder")
        self.assertEqual(self.rij("chef")["rol"], "beheerder")

    def test_onbekende_rol_geweigerd(self):
        with self.assertRaises(ValueError):
            self.maak("anna", "een-lang-wachtwoord", rol="eigenaar")
        self.assertIsNone(self.rij("anna"))

    def test_naam_bestaat_ongeacht_hoofdletters(self):
        self.assertTrue(self.maak("Anna", "een-lang-wachtwoord"))
        self.assertFalse(self.maak("anna", "een-ander-wachtwoord"))
        self.assertFalse(self.maak("ANNA", "een-ander-wachtwoord"))

    def test_init_db_maakt_admin_als_beheerder(self):
        with self.app.app_context():
            init_db()
        self.assertEqual(self.rij("admin")["rol"], "beheerder")


class CreateAdminRolTests(ToegangTestBasis):
    def test_create_admin_is_standaard_beheerder(self):
        runner = self.app.test_cli_runner()
        wachtwoord = "dummy-wachtwoord-123"
        resultaat = runner.invoke(args=["create-admin", "--gebruikersnaam", "chef"], input=f"{wachtwoord}\n{wachtwoord}\n")
        self.assertEqual(resultaat.exit_code, 0, resultaat.output)
        self.assertEqual(self.rij("chef")["rol"], "beheerder")

    def test_create_admin_met_rol_medewerker(self):
        runner = self.app.test_cli_runner()
        wachtwoord = "dummy-wachtwoord-123"
        resultaat = runner.invoke(
            args=["create-admin", "--gebruikersnaam", "anna", "--rol", "medewerker"], input=f"{wachtwoord}\n{wachtwoord}\n")
        self.assertEqual(resultaat.exit_code, 0, resultaat.output)
        self.assertEqual(self.rij("anna")["rol"], "medewerker")


if __name__ == "__main__":
    unittest.main()
````

#### Gewijzigde bestanden (regels met `-` weg, regels met `+` erbij; de rest is omgeving)

**`app/__init__.py`**

````diff
@@ -7,12 +7,13 @@ from flask import Flask
 from sqlalchemy.exc import SQLAlchemyError
 from werkzeug.middleware.proxy_fix import ProxyFix
 from app.security import csrf_token
+from app.toegang import MIN_WACHTWOORD_LENGTE
 from app.config import Config
 from app.database import (
     init_db_pool, close_db, init_db, get_db, haal_reservering_op,
     controleer_dialect, dialect_uit_config, maak_gebruiker, tel_of_schoon_oude_reserveringen,
     zoek_dubbele_reserveringen,
-    ProductieVlagVereist,
+    ProductieVlagVereist, ROLLEN,
 )
 from app.services.email_service import stuur_bevestigingsmail_sync
 from app.reserveringsregels import laad_regels
@@ -21,8 +22,6 @@ from app.privacy import laad_privacy
 from app.huisstijl import laad_huisstijl
 from app import weergave
 
-MIN_WACHTWOORD_LENGTE = 12
-
 def create_app(config_class=Config):
     # Enige plek die dit configureert: geldt zo voor run.py, wsgi.py (gunicorn) en `flask` CLI-commands.
     # basicConfig is een no-op als er al handlers staan, dus dubbel aanroepen is onschadelijk.
@@ -88,15 +87,16 @@ def create_app(config_class=Config):
 
     @app.cli.command('create-admin')
     @click.option('--gebruikersnaam', default='admin', show_default=True)
+    @click.option('--rol', type=click.Choice(ROLLEN), default='beheerder', show_default=True)
     @click.option('--productie', is_flag=True, help='Bevestig bewust een niet-SQLite database.')
-    def create_admin_command(gebruikersnaam, productie):
-        """Maak een personeelsaccount aan (wachtwoord via verborgen prompt)."""
+    def create_admin_command(gebruikersnaam, rol, productie):
+        """Maak een personeelsaccount aan (wachtwoord via verborgen prompt). Noodoptie; normaal doet een beheerder dit op de website."""
         _guard(productie)
         wachtwoord = click.prompt('Wachtwoord', hide_input=True, confirmation_prompt=True)
         if len(wachtwoord) < MIN_WACHTWOORD_LENGTE:
             raise click.ClickException(f"Wachtwoord moet minstens {MIN_WACHTWOORD_LENGTE} tekens hebben.")
         try:
-            aangemaakt = maak_gebruiker(get_db(), gebruikersnaam, wachtwoord)
+            aangemaakt = maak_gebruiker(get_db(), gebruikersnaam, wachtwoord, rol)
         except SQLAlchemyError:
             app.logger.error("create-admin mislukt door een databasefout.")
             raise click.ClickException("Aanmaken mislukt door een databasefout.")
````

**`app/database.py`**

````diff
@@ -4,8 +4,8 @@ from flask import current_app, g
 from werkzeug.security import generate_password_hash
 from sqlalchemy.engine import make_url
 from sqlalchemy import (
-    MetaData, Table, Column, Text, Integer, DateTime, ForeignKey,
-    create_engine, event, select, insert, delete, func, text,
+    MetaData, Table, Column, Text, Integer, Boolean, DateTime, ForeignKey,
+    create_engine, event, select, insert, delete, func, text, true,
 )
 from app.normalisatie import normaliseer_email, normaliseer_telefoon
 
@@ -40,8 +40,14 @@ personeel = Table(
     Column('id', Integer, primary_key=True, autoincrement=True),
     Column('gebruikersnaam', Text, unique=True, nullable=False),
     Column('wachtwoord_hash', Text, nullable=False),
+    Column('rol', Text, nullable=False, server_default='medewerker'),
+    Column('actief', Boolean, nullable=False, server_default=true()),
+    Column('taal', Text, nullable=False, server_default='nl'),
 )
 
+ROLLEN = ('beheerder', 'medewerker')
+TALEN = ('nl', 'id')
+
 class CapaciteitVolFout(Exception):
     """Geen ruimte meer op het gevraagde tijdslot. `vrij` is het aantal resterende plekken (kan <= 0 zijn)."""
     def __init__(self, vrij):
@@ -392,17 +398,22 @@ def tel_of_schoon_oude_reserveringen(conn, uitvoeren):
             _verwijder_ouder_dan(conn, grens)
     return aantal
 
-def maak_gebruiker(conn, gebruikersnaam, wachtwoord):
-    """Maakt een personeelsaccount aan. Geeft False terug (zonder iets te wijzigen) als de naam al bestaat."""
+def maak_gebruiker(conn, gebruikersnaam, wachtwoord, rol='medewerker'):
+    """
+    Maakt een personeelsaccount aan. Geeft False terug (zonder iets te wijzigen) als de naam al bestaat;
+    hoofdletters tellen daarbij niet mee, zodat 'Anna' en 'anna' niet naast elkaar kunnen bestaan.
+    """
+    if rol not in ROLLEN:
+        raise ValueError(f"Onbekende rol: {rol}")
     with conn.begin():
         bestaat = conn.execute(
-            select(personeel.c.id).where(personeel.c.gebruikersnaam == gebruikersnaam)
+            select(personeel.c.id).where(func.lower(personeel.c.gebruikersnaam) == gebruikersnaam.lower())
         ).first()
         if bestaat:
             return False
         conn.execute(
             insert(personeel).values(
-                gebruikersnaam=gebruikersnaam, wachtwoord_hash=generate_password_hash(wachtwoord)
+                gebruikersnaam=gebruikersnaam, wachtwoord_hash=generate_password_hash(wachtwoord), rol=rol
             )
         )
     return True
@@ -435,7 +446,7 @@ def init_db():
                 raise RuntimeError("Configureer ADMIN_INITIAL_PASSWORD voordat de admin-gebruiker wordt aangemaakt.")
             conn.execute(
                 insert(personeel).values(
-                    gebruikersnaam='admin', wachtwoord_hash=generate_password_hash(initial_pw)
+                    gebruikersnaam='admin', wachtwoord_hash=generate_password_hash(initial_pw), rol='beheerder'
                 )
             )
     schonen_oude_reserveringen()
````

**`app/routes/web.py`**

````diff
@@ -17,6 +17,7 @@ from app.schemas import NAAM_MELDING, TELEFOON_MELDING, ReserveringSchema
 from app.services.email_service import stuur_bevestigingsmail_async
 from app.security import rate_limit, rate_limit_check_adres, valideer_csrf
 from app.reserveringsregels import RegelFout
+from app.toegang import login_vereist, start_sessie
 
 web_bp = Blueprint('web', __name__)
 web_bp.before_request(valideer_csrf)
@@ -132,10 +133,9 @@ def login():
         conn = get_db()
         user = haal_personeel_op(conn, gebruikersnaam)
 
-        if user and check_password_hash(user['wachtwoord_hash'], wachtwoord):
-            session.clear()
-            session['ingelogd'] = True
-            session['gebruiker'] = user['gebruikersnaam']
+        # Een uitgezet account krijgt dezelfde melding als een fout wachtwoord.
+        if user and check_password_hash(user['wachtwoord_hash'], wachtwoord) and user['actief']:
+            start_sessie(user)
             return redirect(url_for('web.overzicht'))
         else:
             foutmelding = "Ongeldige gebruikersnaam of wachtwoord!"
@@ -148,10 +148,8 @@ def logout():
     return redirect(url_for('web.login'))
 
 @web_bp.route('/overzicht')
+@login_vereist
 def overzicht():
-    if not session.get('ingelogd'):
-        return redirect(url_for('web.login'))
-
     regels = current_app.config['REGELS']
     vandaag = regels.nu().date()
     try:
@@ -213,9 +211,8 @@ def _kies_moment(regels, datum_tekst, tijd_tekst):
     return dag.isoformat(), f"{tijdstip:%H:%M}"
 
 @web_bp.route('/plattegrond')
+@login_vereist
 def plattegrond():
-    if not session.get('ingelogd'):
-        return redirect(url_for('web.login'))
     indeling = current_app.config.get('PLATTEGROND')
     if indeling is None:
         abort(404)
@@ -261,9 +258,8 @@ def _tijdknoppen(regels, dag):
     return tijden
 
 @web_bp.route('/plattegrond/toewijzen', methods=['POST'])
+@login_vereist(json_response=True)
 def tafels_toewijzen():
-    if not session.get('ingelogd'):
-        return jsonify({"status": "fout", "bericht": "Je bent uitgelogd. Log opnieuw in."}), 401
     indeling = current_app.config.get('PLATTEGROND')
     if indeling is None:
         abort(404)
@@ -395,10 +391,8 @@ def nieuwe_reservering():
     return jsonify({"status": "succes", "bericht": "Reservering opgeslagen!", "id": unieke_id}), 200
 
 @web_bp.route('/verwijder/<reservering_id>', methods=['POST'])
+@login_vereist
 def verwijder_reservering(reservering_id):
-    if not session.get('ingelogd'):
-        return redirect(url_for('web.login'))
-
     conn = get_db()
     db_verwijder_reservering(conn, reservering_id)
 
````

**`tests/test_overzicht.py`**

````diff
@@ -5,6 +5,7 @@ from app import create_app
 from app.config import Config
 from app.database import get_db, metadata, reserveringen, verwerk_reservering, wijs_tafels_toe
 from app.security import reset_rate_limits
+from tests.hulp import log_in
 
 DAG = "2030-01-01"  # een dinsdag
 
@@ -40,8 +41,7 @@ class OverzichtTests(unittest.TestCase):
             verwerk_reservering(conn, 69, "Eva", "eva@example.com", "0611111111", "2030-01-02", "18:00", 2,
                                 zitduur_minuten=90)
         self.client = self.app.test_client()
-        with self.client.session_transaction() as sessie:
-            sessie["ingelogd"] = True
+        log_in(self.app, self.client)
 
     def pagina(self, query=f"?datum={DAG}"):
         antwoord = self.client.get("/overzicht" + query)
````

**`tests/test_overzicht_xss.py`**

````diff
@@ -5,6 +5,7 @@ from app import create_app
 from app.config import Config
 from app.database import get_db, metadata, reserveringen, verwerk_reservering
 from app.security import reset_rate_limits
+from tests.hulp import log_in
 
 KWAADAARDIGE_NAAM = "x'+(window.GEHACKT=1)+'"
 
@@ -33,8 +34,7 @@ class OverzichtXssTests(unittest.TestCase):
             verwerk_reservering(conn, 10, KWAADAARDIGE_NAAM, "a@example.com", "0612345678",
                                 "2030-01-01", "19:00", 2)
         self.client = self.app.test_client()
-        with self.client.session_transaction() as sessie:
-            sessie["ingelogd"] = True
+        log_in(self.app, self.client)
 
     def test_naam_staat_niet_in_javascript(self):
         html = self.client.get("/overzicht?datum=2030-01-01").get_data(as_text=True)
````

**`tests/test_plattegrond_pagina.py`**

````diff
@@ -6,6 +6,7 @@ from sqlalchemy import insert
 from app import create_app
 from app.config import Config
 from app.database import get_db, init_db, reserveringen, tafeltoewijzingen, wijs_tafels_toe
+from tests.hulp import log_in
 
 KWAADAARDIGE_NAAM = "<script>window.GEHACKT=1</script>"
 
@@ -31,8 +32,7 @@ def maak_client(config, ingelogd=True):
     app = create_app(config)
     client = app.test_client()
     if ingelogd:
-        with client.session_transaction() as sessie:
-            sessie["ingelogd"] = True
+        log_in(app, client)
     return app, client
 
 
````

**`tests/test_plattegrond_stijl.py`**

````diff
@@ -6,6 +6,7 @@ from sqlalchemy import insert
 from app import create_app
 from app.config import Config
 from app.database import get_db, init_db, reserveringen, tafeltoewijzingen, wijs_tafels_toe
+from tests.hulp import log_in
 
 
 class TestConfig(Config):
@@ -24,8 +25,7 @@ class PlattegrondStijlTests(unittest.TestCase):
     def setUp(self):
         self.app = create_app(TestConfig)
         self.client = self.app.test_client()
-        with self.client.session_transaction() as sessie:
-            sessie["ingelogd"] = True
+        log_in(self.app, self.client)
         with self.app.app_context():
             init_db()
             conn = get_db()
````

**`tests/test_tafeltoewijzingen.py`**

````diff
@@ -153,25 +153,50 @@ class TafeltoewijzingTests(unittest.TestCase):
 
 
 class MigratieTests(unittest.TestCase):
+    def _alembic(self, url, *args):
+        omgeving = {**os.environ, "MIGRATION_DATABASE_URL": url}
+        omgeving.pop("ALLOW_PROD_MIGRATE", None)
+        resultaat = subprocess.run(
+            [sys.executable, "-m", "alembic", *args], cwd=PROJECTMAP, env=omgeving,
+            capture_output=True, text=True)
+        self.assertEqual(resultaat.returncode, 0, resultaat.stderr)
+
     def test_upgrade_en_downgrade(self):
         with tempfile.TemporaryDirectory() as map_:
             url = f"sqlite:///{Path(map_) / 'migratie.db'}"
-            omgeving = {**os.environ, "MIGRATION_DATABASE_URL": url}
-            omgeving.pop("ALLOW_PROD_MIGRATE", None)
-
-            def alembic(*args):
-                resultaat = subprocess.run(
-                    [sys.executable, "-m", "alembic", *args], cwd=PROJECTMAP, env=omgeving,
-                    capture_output=True, text=True)
-                self.assertEqual(resultaat.returncode, 0, resultaat.stderr)
-
-            alembic("upgrade", "head")
             engine = create_engine(url)
-            self.assertIn("tafeltoewijzingen", inspect(engine).get_table_names())
-            alembic("downgrade", "-1")
-            self.assertNotIn("tafeltoewijzingen", inspect(engine).get_table_names())
-            self.assertIn("reserveringen", inspect(engine).get_table_names())
-            engine.dispose()
+            try:
+                self._alembic(url, "upgrade", "head")
+                kolommen = {k["name"] for k in inspect(engine).get_columns("personeel")}
+                self.assertTrue({"rol", "actief", "taal"} <= kolommen)
+                self.assertIn("tafeltoewijzingen", inspect(engine).get_table_names())
+
+                self._alembic(url, "downgrade", "c3f1a7d2e9b4")
+                kolommen = {k["name"] for k in inspect(engine).get_columns("personeel")}
+                self.assertFalse({"rol", "actief", "taal"} & kolommen)
+                self.assertIn("tafeltoewijzingen", inspect(engine).get_table_names())
+
+                self._alembic(url, "downgrade", "ba7cbc14b3a2")
+                self.assertNotIn("tafeltoewijzingen", inspect(engine).get_table_names())
+                self.assertIn("reserveringen", inspect(engine).get_table_names())
+            finally:
+                engine.dispose()
+
+    def test_bestaande_accounts_worden_beheerder(self):
+        with tempfile.TemporaryDirectory() as map_:
+            url = f"sqlite:///{Path(map_) / 'migratie.db'}"
+            engine = create_engine(url)
+            try:
+                self._alembic(url, "upgrade", "c3f1a7d2e9b4")
+                with engine.begin() as conn:
+                    conn.exec_driver_sql(
+                        "INSERT INTO personeel (gebruikersnaam, wachtwoord_hash) VALUES ('admin', 'hash')")
+                self._alembic(url, "upgrade", "head")
+                with engine.connect() as conn:
+                    rij = conn.exec_driver_sql("SELECT rol, actief, taal FROM personeel").one()
+                self.assertEqual(tuple(rij), ("beheerder", 1, "nl"))
+            finally:
+                engine.dispose()
 
 
 if __name__ == "__main__":
````


### Controlepunten voor Opus

1. **Faalt dicht.** In `app/toegang.py` geeft `huidige_gebruiker()` alleen een gebruiker terug als de sessie `ingelogd`, een `gebruiker` en een `stempel` heeft, het account bestaat, `actief` is en het stempel klopt. Een sessie met alleen `ingelogd` mag nooit toegang geven.
2. **Alle oude controles weg.** Alleen `app/toegang.py` mag nog `session.get('ingelogd')` bevatten.
   ```bash
   grep -rn --include="*.py" "def huidige_gebruiker" app
   grep -rn --include="*.py" "session.get('ingelogd')" app
   grep -c "login_vereist" app/routes/web.py
   ```
   De bestanden zijn op dit moment nog niet gecommit, dus zoek met `grep -r` in de map `app` (die bevat geen venv) en niet met `git ls-files`. Verwacht: de eerste regel geeft precies één treffer (bewijs dat het zoeken werkt), de tweede precies één treffer in `app/toegang.py`, en de derde `5` voor `web.py` (1 import en 4 decorators: `overzicht`, `plattegrond`, `tafels_toewijzen` met `json_response=True`, `verwijder_reservering`).
3. **Login.** Een uitgezet account krijgt dezelfde melding als een fout wachtwoord, en de wachtwoordcontrole draait ook voor een uitgezet account.
4. **Migratie** `d4a8b2c6f1e3`: `down_revision` is `c3f1a7d2e9b4`; drie kolommen `NOT NULL` met `server_default`; `UPDATE personeel SET rol = 'beheerder'`; de downgrade haalt precies die drie kolommen weg. Er is één enkele head (de test `test_upgrade_en_downgrade` loopt de hele keten).
5. **`maak_gebruiker`** weigert dezelfde naam in andere hoofdletters en een onbekende rol (`ValueError`).
6. **Geen rest.** `MIN_WACHTWOORD_LENGTE` staat nu in `app/toegang.py` en wordt in `app/__init__.py` geïmporteerd; `create-admin` heeft `--rol` (standaard `beheerder`).
7. **Tests.** De bestaande tests loggen in via `tests/hulp.py::log_in`. De migratietest is herschreven omdat `downgrade -1` niet meer naar de tafeltoewijzingen terugvoert; controleer dat hij nog steeds beide migraties test.

### Verwacht

`Ran 274 tests ... OK (skipped=6)` (was 253; het aantal migratietests ging van 1 naar 2, plus 20 nieuwe tests in `test_toegang.py`).

### Voor de merge

- PR maken, CI `unit-tests` moet groen zijn.
- Let op: de CI-job `postgres-tests` draait de migratie **niet**. De echte proef is de Render-build na de merge.

### Na de merge (door de gebruiker)

1. Kijk in het Render-buildlog of de regel `Running upgrade c3f1a7d2e9b4 -> d4a8b2c6f1e3` voorkomt en de deploy groen is. Zie je een fout, doe dan niets zelf aan de database en meld het aan Claude; de vorige versie blijft naar mijn weten live.
2. Open de site en controleer `/health` (verwacht 200).
3. Log in als jezelf. Dit moet **één keer opnieuw** (oude sessies hebben geen stempel). Daarna werken Reserveringen en Plattegrond zoals voorheen.

## Fase 2 — Pagina Medewerkers (alleen beheerder)

Begin pas na de merge en een groene deploy van fase 1.

### Branch (Git Bash, door de gebruiker)

```bash
git checkout main
git pull origin main
git checkout -b feat/accounts-fase2
```

### Cline-prompt

```text
Context
Je werkt in C:\Codes\WPL (Flask-app voor reserveringen). Branch feat/accounts-fase2 is actief; fase 1 (rollen en app/toegang.py) staat al in main. Het fasenplan staat in "Fasenplan voor Cline accounts personeel.md"; lees alleen "Fase 2". Deze fase voegt de pagina /accounts toe waar een beheerder personeelsaccounts aanmaakt, aan- en uitzet en een nieuw wachtwoord instelt.

Taak
1. Maak de nieuwe bestanden precies zoals in "Fase 2 > Bestanden > Nieuwe bestanden".
2. Pas de bestaande bestanden aan zoals in "Fase 2 > Bestanden > Gewijzigde bestanden" (regels met - weg, regels met + erbij). Gebruik je bewerk-tool per blok, niet git apply. Behoud de regeleinden (CRLF) van bestaande bestanden; nieuwe bestanden ook met CRLF.
3. Draai in Git Bash, vanuit de repo-root, met de venv actief:
   python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"

Rapporteer alleen
Wat er gebeurt; verzin niets en verbeter niets.

Beperkingen
- Geen git-commando's (geen add, commit, push, branch).
- Geen echte databaseverbinding: gebruik geen DATABASE_URL, geen Neon, geen .env. Start de app niet tegen een echte database.
- Lees of toon geen .env, .flaskenv, mcp.json of .neon.
- Wijzig geen andere bestanden en voeg niets toe dat niet in het plan staat. Bij twijfel stop je en vraagt het mij.

Wat je mij meldt
- Lijst van nieuwe en gewijzigde bestanden.
- De testuitslag (de regels Ran, OK of FAILED).
- Elke afwijking van het plan, met reden.
```

### Bestanden

#### Nieuwe bestanden (maak ze precies zo aan)

**`app/routes/accounts.py`**

````python
"""
Personeelsaccounts beheren: alleen voor beheerders. Aanmaken, aan- en uitzetten en een nieuw
wachtwoord instellen. Een account wordt nooit verwijderd, alleen uitgezet.
"""
import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import OperationalError

from app.database import (
    ROLLEN, LaatsteBeheerderFout, get_db, haal_alle_personeel, haal_gebruiker_op_id, maak_gebruiker,
    zet_actief, zet_wachtwoord,
)
from app.security import rate_limit, valideer_csrf
from app.toegang import MIN_WACHTWOORD_LENGTE, beheerder_vereist, huidige_gebruiker, wachtwoord_fout

accounts_bp = Blueprint('accounts', __name__, url_prefix='/accounts')
accounts_bp.before_request(valideer_csrf)

GEBRUIKERSNAAM_PATROON = re.compile(r'[a-z0-9._-]{3,30}')
DATABASE_DRUK = "Het lukte niet om op te slaan. Probeer het opnieuw."


def _terug():
    return redirect(url_for('accounts.overzicht'))


@accounts_bp.route('')
@beheerder_vereist
def overzicht():
    return render_template(
        'accounts.html', actief='accounts', accounts=haal_alle_personeel(get_db()),
        ik=huidige_gebruiker(), rollen=ROLLEN, min_lengte=MIN_WACHTWOORD_LENGTE,
    )


@accounts_bp.post('/nieuw')
@beheerder_vereist
@rate_limit('accounts', 20, 600)
def nieuw():
    naam = request.form.get('gebruikersnaam', '').strip().lower()
    wachtwoord = request.form.get('wachtwoord', '')
    rol = request.form.get('rol', 'medewerker')
    if not GEBRUIKERSNAAM_PATROON.fullmatch(naam):
        flash("De gebruikersnaam mag 3 tot 30 tekens hebben: kleine letters, cijfers, punt, streepje en underscore.", 'fout')
    elif rol not in ROLLEN:
        flash("Kies een rol.", 'fout')
    elif (fout := wachtwoord_fout(wachtwoord)) is not None:
        flash(fout, 'fout')
    else:
        try:
            aangemaakt = maak_gebruiker(get_db(), naam, wachtwoord, rol)
        except OperationalError:
            flash(DATABASE_DRUK, 'fout')
        else:
            if aangemaakt:
                flash(f"Account {naam} is aangemaakt. Geef de gebruikersnaam en het wachtwoord zelf door.", 'ok')
            else:
                flash(f"De gebruikersnaam {naam} bestaat al.", 'fout')
    return _terug()


@accounts_bp.post('/<int:gebruiker_id>/actief')
@beheerder_vereist
def actief(gebruiker_id):
    aan = request.form.get('actief') == '1'
    conn = get_db()
    doel = haal_gebruiker_op_id(conn, gebruiker_id)
    if doel is None:
        flash("Dit account bestaat niet.", 'fout')
    elif doel['id'] == huidige_gebruiker()['id'] and not aan:
        flash("Je kunt je eigen account niet uitzetten.", 'fout')
    else:
        try:
            zet_actief(conn, gebruiker_id, aan)
        except LaatsteBeheerderFout as fout:
            flash(fout.bericht, 'fout')
        except OperationalError:
            flash(DATABASE_DRUK, 'fout')
        else:
            flash(f"Account {doel['gebruikersnaam']} staat nu {'aan' if aan else 'uit'}.", 'ok')
    return _terug()


@accounts_bp.post('/<int:gebruiker_id>/wachtwoord')
@beheerder_vereist
@rate_limit('accounts', 20, 600)
def wachtwoord(gebruiker_id):
    nieuw_wachtwoord = request.form.get('wachtwoord', '')
    conn = get_db()
    doel = haal_gebruiker_op_id(conn, gebruiker_id)
    if doel is None:
        flash("Dit account bestaat niet.", 'fout')
    elif doel['id'] == huidige_gebruiker()['id']:
        flash("Wijzig je eigen wachtwoord via je eigen account.", 'fout')
    elif (fout := wachtwoord_fout(nieuw_wachtwoord)) is not None:
        flash(fout, 'fout')
    else:
        try:
            zet_wachtwoord(conn, gebruiker_id, nieuw_wachtwoord)
        except OperationalError:
            flash(DATABASE_DRUK, 'fout')
        else:
            flash(f"Nieuw wachtwoord voor {doel['gebruikersnaam']} is ingesteld. Alle apparaten van "
                  f"{doel['gebruikersnaam']} zijn uitgelogd. Geef het wachtwoord zelf door.", 'ok')
    return _terug()
````

**`templates/accounts.html`**

````html
{% extends "personeel.html" %}
{% block titel %}Medewerkers · {{ config.RESTAURANT_NAAM }}{% endblock %}
{% block inhoud %}
<div class="dagnav"><h2>Medewerkers</h2></div>

{% for categorie, bericht in get_flashed_messages(with_categories=true) %}
<div class="melding {{ categorie }}" role="{{ 'alert' if categorie == 'fout' else 'status' }}">{{ bericht }}</div>
{% endfor %}

<div class="indeling">
    <div class="paneel">
        <h3>Accounts</h3>
        <p class="klein">Een beheerder kan accounts beheren. Een medewerker ziet alleen reserveringen en plattegrond.
            Een uitgezet account kan niet meer inloggen; ook niet op een telefoon die nog ingelogd is.</p>
        <ul class="accountlijst">
            {% for a in accounts %}
            <li class="account {{ 'uit' if not a.actief }}">
                <div class="wie">
                    <b>{{ a.gebruikersnaam }}</b>{% if a.id == ik.id %}<span class="label">jij</span>{% endif %}
                    <small>{{ 'Beheerder' if a.rol == 'beheerder' else 'Medewerker' }} · {{ 'actief' if a.actief else 'uitgezet' }}</small>
                </div>
                {% if a.id != ik.id %}
                <form action="/accounts/{{ a.id }}/actief" method="POST">
                    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                    <input type="hidden" name="actief" value="{{ '0' if a.actief else '1' }}">
                    <button type="submit" class="pil">{{ 'Uitzetten' if a.actief else 'Aanzetten' }}</button>
                </form>
                <details>
                    <summary>Nieuw wachtwoord instellen</summary>
                    <form action="/accounts/{{ a.id }}/wachtwoord" method="POST">
                        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                        <label for="wachtwoord-{{ a.id }}" class="verborgen">Nieuw wachtwoord voor {{ a.gebruikersnaam }}</label>
                        <input type="password" id="wachtwoord-{{ a.id }}" name="wachtwoord" required minlength="{{ min_lengte }}"
                               autocomplete="new-password" placeholder="Minstens {{ min_lengte }} tekens">
                        <button type="submit" class="pil">Opslaan</button>
                    </form>
                </details>
                {% endif %}
            </li>
            {% endfor %}
        </ul>
    </div>

    <div class="paneel">
        <h3>Nieuw account</h3>
        <form action="/accounts/nieuw" method="POST" style="margin-top: 12px">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
            <div class="veld">
                <label for="gebruikersnaam">Gebruikersnaam</label>
                <input type="text" id="gebruikersnaam" name="gebruikersnaam" required minlength="3" maxlength="30"
                       pattern="[a-zA-Z0-9._\-]+" autocomplete="off" autocapitalize="none" spellcheck="false">
            </div>
            <div class="veld">
                <label for="nieuw-wachtwoord">Wachtwoord</label>
                <input type="password" id="nieuw-wachtwoord" name="wachtwoord" required minlength="{{ min_lengte }}"
                       autocomplete="new-password" placeholder="Minstens {{ min_lengte }} tekens">
            </div>
            <div class="veld">
                <label for="rol">Rol</label>
                <select id="rol" name="rol">
                    <option value="medewerker" selected>Medewerker</option>
                    <option value="beheerder">Beheerder</option>
                </select>
            </div>
            <button type="submit" class="knop klein">Account aanmaken</button>
            <p class="klein" style="margin-top: 10px">Geef de gebruikersnaam en het wachtwoord zelf door, niet per mail.</p>
        </form>
    </div>
</div>
{% endblock %}
````

**`tests/test_accounts.py`**

````python
import re
import unittest

from sqlalchemy import func, select

from app.database import (
    LaatsteBeheerderFout, get_db, personeel, zet_actief,
)
from tests.hulp import WACHTWOORD, log_in, zet_gebruiker
from tests.test_toegang import TestConfig, ToegangTestBasis

NIEUW_WACHTWOORD = "nieuw-wachtwoord-456"


class MetCsrfConfig(TestConfig):
    CSRF_ENABLED = True


class AccountsTestBasis(ToegangTestBasis):
    def setUp(self):
        super().setUp()
        log_in(self.app, self.client, naam="chef", rol="beheerder")

    def id_van(self, naam):
        return self.rij(naam)["id"]

    def post(self, pad, **data):
        return self.client.post(pad, data=data)

    def pagina(self):
        return self.client.get("/accounts").get_data(as_text=True)

    def tel(self):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                return conn.execute(select(func.count()).select_from(personeel)).scalar()

    def inloggen(self, naam, wachtwoord):
        client = self.app.test_client()
        antwoord = client.post("/login", data={"gebruikersnaam": naam, "wachtwoord": wachtwoord})
        return client, antwoord


class ToegangTests(AccountsTestBasis):
    def test_niet_ingelogd_naar_login(self):
        antwoord = self.app.test_client().get("/accounts")
        self.assertEqual(antwoord.status_code, 302)
        self.assertTrue(antwoord.headers["Location"].endswith("/login"))

    def test_medewerker_krijgt_403_op_alle_routes(self):
        client = self.app.test_client()
        log_in(self.app, client, naam="anna", rol="medewerker")
        anna = self.id_van("anna")
        self.assertEqual(client.get("/accounts").status_code, 403)
        self.assertEqual(client.post("/accounts/nieuw", data={"gebruikersnaam": "bob", "wachtwoord": WACHTWOORD}).status_code, 403)
        self.assertEqual(client.post(f"/accounts/{anna}/actief", data={"actief": "0"}).status_code, 403)
        self.assertEqual(client.post(f"/accounts/{anna}/wachtwoord", data={"wachtwoord": NIEUW_WACHTWOORD}).status_code, 403)
        self.assertIsNone(self.rij("bob"))

    def test_menu_toont_medewerkers_alleen_aan_beheerder(self):
        self.assertIn('href="/accounts"', self.client.get("/overzicht").get_data(as_text=True))
        client = self.app.test_client()
        log_in(self.app, client, naam="anna", rol="medewerker")
        self.assertNotIn('href="/accounts"', client.get("/overzicht").get_data(as_text=True))

    def test_lijst_toont_accounts_en_wie_jij_bent(self):
        zet_gebruiker(self.app, "anna", rol="medewerker", actief=False)
        html = self.pagina()
        self.assertIn("<b>chef</b>", html)
        self.assertIn("<b>anna</b>", html)
        self.assertEqual(html.count('class="label">jij<'), 1)
        self.assertIn("uitgezet", html)
        self.assertNotIn(f'/accounts/{self.id_van("chef")}/actief', html)  # geen knop voor jezelf


class AanmakenTests(AccountsTestBasis):
    def test_nieuw_account_wordt_medewerker_en_kan_inloggen(self):
        antwoord = self.post("/accounts/nieuw", gebruikersnaam="Anna", wachtwoord=WACHTWOORD, rol="medewerker")
        self.assertEqual(antwoord.status_code, 302)
        rij = self.rij("anna")  # hoofdletters worden kleine letters
        self.assertEqual((rij["rol"], rij["actief"], rij["taal"]), ("medewerker", True, "nl"))
        self.assertIn("Account anna is aangemaakt", self.pagina())
        client, antwoord = self.inloggen("anna", WACHTWOORD)
        self.assertEqual(antwoord.status_code, 302)
        self.assertEqual(client.get("/overzicht").status_code, 200)
        self.assertEqual(client.get("/accounts").status_code, 403)

    def test_nieuwe_beheerder(self):
        self.post("/accounts/nieuw", gebruikersnaam="tweede", wachtwoord=WACHTWOORD, rol="beheerder")
        client, _ = self.inloggen("tweede", WACHTWOORD)
        self.assertEqual(client.get("/accounts").status_code, 200)

    def test_ongeldige_invoer_maakt_niets_aan(self):
        voor = self.tel()
        gevallen = [
            dict(gebruikersnaam="ab", wachtwoord=WACHTWOORD, rol="medewerker"),          # te kort
            dict(gebruikersnaam="a b c", wachtwoord=WACHTWOORD, rol="medewerker"),       # spaties
            dict(gebruikersnaam="<script>", wachtwoord=WACHTWOORD, rol="medewerker"),    # tekens
            dict(gebruikersnaam="x" * 31, wachtwoord=WACHTWOORD, rol="medewerker"),      # te lang
            dict(gebruikersnaam="bob", wachtwoord="kort", rol="medewerker"),             # wachtwoord te kort
            dict(gebruikersnaam="bob", wachtwoord="x" * 129, rol="medewerker"),          # wachtwoord te lang
            dict(gebruikersnaam="bob", wachtwoord=WACHTWOORD, rol="eigenaar"),           # onbekende rol
            dict(wachtwoord=WACHTWOORD),                                                 # alles ontbreekt
        ]
        for data in gevallen:
            with self.subTest(data=data):
                self.assertEqual(self.post("/accounts/nieuw", **data).status_code, 302)
        self.assertEqual(self.tel(), voor)
        self.assertIn("melding fout", self.pagina())

    def test_bestaande_naam_ongeacht_hoofdletters(self):
        self.post("/accounts/nieuw", gebruikersnaam="anna", wachtwoord=WACHTWOORD)
        voor = self.tel()
        self.post("/accounts/nieuw", gebruikersnaam="ANNA", wachtwoord=NIEUW_WACHTWOORD)
        self.assertEqual(self.tel(), voor)
        self.assertIn("bestaat al", self.pagina())
        _, antwoord = self.inloggen("anna", NIEUW_WACHTWOORD)  # het wachtwoord is niet overschreven
        self.assertEqual(antwoord.status_code, 200)

    def test_melding_verdwijnt_na_een_keer_tonen(self):
        self.post("/accounts/nieuw", gebruikersnaam="anna", wachtwoord=WACHTWOORD)
        self.assertIn("is aangemaakt", self.pagina())
        self.assertNotIn("is aangemaakt", self.pagina())


class AanEnUitzettenTests(AccountsTestBasis):
    def setUp(self):
        super().setUp()
        self.anna_client = self.app.test_client()
        log_in(self.app, self.anna_client, naam="anna", rol="medewerker")
        self.anna = self.id_van("anna")

    def test_uitzetten_zet_ook_een_lopende_sessie_stil(self):
        self.assertEqual(self.anna_client.get("/overzicht").status_code, 200)
        self.post(f"/accounts/{self.anna}/actief", actief="0")
        self.assertFalse(self.rij("anna")["actief"])
        self.assertEqual(self.anna_client.get("/overzicht").status_code, 302)
        _, antwoord = self.inloggen("anna", WACHTWOORD)
        self.assertEqual(antwoord.status_code, 200)  # blijft op de loginpagina

    def test_weer_aanzetten(self):
        self.post(f"/accounts/{self.anna}/actief", actief="0")
        self.post(f"/accounts/{self.anna}/actief", actief="1")
        self.assertTrue(self.rij("anna")["actief"])
        _, antwoord = self.inloggen("anna", WACHTWOORD)
        self.assertEqual(antwoord.status_code, 302)

    def test_jezelf_niet_uitzetten(self):
        self.post(f"/accounts/{self.id_van('chef')}/actief", actief="0")
        self.assertTrue(self.rij("chef")["actief"])
        self.assertIn("eigen account niet uitzetten", self.pagina())
        self.assertEqual(self.client.get("/accounts").status_code, 200)

    def test_onbekend_account(self):
        antwoord = self.post("/accounts/99999/actief", actief="0")
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn("bestaat niet", self.pagina())

    def test_andere_beheerder_uitzetten_mag(self):
        zet_gebruiker(self.app, "tweede", rol="beheerder")
        self.post(f"/accounts/{self.id_van('tweede')}/actief", actief="0")
        self.assertFalse(self.rij("tweede")["actief"])

    def test_laatste_actieve_beheerder_kan_niet_uit(self):
        with self.app.app_context():
            conn = get_db()
            with self.assertRaises(LaatsteBeheerderFout):
                zet_actief(conn, self.id_van("chef"), False)
        self.assertTrue(self.rij("chef")["actief"])

    def test_medewerker_uitzetten_vraagt_geen_beheerder(self):
        with self.app.app_context():
            self.assertTrue(zet_actief(get_db(), self.anna, False))
            self.assertFalse(zet_actief(get_db(), 99999, False))

    def test_beheerder_uitzetten_mag_als_er_een_andere_actieve_is(self):
        zet_gebruiker(self.app, "tweede", rol="beheerder")
        with self.app.app_context():
            self.assertTrue(zet_actief(get_db(), self.id_van("chef"), False))
            with self.assertRaises(LaatsteBeheerderFout):
                zet_actief(get_db(), self.id_van("tweede"), False)

    def test_uitgezette_beheerder_telt_niet_mee_als_andere(self):
        zet_gebruiker(self.app, "tweede", rol="beheerder", actief=False)
        with self.app.app_context():
            with self.assertRaises(LaatsteBeheerderFout):
                zet_actief(get_db(), self.id_van("chef"), False)


class WachtwoordResetTests(AccountsTestBasis):
    def setUp(self):
        super().setUp()
        self.anna_client = self.app.test_client()
        log_in(self.app, self.anna_client, naam="anna", rol="medewerker")
        self.anna = self.id_van("anna")

    def test_nieuw_wachtwoord_werkt_en_oude_sessie_vervalt(self):
        self.assertEqual(self.anna_client.get("/overzicht").status_code, 200)
        self.post(f"/accounts/{self.anna}/wachtwoord", wachtwoord=NIEUW_WACHTWOORD)
        self.assertEqual(self.anna_client.get("/overzicht").status_code, 302)
        self.assertEqual(self.inloggen("anna", WACHTWOORD)[1].status_code, 200)
        self.assertEqual(self.inloggen("anna", NIEUW_WACHTWOORD)[1].status_code, 302)
        self.assertIn("Nieuw wachtwoord voor anna", self.pagina())

    def test_te_kort_wachtwoord(self):
        hash_voor = self.rij("anna")["wachtwoord_hash"]
        self.post(f"/accounts/{self.anna}/wachtwoord", wachtwoord="kort")
        self.assertEqual(self.rij("anna")["wachtwoord_hash"], hash_voor)
        self.assertIn("minstens 12 tekens", self.pagina())

    def test_eigen_wachtwoord_niet_via_deze_route(self):
        hash_voor = self.rij("chef")["wachtwoord_hash"]
        self.post(f"/accounts/{self.id_van('chef')}/wachtwoord", wachtwoord=NIEUW_WACHTWOORD)
        self.assertEqual(self.rij("chef")["wachtwoord_hash"], hash_voor)
        self.assertEqual(self.client.get("/accounts").status_code, 200)  # sessie is nog geldig

    def test_onbekend_account(self):
        self.post("/accounts/99999/wachtwoord", wachtwoord=NIEUW_WACHTWOORD)
        self.assertIn("bestaat niet", self.pagina())


class CsrfTests(unittest.TestCase):
    def test_post_zonder_token_wordt_geweigerd(self):
        from app import create_app
        from app.security import reset_rate_limits
        reset_rate_limits()
        app = create_app(MetCsrfConfig)
        client = app.test_client()
        log_in(app, client, naam="chef", rol="beheerder")
        antwoord = client.post("/accounts/nieuw", data={"gebruikersnaam": "bob", "wachtwoord": WACHTWOORD})
        self.assertEqual(antwoord.status_code, 400)
        html = client.get("/accounts").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        antwoord = client.post("/accounts/nieuw", data={
            "gebruikersnaam": "bob", "wachtwoord": WACHTWOORD, "csrf_token": token})
        self.assertEqual(antwoord.status_code, 302)
        with app.app_context():
            conn = get_db()
            with conn.begin():
                namen = conn.execute(select(personeel.c.gebruikersnaam)).scalars().all()
        self.assertIn("bob", namen)


if __name__ == "__main__":
    unittest.main()
````

#### Gewijzigde bestanden (regels met `-` weg, regels met `+` erbij; de rest is omgeving)

**`app/__init__.py`**

````diff
@@ -3,11 +3,11 @@ import logging
 from datetime import date
 from pathlib import Path
 import click
-from flask import Flask
+from flask import Flask, has_request_context
 from sqlalchemy.exc import SQLAlchemyError
 from werkzeug.middleware.proxy_fix import ProxyFix
 from app.security import csrf_token
-from app.toegang import MIN_WACHTWOORD_LENGTE
+from app.toegang import MIN_WACHTWOORD_LENGTE, huidige_gebruiker
 from app.config import Config
 from app.database import (
     init_db_pool, close_db, init_db, get_db, haal_reservering_op,
@@ -55,15 +55,19 @@ def create_app(config_class=Config):
         app.wsgi_app = ProxyFix(app.wsgi_app, x_for=app.config['TRUSTED_PROXY_COUNT'])
     app.jinja_env.globals['csrf_token'] = csrf_token
     app.context_processor(lambda: {'huisstijl': app.config['HUISSTIJL']})
+    # De ingelogde gebruiker voor het menu; None op gastpagina's en zonder geldige sessie.
+    app.context_processor(lambda: {'gebruiker': huidige_gebruiker() if has_request_context() else None})
     weergave.registreer(app)
 
     from app.routes.web import web_bp
     from app.routes.api import api_bp
     from app.routes.beheer import beheer_bp
+    from app.routes.accounts import accounts_bp
 
     app.register_blueprint(web_bp)
     app.register_blueprint(api_bp)
     app.register_blueprint(beheer_bp)
+    app.register_blueprint(accounts_bp)
 
     def _guard(productie):
         try:
````

**`app/database.py`**

````diff
@@ -5,7 +5,7 @@ from werkzeug.security import generate_password_hash
 from sqlalchemy.engine import make_url
 from sqlalchemy import (
     MetaData, Table, Column, Text, Integer, Boolean, DateTime, ForeignKey,
-    create_engine, event, select, insert, delete, func, text, true,
+    create_engine, event, select, insert, update, delete, func, text, true,
 )
 from app.normalisatie import normaliseer_email, normaliseer_telefoon
 
@@ -418,6 +418,49 @@ def maak_gebruiker(conn, gebruikersnaam, wachtwoord, rol='medewerker'):
         )
     return True
 
+class LaatsteBeheerderFout(Exception):
+    """Dit account is de laatste actieve beheerder; uitzetten laat niemand over om accounts te beheren."""
+    bericht = "Er moet minstens één actieve beheerder overblijven."
+
+def haal_alle_personeel(conn):
+    with conn.begin():
+        return conn.execute(
+            select(personeel).order_by(func.lower(personeel.c.gebruikersnaam))
+        ).mappings().all()
+
+def haal_gebruiker_op_id(conn, gebruiker_id):
+    with conn.begin():
+        return conn.execute(select(personeel).where(personeel.c.id == gebruiker_id)).mappings().first()
+
+def zet_actief(conn, gebruiker_id, actief):
+    """
+    Zet een account aan of uit. Geeft False terug als het account niet bestaat.
+    Gooit LaatsteBeheerderFout als dit de enige actieve beheerder is en hij uit moet.
+    """
+    with conn.begin():
+        rij = conn.execute(select(personeel).where(personeel.c.id == gebruiker_id)).mappings().first()
+        if rij is None:
+            return False
+        if not actief and rij['rol'] == 'beheerder' and rij['actief']:
+            anderen = conn.execute(
+                select(func.count()).select_from(personeel).where(
+                    personeel.c.rol == 'beheerder', personeel.c.actief == true(), personeel.c.id != gebruiker_id
+                )
+            ).scalar()
+            if not anderen:
+                raise LaatsteBeheerderFout()
+        conn.execute(update(personeel).where(personeel.c.id == gebruiker_id).values(actief=bool(actief)))
+    return True
+
+def zet_wachtwoord(conn, gebruiker_id, wachtwoord):
+    """Vervangt het wachtwoord van een account. Geeft False terug als het account niet bestaat."""
+    with conn.begin():
+        resultaat = conn.execute(
+            update(personeel).where(personeel.c.id == gebruiker_id)
+            .values(wachtwoord_hash=generate_password_hash(wachtwoord))
+        )
+    return resultaat.rowcount > 0
+
 class ProductieVlagVereist(Exception):
     """Het commando richt zich op een niet-SQLite database en `--productie` ontbreekt."""
 
````

**`app/toegang.py`**

````diff
@@ -17,6 +17,15 @@ MIN_WACHTWOORD_LENGTE = 12
 MAX_WACHTWOORD_LENGTE = 128
 
 
+def wachtwoord_fout(wachtwoord):
+    """Melding voor een onbruikbaar nieuw wachtwoord, of None als het goed is."""
+    if len(wachtwoord) < MIN_WACHTWOORD_LENGTE:
+        return f"Het wachtwoord moet minstens {MIN_WACHTWOORD_LENGTE} tekens hebben."
+    if len(wachtwoord) > MAX_WACHTWOORD_LENGTE:
+        return f"Het wachtwoord mag hoogstens {MAX_WACHTWOORD_LENGTE} tekens hebben."
+    return None
+
+
 def sessie_stempel(wachtwoord_hash):
     """Korte vingerafdruk van de wachtwoordhash; verandert het wachtwoord, dan vervalt de sessie."""
     return hashlib.sha256(wachtwoord_hash.encode('utf-8')).hexdigest()[:16]
````

**`static/css/huisstijl.css`**

````diff
@@ -78,6 +78,9 @@ label { display: block; font-size: 12.5px; color: var(--zacht); margin-bottom: 5
 input[type=text], input[type=email], input[type=tel], input[type=password], input[type=date], input[type=search] {
     width: 100%; height: 44px; border-radius: 10px; border: 1px solid var(--lijn); background: var(--veld);
     padding: 0 12px; font: inherit; font-size: 14px; color: var(--tekst); color-scheme: dark; }
+select { width: 100%; height: 44px; border-radius: 10px; border: 1px solid var(--lijn); background: var(--veld);
+         padding: 0 12px; font: inherit; font-size: 14px; color: var(--tekst); color-scheme: dark; }
+select:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
 input::placeholder { color: #8f8676; }
 input:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
 .twee { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@@ -196,6 +199,17 @@ input:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
 .reservering.zonder-tafel small { color: var(--accent); }
 #reserveringen { padding: 0; list-style: none; }
 
+/* Personeel: accounts */
+.accountlijst { list-style: none; padding: 0; margin-top: 12px; }
+.account { display: grid; grid-template-columns: 1fr auto; gap: 6px 12px; align-items: center; padding: 12px 0; border-bottom: 1px solid rgba(255, 255, 255, .06); }
+.account:last-child { border-bottom: 0; }
+.account.uit .wie b { color: var(--zacht); text-decoration: line-through; }
+.account form { margin: 0; }
+.account details { grid-column: 1 / -1; }
+.account summary { font-size: 12px; color: var(--zacht); cursor: pointer; }
+.account details form { display: flex; gap: 8px; margin-top: 8px; }
+.account details input { flex: 1; min-width: 0; }
+
 @media (max-width: 700px) {
     .tellers { grid-template-columns: 1fr 1fr; }
     .res { grid-template-columns: 40px 1fr; row-gap: 8px; }
````

**`templates/personeel.html`**

````diff
@@ -10,6 +10,9 @@
             {% if config.PLATTEGROND %}
             <a class="pil {{ 'aan' if actief == 'plattegrond' }}" href="/plattegrond{{ '?datum=' ~ datum if datum }}">Plattegrond</a>
             {% endif %}
+            {% if gebruiker and gebruiker.rol == 'beheerder' %}
+            <a class="pil {{ 'aan' if actief == 'accounts' }}" href="/accounts">Medewerkers</a>
+            {% endif %}
             <a class="pil" href="/">Reserveringsformulier</a>
             <form action="/logout" method="POST">
                 <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
````

**`tests/test_beschikbaarheid.py`**

````diff
@@ -23,6 +23,7 @@ class TestConfig(Config):
     API_KEY = "test-key"
     WEBHOOK_API_KEY = "test-key"
     DATABASE_URL = "sqlite:///:memory:"
+    ADMIN_INITIAL_PASSWORD = "test-admin-pw"
     SESSION_COOKIE_SECURE = False
     TRUSTED_PROXY_COUNT = 0
     RESTAURANT_CONFIG = "restaurants/wpl.toml"  # 69 gasten tegelijk, 90 minuten, knoppen per 30 minuten
````

**`tests/test_gastpaginas.py`**

````diff
@@ -24,6 +24,7 @@ class TestConfig(Config):
     API_KEY = "test-key"
     WEBHOOK_API_KEY = "test-key"
     DATABASE_URL = "sqlite:///:memory:"
+    ADMIN_INITIAL_PASSWORD = "test-admin-pw"
     SESSION_COOKIE_SECURE = False
     TRUSTED_PROXY_COUNT = 0
     RESTAURANT_CONFIG = "restaurants/wpl.toml"
````

**`tests/test_plattegrond_stijl.py`**

````diff
@@ -15,6 +15,7 @@ class TestConfig(Config):
     API_KEY = "test-key"
     WEBHOOK_API_KEY = "test-key"
     DATABASE_URL = "sqlite:///:memory:"
+    ADMIN_INITIAL_PASSWORD = "test-admin-pw"
     SESSION_COOKIE_SECURE = False
     TRUSTED_PROXY_COUNT = 0
     CSRF_ENABLED = False
````


### Controlepunten voor Opus

1. **Elke route is beheerder-only.** Het aantal routes en het aantal `@beheerder_vereist` moeten gelijk zijn, en `@beheerder_vereist` staat boven `@rate_limit` (zodat alleen beheerders de teller ophogen).
   ```bash
   grep -c "^@accounts_bp\." app/routes/accounts.py
   grep -c "^@beheerder_vereist" app/routes/accounts.py
   grep -c "^@rate_limit" app/routes/accounts.py
   grep -c "safe" templates/accounts.html
   ```
   Verwacht: `4`, `4`, `2` en `0` (geen `|safe`; meldingen worden dus ge-escaped). Een `0` kan een kapotte pipe zijn: controleer ook een patroon waarvan je weet dat het matcht, `grep -c "beheerder_vereist" app/routes/accounts.py` (verwacht `5`: de importregel en 4 decorators).
2. **CSRF.** `accounts_bp.before_request(valideer_csrf)` staat er, en elk formulier in `accounts.html` heeft `csrf_token`. Er is een test met `CSRF_ENABLED = True`.
3. **Geen gebruikersnaam in de URL.** De routes gebruiken `<int:gebruiker_id>`.
4. **Zelfbescherming.** Je kunt jezelf niet uitzetten en je eigen wachtwoord niet via deze pagina wijzigen (anders zou je sessiestempel ongeldig worden). `LaatsteBeheerderFout` voorkomt dat de laatste actieve beheerder uitgezet wordt; de test voor een beheerder die niet meetelt omdat hij uit staat is aanwezig.
5. **Gebruikersnaam.** Kleine letters, cijfers, punt, streepje, underscore, 3 tot 30 tekens (`GEBRUIKERSNAAM_PATROON`); wachtwoord 12 tot 128 tekens; rol alleen uit `ROLLEN`.
6. **Menu.** De tab Medewerkers verschijnt alleen voor een beheerder (`gebruiker.rol == 'beheerder'` in `personeel.html`); de contextprocessor in `app/__init__.py` roept `huidige_gebruiker()` alleen aan binnen een verzoek.
7. **Testisolatie.** Drie bestaande testconfiguraties kregen `ADMIN_INITIAL_PASSWORD`. Dat was nodig omdat de nieuwe tests de tabel `personeel` leegmaken en `init_db()` anders faalt, afhankelijk van de volgorde van de tests. Voer de volledige suite twee keer uit.

### Verwacht

`Ran 297 tests ... OK (skipped=6)` (23 nieuwe tests in `tests/test_accounts.py`).

### Voor de merge

PR maken; CI `unit-tests` groen.

### Na de merge (door de gebruiker)

1. Wacht op de groene Render-deploy en open `/overzicht`: in het menu staat nu **Medewerkers** (dit bewijst dat jouw bestaande account beheerder is geworden).
2. Maak een testaccount: genereer een wachtwoord in je eigen terminal (Git Bash) en plak het **niet** in een chat:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(16))"
   ```
   Maak op `/accounts` een account `test-medewerker` met de rol Medewerker. Log in een privévenster in met dat account: je ziet Reserveringen en Plattegrond maar geen Medewerkers, en `/accounts` geeft "Geen toegang."
3. Zet het testaccount uit en probeer in het privévenster een pagina te openen: je wordt direct uitgelogd. Je kunt het testaccount laten staan (uitgezet).

## Fase 3 — Eigen wachtwoord wijzigen

Begin pas na de merge en een groene deploy van fase 2.

### Branch (Git Bash, door de gebruiker)

```bash
git checkout main
git pull origin main
git checkout -b feat/accounts-fase3
```

### Cline-prompt

```text
Context
Je werkt in C:\Codes\WPL (Flask-app voor reserveringen). Branch feat/accounts-fase3 is actief; fase 1 en 2 staan in main. Het fasenplan staat in "Fasenplan voor Cline accounts personeel.md"; lees alleen "Fase 3". Deze fase voegt de pagina /account toe waar ingelogd personeel zijn eigen wachtwoord wijzigt, en zet de eigen gebruikersnaam in het menu.

Taak
1. Maak de nieuwe bestanden precies zoals in "Fase 3 > Bestanden > Nieuwe bestanden".
2. Pas de bestaande bestanden aan zoals in "Fase 3 > Bestanden > Gewijzigde bestanden" (regels met - weg, regels met + erbij). Gebruik je bewerk-tool per blok, niet git apply. Behoud de regeleinden (CRLF) van bestaande bestanden; nieuwe bestanden ook met CRLF.
3. Draai in Git Bash, vanuit de repo-root, met de venv actief:
   python -m unittest discover -s tests 2>&1 | grep -E "^Ran|^OK|FAILED"

Rapporteer alleen
Wat er gebeurt; verzin niets en verbeter niets.

Beperkingen
- Geen git-commando's (geen add, commit, push, branch).
- Geen echte databaseverbinding: gebruik geen DATABASE_URL, geen Neon, geen .env.
- Lees of toon geen .env, .flaskenv, mcp.json of .neon.
- Wijzig geen andere bestanden en voeg niets toe dat niet in het plan staat. Bij twijfel stop je en vraagt het mij.

Wat je mij meldt
- Lijst van nieuwe en gewijzigde bestanden.
- De testuitslag (de regels Ran, OK of FAILED).
- Elke afwijking van het plan, met reden.
```

### Bestanden

#### Nieuwe bestanden (maak ze precies zo aan)

**`app/routes/account.py`**

````python
"""Het eigen account van ingelogd personeel: nu alleen het eigen wachtwoord wijzigen."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import OperationalError
from werkzeug.security import check_password_hash

from app.database import get_db, haal_gebruiker_op_id, zet_wachtwoord
from app.security import rate_limit, valideer_csrf
from app.toegang import MIN_WACHTWOORD_LENGTE, huidige_gebruiker, login_vereist, sessie_stempel, wachtwoord_fout

account_bp = Blueprint('account', __name__, url_prefix='/account')
account_bp.before_request(valideer_csrf)


@account_bp.route('')
@login_vereist
def mijn_account():
    return render_template('account.html', actief='account', ik=huidige_gebruiker(), min_lengte=MIN_WACHTWOORD_LENGTE)


@account_bp.post('/wachtwoord')
@login_vereist
@rate_limit('eigen-wachtwoord', 10, 600)
def wijzig_wachtwoord():
    ik = huidige_gebruiker()
    huidig = request.form.get('huidig', '')
    nieuw = request.form.get('nieuw', '')
    herhaal = request.form.get('herhaal', '')
    if not check_password_hash(ik['wachtwoord_hash'], huidig):
        flash("Je huidige wachtwoord klopt niet.", 'fout')
    elif (fout := wachtwoord_fout(nieuw)) is not None:
        flash(fout, 'fout')
    elif nieuw != herhaal:
        flash("De twee nieuwe wachtwoorden zijn niet hetzelfde.", 'fout')
    elif nieuw == huidig:
        flash("Kies een ander wachtwoord dan je huidige.", 'fout')
    else:
        conn = get_db()
        try:
            zet_wachtwoord(conn, ik['id'], nieuw)
        except OperationalError:
            flash("Het lukte niet om op te slaan. Probeer het opnieuw.", 'fout')
        else:
            # Het stempel hoort bij het wachtwoord: werk het bij, anders logt deze wijziging jezelf uit.
            # Andere apparaten met dit account blijven met het oude stempel achter en zijn dus uitgelogd.
            session['stempel'] = sessie_stempel(haal_gebruiker_op_id(conn, ik['id'])['wachtwoord_hash'])
            flash("Je wachtwoord is gewijzigd. Op je andere apparaten moet je opnieuw inloggen.", 'ok')
    return redirect(url_for('account.mijn_account'))
````

**`templates/account.html`**

````html
{% extends "personeel.html" %}
{% block titel %}Mijn account · {{ config.RESTAURANT_NAAM }}{% endblock %}
{% block inhoud %}
<div class="dagnav"><h2>Mijn account</h2></div>

{% for categorie, bericht in get_flashed_messages(with_categories=true) %}
<div class="melding {{ categorie }}" role="{{ 'alert' if categorie == 'fout' else 'status' }}">{{ bericht }}</div>
{% endfor %}

<div class="paneel paneel-smal">
    <div class="details">
        <div class="rij"><span>Gebruikersnaam</span><b>{{ ik.gebruikersnaam }}</b></div>
        <div class="rij"><span>Rol</span><b>{{ 'Beheerder' if ik.rol == 'beheerder' else 'Medewerker' }}</b></div>
    </div>

    <h3>Wachtwoord wijzigen</h3>
    <form action="/account/wachtwoord" method="POST" style="margin-top: 12px">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <div class="veld">
            <label for="huidig">Huidig wachtwoord</label>
            <input type="password" id="huidig" name="huidig" required autocomplete="current-password">
        </div>
        <div class="veld">
            <label for="nieuw">Nieuw wachtwoord</label>
            <input type="password" id="nieuw" name="nieuw" required minlength="{{ min_lengte }}" autocomplete="new-password"
                   placeholder="Minstens {{ min_lengte }} tekens">
        </div>
        <div class="veld">
            <label for="herhaal">Nieuw wachtwoord nogmaals</label>
            <input type="password" id="herhaal" name="herhaal" required minlength="{{ min_lengte }}" autocomplete="new-password">
        </div>
        <button type="submit" class="knop klein">Wachtwoord opslaan</button>
    </form>
</div>
{% endblock %}
````

**`tests/test_eigen_account.py`**

````python
import re
import unittest

from werkzeug.security import check_password_hash

from tests.hulp import WACHTWOORD, log_in
from tests.test_accounts import NIEUW_WACHTWOORD
from tests.test_toegang import ToegangTestBasis


class EigenAccountTests(ToegangTestBasis):
    def setUp(self):
        super().setUp()
        log_in(self.app, self.client, naam="anna", rol="medewerker")

    def wijzig(self, huidig=WACHTWOORD, nieuw=NIEUW_WACHTWOORD, herhaal=None, client=None):
        return (client or self.client).post("/account/wachtwoord", data={
            "huidig": huidig, "nieuw": nieuw, "herhaal": nieuw if herhaal is None else herhaal})

    def pagina(self):
        return self.client.get("/account").get_data(as_text=True)

    def inloggen(self, wachtwoord):
        client = self.app.test_client()
        return client.post("/login", data={"gebruikersnaam": "anna", "wachtwoord": wachtwoord}).status_code

    def test_niet_ingelogd_naar_login(self):
        client = self.app.test_client()
        self.assertEqual(client.get("/account").status_code, 302)
        self.assertEqual(self.wijzig(client=client).status_code, 302)

    def test_pagina_toont_naam_en_rol_voor_medewerker(self):
        html = self.pagina()
        self.assertIn("<b>anna</b>", html)
        self.assertIn("<b>Medewerker</b>", html)
        self.assertIn('href="/account"', html)  # de naam staat in het menu

    def test_wijzigen_lukt_en_je_blijft_ingelogd(self):
        antwoord = self.wijzig()
        self.assertEqual(antwoord.status_code, 302)
        self.assertTrue(check_password_hash(self.rij("anna")["wachtwoord_hash"], NIEUW_WACHTWOORD))
        self.assertIn("Je wachtwoord is gewijzigd", self.pagina())
        self.assertEqual(self.client.get("/overzicht").status_code, 200)  # eigen sessie blijft geldig
        self.assertEqual(self.inloggen(NIEUW_WACHTWOORD), 302)
        self.assertEqual(self.inloggen(WACHTWOORD), 200)

    def test_ander_apparaat_wordt_uitgelogd(self):
        telefoon = self.app.test_client()
        telefoon.post("/login", data={"gebruikersnaam": "anna", "wachtwoord": WACHTWOORD})
        self.assertEqual(telefoon.get("/overzicht").status_code, 200)
        self.wijzig()
        self.assertEqual(telefoon.get("/overzicht").status_code, 302)

    def test_fout_huidig_wachtwoord(self):
        hash_voor = self.rij("anna")["wachtwoord_hash"]
        self.wijzig(huidig="verkeerd-wachtwoord")
        self.assertEqual(self.rij("anna")["wachtwoord_hash"], hash_voor)
        self.assertIn("huidige wachtwoord klopt niet", self.pagina())

    def test_ongeldige_nieuwe_wachtwoorden(self):
        hash_voor = self.rij("anna")["wachtwoord_hash"]
        gevallen = [
            (dict(nieuw="kort"), "minstens 12 tekens"),
            (dict(nieuw="x" * 129), "hoogstens 128 tekens"),
            (dict(nieuw=NIEUW_WACHTWOORD, herhaal="iets-heel-anders-123"), "niet hetzelfde"),
            (dict(nieuw=WACHTWOORD), "ander wachtwoord"),
        ]
        for data, tekst in gevallen:
            with self.subTest(tekst=tekst):
                self.wijzig(**data)
                self.assertIn(tekst, self.pagina())
                self.assertEqual(self.rij("anna")["wachtwoord_hash"], hash_voor)

    def test_beheerder_ziet_zijn_rol(self):
        client = self.app.test_client()
        log_in(self.app, client, naam="chef", rol="beheerder")
        self.assertIn("<b>Beheerder</b>", client.get("/account").get_data(as_text=True))

    def test_formulier_bevat_csrf_token(self):
        self.assertTrue(re.search(r'name="csrf_token" value="[^"]+"', self.pagina()))


if __name__ == "__main__":
    unittest.main()
````

#### Gewijzigde bestanden (regels met `-` weg, regels met `+` erbij; de rest is omgeving)

**`app/__init__.py`**

````diff
@@ -63,11 +63,13 @@ def create_app(config_class=Config):
     from app.routes.api import api_bp
     from app.routes.beheer import beheer_bp
     from app.routes.accounts import accounts_bp
+    from app.routes.account import account_bp
 
     app.register_blueprint(web_bp)
     app.register_blueprint(api_bp)
     app.register_blueprint(beheer_bp)
     app.register_blueprint(accounts_bp)
+    app.register_blueprint(account_bp)
 
     def _guard(productie):
         try:
````

**`static/css/huisstijl.css`**

````diff
@@ -200,6 +200,7 @@ input:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
 #reserveringen { padding: 0; list-style: none; }
 
 /* Personeel: accounts */
+.paneel-smal { max-width: 460px; }
 .accountlijst { list-style: none; padding: 0; margin-top: 12px; }
 .account { display: grid; grid-template-columns: 1fr auto; gap: 6px 12px; align-items: center; padding: 12px 0; border-bottom: 1px solid rgba(255, 255, 255, .06); }
 .account:last-child { border-bottom: 0; }
````

**`templates/personeel.html`**

````diff
@@ -14,6 +14,9 @@
             <a class="pil {{ 'aan' if actief == 'accounts' }}" href="/accounts">Medewerkers</a>
             {% endif %}
             <a class="pil" href="/">Reserveringsformulier</a>
+            {% if gebruiker %}
+            <a class="pil {{ 'aan' if actief == 'account' }}" href="/account">{{ gebruiker.gebruikersnaam }}</a>
+            {% endif %}
             <form action="/logout" method="POST">
                 <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                 <button type="submit" class="pil">Uitloggen</button>
````


### Controlepunten voor Opus

1. **Huidig wachtwoord vereist.** `wijzig_wachtwoord` controleert eerst `check_password_hash` met het huidige wachtwoord, daarna lengte (via `wachtwoord_fout`), dat de twee nieuwe gelijk zijn en dat het nieuwe wachtwoord anders is dan het huidige.
2. **Sessiestempel.** Na het opslaan wordt `session['stempel']` bijgewerkt, zodat de eigen sessie geldig blijft; andere apparaten behouden het oude stempel en zijn uitgelogd (test `test_ander_apparaat_wordt_uitgelogd`).
3. **Routes.**
   ```bash
   grep -c "^@account_bp\." app/routes/account.py
   grep -c "^@login_vereist" app/routes/account.py
   ```
   Verwacht `2` en `2`. `@login_vereist` staat boven `@rate_limit`. Er is `account_bp.before_request(valideer_csrf)` en het formulier heeft `csrf_token`.
4. **Menu.** De eigen naam in het menu verwijst naar `/account` en wordt ge-escaped weergegeven (geen `|safe`).

### Verwacht

`Ran 305 tests ... OK (skipped=6)` (8 nieuwe tests in `tests/test_eigen_account.py`).

### Voor de merge

PR maken; CI `unit-tests` groen.

### Na de merge (door de gebruiker)

1. Open `/account` via je naam in het menu en wijzig je eigen wachtwoord met een nieuw, zelf gegenereerd wachtwoord (niet in een chat plakken). Je blijft ingelogd; log uit en weer in om het nieuwe wachtwoord te bewijzen.
2. Bewaar het nieuwe wachtwoord in je wachtwoordmanager.
3. Daarna is het account-onderwerp klaar. Zet in `OVERDRACHT.md` onder "Wat is af" een regel voor 8 nov (accounts met rollen) en pas bij Routes `/accounts` en `/account` toe, en bij Beheercommando's de nieuwe `--rol`.
