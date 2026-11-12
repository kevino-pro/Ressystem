import unittest

from app import create_app
from app.config import Config
from app.privacy import Privacy

KWAADAARDIG = "<script>window.GEHACKT=1</script>"


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    RESTAURANT_CONFIG = "restaurants/wpl.toml"
    RETENTIE_DAGEN_AVG = 60


class ZonderPrivacyConfig(TestConfig):
    RESTAURANT_CONFIG = "tests/fixtures/restaurant_test.toml"


def pagina(config, privacy=None):
    app = create_app(config)
    if privacy is not None:
        app.config["PRIVACY"] = privacy
    antwoord = app.test_client().get("/privacy", headers={"Accept-Language": "nl"})  # deze tests lezen de Nederlandse tekst
    return antwoord.status_code, antwoord.get_data(as_text=True)


class PrivacyPaginaTests(unittest.TestCase):
    def test_toont_gegevens_uit_restaurantbestand(self):
        status, html = pagina(TestConfig)
        self.assertEqual(status, 200)
        config = create_app(TestConfig).config  # wat er in restaurants/wpl.toml staat
        p = config["PRIVACY"]
        verwacht = [p.verantwoordelijke, p.adres, *(v.naam for v in p.verwerkers),
                    "60 dagen", config["RESTAURANT_EMAIL"], "Autoriteit Persoonsgegevens"]
        for tekst in verwacht:
            with self.subTest(tekst=tekst):
                self.assertIn(tekst, html)

    def test_bijgewerkt_als_nederlandse_datum(self):
        _, html = pagina(TestConfig)
        datum = create_app(TestConfig).config["PRIVACY"].bijgewerkt
        self.assertIn(f"laatst bijgewerkt op {datum:%d-%m-%Y}", html)

    def test_kvk_alleen_als_ingevuld(self):
        _, html = pagina(TestConfig)
        self.assertNotIn("KvK", html)
        p = create_app(TestConfig).config["PRIVACY"].model_copy(update={"kvk": "12345678"})
        _, html = pagina(TestConfig, p)
        self.assertIn("KvK 12345678", html)

    def test_zonder_privacy_waarschuwing(self):
        status, html = pagina(ZonderPrivacyConfig)
        self.assertEqual(status, 200)
        self.assertIn("nog geen sectie [privacy]", html)
        self.assertNotIn("Wie helpen ons", html)

    def test_tekst_wordt_ge_escaped(self):
        p = Privacy.model_validate({
            "verantwoordelijke": KWAADAARDIG, "adres": "A", "bijgewerkt": "2026-11-06",
            "verwerkers": [{"naam": KWAADAARDIG, "doel": "d", "locatie": "l"}],
        })
        _, html = pagina(TestConfig, p)
        self.assertNotIn(KWAADAARDIG, html)
        self.assertIn("&lt;script&gt;", html)

    def test_html_is_gesloten(self):
        _, html = pagina(TestConfig)
        self.assertEqual(html.count("<main"), html.count("</main>"))
        self.assertEqual(html.count("<section"), html.count("</section>"))


if __name__ == "__main__":
    unittest.main()
