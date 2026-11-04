import tempfile
import unittest
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from app import create_app
from app.config import Config
from app.reserveringsregels import RegelFout, ReserveringsRegels, laad_regels

PROJECTMAP = Path(__file__).resolve().parent.parent
AMSTERDAM = ZoneInfo("Europe/Amsterdam")
# Dinsdag 3 november 2026, 15:00 lokale tijd.
NU = datetime(2026, 11, 3, 15, 0, tzinfo=AMSTERDAM)


def regels(**extra):
    basis = {
        "slot_minuten": 15,
        "min_minuten_vooraf": 60,
        "max_dagen_vooruit": 90,
        "max_personen_per_boeking": 8,
        "sluitingsdagen": [date(2026, 12, 25)],
        "openingstijden": {
            "maandag": [],
            "dinsdag": [["17:00", "20:30"]],
            "zaterdag": [["12:00", "14:30"], ["17:00", "21:00"]],
        },
    }
    basis.update(extra)
    return ReserveringsRegels.model_validate(basis)


class ControleerTests(unittest.TestCase):
    def test_geldig_verzoek(self):
        regels().controleer(date(2026, 11, 3), time(19, 0), 4, nu=NU)

    def test_gesloten_weekdag(self):
        with self.assertRaisesRegex(RegelFout, "maandag gesloten"):
            regels().controleer(date(2026, 11, 9), time(19, 0), 2, nu=NU)

    def test_weekdag_zonder_regel_is_gesloten(self):
        with self.assertRaises(RegelFout):
            regels().controleer(date(2026, 11, 4), time(19, 0), 2, nu=NU)  # woensdag

    def test_buiten_venster(self):
        for tijdstip in (time(16, 45), time(20, 45)):
            with self.subTest(tijdstip=tijdstip), self.assertRaisesRegex(RegelFout, "17:00-20:30"):
                regels().controleer(date(2026, 11, 3), tijdstip, 2, nu=NU)

    def test_grenzen_van_venster_mogen(self):
        for tijdstip in (time(17, 0), time(20, 30)):
            regels().controleer(date(2026, 11, 3), tijdstip, 2, nu=NU)

    def test_twee_vensters_op_een_dag(self):
        zaterdag = date(2026, 11, 7)
        regels().controleer(zaterdag, time(13, 0), 2, nu=NU)
        with self.assertRaises(RegelFout):
            regels().controleer(zaterdag, time(15, 30), 2, nu=NU)

    def test_tijd_moet_op_slot_vallen(self):
        with self.assertRaisesRegex(RegelFout, "per 15 minuten"):
            regels().controleer(date(2026, 11, 3), time(19, 1), 2, nu=NU)

    def test_verleden_en_te_kort_van_tevoren(self):
        with self.assertRaisesRegex(RegelFout, "verleden"):
            regels().controleer(date(2026, 11, 2), time(19, 0), 2, nu=NU)
        with self.assertRaisesRegex(RegelFout, "60 minuten"):
            regels().controleer(date(2026, 11, 3), time(15, 45), 2, nu=NU.replace(hour=15))

    def test_te_ver_vooruit(self):
        with self.assertRaisesRegex(RegelFout, "90 dagen"):
            regels().controleer(date(2027, 3, 2), time(19, 0), 2, nu=NU)

    def test_sluitingsdag(self):
        with self.assertRaisesRegex(RegelFout, "gesloten"):
            regels().controleer(date(2026, 12, 25), time(19, 0), 2, nu=NU)

    def test_te_grote_groep(self):
        with self.assertRaisesRegex(RegelFout, "maximaal 8"):
            regels().controleer(date(2026, 11, 3), time(19, 0), 9, nu=NU)

    def test_nu_gebruikt_tijdzone_van_restaurant(self):
        self.assertEqual(regels().nu().tzinfo, AMSTERDAM)


class ValidatieTests(unittest.TestCase):
    def test_onbekende_weekdag(self):
        with self.assertRaises(ValueError):
            regels(openingstijden={"maandagg": []})

    def test_begin_na_einde(self):
        with self.assertRaises(ValueError):
            regels(openingstijden={"dinsdag": [["21:00", "17:00"]]})

    def test_venster_niet_op_slotgrens(self):
        with self.assertRaises(ValueError):
            regels(openingstijden={"dinsdag": [["17:10", "20:30"]]})

    def test_ongeldige_slotlengte_en_tijdzone(self):
        with self.assertRaises(ValueError):
            regels(slot_minuten=7)
        with self.assertRaises(ValueError):
            regels(tijdzone="Europe/Nergens")


class LaadRegelsTests(unittest.TestCase):
    def test_alle_restaurantbestanden_zijn_geldig(self):
        bestanden = sorted((PROJECTMAP / "restaurants").glob("*.toml"))
        self.assertTrue(bestanden)
        for pad in bestanden:
            with self.subTest(bestand=pad.name):
                laad_regels(pad)

    def test_ontbrekend_bestand(self):
        with self.assertRaisesRegex(RuntimeError, "niet gevonden"):
            laad_regels(PROJECTMAP / "restaurants" / "bestaat-niet.toml")

    def test_kapotte_toml(self):
        with tempfile.TemporaryDirectory() as map_:
            pad = Path(map_) / "kapot.toml"
            pad.write_text("[reserveringen\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "geen geldige TOML"):
                laad_regels(pad)


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0


class AppTests(unittest.TestCase):
    def test_app_laadt_regels(self):
        app = create_app(TestConfig)
        self.assertIsInstance(app.config["REGELS"], ReserveringsRegels)

    def test_productie_zonder_restaurant_config_start_niet(self):
        class Productie(TestConfig):
            APP_ENV = "production"
            DATABASE_URL_IS_DEFAULT = False
            RESTAURANT_CONFIG_IS_DEFAULT = True
        with self.assertRaisesRegex(RuntimeError, "RESTAURANT_CONFIG"):
            create_app(Productie)


if __name__ == "__main__":
    unittest.main()
