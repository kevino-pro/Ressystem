import re
import unittest
from unittest import mock

from app import create_app
from app.config import Config
from app.database import init_db
from app.security import reset_rate_limits


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    WEBHOOK_API_KEY = "test-key"
    API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    ADMIN_INITIAL_PASSWORD = "test-admin-pw"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0


def payload(email, datum="2030-01-01"):
    return {
        "naam": "Test Gast", "email": email, "telefoon": "0612345678",
        "datum": datum, "tijd": "18:00", "aantal": 1, "privacy_akkoord": True,
    }


class AdresLimietTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)
        with self.app.app_context():
            init_db()
        self.client = self.app.test_client()
        html = self.client.get("/login").get_data(as_text=True)
        self.headers = {"X-CSRF-Token": re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)}
        patcher = mock.patch("app.routes.web.stuur_bevestigingsmail_async")
        self.mail = patcher.start()
        self.addCleanup(patcher.stop)

    def _post(self, email):
        return self.client.post("/reservering", json=payload(email), headers=self.headers)

    def test_vierde_verzoek_zelfde_adres_geeft_429(self):
        for _ in range(3):
            self.assertEqual(self._post("gast@example.com").status_code, 200)
        response = self._post(" Gast@Example.com ".strip())
        self.assertEqual(response.status_code, 429)
        self.assertEqual(self.mail.call_count, 3)

    def test_ander_adres_gaat_door(self):
        for _ in range(3):
            self._post("gast@example.com")
        self.assertEqual(self._post("ander@example.com").status_code, 200)

    def test_ongeldige_payload_telt_niet_mee(self):
        for _ in range(5):
            bad = payload("gast@example.com")
            bad["telefoon"] = "1"
            self.assertEqual(self.client.post("/reservering", json=bad, headers=self.headers).status_code, 422)
        self.assertEqual(self._post("gast@example.com").status_code, 200)


if __name__ == "__main__":
    unittest.main()
