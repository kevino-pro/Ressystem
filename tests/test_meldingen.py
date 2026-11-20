"""Meldingen (fase 7): reserveringen zonder tafel voor vandaag en de dagen daarna."""
import unittest
from datetime import datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

from sqlalchemy import insert
from sqlalchemy.exc import OperationalError

from app.database import get_db, haal_toewijzingen_op, init_db, reserveringen, tafeltoewijzingen, wijs_tafels_toe
from app.reserveringsregels import ReserveringsRegels
from app.routes.web import MELDINGEN_DAGEN, _kenmerk
from app.security import reset_rate_limits
from tests.test_plattegrond_pagina import TestConfig, ZonderPlattegrondConfig, maak_client

NU = datetime(2030, 1, 1, 18, 7, tzinfo=ZoneInfo("Europe/Amsterdam"))  # een dinsdag
VANDAAG = "2030-01-01"


def dag_na(aantal):
    return (NU.date() + timedelta(days=aantal)).isoformat()


class MeldingenTests(unittest.TestCase):
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

    def reservering(self, rid, tijd="19:00", datum=VANDAAG, aantal=2, status="verwacht", tafels=()):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=rid, naam=f"Gast {rid}", email=f"{rid}@example.com", telefoon="0612345678",
                    datum=datum, tijd=tijd, aantal=aantal, status=status))
            if tafels:
                wijs_tafels_toe(conn, rid, list(tafels), self.app.config["PLATTEGROND"], 90)

    def meldingen(self, client=None):
        return (client or self.client).get("/meldingen").get_data(as_text=True)

    def tafels(self):
        with self.app.app_context():
            return haal_toewijzingen_op(get_db(), VANDAAG)

    def menu(self, html):
        """Alleen het stuk tussen id="menu" en het einde van het menu."""
        begin = html.index('<div class="menu-lijst" id="menu">')
        return html[begin:html.index("</nav>", html.index("Uitloggen", begin))]

    def test_alleen_na_inloggen(self):
        _, client = maak_client(TestConfig, ingelogd=False)
        antwoord = client.get("/meldingen")
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn("/login", antwoord.headers["Location"])

    def test_404_zonder_plattegrond(self):
        _, client = maak_client(ZonderPlattegrondConfig)
        self.assertEqual(client.get("/meldingen").status_code, 404)

    def test_toont_reservering_zonder_tafel_met_voorstel_en_accepteren(self):
        self.reservering("a")
        html = self.meldingen()
        self.assertIn("Gast a", html)
        self.assertIn("Voorstel:", html)
        self.assertIn("Voorstel: 8", html)  # de kleinste losse tafel die past
        self.assertIn('action="/tafels/accepteren"', html)
        self.assertIn('name="tafels" value="8"', html)
        self.assertIn('name="terug" value="meldingen"', html)
        self.assertIn("Accepteren", html)

    def test_reservering_met_tafel_staat_er_niet_in(self):
        self.reservering("a", tafels=["8"])
        html = self.meldingen()
        self.assertNotIn("Gast a", html)
        self.assertIn("Alle reserveringen hebben een tafel.", html)

    def test_achtste_dag_staat_er_niet_in_zesde_wel(self):
        self.assertEqual(MELDINGEN_DAGEN, 7)
        self.reservering("ver", datum=dag_na(8))
        self.reservering("zes", datum=dag_na(6))
        html = self.meldingen()
        self.assertIn("Gast zes", html)
        self.assertNotIn("Gast ver", html)

    def test_accepteren_met_terug_meldingen_gaat_terug_en_slaat_op(self):
        self.reservering("a")
        with self.app.app_context():
            kenmerk = _kenmerk("a")
        antwoord = self.client.post("/tafels/accepteren", data={
            "datum": VANDAAG, "kenmerk": kenmerk, "tafels": "8", "terug": "meldingen",
        })
        self.assertEqual(antwoord.status_code, 303)
        self.assertTrue(antwoord.headers["Location"].endswith("/meldingen"), antwoord.headers["Location"])
        self.assertEqual(self.tafels(), {"a": ["8"]})

    def test_menu_toont_de_teller_met_het_juiste_aantal(self):
        self.reservering("nu", tijd="19:00")            # vandaag, nog te komen
        self.reservering("geweest", tijd="17:00")       # vandaag, al voorbij: telt niet mee
        self.reservering("morgen", tijd="19:00", datum=dag_na(1))
        self.reservering("tafel", tijd="19:30", tafels=["8"])
        menu = self.menu(self.client.get("/overzicht").get_data(as_text=True))
        self.assertIn('class="teller-melding">2</span>', menu)

    def test_zonder_reserveringen_zonder_tafel_geen_teller(self):
        self.reservering("a", tafels=["8"])
        html = self.meldingen()
        self.assertIn("Alle reserveringen hebben een tafel.", html)
        self.assertNotIn("teller-melding", html)

    def test_foutpagina_werkt_als_de_database_storing_heeft(self):
        """Het opslaan mislukt en ook de teller kan de database niet lezen: de pagina moet blijven werken."""
        fout = OperationalError("SELECT 1", {}, Exception("database onbereikbaar"))
        with mock.patch("app.routes.invoeren.verwerk_reservering", side_effect=fout), \
                mock.patch("app.routes.web.haal_toewijzingen_op", side_effect=fout), \
                mock.patch("app.routes.web.haal_reserveringen_op", side_effect=fout):
            antwoord = self.client.post("/reservering/nieuw", data={
                "bron": "telefoon", "naam": "Piet", "telefoon": "0612345678", "datum": VANDAAG,
                "tijd": "19:00", "aantal": "2",
            })
        self.assertEqual(antwoord.status_code, 503)
        html = antwoord.get_data(as_text=True)
        self.assertIn("Het lukte niet om op te slaan. Probeer het opnieuw.", html)
        self.assertNotIn("teller-melding", html)


if __name__ == "__main__":
    unittest.main()
