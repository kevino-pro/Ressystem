import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.config import Config
from app.privacy import Privacy, laad_privacy

PROJECTMAP = Path(__file__).resolve().parent.parent


def privacy(**extra):
    basis = {
        "verantwoordelijke": "Test B.V.",
        "adres": "Straat 1, 1234 AB Stad",
        "bijgewerkt": "2026-11-06",
        "verwerkers": [{"naam": "Render", "doel": "hosting", "locatie": "Europese Unie"}],
    }
    basis.update(extra)
    return Privacy.model_validate(basis)


class PrivacyValidatieTests(unittest.TestCase):
    def test_geldig(self):
        p = privacy(kvk="12345678")
        self.assertEqual(p.verwerkers[0].naam, "Render")
        self.assertEqual(str(p.bijgewerkt), "2026-11-06")

    def test_kvk_optioneel_maar_acht_cijfers(self):
        self.assertIsNone(privacy().kvk)
        for kvk in ("1234567", "123456789", "1234567a"):
            with self.subTest(kvk=kvk), self.assertRaises(ValueError):
                privacy(kvk=kvk)

    def test_minstens_een_verwerker(self):
        with self.assertRaises(ValueError):
            privacy(verwerkers=[])

    def test_onbekend_veld(self):
        with self.assertRaises(ValueError):
            privacy(website="x")

    def test_lege_velden(self):
        for veld in ("verantwoordelijke", "adres"):
            with self.subTest(veld=veld), self.assertRaises(ValueError):
                privacy(**{veld: ""})


class LaadPrivacyTests(unittest.TestCase):
    def test_alle_restaurantbestanden_hebben_geldige_privacy(self):
        for pad in sorted((PROJECTMAP / "restaurants").glob("*.toml")):
            with self.subTest(bestand=pad.name):
                self.assertIsNotNone(laad_privacy(pad), f"{pad.name} mist [privacy]")

    def test_wpl_den_haag(self):
        p = laad_privacy(PROJECTMAP / "restaurants" / "wpl.toml")
        self.assertIn("Den Haag", p.adres)
        self.assertIn("Resend", [v.naam for v in p.verwerkers])

    def test_zonder_sectie_none(self):
        self.assertIsNone(laad_privacy(PROJECTMAP / "tests" / "fixtures" / "restaurant_test.toml"))

    def test_fout_wordt_runtimeerror(self):
        with tempfile.TemporaryDirectory() as map_:
            pad = Path(map_) / "kapot.toml"
            pad.write_text('[privacy]\nverantwoordelijke = "X"\n', encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Privacygegevens in"):
                laad_privacy(pad)


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    DATABASE_URL_IS_DEFAULT = False
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    RESTAURANT_CONFIG = "tests/fixtures/restaurant_test.toml"
    RESTAURANT_CONFIG_IS_DEFAULT = False


class AppPrivacyTests(unittest.TestCase):
    def test_ontwikkeling_zonder_privacy_start(self):
        self.assertIsNone(create_app(TestConfig).config["PRIVACY"])

    def test_productie_zonder_privacy_start_niet(self):
        class Productie(TestConfig):
            APP_ENV = "production"
        with self.assertRaisesRegex(RuntimeError, r"\[privacy\]"):
            create_app(Productie)

    def test_productie_met_wpl_start(self):
        class Productie(TestConfig):
            APP_ENV = "production"
            RESTAURANT_CONFIG = "restaurants/wpl.toml"
        self.assertIsNotNone(create_app(Productie).config["PRIVACY"])


if __name__ == "__main__":
    unittest.main()
