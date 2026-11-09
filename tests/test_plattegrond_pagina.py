import re
import unittest

from sqlalchemy import insert

from app import create_app
from app.config import Config
from app.database import get_db, init_db, reserveringen, tafeltoewijzingen, wijs_tafels_toe

KWAADAARDIGE_NAAM = "<script>window.GEHACKT=1</script>"


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    ADMIN_INITIAL_PASSWORD = "test-admin-pw"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    CSRF_ENABLED = False
    RESTAURANT_CONFIG = "tests/restaurant_vast.toml"


class ZonderPlattegrondConfig(TestConfig):
    RESTAURANT_CONFIG = "tests/fixtures/restaurant_test.toml"


def maak_client(config, ingelogd=True):
    app = create_app(config)
    client = app.test_client()
    if ingelogd:
        with client.session_transaction() as sessie:
            sessie["ingelogd"] = True
    return app, client


class PlattegrondPaginaTests(unittest.TestCase):
    def setUp(self):
        self.app, self.client = maak_client(TestConfig)
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():  # de in-memory database wordt gedeeld tussen tests
                conn.execute(tafeltoewijzingen.delete())
                conn.execute(reserveringen.delete())

    def reservering(self, rid, naam="Jan", tijd="19:00", aantal=2, tafels=()):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=rid, naam=naam, email=f"{rid}@example.com", telefoon="0612345678",
                    datum="2030-01-01", tijd=tijd, aantal=aantal))
            if tafels:
                wijs_tafels_toe(conn, rid, list(tafels), self.app.config["PLATTEGROND"], 90)

    def pagina(self, query="?datum=2030-01-01&tijd=19:30"):
        antwoord = self.client.get("/plattegrond" + query)
        return antwoord.status_code, antwoord.get_data(as_text=True)

    def test_alleen_na_inloggen(self):
        _, client = maak_client(TestConfig, ingelogd=False)
        antwoord = client.get("/plattegrond")
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn("/login", antwoord.headers["Location"])

    def test_404_zonder_plattegrond(self):
        _, client = maak_client(ZonderPlattegrondConfig)
        self.assertEqual(client.get("/plattegrond").status_code, 404)

    def test_toont_alle_tafels(self):
        status, html = self.pagina()
        self.assertEqual(status, 200)
        self.assertEqual(len(re.findall(r'data-tafel="', html)), 22)
        self.assertIn('data-tafel="10a"', html)
        self.assertIn("Meterkast", html)

    def test_zonder_datum_en_tijd(self):
        status, _ = self.pagina("")
        self.assertEqual(status, 200)

    def test_ongeldige_datum_of_tijd(self):
        for query in ("?datum=morgen", "?datum=2030-02-30", "?datum=2030-01-01&tijd=7uur",
                      "?datum=2030-01-01&tijd=25:00"):
            with self.subTest(query=query):
                self.assertEqual(self.pagina(query)[0], 400)

    def test_bezette_tafel_om_dit_tijdstip(self):
        self.reservering("a", naam="Familie Bakker", tijd="19:00", tafels=["2"])
        _, html = self.pagina("?datum=2030-01-01&tijd=19:30")
        self.assertIn("Familie Bakker", html)
        self.assertIn("bezet om 19:30", html)
        _, html_later = self.pagina("?datum=2030-01-01&tijd=20:30")  # 19:00 + 90 min is voorbij
        tafel_2 = re.search(r'data-tafel="2".*?</g>', html_later, re.S).group(0)
        self.assertNotIn("Familie Bakker", tafel_2)

    def test_reservering_zonder_tafel_valt_op(self):
        self.reservering("a", tijd="19:00")
        _, html = self.pagina()
        self.assertIn("Nog geen tafel", html)

    def test_naam_wordt_ge_escaped(self):
        self.reservering("a", naam=KWAADAARDIGE_NAAM, tafels=["1a"])
        _, html = self.pagina()
        self.assertNotIn(KWAADAARDIGE_NAAM, html)
        self.assertIn("&lt;script&gt;", html)

    def test_overzicht_linkt_naar_plattegrond(self):
        html = self.client.get("/overzicht").get_data(as_text=True)
        self.assertIn('href="/plattegrond?datum=', html)
        _, client = maak_client(ZonderPlattegrondConfig)
        self.assertNotIn("/plattegrond", client.get("/overzicht").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
