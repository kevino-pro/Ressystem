import re
import unittest
from datetime import date, timedelta
from unittest import mock

from sqlalchemy import func, select

from app import create_app
from app.config import Config
from app.database import get_db, init_db, reserveringen
from app.routes import api as api_module
from app.schemas import AIReserveringExtractieSchema
from app.security import reset_rate_limits


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
    ADMIN_INITIAL_PASSWORD = "test-admin-pw"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    RESTAURANT_CONFIG = "tests/fixtures/restaurant_streng.toml"


class RegelsInRoutesTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():
                conn.execute(reserveringen.delete())
        self.client = self.app.test_client()
        html = self.client.get("/login").get_data(as_text=True)
        self.headers = {"X-CSRF-Token": re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)}
        for doel in ("app.routes.web.stuur_bevestigingsmail_async", "app.routes.api.stuur_bevestigingsmail_async"):
            patcher = mock.patch(doel)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _aantal_opgeslagen(self):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                return conn.execute(select(func.count()).select_from(reserveringen)).scalar()

    def _formulier(self, datum, tijd="19:00", aantal=2):
        return self.client.post("/reservering", headers=self.headers, json={
            "naam": "Test Gast", "email": "gast@example.com", "telefoon": "0612345678",
            "datum": datum.isoformat(), "tijd": tijd, "aantal": aantal, "privacy_akkoord": True,
        })

    def test_formulier_geldig(self):
        self.assertEqual(self._formulier(volgende(1)).status_code, 200)
        self.assertEqual(self._aantal_opgeslagen(), 1)

    def test_formulier_weigert_buiten_regels(self):
        gevallen = (
            (volgende(0), "19:00", 2, "maandag gesloten"),
            (volgende(1), "22:00", 2, "17:00-21:00"),
            (volgende(1), "19:05", 2, "per 15 minuten"),
            (volgende(1), "19:00", 7, "maximaal 6"),
            (date.today() - timedelta(days=1), "19:00", 2, "verleden"),
            (date.today() + timedelta(days=120), "19:00", 2, "90 dagen"),
        )
        for datum, tijd, aantal, tekst in gevallen:
            with self.subTest(datum=datum, tijd=tijd, aantal=aantal):
                antwoord = self._formulier(datum, tijd, aantal)
                self.assertEqual(antwoord.status_code, 400)
                self.assertIn(tekst, antwoord.get_json()["bericht"])
        self.assertEqual(self._aantal_opgeslagen(), 0)

    def _ai(self, datum, tijd="19:00"):
        extractie = AIReserveringExtractieSchema(
            naam="Test Gast", email="gast@example.com", telefoon="0612345678",
            datum=datum.isoformat(), tijd=tijd, aantal=2,
        )
        with mock.patch.object(api_module, "verwerk_tekst_met_anthropic", return_value=extractie):
            return self.client.post("/api/v1/ai-reservering", headers={"X-API-Key": "test-key"},
                                    json={"klant_tekst": "Tafel voor twee graag"})

    def test_ai_route_weigert_gesloten_dag(self):
        antwoord = self._ai(volgende(0))
        self.assertEqual(antwoord.status_code, 400)
        self.assertIn("maandag gesloten", antwoord.get_json()["bericht"])
        self.assertIn("geparsed_data", antwoord.get_json())
        self.assertEqual(self._aantal_opgeslagen(), 0)

    def test_ai_route_geldig(self):
        self.assertEqual(self._ai(volgende(1)).status_code, 201)
        self.assertEqual(self._aantal_opgeslagen(), 1)

    def test_formulier_toont_slot_en_maximum(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn('step="900"', html)
        self.assertIn('max="6"', html)


if __name__ == "__main__":
    unittest.main()
