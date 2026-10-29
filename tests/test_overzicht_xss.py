import re
import unittest

from app import create_app
from app.config import Config
from app.database import get_db, metadata, reserveringen, verwerk_reservering
from app.security import reset_rate_limits

KWAADAARDIGE_NAAM = "x'+(window.GEHACKT=1)+'"


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    CSRF_ENABLED = False


class OverzichtXssTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)
        with self.app.app_context():
            conn = get_db()
            metadata.create_all(conn)
            conn.commit()
            with conn.begin():
                conn.execute(reserveringen.delete())
            verwerk_reservering(conn, 10, KWAADAARDIGE_NAAM, "a@example.com", "0612345678",
                                "2030-01-01", "19:00", 2)
        self.client = self.app.test_client()
        with self.client.session_transaction() as sessie:
            sessie["ingelogd"] = True

    def test_naam_staat_niet_in_javascript(self):
        html = self.client.get("/overzicht").get_data(as_text=True)
        handlers = re.findall(r'onsubmit="([^"]*)"', html)
        self.assertTrue(handlers)
        for handler in handlers:
            self.assertEqual(handler, "return confirm(this.dataset.bericht);")
        self.assertNotIn("GEHACKT=1)+'", html)  # de ruwe ' mag nergens onge-escaped staan

    def test_uitloggen_alleen_via_post(self):
        self.assertEqual(self.client.get("/logout").status_code, 405)
        antwoord = self.client.post("/logout")
        self.assertEqual(antwoord.status_code, 302)
        with self.client.session_transaction() as sessie:
            self.assertNotIn("ingelogd", sessie)


if __name__ == "__main__":
    unittest.main()
