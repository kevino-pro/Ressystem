"""
Deel 7: de herinneringsmail de dag voor het bezoek, in de taal van de gast.
POST /beheer/herinneringen verstuurt vanaf het ingestelde uur, elke reservering hoogstens een keer.
"""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from sqlalchemy import insert, select

from app import create_app
from app.config import Config
from app.database import claim_herinnering, get_db, init_db, reserveringen, tafeltoewijzingen
from app.herinnering import Herinnering, laad_herinnering, morgen_en_grens, verstuur_herinneringen
from app.reserveringsregels import ReserveringsRegels
from app.security import reset_rate_limits
from app.services.email_service import _bouw_herinneringsmail, async_send_email

SLEUTEL = "s" * 40
NU = datetime(2026, 11, 17, 10, 5, tzinfo=ZoneInfo("Europe/Amsterdam"))  # dinsdag; morgen is woensdag 18 november
MORGEN = "2026-11-18"
GISTEREN_UTC = datetime(2026, 11, 16, 12, 0)   # aangemaakt_op staat in UTC zonder tijdzone
VANDAAG_UTC = datetime(2026, 11, 17, 8, 0)     # 09:00 in Amsterdam: vandaag gereserveerd


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    ADMIN_INITIAL_PASSWORD = "test-admin-pw"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    BEHEER_API_KEY = SLEUTEL
    RESTAURANT_CONFIG = "restaurants/wpl.toml"
    RESEND_API_KEY = "test-resend"
    APP_BASE_URL = "https://reserveren.example"
    RESTAURANT_TELEFOON = "070-0000000"


class ZonderHerinneringConfig(TestConfig):
    RESTAURANT_CONFIG = "tests/fixtures/restaurant_test.toml"


class Basis(unittest.TestCase):
    config = TestConfig

    def setUp(self):
        reset_rate_limits()
        for doel, waarde in (("nu", lambda self: NU),):
            patcher = mock.patch.object(ReserveringsRegels, doel, waarde)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch("app.services.email_service._verstuur_via_resend")
        self.resend = patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch("app.herinnering.time.sleep")
        self.slaap = patcher.start()
        self.addCleanup(patcher.stop)
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():  # de in-memory database wordt gedeeld tussen tests
                conn.execute(tafeltoewijzingen.delete())
                conn.execute(reserveringen.delete())

    def voeg_toe(self, rid, datum=MORGEN, tijd="19:00", email=None, taal="nl", status="verwacht",
                 aangemaakt_op=GISTEREN_UTC, herinnering_verstuurd=None):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=rid, naam=f"Gast {rid}", email=f"{rid}@example.com" if email is None else email,
                    telefoon="0612345678", datum=datum, tijd=tijd, aantal=2, taal=taal, status=status,
                    aangemaakt_op=aangemaakt_op, herinnering_verstuurd=herinnering_verstuurd))

    def post(self, sleutel=SLEUTEL):
        return self.client.post("/beheer/herinneringen", headers={"X-Beheer-Key": sleutel})

    def ontvangers(self):
        return [aanroep.args[1]["to"] for aanroep in self.resend.call_args_list]

    def herinnerd(self, rid):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                return conn.execute(select(reserveringen.c.herinnering_verstuurd)
                                    .where(reserveringen.c.id == rid)).scalar() is not None


class InstellingTests(unittest.TestCase):
    def schrijf(self, inhoud):
        map_ = tempfile.TemporaryDirectory()
        self.addCleanup(map_.cleanup)
        pad = Path(map_.name) / "r.toml"
        pad.write_text(inhoud, encoding="utf-8")
        return pad

    def test_zonder_sectie_geen_herinnering(self):
        self.assertIsNone(laad_herinnering(self.schrijf("[x]\na = 1\n")))

    def test_uur_ingesteld(self):
        self.assertEqual(laad_herinnering(self.schrijf("[herinnering]\nuur = 9\n")), Herinnering(uur=9))

    def test_ongeldig_uur_of_onbekende_sleutel(self):
        for inhoud in ("[herinnering]\nuur = 24\n", "[herinnering]\nuur = -1\n", "[herinnering]\nuren = 10\n"):
            with self.subTest(inhoud=inhoud), self.assertRaises(RuntimeError):
                laad_herinnering(self.schrijf(inhoud))

    def test_wpl_om_tien_uur(self):
        self.assertEqual(laad_herinnering("restaurants/wpl.toml").uur, 10)

    def test_grens_is_begin_van_vandaag_in_utc(self):
        regels = mock.Mock(nu=lambda: NU)
        self.assertEqual(morgen_en_grens(regels), (MORGEN, datetime(2026, 11, 16, 23, 0)))


class RouteTests(Basis):
    def test_verkeerde_sleutel(self):
        self.voeg_toe("a")
        self.assertEqual(self.post("x" * 40).status_code, 401)
        self.resend.assert_not_called()

    def test_stuurt_herinneringen_voor_morgen(self):
        self.voeg_toe("a")
        self.voeg_toe("b", tijd="12:00")
        antwoord = self.post()
        self.assertEqual(antwoord.status_code, 200)
        self.assertEqual(antwoord.get_json(), {"status": "succes", "verstuurd": 2, "mislukt": 0, "resterend": 0})
        self.assertEqual(self.ontvangers(), ["b@example.com", "a@example.com"])  # op volgorde van tijd
        self.assertTrue(self.herinnerd("a"))

    def test_tweede_keer_niets_dubbel(self):
        self.voeg_toe("a")
        self.post()
        antwoord = self.post()
        self.assertEqual(antwoord.get_json()["verstuurd"], 0)
        self.assertEqual(self.resend.call_count, 1)

    def test_voor_het_ingestelde_uur_niets(self):
        self.voeg_toe("a")
        with mock.patch.object(ReserveringsRegels, "nu", lambda self: NU.replace(hour=9, minute=59)):
            antwoord = self.post()
        self.assertEqual(antwoord.get_json()["status"], "te_vroeg")
        self.resend.assert_not_called()
        self.assertFalse(self.herinnerd("a"))

    def test_slaat_over_wie_geen_herinnering_hoort_te_krijgen(self):
        self.voeg_toe("vandaag_gemaakt", aangemaakt_op=VANDAAG_UTC)
        self.voeg_toe("zonder_mail", email="")
        self.voeg_toe("al_herinnerd", herinnering_verstuurd=datetime(2026, 11, 17, 9, 0))
        self.voeg_toe("niet_gekomen", status="no_show")
        self.voeg_toe("vandaag", datum="2026-11-17")
        self.voeg_toe("overmorgen", datum="2026-11-19")
        self.voeg_toe("wel")
        self.post()
        self.assertEqual(self.ontvangers(), ["wel@example.com"])

    def test_mislukte_mail_wordt_later_opnieuw_geprobeerd(self):
        self.voeg_toe("a")
        self.resend.side_effect = OSError("geen verbinding")
        self.assertEqual(self.post().get_json()["mislukt"], 1)
        self.assertFalse(self.herinnerd("a"))
        self.resend.side_effect = None
        self.assertEqual(self.post().get_json()["verstuurd"], 1)
        self.assertTrue(self.herinnerd("a"))

    def test_zonder_herinnering_in_restaurantbestand(self):
        self.app = create_app(ZonderHerinneringConfig)
        self.client = self.app.test_client()
        self.voeg_toe("a")
        self.assertEqual(self.post().get_json()["status"], "uit")
        self.resend.assert_not_called()


class VersturenTests(Basis):
    def test_hoogstens_max_per_keer_met_pauze(self):
        for rid in ("a", "b", "c"):
            self.voeg_toe(rid)
        with self.app.app_context():
            self.assertEqual(verstuur_herinneringen(get_db(), self.app.config, max_aantal=2, pauze=0.6), (2, 0, 1))
            self.assertEqual(self.slaap.call_count, 1)  # alleen tussen twee mails
            self.assertEqual(verstuur_herinneringen(get_db(), self.app.config, max_aantal=2), (1, 0, 0))
        self.assertEqual(self.resend.call_count, 3)

    def test_claim_maar_een_keer(self):
        self.voeg_toe("a")
        with self.app.app_context():
            self.assertTrue(claim_herinnering(get_db(), "a"))
            self.assertFalse(claim_herinnering(get_db(), "a"))

    def test_versturen_geeft_resultaat_terug(self):
        bericht = {"from": "a@example.com", "to": "b@example.com", "subject": "s", "tekst": "t"}
        self.assertTrue(async_send_email(self.app.config, bericht, "b@example.com", "x"))
        self.resend.side_effect = OSError("weg")
        self.assertFalse(async_send_email(self.app.config, bericht, "b@example.com", "x"))


class MailTests(Basis):
    def mail(self, taal):
        self.voeg_toe("a", taal=taal)
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                r = conn.execute(select(reserveringen).where(reserveringen.c.id == "a")).mappings().first()
            return _bouw_herinneringsmail(self.app.config, r)

    def test_nederlands(self):
        mail = self.mail("nl")
        self.assertEqual(mail["subject"], "Herinnering: je reservering morgen om 19:00 - " + self.app.config["RESTAURANT_NAAM"])
        for tekst in ("Beste Gast a,", "Woensdag 18 november 2026", "Tijdstip: 19:00", "Aantal personen: 2",
                      "Adres: Schoolstraat 35, 2511 AW Den Haag", "https://reserveren.example/annuleren/a",
                      "Bel ons op 070-0000000."):
            with self.subTest(tekst=tekst):
                self.assertIn(tekst, mail["tekst"])

    def test_engels(self):
        mail = self.mail("en")
        self.assertTrue(mail["subject"].startswith("Reminder: your booking tomorrow at 19:00"))
        self.assertIn("Wednesday 18 November 2026", mail["tekst"])
        self.assertNotIn("Beste", mail["tekst"])

    def test_indonesisch(self):
        mail = self.mail("id")
        self.assertTrue(mail["subject"].startswith("Pengingat: reservasi Anda besok pukul 19:00"))
        self.assertIn("Rabu 18 November 2026", mail["tekst"])

    def test_geen_am_pm(self):
        self.assertNotRegex(self.mail("en")["tekst"], r"\b(am|pm)\b")


class CliTests(Basis):
    def test_tellen_en_versturen(self):
        self.voeg_toe("a")
        runner = self.app.test_cli_runner()
        resultaat = runner.invoke(args=["herinneringen"])
        self.assertIn(f"1 herinnering(en) voor {MORGEN} klaar", resultaat.output)
        self.resend.assert_not_called()
        resultaat = runner.invoke(args=["herinneringen", "--uitvoeren"])
        self.assertEqual(resultaat.exit_code, 0, resultaat.output)
        self.assertIn("1 herinnering(en) voor 2026-11-18 verstuurd, 0 mislukt.", resultaat.output)

    def test_zonder_herinnering_foutmelding(self):
        app = create_app(ZonderHerinneringConfig)
        resultaat = app.test_cli_runner().invoke(args=["herinneringen"])
        self.assertNotEqual(resultaat.exit_code, 0)
        self.assertIn("geen [herinnering]", resultaat.output)


if __name__ == "__main__":
    unittest.main()
