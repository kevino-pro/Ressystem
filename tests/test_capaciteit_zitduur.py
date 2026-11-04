import unittest

from app import create_app
from app.config import Config
from app.database import CapaciteitVolFout, get_db, metadata, piekbezetting, reserveringen, verwerk_reservering

UUR = 60


class PiekbezettingTests(unittest.TestCase):
    def test_lege_dag(self):
        self.assertEqual(piekbezetting([], 19 * UUR, 120), 0)

    def test_overlap_telt_mee(self):
        # 18:00 (4p) zit tot 20:00, dus een nieuwe boeking om 19:00 overlapt.
        self.assertEqual(piekbezetting([(18 * UUR, 4)], 19 * UUR, 120), 4)

    def test_aansluitend_telt_niet_mee(self):
        # 17:00 zit tot 19:00; om 19:00 is die tafel net vrij.
        self.assertEqual(piekbezetting([(17 * UUR, 4)], 19 * UUR, 120), 0)
        # 21:00 begint precies als de nieuwe boeking (19:00-21:00) klaar is.
        self.assertEqual(piekbezetting([(21 * UUR, 4)], 19 * UUR, 120), 0)

    def test_piek_ligt_later_in_het_venster(self):
        # Om 19:00 zit alleen 18:00 (2p); om 20:00 zitten 19:30 (3p) en 20:00 (5p) = 8.
        bestaande = [(18 * UUR, 2), (19 * UUR + 30, 3), (20 * UUR, 5)]
        self.assertEqual(piekbezetting(bestaande, 19 * UUR, 120), 8)

    def test_niet_overlappende_boekingen_tellen_niet_op(self):
        # 17:00 en 19:30 overlappen allebei met 18:30-20:30, maar niet met elkaar.
        bestaande = [(17 * UUR, 6), (19 * UUR + 30, 6)]
        self.assertEqual(piekbezetting(bestaande, 18 * UUR + 30, 120), 6)


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0


class VerwerkReserveringZitduurTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        with self.app.app_context():
            conn = get_db()
            metadata.create_all(conn)
            conn.commit()
            with conn.begin():
                conn.execute(reserveringen.delete())

    def _boek(self, tijd, aantal, maximum=10):
        with self.app.app_context():
            return verwerk_reservering(
                get_db(), maximum, "Gast", "a@example.com", "0612345678",
                "2030-01-01", tijd, aantal, zitduur_minuten=120,
            )

    def test_een_minuut_later_omzeilt_capaciteit_niet_meer(self):
        self._boek("19:00", 10)
        with self.assertRaises(CapaciteitVolFout):
            self._boek("19:15", 1)

    def test_na_de_zitduur_is_er_weer_plek(self):
        self._boek("17:00", 10)
        self._boek("19:00", 10)

    def test_vrije_plekken_in_foutmelding(self):
        self._boek("18:00", 7)
        with self.assertRaises(CapaciteitVolFout) as fout:
            self._boek("19:00", 4)
        self.assertEqual(fout.exception.vrij, 3)


if __name__ == "__main__":
    unittest.main()
