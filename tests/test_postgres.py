"""
Tests die een echte Postgres nodig hebben. Ze draaien alleen als TEST_POSTGRES_URL is gezet
(in CI de job `postgres-tests`); lokaal worden ze overgeslagen.
"""
import os
import threading
import unittest
from datetime import date, timedelta

from sqlalchemy import func, insert, select

import app.database as database
from app import create_app
from app.config import Config
from app.database import (
    CapaciteitVolFout, DubbeleReserveringFout, TafelBezetFout, dagtellingen, get_db, metadata, reserveringen,
    tafeltoewijzingen, verwerk_reservering, wijs_tafels_toe, wijzig_reservering,
)
from app.plattegrond import Plattegrond

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")


class PostgresConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = POSTGRES_URL or "postgresql://niet-gebruikt/db"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    RETENTIE_DAGEN_AVG = 60


@unittest.skipUnless(POSTGRES_URL, "TEST_POSTGRES_URL niet gezet")
class PostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # De engine is proces-breed; een eerdere test kan al een SQLite-engine hebben gemaakt.
        cls._vorige_engine = database._engine
        database._engine = None
        cls.app = create_app(PostgresConfig)

    @classmethod
    def tearDownClass(cls):
        database._engine.dispose()
        database._engine = cls._vorige_engine

    def setUp(self):
        with self.app.app_context():
            conn = get_db()
            metadata.create_all(conn)
            conn.commit()
            with conn.begin():
                conn.execute(tafeltoewijzingen.delete())
                conn.execute(reserveringen.delete())
        self.runner = self.app.test_cli_runner()

    def _voeg_toe(self, rid, dagen_geleden):
        datum = (date.today() - timedelta(days=dagen_geleden)).isoformat()
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=rid, naam="N", email="a@example.com", telefoon="0612345678",
                    datum=datum, tijd="18:00", aantal=1))

    def _ids(self):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                return sorted(r[0] for r in conn.execute(select(reserveringen.c.id)))

    def test_purge_telt_op_postgres(self):
        self._voeg_toe("oud", 100)
        self._voeg_toe("nieuw", 1)
        result = self.runner.invoke(args=["purge-retention", "--productie"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("1 reservering", result.output)
        self.assertEqual(self._ids(), ["nieuw", "oud"])

    def test_purge_verwijdert_alleen_oude_op_postgres(self):
        self._voeg_toe("oud", 100)
        self._voeg_toe("nieuw", 1)
        result = self.runner.invoke(args=["purge-retention", "--uitvoeren", "--productie"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self._ids(), ["nieuw"])

    def test_purge_bewaart_dagtelling_op_postgres(self):
        # Deel 10: de aantallen van de verwijderde dag blijven, zonder namen.
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(dagtellingen.delete())
        self._voeg_toe("oud", 100)
        result = self.runner.invoke(args=["purge-retention", "--uitvoeren", "--productie"])
        self.assertEqual(result.exit_code, 0, result.output)
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                rijen = [tuple(r) for r in conn.execute(select(dagtellingen))]
        self.assertEqual(rijen, [((date.today() - timedelta(days=100)).isoformat(), "online", 1, 1, 0)])

    def test_capaciteit_met_advisory_lock(self):
        with self.app.app_context():
            conn = get_db()
            verwerk_reservering(conn, 4, "Jan", "a@example.com", "0612345678", "2030-01-01", "19:00", 3)
            with self.assertRaises(CapaciteitVolFout):
                verwerk_reservering(conn, 4, "Piet", "b@example.com", "0687654321", "2030-01-01", "19:00", 2)
            with conn.begin():
                totaal = conn.execute(select(func.sum(reserveringen.c.aantal))).scalar()
        self.assertEqual(totaal, 3)

    def test_overlappende_tijden_met_zitduur(self):
        with self.app.app_context():
            conn = get_db()
            verwerk_reservering(conn, 4, "Jan", "a@example.com", "0612345678", "2030-01-01", "19:00", 3,
                                zitduur_minuten=120)
            with self.assertRaises(CapaciteitVolFout):
                verwerk_reservering(conn, 4, "Piet", "b@example.com", "0612345678", "2030-01-01", "20:00", 2,
                                    zitduur_minuten=120)
            verwerk_reservering(conn, 4, "Kees", "c@example.com", "0612345678", "2030-01-01", "21:00", 4,
                                zitduur_minuten=120)

    def test_gelijktijdige_dubbele_boeking_slaagt_maar_een_keer(self):
        start = threading.Barrier(4)
        uitkomsten = []

        def poging():
            with self.app.app_context():
                start.wait()
                try:
                    verwerk_reservering(get_db(), 20, "Jan", "a@example.com", "0612345678",
                                        "2030-01-01", "19:00", 2, zitduur_minuten=120)
                    uitkomsten.append("opgeslagen")
                except DubbeleReserveringFout:
                    uitkomsten.append("dubbel")

        threads = [threading.Thread(target=poging) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertEqual(sorted(uitkomsten), ["dubbel", "dubbel", "dubbel", "opgeslagen"])
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                self.assertEqual(conn.execute(select(func.count()).select_from(reserveringen)).scalar(), 1)


    def test_gelijktijdig_dezelfde_tafel_slaagt_maar_een_keer(self):
        plattegrond = Plattegrond.model_validate({
            "kolommen": 2, "rijen": 1,
            "tafels": [{"nummer": "1", "stoelen": 4, "kolom": 0, "rij": 0}],
        })
        ids = []
        with self.app.app_context():
            for i, tijd in enumerate(["19:00", "19:15", "19:30", "19:45"]):
                ids.append(verwerk_reservering(get_db(), 20, f"Gast {i}", f"g{i}@example.com",
                                               "0612345678", "2030-01-01", tijd, 2, zitduur_minuten=90))
        start = threading.Barrier(len(ids))
        uitkomsten = []

        def poging(reservering_id):
            with self.app.app_context():
                start.wait()
                try:
                    wijs_tafels_toe(get_db(), reservering_id, ["1"], plattegrond, 90)
                    uitkomsten.append("toegewezen")
                except TafelBezetFout:
                    uitkomsten.append("bezet")

        threads = [threading.Thread(target=poging, args=(rid,)) for rid in ids]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertEqual(sorted(uitkomsten), ["bezet", "bezet", "bezet", "toegewezen"])
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                self.assertEqual(conn.execute(select(func.count()).select_from(tafeltoewijzingen)).scalar(), 1)

    def test_gelijktijdig_wijzigen_naar_de_laatste_plekken_slaagt_maar_een_keer(self):
        # Deel 9: vier gasten zetten hun reservering tegelijk op een dag waar nog plek is voor één groep.
        with self.app.app_context():
            ids = [verwerk_reservering(get_db(), 20, f"Gast {i}", f"g{i}@example.com", f"061234567{i}",
                                       "2030-01-02", "19:00", 3, zitduur_minuten=60) for i in range(4)]
        start = threading.Barrier(len(ids))
        uitkomsten = []

        def poging(reservering_id):
            with self.app.app_context():
                start.wait()
                try:
                    wijzig_reservering(get_db(), reservering_id, 4, "2030-01-01", "19:00", 3, 60)
                    uitkomsten.append("gewijzigd")
                except CapaciteitVolFout:
                    uitkomsten.append("vol")

        threads = [threading.Thread(target=poging, args=(rid,)) for rid in ids]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertEqual(sorted(uitkomsten), ["gewijzigd", "vol", "vol", "vol"])
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                op_de_dag = conn.execute(select(func.sum(reserveringen.c.aantal))
                                         .where(reserveringen.c.datum == "2030-01-01")).scalar()
        self.assertEqual(op_de_dag, 3)


if __name__ == "__main__":
    unittest.main()
