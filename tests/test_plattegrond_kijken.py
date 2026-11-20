"""De plattegrond als kijkpagina (fase 5): kijken wie er zit, geen tafels kiezen."""
import unittest

from sqlalchemy import insert

from app.database import get_db, init_db, reserveringen, tafeltoewijzingen
from app.security import reset_rate_limits
from tests.hulp import log_in
from tests.test_plattegrond_pagina import TestConfig, maak_client

DAG = "2030-01-01"


class PlattegrondKijkenTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app, self.client = maak_client(TestConfig)
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():  # de in-memory database wordt gedeeld tussen tests
                conn.execute(tafeltoewijzingen.delete())
                conn.execute(reserveringen.delete())

    def reservering(self, rid="kijker", tijd="19:00", aantal=2, tafels=()):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=rid, naam="N", email=f"{rid}@example.com", telefoon="0612345678",
                    datum=DAG, tijd=tijd, aantal=aantal))
                if tafels:
                    conn.execute(tafeltoewijzingen.insert(),
                                 [{"reservering_id": rid, "tafel": tafel} for tafel in tafels])

    def test_plattegrond_heeft_geen_toewijspaneel_ook_niet_voor_een_beheerder(self):
        log_in(self.app, self.client, naam="anna", rol="beheerder")
        self.reservering()
        html = self.client.get(f"/plattegrond?datum={DAG}&tijd=19:30").get_data(as_text=True)
        self.assertIn("Nog geen tafel", html)  # de reserveringen staan er nog wel
        self.assertNotIn('id="toewijzen"', html)
        self.assertNotIn("Tafels opslaan", html)

    def test_de_oude_toewijsroute_bestaat_niet_meer(self):
        log_in(self.app, self.client, naam="anna", rol="beheerder")
        self.reservering()
        antwoord = self.client.post("/plattegrond/toewijzen",
                                    json={"datum": DAG, "kenmerk": "x", "tafels": ["1a"]})
        self.assertIn(antwoord.status_code, (404, 405))

    def test_binnenloper_gaat_naar_het_overzicht(self):
        antwoord = self.client.post("/reservering/nieuw", data={
            "bron": "binnenloper", "datum": DAG, "tijd": "19:00", "aantal": "2"})
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn("/overzicht", antwoord.headers["Location"])
        self.assertIn("#r-", antwoord.headers["Location"])
        self.assertNotIn("/plattegrond", antwoord.headers["Location"])
        gevolgd = self.client.post("/reservering/nieuw", data={
            "bron": "binnenloper", "datum": DAG, "tijd": "19:00", "aantal": "3"},
            follow_redirects=True)
        self.assertEqual(gevolgd.status_code, 200)
        self.assertIn("Accepteer het in het overzicht", gevolgd.get_data(as_text=True))

    def test_overzicht_heeft_geen_tafel_kiezen_meer(self):
        log_in(self.app, self.client, naam="anna", rol="beheerder")
        self.reservering()
        html = self.client.get(f"/overzicht?datum={DAG}").get_data(as_text=True)
        self.assertNotIn("Tafel kiezen", html)
        self.assertIn("Wijzigen", html)  # een beheerder regelt de tafels in het overzicht


if __name__ == "__main__":
    unittest.main()
