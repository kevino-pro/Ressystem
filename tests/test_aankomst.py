"""Gearriveerd en no-show: het personeel vinkt aan wie er is en wie niet kwam (deel 5)."""
import itertools
import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app import create_app
from app.database import (
    CapaciteitVolFout, GeenReserveringFout, get_db, init_db, reserveringen, tafeltoewijzingen,
    verwerk_reservering, wijs_tafels_toe, zet_status,
)
from app.reserveringsregels import ReserveringsRegels
from app.routes.web import _kenmerk
from app.security import reset_rate_limits
from tests.hulp import log_in
from tests.test_toegang import TestConfig

NU = datetime(2030, 1, 1, 18, 7, tzinfo=ZoneInfo("Europe/Amsterdam"))  # een dinsdag
VANDAAG = "2030-01-01"
MORGEN = "2030-01-02"
GISTEREN = "2029-12-31"
NUMMERS = itertools.count(10000000)  # elk testgast een eigen telefoonnummer


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

    def reservering(self, naam="Siti", tijd="18:00", datum=VANDAAG, aantal=4, telefoon=None):
        with self.app.app_context():
            return verwerk_reservering(get_db(), None, naam, "", telefoon or f"06{next(NUMMERS)}",
                                       datum, tijd, aantal, zitduur_minuten=60)

    def kenmerk(self, reservering_id):
        with self.app.test_request_context():
            return _kenmerk(reservering_id)

    def zet(self, reservering_id, status, datum=VANDAAG, **velden):
        data = {"datum": datum, "kenmerk": self.kenmerk(reservering_id), "status": status, **velden}
        return self.client.post("/aankomst", data=data)

    def status(self, reservering_id):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                return conn.execute(
                    select(reserveringen.c.status).where(reserveringen.c.id == reservering_id)
                ).scalar()


class StatusZettenTests(Basis):
    def test_nieuwe_reservering_is_verwacht(self):
        self.assertEqual(self.status(self.reservering()), "verwacht")

    def test_is_er(self):
        rid = self.reservering()
        antwoord = self.zet(rid, "gearriveerd")
        self.assertEqual(antwoord.status_code, 302)
        self.assertEqual(antwoord.headers["Location"], f"/overzicht?datum={VANDAAG}")
        self.assertEqual(self.status(rid), "gearriveerd")
        html = self.client.get(f"/overzicht?datum={VANDAAG}").get_data(as_text=True)
        self.assertIn("Siti is er.", html)
        self.assertIn('class="res aangekomen', html)

    def test_no_show_na_de_begintijd(self):
        rid = self.reservering(tijd="18:00")
        self.zet(rid, "no_show")
        self.assertEqual(self.status(rid), "no_show")

    def test_no_show_voor_de_begintijd_geweigerd(self):
        rid = self.reservering(tijd="19:00")
        antwoord = self.zet(rid, "no_show")
        self.assertEqual(antwoord.status_code, 302)
        self.assertEqual(self.status(rid), "verwacht")
        html = self.client.get(f"/overzicht?datum={VANDAAG}").get_data(as_text=True)
        self.assertIn("Een no-show kan pas na de begintijd (19:00).", html)

    def test_terugdraaien(self):
        rid = self.reservering()
        self.zet(rid, "no_show")
        self.zet(rid, "verwacht")
        self.assertEqual(self.status(rid), "verwacht")

    def test_toekomstige_dag_geweigerd(self):
        rid = self.reservering(datum=MORGEN)
        self.zet(rid, "gearriveerd", datum=MORGEN)
        self.assertEqual(self.status(rid), "verwacht")

    def test_dag_in_het_verleden_mag_nog(self):
        rid = self.reservering(datum=GISTEREN, tijd="20:00")
        self.zet(rid, "no_show", datum=GISTEREN)
        self.assertEqual(self.status(rid), "no_show")

    def test_terug_naar_de_plattegrond(self):
        rid = self.reservering()
        antwoord = self.zet(rid, "gearriveerd", terug="plattegrond")
        self.assertEqual(antwoord.headers["Location"], f"/plattegrond?datum={VANDAAG}&tijd=18:00")

    def test_ongeldige_status(self):
        rid = self.reservering()
        self.assertEqual(self.zet(rid, "weg").status_code, 400)
        self.assertEqual(self.status(rid), "verwacht")

    def test_ongeldige_datum(self):
        rid = self.reservering()
        self.assertEqual(self.zet(rid, "gearriveerd", datum="gisteren").status_code, 400)

    def test_id_werkt_niet_als_kenmerk(self):
        rid = self.reservering()
        antwoord = self.client.post("/aankomst", data={"datum": VANDAAG, "kenmerk": rid, "status": "gearriveerd"})
        self.assertEqual(antwoord.status_code, 404)
        self.assertEqual(self.status(rid), "verwacht")

    def test_kenmerk_van_een_andere_dag(self):
        rid = self.reservering(datum=GISTEREN)
        self.assertEqual(self.zet(rid, "gearriveerd", datum=VANDAAG).status_code, 404)

    def test_niet_ingelogd(self):
        rid = self.reservering()
        self.client.post("/logout")
        antwoord = self.zet(rid, "gearriveerd")
        self.assertNotEqual(antwoord.status_code, 200)
        self.assertNotIn("/overzicht", antwoord.headers.get("Location", ""))
        self.assertEqual(self.status(rid), "verwacht")


class ZetStatusTests(Basis):
    def test_onbekende_status(self):
        rid = self.reservering()
        with self.app.app_context(), self.assertRaises(ValueError):
            zet_status(get_db(), rid, "misschien")

    def test_onbekende_reservering(self):
        with self.app.app_context(), self.assertRaises(GeenReserveringFout):
            zet_status(get_db(), "bestaat-niet", "gearriveerd")


class NoShowGeeftRuimteTests(Basis):
    def test_plaatsen_komen_vrij(self):
        rid = self.reservering(naam="Groep", aantal=69)
        with self.app.app_context():
            with self.assertRaises(CapaciteitVolFout):
                verwerk_reservering(get_db(), 69, "Online", "o@voorbeeld.nl", "0611111111",
                                    VANDAAG, "18:30", 2, zitduur_minuten=60)
        self.zet(rid, "no_show")
        with self.app.app_context():
            verwerk_reservering(get_db(), 69, "Online", "o@voorbeeld.nl", "0611111111",
                                VANDAAG, "18:30", 2, zitduur_minuten=60)

    def test_tafel_komt_vrij(self):
        weg = self.reservering(naam="Weg", tijd="18:00")
        nieuw = self.reservering(naam="Nieuw", tijd="18:15")
        indeling = self.app.config["PLATTEGROND"]
        tafel = indeling.tafels[0].nummer
        with self.app.app_context():
            wijs_tafels_toe(get_db(), weg, [tafel], indeling, 60)
        self.zet(weg, "no_show")
        with self.app.app_context():
            wijs_tafels_toe(get_db(), nieuw, [tafel], indeling, 60)
        html = self.client.get(f"/plattegrond?datum={VANDAAG}&tijd=18:05").get_data(as_text=True)
        self.assertIn("Niet gekomen · 1", html)
        self.assertIn("Niet gekomen · de plaatsen zijn weer vrij", html)

    def test_overzicht_telt_no_show_niet_mee(self):
        self.reservering(naam="A", aantal=4)
        rid = self.reservering(naam="B", aantal=6)
        self.zet(rid, "no_show")
        html = self.client.get(f"/overzicht?datum={VANDAAG}").get_data(as_text=True)
        self.assertIn("<small>Gasten</small><b>4</b>", html)
        self.assertIn("Niet gekomen</span>", html)
        self.assertEqual(html.count("+ Tafel kiezen"), 1)  # niet bij de no-show


class WeergaveTests(Basis):
    def test_knoppen_vandaag(self):
        self.reservering(naam="Vroeg", tijd="18:00")
        self.reservering(naam="Laat", tijd="19:00")
        html = self.client.get(f"/overzicht?datum={VANDAAG}").get_data(as_text=True)
        self.assertEqual(html.count('value="gearriveerd">Is er</button>'), 2)
        self.assertEqual(html.count('value="no_show">Niet gekomen</button>'), 1)  # alleen na de begintijd
        self.assertIn("<small>Nog niet binnen</small><b>2</b>", html)

    def test_geen_knoppen_voor_morgen(self):
        self.reservering(datum=MORGEN)
        html = self.client.get(f"/overzicht?datum={MORGEN}").get_data(as_text=True)
        self.assertNotIn('action="/aankomst"', html)
        self.assertNotIn("Nog niet binnen", html)

    def test_geen_id_in_het_overzicht_voor_medewerker(self):
        rid = self.reservering()
        html = self.client.get(f"/overzicht?datum={VANDAAG}").get_data(as_text=True)
        self.assertNotIn(rid, html)

    def test_ongedaan_maken_knop(self):
        rid = self.reservering()
        self.zet(rid, "gearriveerd")
        html = self.client.get(f"/overzicht?datum={VANDAAG}").get_data(as_text=True)
        self.assertIn('value="verwacht">Ongedaan maken</button>', html)
        self.assertNotIn('value="gearriveerd">Is er</button>', html)

    def test_plattegrond_nog_niet_binnen(self):
        rid = self.reservering(naam="Siti", tijd="18:00")
        self.reservering(naam="Dewi", tijd="18:00")
        self.zet(rid, "gearriveerd")
        html = self.client.get(f"/plattegrond?datum={VANDAAG}&tijd=18:05").get_data(as_text=True)
        self.assertIn("· is er", html)
        self.assertIn("· nog niet binnen", html)

    def test_naam_wordt_ge_escaped(self):
        rid = self.reservering(naam="<b>x</b>")
        self.zet(rid, "gearriveerd")
        html = self.client.get(f"/overzicht?datum={VANDAAG}").get_data(as_text=True)
        self.assertIn("&lt;b&gt;x&lt;/b&gt; is er.", html)


class AnnulerenTests(Basis):
    def test_na_no_show_niet_meer_annuleren(self):
        rid = self.reservering()
        self.zet(rid, "no_show")
        self.client.post("/logout")
        self.assertEqual(self.client.get(f"/annuleren/{rid}").status_code, 409)
        self.assertEqual(self.client.post(f"/annuleren/{rid}").status_code, 409)
        self.assertEqual(self.status(rid), "no_show")

    def test_verwacht_kan_nog_annuleren(self):
        rid = self.reservering()
        self.client.post("/logout")
        self.assertEqual(self.client.get(f"/annuleren/{rid}").status_code, 200)


class BeheerderTests(Basis):
    rol = "beheerder"

    def test_beheerder_mag_ook(self):
        rid = self.reservering()
        self.zet(rid, "gearriveerd")
        self.assertEqual(self.status(rid), "gearriveerd")


if __name__ == "__main__":
    unittest.main()
