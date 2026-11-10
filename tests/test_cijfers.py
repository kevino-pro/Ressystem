"""Deel 10 fase 2: de pagina Cijfers voor de beheerder."""
import itertools
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from sqlalchemy import insert

from app import cijfers, create_app
from app.database import dagtellingen, get_db, init_db, reserveringen, tafeltoewijzingen
from app.reserveringsregels import ReserveringsRegels, laad_regels
from app.security import reset_rate_limits
from tests.hulp import log_in
from tests.test_toegang import TestConfig

PROJECTMAP = Path(__file__).resolve().parent.parent
NU = datetime(2030, 1, 9, 12, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))  # woensdag
MAANDAG = date(2030, 1, 7)
NUMMERS = itertools.count(1)


def telling(reserveringen=0, gasten=0, no_shows=0):
    return {'reserveringen': reserveringen, 'gasten': gasten, 'no_shows': no_shows}


class RekenTests(unittest.TestCase):
    def test_maandag_van(self):
        self.assertEqual(cijfers.maandag_van(date(2030, 1, 9)), MAANDAG)
        self.assertEqual(cijfers.maandag_van(date(2030, 1, 13)), MAANDAG)
        self.assertEqual(cijfers.maandag_van(MAANDAG), MAANDAG)

    def test_week_met_de_week_ervoor(self):
        tellingen = {
            ("2030-01-08", "online"): telling(2, 5),
            ("2030-01-08", "telefoon"): telling(1, 4, 0),
            ("2030-01-01", "online"): telling(3, 7, 1),
        }
        rijen = cijfers.week(tellingen, MAANDAG)
        self.assertEqual([r['dag'] for r in rijen][:2], [MAANDAG, date(2030, 1, 8)])
        self.assertEqual(len(rijen), 7)
        dinsdag = rijen[1]
        self.assertEqual((dinsdag['reserveringen'], dinsdag['gasten'], dinsdag['vorige']), (3, 9, 7))
        self.assertEqual(rijen[0]['gasten'], 0)

    def test_weektotalen_en_balk(self):
        tellingen = {("2030-01-08", "online"): telling(2, 10), ("2029-12-31", "online"): telling(1, 5)}
        weken = cijfers.weektotalen(tellingen, MAANDAG, aantal=3)
        self.assertEqual([w['maandag'] for w in weken], [date(2029, 12, 24), date(2029, 12, 31), MAANDAG])
        self.assertEqual([(w['gasten'], w['balk']) for w in weken], [(0, 0), (5, 50), (10, 100)])

    def test_verschil_en_procent(self):
        self.assertEqual(cijfers.verschil(110, 100), 10)
        self.assertEqual(cijfers.verschil(75, 100), -25)
        self.assertIsNone(cijfers.verschil(10, 0))
        self.assertEqual(cijfers.procent(1, 3), 33)
        self.assertEqual(cijfers.procent(0, 0), 0)

    def test_no_shows_en_bronnen(self):
        tellingen = {
            ("2030-01-01", "online"): telling(6, 12, 1),
            ("2030-01-02", "telefoon"): telling(3, 9, 1),
            ("2030-01-02", "onbekend"): telling(1, 2, 0),
        }
        self.assertEqual(cijfers.no_shows(tellingen), {'reserveringen': 10, 'no_shows': 2, 'procent': 20})
        self.assertEqual([(b['bron'], b['reserveringen'], b['procent']) for b in cijfers.per_bron(tellingen)], [
            ("online", 6, 60), ("ai", 0, 0), ("telefoon", 3, 30), ("binnenloper", 0, 0), ("onbekend", 1, 10)])

    def test_drukste_tijden_per_half_uur(self):
        regels = laad_regels(PROJECTMAP / "restaurants" / "wpl.toml")  # zitduur 1 uur, open di-zo 12:00-20:00
        bezoeken = [("2030-01-08", "18:00", 4), ("2030-01-08", "18:30", 2)]
        rijen = cijfers.drukste_tijden(regels, bezoeken, MAANDAG, date(2030, 1, 8))  # maandag dicht
        tijden = {r['tijd']: r['gasten'] for r in rijen}
        self.assertEqual(rijen[0]['tijd'], "12:00")
        self.assertEqual(rijen[-1]['tijd'], "20:30")  # laatste begintijd 20:00 + 1 uur aan tafel
        self.assertEqual((tijden["17:30"], tijden["18:00"], tijden["18:30"], tijden["19:00"], tijden["19:30"]),
                         (0, 4, 6, 2, 0))
        self.assertEqual(next(r for r in rijen if r['tijd'] == "18:30")['balk'], 100)

    def test_drukste_tijden_gemiddeld_over_open_dagen(self):
        regels = laad_regels(PROJECTMAP / "restaurants" / "wpl.toml")
        rijen = cijfers.drukste_tijden(regels, [("2030-01-08", "19:00", 6)], date(2030, 1, 8), date(2030, 1, 9))
        self.assertEqual(next(r for r in rijen if r['tijd'] == "19:00")['gasten'], 3.0)
        self.assertEqual(cijfers.drukste_tijden(regels, [], MAANDAG, MAANDAG), [])


class Basis(unittest.TestCase):
    rol = "beheerder"

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
                for tabel in (tafeltoewijzingen, reserveringen, dagtellingen):
                    conn.execute(tabel.delete())
        self.client = self.app.test_client()
        log_in(self.app, self.client, naam="eigenaar", rol=self.rol)

    def voeg_toe(self, datum, tijd="18:00", aantal=2, bron="online", status="verwacht"):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=f"c{next(NUMMERS)}", naam="Siti Rahma", email="siti@example.com", telefoon="0612345678",
                    datum=datum, tijd=tijd, aantal=aantal, bron=bron, status=status))

    def pagina(self, **query):
        antwoord = self.client.get("/cijfers", query_string=query)
        self.assertEqual(antwoord.status_code, 200)
        return antwoord.get_data(as_text=True)


class PaginaTests(Basis):
    def test_week_met_totalen(self):
        self.voeg_toe("2030-01-08", aantal=4)
        self.voeg_toe("2030-01-08", aantal=3, status="no_show")
        self.voeg_toe("2030-01-10", aantal=6, bron="telefoon")
        self.voeg_toe("2030-01-01", aantal=5)  # de week ervoor
        html = self.pagina()
        self.assertIn("Week 2", html)
        self.assertIn("7 jan t/m 13 jan", html)
        self.assertIn("<small>Gasten deze week</small><b>10</b>", html)
        self.assertIn("<small>Week ervoor</small><b>5</b>", html)
        self.assertIn("+100%", html)
        self.assertIn('href="/overzicht?datum=2030-01-08"', html)

    def test_geen_namen_of_gegevens_van_gasten(self):
        self.voeg_toe("2030-01-08")
        html = self.pagina()
        for tekst in ("Siti", "siti@example.com", "0612345678"):
            self.assertNotIn(tekst, html)

    def test_oude_dagen_uit_de_dagtellingen(self):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(dagtellingen).values(
                    datum="2029-10-02", bron="online", reserveringen=12, gasten=40, no_shows=1))
        self.voeg_toe("2029-10-02", aantal=3)  # een late reservering die er nog staat: opgeteld
        html = self.pagina(week="2029-10-03")
        self.assertIn("1 okt t/m 7 okt", html)
        self.assertIn("<small>Gasten deze week</small><b>43</b>", html)

    def test_andere_dag_in_de_week_en_navigatie(self):
        html = self.pagina(week="2030-01-03")
        self.assertIn("Week 1", html)
        self.assertIn("31 dec t/m 6 jan", html)
        self.assertIn('href="/cijfers?week=2029-12-24"', html)
        self.assertIn('href="/cijfers?week=2030-01-07"', html)

    def test_ongeldige_week(self):
        self.assertEqual(self.client.get("/cijfers", query_string={"week": "gisteren"}).status_code, 400)

    def test_laatste_vier_weken(self):
        self.voeg_toe("2030-01-08", tijd="19:00", aantal=6)
        self.voeg_toe("2030-01-07", tijd="19:00", aantal=2, status="no_show", bron="telefoon")
        self.voeg_toe("2030-01-09", tijd="19:00", aantal=8)  # vandaag: telt nog niet mee
        html = self.pagina()
        self.assertIn("12 dec t/m 8 jan", html)
        self.assertIn("1 van 2 reserveringen", html)
        self.assertIn("<b>50%</b>", html)
        self.assertIn("Drukste tijden", html)

    def test_in_het_engels(self):
        self.client.get("/taal/en")
        html = self.pagina()
        self.assertIn("Busiest times", html)
        self.assertIn("Guests this week", html)

    def test_link_in_de_navigatie(self):
        self.assertIn('href="/cijfers"', self.client.get("/overzicht").get_data(as_text=True))


class MedewerkerTests(Basis):
    rol = "medewerker"

    def test_geen_toegang(self):
        self.assertEqual(self.client.get("/cijfers").status_code, 403)
        self.assertNotIn('href="/cijfers"', self.client.get("/overzicht").get_data(as_text=True))

    def test_niet_ingelogd(self):
        self.client.post("/logout")
        antwoord = self.client.get("/cijfers")
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn("/login", antwoord.headers["Location"])


if __name__ == "__main__":
    unittest.main()
