"""
Fase 6: de online vol-check op tafelniveau. Past een groep qua plekken nog, maar is er op dat
tijdstip geen passende tafel (of combinatie) vrij, dan weigert het systeem en kan de gast bellen.
Het personeel ziet alleen een waarschuwing en mag toch opslaan.
"""
import unittest
from datetime import date, timedelta
from unittest import mock

from sqlalchemy import insert

from app import create_app
from app.config import Config
from app.database import get_db, haal_reservering_op, haal_reserveringen_op, init_db, reserveringen, tafeltoewijzingen
from app.routes import api as api_module
from app.schemas import AIReserveringExtractieSchema
from app.security import reset_rate_limits
from tests.hulp import log_in


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    ADMIN_INITIAL_PASSWORD = "test-admin-pw"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    CSRF_ENABLED = False
    RESTAURANT_CONFIG = "tests/restaurant_vast.toml"  # 69 gasten, 90 minuten, plattegrond met tafelvoorstel


class ZonderPlattegrondConfig(TestConfig):
    RESTAURANT_CONFIG = "tests/fixtures/restaurant_test.toml"


def volgende(weekdag):
    """Eerstvolgende datum met deze weekdag (0 = maandag), minstens een week vooruit."""
    dag = date.today() + timedelta(days=7)
    return dag + timedelta(days=(weekdag - dag.weekday()) % 7)


class Basis(unittest.TestCase):
    config = TestConfig

    def setUp(self):
        reset_rate_limits()
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        self.dag = volgende(1).isoformat()  # een dinsdag: open van 12:00 tot 19:30
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():  # de in-memory database wordt gedeeld tussen tests
                conn.execute(tafeltoewijzingen.delete())
                conn.execute(reserveringen.delete())
        patcher = mock.patch("app.routes.web.stuur_bevestigingsmail_async")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.teller = 0

    def reservering(self, rid, tijd="18:00", aantal=2, tafels=(), status="verwacht"):
        """Een reservering in de database, eventueel met al toegewezen tafels."""
        self.teller += 1  # elke gast een eigen nummer, anders is het een dubbele boeking
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=rid, naam=f"Gast {rid}", email=f"{rid}@example.com", telefoon=f"06123400{self.teller:02d}",
                    datum=self.dag, tijd=tijd, aantal=aantal, status=status))
                if tafels:
                    conn.execute(tafeltoewijzingen.insert(),
                                 [{"reservering_id": rid, "tafel": tafel} for tafel in tafels])

    def lees(self, rid):
        with self.app.app_context():
            return haal_reservering_op(get_db(), rid)

    def aantal_rijen(self):
        with self.app.app_context():
            return len(haal_reserveringen_op(get_db(), self.dag))

    def boek(self, tijd="18:00", aantal=6, email="online@example.com", telefoon="0687654321"):
        """Een online reservering, precies zoals het formulier hem verstuurt."""
        return self.client.post("/reservering", json={
            "naam": "Online Gast", "email": email, "telefoon": telefoon,
            "datum": self.dag, "tijd": tijd, "aantal": aantal, "privacy_akkoord": True})

    def wijzig(self, rid, tijd, aantal):
        return self.client.post(f"/wijzigen/{rid}", data={"datum": self.dag, "tijd": tijd, "aantal": str(aantal)})


class VolTafelsTests(Basis):
    def test_online_reserveren_lukt_als_er_een_tafel_vrij_is(self):
        antwoord = self.boek()
        self.assertEqual(antwoord.status_code, 200)
        self.assertEqual(antwoord.get_json()["status"], "succes")
        self.assertEqual(self.aantal_rijen(), 1)

    def test_alle_passende_tafels_bezet_geeft_400(self):
        self.reservering("bezet", aantal=6, tafels=("2",))  # de enige tafel waar zes mensen aan passen
        antwoord = self.boek()
        self.assertEqual(antwoord.status_code, 400)
        self.assertIn("Bel het restaurant", antwoord.get_json()["bericht"])
        self.assertEqual(self.aantal_rijen(), 1)  # niets opgeslagen

    def test_voorstel_van_eerdere_reservering_telt_ook_als_bezet(self):
        self.reservering("eerste", aantal=6)   # krijgt tafel 2 als voorstel
        self.reservering("tweede", aantal=6)   # past daar niet meer bij
        antwoord = self.boek()
        self.assertEqual(antwoord.status_code, 400)
        self.assertIn("Bel het restaurant", antwoord.get_json()["bericht"])
        self.assertEqual(self.aantal_rijen(), 2)

    def test_no_show_maakt_de_tafel_weer_vrij(self):
        self.reservering("niet-gekomen", aantal=6, tafels=("2",), status="no_show")
        self.assertEqual(self.boek().status_code, 200)

    def test_groep_van_zeven_zonder_vrije_combinatie(self):
        self.reservering("combinatie-een", aantal=7, tafels=("1a", "1b"))
        self.reservering("combinatie-twee", aantal=7, tafels=("3a", "3b"))
        antwoord = self.boek(aantal=7)
        self.assertEqual(antwoord.status_code, 400)
        self.assertIn("Bel het restaurant", antwoord.get_json()["bericht"])

    def test_na_de_zitduur_weer_mogelijk(self):
        self.reservering("vroeg", tijd="18:00", aantal=6, tafels=("2",))
        self.assertEqual(self.boek(tijd="18:30").status_code, 400)  # 18:00 + 90 minuten
        self.assertEqual(self.boek(tijd="19:30").status_code, 200)  # de tafel is dan net vrij

    def test_gast_wijzigt_naar_een_volle_tijd(self):
        self.reservering("eigen", tijd="17:00", aantal=6)
        self.reservering("bezet", tijd="19:00", aantal=6, tafels=("2",))
        antwoord = self.wijzig("eigen", tijd="19:00", aantal=6)
        self.assertEqual(antwoord.status_code, 400)
        self.assertIn("Bel het restaurant", antwoord.get_data(as_text=True))
        self.assertEqual((self.lees("eigen")["tijd"], self.lees("eigen")["aantal"]), ("17:00", 6))

    def test_gast_wijzigt_alleen_het_aantal_en_houdt_zijn_eigen_tafelruimte(self):
        self.reservering("eigen", tijd="18:00", aantal=6, tafels=("2",))
        antwoord = self.wijzig("eigen", tijd="18:00", aantal=5)  # de eigen tafel telt niet tegen hem
        self.assertEqual(antwoord.status_code, 200)
        self.assertEqual(self.lees("eigen")["aantal"], 5)

    def test_beschikbaarheid_geeft_bel_in_plaats_van_beschikbaar(self):
        self.reservering("bezet", aantal=6, tafels=("2",))
        data = self.client.get(f"/beschikbaarheid?datum={self.dag}&aantal=6").get_json()
        self.assertTrue(data["open"])
        knoppen = {tijd["tijd"]: tijd for tijd in data["tijden"]}
        self.assertGreaterEqual(knoppen["18:00"]["vrij"], 6)  # plekken genoeg: het gaat om de tafel
        self.assertFalse(knoppen["18:00"]["beschikbaar"])
        self.assertTrue(knoppen["18:00"]["bel"])
        self.assertTrue(knoppen["12:00"]["beschikbaar"])
        self.assertNotIn("bel", knoppen["12:00"])
        self.assertEqual(data["telefoon"], self.app.config["RESTAURANT_TELEFOON"])

    def test_ai_route_geeft_dezelfde_weigering(self):
        self.reservering("bezet", aantal=6, tafels=("2",))
        extractie = AIReserveringExtractieSchema(
            naam="Gast", email="ai@example.com", telefoon="0612345678", datum=self.dag, tijd="18:00", aantal=6)
        with mock.patch.object(api_module, "verwerk_tekst_met_anthropic", return_value=extractie), \
                mock.patch.object(api_module, "stuur_bevestigingsmail_async"):
            antwoord = self.client.post("/api/v1/ai-reservering", headers={"X-API-Key": "test-key"},
                                        json={"klant_tekst": "Tafel voor zes graag"})
        self.assertEqual(antwoord.status_code, 400)
        self.assertIn("Bel het restaurant", antwoord.get_json()["bericht"])

    def test_telefonisch_invoeren_waarschuwt_maar_slaat_toch_op(self):
        log_in(self.app, self.client, naam="anna", rol="medewerker")
        self.reservering("combinatie-een", aantal=7, tafels=("1a", "1b"))
        self.reservering("combinatie-twee", aantal=7, tafels=("3a", "3b"))
        gegevens = {"bron": "telefoon", "naam": "Siti Rahma", "telefoon": "0611111111",
                    "datum": self.dag, "tijd": "18:00", "aantal": "7"}
        antwoord = self.client.post("/reservering/nieuw", data=gegevens)
        self.assertEqual(antwoord.status_code, 200)
        self.assertIn("Er is geen passende tafel vrij op dit tijdstip", antwoord.get_data(as_text=True))
        self.assertIn('name="bevestigd" value="1"', antwoord.get_data(as_text=True))
        self.assertEqual(self.aantal_rijen(), 2)  # nog niets opgeslagen
        self.assertEqual(self.client.post("/reservering/nieuw", data={**gegevens, "bevestigd": "1"}).status_code, 302)
        self.assertEqual(self.aantal_rijen(), 3)


class ZonderPlattegrondTests(Basis):
    """Zonder plattegrond is er geen tafelcontrole: alles blijft zoals het was."""

    config = ZonderPlattegrondConfig

    def test_zonder_plattegrond_verandert_er_niets(self):
        eerste = self.boek(email="een@example.com", aantal=4)
        tweede = self.boek(email="twee@example.com", telefoon="0687654322", aantal=4)
        self.assertEqual((eerste.status_code, tweede.status_code), (200, 200))
        data = self.client.get(f"/beschikbaarheid?datum={self.dag}&aantal=4").get_json()
        self.assertNotIn("telefoon", data)
        self.assertFalse(any("bel" in tijd for tijd in data["tijden"]))


if __name__ == "__main__":
    unittest.main()

