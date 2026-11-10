"""Mijn account: eigen wachtwoord wijzigen (deel 3, fase 3)."""
import re
import unittest

from werkzeug.security import check_password_hash

from tests.hulp import WACHTWOORD, log_in
from tests.test_accounts import NIEUW_WACHTWOORD
from tests.test_toegang import ToegangTestBasis


class EigenAccountTests(ToegangTestBasis):
    def setUp(self):
        super().setUp()
        log_in(self.app, self.client, naam="anna", rol="medewerker")

    def wijzig(self, huidig=WACHTWOORD, nieuw=NIEUW_WACHTWOORD, herhaal=None, client=None):
        return (client or self.client).post("/account/wachtwoord", data={
            "huidig": huidig, "nieuw": nieuw, "herhaal": nieuw if herhaal is None else herhaal})

    def pagina(self):
        return self.client.get("/account").get_data(as_text=True)

    def inloggen(self, wachtwoord):
        client = self.app.test_client()
        return client.post("/login", data={"gebruikersnaam": "anna", "wachtwoord": wachtwoord}).status_code

    def test_niet_ingelogd_naar_login(self):
        client = self.app.test_client()
        self.assertEqual(client.get("/account").status_code, 302)
        self.assertEqual(self.wijzig(client=client).status_code, 302)

    def test_pagina_toont_naam_en_rol_voor_medewerker(self):
        html = self.pagina()
        self.assertIn("<b>anna</b>", html)
        self.assertIn("<b>Medewerker</b>", html)
        self.assertIn('href="/account"', html)  # de naam staat in het menu

    def test_wijzigen_lukt_en_je_blijft_ingelogd(self):
        antwoord = self.wijzig()
        self.assertEqual(antwoord.status_code, 302)
        self.assertTrue(check_password_hash(self.rij("anna")["wachtwoord_hash"], NIEUW_WACHTWOORD))
        self.assertIn("Je wachtwoord is gewijzigd", self.pagina())
        self.assertEqual(self.client.get("/overzicht").status_code, 200)  # eigen sessie blijft geldig
        self.assertEqual(self.inloggen(NIEUW_WACHTWOORD), 302)
        self.assertEqual(self.inloggen(WACHTWOORD), 200)

    def test_ander_apparaat_wordt_uitgelogd(self):
        telefoon = self.app.test_client()
        telefoon.post("/login", data={"gebruikersnaam": "anna", "wachtwoord": WACHTWOORD})
        self.assertEqual(telefoon.get("/overzicht").status_code, 200)
        self.wijzig()
        self.assertEqual(telefoon.get("/overzicht").status_code, 302)

    def test_fout_huidig_wachtwoord(self):
        hash_voor = self.rij("anna")["wachtwoord_hash"]
        self.wijzig(huidig="verkeerd-wachtwoord")
        self.assertEqual(self.rij("anna")["wachtwoord_hash"], hash_voor)
        self.assertIn("huidige wachtwoord klopt niet", self.pagina())

    def test_ongeldige_nieuwe_wachtwoorden(self):
        hash_voor = self.rij("anna")["wachtwoord_hash"]
        gevallen = [
            (dict(nieuw="kort"), "minstens 12 tekens"),
            (dict(nieuw="x" * 129), "hoogstens 128 tekens"),
            (dict(nieuw=NIEUW_WACHTWOORD, herhaal="iets-heel-anders-123"), "niet hetzelfde"),
            (dict(nieuw=WACHTWOORD), "ander wachtwoord"),
        ]
        for data, tekst in gevallen:
            with self.subTest(tekst=tekst):
                self.wijzig(**data)
                self.assertIn(tekst, self.pagina())
                self.assertEqual(self.rij("anna")["wachtwoord_hash"], hash_voor)

    def test_beheerder_ziet_zijn_rol(self):
        client = self.app.test_client()
        log_in(self.app, client, naam="chef", rol="beheerder")
        self.assertIn("<b>Beheerder</b>", client.get("/account").get_data(as_text=True))

    def test_formulier_bevat_csrf_token(self):
        self.assertTrue(re.search(r'name="csrf_token" value="[^"]+"', self.pagina()))


if __name__ == "__main__":
    unittest.main()
