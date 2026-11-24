"""Automatisch uitloggen na een tijd niets doen (tafelvoorstel verbeteren, fase 3)."""
import unittest
from unittest.mock import patch

from tests.hulp import WACHTWOORD, log_in, zet_gebruiker
from tests.test_toegang import ToegangTestBasis

BEGIN = 1_800_000_000  # vaste tijd; de tests schuiven hem per stap op
MINUUT = 60


def op_tijd(seconden):
    """Laat app.toegang.time.time denken dat het BEGIN + seconden is."""
    return patch("app.toegang.time.time", return_value=BEGIN + seconden)


class AutomatischUitloggenTests(ToegangTestBasis):
    def inloggen(self, naam, rol):
        """Logt in via /login op BEGIN, zodat start_sessie ook laatst_actief zet."""
        zet_gebruiker(self.app, naam, rol=rol)
        with op_tijd(0):
            antwoord = self.client.post("/login", data={"gebruikersnaam": naam, "wachtwoord": WACHTWOORD})
        self.assertEqual(antwoord.status_code, 302)

    def bezoek(self, seconden, pad="/overzicht"):
        with op_tijd(seconden):
            return self.client.get(pad, headers={"Accept-Language": "nl"})

    def sessie(self):
        with self.client.session_transaction() as sessie:
            return dict(sessie)

    def sessie_op(self, seconden):
        """De sessie zoals de app hem ziet op BEGIN + seconden: Flask stempelt de cookie met dezelfde klok."""
        with op_tijd(seconden):
            return self.sessie()

    def test_1_beheerder_die_31_minuten_niets_doet_gaat_naar_login(self):
        self.inloggen("chef", "beheerder")
        self.assertEqual(self.bezoek(0).status_code, 200)
        antwoord = self.bezoek(31 * MINUUT)
        self.assertEqual(antwoord.status_code, 302)
        self.assertTrue(antwoord.headers["Location"].endswith("/login"))
        self.assertNotIn("ingelogd", self.sessie_op(31 * MINUUT))

    def test_2_login_toont_de_melding_van_automatisch_uitloggen(self):
        self.inloggen("chef", "beheerder")
        self.assertEqual(self.bezoek(0).status_code, 200)
        self.assertEqual(self.bezoek(31 * MINUUT).status_code, 302)
        html = self.bezoek(31 * MINUUT, "/login").get_data(as_text=True)
        self.assertIn("automatisch uitgelogd", html)

    def test_3_beheerder_die_om_de_20_minuten_iets_doet_blijft_ingelogd(self):
        self.inloggen("chef", "beheerder")
        for minuten in (0, 20, 40):
            self.assertEqual(self.bezoek(minuten * MINUUT).status_code, 200, minuten)

    def test_4_medewerker_blijft_na_31_minuten_niets_doen_ingelogd(self):
        self.inloggen("anna", "medewerker")
        self.assertEqual(self.bezoek(0).status_code, 200)
        self.assertEqual(self.bezoek(31 * MINUUT).status_code, 200)

    def test_5_medewerker_is_na_12_uur_en_1_minuut_niets_doen_uitgelogd(self):
        self.inloggen("anna", "medewerker")
        self.assertEqual(self.bezoek(0).status_code, 200)
        self.assertEqual(self.bezoek(12 * 60 * MINUUT + MINUUT).status_code, 302)

    def test_6_sessie_zonder_laatst_actief_blijft_ingelogd_en_krijgt_een_tijd(self):
        # Net als de bestaande tests: een sessie met gebruiker en stempel, maar zonder laatst_actief.
        # De klok staat stil, want Flask stempelt de sessiecookie met dezelfde tijd.
        with op_tijd(0):
            log_in(self.app, self.client, naam="chef", rol="beheerder")
            self.assertNotIn("laatst_actief", self.sessie())
            self.assertEqual(self.client.get("/overzicht").status_code, 200)
            self.assertEqual(self.sessie()["laatst_actief"], BEGIN)

    def test_7_json_route_geeft_401_na_een_verlopen_sessie(self):
        self.inloggen("chef", "beheerder")
        self.assertEqual(self.bezoek(0).status_code, 200)
        with op_tijd(31 * MINUUT):
            antwoord = self.client.get("/reservering/ruimte", query_string={
                "datum": "2030-01-01", "tijd": "18:00", "aantal": "2"})
        self.assertEqual(antwoord.status_code, 401)
        self.assertEqual(antwoord.get_json()["status"], "fout")
        self.assertNotIn("ingelogd", self.sessie_op(31 * MINUUT))


if __name__ == "__main__":
    unittest.main()
