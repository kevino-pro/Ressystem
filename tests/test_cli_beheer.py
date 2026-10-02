import unittest
from datetime import date, timedelta

from sqlalchemy import insert, select, func
from werkzeug.security import check_password_hash

from app import create_app
from app.config import Config
from app.database import (
    ProductieVlagVereist, controleer_dialect, get_db, metadata, personeel, reserveringen,
)

DUMMY_WACHTWOORD = "dummy-wachtwoord-123"


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    MIGRATION_DATABASE_URL = "sqlite:///:memory:"
    ADMIN_INITIAL_PASSWORD = "dummy-initial"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    RETENTIE_DAGEN_AVG = 60


def _prompt(wachtwoord):
    return f"{wachtwoord}\n{wachtwoord}\n"


class GuardTests(unittest.TestCase):
    def test_niet_sqlite_zonder_vlag_geweigerd(self):
        with self.assertRaises(ProductieVlagVereist):
            controleer_dialect("postgresql", False)

    def test_niet_sqlite_met_vlag_toegestaan(self):
        controleer_dialect("postgresql", True)

    def test_sqlite_toegestaan(self):
        controleer_dialect("sqlite", False)


class BeheerCliTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.runner = self.app.test_cli_runner()
        with self.app.app_context():
            conn = get_db()
            metadata.create_all(conn)
            conn.commit()
            with conn.begin():
                conn.execute(personeel.delete())
                conn.execute(reserveringen.delete())

    def _tel(self, tabel):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                return conn.execute(select(func.count()).select_from(tabel)).scalar()

    def _voeg_reservering_toe(self, rid, dagen_geleden):
        datum = (date.today() - timedelta(days=dagen_geleden)).isoformat()
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=rid, naam="N", email="a@example.com", telefoon="0612345678",
                    datum=datum, tijd="18:00", aantal=1))

    def test_create_admin_maakt_gebruiker_met_geldige_hash(self):
        result = self.runner.invoke(args=["create-admin"], input=_prompt(DUMMY_WACHTWOORD))
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("aangemaakt", result.output)
        self.assertNotIn(DUMMY_WACHTWOORD, result.output)
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                rij = conn.execute(select(personeel)).mappings().first()
        self.assertEqual(rij["gebruikersnaam"], "admin")
        self.assertTrue(check_password_hash(rij["wachtwoord_hash"], DUMMY_WACHTWOORD))

    def test_create_admin_tweede_keer_weigert_en_overschrijft_niet(self):
        self.runner.invoke(args=["create-admin"], input=_prompt(DUMMY_WACHTWOORD))
        result = self.runner.invoke(args=["create-admin"], input=_prompt("ander-wachtwoord-456"))
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("bestaat al", result.output)
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                hash_ = conn.execute(select(personeel.c.wachtwoord_hash)).scalar()
        self.assertTrue(check_password_hash(hash_, DUMMY_WACHTWOORD))
        self.assertEqual(self._tel(personeel), 1)

    def test_create_admin_kort_wachtwoord_geweigerd(self):
        result = self.runner.invoke(args=["create-admin"], input=_prompt("kort"))
        self.assertNotEqual(result.exit_code, 0)
        self.assertEqual(self._tel(personeel), 0)

    def test_create_admin_eigen_gebruikersnaam(self):
        result = self.runner.invoke(
            args=["create-admin", "--gebruikersnaam", "chef"], input=_prompt(DUMMY_WACHTWOORD))
        self.assertEqual(result.exit_code, 0, result.output)
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                naam = conn.execute(select(personeel.c.gebruikersnaam)).scalar()
        self.assertEqual(naam, "chef")

    def test_guard_blokkeert_niet_sqlite_voor_verbinding(self):
        self.app.config["DATABASE_URL"] = "postgresql://gebruiker:geheim@host.example/db"
        for args in (["create-admin"], ["purge-retention"]):
            result = self.runner.invoke(args=args, input=_prompt(DUMMY_WACHTWOORD))
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("--productie", result.output)
            self.assertNotIn("host.example", result.output)
            self.assertNotIn("geheim", result.output)

    def test_purge_zonder_uitvoeren_wijzigt_niets(self):
        self._voeg_reservering_toe("oud", 100)
        self._voeg_reservering_toe("nieuw", 1)
        result = self.runner.invoke(args=["purge-retention"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("1 reservering", result.output)
        self.assertEqual(self._tel(reserveringen), 2)

    def test_purge_met_uitvoeren_verwijdert_alleen_oude(self):
        self._voeg_reservering_toe("oud", 100)
        self._voeg_reservering_toe("nieuw", 1)
        result = self.runner.invoke(args=["purge-retention", "--uitvoeren"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("1 reservering(en) verwijderd", result.output)
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                ids = [r[0] for r in conn.execute(select(reserveringen.c.id))]
        self.assertEqual(ids, ["nieuw"])


if __name__ == "__main__":
    unittest.main()
