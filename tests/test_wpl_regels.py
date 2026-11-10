"""De echte regels van Den Haag in restaurants/wpl.toml (afgesproken met de eigenaar op 8 nov 2026).

De andere tests gebruiken tests/restaurant_vast.toml, zodat ze niet breken als wpl.toml verandert.
Deze tests controleren juist wat er in wpl.toml staat.
"""
import unittest
from datetime import datetime, time, timedelta

from app import create_app
from app.config import Config
from app.database import get_db, init_db, reserveringen, verwerk_reservering
from app.reserveringsregels import RegelFout
from app.security import reset_rate_limits


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    RESTAURANT_CONFIG = "restaurants/wpl.toml"


class WplRegelsTests(unittest.TestCase):
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
        dag = self.regels.nu().date() + timedelta(days=7)
        self.dinsdag = dag + timedelta(days=(1 - dag.weekday()) % 7)

    def test_een_uur_en_vijftien_personen(self):
        self.assertEqual(self.regels.zitduur_minuten, 60)
        self.assertEqual(self.regels.max_personen_per_boeking, 15)
        self.assertEqual(self.regels.max_gasten_tegelijk, 69)

    def test_laatste_begintijd_20_uur(self):
        for i in range(7):
            dag = self.dinsdag + timedelta(days=i)
            tijden = self.regels.knoptijden_op(dag)
            with self.subTest(dag=dag.strftime("%A")):
                if dag.weekday() == 0:
                    self.assertEqual(tijden, [])  # maandag dicht
                else:
                    self.assertEqual((tijden[0], tijden[-1]), (time(12, 0), time(20, 0)))
                    self.assertEqual(len(tijden), 17)

    def test_controle_bij_versturen(self):
        nu = datetime.combine(self.dinsdag - timedelta(days=1), time(12, 0), tzinfo=self.regels.zone)
        self.regels.controleer(self.dinsdag, time(20, 0), 15, nu=nu)
        for tijdstip, aantal in ((time(20, 15), 2), (time(19, 0), 16)):
            with self.subTest(tijd=tijdstip, aantal=aantal), self.assertRaises(RegelFout):
                self.regels.controleer(self.dinsdag, tijdstip, aantal, nu=nu)

    def test_formulier(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertEqual(html.count('class="keuze" data-aantal='), 15)
        self.assertIn("1 uur", html)
        self.assertNotIn("1,5 uur", html)
        self.assertIn("const ZITDUUR = 60;", html)
        self.assertIn("Met meer dan 15 personen? Bel", html)
        self.assertIn("vooraf bestellen", html)

    def test_na_een_uur_weer_vrij(self):
        with self.app.app_context():
            for i in range(5):  # 5 x 13 = 65 gasten om 18:00
                verwerk_reservering(get_db(), 69, f"Gast {i}", f"gast{i}@example.com", f"061234567{i}",
                                    self.dinsdag.isoformat(), "18:00", 13, zitduur_minuten=60)
        tijden = {t["tijd"]: t for t in self.client.get(
            f"/beschikbaarheid?datum={self.dinsdag}&aantal=15").get_json()["tijden"]}
        self.assertFalse(tijden["18:30"]["beschikbaar"])  # 18:00-groep zit er nog
        self.assertTrue(tijden["19:00"]["beschikbaar"])   # na een uur is de tafel weer vrij
        self.assertEqual(tijden["20:00"]["vrij"], 69)


if __name__ == "__main__":
    unittest.main()
