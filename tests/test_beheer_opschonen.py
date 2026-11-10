import unittest
from datetime import date, timedelta
from unittest import mock

from sqlalchemy import insert, select
from sqlalchemy.exc import OperationalError

from app import create_app
from app.config import Config
from app.database import get_db, init_db, reserveringen, tafeltoewijzingen
from app.security import reset_rate_limits

SLEUTEL = "s" * 40


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    ADMIN_INITIAL_PASSWORD = "test-admin-pw"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    RETENTIE_DAGEN_AVG = 60
    BEHEER_API_KEY = SLEUTEL


class BeheerOpschonenTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():  # de in-memory database wordt gedeeld tussen tests
                conn.execute(tafeltoewijzingen.delete())
                conn.execute(reserveringen.delete())
        self.voeg_toe("oud", 100)
        self.voeg_toe("nieuw", -1)

    def voeg_toe(self, rid, dagen_geleden):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=rid, naam="N", email=f"{rid}@example.com", telefoon="0612345678",
                    datum=(date.today() - timedelta(days=dagen_geleden)).isoformat(),
                    tijd="19:00", aantal=2))

    def ids(self):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                return sorted(conn.execute(select(reserveringen.c.id)).scalars())

    def post(self, sleutel=SLEUTEL, client=None):
        headers = {"X-Beheer-Key": sleutel} if sleutel else {}
        return (client or self.client).post("/beheer/opschonen", headers=headers)

    def test_verwijdert_alleen_oude_reserveringen(self):
        antwoord = self.post()
        self.assertEqual(antwoord.status_code, 200)
        self.assertEqual(antwoord.get_json(), {"status": "succes", "verwijderd": 1, "allergieen_gewist": 0})
        self.assertEqual(self.ids(), ["nieuw"])

    def test_tweede_keer_niets_meer(self):
        self.post()
        self.assertEqual(self.post().get_json()["verwijderd"], 0)

    def test_zonder_of_met_foute_sleutel(self):
        for sleutel in (None, "fout", SLEUTEL + "x", "test-key"):
            with self.subTest(sleutel=sleutel):
                self.assertEqual(self.post(sleutel).status_code, 401)
        self.assertEqual(self.ids(), ["nieuw", "oud"])

    def test_n8n_sleutel_werkt_niet(self):
        antwoord = self.client.post("/beheer/opschonen", headers={"X-API-Key": "test-key"})
        self.assertEqual(antwoord.status_code, 401)

    def test_alleen_post(self):
        self.assertEqual(self.client.get("/beheer/opschonen", headers={"X-Beheer-Key": SLEUTEL}).status_code, 405)

    def test_route_uit_zonder_of_met_korte_sleutel(self):
        for waarde in ("", "kort"):
            with self.subTest(waarde=waarde):
                class ZonderSleutel(TestConfig):
                    BEHEER_API_KEY = waarde
                client = create_app(ZonderSleutel).test_client()
                self.assertEqual(self.post(waarde or None, client=client).status_code, 404)
        self.assertEqual(self.ids(), ["nieuw", "oud"])

    def test_rate_limit_na_tien_pogingen(self):
        for _ in range(10):
            self.post("fout")
        self.assertEqual(self.post().status_code, 429)

    def test_databasefout_geeft_503(self):
        with mock.patch("app.routes.beheer.tel_of_schoon_oude_reserveringen",
                        side_effect=OperationalError("x", {}, Exception("x"))):
            antwoord = self.post()
        self.assertEqual(antwoord.status_code, 503)
        self.assertNotIn("Traceback", antwoord.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
