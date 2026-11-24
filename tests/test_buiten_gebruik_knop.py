"""
Tafelvoorstel, fase 6: de knop buiten gebruik op de plattegrond. Alleen een beheerder mag een tafel
voor één dag buiten gebruik zetten of weer in gebruik nemen; wie er al staat, houdt zijn tafel.
"""
import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from sqlalchemy import delete

from app import create_app
from app.database import (
    get_db, haal_buiten_gebruik_op, haal_toewijzingen_op, metadata, reserveringen, tafels_buiten_gebruik,
    tafeltoewijzingen, verwerk_reservering, wijs_tafels_toe, zet_buiten_gebruik,
)
from app.reserveringsregels import ReserveringsRegels
from app.security import reset_rate_limits
from tests.hulp import log_in
from tests.test_toegang import TestConfig

NU = datetime(2030, 1, 1, 18, 7, tzinfo=ZoneInfo("Europe/Amsterdam"))  # een dinsdag
DAG = "2030-01-01"
TIJD = "18:00"
ZITDUUR = 60


class BuitenGebruikKnopTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        patcher = mock.patch.object(ReserveringsRegels, "nu", lambda self: NU)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app = create_app(TestConfig)
        with self.app.app_context():
            conn = get_db()
            metadata.create_all(conn)
            conn.commit()
            with conn.begin():
                conn.execute(delete(tafeltoewijzingen))
                conn.execute(delete(reserveringen))
                conn.execute(delete(tafels_buiten_gebruik))
        self.client = self.app.test_client()
        self.indeling = self.app.config["PLATTEGROND"]
        self.tafels = [tafel.nummer for tafel in self.indeling.tafels]
        self.teller = 0

    def tearDown(self):
        # De in-memory database wordt met de andere testbestanden gedeeld: laat niets achter.
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(delete(tafeltoewijzingen))
                conn.execute(delete(reserveringen))
                conn.execute(delete(tafels_buiten_gebruik))

    def inloggen(self, rol="beheerder"):
        log_in(self.app, self.client, naam="anna", rol=rol)

    def reservering(self, naam="Siti", tijd=TIJD, aantal=2):
        """Zet een reservering in de database en geeft het id terug."""
        self.teller += 1  # elke gast een eigen mail en nummer: dezelfde gast twee keer op één tijd mag niet
        with self.app.app_context():
            return verwerk_reservering(get_db(), None, naam, f"gast{self.teller}@example.com",
                                       f"06123456{self.teller:02d}", DAG, tijd, aantal, zitduur_minuten=ZITDUUR)

    def zet_buiten(self, tafel, aan="1", tijd=TIJD):
        """Het formulier van de plattegrond."""
        return self.client.post("/tafels/buiten-gebruik",
                                data={"datum": DAG, "tijd": tijd, "tafel": tafel, "aan": aan})

    def buiten_gebruik(self):
        with self.app.app_context():
            return haal_buiten_gebruik_op(get_db(), DAG)

    def toewijzingen(self, reservering_id):
        with self.app.app_context():
            return haal_toewijzingen_op(get_db(), DAG).get(reservering_id)

    def plattegrond(self):
        return self.client.get(f"/plattegrond?datum={DAG}&tijd={TIJD}").get_data(as_text=True)

    def test_beheerder_zet_een_tafel_buiten_gebruik(self):
        self.inloggen()
        tafel = self.tafels[0]
        antwoord = self.zet_buiten(tafel)
        self.assertEqual(antwoord.status_code, 303)
        self.assertIn(f"datum={DAG}", antwoord.headers["Location"])
        self.assertEqual(self.buiten_gebruik(), frozenset({tafel}))
        self.assertIn(f"Tafel {tafel} is op {DAG} buiten gebruik.", self.plattegrond())

    def test_beheerder_zet_de_tafel_weer_in_gebruik(self):
        tafel = self.tafels[0]
        with self.app.app_context():
            zet_buiten_gebruik(get_db(), DAG, tafel, True, door="anna")
        self.inloggen()
        antwoord = self.zet_buiten(tafel, aan="0")
        self.assertEqual(antwoord.status_code, 303)
        self.assertEqual(self.buiten_gebruik(), frozenset())
        self.assertIn(f"Tafel {tafel} is weer in gebruik.", self.plattegrond())

    def test_medewerker_mag_niets_zetten(self):
        self.inloggen(rol="medewerker")
        antwoord = self.zet_buiten(self.tafels[0])
        self.assertEqual(antwoord.status_code, 403)
        self.assertIn("Geen toegang.", antwoord.get_data(as_text=True))
        self.assertEqual(self.buiten_gebruik(), frozenset())

    def test_onbekende_tafel_geeft_een_fout(self):
        self.inloggen()
        antwoord = self.zet_buiten("999")
        self.assertEqual(antwoord.status_code, 400)
        self.assertIn("Ongeldig verzoek.", antwoord.get_data(as_text=True))
        self.assertEqual(self.buiten_gebruik(), frozenset())

    def test_waarschuwing_als_de_tafel_al_een_reservering_heeft(self):
        tafel = self.tafels[0]
        reservering_id = self.reservering(naam="De Vries", tijd="18:00")
        with self.app.app_context():
            wijs_tafels_toe(get_db(), reservering_id, [tafel], self.indeling, ZITDUUR)
        self.inloggen()
        self.zet_buiten(tafel)
        pagina = self.plattegrond()
        self.assertIn(f"Let op: tafel {tafel} heeft nog reserveringen: 18:00 De Vries. "
                      "Wijzig hun tafels in het overzicht.", pagina)
        self.assertEqual(self.toewijzingen(reservering_id), [tafel])
        self.assertEqual(self.buiten_gebruik(), frozenset({tafel}))

    def test_plattegrond_geeft_de_tafel_de_class(self):
        tafel = self.tafels[0]
        with self.app.app_context():
            zet_buiten_gebruik(get_db(), DAG, tafel, True, door="anna")
        self.inloggen()
        pagina = self.plattegrond()
        self.assertIn(f'class="tafel buiten-gebruik" data-tafel="{tafel}"', pagina)
        self.assertIn("Buiten gebruik", pagina)

    def test_medewerker_ziet_de_lijst_maar_geen_formulier(self):
        tafel = self.tafels[0]
        with self.app.app_context():
            zet_buiten_gebruik(get_db(), DAG, tafel, True, door="anna")
        self.inloggen(rol="medewerker")
        pagina = self.plattegrond()
        self.assertIn("Tafels buiten gebruik op deze dag", pagina)
        self.assertIn(f'<p class="buiten-lijst">{tafel}</p>', pagina)
        self.assertNotIn('action="/tafels/buiten-gebruik"', pagina)
        self.inloggen()  # een beheerder ziet de knoppen wel
        beheerder = self.plattegrond()
        self.assertIn('action="/tafels/buiten-gebruik"', beheerder)
        self.assertIn("Weer in gebruik", beheerder)


if __name__ == "__main__":
    unittest.main()
