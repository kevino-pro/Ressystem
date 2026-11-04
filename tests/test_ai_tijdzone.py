import os
import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from app import create_app
from app.config import Config
from app.reserveringsregels import ReserveringsRegels
from app.services import ai_service


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0


class AiTijdzoneTests(unittest.TestCase):
    def test_vandaag_is_lokale_datum_van_restaurant(self):
        # 00:30 in Amsterdam op 3 november is nog 2 november in UTC.
        lokaal = datetime(2026, 11, 3, 0, 30, tzinfo=ZoneInfo("Europe/Amsterdam"))
        app = create_app(TestConfig)
        nep_client = mock.Mock()
        nep_client.messages.create.return_value = mock.Mock(content=[])
        with app.app_context(), \
                mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "dummy"}), \
                mock.patch.object(ai_service.anthropic, "Anthropic", return_value=nep_client), \
                mock.patch.object(ReserveringsRegels, "nu", return_value=lokaal):
            with self.assertRaises(ValueError):  # lege respons -> geen tool_use
                ai_service.verwerk_tekst_met_anthropic("Tafel voor twee morgen om 19:00")
        prompt = nep_client.messages.create.call_args.kwargs["system"]
        self.assertIn("Vandaag is: 2026-11-03", prompt)
        self.assertIn("Morgen is exact: 2026-11-04", prompt)
        self.assertIn("Europe/Amsterdam", prompt)


if __name__ == "__main__":
    unittest.main()
