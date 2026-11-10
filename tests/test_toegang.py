"""Rollen en toegang voor personeel (deel 3, fase 1)."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect, select, update

from app import create_app
from app.config import Config
from app.database import (
    get_db, haal_reservering_op, init_db, maak_gebruiker, metadata, personeel, reserveringen, verwerk_reservering,
)
from app.security import reset_rate_limits
from app.toegang import beheerder_vereist, login_vereist
from tests.hulp import WACHTWOORD, log_in, zet_gebruiker

PROJECTMAP = Path(__file__).resolve().parent.parent


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

    def tearDown(self):
        # De testdatabase is gedeeld binnen het proces: laat de admin weer achter zoals init_db dat doet,
        # zodat andere testbestanden niet afhangen van de volgorde.
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(personeel.delete())
            init_db()

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
    DAG = "2030-01-01"  # een dinsdag

    def setUp(self):
        super().setUp()
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(reserveringen.delete())

    def reservering(self):
        with self.app.app_context():
            return verwerk_reservering(get_db(), 69, "Eva", "eva@example.com", "0611111111", self.DAG, "18:00", 2,
                                       zitduur_minuten=60)

    def bestaat(self, reservering_id):
        with self.app.app_context():
            return haal_reservering_op(get_db(), reservering_id) is not None

    def test_beheerder_komt_binnen(self):
        log_in(self.app, self.client, rol="beheerder")
        self.assertEqual(self.client.get("/_alleen-beheerder").status_code, 200)

    def test_medewerker_krijgt_403_maar_mag_wel_overzicht_en_plattegrond(self):
        log_in(self.app, self.client, naam="anna", rol="medewerker")
        self.assertEqual(self.client.get("/_alleen-beheerder").status_code, 403)
        self.assertEqual(self.client.get("/overzicht").status_code, 200)
        self.assertEqual(self.client.get("/plattegrond").status_code, 200)

    def test_medewerker_mag_tafels_toewijzen(self):
        reservering_id = self.reservering()
        log_in(self.app, self.client, naam="anna", rol="medewerker")
        antwoord = self.client.post("/plattegrond/toewijzen", json={"reservering_id": reservering_id, "tafels": []})
        self.assertEqual(antwoord.status_code, 200, antwoord.get_data(as_text=True))

    def test_medewerker_mag_niet_verwijderen(self):
        reservering_id = self.reservering()
        log_in(self.app, self.client, naam="anna", rol="medewerker")
        html = self.client.get(f"/overzicht?datum={self.DAG}").get_data(as_text=True)
        self.assertIn("Eva", html)
        self.assertNotIn(f"/verwijder/{reservering_id}", html)
        self.assertEqual(self.client.post(f"/verwijder/{reservering_id}").status_code, 403)
        self.assertTrue(self.bestaat(reservering_id))

    def test_beheerder_mag_verwijderen(self):
        reservering_id = self.reservering()
        log_in(self.app, self.client, naam="chef", rol="beheerder")
        html = self.client.get(f"/overzicht?datum={self.DAG}").get_data(as_text=True)
        self.assertIn(f"/verwijder/{reservering_id}", html)
        self.assertEqual(self.client.post(f"/verwijder/{reservering_id}").status_code, 302)
        self.assertFalse(self.bestaat(reservering_id))

    def test_niet_ingelogd_verwijderen_naar_login(self):
        reservering_id = self.reservering()
        antwoord = self.client.post(f"/verwijder/{reservering_id}")
        self.assertEqual(antwoord.status_code, 302)
        self.assertTrue(antwoord.headers["Location"].endswith("/login"))
        self.assertTrue(self.bestaat(reservering_id))


class DatalaagTests(ToegangTestBasis):
    def maak(self, *args, **kwargs):
        with self.app.app_context():
            return maak_gebruiker(get_db(), *args, **kwargs)

    def test_standaardrol_is_medewerker(self):
        self.assertTrue(self.maak("anna", "een-lang-wachtwoord"))
        rij = self.rij("anna")
        self.assertEqual((rij["rol"], rij["actief"]), ("medewerker", True))

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
            args=["create-admin", "--gebruikersnaam", "anna", "--rol", "medewerker"],
            input=f"{wachtwoord}\n{wachtwoord}\n")
        self.assertEqual(resultaat.exit_code, 0, resultaat.output)
        self.assertEqual(self.rij("anna")["rol"], "medewerker")


class MigratieTests(unittest.TestCase):
    def test_bestaande_accounts_worden_beheerder(self):
        with tempfile.TemporaryDirectory() as map_:
            url = f"sqlite:///{Path(map_) / 'migratie.db'}"
            omgeving = {**os.environ, "MIGRATION_DATABASE_URL": url}
            omgeving.pop("ALLOW_PROD_MIGRATE", None)

            def alembic(*args):
                resultaat = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=PROJECTMAP,
                                           env=omgeving, capture_output=True, text=True)
                self.assertEqual(resultaat.returncode, 0, resultaat.stderr)

            engine = create_engine(url)
            try:
                alembic("upgrade", "e5b9c1d3a7f2")
                with engine.begin() as conn:
                    conn.exec_driver_sql(
                        "INSERT INTO personeel (gebruikersnaam, wachtwoord_hash) VALUES ('admin', 'hash')")
                alembic("upgrade", "head")
                with engine.connect() as conn:
                    rij = conn.exec_driver_sql("SELECT gebruikersnaam, rol, actief FROM personeel").one()
                self.assertEqual(tuple(rij), ("admin", "beheerder", 1))
                with engine.begin() as conn:
                    conn.exec_driver_sql(
                        "INSERT INTO personeel (gebruikersnaam, wachtwoord_hash) VALUES ('nieuw', 'hash')")
                with engine.connect() as conn:
                    rij = conn.exec_driver_sql("SELECT rol, actief FROM personeel WHERE gebruikersnaam = 'nieuw'").one()
                self.assertEqual(tuple(rij), ("medewerker", 1))
                alembic("downgrade", "e5b9c1d3a7f2")
                kolommen = {k["name"] for k in inspect(engine).get_columns("personeel")}
                self.assertFalse({"rol", "actief"} & kolommen)
                with engine.connect() as conn:
                    self.assertEqual(conn.exec_driver_sql("SELECT count(*) FROM personeel").scalar(), 2)
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
