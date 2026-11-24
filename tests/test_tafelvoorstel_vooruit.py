"""Tafelvoorstel met het oog op grote groepen: kleine groepen laten de bank vrij voor de combinaties."""
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from app import create_app
from app.config import Config
from app.plattegrond import laad_plattegrond
from app.tafelvoorstel import Tafelvoorstel, laad_tafelvoorstel, past_nog, voorstellen

PROJECTMAP = Path(__file__).resolve().parent.parent
WPL = PROJECTMAP / "restaurants" / "wpl.toml"

PLATTEGROND = laad_plattegrond(WPL)
VOORSTEL = laad_tafelvoorstel(WPL, PLATTEGROND)
ZITDUUR = 60
BEGIN = datetime(2026, 11, 6, 9, 0)


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    RESTAURANT_CONFIG = "restaurants/wpl.toml"


def groep(reservering_id, aantal, minuut=0, tijd="18:00"):
    """Eén reservering; `minuut` houdt de volgorde van aanmaken bij (hoger = later gemaakt)."""
    return {
        "id": reservering_id,
        "tijd": tijd,
        "aantal": aantal,
        "status": "verwacht",
        "aangemaakt_op": BEGIN + timedelta(minutes=minuut),
    }


def groepen(hoeveel, aantal, tijd="18:00"):
    """`hoeveel` reserveringen van `aantal` personen om `tijd`, in de volgorde van aanmaken."""
    return [groep(f"groep-{nummer}", aantal, nummer, tijd) for nummer in range(hoeveel)]


class GroteGroepenTests(unittest.TestCase):
    def test_01_zes_groepen_van_vier_houden_alle_grote_groepen_mogelijk(self):
        self.assertEqual(create_app(TestConfig).config["TAFELVOORSTEL"], VOORSTEL)
        lijst = groepen(6, 4)
        for aantal in range(7, 16):
            with self.subTest(aantal=aantal):
                self.assertTrue(past_nog(lijst, {}, PLATTEGROND, VOORSTEL, ZITDUUR, "18:00", aantal))

    def test_02_zeven_groepen_van_vier_sluiten_13_en_14_uit(self):
        lijst = groepen(7, 4)
        for aantal in list(range(7, 13)) + [15]:
            with self.subTest(aantal=aantal):
                self.assertTrue(past_nog(lijst, {}, PLATTEGROND, VOORSTEL, ZITDUUR, "18:00", aantal))
        for aantal in (13, 14):
            with self.subTest(aantal=aantal):
                self.assertFalse(past_nog(lijst, {}, PLATTEGROND, VOORSTEL, ZITDUUR, "18:00", aantal))

    def test_03_groep_van_2_krijgt_tafel_8(self):
        self.assertEqual(voorstellen(groepen(1, 2), {}, PLATTEGROND, VOORSTEL, ZITDUUR), {"groep-0": ("8",)})

    def test_04_groep_van_3_krijgt_tafel_10a(self):
        self.assertEqual(voorstellen(groepen(1, 3), {}, PLATTEGROND, VOORSTEL, ZITDUUR), {"groep-0": ("10a",)})

    def test_05_groep_van_5_krijgt_tafel_4(self):
        self.assertEqual(voorstellen(groepen(1, 5), {}, PLATTEGROND, VOORSTEL, ZITDUUR), {"groep-0": ("4",)})

    def test_06_zonder_voorstel_tafel_1a(self):
        # Zonder combinaties in het voorstel geldt het oude gedrag: de eerste vrije tafel uit het bestand.
        self.assertEqual(
            voorstellen(groepen(1, 4), {}, PLATTEGROND, Tafelvoorstel(), ZITDUUR),
            {"groep-0": ("1a",)},
        )

    def test_07_latere_reservering_verschuift_bestaande_voorstellen_niet(self):
        drie = [groep("a", 4, 0), groep("b", 4, 1), groep("c", 7, 2)]
        voor = voorstellen(drie, {}, PLATTEGROND, VOORSTEL, ZITDUUR)
        na = voorstellen(drie + [groep("d", 4, 3)], {}, PLATTEGROND, VOORSTEL, ZITDUUR)
        self.assertEqual(sorted(na), ["a", "b", "c", "d"])
        self.assertEqual({sleutel: na[sleutel] for sleutel in voor}, voor)


if __name__ == "__main__":
    unittest.main()
