import unittest

from app import create_app
from app.config import Config
from app.security import reset_rate_limits

DUMMY_KEY = "dummy-test-key"


class _TestConfig(Config):
    TESTING = True
    SECRET_KEY = "dummy-secret"
    API_KEY = DUMMY_KEY
    WEBHOOK_API_KEY = DUMMY_KEY
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0


class WebhookAuthTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.client = create_app(_TestConfig).test_client()

    def test_missing_header_returns_401(self):
        response = self.client.post("/api/v1/ai-reservering", json={"klant_tekst": "Tafel voor twee"})
        self.assertEqual(response.status_code, 401)

    def test_wrong_key_returns_401(self):
        response = self.client.post(
            "/api/v1/ai-reservering",
            json={"klant_tekst": "Tafel voor twee"},
            headers={"X-API-Key": "fout-é"},
        )
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
