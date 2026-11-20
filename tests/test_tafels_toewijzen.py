"""Tafels van een reservering wijzigen via het overzicht (beheerder); de plattegrond is een kijkpagina."""
import unittest

from sqlalchemy import insert

from app.database import get_db, haal_toewijzingen_op, init_db, reserveringen, tafeltoewijzingen
from app.routes.web import _kenmerk
from tests.test_plattegrond_pagina import TestConfig, ZonderPlattegrondConfig, maak_client

DAG = "2030-01-01"


class MetCsrfConfig(TestConfig):
    CSRF_ENABLED = True


class TafelsToewijzenTests(unittest.TestCase):
    def setUp(self):
        self.app, self.client = maak_client(TestConfig)
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():  # de in-memory database wordt gedeeld tussen tests
                conn.execute(tafeltoewijzingen.delete())
                conn.execute(reserveringen.delete())
        self.reservering("a", tijd="19:00", aantal=5)
        self.reservering("b", tijd="20:00", aantal=2)

    def reservering(self, rid, tijd, aantal):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=rid, naam="N", email=f"{rid}@example.com", telefoon="0612345678",
                    datum="2030-01-01", tijd=tijd, aantal=aantal))

    def verzoek(self, rid, tafels):
        """Wat het wijzigformulier verstuurt: de dag, het kenmerk (niet het id) en de tafels."""
        with self.app.app_context():
            return {"datum": DAG, "kenmerk": _kenmerk(rid), "tafels": "+".join(tafels)}

    def post(self, data, client=None, **kwargs):
        return (client or self.client).post("/tafels/wijzigen", data=data, **kwargs)

    def melding(self, data, client=None):
        """Het overzicht na het opslaan: daarin staat de melding van de wijziging."""
        antwoord = self.post(data, client=client, follow_redirects=True)
        self.assertEqual(antwoord.status_code, 200)
        return antwoord.get_data(as_text=True)

    def tafels(self):
        with self.app.app_context():
            return haal_toewijzingen_op(get_db(), "2030-01-01")

    def test_toewijzen(self):
        html = self.melding(self.verzoek("a", ["1a", "1b"]))
        self.assertIn("Tafel 1a + 1b voor N is opgeslagen.", html)
        self.assertEqual(self.tafels(), {"a": ["1a", "1b"]})

    def test_waarschuwing_bij_te_weinig_stoelen(self):
        html = self.melding(self.verzoek("a", ["1a"]))
        self.assertIn("Let op: 4 stoelen voor 5 gasten.", html)
        self.assertEqual(self.tafels(), {"a": ["1a"]})

    def test_bezette_tafel(self):
        self.post(self.verzoek("a", ["2"]))
        html = self.melding(self.verzoek("b", ["2"]))
        self.assertIn("Tafel 2 is al toegewezen aan een reservering van 19:00.", html)
        self.assertEqual(self.tafels(), {"a": ["2"]})

    def test_onbekende_tafel(self):
        html = self.melding(self.verzoek("a", ["99"]))
        self.assertIn("Onbekende tafel: 99.", html)
        self.assertEqual(self.tafels(), {})

    def test_reservering_bestaat_niet(self):
        html = self.melding(self.verzoek("weg", ["1a"]))
        self.assertIn("Deze reservering bestaat niet meer", html)
        self.assertEqual(self.tafels(), {})

    def test_id_zelf_werkt_niet(self):
        # Het id is de annuleerlink van de gast; alleen het kenmerk van het overzicht telt.
        html = self.melding({"datum": DAG, "kenmerk": "a", "tafels": "1a"})
        self.assertIn("Deze reservering bestaat niet meer", html)
        self.assertEqual(self.tafels(), {})

    def test_ongeldige_invoer(self):
        goed = self.verzoek("a", ["1a"])
        # Zonder datum of kenmerk is er geen pagina om naartoe te gaan: een gewone 400.
        for data in ({}, {**goed, "datum": ""}, {**goed, "datum": "morgen"}, {**goed, "kenmerk": ""}):
            with self.subTest(data=data):
                antwoord = self.post(data)
                self.assertEqual(antwoord.status_code, 400)
                self.assertIn("Ongeldig verzoek.", antwoord.get_data(as_text=True))
        # Een lege of te lange keuze: terug naar het overzicht met dezelfde melding.
        for tafels in ("", "+".join(["1a"] * 23)):
            with self.subTest(tafels=tafels):
                self.assertIn("Ongeldig verzoek.", self.melding({**goed, "tafels": tafels}))
        self.assertEqual(self.tafels(), {})

    def test_alleen_ingelogd(self):
        _, client = maak_client(TestConfig, ingelogd=False)
        antwoord = self.post(self.verzoek("a", ["1a"]), client=client)
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn("/login", antwoord.headers["Location"])
        self.assertEqual(self.tafels(), {})

    def test_csrf_verplicht(self):
        _, client = maak_client(MetCsrfConfig)
        antwoord = self.post(self.verzoek("a", ["1a"]), client=client)
        self.assertEqual(antwoord.status_code, 400)
        self.assertIn("CSRF", antwoord.get_data(as_text=True))
        self.assertEqual(self.tafels(), {})

    def test_404_zonder_plattegrond(self):
        _, client = maak_client(ZonderPlattegrondConfig)
        self.assertEqual(self.post(self.verzoek("a", []), client=client).status_code, 404)

    def test_overzicht_toont_tafel(self):
        self.post(self.verzoek("a", ["3a", "3b"]))
        html = self.client.get("/overzicht?datum=2030-01-01").get_data(as_text=True)
        self.assertIn("3a + 3b", html)
        self.assertIn("Tafel 3a + 3b", html)
        self.assertIn("Nog zonder tafel", html)
        _, client = maak_client(ZonderPlattegrondConfig)
        self.assertNotIn("Nog zonder tafel", client.get("/overzicht").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
