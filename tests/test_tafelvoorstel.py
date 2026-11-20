import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app import create_app
from app.config import Config
from app.plattegrond import laad_plattegrond
from app.tafelvoorstel import laad_tafelvoorstel, opties, past_nog, voorstellen

PROJECTMAP = Path(__file__).resolve().parent.parent
VAST = PROJECTMAP / "tests" / "restaurant_vast.toml"
WPL = PROJECTMAP / "restaurants" / "wpl.toml"

PLATTEGROND = laad_plattegrond(VAST)
VOORSTEL = laad_tafelvoorstel(VAST, PLATTEGROND)


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    RESTAURANT_CONFIG = "tests/restaurant_vast.toml"


def laad_voorstel(inhoud, plattegrond=PLATTEGROND):
    """Laadt een tijdelijk restaurantbestand met alleen [tafelvoorstel]; de indeling komt uit restaurant_vast.toml."""
    with tempfile.TemporaryDirectory() as map_:
        pad = Path(map_) / "restaurant.toml"
        pad.write_text(inhoud, encoding="utf-8")
        return laad_tafelvoorstel(pad, plattegrond)


def reservering(reservering_id, tijd, aantal, status="verwacht", aangemaakt_op=None):
    return {"id": reservering_id, "tijd": tijd, "aantal": aantal, "status": status, "aangemaakt_op": aangemaakt_op}


class LaadTafelvoorstelTests(unittest.TestCase):
    def test_01_wpl_heeft_drie_groepsgroottes(self):
        voorstel = laad_tafelvoorstel(WPL, laad_plattegrond(WPL))
        self.assertEqual(sorted(voorstel.combinaties), [7, 10, 14])
        self.assertEqual(voorstel.combinaties[10], (("1e", "2"), ("9", "10a", "10b")))

        class MetWpl(TestConfig):
            RESTAURANT_CONFIG = "restaurants/wpl.toml"

        self.assertEqual(create_app(MetWpl).config["TAFELVOORSTEL"], voorstel)

    def test_02_restaurant_vast_laadt(self):
        self.assertEqual(sorted(VOORSTEL.combinaties), [7, 10, 14])
        self.assertEqual(VOORSTEL.combinaties[7], (("1a", "1b"), ("3a", "3b")))
        self.assertEqual(create_app(TestConfig).config["TAFELVOORSTEL"], VOORSTEL)

    def test_03_onbekende_tafel(self):
        with self.assertRaisesRegex(RuntimeError, "onbekende tafel"):
            laad_voorstel('[tafelvoorstel]\n7 = [["1a", "99"]]\n')

    def test_04_te_weinig_stoelen(self):
        with self.assertRaisesRegex(RuntimeError, "stoelen"):
            laad_voorstel('[tafelvoorstel]\n7 = [["8", "11"]]\n')

    def test_05_combinatie_met_een_tafel(self):
        with self.assertRaisesRegex(RuntimeError, "minstens twee tafels"):
            laad_voorstel('[tafelvoorstel]\n7 = [["2"]]\n')

    def test_06_dezelfde_tafel_twee_keer(self):
        with self.assertRaisesRegex(RuntimeError, "twee keer"):
            laad_voorstel('[tafelvoorstel]\n7 = [["1a", "1a"]]\n')

    def test_07_zonder_sectie_lege_combinaties(self):
        voorstel = laad_voorstel('[restaurant]\nnaam = "Zonder voorstel"\n')
        self.assertEqual(voorstel.combinaties, {})

    def test_08_zonder_plattegrond_en_zonder_sectie_none(self):
        self.assertIsNone(laad_voorstel('[restaurant]\nnaam = "Zonder plattegrond"\n', plattegrond=None))
        with self.assertRaisesRegex(RuntimeError, "plattegrond"):
            laad_voorstel('[tafelvoorstel]\n7 = [["1a", "1b"]]\n', plattegrond=None)


class OptiesTests(unittest.TestCase):
    def test_09_opties_voor_2_begint_met_tafel_8(self):
        self.assertEqual(opties(PLATTEGROND, VOORSTEL, 2)[0], ("8",))

    def test_10_opties_voor_5_alleen_losse_tafels_kleinste_eerst(self):
        # In restaurant_vast.toml heeft alleen tafel 2 minstens 5 stoelen (tafel 4 heeft er 4).
        opties_vijf = opties(PLATTEGROND, VOORSTEL, 5)
        self.assertEqual(opties_vijf, [("2",)])
        self.assertTrue(all(len(optie) == 1 for optie in opties_vijf))
        self.assertTrue(all(PLATTEGROND.tafel(optie[0]).stoelen >= 5 for optie in opties_vijf))

    def test_11_opties_voor_7_zijn_de_twee_combinaties(self):
        self.assertEqual(opties(PLATTEGROND, VOORSTEL, 7), [("1a", "1b"), ("3a", "3b")])


class VoorstellenTests(unittest.TestCase):
    def test_12_twee_reserveringen_van_2_krijgen_verschillende_tafels(self):
        lijst = [
            reservering("a", "18:00", 2, aangemaakt_op=datetime(2026, 11, 6, 9, 0)),
            reservering("b", "18:00", 2, aangemaakt_op=datetime(2026, 11, 6, 10, 0)),
        ]
        self.assertEqual(voorstellen(lijst, {}, PLATTEGROND, VOORSTEL, 90), {"a": ("8",), "b": ("7b",)})

    def test_13_toegewezen_tafel_wordt_niet_voorgesteld(self):
        lijst = [
            reservering("a", "18:00", 2, status="gearriveerd"),
            reservering("b", "18:00", 2),
        ]
        self.assertEqual(voorstellen(lijst, {"a": ["8"]}, PLATTEGROND, VOORSTEL, 90), {"b": ("7b",)})

    def test_14_no_show_bezet_geen_tafel_en_krijgt_geen_voorstel(self):
        lijst = [
            reservering("weg", "18:00", 2, status="no_show"),
            reservering("b", "18:00", 2),
        ]
        self.assertEqual(voorstellen(lijst, {"weg": ["8"]}, PLATTEGROND, VOORSTEL, 90), {"b": ("8",)})

    def test_15_na_de_zitduur_mag_dezelfde_tafel(self):
        lijst = [reservering("a", "18:00", 2), reservering("b", "19:30", 2)]
        self.assertEqual(voorstellen(lijst, {}, PLATTEGROND, VOORSTEL, 90), {"a": ("8",), "b": ("8",)})

    def test_16_past_nog(self):
        bezet = [
            reservering("1", "18:00", 4, status="gearriveerd"),
            reservering("2", "18:00", 4, status="gearriveerd"),
        ]
        self.assertFalse(past_nog(
            bezet, {"1": ["1a", "1b"], "2": ["3a", "3b"]}, PLATTEGROND, VOORSTEL, 90, "18:00", 7))
        self.assertTrue(past_nog(
            [bezet[0]], {"1": ["1a", "1b"]}, PLATTEGROND, VOORSTEL, 90, "18:00", 7))

    def test_17_groep_van_16_zonder_lijst_krijgt_none(self):
        lijst = [reservering("groot", "18:00", 16)]
        self.assertEqual(voorstellen(lijst, {}, PLATTEGROND, VOORSTEL, 90), {"groot": None})


if __name__ == "__main__":
    unittest.main()
