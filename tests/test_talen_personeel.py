"""Talen voor het personeel (deel 6, fase 3): de taal hoort bij het account."""
import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from sqlalchemy import select, update

from app import create_app
from app.database import (
    get_db, init_db, personeel, reserveringen, tafeltoewijzingen, verwerk_reservering, wijs_tafels_toe,
)
from app.reserveringsregels import ReserveringsRegels
from app.routes.web import _kenmerk
from app.security import reset_rate_limits
from tests.hulp import WACHTWOORD, log_in, zet_gebruiker
from tests.test_gastpaginas import TestConfig as ZonderTalenConfig
from tests.test_toegang import TestConfig

NU = datetime(2030, 1, 1, 18, 7, tzinfo=ZoneInfo("Europe/Amsterdam"))  # een dinsdag
VANDAAG = "2030-01-01"


class Basis(unittest.TestCase):
    config = TestConfig
    rol = "medewerker"

    def setUp(self):
        reset_rate_limits()
        patcher = mock.patch.object(ReserveringsRegels, "nu", lambda self: NU)
        patcher.start()
        self.addCleanup(patcher.stop)
        mail = mock.patch("app.routes.invoeren.stuur_bevestigingsmail_async")
        mail.start()
        self.addCleanup(mail.stop)
        self.app = create_app(self.config)
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():
                conn.execute(tafeltoewijzingen.delete())
                conn.execute(reserveringen.delete())
        self.client = self.app.test_client()
        log_in(self.app, self.client, naam="anna", rol=self.rol)

    def zet_taal(self, taal, naam="anna"):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(update(personeel).where(personeel.c.gebruikersnaam == naam).values(taal=taal))

    def taal_van(self, naam="anna"):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                return conn.execute(select(personeel.c.taal).where(personeel.c.gebruikersnaam == naam)).scalar()

    def pagina(self, pad, **headers):
        return self.client.get(pad, headers=headers).get_data(as_text=True)

    def reservering(self, naam="Siti", tijd="18:00"):
        with self.app.app_context():
            return verwerk_reservering(get_db(), None, naam, "", "0612345678", VANDAAG, tijd, 4, zitduur_minuten=60)


class AccountTaalTests(Basis):
    def test_nieuw_account_is_nederlands(self):
        self.assertEqual(self.taal_van(), "nl")
        html = self.pagina(f"/overzicht?datum={VANDAAG}", **{"Accept-Language": "en"})
        self.assertIn("Reserveringen", html)
        self.assertIn("Dinsdag 1 januari", html)

    def test_kiezen_bewaart_de_taal_bij_het_account(self):
        self.client.get("/taal/id?terug=/overzicht")
        self.assertEqual(self.taal_van(), "id")
        html = self.pagina(f"/overzicht?datum={VANDAAG}")
        self.assertIn("Hari ini", html)
        self.assertIn("Selasa 1 Januari", html)
        self.assertIn('<html lang="id">', html)

    def test_taal_geldt_op_een_ander_apparaat(self):
        self.client.get("/taal/en?terug=/overzicht")
        ander = self.app.test_client()
        ander.post("/login", data={"gebruikersnaam": "anna", "wachtwoord": WACHTWOORD},
                   headers={"Accept-Language": "nl"})
        self.assertIn("Bookings", ander.get(f"/overzicht?datum={VANDAAG}").get_data(as_text=True))

    def test_taalkiezer_in_het_menu(self):
        html = self.pagina("/overzicht")
        self.assertIn('href="/taal/en?terug=/overzicht"', html)
        self.assertIn('aria-current="true">NL</a>', html)

    def test_inlogpagina_volgt_de_browser(self):
        self.client.post("/logout")
        html = self.pagina("/login", **{"Accept-Language": "id"})
        self.assertIn("Masuk", html)
        antwoord = self.client.post("/login", data={"gebruikersnaam": "anna", "wachtwoord": "fout-wachtwoord-1"},
                                    headers={"Accept-Language": "en"})
        self.assertIn("Invalid username or password!", antwoord.get_data(as_text=True))


class EngelsePaginaTests(Basis):
    def setUp(self):
        super().setUp()
        self.zet_taal("en")

    def test_overzicht(self):
        self.reservering()
        html = self.pagina(f"/overzicht?datum={VANDAAG}")
        for tekst in ("Tuesday 1 January", "Busiest moment", "Not yet arrived", "1 booking · 4 guests",
                      '>Arrived</button>', '>No-show</button>', "+ Choose table", "+ Walk-in"):
            self.assertIn(tekst, html)

    def test_status_melding(self):
        rid = self.reservering()
        with self.app.test_request_context():
            kenmerk = _kenmerk(rid)
        self.client.post("/aankomst", data={"datum": VANDAAG, "kenmerk": kenmerk, "status": "gearriveerd"})
        self.assertIn("Siti has arrived.", self.pagina(f"/overzicht?datum={VANDAAG}"))

    def test_plattegrond(self):
        self.reservering()
        html = self.pagina(f"/plattegrond?datum={VANDAAG}&tijd=18:05")
        for tekst in ("Floor plan", "Occupancy at", "No table yet", "Table 1a, 4 seats", '"mislukt": "Saving failed."'):
            self.assertIn(tekst, html)

    def test_tafel_bezet_melding(self):
        eerste = self.reservering(naam="A")
        tweede = self.reservering(naam="B", tijd="18:15")
        indeling = self.app.config["PLATTEGROND"]
        with self.app.app_context():
            wijs_tafels_toe(get_db(), eerste, ["1a"], indeling, 60)
        with self.app.test_request_context():
            kenmerk = _kenmerk(tweede)
        antwoord = self.client.post("/plattegrond/toewijzen",
                                    json={"datum": VANDAAG, "kenmerk": kenmerk, "tafels": ["1a"]})
        self.assertEqual(antwoord.status_code, 409)
        self.assertEqual(antwoord.get_json()["bericht"], "Table 1a is already assigned to a booking at 18:00.")

    def test_invoeren_met_waarschuwing_en_melding(self):
        html = self.client.post("/reservering/nieuw", data={
            "bron": "telefoon", "naam": "Groep", "telefoon": "0612345678", "datum": VANDAAG, "tijd": "18:00",
            "aantal": "75"}).get_data(as_text=True)
        self.assertIn("Around 18:00 there will then be 75 guests at the same time; the maximum is 69.", html)
        self.assertIn(">Save anyway</button>", html)
        antwoord = self.client.post("/reservering/nieuw", data={
            "bron": "telefoon", "naam": "Groep", "telefoon": "0612345678", "datum": VANDAAG, "tijd": "18:00",
            "aantal": "75", "bevestigd": "1"})
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn("Booking for Groep at 18:00 (75 p.) has been saved.", self.pagina(f"/overzicht?datum={VANDAAG}"))

    def test_veldfout(self):
        html = self.client.post("/reservering/nieuw", data={
            "bron": "telefoon", "naam": "", "telefoon": "0612345678", "datum": VANDAAG, "tijd": "18:00",
            "aantal": "0"}).get_data(as_text=True)
        self.assertIn("Check the name, the number of people (1 to 200).", html)

    def test_mijn_account(self):
        html = self.pagina("/account")
        self.assertIn("Change password", html)
        self.client.post("/account/wachtwoord", data={"huidig": WACHTWOORD, "nieuw": "kort", "herhaal": "kort"})
        self.assertIn("The password must have at least 12 characters.", self.pagina("/account"))

    def test_uitgelogd_in_json(self):
        self.client.post("/logout")
        self.client.set_cookie("taal", "en")
        antwoord = self.client.post("/plattegrond/toewijzen", json={})
        self.assertEqual(antwoord.get_json()["bericht"], "You have been logged out. Please log in again.")


class BeheerderTests(Basis):
    rol = "beheerder"

    def test_accounts_in_het_indonesisch(self):
        self.zet_taal("id")
        self.assertIn("Akun baru", self.pagina("/accounts"))
        self.client.post("/accounts/nieuw", data={"gebruikersnaam": "budi", "wachtwoord": "lang-genoeg-123",
                                                  "rol": "medewerker"})
        self.assertIn("Akun budi sudah dibuat.", self.pagina("/accounts"))


class ZonderTalenTests(Basis):
    config = ZonderTalenConfig

    def test_account_taal_die_er_niet_is_wordt_nederlands(self):
        self.zet_taal("en")
        html = self.pagina(f"/overzicht?datum={VANDAAG}")
        self.assertIn("Reserveringen", html)
        self.assertNotIn('class="talen"', html)


if __name__ == "__main__":
    unittest.main()
