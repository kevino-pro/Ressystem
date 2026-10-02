import unittest
from unittest import mock

from sqlalchemy.exc import OperationalError

from app import create_app
from app.config import Config
from app.routes import web as web_module


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    WEBHOOK_API_KEY = "test-key"
    API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0


class NepDriverFout(Exception):
    """Bootst een psycopg2-fout na die een SQLSTATE via `pgcode` meegeeft."""


def bouw_operational_error(melding, pgcode="28P01"):
    driverfout = NepDriverFout(melding)
    if pgcode is not None:
        driverfout.pgcode = pgcode
    return OperationalError("SELECT 1", {}, driverfout)


class HealthDiagnostiekTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def test_health_geeft_503_en_logt_driverfout_met_sqlstate(self):
        fout = bouw_operational_error(
            'connection to server at "ep-voorbeeld-pooler.eu-central-1.aws.neon.tech" (1.2.3.4), '
            'port 5432 failed: FATAL:  password authentication failed for user "neondb_owner"'
        )
        with mock.patch("app.routes.web.get_db", side_effect=fout):
            with self.assertLogs(self.app.logger, level="ERROR") as logboek:
                response = self.client.get("/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json(), {"status": "fout", "bericht": "Database niet bereikbaar"})
        gelogd = "\n".join(logboek.output)
        self.assertIn("NepDriverFout", gelogd)
        self.assertIn("28P01", gelogd)
        self.assertIn("password authentication failed", gelogd)

    def test_gezonde_healthcheck_geeft_200_en_logt_geen_fout(self):
        with mock.patch("app.routes.web.get_db", return_value=mock.MagicMock()):
            with mock.patch.object(self.app.logger, "error") as log_fout:
                response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})
        log_fout.assert_not_called()

    def test_foutdetails_kappen_lange_meerregelige_melding_af(self):
        driver, sqlstate, melding = web_module._db_foutdetails(
            bouw_operational_error("eerste regel\n" + "x" * 500, pgcode="08006")
        )
        self.assertEqual(driver, "NepDriverFout")
        self.assertEqual(sqlstate, "08006")
        self.assertLessEqual(len(melding), 300)
        self.assertNotIn("\n", melding)

    def test_foutdetails_zonder_pgcode_geven_none(self):
        driver, sqlstate, melding = web_module._db_foutdetails(
            OperationalError("SELECT 1", {}, Exception("driver zonder SQLSTATE"))
        )
        self.assertEqual(driver, "Exception")
        self.assertIsNone(sqlstate)
        self.assertTrue(melding)


if __name__ == "__main__":
    unittest.main()
