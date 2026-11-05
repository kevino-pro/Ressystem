import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine, func, inspect, insert, select

from app import create_app
from app.config import Config
from app.database import (
    GeenReserveringFout, OnbekendeTafelFout, TafelBezetFout, get_db, haal_toewijzingen_op,
    init_db, reserveringen, schonen_oude_reserveringen, tafeltoewijzingen,
    verwijder_reservering, wijs_tafels_toe,
)
from app.plattegrond import Plattegrond

PROJECTMAP = Path(__file__).resolve().parent.parent
ZITDUUR = 90

PLATTEGROND = Plattegrond.model_validate({
    "kolommen": 6,
    "rijen": 2,
    "tafels": [
        {"nummer": "1", "stoelen": 4, "kolom": 0, "rij": 0, "breedte": 2},
        {"nummer": "2a", "stoelen": 2, "kolom": 3, "rij": 0},
        {"nummer": "2b", "stoelen": 2, "kolom": 4, "rij": 0},
    ],
    "combinaties": [["2a", "2b"]],
})


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
    RETENTIE_DAGEN_AVG = 60


class TafeltoewijzingTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        init_db()
        conn = get_db()
        with conn.begin():  # de in-memory database wordt gedeeld tussen tests
            conn.execute(tafeltoewijzingen.delete())
            conn.execute(reserveringen.delete())

    def reservering(self, rid, tijd="19:00", aantal=2, datum="2030-01-01"):
        conn = get_db()
        with conn.begin():
            conn.execute(insert(reserveringen).values(
                id=rid, naam="N", email=f"{rid}@example.com", telefoon="0612345678",
                datum=datum, tijd=tijd, aantal=aantal))
        return rid

    def wijs_toe(self, rid, tafels):
        return wijs_tafels_toe(get_db(), rid, tafels, PLATTEGROND, ZITDUUR)

    def tafels_van(self, rid, datum="2030-01-01"):
        return haal_toewijzingen_op(get_db(), datum).get(rid, [])

    def test_toewijzen_en_ophalen(self):
        self.reservering("a", aantal=4)
        self.assertIsNone(self.wijs_toe("a", ["2a", "2b"]))
        self.assertEqual(self.tafels_van("a"), ["2a", "2b"])

    def test_dubbele_tafel_in_lijst_telt_een_keer(self):
        self.reservering("a")
        self.wijs_toe("a", ["1", "1"])
        self.assertEqual(self.tafels_van("a"), ["1"])

    def test_opnieuw_toewijzen_vervangt(self):
        self.reservering("a")
        self.wijs_toe("a", ["1"])
        self.wijs_toe("a", ["2a"])
        self.assertEqual(self.tafels_van("a"), ["2a"])

    def test_lege_lijst_maakt_los(self):
        self.reservering("a")
        self.wijs_toe("a", ["1"])
        self.assertIsNone(self.wijs_toe("a", []))
        self.assertEqual(self.tafels_van("a"), [])

    def test_onbekende_tafel(self):
        self.reservering("a")
        with self.assertRaises(OnbekendeTafelFout):
            self.wijs_toe("a", ["1", "99"])
        self.assertEqual(self.tafels_van("a"), [])

    def test_onbekende_reservering(self):
        with self.assertRaises(GeenReserveringFout):
            self.wijs_toe("bestaat-niet", ["1"])

    def test_overlappende_reservering_krijgt_tafel_niet(self):
        self.reservering("a", tijd="19:00")
        self.reservering("b", tijd="20:00")  # 19:00 + 90 minuten = 20:30, dus overlap
        self.wijs_toe("a", ["1"])
        with self.assertRaises(TafelBezetFout):
            self.wijs_toe("b", ["2a", "1"])
        self.assertEqual(self.tafels_van("b"), [])

    def test_tafel_vrij_na_zitduur(self):
        self.reservering("a", tijd="19:00")
        self.reservering("b", tijd="20:30")
        self.wijs_toe("a", ["1"])
        self.wijs_toe("b", ["1"])
        self.assertEqual(self.tafels_van("b"), ["1"])

    def test_andere_dag_telt_niet(self):
        self.reservering("a", tijd="19:00")
        self.reservering("b", tijd="19:00", datum="2030-01-02")
        self.wijs_toe("a", ["1"])
        self.wijs_toe("b", ["1"])
        self.assertEqual(self.tafels_van("b", "2030-01-02"), ["1"])

    def test_waarschuwing_bij_te_weinig_stoelen(self):
        self.reservering("a", aantal=5)
        self.assertEqual(self.wijs_toe("a", ["1"]), "Let op: 4 stoelen voor 5 gasten.")
        self.assertEqual(self.tafels_van("a"), ["1"])  # waarschuwing, geen blokkade

    def test_verwijderen_ruimt_toewijzing_op(self):
        self.reservering("a")
        self.wijs_toe("a", ["1"])
        verwijder_reservering(get_db(), "a")
        conn = get_db()
        with conn.begin():
            self.assertEqual(conn.execute(select(func.count()).select_from(tafeltoewijzingen)).scalar(), 0)

    def test_schonen_ruimt_oude_toewijzingen_op(self):
        oud = (date.today() - timedelta(days=100)).isoformat()
        nieuw = (date.today() + timedelta(days=1)).isoformat()
        self.reservering("oud", datum=oud)
        self.reservering("nieuw", datum=nieuw)
        self.wijs_toe("oud", ["1"])
        self.wijs_toe("nieuw", ["1"])
        schonen_oude_reserveringen()
        conn = get_db()
        with conn.begin():
            over = conn.execute(select(tafeltoewijzingen.c.reservering_id)).scalars().all()
        self.assertEqual(over, ["nieuw"])


class MigratieTests(unittest.TestCase):
    def test_upgrade_en_downgrade(self):
        with tempfile.TemporaryDirectory() as map_:
            url = f"sqlite:///{Path(map_) / 'migratie.db'}"
            omgeving = {**os.environ, "MIGRATION_DATABASE_URL": url}
            omgeving.pop("ALLOW_PROD_MIGRATE", None)

            def alembic(*args):
                resultaat = subprocess.run(
                    [sys.executable, "-m", "alembic", *args], cwd=PROJECTMAP, env=omgeving,
                    capture_output=True, text=True)
                self.assertEqual(resultaat.returncode, 0, resultaat.stderr)

            alembic("upgrade", "head")
            engine = create_engine(url)
            self.assertIn("tafeltoewijzingen", inspect(engine).get_table_names())
            alembic("downgrade", "-1")
            self.assertNotIn("tafeltoewijzingen", inspect(engine).get_table_names())
            self.assertIn("reserveringen", inspect(engine).get_table_names())
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
