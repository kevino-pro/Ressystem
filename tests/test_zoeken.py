"""Deel 8: zoeken op naam of telefoonnummer in de reserveringen van vandaag en later."""
import itertools
import re
import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from sqlalchemy import insert

from app import create_app
from app.database import get_db, init_db, reserveringen, tafeltoewijzingen
from app.reserveringsregels import ReserveringsRegels
from app.routes.web import ZOEK_MAX_RESULTATEN, zoek_reserveringen
from app.security import reset_rate_limits
from tests.hulp import log_in
from tests.test_toegang import TestConfig

NU = datetime(2030, 1, 1, 12, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
VANDAAG, MORGEN, GISTEREN = "2030-01-01", "2030-01-02", "2029-12-31"
IDS = itertools.count(1)


def r(naam, telefoon="0611111111"):
    return {"naam": naam, "telefoon": telefoon}


class ZoekFunctieTests(unittest.TestCase):
    def namen(self, lijst, zoekterm):
        return [x["naam"] for x in zoek_reserveringen(lijst, zoekterm)]

    def test_deel_van_de_naam_zonder_hoofdletters(self):
        lijst = [r("Siti Rahma"), r("Budi"), r("Rahmat")]
        self.assertEqual(self.namen(lijst, "RAHM"), ["Siti Rahma", "Rahmat"])

    def test_accenten_en_spaties_maken_niet_uit(self):
        lijst = [r("José  de Vries"), r("Jose Ramos")]
        self.assertEqual(self.namen(lijst, "jose"), ["José  de Vries", "Jose Ramos"])
        self.assertEqual(self.namen(lijst, "  josé de vries "), ["José  de Vries"])

    def test_telefoonnummer_in_elke_schrijfwijze(self):
        lijst = [r("A", "06-12345678"), r("B", "+31 6 87654321"), r("C", "")]
        for zoekterm in ("0612", "06 12 34", "+31 612", "612345"):
            with self.subTest(zoekterm=zoekterm):
                self.assertEqual(self.namen(lijst, zoekterm), ["A"])
        self.assertEqual(self.namen(lijst, "0031687"), ["B"])

    def test_te_weinig_cijfers_is_geen_telefoonnummer(self):
        self.assertEqual(self.namen([r("A", "0612345678")], "06"), [])


class Basis(unittest.TestCase):
    rol = "medewerker"

    def setUp(self):
        reset_rate_limits()
        patcher = mock.patch.object(ReserveringsRegels, "nu", lambda self: NU)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app = create_app(TestConfig)
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():
                conn.execute(tafeltoewijzingen.delete())
                conn.execute(reserveringen.delete())
        self.client = self.app.test_client()
        log_in(self.app, self.client, naam="anna", rol=self.rol)

    def voeg_toe(self, naam, datum=VANDAAG, tijd="18:00", telefoon="0611111111", status="verwacht"):
        rid = f"res-{next(IDS)}"
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=rid, naam=naam, email="", telefoon=telefoon, datum=datum, tijd=tijd, aantal=2, status=status))
        return rid

    def zoek(self, zoekterm):
        antwoord = self.client.get("/zoeken", query_string={"q": zoekterm})
        self.assertEqual(antwoord.status_code, 200)
        return antwoord.get_data(as_text=True)


class ZoekPaginaTests(Basis):
    def test_alleen_voor_personeel(self):
        antwoord = self.app.test_client().get("/zoeken?q=Siti")
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn("/login", antwoord.headers["Location"])

    def test_vindt_reservering_met_link_naar_de_dag(self):
        self.voeg_toe("Siti Rahma", datum=MORGEN, tijd="19:00")
        html = self.zoek("siti")
        self.assertIn("19:00 · Siti Rahma", html)
        self.assertIn('href="/overzicht?datum=2030-01-02"', html)
        self.assertIn("Woensdag 2 januari", html)

    def test_geen_oude_reserveringen(self):
        self.voeg_toe("Siti Gisteren", datum=GISTEREN)
        self.voeg_toe("Siti Vandaag", datum=VANDAAG)
        html = self.zoek("siti")
        self.assertIn("Siti Vandaag", html)
        self.assertNotIn("Siti Gisteren", html)

    def test_op_datum_en_tijd_gegroepeerd(self):
        self.voeg_toe("Siti B", datum=MORGEN, tijd="12:00")
        self.voeg_toe("Siti A", datum=VANDAAG, tijd="20:00")
        self.voeg_toe("Siti C", datum=VANDAAG, tijd="13:00")
        html = self.zoek("siti")
        volgorde = [html.index(naam) for naam in ("Siti C", "Siti A", "Siti B")]
        self.assertEqual(volgorde, sorted(volgorde))
        self.assertEqual(html.count('class="tijdkop datumkop"'), 2)

    def test_op_telefoonnummer(self):
        self.voeg_toe("Budi", telefoon="+31 6 12345678")
        self.voeg_toe("Ani", telefoon="0687654321")
        html = self.zoek("06 1234")
        self.assertIn("Budi", html)
        self.assertNotIn("Ani", html)

    def test_te_korte_zoekterm(self):
        self.voeg_toe("Siti")
        html = self.zoek("s")
        self.assertIn("Typ minstens 2 tekens.", html)
        self.assertNotIn('class="lijst"', html)

    def test_zonder_zoekterm_geen_melding(self):
        html = self.zoek("")
        self.assertNotIn("Typ minstens", html)
        self.assertNotIn("Geen reserveringen gevonden", html)

    def test_niets_gevonden(self):
        self.voeg_toe("Siti")
        self.assertIn("Geen reserveringen gevonden.", self.zoek("Budi"))

    def test_hoogstens_vijftig_resultaten(self):
        for i in range(ZOEK_MAX_RESULTATEN + 1):
            self.voeg_toe(f"Siti {i:02d}", tijd=f"{12 + i // 10}:{i % 10}0")
        html = self.zoek("siti")
        self.assertIn("Meer dan 50 resultaten", html)
        self.assertEqual(html.count('class="res zoek'), ZOEK_MAX_RESULTATEN)

    def test_status_zichtbaar(self):
        self.voeg_toe("Siti Weg", status="no_show")
        self.voeg_toe("Siti Binnen", status="gearriveerd")
        html = self.zoek("siti")
        self.assertIn("Niet gekomen", html)
        self.assertIn("Is er", html)

    def test_naam_en_zoekterm_worden_ge_escaped(self):
        self.voeg_toe("<script>alert(1)</script> Siti")
        html = self.zoek('Siti"><b>x')
        self.assertNotIn("<script>alert(1)", html)
        self.assertNotIn('"><b>x', html)
        html = self.zoek("siti")
        self.assertIn("&lt;script&gt;", html)

    def test_geen_reservering_id_in_de_pagina(self):
        rid = self.voeg_toe("Siti")
        self.assertNotIn(rid, self.zoek("siti"))

    def test_lange_zoekterm_wordt_ingekort(self):
        html = self.zoek("a" * 500)
        self.assertIn('name="q" value="' + "a" * 100 + '"', html)

    def test_zoekveld_in_het_overzicht(self):
        html = self.client.get("/overzicht").get_data(as_text=True)
        self.assertRegex(html, r'<form class="zoek" action="/zoeken" method="GET" role="search">')
        self.assertIn('name="q"', html)


class BeheerderTests(Basis):
    rol = "beheerder"

    def test_beheerder_mag_ook_zoeken(self):
        self.voeg_toe("Siti")
        self.assertIn("Siti", self.zoek("siti"))


if __name__ == "__main__":
    unittest.main()
