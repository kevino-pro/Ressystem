"""Tafelvoorstel, fase 4: de tafels van een reservering wijzigen is voor een beheerder."""
import re
import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from sqlalchemy import delete

from app import create_app
from app.database import (
    get_db, haal_toewijzingen_op, metadata, reserveringen, tafeltoewijzingen, verwerk_reservering, wijs_tafels_toe,
)
from app.reserveringsregels import ReserveringsRegels
from app.routes.web import _kenmerk
from app.security import reset_rate_limits
from tests.hulp import log_in
from tests.test_toegang import TestConfig

NU = datetime(2030, 1, 1, 18, 7, tzinfo=ZoneInfo("Europe/Amsterdam"))  # een dinsdag
DAG = "2030-01-01"
ZITDUUR = 60


class TafelWijzigenTests(unittest.TestCase):
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
        self.client = self.app.test_client()
        self.indeling = self.app.config["PLATTEGROND"]
        self.tafels = [tafel.nummer for tafel in self.indeling.tafels]
        self.teller = 0

    def inloggen(self, rol="beheerder"):
        log_in(self.app, self.client, naam="anna", rol=rol)

    def reservering(self, naam="Siti", tijd="18:00", aantal=2):
        """Zet een reservering in de database en geeft het id terug."""
        self.teller += 1  # elke gast een eigen mail en nummer: dezelfde gast twee keer op één tijd mag niet
        with self.app.app_context():
            return verwerk_reservering(get_db(), None, naam, f"gast{self.teller}@example.com",
                                       f"06123456{self.teller:02d}", DAG, tijd, aantal, zitduur_minuten=ZITDUUR)

    def kenmerk(self, reservering_id):
        with self.app.test_request_context():
            return _kenmerk(reservering_id)

    def toewijzingen(self, reservering_id):
        with self.app.app_context():
            return haal_toewijzingen_op(get_db(), DAG).get(reservering_id)

    def overzicht(self):
        return self.client.get(f"/overzicht?datum={DAG}").get_data(as_text=True)

    def plattegrond(self):
        return self.client.get(f"/plattegrond?datum={DAG}&tijd=18:00").get_data(as_text=True)

    def keuzelijst(self, kenmerk):
        """De waarden uit de keuzelijst van één reservering in het overzicht."""
        keuze = re.search(rf'<select id="tafels-{kenmerk}"[^>]*>(.*?)</select>', self.overzicht(), re.S)
        self.assertIsNotNone(keuze, "geen keuzelijst in het overzicht")
        return re.findall(r'<option value="([^"]*)"', keuze.group(1))

    def wijzig(self, kenmerk, **velden):
        return self.client.post("/tafels/wijzigen", data={"datum": DAG, "kenmerk": kenmerk, **velden})

    def test_beheerder_kiest_een_optie_uit_de_lijst(self):
        reservering_id = self.reservering()
        kenmerk = self.kenmerk(reservering_id)
        self.inloggen()
        opties = self.keuzelijst(kenmerk)
        self.assertTrue(opties)
        antwoord = self.wijzig(kenmerk, tafels=opties[0])
        self.assertEqual(antwoord.status_code, 303)
        self.assertTrue(antwoord.headers["Location"].endswith(f"#r-{kenmerk}"))
        self.assertEqual(self.toewijzingen(reservering_id), opties[0].split("+"))
        self.assertIn("is opgeslagen", self.overzicht())

    def test_andere_tafels_wint_van_de_keuzelijst(self):
        reservering_id = self.reservering()
        kenmerk = self.kenmerk(reservering_id)
        self.inloggen()
        opties = self.keuzelijst(kenmerk)
        self.wijzig(kenmerk, tafels=opties[0], andere=f"{self.tafels[0]}+{self.tafels[1]}")
        self.assertEqual(self.toewijzingen(reservering_id), self.tafels[:2])
        self.assertNotEqual(self.tafels[:2], opties[0].split("+"))  # het veld won echt van de keuzelijst

    def test_komma_en_spatie_als_scheiding(self):
        reservering_id = self.reservering()
        kenmerk = self.kenmerk(reservering_id)
        self.inloggen()
        eerste, tweede = self.tafels[:2]
        for andere in (f"{eerste}, {tweede}", f"{eerste} {tweede}"):
            with self.subTest(andere=andere):
                self.wijzig(kenmerk, andere=andere)
                self.assertEqual(self.toewijzingen(reservering_id), [eerste, tweede])

    def test_losmaken_maakt_de_reservering_los(self):
        reservering_id = self.reservering()
        with self.app.app_context():
            wijs_tafels_toe(get_db(), reservering_id, [self.tafels[0]], self.indeling, ZITDUUR)
        kenmerk = self.kenmerk(reservering_id)
        self.inloggen()
        self.assertEqual(self.toewijzingen(reservering_id), [self.tafels[0]])
        # Een lege keuze zonder Losmaken is geen opdracht om los te maken: de tafels blijven staan.
        self.wijzig(kenmerk, tafels="", andere="")
        self.assertEqual(self.toewijzingen(reservering_id), [self.tafels[0]])
        self.assertIn("Ongeldig verzoek.", self.overzicht())
        self.wijzig(kenmerk, tafels=self.tafels[0], losmaken="1")
        self.assertIsNone(self.toewijzingen(reservering_id))
        self.assertIn("losgemaakt", self.overzicht())

    def test_onbekende_tafel_wordt_geweigerd(self):
        reservering_id = self.reservering()
        kenmerk = self.kenmerk(reservering_id)
        self.inloggen()
        self.wijzig(kenmerk, andere="999")
        self.assertIsNone(self.toewijzingen(reservering_id))
        self.assertIn("Onbekende tafel: 999.", self.overzicht())

    def test_bezette_tafel_wordt_geweigerd(self):
        bezet = self.reservering(naam="A", tijd="18:00")
        reservering_id = self.reservering(naam="B", tijd="18:15")
        with self.app.app_context():
            wijs_tafels_toe(get_db(), bezet, [self.tafels[0]], self.indeling, ZITDUUR)
        kenmerk = self.kenmerk(reservering_id)
        self.inloggen()
        self.wijzig(kenmerk, andere=self.tafels[0])
        self.assertIsNone(self.toewijzingen(reservering_id))
        self.assertEqual(self.toewijzingen(bezet), [self.tafels[0]])
        self.assertIn(f"Tafel {self.tafels[0]} is al toegewezen", self.overzicht())

    def test_te_weinig_stoelen_geeft_een_waarschuwing(self):
        reservering_id = self.reservering(aantal=6)
        kenmerk = self.kenmerk(reservering_id)
        self.inloggen()
        klein = next(tafel for tafel in self.indeling.tafels if tafel.stoelen == 2)
        self.wijzig(kenmerk, andere=klein.nummer)
        self.assertEqual(self.toewijzingen(reservering_id), [klein.nummer])
        self.assertIn(f"Let op: {klein.stoelen} stoelen voor 6 gasten.", self.overzicht())

    def test_medewerker_mag_niet_wijzigen(self):
        reservering_id = self.reservering()
        kenmerk = self.kenmerk(reservering_id)
        self.inloggen(rol="medewerker")
        antwoord = self.wijzig(kenmerk, andere=self.tafels[0])
        self.assertEqual(antwoord.status_code, 403)
        self.assertIn("Geen toegang.", antwoord.get_data(as_text=True))
        self.assertIsNone(self.toewijzingen(reservering_id))

    def test_alleen_de_beheerder_ziet_wijzigen(self):
        self.reservering()  # nog zonder tafel: dan staat er een voorstel of "Geen tafel vrij"
        self.inloggen(rol="medewerker")
        medewerker = self.overzicht()
        self.assertNotIn("Wijzigen", medewerker)
        self.assertNotIn("Tafel kiezen", medewerker)  # een medewerker kiest zelf geen tafels
        self.assertNotIn("Kies een reservering", self.plattegrond())  # de plattegrond is een kijkpagina
        self.inloggen()
        beheerder = self.overzicht()
        self.assertIn("Wijzigen", beheerder)
        self.assertIn('name="andere"', beheerder)
        self.assertNotIn("Tafel kiezen", beheerder)  # kiezen gebeurt in het overzicht, niet op de plattegrond
        self.assertNotIn("Kies een reservering", self.plattegrond())

    def test_keuzelijst_laat_tafels_van_een_andere_reservering_weg(self):
        eerste = self.reservering(naam="A")
        tweede = self.reservering(naam="B")
        with self.app.app_context():
            wijs_tafels_toe(get_db(), eerste, [self.tafels[0]], self.indeling, ZITDUUR)
        self.inloggen()
        opties = self.keuzelijst(self.kenmerk(tweede))
        self.assertTrue(opties)
        self.assertNotIn(self.tafels[0], [nummer for optie in opties for nummer in optie.split("+")])


if __name__ == "__main__":
    unittest.main()
