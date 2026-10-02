import re
import unittest

from app import create_app
from app.config import Config
from app.database import get_db, init_db, verwerk_reservering
from app.security import constant_time_equals, reset_rate_limits


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    WEBHOOK_API_KEY = "test-key"
    API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    ADMIN_INITIAL_PASSWORD = "test-admin-pw"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0


class SecurityTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def _csrf(self):
        html = self.client.get("/login").get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def test_constant_time_equals_is_fail_closed(self):
        self.assertTrue(constant_time_equals("abc", "abc"))
        self.assertFalse(constant_time_equals("abc", "abd"))
        self.assertFalse(constant_time_equals(None, "abc"))
        self.assertFalse(constant_time_equals("abc", None))
        self.assertFalse(constant_time_equals("", ""))

    def test_api_wrong_key_401_and_locked_out_after_repeats(self):
        codes = [
            self.client.post("/api/v1/ai-reservering", headers={"X-API-Key": "fout"}).status_code
            for _ in range(12)
        ]
        self.assertEqual(codes[:10], [401] * 10)
        self.assertEqual(codes[10:], [429, 429])

    def test_post_without_csrf_is_rejected(self):
        self.assertEqual(self.client.post("/login", data={"gebruikersnaam": "a", "wachtwoord": "b"}).status_code, 400)
        response = self.client.post("/reservering", json={})
        self.assertEqual(response.status_code, 400)
        self.assertIn("CSRF", response.get_json()["bericht"])

    def test_login_with_csrf_token_is_processed(self):
        token = self._csrf()
        response = self.client.post(
            "/login", data={"gebruikersnaam": "x", "wachtwoord": "y", "csrf_token": token}
        )
        self.assertEqual(response.status_code, 200)

    def test_login_rate_limited(self):
        statuses = [self.client.get("/login").status_code for _ in range(12)]
        self.assertEqual(statuses[-1], 429)

    def test_reservering_header_token_passes_csrf(self):
        token = self._csrf()
        response = self.client.post("/reservering", json={}, headers={"X-CSRF-Token": token})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("CSRF", response.get_json()["bericht"])

    def test_new_reservation_ids_are_unguessable(self):
        with self.app.app_context():
            init_db()
            ids = {
                verwerk_reservering(
                    get_db(), 100, naam="N", email="a@b.nl", telefoon="0612345678",
                    datum="2030-01-01", tijd="18:00", aantal=2,
                )
                for _ in range(5)
            }
        self.assertEqual(len(ids), 5)
        self.assertTrue(all(len(i) >= 22 for i in ids))

    def test_cancel_flow_requires_csrf_and_works(self):
        with self.app.app_context():
            init_db()
            rid = verwerk_reservering(
                get_db(), 100, naam="N", email="a@b.nl", telefoon="0612345678",
                datum="2030-01-01", tijd="18:00", aantal=2,
            )
        page = self.client.get(f"/annuleren/{rid}")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(self.client.post(f"/annuleren/{rid}").status_code, 400)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
        self.assertEqual(self.client.post(f"/annuleren/{rid}", data={"csrf_token": token}).status_code, 200)
        self.assertEqual(self.client.get(f"/annuleren/{rid}").status_code, 404)


if __name__ == "__main__":
    unittest.main()
