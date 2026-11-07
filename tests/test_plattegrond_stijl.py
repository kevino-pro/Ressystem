import re
import unittest

from sqlalchemy import insert

from app import create_app
from app.config import Config
from app.database import get_db, init_db, reserveringen, tafeltoewijzingen, wijs_tafels_toe


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    CSRF_ENABLED = False
    RESTAURANT_CONFIG = "restaurants/wpl.toml"


class PlattegrondStijlTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        with self.client.session_transaction() as sessie:
            sessie["ingelogd"] = True
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():
                conn.execute(tafeltoewijzingen.delete())
                conn.execute(reserveringen.delete())

    def reservering(self, rid, tijd, tafels=(), naam="Jan"):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=rid, naam=naam, email=f"{rid}@example.com", telefoon="0612345678",
                    datum="2030-01-01", tijd=tijd, aantal=2))
            if tafels:
                wijs_tafels_toe(conn, rid, list(tafels), self.app.config["PLATTEGROND"], 90)

    def pagina(self, query="?datum=2030-01-01&tijd=19:00"):
        return self.client.get("/plattegrond" + query).get_data(as_text=True)

    def tafel(self, html, nummer):
        return re.search(rf'data-tafel="{nummer}".*?</g>', html, re.S).group(0)

    def test_tijdknoppen_tot_de_laatste_gast_weg_is(self):
        html = self.pagina()
        knoppen = re.findall(r'tijd=(\d\d:\d\d)">', html)
        self.assertEqual(knoppen[0], "12:00")
        self.assertEqual(knoppen[-1], "20:30")  # laatste begintijd 19:30 + 90 min zitduur
        self.assertIn('class="pil aan" href="/plattegrond?datum=2030-01-01&amp;tijd=19:00"', html)

    def test_binnenkort_bezet(self):
        self.reservering("a", "19:30", ["4"], naam="Later")
        self.reservering("b", "18:00", ["2"], naam="Nu")
        html = self.pagina()
        self.assertIn("vanaf 19:30", self.tafel(html, "4"))
        self.assertIn('stroke-dasharray="5 4"', self.tafel(html, "4"))
        self.assertNotIn("stroke-dasharray", self.tafel(html, "2"))  # die is gewoon bezet
        self.assertIn("Nu", self.tafel(html, "2"))
        self.assertNotIn("vanaf", self.tafel(self.pagina("?datum=2030-01-01&tijd=18:00"), "4"))  # 19:30 is > 30 min

    def test_zonder_tafel_bovenaan(self):
        self.reservering("a", "18:00", ["1a"], naam="Met")
        self.reservering("b", "19:00", naam="Zonder")
        html = self.pagina()
        self.assertIn("Nog zonder tafel · 1", html)
        self.assertLess(html.index("19:00 · Zonder"), html.index("18:00 · Met"))

    def test_dagnavigatie_en_stijl(self):
        html = self.pagina()
        self.assertIn("Dinsdag 1 januari 2030", html)
        self.assertIn('href="/plattegrond?datum=2030-01-02"', html)
        self.assertIn('class="pil aan" href="/plattegrond?datum=2030-01-01"', html)  # menu: Plattegrond actief
        self.assertNotIn("cdn.tailwindcss.com", html)
        self.assertNotIn("Nu</a>", html)  # alleen vandaag


if __name__ == "__main__":
    unittest.main()
