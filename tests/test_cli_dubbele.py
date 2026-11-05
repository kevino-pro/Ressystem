import unittest
from datetime import date, timedelta

from sqlalchemy import func, insert, select

from app import create_app
from app.config import Config
from app.database import get_db, init_db, reserveringen


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    ADMIN_INITIAL_PASSWORD = "test-admin-pw"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0


MORGEN = (date.today() + timedelta(days=1)).isoformat()
GISTEREN = (date.today() - timedelta(days=1)).isoformat()


class DubbeleReserveringenCommandoTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():
                conn.execute(reserveringen.delete())
        self.runner = self.app.test_cli_runner()

    def _voeg_toe(self, rid, naam, email, telefoon, datum=MORGEN, tijd="19:00"):
        # Direct in de tabel, zoals oude data van voor de duplicaatcontrole.
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=rid, naam=naam, email=email, telefoon=telefoon, datum=datum, tijd=tijd, aantal=2))

    def _aantal(self):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                return conn.execute(select(func.count()).select_from(reserveringen)).scalar()

    def test_geen_dubbele(self):
        self._voeg_toe("a", "Jan Jansen", "jan@example.com", "0612345678")
        self._voeg_toe("b", "Piet Pieters", "piet@example.com", "0687654321")
        resultaat = self.runner.invoke(args=["dubbele-reserveringen"])
        self.assertEqual(resultaat.exit_code, 0, resultaat.output)
        self.assertIn("Geen dubbele reserveringen gevonden.", resultaat.output)

    def test_vindt_groep_en_verwijdert_niets(self):
        self._voeg_toe("a", "Jan Jansen", "jan@example.com", "0612345678")
        self._voeg_toe("b", "jan jansen", " JAN@Example.com", "0687654321")
        resultaat = self.runner.invoke(args=["dubbele-reserveringen"])
        self.assertEqual(resultaat.exit_code, 0, resultaat.output)
        self.assertIn(f"{MORGEN} 19:00: 2 reserveringen", resultaat.output)
        self.assertIn("id=a", resultaat.output)
        self.assertIn("id=b", resultaat.output)
        self.assertIn("1 groep(en)", resultaat.output)
        self.assertEqual(self._aantal(), 2)

    def test_alleen_zelfde_naam_is_niet_dubbel(self):
        # Twee verschillende gasten met dezelfde naam: andere e-mail en ander nummer.
        self._voeg_toe("a", "Jan Jansen", "jan@example.com", "0612345678")
        self._voeg_toe("b", "Jan Jansen", "ander@example.com", "0687654321")
        resultaat = self.runner.invoke(args=["dubbele-reserveringen"])
        self.assertEqual(resultaat.exit_code, 0, resultaat.output)
        self.assertIn("Geen dubbele reserveringen gevonden.", resultaat.output)

    def test_toont_geen_volledige_gegevens(self):
        self._voeg_toe("a", "Jan Jansen", "jan@example.com", "0612345678")
        self._voeg_toe("b", "Jan Jansen", "jan@example.com", "0612345678")
        resultaat = self.runner.invoke(args=["dubbele-reserveringen"])
        self.assertNotIn("jan@example.com", resultaat.output)
        self.assertNotIn("0612345678", resultaat.output)
        self.assertNotIn("Jansen", resultaat.output)

    def test_groepeert_via_tussenschakel(self):
        # a en c delen niets, maar allebei delen ze iets met b.
        self._voeg_toe("a", "Jan Jansen", "jan@example.com", "0611111111")
        self._voeg_toe("b", "Iemand", "jan@example.com", "0622222222")
        self._voeg_toe("c", "Nog Iemand", "c@example.com", "0622222222")
        resultaat = self.runner.invoke(args=["dubbele-reserveringen"])
        self.assertIn(f"{MORGEN} 19:00: 3 reserveringen", resultaat.output)

    def test_verleden_en_andere_tijd_tellen_niet(self):
        self._voeg_toe("a", "Jan Jansen", "jan@example.com", "0612345678", datum=GISTEREN)
        self._voeg_toe("b", "Jan Jansen", "jan@example.com", "0612345678", datum=GISTEREN)
        self._voeg_toe("c", "Jan Jansen", "jan@example.com", "0612345678", tijd="19:00")
        self._voeg_toe("d", "Jan Jansen", "jan@example.com", "0612345678", tijd="19:15")
        resultaat = self.runner.invoke(args=["dubbele-reserveringen"])
        self.assertIn("Geen dubbele reserveringen gevonden.", resultaat.output)


if __name__ == "__main__":
    unittest.main()
