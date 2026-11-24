"""
Tafel buiten gebruik (fase 5): een tafel die die dag niet gebruikt kan worden, krijgt geen voorstel
en telt niet mee als plek. Dat geldt alleen voor die datum; het nachtelijk opschonen ruimt oude rijen op.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, insert, inspect

from app import tafelvoorstel
from app.database import (
    get_db, haal_buiten_gebruik_op, init_db, reserveringen, schonen_oude_reserveringen, tafels_buiten_gebruik,
    tafeltoewijzingen, zet_buiten_gebruik,
)
from app.reserveringsregels import ReserveringsRegels
from app.security import reset_rate_limits
from tests.test_plattegrond_pagina import TestConfig as PlattegrondConfig, maak_client

PROJECTMAP = Path(__file__).resolve().parent.parent
NU = datetime(2030, 1, 1, 18, 7, tzinfo=ZoneInfo("Europe/Amsterdam"))  # een dinsdag
VANDAAG = "2030-01-01"
MORGEN = "2030-01-02"
VOLGENDE_WEEK = "2030-01-08"  # ook een dinsdag, ruim binnen de 90 dagen vooruit


class TestConfig(PlattegrondConfig):
    RETENTIE_DAGEN_AVG = 60  # vast, zodat de opschoonproef niet van de omgeving afhangt


class MigratieTests(unittest.TestCase):
    def test_tabel_tafels_buiten_gebruik_op_en_neer(self):
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
            self.assertIn("tafels_buiten_gebruik", inspect(engine).get_table_names())
            alembic("downgrade", "e8b3f1a6c2d9")
            self.assertNotIn("tafels_buiten_gebruik", inspect(engine).get_table_names())
            self.assertIn("reserveringen", inspect(engine).get_table_names())
            engine.dispose()


class BuitenGebruikTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        patcher = mock.patch.object(ReserveringsRegels, "nu", lambda self: NU)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app, self.client = maak_client(TestConfig)
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():  # de in-memory database wordt gedeeld tussen tests
                conn.execute(tafeltoewijzingen.delete())
                conn.execute(reserveringen.delete())
                conn.execute(tafels_buiten_gebruik.delete())

    def tearDown(self):
        # De in-memory database wordt met de andere testbestanden gedeeld: laat geen tafels buiten
        # gebruik (of reserveringen van deze tests) achter voor de volgende.
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(tafeltoewijzingen.delete())
                conn.execute(reserveringen.delete())
                conn.execute(tafels_buiten_gebruik.delete())

    def reservering(self, rid, datum=VANDAAG, tijd="19:00", aantal=2):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=rid, naam=f"Gast {rid}", email=f"{rid}@example.com", telefoon="0612345678",
                    datum=datum, tijd=tijd, aantal=aantal))

    def zet_buiten(self, datum, tafel, aan=True):
        with self.app.app_context():
            zet_buiten_gebruik(get_db(), datum, tafel, aan, door="anna")

    def buiten_gebruik(self, datum):
        with self.app.app_context():
            return haal_buiten_gebruik_op(get_db(), datum)

    def overzicht(self, datum=VANDAAG):
        return self.client.get(f"/overzicht?datum={datum}").get_data(as_text=True)

    def test_buiten_gebruik_aan_en_uit_en_twee_keer_aan(self):
        self.zet_buiten(VANDAAG, "8")
        self.assertEqual(self.buiten_gebruik(VANDAAG), frozenset({"8"}))
        self.zet_buiten(VANDAAG, "8")  # tweede keer aan: geen fout en geen tweede rij
        self.assertEqual(self.buiten_gebruik(VANDAAG), frozenset({"8"}))
        self.zet_buiten(VANDAAG, "7b")
        self.assertEqual(self.buiten_gebruik(VANDAAG), frozenset({"7b", "8"}))
        self.zet_buiten(VANDAAG, "8", aan=False)
        self.assertEqual(self.buiten_gebruik(VANDAAG), frozenset({"7b"}))

    def test_opties_laat_een_losse_tafel_buiten_gebruik_weg(self):
        indeling, voorstel = self.app.config["PLATTEGROND"], self.app.config["TAFELVOORSTEL"]
        self.assertEqual(tafelvoorstel.opties(indeling, voorstel, 2)[0], ("8",))
        opties = tafelvoorstel.opties(indeling, voorstel, 2, buiten_gebruik=frozenset({"8"}))
        self.assertEqual(opties[0], ("7b",))  # de volgende tafel van twee stoelen
        self.assertFalse(any("8" in optie for optie in opties))

    def test_opties_laat_een_combinatie_met_die_tafel_weg(self):
        indeling, voorstel = self.app.config["PLATTEGROND"], self.app.config["TAFELVOORSTEL"]
        opties = tafelvoorstel.opties(indeling, voorstel, 7, buiten_gebruik=frozenset({"3a"}))
        self.assertIn(("1a", "1b"), opties)
        self.assertNotIn(("3a", "3b"), opties)

    def test_overzicht_stelt_tafel_buiten_gebruik_niet_voor(self):
        self.reservering("a")
        self.assertIn("Voorstel: 8", self.overzicht())
        self.zet_buiten(VANDAAG, "8")
        html = self.overzicht()
        self.assertNotIn("Voorstel: 8", html)
        self.assertIn("Voorstel: 7b", html)

    def test_beschikbaarheid_geeft_bel_als_enige_tafel_buiten_gebruik_is(self):
        url = f"/beschikbaarheid?datum={VOLGENDE_WEEK}&aantal=6"
        eerst = self.client.get(url).get_json()
        self.assertTrue(eerst["tijden"])
        self.assertTrue(all(knop["beschikbaar"] for knop in eerst["tijden"]))
        self.zet_buiten(VOLGENDE_WEEK, "2")  # de enige tafel met zes stoelen
        daarna = self.client.get(url).get_json()
        self.assertTrue(daarna["tijden"])
        self.assertTrue(all(knop.get("bel") and not knop["beschikbaar"] for knop in daarna["tijden"]))
        self.assertIn("telefoon", daarna)

    def test_geldt_alleen_voor_die_datum(self):
        self.reservering("vandaag")
        self.reservering("morgen", datum=MORGEN)
        self.zet_buiten(VANDAAG, "8")
        self.assertIn("Voorstel: 7b", self.overzicht(VANDAAG))
        self.assertIn("Voorstel: 8", self.overzicht(MORGEN))

    def test_opschonen_verwijdert_rijen_ouder_dan_de_bewaartermijn(self):
        oud = (date.today() - timedelta(days=70)).isoformat()
        recent = (date.today() - timedelta(days=1)).isoformat()
        self.zet_buiten(oud, "8")
        self.zet_buiten(recent, "7b")
        with self.app.app_context():
            schonen_oude_reserveringen()
        self.assertEqual(self.buiten_gebruik(oud), frozenset())
        self.assertEqual(self.buiten_gebruik(recent), frozenset({"7b"}))


if __name__ == "__main__":
    unittest.main()
