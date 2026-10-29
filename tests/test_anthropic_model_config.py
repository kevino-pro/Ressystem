import os
import unittest
from unittest import mock

from app import create_app
from app.config import Config
from app.services import ai_service


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    ANTHROPIC_MODEL = "test-model"


class AnthropicModelConfigTests(unittest.TestCase):
    def test_config_kent_anthropic_model(self):
        self.assertTrue(Config.ANTHROPIC_MODEL)

    def test_ai_service_gebruikt_model_uit_config(self):
        app = create_app(TestConfig)
        nep_client = mock.Mock()
        nep_client.messages.create.return_value = mock.Mock(content=[])
        with app.app_context(), \
                mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "dummy"}), \
                mock.patch.object(ai_service.anthropic, "Anthropic", return_value=nep_client):
            with self.assertRaises(ValueError):  # lege respons -> geen tool_use
                ai_service.verwerk_tekst_met_anthropic("Tafel voor twee morgen om 19:00")
        self.assertEqual(nep_client.messages.create.call_args.kwargs["model"], "test-model")


if __name__ == "__main__":
    unittest.main()
