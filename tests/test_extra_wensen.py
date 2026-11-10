"""Opmerking en kinderstoelen bij een reservering (deel 2, fase 1)."""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from datetime import timedelta
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app import create_app
from app.config import Config
from app.database import (
    KinderstoelVolFout, get_db, haal_reservering_op, init_db, reserveringen, verwerk_reservering,
)
from app.reserveringsregels import RegelFout, ReserveringsRegels
from app.schemas import ReserveringSchema
from app.security import reset_rate_limits
from tests.hulp import log_in

PROJECTMAP = Path(__file__).resolve().parent.parent


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    ADMIN_INITIAL_PASSWORD = "test-admin-wachtwoord"
    RESTAURANT_CONFIG = "restaurants/wpl.toml"  # 2 kinderstoelen, zitduur 60


class Basis(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)
        self.regels = self.app.config["REGELS"]
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():
                conn.execute(reserveringen.delete())
        self.client = self.app.test_client()
        self.client.environ_base["HTTP_ACCEPT_LANGUAGE"] = "nl"  # deze tests controleren de Nederlandse teksten
        html = self.client.get("/").get_data(as_text=True)
        self.headers = {"X-CSRF-Token": re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)}
        dag = self.regels.nu().date() + timedelta(days=7)
        self.dinsdag = dag + timedelta(days=(1 - dag.weekday()) % 7)
        self.teller = 0
        patcher = mock.patch("app.routes.web.stuur_bevestigingsmail_async")
        patcher.start()
        self.addCleanup(patcher.stop)

    def boek(self, tijd="18:00", aantal=2, **extra):
        self.teller += 1
        payload = {"naam": f"Gast {self.teller}", "email": f"gast{self.teller}@example.com",
                   "telefoon": f"06123456{self.teller:02d}", "datum": self.dinsdag.isoformat(),
                   "tijd": tijd, "aantal": aantal, "privacy_akkoord": True, **extra}
        return self.client.post("/reservering", json=payload, headers=self.headers)

    def opgeslagen(self, antwoord):
        with self.app.app_context():
            return haal_reservering_op(get_db(), antwoord.get_json()["id"])


class FormulierTests(Basis):
    def test_velden_op_het_formulier(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn('<select id="kinderstoelen">', html)
        self.assertEqual(html.count("<option value="), 3)  # Geen, 1, 2
        self.assertIn('<textarea id="opmerking"', html)
        self.assertIn('maxlength="300"', html)

    def test_zonder_kinderstoelen_geen_keuze(self):
        class ZonderConfig(TestConfig):
            RESTAURANT_CONFIG = "tests/restaurant_vast.toml"
        html = create_app(ZonderConfig).test_client().get("/").get_data(as_text=True)
        self.assertNotIn('id="kinderstoelen"', html)
        self.assertIn('<textarea id="opmerking"', html)


class OpslaanTests(Basis):
    def test_opmerking_en_kinderstoelen_worden_bewaard(self):
        antwoord = self.boek(opmerking="  We vieren\neen verjaardag  ", kinderstoelen=1)
        self.assertEqual(antwoord.status_code, 200, antwoord.get_json())
        r = self.opgeslagen(antwoord)
        self.assertEqual(r["opmerking"], "We vieren een verjaardag")
        self.assertEqual(r["kinderstoelen"], 1)

    def test_zonder_extra_velden_zoals_vroeger(self):
        r = self.opgeslagen(self.boek())
        self.assertIsNone(r["opmerking"])
        self.assertEqual(r["kinderstoelen"], 0)

    def test_lege_opmerking_wordt_niets(self):
        self.assertIsNone(self.opgeslagen(self.boek(opmerking="   "))["opmerking"])

    def test_opmerking_te_lang(self):
        antwoord = self.boek(opmerking="x" * 301)
        self.assertEqual(antwoord.status_code, 422)
        self.assertIn("300 tekens", antwoord.get_json()["bericht"])

    def test_meer_kinderstoelen_dan_er_zijn(self):
        antwoord = self.boek(kinderstoelen=3)
        self.assertEqual(antwoord.status_code, 400)
        self.assertIn("maximaal 2 kinderstoelen", antwoord.get_json()["bericht"])

    def test_kinderstoelen_tellen_over_de_zitduur(self):
        self.assertEqual(self.boek("18:00", kinderstoelen=2).status_code, 200)
        vol = self.boek("18:30", kinderstoelen=1)  # 18:00-groep zit er tot 19:00
        self.assertEqual(vol.status_code, 400)
        self.assertIn("kinderstoelen al gereserveerd", vol.get_json()["bericht"])
        self.assertEqual(self.boek("18:30").status_code, 200)  # zonder kinderstoel kan het wel
        self.assertEqual(self.boek("19:00", kinderstoelen=2).status_code, 200)  # na een uur weer vrij

    def test_opmerking_wordt_ge_escaped(self):
        self.boek(opmerking="<script>alert(1)</script>", kinderstoelen=1)
        log_in(self.app, self.client)
        html = self.client.get(f"/overzicht?datum={self.dinsdag}").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertIn("1 kinderstoel<", html)


class RegelTests(unittest.TestCase):
    OPEN = {"dinsdag": [["12:00", "20:00"]]}

    def test_zonder_kinderstoelen_in_het_restaurant(self):
        regels = ReserveringsRegels(openingstijden=self.OPEN)
        self.assertEqual(regels.kinderstoelen, 0)
        with self.assertRaises(RegelFout) as fout:
            regels.controleer(regels.nu().date() + timedelta(days=8), __import__("datetime").time(18, 0), 2,
                              kinderstoelen=1)
        self.assertIn("geen kinderstoel", fout.exception.bericht)

    def test_schema(self):
        basis = {"naam": "Jan", "email": "jan@example.com", "telefoon": "0612345678",
                 "datum": "2030-01-01", "tijd": "18:00", "aantal": 2, "privacy_akkoord": True}
        self.assertIsNone(ReserveringSchema(**basis).opmerking)
        self.assertEqual(ReserveringSchema(**basis, opmerking="a\tb\x00c").opmerking, "a b c")
        for fout in ({"kinderstoelen": -1}, {"opmerking": 5}, {"opmerking": "x" * 301}):
            with self.subTest(fout=fout), self.assertRaises(ValueError):
                ReserveringSchema(**basis, **fout)


class DatabaseTests(Basis):
    def test_zonder_maximum_geen_controle(self):
        with self.app.app_context():
            conn = get_db()
            for i in range(3):  # zoals de AI-route: max_kinderstoelen None
                verwerk_reservering(conn, 69, f"G{i}", f"g{i}@example.com", f"06111111{i:02d}",
                                    self.dinsdag.isoformat(), "18:00", 2, zitduur_minuten=60, kinderstoelen=2)
            with self.assertRaises(KinderstoelVolFout):
                verwerk_reservering(conn, 69, "G9", "g9@example.com", "0611111199",
                                    self.dinsdag.isoformat(), "18:00", 2, zitduur_minuten=60,
                                    kinderstoelen=1, max_kinderstoelen=2)


class MigratieTests(unittest.TestCase):
    def test_bestaande_reserveringen_blijven(self):
        with tempfile.TemporaryDirectory() as map_:
            url = f"sqlite:///{Path(map_) / 'migratie.db'}"
            omgeving = {**os.environ, "MIGRATION_DATABASE_URL": url}
            omgeving.pop("ALLOW_PROD_MIGRATE", None)

            def alembic(*args):
                resultaat = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=PROJECTMAP,
                                           env=omgeving, capture_output=True, text=True)
                self.assertEqual(resultaat.returncode, 0, resultaat.stderr)

            alembic("upgrade", "c3f1a7d2e9b4")
            engine = create_engine(url)
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO reserveringen (id, naam, email, telefoon, datum, tijd, aantal) "
                                  "VALUES ('oud', 'Oud', 'o@example.com', '0612345678', '2030-01-01', '18:00', 4)"))
            alembic("upgrade", "head")
            with engine.connect() as conn:
                rij = conn.execute(text("SELECT kinderstoelen, opmerking, allergieen FROM reserveringen")).one()
            self.assertEqual(tuple(rij), (0, None, None))
            alembic("downgrade", "c3f1a7d2e9b4")
            kolommen = {k["name"] for k in inspect(engine).get_columns("reserveringen")}
            self.assertNotIn("kinderstoelen", kolommen)
            with engine.connect() as conn:
                self.assertEqual(conn.execute(text("SELECT count(*) FROM reserveringen")).scalar(), 1)
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
