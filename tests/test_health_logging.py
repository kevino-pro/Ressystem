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


# Onwaarachtige maar volledige drivermelding: host, gebruikersnaam, wachtwoord en een
# connectiestring. Wat hierin staat mag na een healthcheck-fout nooit in het logboek belanden.
GEHEIME_HOST = "ep-voorbeeld-pooler.eu-central-1.aws.neon.tech"
GEHEIME_GEBRUIKER = "neondb_owner"
GEHEIM_WACHTWOORD = "voorbeeldgeheim"
DRIVERMELDING = (
    f'connection to server at "{GEHEIME_HOST}" (1.2.3.4), port 5432 failed: '
    f'FATAL:  password authentication failed for user "{GEHEIME_GEBRUIKER}" '
    f"(url=postgresql://{GEHEIME_GEBRUIKER}:{GEHEIM_WACHTWOORD}@{GEHEIME_HOST}:5432/neondb) "
    "[SQL: SELECT 1]"
)
SENSITIEVE_DELEN = (
    GEHEIME_HOST,
    GEHEIME_GEBRUIKER,
    GEHEIM_WACHTWOORD,
    "password authentication failed",
    "postgresql://",
    "SELECT 1",
)


def bouw_operational_error(melding, pgcode="28P01"):
    driverfout = NepDriverFout(melding)
    if pgcode is not None:
        driverfout.pgcode = pgcode
    return OperationalError("SELECT 1", {}, driverfout)


class HealthDiagnostiekTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def test_health_geeft_503_en_logt_alleen_driverklasse_en_sqlstate(self):
        fout = bouw_operational_error(DRIVERMELDING)
        with mock.patch("app.routes.web.get_db", side_effect=fout):
            with self.assertLogs(self.app.logger, level="ERROR") as logboek:
                response = self.client.get("/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json(), {"status": "fout", "bericht": "Database niet bereikbaar"})
        gelogd = "\n".join(logboek.output)
        self.assertIn("Healthcheck: database niet bereikbaar", gelogd)
        self.assertIn("driver=NepDriverFout", gelogd)
        self.assertIn("sqlstate=28P01", gelogd)

    def test_log_bevat_geen_host_gebruiker_of_wachtwoord(self):
        fout = bouw_operational_error(DRIVERMELDING)
        with mock.patch("app.routes.web.get_db", side_effect=fout):
            with self.assertLogs(self.app.logger, level="ERROR") as logboek:
                self.client.get("/health")

        gelogd = "\n".join(logboek.output)
        for deel in SENSITIEVE_DELEN:
            with self.subTest(deel=deel):
                self.assertNotIn(deel, gelogd)

    def test_gezonde_healthcheck_geeft_200_en_logt_geen_fout(self):
        with mock.patch("app.routes.web.get_db", return_value=mock.MagicMock()):
            with mock.patch.object(self.app.logger, "error") as log_fout:
                response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})
        log_fout.assert_not_called()

    def test_foutdetails_met_pgcode_geven_driverklasse_en_sqlstate(self):
        driver, sqlstate = web_module._db_foutdetails(bouw_operational_error(DRIVERMELDING, pgcode="08006"))
        self.assertEqual(driver, "NepDriverFout")
        self.assertEqual(sqlstate, "08006")

    def test_foutdetails_zonder_pgcode_geven_none(self):
        driver, sqlstate = web_module._db_foutdetails(
            OperationalError("SELECT 1", {}, Exception(DRIVERMELDING))
        )
        self.assertEqual(driver, "Exception")
        self.assertIsNone(sqlstate)

    def test_foutdetails_vallen_terug_op_de_bovenliggende_fout(self):
        driver, sqlstate = web_module._db_foutdetails(NepDriverFout(DRIVERMELDING))
        self.assertEqual(driver, "NepDriverFout")
        self.assertIsNone(sqlstate)

    def test_foutdetails_geven_nooit_de_drivermelding(self):
        uitkomst = web_module._db_foutdetails(bouw_operational_error(DRIVERMELDING))
        self.assertEqual(len(uitkomst), 2)
        for deel in SENSITIEVE_DELEN:
            with self.subTest(deel=deel):
                self.assertNotIn(deel, repr(uitkomst))


if __name__ == "__main__":
    unittest.main()
