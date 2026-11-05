import re
import shutil
import tempfile
import threading
import unittest
from unittest import mock

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

import app.database as database
from app import create_app
from app.config import Config
from app.database import (
    CapaciteitVolFout, DubbeleReserveringFout, get_db, init_db, metadata, reserveringen,
    verwerk_reservering, verwijder_reservering,
)
from app.routes import api as api_module
from app.schemas import AIReserveringExtractieSchema
from app.security import reset_rate_limits


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    ADMIN_INITIAL_PASSWORD = "test-admin-pw"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    RESTAURANT_CONFIG = "tests/fixtures/restaurant_test.toml"


def boek(naam="Jan Jansen", email="jan@example.com", telefoon="0612345678",
         datum="2030-01-01", tijd="19:00", aantal=2, maximum=10):
    return verwerk_reservering(get_db(), maximum, naam, email, telefoon, datum, tijd, aantal,
                               zitduur_minuten=120)


def aantal_rijen():
    conn = get_db()
    with conn.begin():
        return conn.execute(select(func.count()).select_from(reserveringen)).scalar()


class DubbeleReserveringTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        init_db()
        conn = get_db()
        with conn.begin():
            conn.execute(reserveringen.delete())

    def test_zelfde_email_andere_schrijfwijze(self):
        boek()
        with self.assertRaises(DubbeleReserveringFout):
            boek(naam="Iemand Anders", email=" JAN@Example.com", telefoon="0687654321")

    def test_zelfde_telefoon_andere_notatie(self):
        boek()
        with self.assertRaises(DubbeleReserveringFout):
            boek(naam="Iemand Anders", email="ander@example.com", telefoon="+31 6 1234 5678")

    def test_zelfde_naam_andere_gast_mag(self):
        boek()
        boek(naam="Jan Jansen", email="ander@example.com", telefoon="0687654321")
        self.assertEqual(aantal_rijen(), 2)

    def test_ander_aantal_personen_is_ook_dubbel(self):
        boek(aantal=2)
        with self.assertRaises(DubbeleReserveringFout):
            boek(aantal=4)

    def test_andere_tijd_of_datum_mag(self):
        boek()
        boek(tijd="19:15")
        boek(datum="2030-01-02")
        self.assertEqual(aantal_rijen(), 3)

    def test_andere_gast_zelfde_tijd_mag(self):
        boek()
        boek(naam="Piet Pieters", email="piet@example.com", telefoon="0687654321")
        self.assertEqual(aantal_rijen(), 2)

    def test_na_verwijderen_mag_het_weer(self):
        rid = boek()
        verwijder_reservering(get_db(), rid)
        boek()
        self.assertEqual(aantal_rijen(), 1)

    def test_dubbel_gaat_voor_vol(self):
        boek(aantal=10)
        with self.assertRaises(DubbeleReserveringFout):
            boek(aantal=2)
        with self.assertRaises(CapaciteitVolFout):
            boek(naam="Piet Pieters", email="piet@example.com", telefoon="0687654321")

    def test_melding_noemt_datum_en_tijd(self):
        boek(datum="2030-11-12")
        with self.assertRaises(DubbeleReserveringFout) as fout:
            boek(datum="2030-11-12")
        self.assertIn("12 november om 19:00", fout.exception.bericht)

    def test_oud_nummer_zonder_cijfers_matcht_niet_met_alles(self):
        # Oude records kunnen nog een telefoonnummer zonder cijfers hebben (van voor de telefoonregel).
        conn = get_db()
        with conn.begin():
            conn.execute(reserveringen.insert().values(
                id="oud", naam="Oude Gast", email="oud@example.com", telefoon="abcdefghij",
                datum="2030-01-01", tijd="19:00", aantal=2))
        boek()
        self.assertEqual(aantal_rijen(), 2)


class DubbeleReserveringRouteTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():
                conn.execute(reserveringen.delete())
        self.client = self.app.test_client()
        html = self.client.get("/login").get_data(as_text=True)
        self.headers = {"X-CSRF-Token": re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)}
        patcher = mock.patch("app.routes.web.stuur_bevestigingsmail_async")
        self.mail = patcher.start()
        self.addCleanup(patcher.stop)

    def _formulier(self):
        return self.client.post("/reservering", headers=self.headers, json={
            "naam": "Jan Jansen", "email": "jan@example.com", "telefoon": "0612345678",
            "datum": "2030-01-01", "tijd": "19:00", "aantal": 2, "privacy_akkoord": True,
        })

    def test_formulier_tweede_keer_geeft_409_zonder_mail(self):
        self.assertEqual(self._formulier().status_code, 200)
        antwoord = self._formulier()
        self.assertEqual(antwoord.status_code, 409)
        self.assertIn("Je hebt al een reservering op 1 januari om 19:00", antwoord.get_json()["bericht"])
        self.assertEqual(self.mail.call_count, 1)
        with self.app.app_context():
            self.assertEqual(aantal_rijen(), 1)

    def test_ai_route_tweede_keer_geeft_409(self):
        extractie = AIReserveringExtractieSchema(
            naam="Jan Jansen", email="jan@example.com", telefoon="0612345678",
            datum="2030-01-01", tijd="19:00", aantal=2,
        )
        with mock.patch.object(api_module, "verwerk_tekst_met_anthropic", return_value=extractie), \
                mock.patch.object(api_module, "stuur_bevestigingsmail_async") as ai_mail:
            eerste = self.client.post("/api/v1/ai-reservering", headers={"X-API-Key": "test-key"},
                                      json={"klant_tekst": "Tafel voor twee graag"})
            tweede = self.client.post("/api/v1/ai-reservering", headers={"X-API-Key": "test-key"},
                                      json={"klant_tekst": "Tafel voor twee graag"})
        self.assertEqual(eerste.status_code, 201)
        self.assertEqual(tweede.status_code, 409)
        self.assertIn("geparsed_data", tweede.get_json())
        self.assertEqual(ai_mail.call_count, 1)


class GelijktijdigSqliteTests(unittest.TestCase):
    """Twee gelijktijdige pogingen op een echt SQLite-bestand: er mag er maar een worden opgeslagen."""

    def setUp(self):
        self._vorige_engine = database._engine
        database._engine = None  # de engine is proces-breed; deze test wil een eigen bestand
        self.map = tempfile.mkdtemp()

        class BestandConfig(TestConfig):
            DATABASE_URL = f"sqlite:///{self.map}/gelijktijdig.db"

        self.app = create_app(BestandConfig)
        with self.app.app_context():
            conn = get_db()
            metadata.create_all(conn)
            conn.commit()

    def tearDown(self):
        database._engine.dispose()
        database._engine = self._vorige_engine
        shutil.rmtree(self.map, ignore_errors=True)

    def test_twee_gelijktijdige_pogingen_geven_een_boeking(self):
        start = threading.Barrier(2)
        uitkomsten = []

        def poging():
            with self.app.app_context():
                start.wait()
                try:
                    boek()
                    uitkomsten.append("opgeslagen")
                except (DubbeleReserveringFout, OperationalError) as fout:
                    uitkomsten.append(type(fout).__name__)

        threads = [threading.Thread(target=poging) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertEqual(uitkomsten.count("opgeslagen"), 1, uitkomsten)
        with self.app.app_context():
            self.assertEqual(aantal_rijen(), 1)


if __name__ == "__main__":
    unittest.main()
