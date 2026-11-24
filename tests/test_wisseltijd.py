"""Wisseltijd (tafelvoorstel, fase 2): een tafel blijft na een groep nog even bezet.

De wisseltijd telt mee voor de tafels, maar niet voor het aantal gasten dat tegelijk binnen is.
Deze tests gebruiken tests/restaurant_vast.toml: 90 minuten zitduur en standaard geen wisseltijd.
"""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from sqlalchemy import delete

from app import create_app
from app.config import Config
from app.database import (
    get_db, haal_toewijzingen_op, metadata, reserveringen, tafeltoewijzingen, verwerk_reservering, wijs_tafels_toe,
)
from app.reserveringsregels import ReserveringsRegels, laad_regels
from app.routes.web import _kenmerk
from app.security import reset_rate_limits
from app.tafelvoorstel import voorstellen
from tests.hulp import log_in

PROJECTMAP = Path(__file__).resolve().parent.parent
VAST = PROJECTMAP / "tests" / "restaurant_vast.toml"
WPL = PROJECTMAP / "restaurants" / "wpl.toml"
DAG = "2030-01-01"  # een dinsdag
NU = datetime(2030, 1, 1, 10, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    CSRF_ENABLED = False
    RESTAURANT_CONFIG = "tests/restaurant_vast.toml"


def met_wisseltijd(app, minuten=15):
    """Zet de wisseltijd op de regels van deze app; de rest blijft zoals in restaurant_vast.toml."""
    app.config["REGELS"] = app.config["REGELS"].model_copy(update={"wisseltijd_minuten": minuten})
    return app.config["REGELS"]


def vaste_klok(testcase):
    """Zet de klok van de regels stil op NU, zodat de testdag altijd in de toekomst ligt."""
    patcher = mock.patch.object(ReserveringsRegels, "nu", lambda self: NU)
    patcher.start()
    testcase.addCleanup(patcher.stop)


def reservering(reservering_id, tijd, aantal=2):
    """Een reservering zoals de functies van het tafelvoorstel hem verwachten."""
    return {"id": reservering_id, "tijd": tijd, "aantal": aantal, "status": "verwacht", "aangemaakt_op": None}


class MetDatabase(unittest.TestCase):
    """Een app met de vaste regels, een lege database en een stilstaande klok."""

    def setUp(self):
        reset_rate_limits()
        vaste_klok(self)
        self.app = create_app(TestConfig)
        self.regels = self.app.config["REGELS"]
        with self.app.app_context():
            conn = get_db()
            metadata.create_all(conn)
            conn.commit()
            with conn.begin():
                conn.execute(delete(tafeltoewijzingen))
                conn.execute(delete(reserveringen))
        self.client = self.app.test_client()


class RegelsTests(unittest.TestCase):
    def test_01_zonder_instelling_geen_wisseltijd(self):
        regels = create_app(TestConfig).config["REGELS"]
        self.assertEqual(regels.wisseltijd_minuten, 0)
        self.assertEqual(regels.tafel_bezet_minuten, regels.zitduur_minuten)

    def test_02_wisseltijd_van_een_uur_is_te_veel(self):
        tekst = VAST.read_text(encoding="utf-8").replace(
            "[reserveringen]\n", "[reserveringen]\nwisseltijd_minuten = 61\n", 1)
        with tempfile.TemporaryDirectory() as map_:
            pad = Path(map_) / "restaurant.toml"
            pad.write_text(tekst, encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "wisseltijd_minuten"):
                laad_regels(pad)

    def test_03_wpl_heeft_vijftien_minuten_wisseltijd(self):
        self.assertEqual(laad_regels(WPL).wisseltijd_minuten, 15)


class VoorstellenTests(unittest.TestCase):
    def setUp(self):
        vaste_klok(self)
        self.app = create_app(TestConfig)  # 90 minuten zitduur, dus een tafel is 105 minuten bezet
        self.regels = met_wisseltijd(self.app)

    def voorstel(self, lijst):
        return voorstellen(lijst, {}, self.app.config["PLATTEGROND"], self.app.config["TAFELVOORSTEL"],
                           self.regels.tafel_bezet_minuten)

    def test_04_precies_een_zitduur_later_niet_dezelfde_tafel(self):
        voorstel = self.voorstel([reservering("a", "18:00"), reservering("b", "19:30")])
        self.assertEqual(voorstel["a"], ("8",))
        self.assertIsNotNone(voorstel["b"])
        self.assertNotEqual(voorstel["b"], ("8",))  # 90 minuten later is de tafel door de wisseltijd nog bezet

    def test_05_na_zitduur_plus_wisseltijd_weer_dezelfde_tafel(self):
        voorstel = self.voorstel([reservering("a", "18:00"), reservering("b", "19:45")])  # 90 + 15 minuten later
        self.assertEqual(voorstel, {"a": ("8",), "b": ("8",)})


class TafelsWijzigenTests(MetDatabase):
    def setUp(self):
        super().setUp()
        self.regels = met_wisseltijd(self.app)
        self.indeling = self.app.config["PLATTEGROND"]
        self.tafel = self.indeling.tafel("8").nummer  # een tafel van twee

    def maak_reservering(self, naam, tijd, nummer):
        with self.app.app_context():
            return verwerk_reservering(get_db(), None, naam, f"gast{nummer}@example.com",
                                       f"06123456{nummer:02d}", DAG, tijd, 2,
                                       zitduur_minuten=self.regels.zitduur_minuten)

    def kenmerk(self, reservering_id):
        with self.app.test_request_context():
            return _kenmerk(reservering_id)

    def test_06_wijzigen_weigert_tafel_binnen_zitduur_plus_wisseltijd(self):
        eerste = self.maak_reservering("A", "18:00", 1)
        tweede = self.maak_reservering("B", "19:30", 2)  # precies één zitduur later
        with self.app.app_context():
            wijs_tafels_toe(get_db(), eerste, [self.tafel], self.indeling, self.regels.tafel_bezet_minuten)
        log_in(self.app, self.client, naam="anna", rol="beheerder")
        self.client.post("/tafels/wijzigen",
                         data={"datum": DAG, "kenmerk": self.kenmerk(tweede), "andere": self.tafel})
        with self.app.app_context():
            self.assertIsNone(haal_toewijzingen_op(get_db(), DAG).get(tweede))
        self.assertIn(f"Tafel {self.tafel} is al toegewezen",
                      self.client.get(f"/overzicht?datum={DAG}").get_data(as_text=True))


class GastentellingTests(MetDatabase):
    def setUp(self):
        super().setUp()
        with self.app.app_context():
            for nummer in range(5):  # 5 x 13 = 65 gasten om 18:00
                verwerk_reservering(get_db(), self.regels.max_gasten_tegelijk, f"Gast {nummer}",
                                    f"gast{nummer}@example.com", f"06123456{nummer:02d}", DAG, "18:00", 13,
                                    zitduur_minuten=self.regels.zitduur_minuten)

    def vrij(self):
        antwoord = self.client.get(f"/beschikbaarheid?datum={DAG}&aantal=2")
        return [tijd["vrij"] for tijd in antwoord.get_json()["tijden"]]

    def test_07_wisseltijd_verandert_de_gastentelling_niet(self):
        zonder = self.vrij()
        self.assertLess(min(zonder), self.regels.max_gasten_tegelijk)  # de telling is echt gebruikt
        met_wisseltijd(self.app)
        self.assertEqual(self.vrij(), zonder)


if __name__ == "__main__":
    unittest.main()
