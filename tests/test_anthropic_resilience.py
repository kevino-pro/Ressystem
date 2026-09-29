import logging
import unittest
from unittest.mock import Mock, patch

import anthropic
import httpx
from flask import Flask

from app.routes import api as api_module
from app.services.ai_service import _anthropic_aanroep_met_retry


class AnthropicRetryTests(unittest.TestCase):
    def setUp(self):
        self.request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")

    def _status_error(self, exception_type, status_code):
        response = httpx.Response(status_code, request=self.request)
        return exception_type(
            "test upstream failure",
            response=response,
            body={"message": "test upstream failure"},
        )

    def test_retries_transient_anthropic_errors(self):
        errors = (
            anthropic.RateLimitError,
            anthropic.APITimeoutError,
            anthropic.APIConnectionError,
            anthropic.InternalServerError,
        )
        for exception_type in errors:
            with self.subTest(exception=exception_type.__name__):
                client = Mock()
                if exception_type is anthropic.APITimeoutError:
                    error = anthropic.APITimeoutError(request=self.request)
                elif exception_type is anthropic.APIConnectionError:
                    error = anthropic.APIConnectionError(message="test connection error", request=self.request)
                else:
                    error = self._status_error(
                        exception_type,
                        429 if exception_type is anthropic.RateLimitError else 500,
                    )
                expected = object()
                client.messages.create.side_effect = [error, expected]

                with patch("app.services.ai_service.time.sleep") as sleep:
                    result = _anthropic_aanroep_met_retry(client, model="test")

                self.assertIs(result, expected)
                self.assertEqual(client.messages.create.call_count, 2)
                sleep.assert_called_once_with(1)


class AnthropicRouteErrorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_logging_disable = logging.root.manager.disable
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        logging.disable(cls.previous_logging_disable)

    def setUp(self):
        self.request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, WEBHOOK_API_KEY="test-key")
        self.app.register_blueprint(api_module.api_bp)
        self.client = self.app.test_client()

    def _status_error(self, exception_type, status_code):
        response = httpx.Response(status_code, request=self.request)
        return exception_type(
            "test upstream failure",
            response=response,
            body={"message": "private upstream detail"},
        )

    def _post_with_error(self, error):
        with patch.object(api_module, "verwerk_tekst_met_anthropic", side_effect=error):
            return self.client.post(
                "/api/v1/ai-reservering",
                headers={"X-API-Key": "test-key"},
                json={"klant_tekst": "Test reservering"},
            )

    def test_timeout_and_rate_limit_return_sanitized_503(self):
        errors = (
            anthropic.APITimeoutError(request=self.request),
            self._status_error(anthropic.RateLimitError, 429),
        )
        for error in errors:
            with self.subTest(exception=type(error).__name__):
                response = self._post_with_error(error)
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("private upstream detail", response.get_data(as_text=True))

    def test_anthropic_5xx_returns_sanitized_503(self):
        response = self._post_with_error(self._status_error(anthropic.InternalServerError, 500))
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private upstream detail", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()