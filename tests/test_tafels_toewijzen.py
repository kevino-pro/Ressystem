import unittest

from sqlalchemy import insert

from app.database import get_db, haal_toewijzingen_op, init_db, reserveringen, tafeltoewijzingen
from tests.test_plattegrond_pagina import TestConfig, ZonderPlattegrondConfig, maak_client


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

    def post(self, data, client=None, **kwargs):
        return (client or self.client).post("/plattegrond/toewijzen", json=data, **kwargs)

    def tafels(self):
        with self.app.app_context():
            return haal_toewijzingen_op(get_db(), "2030-01-01")

    def test_toewijzen(self):
        antwoord = self.post({"reservering_id": "a", "tafels": ["1a", "1b"]})
        self.assertEqual(antwoord.status_code, 200)
        self.assertIsNone(antwoord.get_json()["waarschuwing"])
        self.assertEqual(self.tafels(), {"a": ["1a", "1b"]})

    def test_waarschuwing_bij_te_weinig_stoelen(self):
        antwoord = self.post({"reservering_id": "a", "tafels": ["1a"]})
        self.assertEqual(antwoord.status_code, 200)
        self.assertEqual(antwoord.get_json()["waarschuwing"], "Let op: 4 stoelen voor 5 gasten.")

    def test_bezette_tafel(self):
        self.post({"reservering_id": "a", "tafels": ["2"]})
        antwoord = self.post({"reservering_id": "b", "tafels": ["2"]})
        self.assertEqual(antwoord.status_code, 409)
        self.assertIn("Tafel 2", antwoord.get_json()["bericht"])

    def test_onbekende_tafel(self):
        self.assertEqual(self.post({"reservering_id": "a", "tafels": ["99"]}).status_code, 400)

    def test_reservering_bestaat_niet(self):
        self.assertEqual(self.post({"reservering_id": "weg", "tafels": ["1a"]}).status_code, 404)

    def test_ongeldige_invoer(self):
        for data in ({}, ["a"], {"reservering_id": "a"}, {"reservering_id": 1, "tafels": []},
                     {"reservering_id": "a", "tafels": "1a"}, {"reservering_id": "a", "tafels": [1]},
                     {"reservering_id": "a", "tafels": ["1a"] * 23}):
            with self.subTest(data=data):
                self.assertEqual(self.post(data).status_code, 400)

    def test_alleen_ingelogd(self):
        _, client = maak_client(TestConfig, ingelogd=False)
        self.assertEqual(self.post({"reservering_id": "a", "tafels": ["1a"]}, client=client).status_code, 401)
        self.assertEqual(self.tafels(), {})

    def test_csrf_verplicht(self):
        _, client = maak_client(MetCsrfConfig)
        antwoord = self.post({"reservering_id": "a", "tafels": ["1a"]}, client=client)
        self.assertEqual(antwoord.status_code, 400)
        self.assertIn("CSRF", antwoord.get_json()["bericht"])
        self.assertEqual(self.tafels(), {})

    def test_404_zonder_plattegrond(self):
        _, client = maak_client(ZonderPlattegrondConfig)
        self.assertEqual(self.post({"reservering_id": "a", "tafels": []}, client=client).status_code, 404)

    def test_overzicht_toont_tafel(self):
        self.post({"reservering_id": "a", "tafels": ["3a", "3b"]})
        html = self.client.get("/overzicht?datum=2030-01-01").get_data(as_text=True)
        self.assertIn("3a + 3b", html)
        self.assertIn(">Tafel</th>", html)
        _, client = maak_client(ZonderPlattegrondConfig)
        self.assertNotIn(">Tafel</th>", client.get("/overzicht").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
