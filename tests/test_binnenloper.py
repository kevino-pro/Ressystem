"""Binnenlopers: iemand zonder reservering aan de deur (deel 4, fase 2)."""
import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app import create_app
from app.database import get_db, init_db, reserveringen
from app.reserveringsregels import ReserveringsRegels
from app.security import reset_rate_limits
from tests.hulp import log_in
from tests.test_toegang import TestConfig

NU = datetime(2030, 1, 1, 18, 7, tzinfo=ZoneInfo("Europe/Amsterdam"))  # een dinsdag
VANDAAG = "2030-01-01"


class ZonderPlattegrondConfig(TestConfig):
    RESTAURANT_CONFIG = "restaurants/voorbeeld.toml"


class Basis(unittest.TestCase):
    config = TestConfig

    def setUp(self):
        reset_rate_limits()
        patcher = mock.patch.object(ReserveringsRegels, "nu", lambda self: NU)
        patcher.start()
        self.addCleanup(patcher.stop)
        mail = mock.patch("app.routes.invoeren.stuur_bevestigingsmail_async")
        mail.start()
        self.addCleanup(mail.stop)
        self.app = create_app(self.config)
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():
                conn.execute(reserveringen.delete())
        self.client = self.app.test_client()
        log_in(self.app, self.client, naam="anna", rol="medewerker")

    def binnenloper(self, **velden):
        data = {"bron": "binnenloper", "naam": "", "telefoon": "", "datum": VANDAAG, "tijd": "18:05",
                "aantal": "3", **velden}
        return self.client.post("/reservering/nieuw", data=data)

    def rijen(self):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                return conn.execute(select(reserveringen)).mappings().all()


class BinnenloperTests(Basis):
    def test_formulier_staat_op_nu(self):
        html = self.client.get("/reservering/nieuw?bron=binnenloper").get_data(as_text=True)
        self.assertIn("<h2>Binnenloper</h2>", html)
        self.assertIn('name="tijd" value="18:05"', html)  # 18:07 afgerond op 5 minuten
        self.assertIn(f'name="datum" value="{VANDAAG}"', html)
        self.assertIn('name="bron" value="binnenloper"', html)
        self.assertNotRegex(html, r'id="naam"[^>]*required')
        self.assertNotRegex(html, r'id="telefoon"[^>]*required')

    def test_zonder_naam_en_telefoon_naar_de_plattegrond(self):
        antwoord = self.binnenloper()
        self.assertEqual(antwoord.status_code, 302)
        self.assertEqual(antwoord.headers["Location"], f"/plattegrond?datum={VANDAAG}&tijd=18:05")
        rij = self.rijen()[0]
        self.assertEqual((rij["naam"], rij["telefoon"], rij["email"], rij["bron"], rij["ingevoerd_door"]),
                         ("Binnenloper", "", "", "binnenloper", "anna"))
        html = self.client.get(f"/plattegrond?datum={VANDAAG}&tijd=18:05").get_data(as_text=True)
        self.assertIn("Reservering voor Binnenloper om 18:05 (3 p.) is opgeslagen.", html)
        self.assertIn("· binnenloper", html)

    def test_met_naam(self):
        self.binnenloper(naam="Familie Wijaya")
        self.assertEqual(self.rijen()[0]["naam"], "Familie Wijaya")

    def test_twee_binnenlopers_tegelijk_zijn_geen_dubbele_boeking(self):
        self.assertEqual(self.binnenloper().status_code, 302)
        self.assertEqual(self.binnenloper(aantal="2").status_code, 302)
        self.assertEqual(len(self.rijen()), 2)

    def test_binnenloper_telt_mee_voor_online(self):
        self.binnenloper(aantal="60", tijd="18:00")
        with self.app.app_context():
            from app.database import bezetting_op, piekbezetting
            bezet = piekbezetting(bezetting_op(get_db(), VANDAAG), 18 * 60 + 30, 60)
        self.assertEqual(bezet, 60)

    def test_knoppen_alleen_vandaag(self):
        vandaag = self.client.get(f"/overzicht?datum={VANDAAG}").get_data(as_text=True)
        self.assertIn('href="/reservering/nieuw?bron=binnenloper"', vandaag)
        morgen = self.client.get("/overzicht?datum=2030-01-02").get_data(as_text=True)
        self.assertNotIn('href="/reservering/nieuw?bron=binnenloper"', morgen)
        self.assertIn('href="/reservering/nieuw?bron=binnenloper"',
                      self.client.get(f"/plattegrond?datum={VANDAAG}").get_data(as_text=True))

    def test_telefonisch_label_op_plattegrond(self):
        self.client.post("/reservering/nieuw", data={
            "bron": "telefoon", "naam": "Siti", "telefoon": "0612345678", "datum": VANDAAG, "tijd": "18:30",
            "aantal": "2"})
        html = self.client.get(f"/plattegrond?datum={VANDAAG}&tijd=18:30").get_data(as_text=True)
        self.assertIn("· telefonisch", html)


class ZonderPlattegrondTests(Basis):
    config = ZonderPlattegrondConfig

    def test_terug_naar_het_overzicht(self):
        antwoord = self.binnenloper()
        self.assertEqual(antwoord.status_code, 302)
        self.assertEqual(antwoord.headers["Location"], f"/overzicht?datum={VANDAAG}")


if __name__ == "__main__":
    unittest.main()
