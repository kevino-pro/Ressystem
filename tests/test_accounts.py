"""Pagina Medewerkers: accounts beheren (deel 3, fase 2)."""
import re
import unittest

from sqlalchemy import func, select

from app.database import (
    LaatsteBeheerderFout, get_db, personeel, zet_actief,
)
from tests.hulp import WACHTWOORD, log_in, zet_gebruiker
from tests.test_toegang import TestConfig, ToegangTestBasis

NIEUW_WACHTWOORD = "nieuw-wachtwoord-456"


class MetCsrfConfig(TestConfig):
    CSRF_ENABLED = True


class AccountsTestBasis(ToegangTestBasis):
    def setUp(self):
        super().setUp()
        log_in(self.app, self.client, naam="chef", rol="beheerder")

    def id_van(self, naam):
        return self.rij(naam)["id"]

    def post(self, pad, **data):
        return self.client.post(pad, data=data)

    def pagina(self):
        return self.client.get("/accounts").get_data(as_text=True)

    def tel(self):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                return conn.execute(select(func.count()).select_from(personeel)).scalar()

    def inloggen(self, naam, wachtwoord):
        client = self.app.test_client()
        antwoord = client.post("/login", data={"gebruikersnaam": naam, "wachtwoord": wachtwoord})
        return client, antwoord


class ToegangTests(AccountsTestBasis):
    def test_niet_ingelogd_naar_login(self):
        antwoord = self.app.test_client().get("/accounts")
        self.assertEqual(antwoord.status_code, 302)
        self.assertTrue(antwoord.headers["Location"].endswith("/login"))

    def test_medewerker_krijgt_403_op_alle_routes(self):
        client = self.app.test_client()
        log_in(self.app, client, naam="anna", rol="medewerker")
        anna = self.id_van("anna")
        self.assertEqual(client.get("/accounts").status_code, 403)
        self.assertEqual(client.post("/accounts/nieuw", data={"gebruikersnaam": "bob", "wachtwoord": WACHTWOORD}).status_code, 403)
        self.assertEqual(client.post(f"/accounts/{anna}/actief", data={"actief": "0"}).status_code, 403)
        self.assertEqual(client.post(f"/accounts/{anna}/wachtwoord", data={"wachtwoord": NIEUW_WACHTWOORD}).status_code, 403)
        self.assertIsNone(self.rij("bob"))

    def test_menu_toont_medewerkers_alleen_aan_beheerder(self):
        self.assertIn('href="/accounts"', self.client.get("/overzicht").get_data(as_text=True))
        client = self.app.test_client()
        log_in(self.app, client, naam="anna", rol="medewerker")
        self.assertNotIn('href="/accounts"', client.get("/overzicht").get_data(as_text=True))

    def test_lijst_toont_accounts_en_wie_jij_bent(self):
        zet_gebruiker(self.app, "anna", rol="medewerker", actief=False)
        html = self.pagina()
        self.assertIn("<b>chef</b>", html)
        self.assertIn("<b>anna</b>", html)
        self.assertEqual(html.count('class="label">jij<'), 1)
        self.assertIn("uitgezet", html)
        self.assertNotIn(f'/accounts/{self.id_van("chef")}/actief', html)  # geen knop voor jezelf


class AanmakenTests(AccountsTestBasis):
    def test_nieuw_account_wordt_medewerker_en_kan_inloggen(self):
        antwoord = self.post("/accounts/nieuw", gebruikersnaam="Anna", wachtwoord=WACHTWOORD, rol="medewerker")
        self.assertEqual(antwoord.status_code, 302)
        rij = self.rij("anna")  # hoofdletters worden kleine letters
        self.assertEqual((rij["rol"], rij["actief"]), ("medewerker", True))
        self.assertIn("Account anna is aangemaakt", self.pagina())
        client, antwoord = self.inloggen("anna", WACHTWOORD)
        self.assertEqual(antwoord.status_code, 302)
        self.assertEqual(client.get("/overzicht").status_code, 200)
        self.assertEqual(client.get("/accounts").status_code, 403)

    def test_nieuwe_beheerder(self):
        self.post("/accounts/nieuw", gebruikersnaam="tweede", wachtwoord=WACHTWOORD, rol="beheerder")
        client, _ = self.inloggen("tweede", WACHTWOORD)
        self.assertEqual(client.get("/accounts").status_code, 200)

    def test_ongeldige_invoer_maakt_niets_aan(self):
        voor = self.tel()
        gevallen = [
            dict(gebruikersnaam="ab", wachtwoord=WACHTWOORD, rol="medewerker"),          # te kort
            dict(gebruikersnaam="a b c", wachtwoord=WACHTWOORD, rol="medewerker"),       # spaties
            dict(gebruikersnaam="<script>", wachtwoord=WACHTWOORD, rol="medewerker"),    # tekens
            dict(gebruikersnaam="x" * 31, wachtwoord=WACHTWOORD, rol="medewerker"),      # te lang
            dict(gebruikersnaam="bob", wachtwoord="kort", rol="medewerker"),             # wachtwoord te kort
            dict(gebruikersnaam="bob", wachtwoord="x" * 129, rol="medewerker"),          # wachtwoord te lang
            dict(gebruikersnaam="bob", wachtwoord=WACHTWOORD, rol="eigenaar"),           # onbekende rol
            dict(wachtwoord=WACHTWOORD),                                                 # alles ontbreekt
        ]
        for data in gevallen:
            with self.subTest(data=data):
                self.assertEqual(self.post("/accounts/nieuw", **data).status_code, 302)
        self.assertEqual(self.tel(), voor)
        self.assertIn("melding fout", self.pagina())

    def test_bestaande_naam_ongeacht_hoofdletters(self):
        self.post("/accounts/nieuw", gebruikersnaam="anna", wachtwoord=WACHTWOORD)
        voor = self.tel()
        self.post("/accounts/nieuw", gebruikersnaam="ANNA", wachtwoord=NIEUW_WACHTWOORD)
        self.assertEqual(self.tel(), voor)
        self.assertIn("bestaat al", self.pagina())
        _, antwoord = self.inloggen("anna", NIEUW_WACHTWOORD)  # het wachtwoord is niet overschreven
        self.assertEqual(antwoord.status_code, 200)

    def test_melding_verdwijnt_na_een_keer_tonen(self):
        self.post("/accounts/nieuw", gebruikersnaam="anna", wachtwoord=WACHTWOORD)
        self.assertIn("is aangemaakt", self.pagina())
        self.assertNotIn("is aangemaakt", self.pagina())


class AanEnUitzettenTests(AccountsTestBasis):
    def setUp(self):
        super().setUp()
        self.anna_client = self.app.test_client()
        log_in(self.app, self.anna_client, naam="anna", rol="medewerker")
        self.anna = self.id_van("anna")

    def test_uitzetten_zet_ook_een_lopende_sessie_stil(self):
        self.assertEqual(self.anna_client.get("/overzicht").status_code, 200)
        self.post(f"/accounts/{self.anna}/actief", actief="0")
        self.assertFalse(self.rij("anna")["actief"])
        self.assertEqual(self.anna_client.get("/overzicht").status_code, 302)
        _, antwoord = self.inloggen("anna", WACHTWOORD)
        self.assertEqual(antwoord.status_code, 200)  # blijft op de loginpagina

    def test_weer_aanzetten(self):
        self.post(f"/accounts/{self.anna}/actief", actief="0")
        self.post(f"/accounts/{self.anna}/actief", actief="1")
        self.assertTrue(self.rij("anna")["actief"])
        _, antwoord = self.inloggen("anna", WACHTWOORD)
        self.assertEqual(antwoord.status_code, 302)

    def test_jezelf_niet_uitzetten(self):
        self.post(f"/accounts/{self.id_van('chef')}/actief", actief="0")
        self.assertTrue(self.rij("chef")["actief"])
        self.assertIn("eigen account niet uitzetten", self.pagina())
        self.assertEqual(self.client.get("/accounts").status_code, 200)

    def test_onbekend_account(self):
        antwoord = self.post("/accounts/99999/actief", actief="0")
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn("bestaat niet", self.pagina())

    def test_andere_beheerder_uitzetten_mag(self):
        zet_gebruiker(self.app, "tweede", rol="beheerder")
        self.post(f"/accounts/{self.id_van('tweede')}/actief", actief="0")
        self.assertFalse(self.rij("tweede")["actief"])

    def test_laatste_actieve_beheerder_kan_niet_uit(self):
        with self.app.app_context():
            conn = get_db()
            with self.assertRaises(LaatsteBeheerderFout):
                zet_actief(conn, self.id_van("chef"), False)
        self.assertTrue(self.rij("chef")["actief"])

    def test_medewerker_uitzetten_vraagt_geen_beheerder(self):
        with self.app.app_context():
            self.assertTrue(zet_actief(get_db(), self.anna, False))
            self.assertFalse(zet_actief(get_db(), 99999, False))

    def test_beheerder_uitzetten_mag_als_er_een_andere_actieve_is(self):
        zet_gebruiker(self.app, "tweede", rol="beheerder")
        with self.app.app_context():
            self.assertTrue(zet_actief(get_db(), self.id_van("chef"), False))
            with self.assertRaises(LaatsteBeheerderFout):
                zet_actief(get_db(), self.id_van("tweede"), False)

    def test_uitgezette_beheerder_telt_niet_mee_als_andere(self):
        zet_gebruiker(self.app, "tweede", rol="beheerder", actief=False)
        with self.app.app_context():
            with self.assertRaises(LaatsteBeheerderFout):
                zet_actief(get_db(), self.id_van("chef"), False)


class WachtwoordResetTests(AccountsTestBasis):
    def setUp(self):
        super().setUp()
        self.anna_client = self.app.test_client()
        log_in(self.app, self.anna_client, naam="anna", rol="medewerker")
        self.anna = self.id_van("anna")

    def test_nieuw_wachtwoord_werkt_en_oude_sessie_vervalt(self):
        self.assertEqual(self.anna_client.get("/overzicht").status_code, 200)
        self.post(f"/accounts/{self.anna}/wachtwoord", wachtwoord=NIEUW_WACHTWOORD)
        self.assertEqual(self.anna_client.get("/overzicht").status_code, 302)
        self.assertEqual(self.inloggen("anna", WACHTWOORD)[1].status_code, 200)
        self.assertEqual(self.inloggen("anna", NIEUW_WACHTWOORD)[1].status_code, 302)
        self.assertIn("Nieuw wachtwoord voor anna", self.pagina())

    def test_te_kort_wachtwoord(self):
        hash_voor = self.rij("anna")["wachtwoord_hash"]
        self.post(f"/accounts/{self.anna}/wachtwoord", wachtwoord="kort")
        self.assertEqual(self.rij("anna")["wachtwoord_hash"], hash_voor)
        self.assertIn("minstens 12 tekens", self.pagina())

    def test_eigen_wachtwoord_niet_via_deze_route(self):
        hash_voor = self.rij("chef")["wachtwoord_hash"]
        self.post(f"/accounts/{self.id_van('chef')}/wachtwoord", wachtwoord=NIEUW_WACHTWOORD)
        self.assertEqual(self.rij("chef")["wachtwoord_hash"], hash_voor)
        self.assertEqual(self.client.get("/accounts").status_code, 200)  # sessie is nog geldig

    def test_onbekend_account(self):
        self.post("/accounts/99999/wachtwoord", wachtwoord=NIEUW_WACHTWOORD)
        self.assertIn("bestaat niet", self.pagina())


class CsrfTests(unittest.TestCase):
    def test_post_zonder_token_wordt_geweigerd(self):
        from app import create_app
        from app.security import reset_rate_limits
        reset_rate_limits()
        app = create_app(MetCsrfConfig)
        client = app.test_client()
        log_in(app, client, naam="chef", rol="beheerder")
        antwoord = client.post("/accounts/nieuw", data={"gebruikersnaam": "bob", "wachtwoord": WACHTWOORD})
        self.assertEqual(antwoord.status_code, 400)
        html = client.get("/accounts").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        antwoord = client.post("/accounts/nieuw", data={
            "gebruikersnaam": "bob", "wachtwoord": WACHTWOORD, "csrf_token": token})
        self.assertEqual(antwoord.status_code, 302)
        with app.app_context():
            conn = get_db()
            with conn.begin():
                namen = conn.execute(select(personeel.c.gebruikersnaam)).scalars().all()
        self.assertIn("bob", namen)


if __name__ == "__main__":
    unittest.main()
