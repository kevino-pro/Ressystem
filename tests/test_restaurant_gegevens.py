"""
Config per restaurant: naam, e-mail en telefoon uit [restaurant] van het restaurantbestand.
"""
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.config import Config
from app.restaurant import Restaurant, laad_restaurant

PROJECTMAP = Path(__file__).resolve().parent.parent
FIXTURE = PROJECTMAP / "tests" / "fixtures" / "restaurant_test.toml"


def restaurant(**extra):
    basis = {"naam": "Test Eethuis", "email": "info@eethuis.nl", "telefoon": "070-123 4567"}
    basis.update(extra)
    return Restaurant.model_validate(basis)


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    DATABASE_URL_IS_DEFAULT = False
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    RESTAURANT_CONFIG = "restaurants/wpl.toml"
    RESTAURANT_CONFIG_IS_DEFAULT = False
    # Oude manier (omgeving); het restaurantbestand moet hiervan winnen.
    RESTAURANT_NAAM = "Naam uit de omgeving"
    RESTAURANT_EMAIL = "omgeving@example.com"
    RESTAURANT_TELEFOON = "0600000000"


class RestaurantValidatieTests(unittest.TestCase):
    def test_geldig(self):
        r = restaurant(telefoon="+31 70 123 4567")
        self.assertEqual((r.naam, r.email, r.telefoon), ("Test Eethuis", "info@eethuis.nl", "+31 70 123 4567"))

    def test_naam_ongeldig(self):
        for naam in ("", " Eethuis", "x" * 61, "<b>Eethuis</b>", "Eet\nhuis"):
            with self.subTest(naam=naam), self.assertRaises(ValueError):
                restaurant(naam=naam)

    def test_email_ongeldig(self):
        for email in ("", "info", "info@eethuis", "info @eethuis.nl", "info@eethuis.nl\nBcc: x@y.nl"):
            with self.subTest(email=email), self.assertRaises(ValueError):
                restaurant(email=email)

    def test_telefoon_ongeldig(self):
        for telefoon in ("", "070-12345", "070-ABC-4567", "tel 0701234567", "0" * 16):
            with self.subTest(telefoon=telefoon), self.assertRaises(ValueError):
                restaurant(telefoon=telefoon)

    def test_onbekend_of_ontbrekend_veld(self):
        with self.assertRaises(ValueError):
            restaurant(website="https://eethuis.nl")
        with self.assertRaises(ValueError):
            Restaurant.model_validate({"naam": "Eethuis", "email": "info@eethuis.nl"})


class LaadRestaurantTests(unittest.TestCase):
    def test_alle_restaurantbestanden_hebben_restaurantgegevens(self):
        for pad in sorted((PROJECTMAP / "restaurants").glob("*.toml")):
            with self.subTest(bestand=pad.name):
                self.assertIsNotNone(laad_restaurant(pad), f"{pad.name} mist [restaurant]")

    def test_wpl_den_haag(self):
        r = laad_restaurant(PROJECTMAP / "restaurants" / "wpl.toml")
        self.assertEqual(r.naam, "Waroeng Padang Lapek")
        self.assertEqual(r.telefoon, "070-406 2928")

    def test_zonder_sectie_none(self):
        self.assertIsNone(laad_restaurant(FIXTURE))

    def test_fout_wordt_runtimeerror(self):
        with tempfile.TemporaryDirectory() as map_:
            pad = Path(map_) / "kapot.toml"
            pad.write_text('[restaurant]\nnaam = "X"\nemail = "geen-adres"\ntelefoon = "0701234567"\n', encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Restaurantgegevens in"):
                laad_restaurant(pad)


class AppRestaurantTests(unittest.TestCase):
    def test_restaurantbestand_wint_van_de_omgeving(self):
        config = create_app(TestConfig).config
        r = laad_restaurant(PROJECTMAP / "restaurants" / "wpl.toml")
        self.assertEqual(config["RESTAURANT_NAAM"], r.naam)
        self.assertEqual(config["RESTAURANT_EMAIL"], r.email)
        self.assertEqual(config["RESTAURANT_TELEFOON"], r.telefoon)

    def test_zonder_sectie_blijft_de_omgeving(self):
        class ZonderSectie(TestConfig):
            RESTAURANT_CONFIG = "tests/fixtures/restaurant_test.toml"
        config = create_app(ZonderSectie).config
        self.assertEqual(config["RESTAURANT_NAAM"], "Naam uit de omgeving")
        self.assertEqual(config["RESTAURANT_TELEFOON"], "0600000000")

    def test_productie_zonder_sectie_start_niet(self):
        with tempfile.TemporaryDirectory() as map_:
            pad = Path(map_) / "zonder_restaurant.toml"
            pad.write_text(FIXTURE.read_text(encoding="utf-8") + (
                '\n[privacy]\nverantwoordelijke = "Test B.V."\nadres = "Straat 1, 1234 AB Stad"\n'
                'bijgewerkt = 2026-11-11\n'
                'verwerkers = [{ naam = "Render", doel = "hosting", locatie = "Europese Unie" }]\n'), encoding="utf-8")

            class Productie(TestConfig):
                APP_ENV = "production"
                RESTAURANT_CONFIG = str(pad)
            with self.assertRaisesRegex(RuntimeError, r"\[restaurant\]"):
                create_app(Productie)

    def test_productie_met_wpl_start(self):
        class Productie(TestConfig):
            APP_ENV = "production"
        self.assertEqual(create_app(Productie).config["RESTAURANT_NAAM"], "Waroeng Padang Lapek")

    def test_pagina_toont_gegevens_uit_het_restaurantbestand(self):
        app = create_app(TestConfig)
        html = app.test_client().get("/", headers={"Accept-Language": "nl"}).get_data(as_text=True)
        self.assertIn("<h1>Waroeng Padang Lapek</h1>", html)
        self.assertIn('href="tel:070-406 2928"', html)
        self.assertIn("reserveringen@waroengpadang.nl", html)
        self.assertNotIn("Naam uit de omgeving", html)


if __name__ == "__main__":
    unittest.main()
