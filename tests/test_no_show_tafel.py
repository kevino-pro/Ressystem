"""
No-show geeft de tafel vrij (fase 4): wie niet komt verliest zijn tafels, en komt hij toch,
dan krijgt hij een nieuw voorstel in plaats van stilletjes dezelfde tafel terug.
"""
import itertools
import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from sqlalchemy import insert

from app.database import (
    get_db, haal_toewijzingen_op, init_db, reserveringen, tafeltoewijzingen, tellingen_per_dag, wijs_tafels_toe,
)
from app.reserveringsregels import ReserveringsRegels
from app.routes.web import _kenmerk
from app.security import reset_rate_limits
from tests.test_plattegrond_pagina import TestConfig, maak_client

DAG = "2030-01-01"
NU = datetime(2030, 1, 1, 18, 7, tzinfo=ZoneInfo("Europe/Amsterdam"))  # na de begintijd van 18:00
NUMMERS = itertools.count(10000000)  # elk testgast een eigen telefoonnummer


class NoShowTafelTests(unittest.TestCase):
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

    def reservering(self, rid, tijd="18:00", aantal=2, tafels=()):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=rid, naam=f"Gast {rid}", email=f"{rid}@example.com", telefoon=f"06{next(NUMMERS)}",
                    datum=DAG, tijd=tijd, aantal=aantal))
            if tafels:
                wijs_tafels_toe(conn, rid, list(tafels), self.app.config["PLATTEGROND"], 90)

    def wijs_toe(self, rid, tafels):
        with self.app.app_context():
            wijs_tafels_toe(get_db(), rid, list(tafels), self.app.config["PLATTEGROND"], 90)

    def zet(self, rid, status):
        """Wat het overzicht verstuurt: de dag, het kenmerk (niet het id) en de nieuwe status."""
        with self.app.app_context():
            kenmerk = _kenmerk(rid)
        return self.client.post("/aankomst", data={"datum": DAG, "kenmerk": kenmerk, "status": status})

    def tafels(self):
        with self.app.app_context():
            return haal_toewijzingen_op(get_db(), DAG)

    def tafelgebruik(self):
        """Hoe vaak elke tafel in de database staat; een tafel hoort bij hoogstens één reservering."""
        gebruik = {}
        for tafels in self.tafels().values():
            for tafel in tafels:
                gebruik[tafel] = gebruik.get(tafel, 0) + 1
        return gebruik

    def overzicht(self):
        return self.client.get(f"/overzicht?datum={DAG}").get_data(as_text=True)

    def test_1_no_show_verliest_zijn_tafels(self):
        self.reservering("a", tafels=["8"])
        antwoord = self.zet("a", "no_show")
        self.assertEqual(antwoord.status_code, 302)
        self.assertEqual(self.tafels(), {})

    def test_2_terug_op_verwacht_krijgt_een_nieuw_voorstel(self):
        self.reservering("a", tafels=["8"])
        self.zet("a", "no_show")
        self.zet("a", "verwacht")
        self.assertEqual(self.tafels(), {})
        html = self.overzicht()
        self.assertIn("Voorstel: 8", html)
        self.assertIn("Accepteren", html)

    def test_3_tafel_van_een_no_show_gaat_naar_een_ander(self):
        self.reservering("weg", tijd="18:00", tafels=["8"])
        self.reservering("ander", tijd="19:00")
        self.zet("weg", "no_show")
        self.wijs_toe("ander", ["8"])  # de vrijgekomen tafel gaat naar een andere reservering
        self.zet("weg", "verwacht")
        self.assertEqual(self.tafels(), {"ander": ["8"]})
        self.assertEqual(self.tafelgebruik(), {"8": 1})

    def test_4_gearriveerd_houdt_zijn_tafels(self):
        self.reservering("a", tafels=["8"])
        self.zet("a", "gearriveerd")
        self.assertEqual(self.tafels(), {"a": ["8"]})

    def test_5_no_show_telt_mee_in_de_tellingen(self):
        self.reservering("a", tafels=["8"])
        self.zet("a", "no_show")
        with self.app.app_context():
            tellingen = tellingen_per_dag(get_db(), DAG, DAG)
        self.assertEqual(tellingen[(DAG, "online")]["no_shows"], 1)


if __name__ == "__main__":
    unittest.main()
