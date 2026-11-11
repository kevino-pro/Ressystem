import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.config import Config
from app.plattegrond import Plattegrond, laad_plattegrond

PROJECTMAP = Path(__file__).resolve().parent.parent


def plattegrond(**extra):
    basis = {
        "kolommen": 6,
        "rijen": 4,
        "tafels": [
            {"nummer": "1", "stoelen": 4, "kolom": 0, "rij": 0, "breedte": 2, "hoogte": 2},
            {"nummer": "2a", "stoelen": 2, "kolom": 3, "rij": 0},
            {"nummer": "2b", "stoelen": 2, "kolom": 4, "rij": 0},
        ],
        "elementen": [{"naam": "Bar", "kolom": 0, "rij": 3, "breedte": 6}],
        "combinaties": [["2a", "2b"]],
    }
    basis.update(extra)
    return Plattegrond.model_validate(basis)


class PlattegrondValidatieTests(unittest.TestCase):
    def test_geldige_plattegrond(self):
        p = plattegrond()
        self.assertEqual(p.totaal_stoelen, 8)
        self.assertEqual(p.tafel("2a").stoelen, 2)
        self.assertIsNone(p.tafel("99"))
        self.assertEqual(p.tafel("1").vorm, "vierkant")

    def test_dubbel_tafelnummer(self):
        with self.assertRaisesRegex(ValueError, "dubbel"):
            plattegrond(tafels=[
                {"nummer": "1", "stoelen": 2, "kolom": 0, "rij": 0},
                {"nummer": "1", "stoelen": 2, "kolom": 2, "rij": 0},
            ], combinaties=[])

    def test_buiten_raster(self):
        with self.assertRaisesRegex(ValueError, "buiten het raster"):
            plattegrond(tafels=[{"nummer": "1", "stoelen": 2, "kolom": 5, "rij": 0, "breedte": 2}], combinaties=[])

    def test_overlap_tafels_en_elementen(self):
        with self.assertRaisesRegex(ValueError, "overlapt"):
            plattegrond(tafels=[{"nummer": "1", "stoelen": 2, "kolom": 0, "rij": 3}], combinaties=[])

    def test_combinatie_met_onbekende_tafel(self):
        with self.assertRaisesRegex(ValueError, "onbekende tafel"):
            plattegrond(combinaties=[["2a", "9"]])

    def test_tafel_in_twee_combinaties(self):
        with self.assertRaisesRegex(ValueError, "meer dan een combinatie"):
            plattegrond(combinaties=[["1", "2a"], ["2a", "2b"]])

    def test_ongeldige_waarden(self):
        for tafel in (
            {"nummer": "1", "stoelen": 0, "kolom": 0, "rij": 0},
            {"nummer": "1", "stoelen": 21, "kolom": 0, "rij": 0},
            {"nummer": "1", "stoelen": 2, "kolom": 0, "rij": 0, "vorm": "driehoek"},
            {"nummer": "<b>", "stoelen": 2, "kolom": 0, "rij": 0},
            {"nummer": "1", "stoelen": 2, "kolom": -1, "rij": 0},
        ):
            with self.subTest(tafel=tafel), self.assertRaises(ValueError):
                plattegrond(tafels=[tafel], combinaties=[])


class LaadPlattegrondTests(unittest.TestCase):
    def test_wpl_den_haag(self):
        p = laad_plattegrond(PROJECTMAP / "restaurants" / "wpl.toml")
        self.assertEqual(len(p.tafels), 22)
        self.assertEqual(p.totaal_stoelen, 69)  # gelijk aan max_gasten_tegelijk in wpl.toml
        self.assertEqual(p.tafel("2").vorm, "rond")

    def test_alle_restaurantbestanden_hebben_geldige_plattegrond(self):
        for pad in sorted((PROJECTMAP / "restaurants").glob("*.toml")):
            with self.subTest(bestand=pad.name):
                laad_plattegrond(pad)  # None (geen plattegrond) is ook goed

    def test_zonder_sectie_geen_plattegrond(self):
        self.assertIsNone(laad_plattegrond(PROJECTMAP / "restaurants" / "voorbeeld.toml"))

    def test_fout_wordt_runtimeerror(self):
        with tempfile.TemporaryDirectory() as map_:
            pad = Path(map_) / "kapot.toml"
            pad.write_text("[plattegrond]\nkolommen = 2\nrijen = 2\ntafels = []\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Plattegrond in"):
                laad_plattegrond(pad)


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0


class AppPlattegrondTests(unittest.TestCase):
    def test_app_zonder_plattegrond(self):
        self.assertIsNone(create_app(TestConfig).config["PLATTEGROND"])

    def test_app_met_plattegrond(self):
        class MetPlattegrond(TestConfig):
            RESTAURANT_CONFIG = "restaurants/wpl.toml"
        self.assertEqual(len(create_app(MetPlattegrond).config["PLATTEGROND"].tafels), 22)


if __name__ == "__main__":
    unittest.main()
