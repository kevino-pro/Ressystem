"""Talen voor gasten (deel 6, fase 1): EN standaard, NL en ID, keuze via browser of cookie."""
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from app import create_app
from app.database import DubbeleReserveringFout, get_db, init_db, reserveringen, verwerk_reservering
from app.reserveringsregels import RegelFout, ReserveringsRegels
from app.routes.web import _zitduur_tekst
from app.security import reset_rate_limits
from app.taal import datum_tekst, laad_talen, laad_vertalingen
from tests.test_gastpaginas import TestConfig as ZonderTalenConfig
from tests.test_toegang import TestConfig

NU = datetime(2030, 1, 1, 10, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))  # een dinsdag
ZATERDAG = "2030-01-05"
MAANDAG = "2030-01-07"


def schrijf_toml(inhoud):
    map_ = tempfile.mkdtemp()
    pad = Path(map_) / "restaurant.toml"
    pad.write_text(inhoud, encoding="utf-8")
    return pad


class Basis(unittest.TestCase):
    config = TestConfig

    def setUp(self):
        reset_rate_limits()
        patcher = mock.patch.object(ReserveringsRegels, "nu", lambda self: NU)
        patcher.start()
        self.addCleanup(patcher.stop)
        mail = mock.patch("app.routes.web.stuur_bevestigingsmail_async")
        mail.start()
        self.addCleanup(mail.stop)
        self.app = create_app(self.config)
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():
                conn.execute(reserveringen.delete())
        self.client = self.app.test_client()

    def pagina(self, pad="/", **headers):
        return self.client.get(pad, headers=headers).get_data(as_text=True)


class TaalkeuzeTests(Basis):
    def test_engels_als_niets_past(self):
        html = self.pagina()
        self.assertIn('<html lang="en">', html)
        self.assertIn("Book a table", html)
        self.assertIn("1 hour", html)

    def test_browser_nederlands(self):
        html = self.pagina(**{"Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8"})
        self.assertIn('<html lang="nl">', html)
        self.assertIn("Reserveer een tafel", html)

    def test_browser_indonesisch(self):
        html = self.pagina(**{"Accept-Language": "id-ID,id;q=0.9"})
        self.assertIn('<html lang="id">', html)
        self.assertIn("Pesan meja", html)
        self.assertIn('"vol": "Penuh"', html)  # ook de teksten voor het script

    def test_onbekende_browsertaal_wordt_engels(self):
        self.assertIn("Book a table", self.pagina(**{"Accept-Language": "fr-FR,fr;q=0.9"}))

    def test_cookie_gaat_voor_de_browser(self):
        self.client.set_cookie("taal", "id")
        self.assertIn("Pesan meja", self.pagina(**{"Accept-Language": "nl"}))

    def test_taalkiezer(self):
        html = self.pagina()
        for code in ("en", "nl", "id"):
            self.assertIn(f'href="/taal/{code}?terug=', html)
        self.assertIn('aria-current="true">EN</a>', html)

    def test_kiezen_zet_cookie_en_gaat_terug(self):
        antwoord = self.client.get("/taal/nl?terug=/privacy")
        self.assertEqual(antwoord.status_code, 302)
        self.assertEqual(antwoord.headers["Location"], "/privacy")
        cookie = antwoord.headers["Set-Cookie"]
        self.assertIn("taal=nl", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertIn("Reserveer een tafel", self.pagina())

    def test_terug_alleen_naar_deze_site(self):
        for terug in ("https://kwaad.example", "//kwaad.example", "/\\kwaad.example", "javascript:alert(1)", "",
                      "/\t/kwaad.example", "/\n/kwaad.example", "/\r\n/kwaad.example"):
            antwoord = self.client.get("/taal/nl", query_string={"terug": terug})
            self.assertEqual(antwoord.headers["Location"], "/", terug)

    def test_onbekende_taal_geen_cookie(self):
        antwoord = self.client.get("/taal/fr?terug=/")
        self.assertNotIn("Set-Cookie", antwoord.headers)


class MeldingenTests(Basis):
    def boek(self, **velden):
        data = {"naam": "Siti Rahma", "email": "siti@example.com", "telefoon": "0612345678", "datum": ZATERDAG,
                "tijd": "19:00", "aantal": 2, "privacy_akkoord": True, **velden}
        return self.client.post("/reservering", json=data)

    def test_formulierfout_in_het_indonesisch(self):
        self.client.set_cookie("taal", "id")
        antwoord = self.boek(telefoon="abc")
        self.assertEqual(antwoord.status_code, 422)
        self.assertIn("Masukkan nomor telepon yang valid", antwoord.get_json()["bericht"])

    def test_regelfout_met_weekdag_in_het_engels(self):
        antwoord = self.client.get(f"/beschikbaarheid?datum={MAANDAG}&aantal=2")
        self.assertEqual(antwoord.get_json()["bericht"], "The restaurant is closed on Monday.")

    def test_regelfout_in_het_nederlands(self):
        self.client.set_cookie("taal", "nl")
        antwoord = self.client.get(f"/beschikbaarheid?datum={MAANDAG}&aantal=2")
        self.assertEqual(antwoord.get_json()["bericht"], "Het restaurant is op maandag gesloten.")

    def test_dubbele_reservering_in_het_engels(self):
        self.assertEqual(self.boek().status_code, 200)
        bericht = self.boek().get_json()["bericht"]
        self.assertTrue(bericht.startswith("You already have a booking on 5 January at 19:00."), bericht)

    def test_bevestiging_in_het_indonesisch(self):
        self.boek()
        self.client.set_cookie("taal", "id")
        html = self.pagina("/bevestiging")
        self.assertIn("Meja Anda sudah dipesan, Siti!", html)
        self.assertIn("Sabtu 5 Januari", html)

    def test_agenda_in_het_engels(self):
        self.boek()
        ics = self.client.get("/bevestiging/agenda.ics").get_data(as_text=True)
        self.assertIn("SUMMARY:Table at ", ics)

    def test_annuleren_in_het_engels(self):
        self.boek()
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                rid = conn.execute(reserveringen.select()).mappings().first()["id"]
        html = self.pagina(f"/annuleren/{rid}")
        self.assertIn("Cancel your booking?", html)
        self.assertIn("Saturday 5 January", html)


class ZonderTalenTests(Basis):
    config = ZonderTalenConfig

    def test_alles_nederlands_zonder_kiezer(self):
        html = self.pagina(**{"Accept-Language": "en"})
        self.assertIn('<html lang="nl">', html)
        self.assertIn("Reserveer een tafel", html)
        self.assertNotIn('class="talen"', html)

    def test_kiezen_kan_niet(self):
        self.assertNotIn("Set-Cookie", self.client.get("/taal/en?terug=/").headers)


class OnderdelenTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)

    def test_zitduur_per_taal(self):
        for taal, verwacht in (("en", "1.5 hours"), ("nl", "1,5 uur"), ("id", "1,5 jam")):
            with self.app.test_request_context(headers={"Accept-Language": taal}):
                self.assertEqual(_zitduur_tekst(90), verwacht)
                self.assertEqual(_zitduur_tekst(75), {"en": "75 minutes", "nl": "75 minuten", "id": "75 menit"}[taal])

    def test_datum_per_taal(self):
        dag = date(2026, 11, 7)
        self.assertEqual(datum_tekst(dag, taal="nl"), "zaterdag 7 november")
        self.assertEqual(datum_tekst(dag, taal="en", met_jaar=True), "Saturday 7 November 2026")
        self.assertEqual(datum_tekst(dag, taal="id"), "Sabtu 7 November")

    def test_meldingen_blijven_nederlands_in_bericht(self):
        fout = RegelFout("Het restaurant is op {weekdag} gesloten.", weekdag=0)
        self.assertEqual(fout.bericht, "Het restaurant is op maandag gesloten.")
        self.assertIn("5 januari", DubbeleReserveringFout(ZATERDAG, "19:00").bericht)

    def test_talen_in_het_restaurantbestand(self):
        self.assertEqual(laad_talen(schrijf_toml("[reserveringen]\n")).beschikbaar, ["nl"])
        talen = laad_talen(schrijf_toml('[talen]\nbeschikbaar = ["nl", "en"]\nstandaard = "en"\n'))
        self.assertEqual((talen.beschikbaar, talen.standaard), (["nl", "en"], "en"))
        for fout in ('[talen]\nbeschikbaar = ["nl"]\nstandaard = "en"\n',
                     '[talen]\nbeschikbaar = ["fr"]\nstandaard = "fr"\n',
                     '[talen]\nbeschikbaar = ["nl", "nl"]\n'):
            with self.assertRaises(RuntimeError):
                laad_talen(schrijf_toml(fout))

    def test_vertaling_met_andere_plaatshouder_start_niet(self):
        map_ = Path(tempfile.mkdtemp())
        (map_ / "en.toml").write_text('"Hallo {naam}" = "Hello {name}"\n', encoding="utf-8")
        (map_ / "id.toml").write_text('"Hallo {naam}" = "Halo {naam}"\n', encoding="utf-8")
        with self.assertRaises(RuntimeError):
            laad_vertalingen(map_)


if __name__ == "__main__":
    unittest.main()
