"""Tafelvoorstel in het overzicht: het tonen, het accepteren en het voorstel bij het invoeren (fase 2)."""
import unittest
from unittest import mock

from sqlalchemy import insert

from app import create_app
from app.database import (
    GeenReserveringFout, get_db, haal_toewijzingen_op, init_db, reserveringen, tafeltoewijzingen, wijs_tafels_toe,
)
from app.routes.web import _kenmerk
from app.security import reset_rate_limits
from tests.hulp import log_in
from tests.test_plattegrond_pagina import TestConfig, maak_client

DAG = "2030-01-01"


class TafelvoorstelOverzichtTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app, self.client = maak_client(TestConfig)
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():  # de in-memory database wordt gedeeld tussen tests
                conn.execute(tafeltoewijzingen.delete())
                conn.execute(reserveringen.delete())

    def reservering(self, rid, tijd="19:00", aantal=2, status="verwacht", tafels=()):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=rid, naam=f"Gast {rid}", email=f"{rid}@example.com", telefoon="0612345678",
                    datum=DAG, tijd=tijd, aantal=aantal, status=status))
            if tafels:
                wijs_tafels_toe(conn, rid, list(tafels), self.app.config["PLATTEGROND"], 90)

    def overzicht(self, client=None):
        return (client or self.client).get(f"/overzicht?datum={DAG}").get_data(as_text=True)

    def accepteren(self, rid, tafels, client=None, **kwargs):
        """Wat het overzicht verstuurt: de dag, het kenmerk (niet het id) en de voorgestelde tafels."""
        with self.app.app_context():
            kenmerk = _kenmerk(rid)
        return (client or self.client).post(
            "/tafels/accepteren", data={"datum": DAG, "kenmerk": kenmerk, "tafels": "+".join(tafels)}, **kwargs)

    def tafels(self):
        with self.app.app_context():
            return haal_toewijzingen_op(get_db(), DAG)

    def test_overzicht_toont_voorstel(self):
        self.reservering("a", aantal=2)
        html = self.overzicht()
        self.assertIn("Voorstel:", html)
        self.assertIn("Voorstel: 8", html)  # de kleinste losse tafel die past
        self.assertIn('action="/tafels/accepteren"', html)
        self.assertIn('name="tafels" value="8"', html)
        self.assertIn("Accepteren", html)

    def test_twee_reserveringen_krijgen_verschillende_voorstellen(self):
        self.reservering("a", aantal=2)
        self.reservering("b", aantal=2)
        html = self.overzicht()
        self.assertIn("Voorstel: 8", html)
        self.assertIn("Voorstel: 7b", html)

    def test_accepteren_slaat_tafels_op(self):
        self.reservering("a", aantal=2)
        antwoord = self.accepteren("a", ["8"])
        self.assertEqual(antwoord.status_code, 303)
        with self.app.app_context():
            kenmerk = _kenmerk("a")
        self.assertIn(f"datum={DAG}", antwoord.headers["Location"])
        self.assertIn(f"#r-{kenmerk}", antwoord.headers["Location"])
        self.assertEqual(self.tafels(), {"a": ["8"]})

    def test_na_accepteren_toont_de_rij_de_tafel(self):
        self.reservering("a", aantal=2)
        self.accepteren("a", ["8"])
        html = self.overzicht()
        self.assertIn("Tafel 8", html)
        self.assertNotIn("Voorstel:", html)
        self.assertNotIn("Accepteren", html)

    def test_medewerker_mag_accepteren(self):
        self.reservering("a", aantal=2)
        app = create_app(TestConfig)
        client = app.test_client()
        log_in(app, client, naam="anna", rol="medewerker")
        antwoord = self.accepteren("a", ["8"], client=client)
        self.assertEqual(antwoord.status_code, 303)
        self.assertEqual(self.tafels(), {"a": ["8"]})

    def test_andere_tafels_dan_het_voorstel(self):
        self.reservering("a", aantal=2)
        antwoord = self.accepteren("a", ["9"], follow_redirects=True)
        self.assertEqual(antwoord.status_code, 200)
        self.assertIn("Het voorstel is intussen veranderd", antwoord.get_data(as_text=True))
        self.assertEqual(self.tafels(), {})

    def test_onbekend_kenmerk(self):
        self.reservering("a", aantal=2)
        antwoord = self.client.post("/tafels/accepteren",
                                    data={"datum": DAG, "kenmerk": "0" * 24, "tafels": "8"},
                                    follow_redirects=True)
        self.assertEqual(antwoord.status_code, 200)
        self.assertIn("Deze reservering bestaat niet meer", antwoord.get_data(as_text=True))
        self.assertEqual(self.tafels(), {})

    def test_verdwenen_reservering_geeft_een_melding(self):
        # Tussen het tonen van het voorstel en het klikken op Accepteren is de reservering verwijderd:
        # dan geen foutpagina, maar dezelfde melding als bij een onbekend kenmerk.
        self.reservering("a", aantal=2)
        with mock.patch("app.routes.web.wijs_tafels_toe", side_effect=GeenReserveringFout()):
            antwoord = self.accepteren("a", ["8"], follow_redirects=True)
        self.assertEqual(antwoord.status_code, 200)
        self.assertIn("Deze reservering bestaat niet meer", antwoord.get_data(as_text=True))
        self.assertEqual(self.tafels(), {})

    def test_id_als_kenmerk_werkt_niet(self):
        # Het id is de annuleerlink van de gast; alleen het kenmerk van het overzicht telt.
        self.reservering("a", aantal=2)
        self.client.post("/tafels/accepteren", data={"datum": DAG, "kenmerk": "a", "tafels": "8"})
        self.assertEqual(self.tafels(), {})

    def test_alleen_ingelogd(self):
        self.reservering("a", aantal=2)
        _, client = maak_client(TestConfig, ingelogd=False)
        antwoord = self.accepteren("a", ["8"], client=client)
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn("/login", antwoord.headers["Location"])
        self.assertEqual(self.tafels(), {})

    def test_no_show_krijgt_geen_voorstel(self):
        self.reservering("a", aantal=2, status="no_show")
        html = self.overzicht()
        self.assertNotIn("Voorstel:", html)
        self.assertNotIn("Accepteren", html)

    def test_geen_tafel_vrij(self):
        # Tafel 2 is de enige tafel met zes stoelen; staat die bezet, dan past deze groep nergens.
        self.reservering("a", aantal=6, tafels=["2"])
        self.reservering("b", aantal=6)
        html = self.overzicht()
        self.assertIn("Geen tafel vrij", html)
        self.assertNotIn("Voorstel:", html)

    def test_telefonisch_invoeren_toont_voorstel(self):
        antwoord = self.client.post("/reservering/nieuw", data={
            "bron": "telefoon", "naam": "Piet", "telefoon": "0612345678", "datum": DAG, "tijd": "19:00",
            "aantal": "2",
        })
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn("#r-", antwoord.headers["Location"])
        html = self.overzicht()
        self.assertIn("Voorstel: tafel 8.", html)
        self.assertIn("Voorstel: 8", html)

    def test_binnenloper_krijgt_uitleg_over_de_plattegrond(self):
        # Een binnenloper komt op de plattegrond, dus daar wordt naar verwezen en niet naar het overzicht.
        antwoord = self.client.post("/reservering/nieuw", data={
            "bron": "binnenloper", "datum": DAG, "tijd": "19:00", "aantal": "2",
        })
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn("/plattegrond", antwoord.headers["Location"])
        html = self.client.get(antwoord.headers["Location"]).get_data(as_text=True)
        self.assertIn("Voorstel: tafel 8. Kies de tafel op de plattegrond.", html)
        self.assertNotIn("Accepteer het in het overzicht", html)


if __name__ == "__main__":
    unittest.main()
