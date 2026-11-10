"""Deel 10 fase 1: per dag een telling zonder namen, bewaard vlak voordat oude reserveringen weggaan."""
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine, insert, inspect, select

from app import create_app
from app.database import (
    dagtellingen, get_db, init_db, reserveringen, schonen_oude_reserveringen, tafeltoewijzingen,
    tel_of_schoon_oude_reserveringen,
)
from tests.test_toegang import TestConfig

PROJECTMAP = Path(__file__).resolve().parent.parent


def dagen_geleden(n):
    return (date.today() - timedelta(days=n)).isoformat()


class DagtellingTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)  # bewaartermijn 60 dagen
        self.nummer = 0
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():
                for tabel in (tafeltoewijzingen, reserveringen, dagtellingen):
                    conn.execute(tabel.delete())

    def voeg_toe(self, datum, aantal=2, bron="online", status="verwacht"):
        self.nummer += 1
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=f"r{self.nummer}", naam="Siti Rahma", email="siti@example.com", telefoon="0612345678",
                    datum=datum, tijd="18:00", aantal=aantal, bron=bron, status=status))

    def schoon(self):
        with self.app.app_context():
            return tel_of_schoon_oude_reserveringen(get_db(), True)

    def tellingen(self):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                rijen = conn.execute(select(dagtellingen).order_by(dagtellingen.c.datum, dagtellingen.c.bron))
                return [tuple(r) for r in rijen]

    def test_telling_per_dag_en_bron(self):
        oud, ouder = dagen_geleden(70), dagen_geleden(71)
        self.voeg_toe(oud, 2)
        self.voeg_toe(oud, 4, status="gearriveerd")
        self.voeg_toe(oud, 3, status="no_show")
        self.voeg_toe(oud, 5, bron="telefoon")
        self.voeg_toe(ouder, 6, bron="binnenloper")
        self.assertEqual(self.schoon(), 5)
        self.assertEqual(self.tellingen(), [
            (ouder, "binnenloper", 1, 6, 0),
            (oud, "online", 3, 6, 1),  # 3 reserveringen, 2 + 4 gasten, de no-show telt niet als gast
            (oud, "telefoon", 1, 5, 0),
        ])

    def test_binnen_de_bewaartermijn_geen_telling(self):
        self.voeg_toe(dagen_geleden(59))
        self.voeg_toe(dagen_geleden(1))
        self.assertEqual(self.schoon(), 0)
        self.assertEqual(self.tellingen(), [])

    def test_alleen_tellen_zonder_uitvoeren_bewaart_niets(self):
        self.voeg_toe(dagen_geleden(70))
        with self.app.app_context():
            self.assertEqual(tel_of_schoon_oude_reserveringen(get_db(), False), 1)
        self.assertEqual(self.tellingen(), [])

    def test_twee_keer_schonen_telt_niet_dubbel(self):
        self.voeg_toe(dagen_geleden(70), 3)
        self.schoon()
        self.schoon()
        self.assertEqual(self.tellingen(), [(dagen_geleden(70), "online", 1, 3, 0)])

    def test_late_reservering_voor_een_oude_dag_wordt_opgeteld(self):
        oud = dagen_geleden(70)
        self.voeg_toe(oud, 3)
        self.schoon()
        self.voeg_toe(oud, 2, status="no_show")
        self.schoon()
        self.assertEqual(self.tellingen(), [(oud, "online", 2, 3, 1)])

    def test_nachtelijk_schonen_via_de_cli_route(self):
        self.voeg_toe(dagen_geleden(80), 4)
        with self.app.app_context():
            schonen_oude_reserveringen()
        self.assertEqual(self.tellingen(), [(dagen_geleden(80), "online", 1, 4, 0)])

    def test_geen_gegevens_van_gasten(self):
        with self.app.app_context():
            kolommen = {k["name"] for k in inspect(get_db()).get_columns("dagtellingen")}
        self.assertEqual(kolommen, {"datum", "bron", "reserveringen", "gasten", "no_shows"})


class MigratieTests(unittest.TestCase):
    def test_tabel_dagtellingen_op_en_neer(self):
        with tempfile.TemporaryDirectory() as map_:
            url = f"sqlite:///{Path(map_) / 'migratie.db'}"
            omgeving = {**os.environ, "MIGRATION_DATABASE_URL": url}
            omgeving.pop("ALLOW_PROD_MIGRATE", None)

            def alembic(*args):
                resultaat = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=PROJECTMAP, env=omgeving,
                                           capture_output=True, text=True)
                self.assertEqual(resultaat.returncode, 0, resultaat.stderr)

            alembic("upgrade", "head")
            engine = create_engine(url)
            self.assertIn("dagtellingen", inspect(engine).get_table_names())
            alembic("downgrade", "d7a2e4c9f3b1")
            self.assertNotIn("dagtellingen", inspect(engine).get_table_names())
            self.assertIn("reserveringen", inspect(engine).get_table_names())
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
