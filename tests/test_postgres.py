"""
Tests die een echte Postgres nodig hebben. Ze draaien alleen als TEST_POSTGRES_URL is gezet
(in CI de job `postgres-tests`); lokaal worden ze overgeslagen.
"""
import os
import unittest
from datetime import date, timedelta

from sqlalchemy import func, insert, select

import app.database as database
from app import create_app
from app.config import Config
from app.database import CapaciteitVolFout, get_db, metadata, reserveringen, verwerk_reservering

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

    def test_capaciteit_met_advisory_lock(self):
        with self.app.app_context():
            conn = get_db()
            verwerk_reservering(conn, 4, "Jan", "a@example.com", "0612345678", "2030-01-01", "19:00", 3)
            with self.assertRaises(CapaciteitVolFout):
                verwerk_reservering(conn, 4, "Piet", "b@example.com", "0612345678", "2030-01-01", "19:00", 2)
            with conn.begin():
                totaal = conn.execute(select(func.sum(reserveringen.c.aantal))).scalar()
        self.assertEqual(totaal, 3)


if __name__ == "__main__":
    unittest.main()
