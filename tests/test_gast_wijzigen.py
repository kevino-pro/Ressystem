"""Deel 9: de gast wijzigt zelf dag, tijd of aantal personen via de link in de mail."""
import itertools
import os
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, time
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, func, insert, inspect, select

from app import create_app
from app.database import (
    CapaciteitVolFout, DubbeleReserveringFout, KinderstoelVolFout, NietMeerWijzigbaarFout, get_db, init_db,
    reserveringen, tafeltoewijzingen, wijzig_reservering,
)
from app.reserveringsregels import ReserveringsRegels, laad_regels
from app.security import reset_rate_limits
from tests.test_toegang import TestConfig

PROJECTMAP = Path(__file__).resolve().parent.parent
NU = datetime(2030, 1, 1, 12, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))  # een dinsdag
VANDAAG, MORGEN, MAANDAG = "2030-01-01", "2030-01-02", "2030-01-07"  # op maandag is het restaurant dicht
NUMMERS = itertools.count(20000000)
CSRF = re.compile(r'name="csrf_token" value="([^"]+)"')


class MetCsrfConfig(TestConfig):
    CSRF_ENABLED = True


class RegelTests(unittest.TestCase):
    def setUp(self):
        self.regels = laad_regels(PROJECTMAP / "restaurants" / "wpl.toml")

    def test_wpl_wijzigen_tot_twee_uur_van_tevoren(self):
        self.assertEqual(self.regels.wijzigen_minuten_vooraf, 120)

    def test_precies_twee_uur_mag_nog(self):
        self.assertTrue(self.regels.kan_nog_wijzigen(date(2030, 1, 1), time(14, 0), nu=NU))
        self.assertFalse(self.regels.kan_nog_wijzigen(date(2030, 1, 1), time(13, 59), nu=NU))
        self.assertFalse(self.regels.kan_nog_wijzigen(date(2029, 12, 31), time(18, 0), nu=NU))

    def test_standaard_en_ongeldig(self):
        basis = {"openingstijden": {"dinsdag": [["12:00", "20:00"]]}}
        self.assertEqual(ReserveringsRegels.model_validate(basis).wijzigen_minuten_vooraf, 120)
        with self.assertRaises(ValueError):
            ReserveringsRegels.model_validate({**basis, "wijzigen_minuten_vooraf": -1})


class Basis(unittest.TestCase):
    config = TestConfig

    def setUp(self):
        reset_rate_limits()
        patcher = mock.patch.object(ReserveringsRegels, "nu", lambda self: NU)
        patcher.start()
        self.addCleanup(patcher.stop)
        mail = mock.patch("app.routes.web.stuur_wijzigingsmail_async")  # deel 9 fase 2: de wijzigingsmail
        self.wijzigingsmail = mail.start()
        self.addCleanup(mail.stop)
        self.app = create_app(self.config)
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():
                conn.execute(tafeltoewijzingen.delete())
                conn.execute(reserveringen.delete())
        self.client = self.app.test_client()
        self.client.environ_base["HTTP_ACCEPT_LANGUAGE"] = "nl"

    def voeg_toe(self, datum=MORGEN, tijd="18:00", aantal=2, email=None, kinderstoelen=0, status="verwacht",
                 herinnering=None):
        nummer = next(NUMMERS)
        rid = f"res-{nummer}"
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=rid, naam="Siti Rahma", email=email or f"gast{nummer}@example.com", telefoon=f"06{nummer}",
                    datum=datum, tijd=tijd, aantal=aantal, kinderstoelen=kinderstoelen, status=status,
                    herinnering_verstuurd=herinnering))
        return rid

    def lees(self, rid):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                return conn.execute(select(reserveringen).where(reserveringen.c.id == rid)).mappings().first()

    def wijzig(self, rid, **velden):
        """wijzig_reservering met de regels van Den Haag (69 gasten tegelijk, 1 uur, 2 kinderstoelen)."""
        with self.app.app_context():
            return wijzig_reservering(get_db(), rid, 69, velden.get("datum", MORGEN), velden.get("tijd", "18:00"),
                                      velden.get("aantal", 2), 60, max_kinderstoelen=2)


class WijzigFunctieTests(Basis):
    def test_zet_nieuwe_dag_tijd_en_aantal(self):
        rid = self.voeg_toe()
        nieuw = self.wijzig(rid, datum="2030-01-03", tijd="19:30", aantal=4)
        self.assertEqual((nieuw["datum"], nieuw["tijd"], nieuw["aantal"]), ("2030-01-03", "19:30", 4))
        self.assertIsNotNone(self.lees(rid)["gewijzigd_op"])

    def test_verliest_tafels(self):
        rid, ander = self.voeg_toe(), self.voeg_toe()
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(tafeltoewijzingen), [
                    {"reservering_id": rid, "tafel": "4"}, {"reservering_id": ander, "tafel": "8"}])
        self.wijzig(rid, tijd="19:00")
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                over = conn.execute(select(tafeltoewijzingen.c.reservering_id)).scalars().all()
        self.assertEqual(over, [ander])

    def test_eigen_plaatsen_tellen_niet_mee(self):
        self.voeg_toe(aantal=15)
        self.voeg_toe(aantal=15)
        self.voeg_toe(aantal=15)
        self.voeg_toe(aantal=12)  # 57 anderen
        rid = self.voeg_toe(aantal=10)  # samen 67 van de 69
        self.assertEqual(self.wijzig(rid, aantal=12)["aantal"], 12)  # 57 + 12 = 69 past precies
        with self.assertRaises(CapaciteitVolFout) as fout:
            self.wijzig(rid, aantal=13)
        self.assertEqual(fout.exception.vrij, 12)
        self.assertEqual(self.lees(rid)["aantal"], 12)  # niets veranderd

    def test_no_show_telt_niet_mee(self):
        self.voeg_toe(aantal=15, status="no_show")
        for _ in range(4):
            self.voeg_toe(aantal=14)  # 56 gasten
        rid = self.voeg_toe(datum="2030-01-03")
        self.assertEqual(self.wijzig(rid, aantal=13)["datum"], MORGEN)

    def test_zelfde_gast_al_op_die_tijd(self):
        rid = self.voeg_toe(email="siti@example.com")
        self.voeg_toe(tijd="19:00", email="siti@example.com")
        with self.assertRaises(DubbeleReserveringFout):
            self.wijzig(rid, tijd="19:00")
        self.assertEqual(self.wijzig(rid, aantal=3)["aantal"], 3)  # zichzelf telt niet als dubbel

    def test_kinderstoelen(self):
        rid = self.voeg_toe(kinderstoelen=2)
        self.voeg_toe(tijd="19:30", kinderstoelen=1)
        with self.assertRaises(KinderstoelVolFout):
            self.wijzig(rid, tijd="19:00")  # 19:00-20:00 overlapt met 19:30
        self.assertEqual(self.wijzig(rid, aantal=4)["aantal"], 4)  # eigen stoelen tellen niet mee
        self.assertEqual(self.wijzig(rid, tijd="18:30")["tijd"], "18:30")  # 18:30-19:30 raakt 19:30 niet
        self.assertEqual(self.lees(rid)["kinderstoelen"], 2)

    def test_herinnering_opnieuw_bij_andere_dag(self):
        verstuurd = datetime(2030, 1, 1, 9, 0)
        rid = self.voeg_toe(herinnering=verstuurd)
        self.wijzig(rid, tijd="19:00")
        self.assertEqual(self.lees(rid)["herinnering_verstuurd"], verstuurd)  # zelfde dag: niet nog eens
        self.wijzig(rid, datum="2030-01-04", tijd="19:00")
        self.assertIsNone(self.lees(rid)["herinnering_verstuurd"])

    def test_alleen_als_verwacht(self):
        for status in ("gearriveerd", "no_show"):
            with self.subTest(status=status):
                rid = self.voeg_toe(status=status)
                with self.assertRaises(NietMeerWijzigbaarFout):
                    self.wijzig(rid, tijd="19:00")
                self.assertEqual(self.lees(rid)["tijd"], "18:00")
        with self.assertRaises(NietMeerWijzigbaarFout):
            self.wijzig("bestaat-niet")


class WijzigPaginaTests(Basis):
    def post(self, rid, **velden):
        data = {"datum": MORGEN, "tijd": "18:00", "aantal": "2", **velden}
        return self.client.post(f"/wijzigen/{rid}", data=data)

    def test_pagina_toont_wijzigen_en_annuleren(self):
        rid = self.voeg_toe(tijd="18:30", aantal=3)
        html = self.client.get(f"/annuleren/{rid}").get_data(as_text=True)
        self.assertIn("Wijzig of annuleer", html)
        self.assertIn(f'action="/wijzigen/{rid}"', html)
        self.assertIn('name="tijd" id="veld_tijd" value="18:30"', html)
        self.assertIn('<option value="3" selected>', html)
        self.assertIn("&behalve=", html)
        self.assertIn("Ja, annuleer mijn reservering", html)
        self.assertIn("Wijzigen kan tot 2 uur van tevoren.", html)

    def test_wijzigen_lukt(self):
        rid = self.voeg_toe()
        antwoord = self.post(rid, datum="2030-01-03", tijd="19:30", aantal="5")
        self.assertEqual(antwoord.status_code, 200)
        html = antwoord.get_data(as_text=True)
        self.assertIn("Reservering gewijzigd", html)
        self.assertIn("19:30", html)
        rij = self.lees(rid)
        self.assertEqual((rij["datum"], rij["tijd"], rij["aantal"]), ("2030-01-03", "19:30", 5))

    def test_binnen_twee_uur_alleen_annuleren(self):
        rid = self.voeg_toe(datum=VANDAAG, tijd="13:30")  # over anderhalf uur
        html = self.client.get(f"/annuleren/{rid}").get_data(as_text=True)
        self.assertIn("Je reservering begint binnen 2 uur. Wijzigen kan nu niet meer online.", html)
        self.assertNotIn("wijzigForm", html)
        self.assertIn("Ja, annuleer mijn reservering", html)
        self.assertEqual(self.post(rid, datum=VANDAAG, tijd="19:00").status_code, 409)
        self.assertEqual(self.lees(rid)["tijd"], "13:30")

    def test_over_precies_twee_uur_mag_nog(self):
        rid = self.voeg_toe(datum=VANDAAG, tijd="14:00")
        self.assertEqual(self.post(rid, datum=VANDAAG, tijd="19:00").status_code, 200)

    def test_zelfde_regels_als_reserveren(self):
        rid = self.voeg_toe()
        gevallen = {
            "gesloten": ({"datum": MAANDAG}, "Het restaurant is op maandag gesloten."),
            "buiten openingstijd": ({"tijd": "21:00"}, "Op woensdag kun je reserveren tussen 12:00-20:00."),
            "geen kwartier": ({"tijd": "18:10"}, "Kies een tijd per 15 minuten"),
            "te groot": ({"aantal": "16"}, "Online reserveren kan voor 1 tot 15 personen."),
            "te ver vooruit": ({"datum": "2030-06-01"}, "Je kunt maximaal 90 dagen vooruit reserveren."),
            "te kort dag": ({"datum": VANDAAG, "tijd": "12:30"}, "Reserveer minstens 60 minuten van tevoren."),
            "niets veranderd": ({}, "Je hebt niets veranderd."),
            "geen tijd": ({"tijd": "19:3"}, "Kies een dag en een tijd."),
            "geen datum": ({"datum": "morgen"}, "Kies een dag en een tijd."),
        }
        for naam, (velden, melding) in gevallen.items():
            with self.subTest(naam):
                antwoord = self.post(rid, **velden)
                self.assertEqual(antwoord.status_code, 400)
                self.assertIn(melding, antwoord.get_data(as_text=True))
        rij = self.lees(rid)
        self.assertEqual((rij["datum"], rij["tijd"], rij["aantal"], rij["gewijzigd_op"]), (MORGEN, "18:00", 2, None))

    def test_mislukte_poging_houdt_keuze_vast(self):
        rid = self.voeg_toe()
        html = self.post(rid, datum=MAANDAG, tijd="19:00", aantal="4").get_data(as_text=True)
        self.assertIn('"datum": "2030-01-07"', html)
        self.assertIn('<option value="4" selected>', html)

    def test_annuleerknop_na_mislukte_poging_post_naar_annuleren(self):
        # Dezelfde pagina komt terug op /wijzigen/<id>; een formulier zonder action zou daarheen posten en
        # de gast kon dan niet meer annuleren. De knop moet altijd naar /annuleren/<id> wijzen.
        rid = self.voeg_toe()
        antwoord = self.post(rid, tijd="19:3")  # 400: "Kies een dag en een tijd."
        self.assertEqual(antwoord.status_code, 400)
        self.assertIn(f'<form method="POST" action="/annuleren/{rid}">', antwoord.get_data(as_text=True))
        # 409: de reservering begint al binnen twee uur, dus annuleren is de enige optie die overblijft.
        dichtbij = self.voeg_toe(datum=VANDAAG, tijd="13:30")
        antwoord = self.post(dichtbij, datum=VANDAAG, tijd="19:00")
        self.assertEqual(antwoord.status_code, 409)
        self.assertIn(f'<form method="POST" action="/annuleren/{dichtbij}">', antwoord.get_data(as_text=True))
        self.assertEqual(self.lees(dichtbij)["tijd"], "13:30")

    def test_vol(self):
        for _ in range(5):
            self.voeg_toe(tijd="19:00", aantal=13)  # 65 gasten
        rid = self.voeg_toe()
        antwoord = self.post(rid, tijd="19:00", aantal="5")
        self.assertEqual(antwoord.status_code, 400)
        self.assertIn("Geen plek meer op dit tijdstip. Nog 4 plek(ken) beschikbaar.", antwoord.get_data(as_text=True))
        self.assertEqual(self.post(rid, tijd="19:00", aantal="4").status_code, 200)

    def test_al_andere_reservering_op_die_tijd(self):
        rid = self.voeg_toe(email="siti@example.com")
        self.voeg_toe(tijd="19:00", email="SITI@example.com")
        antwoord = self.post(rid, tijd="19:00")
        self.assertEqual(antwoord.status_code, 409)
        self.assertIn("Je hebt op deze dag en tijd al een andere reservering.", antwoord.get_data(as_text=True))

    def test_na_aankomst_of_onbekend(self):
        rid = self.voeg_toe(status="gearriveerd")
        self.assertEqual(self.post(rid, tijd="19:00").status_code, 409)
        self.assertEqual(self.post("bestaat-niet", tijd="19:00").status_code, 404)

    def test_grote_groep_van_het_personeel_belt(self):
        rid = self.voeg_toe(aantal=20)  # telefonisch aangenomen, groter dan online mag
        html = self.client.get(f"/annuleren/{rid}").get_data(as_text=True)
        self.assertIn("Een reservering voor zoveel personen kun je niet online wijzigen.", html)
        self.assertNotIn("wijzigForm", html)
        self.assertEqual(self.post(rid, aantal="10").status_code, 409)

    def test_beschikbaarheid_zonder_eigen_plaatsen(self):
        for _ in range(4):
            self.voeg_toe(aantal=15)  # 60 gasten om 18:00
        rid = self.voeg_toe(aantal=8)  # 68
        def knop(**extra):
            data = self.client.get("/beschikbaarheid", query_string={"datum": MORGEN, "aantal": 9, **extra}).get_json()
            return next(t for t in data["tijden"] if t["tijd"] == "18:00")
        self.assertFalse(knop()["beschikbaar"])
        self.assertEqual(knop(behalve=rid), {"tijd": "18:00", "vrij": 9, "beschikbaar": True})

    def test_taalkeuze_na_een_poging_gaat_terug_naar_de_pagina(self):
        rid = self.voeg_toe()
        antwoord = self.client.get(f"/wijzigen/{rid}")  # de taallinks wijzen naar het huidige pad
        self.assertEqual(antwoord.status_code, 302)
        self.assertTrue(antwoord.headers["Location"].endswith(f"/annuleren/{rid}"))

    def test_in_het_engels(self):
        rid = self.voeg_toe()
        html = self.client.get(f"/annuleren/{rid}", headers={"Accept-Language": "en"}).get_data(as_text=True)
        self.assertIn("Change or cancel", html)
        self.assertIn("Cancel your booking?", html)
        self.assertIn("Save change", html)


class WijzigCsrfTests(Basis):
    config = MetCsrfConfig

    def test_zonder_token_geweigerd(self):
        rid = self.voeg_toe()
        data = {"datum": MORGEN, "tijd": "19:00", "aantal": "2"}
        self.assertEqual(self.client.post(f"/wijzigen/{rid}", data=data).status_code, 400)
        token = CSRF.search(self.client.get(f"/annuleren/{rid}").get_data(as_text=True)).group(1)
        self.assertEqual(self.client.post(f"/wijzigen/{rid}", data={**data, "csrf_token": token}).status_code, 200)
        self.assertEqual(self.lees(rid)["tijd"], "19:00")


class MigratieTests(unittest.TestCase):
    def test_kolom_gewijzigd_op_op_en_neer(self):
        with tempfile.TemporaryDirectory() as map_:
            url = f"sqlite:///{Path(map_) / 'migratie.db'}"
            omgeving = {**os.environ, "MIGRATION_DATABASE_URL": url}
            omgeving.pop("ALLOW_PROD_MIGRATE", None)

            def alembic(*args):
                resultaat = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=PROJECTMAP, env=omgeving,
                                           capture_output=True, text=True)
                self.assertEqual(resultaat.returncode, 0, resultaat.stderr)

            def kolommen(engine):
                return {k["name"] for k in inspect(engine).get_columns("reserveringen")}

            alembic("upgrade", "head")
            engine = create_engine(url)
            self.assertIn("gewijzigd_op", kolommen(engine))
            alembic("downgrade", "c6f3a9d1e8b5")
            self.assertNotIn("gewijzigd_op", kolommen(engine))
            self.assertIn("herinnering_verstuurd", kolommen(engine))
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
