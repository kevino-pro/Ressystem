import unittest
from datetime import timedelta

from app import create_app
from app.config import Config
from app.database import get_db, metadata, reserveringen, verwerk_reservering, wijs_tafels_toe
from app.security import reset_rate_limits
from tests.hulp import log_in

DAG = "2030-01-01"  # een dinsdag


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    CSRF_ENABLED = False
    RESTAURANT_CONFIG = "tests/restaurant_vast.toml"


class OverzichtTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)
        with self.app.app_context():
            conn = get_db()
            metadata.create_all(conn)
            conn.commit()
            with conn.begin():
                conn.execute(reserveringen.delete())
            gasten = [("Ann", "18:00", 4), ("Bas", "18:00", 2), ("Cor", "19:00", 5), ("Dirk", "13:00", 3)]
            self.ids = {}
            for i, (naam, tijd, aantal) in enumerate(gasten):
                self.ids[naam] = verwerk_reservering(conn, 69, naam, f"{naam}@example.com", f"06000000{i:02d}",
                                                     DAG, tijd, aantal, zitduur_minuten=90)
            wijs_tafels_toe(conn, self.ids["Ann"], ["1a"], self.app.config["PLATTEGROND"], 90)
            verwerk_reservering(conn, 69, "Eva", "eva@example.com", "0611111111", "2030-01-02", "18:00", 2,
                                zitduur_minuten=90)
        self.client = self.app.test_client()
        log_in(self.app, self.client)

    def pagina(self, query=f"?datum={DAG}"):
        antwoord = self.client.get("/overzicht" + query)
        return antwoord.status_code, antwoord.get_data(as_text=True)

    def test_alleen_na_inloggen(self):
        client = self.app.test_client()
        self.assertEqual(client.get("/overzicht").status_code, 302)

    def test_dag_en_tellers(self):
        status, html = self.pagina()
        self.assertEqual(status, 200)
        self.assertIn("Dinsdag 1 januari 2030", html)
        self.assertIn("<small>Reserveringen</small><b>4</b>", html)
        self.assertIn("<small>Gasten</small><b>14</b>", html)
        self.assertIn("Drukste moment (19:00)", html)  # 18:00 (6) en 19:00 (5) overlappen: 11
        self.assertIn("<b>11 / 69</b>", html)
        self.assertIn("<small>Nog zonder tafel</small><b>3</b>", html)
        self.assertNotIn("Eva", html)  # andere dag

    def test_gegroepeerd_per_tijd(self):
        _, html = self.pagina()
        self.assertLess(html.index("<b>13:00</b>"), html.index("<b>18:00</b>"))
        self.assertIn("2 reserveringen · 6 gasten", html)
        self.assertIn("Tafel 1a", html)
        self.assertIn(f'href="/plattegrond?datum={DAG}&amp;tijd=18:00"', html)

    def test_dagnavigatie(self):
        _, html = self.pagina()
        self.assertIn('href="/overzicht?datum=2029-12-31"', html)
        self.assertIn('href="/overzicht?datum=2030-01-02"', html)

    def test_zonder_datum_vandaag(self):
        status, html = self.pagina("")
        self.assertEqual(status, 200)
        vandaag = self.app.config["REGELS"].nu().date()
        self.assertIn(f'value="{vandaag.isoformat()}"', html)
        self.assertIn(f'href="/overzicht?datum={(vandaag + timedelta(days=1)).isoformat()}"', html)

    def test_ongeldige_datum(self):
        self.assertEqual(self.pagina("?datum=morgen")[0], 400)

    def test_lege_dag(self):
        _, html = self.pagina("?datum=2030-01-08")
        self.assertIn("Geen reserveringen op deze dag.", html)
        self.assertIn("<b>0 / 69</b>", html)

    def test_verwijderen_achter_menu(self):
        _, html = self.pagina()
        self.assertEqual(html.count("Reservering verwijderen"), 4)
        self.assertIn("<details>", html)


if __name__ == "__main__":
    unittest.main()
