"""Mails in de taal van de gast (deel 6, fase 2)."""
import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app import create_app
from app.database import get_db, init_db, reserveringen, verwerk_reservering
from app.reserveringsregels import ReserveringsRegels
from app.security import reset_rate_limits
from app.services.email_service import _bouw_bevestigingsmail
from tests.hulp import log_in
from tests.test_toegang import TestConfig

NU = datetime(2030, 1, 1, 10, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))  # een dinsdag
ZATERDAG = "2030-01-05"


class MailTekstTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.config = {**self.app.config, "APP_BASE_URL": "https://voorbeeld.test", "RESTAURANT_NAAM": "Waroeng"}

    def mail(self, taal):
        with self.app.app_context():
            return _bouw_bevestigingsmail(self.config, "siti@example.com", "Siti", ZATERDAG, "19:00", 4, "abc", taal)

    def test_nederlands(self):
        mail = self.mail("nl")
        self.assertEqual(mail["subject"], "Bevestiging van je reservering - Waroeng")
        self.assertIn("Beste Siti,", mail["tekst"])
        self.assertIn("- Datum: Zaterdag 5 januari 2030", mail["tekst"])
        self.assertIn("- Tijdstip: 19:00", mail["tekst"])
        self.assertIn("https://voorbeeld.test/annuleren/abc", mail["tekst"])

    def test_engels(self):
        mail = self.mail("en")
        self.assertEqual(mail["subject"], "Your booking confirmation - Waroeng")
        self.assertIn("Dear Siti,", mail["tekst"])
        self.assertIn("- Date: Saturday 5 January 2030", mail["tekst"])
        self.assertIn("- Time: 19:00", mail["tekst"])

    def test_indonesisch(self):
        mail = self.mail("id")
        self.assertEqual(mail["subject"], "Konfirmasi reservasi Anda - Waroeng")
        self.assertIn("- Tanggal: Sabtu 5 Januari 2030", mail["tekst"])
        self.assertIn("Tim Waroeng", mail["tekst"])

    def test_zonder_taal_nederlands(self):
        with self.app.app_context():
            mail = _bouw_bevestigingsmail(self.config, "a@example.com", "A", ZATERDAG, "19:00", 2, "x")
        self.assertIn("Beste A,", mail["tekst"])


class Basis(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        patcher = mock.patch.object(ReserveringsRegels, "nu", lambda self: NU)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app = create_app(TestConfig)
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():
                conn.execute(reserveringen.delete())
        self.client = self.app.test_client()

    def opgeslagen_taal(self):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                return conn.execute(select(reserveringen.c.taal)).scalar_one()


class OnlineTests(Basis):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("app.routes.web.stuur_bevestigingsmail_async")
        self.verstuur = patcher.start()
        self.addCleanup(patcher.stop)

    def boek(self):
        return self.client.post("/reservering", json={
            "naam": "Siti Rahma", "email": "siti@example.com", "telefoon": "0612345678", "datum": ZATERDAG,
            "tijd": "19:00", "aantal": 2, "privacy_akkoord": True})

    def test_taal_van_de_pagina_wordt_bewaard(self):
        self.client.set_cookie("taal", "id")
        self.assertEqual(self.boek().status_code, 200)
        self.assertEqual(self.opgeslagen_taal(), "id")
        self.assertEqual(self.verstuur.call_args.kwargs["taal"], "id")

    def test_zonder_keuze_de_standaard(self):
        self.boek()
        self.assertEqual(self.opgeslagen_taal(), "en")
        self.assertEqual(self.verstuur.call_args.kwargs["taal"], "en")

    def test_browser_nederlands(self):
        self.client.post("/reservering", headers={"Accept-Language": "nl"}, json={
            "naam": "Jan", "email": "jan@example.com", "telefoon": "0612345679", "datum": ZATERDAG,
            "tijd": "19:00", "aantal": 2, "privacy_akkoord": True})
        self.assertEqual(self.opgeslagen_taal(), "nl")


class PersoneelTests(Basis):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("app.routes.invoeren.stuur_bevestigingsmail_async")
        self.verstuur = patcher.start()
        self.addCleanup(patcher.stop)
        log_in(self.app, self.client, naam="anna", rol="medewerker")

    def invoeren(self, **velden):
        data = {"bron": "telefoon", "naam": "Siti Rahma", "telefoon": "0612345678", "email": "siti@example.com",
                "datum": ZATERDAG, "tijd": "18:00", "aantal": "4", **velden}
        return self.client.post("/reservering/nieuw", data=data)

    def test_keuzelijst_met_de_talen(self):
        html = self.client.get("/reservering/nieuw", headers={"Accept-Language": "nl"}).get_data(as_text=True)
        self.assertIn('<select id="taal" name="taal">', html)
        self.assertIn('<option value="nl" selected>Nederlands</option>', html)
        self.assertIn(">Bahasa Indonesia</option>", html)

    def test_gekozen_taal_voor_de_mail(self):
        self.assertEqual(self.invoeren(taal="id").status_code, 302)
        self.assertEqual(self.opgeslagen_taal(), "id")
        self.assertEqual(self.verstuur.call_args.kwargs["taal"], "id")

    def test_zonder_taal_de_standaard(self):
        self.invoeren()
        self.assertEqual(self.opgeslagen_taal(), "en")

    def test_onbekende_taal_geweigerd(self):
        self.assertEqual(self.invoeren(taal="fr").status_code, 400)


class OverigTests(Basis):
    def test_oude_route_zonder_taal_is_nederlands(self):
        with self.app.app_context():
            verwerk_reservering(get_db(), 69, "Jan", "jan@example.com", "0612345678", ZATERDAG, "19:00", 2,
                                zitduur_minuten=60)
        self.assertEqual(self.opgeslagen_taal(), "nl")

    def test_opnieuw_mailen_in_de_bewaarde_taal(self):
        with self.app.app_context():
            rid = verwerk_reservering(get_db(), 69, "Jan", "jan@example.com", "0612345678", ZATERDAG, "19:00", 2,
                                      zitduur_minuten=60, taal="id")
        with mock.patch("app.stuur_bevestigingsmail_sync") as verstuur:
            resultaat = self.app.test_cli_runner().invoke(args=["resend-mail", rid])
        self.assertEqual(resultaat.exit_code, 0, resultaat.output)
        self.assertEqual(verstuur.call_args.kwargs["taal"], "id")


if __name__ == "__main__":
    unittest.main()
