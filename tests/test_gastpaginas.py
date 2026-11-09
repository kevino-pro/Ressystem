import re
import unittest
from datetime import date, timedelta
from unittest import mock

from app import create_app
from app.config import Config
from app.database import get_db, init_db, reserveringen, verwerk_reservering
from app.security import reset_rate_limits
from app.weergave import eindtijd, nl_datum, voornaam

KWAADAARDIGE_NAAM = "<script>window.GEHACKT=1</script> Bakker"


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
    RESTAURANT_CONFIG = "tests/restaurant_vast.toml"
    RESTAURANT_NAAM = "Waroeng Test"
    RESTAURANT_TELEFOON = "070 123 4567"


class WeergaveTests(unittest.TestCase):
    def test_nl_datum(self):
        self.assertEqual(nl_datum("2026-11-07"), "zaterdag 7 november")
        self.assertEqual(nl_datum(date(2027, 1, 1), met_jaar=True), "vrijdag 1 januari 2027")

    def test_eindtijd(self):
        self.assertEqual(eindtijd("19:00", 90), "20:30")
        self.assertEqual(eindtijd("23:30", 60), "00:30")

    def test_voornaam(self):
        self.assertEqual(voornaam("Jan de Vries"), "Jan")
        self.assertEqual(voornaam("  "), "")


class GastpaginaTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)
        self.datum = volgende(5).isoformat()  # zaterdag
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():
                conn.execute(reserveringen.delete())
            self.id = verwerk_reservering(conn, 69, "Jan de Vries", "jan@example.com", "0612345678",
                                          self.datum, "19:00", 2, zitduur_minuten=90)
        self.client = self.app.test_client()

    def onthoud(self, reservering_id):
        with self.client.session_transaction() as sessie:
            sessie["laatste_reservering"] = reservering_id

    def test_bevestiging_toont_de_reservering(self):
        self.onthoud(self.id)
        html = self.client.get("/bevestiging").get_data(as_text=True)
        for tekst in ("Je tafel staat klaar, Jan!", "jan@example.com", nl_datum(self.datum).capitalize(),
                      "19:00 – 20:30", "Schoolstraat 35", "/bevestiging/agenda.ics", "/static/css/huisstijl.css"):
            with self.subTest(tekst=tekst):
                self.assertIn(tekst, html)
        self.assertNotIn("de Vries", html)  # geen volledige naam op een openbare pagina

    def test_bevestiging_zonder_reservering(self):
        html = self.client.get("/bevestiging").get_data(as_text=True)
        self.assertIn("Reservering ontvangen", html)
        self.assertNotIn("agenda.ics", html)
        self.onthoud("bestaat-niet")
        self.assertIn("Reservering ontvangen", self.client.get("/bevestiging").get_data(as_text=True))

    def test_naam_wordt_ge_escaped(self):
        with self.app.app_context():
            rid = verwerk_reservering(get_db(), 69, KWAADAARDIGE_NAAM, "b@example.com", "0687654321",
                                      self.datum, "13:00", 2, zitduur_minuten=90)
        self.onthoud(rid)
        html = self.client.get("/bevestiging").get_data(as_text=True)
        self.assertNotIn("<script>window", html)

    def test_agenda(self):
        self.assertEqual(self.client.get("/bevestiging/agenda.ics").status_code, 404)
        self.onthoud(self.id)
        antwoord = self.client.get("/bevestiging/agenda.ics")
        self.assertEqual(antwoord.status_code, 200)
        self.assertEqual(antwoord.mimetype, "text/calendar")
        ics = antwoord.get_data(as_text=True)
        compact = self.datum.replace("-", "")
        self.assertIn(f"DTSTART;TZID=Europe/Amsterdam:{compact}T190000", ics)
        self.assertIn(f"DTEND;TZID=Europe/Amsterdam:{compact}T203000", ics)
        self.assertIn("LOCATION:Schoolstraat 35\\, 2511 AW Den Haag", ics)
        self.assertNotIn("jan@example.com", ics)

    def test_formulier_onthoudt_reservering(self):
        html = self.client.get("/login").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        with mock.patch("app.routes.web.stuur_bevestigingsmail_async"):
            antwoord = self.client.post("/reservering", headers={"X-CSRF-Token": token}, json={
                "naam": "Piet Klaassen", "email": "piet@example.com", "telefoon": "0611111111",
                "datum": volgende(1).isoformat(), "tijd": "18:00", "aantal": 3, "privacy_akkoord": True,
            })
        self.assertEqual(antwoord.status_code, 200, antwoord.get_json())
        with self.client.session_transaction() as sessie:
            self.assertEqual(sessie["laatste_reservering"], antwoord.get_json()["id"])
        self.assertIn("Je tafel staat klaar, Piet!", self.client.get("/bevestiging").get_data(as_text=True))

    def test_annuleren_toont_voornaam_en_datum(self):
        html = self.client.get(f"/annuleren/{self.id}").get_data(as_text=True)
        self.assertIn("Ja, annuleer mijn reservering", html)
        self.assertIn("Nee, ik kom gewoon", html)
        self.assertIn(nl_datum(self.datum).capitalize(), html)
        self.assertIn(">Jan<", html)
        self.assertNotIn("de Vries", html)

    def test_privacy_in_nieuwe_stijl(self):
        html = self.client.get("/privacy").get_data(as_text=True)
        self.assertIn("In het kort", html)
        self.assertIn('class="verwerkers"', html)
        self.assertNotIn("text-slate", html)


if __name__ == "__main__":
    unittest.main()
