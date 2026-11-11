import re
import unittest
from datetime import timedelta

from app import create_app
from app.config import Config


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    RESTAURANT_CONFIG = "tests/restaurant_vast.toml"


class FormulierTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.html = self.app.test_client().get("/").get_data(as_text=True)
        self.regels = self.app.config["REGELS"]

    def test_stappen_en_knoppen(self):
        for tekst in ("Met hoeveel personen?", "Welke dag?", "Hoe laat?", "Je gegevens",
                      'id="tijden"', "/beschikbaarheid?datum=", "Reservering bevestigen"):
            with self.subTest(tekst=tekst):
                self.assertIn(tekst, self.html)
        self.assertEqual(len(re.findall(r'<option value="\d+"', self.html.split('id="aantal"')[1].split("</select>")[0])), 8)

    def test_zeven_dagen_met_gesloten_maandag(self):
        self.assertEqual(self.html.count('class="keuze" data-datum='), 7)
        vandaag = self.regels.nu().date()
        for i in range(7):
            dag = vandaag + timedelta(days=i)
            if dag.weekday() == 0:  # maandag is Den Haag dicht
                self.assertIn(f'data-datum="{dag.isoformat()}" aria-pressed="false" disabled', self.html)

    def test_kalender_tot_max_dagen_vooruit(self):
        laatste = self.regels.nu().date() + timedelta(days=self.regels.max_dagen_vooruit)
        self.assertIn(f'max="{laatste.isoformat()}"', self.html)

    def test_zitduur_en_huisstijl(self):
        self.assertIn("1,5 uur", self.html)
        self.assertIn("const ZITDUUR = 90;", self.html)
        self.assertIn("/static/css/huisstijl.css", self.html)
        self.assertNotIn("cdn.tailwindcss.com", self.html)

    def test_meldingen_nooit_als_html(self):
        self.assertNotIn("innerHTML", self.html)


if __name__ == "__main__":
    unittest.main()
