import unittest
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app import create_app
from app.config import Config
from app.database import get_db, init_db, reserveringen, verwerk_reservering
from app.reserveringsregels import ReserveringsRegels
from app.security import reset_rate_limits

OPEN = {"dinsdag": [["12:00", "19:30"]], "zaterdag": [["12:00", "14:30"], ["17:00", "21:00"]]}


def volgende(weekdag):
    """Eerstvolgende datum met deze weekdag (0 = maandag), minstens een week vooruit."""
    dag = date.today() + timedelta(days=7)
    return dag + timedelta(days=(weekdag - dag.weekday()) % 7)


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    RESTAURANT_CONFIG = "tests/restaurant_vast.toml"  # 69 gasten tegelijk, 90 minuten, knoppen per 30 minuten


class KnoptijdenTests(unittest.TestCase):
    def test_per_knop_minuten(self):
        regels = ReserveringsRegels(openingstijden=OPEN, knop_minuten=30)
        tijden = regels.knoptijden_op(volgende(1))
        self.assertEqual(len(tijden), 16)
        self.assertEqual((tijden[0], tijden[-1]), (time(12, 0), time(19, 30)))

    def test_zonder_knop_minuten_per_slot(self):
        regels = ReserveringsRegels(openingstijden=OPEN)
        self.assertEqual(len(regels.knoptijden_op(volgende(1))), 31)

    def test_meerdere_blokken_en_gesloten(self):
        regels = ReserveringsRegels(openingstijden=OPEN, knop_minuten=60)
        self.assertEqual([f"{t:%H:%M}" for t in regels.knoptijden_op(volgende(5))],
                         ["12:00", "13:00", "14:00", "17:00", "18:00", "19:00", "20:00", "21:00"])
        self.assertEqual(regels.knoptijden_op(volgende(0)), [])

    def test_knop_minuten_moet_passen(self):
        for waarde in (7, 25, 10):  # 10 is geen veelvoud van slot_minuten 15
            with self.subTest(waarde=waarde), self.assertRaises(ValueError):
                ReserveringsRegels(openingstijden=OPEN, knop_minuten=waarde)

    def test_diner_vanaf(self):
        self.assertEqual(ReserveringsRegels(openingstijden=OPEN, diner_vanaf="16:00").diner_vanaf, time(16, 0))
        with self.assertRaises(ValueError):
            ReserveringsRegels(openingstijden=OPEN, diner_vanaf="vier uur")


class BeschikbaarheidRouteTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():
                conn.execute(reserveringen.delete())
        self.client = self.app.test_client()
        self.dinsdag = volgende(1)

    def vraag(self, datum, aantal=2):
        return self.client.get(f"/beschikbaarheid?datum={datum}&aantal={aantal}")

    def boek(self, tijd, aantal, naam="Gast"):
        self.teller = getattr(self, "teller", 0) + 1  # elke gast een eigen nummer, anders is het een dubbele boeking
        with self.app.app_context():
            verwerk_reservering(get_db(), 69, naam, f"{naam}@example.com", f"06123456{self.teller:02d}",
                                self.dinsdag.isoformat(), tijd, aantal, zitduur_minuten=90)

    def test_lege_dag(self):
        data = self.vraag(self.dinsdag).get_json()
        self.assertTrue(data["open"])
        self.assertEqual([t["tijd"] for t in data["tijden"]][:3], ["12:00", "12:30", "13:00"])
        self.assertEqual(data["tijden"][-1]["tijd"], "19:30")  # nooit later dan de laatste begintijd
        self.assertTrue(all(t["beschikbaar"] and t["vrij"] == 69 for t in data["tijden"]))
        self.assertEqual(data["diner_vanaf"], "16:00")

    def test_vol_telt_de_zitduur_mee(self):
        for gast in "ABCDEFGH":
            self.boek("18:00", 8, f"Gast {gast}")  # 64 gasten van 18:00 tot 19:30
        tijden = {t["tijd"]: t for t in self.vraag(self.dinsdag, 6).get_json()["tijden"]}
        self.assertEqual(tijden["18:00"]["vrij"], 5)
        self.assertFalse(tijden["18:00"]["beschikbaar"])
        self.assertFalse(tijden["17:00"]["beschikbaar"])  # 17:00-18:30 overlapt met 18:00
        self.assertTrue(tijden["16:30"]["beschikbaar"])    # 16:30-18:00 overlapt niet
        self.assertTrue(tijden["19:30"]["beschikbaar"])    # 18:00-groep is om 19:30 weg
        self.assertTrue(self.vraag(self.dinsdag, 5).get_json()["tijden"][12]["beschikbaar"])  # 18:00 voor 5 past

    def test_gesloten_dag(self):
        data = self.vraag(volgende(0)).get_json()  # maandag
        self.assertFalse(data["open"])
        self.assertEqual(data["tijden"], [])
        self.assertIn("gesloten", data["bericht"])

    def test_te_ver_vooruit_of_verleden(self):
        for dag, tekst in ((date.today() + timedelta(days=120), "90 dagen"),
                           (date.today() - timedelta(days=7), "verleden")):
            with self.subTest(dag=dag):
                data = self.vraag(dag).get_json()
                self.assertFalse(data["open"])
                self.assertIn(tekst, data["bericht"])

    def test_vandaag_alleen_tijden_na_een_uur(self):
        zone = ZoneInfo("Europe/Amsterdam")
        nu = datetime.now(zone)
        for t in self.vraag(nu.date()).get_json()["tijden"]:
            begin = datetime.combine(nu.date(), time.fromisoformat(t["tijd"]), tzinfo=zone)
            self.assertGreaterEqual(begin, nu + timedelta(minutes=59))

    def test_ongeldige_invoer(self):
        for query in ("", "?datum=morgen&aantal=2", f"?datum={self.dinsdag}&aantal=twee",
                      f"?datum={self.dinsdag}&aantal=0", f"?datum={self.dinsdag}&aantal=9"):
            with self.subTest(query=query):
                self.assertEqual(self.client.get("/beschikbaarheid" + query).status_code, 400)
        self.assertIn("contact", self.vraag(self.dinsdag, 9).get_json()["bericht"])

    def test_geen_persoonsgegevens(self):
        self.boek("18:00", 4, "Jansen")
        tekst = self.vraag(self.dinsdag).get_data(as_text=True)
        self.assertNotIn("Jansen", tekst)
        self.assertNotIn("example.com", tekst)


if __name__ == "__main__":
    unittest.main()
