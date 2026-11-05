import re
import unittest
from unittest import mock

from pydantic import ValidationError

from app import create_app
from app.config import Config
from app.database import init_db
from app.normalisatie import normaliseer_email, normaliseer_naam, normaliseer_telefoon
from app.routes import api as api_module
from app.schemas import AIReserveringExtractieSchema, ReserveringSchema
from app.security import reset_rate_limits

GELDIGE_NUMMERS = ("0612345678", "06-12345678", "070 406 2928", "+31 6 1234 5678", "0031612345678", "+32 2 123 45 67")
ONGELDIGE_NUMMERS = ("abcdefghij", "06-1234abcd", "12345678", "++31612345678", "06 1234 5678 ext 2", "(070) 4062928", "")


def formulier(**extra):
    gegevens = {
        "naam": "Test Gast", "email": "gast@example.com", "telefoon": "0612345678",
        "datum": "2030-01-01", "tijd": "18:00", "aantal": 2, "privacy_akkoord": True,
    }
    gegevens.update(extra)
    return gegevens


class NormalisatieTests(unittest.TestCase):
    def test_email(self):
        self.assertEqual(normaliseer_email("  Gast@Example.COM "), "gast@example.com")

    def test_telefoon_varianten_zijn_gelijk(self):
        varianten = ("0612345678", "06-12345678", "06 1234 5678", "+31 6 1234 5678", "+31612345678", "0031612345678")
        self.assertEqual({normaliseer_telefoon(nummer) for nummer in varianten}, {"0612345678"})

    def test_buitenlands_nummer_blijft_herkenbaar(self):
        self.assertEqual(normaliseer_telefoon("+32 2 123 45 67"), "003221234567")

    def test_naam(self):
        self.assertEqual(normaliseer_naam("  Jan   JANSEN "), "jan jansen")


class TelefoonSchemaTests(unittest.TestCase):
    def test_geldige_nummers(self):
        for nummer in GELDIGE_NUMMERS:
            with self.subTest(nummer=nummer):
                self.assertEqual(ReserveringSchema(**formulier(telefoon=nummer)).telefoon, nummer)
                self.assertEqual(AIReserveringExtractieSchema(telefoon=nummer).telefoon, nummer)

    def test_ongeldige_nummers(self):
        for nummer in ONGELDIGE_NUMMERS:
            with self.subTest(nummer=nummer):
                with self.assertRaises(ValidationError):
                    ReserveringSchema(**formulier(telefoon=nummer))
                with self.assertRaises(ValidationError):
                    AIReserveringExtractieSchema(telefoon=nummer)

    def test_spaties_eromheen_worden_weggehaald(self):
        self.assertEqual(ReserveringSchema(**formulier(telefoon=" 0612345678 ")).telefoon, "0612345678")

    def test_ai_mag_telefoon_weglaten(self):
        self.assertIsNone(AIReserveringExtractieSchema().telefoon)


class NaamSchemaTests(unittest.TestCase):
    def test_toegestane_namen(self):
        for naam in ("D'Souza", "Jean-Luc", "\u00c9lise van den Berg", "Tafel 12 bedrijfsuitje"):
            with self.subTest(naam=naam):
                self.assertEqual(ReserveringSchema(**formulier(naam=naam)).naam, naam)

    def test_spaties_worden_opgeschoond(self):
        self.assertEqual(ReserveringSchema(**formulier(naam="  Jan   Jansen ")).naam, "Jan Jansen")

    def test_geweigerde_namen(self):
        for naam in ("  ", "--", "12", "Jan\x00Jansen", "a"):
            with self.subTest(naam=naam), self.assertRaises(ValidationError):
                ReserveringSchema(**formulier(naam=naam))

    def test_maximaal_100_tekens(self):
        ReserveringSchema(**formulier(naam="a" * 100))
        with self.assertRaises(ValidationError):
            ReserveringSchema(**formulier(naam="a" * 101))


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


class RouteMeldingTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)
        with self.app.app_context():
            init_db()
        self.client = self.app.test_client()
        html = self.client.get("/login").get_data(as_text=True)
        self.headers = {"X-CSRF-Token": re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)}

    def test_formulier_telefoon_met_letters(self):
        antwoord = self.client.post("/reservering", headers=self.headers, json=formulier(telefoon="abcdefghij"))
        self.assertEqual(antwoord.status_code, 422)
        self.assertIn("geldig telefoonnummer", antwoord.get_json()["bericht"])
        self.assertIn("telefoon", antwoord.get_json()["velden"])

    def test_formulier_lege_naam(self):
        antwoord = self.client.post("/reservering", headers=self.headers, json=formulier(naam="   "))
        self.assertEqual(antwoord.status_code, 422)
        self.assertEqual(antwoord.get_json()["bericht"], "Vul je naam in.")

    def test_ai_telefoon_met_letters_geeft_geen_500(self):
        def nep_ai(_tekst):
            return AIReserveringExtractieSchema(
                naam="Test Gast", email="gast@example.com", telefoon="abcdefghij",
                datum="2030-01-01", tijd="18:00", aantal=2,
            )
        with mock.patch.object(api_module, "verwerk_tekst_met_anthropic", side_effect=nep_ai):
            antwoord = self.client.post("/api/v1/ai-reservering", headers={"X-API-Key": "test-key"},
                                        json={"klant_tekst": "Tafel voor twee graag"})
        self.assertEqual(antwoord.status_code, 400)
        self.assertIn("telefoon", antwoord.get_json()["ontbrekende_velden"])

    def test_formulier_toont_telefoonpatroon(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn('inputmode="tel"', html)
        self.assertIn('pattern="\\+?[0-9][0-9 \\-]*"', html)
        self.assertNotIn("alertBox.innerHTML = errorMsg", html)


if __name__ == "__main__":
    unittest.main()
