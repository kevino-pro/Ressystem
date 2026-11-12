"""
Config per restaurant, fase 2: de mails komen van de naam van het restaurant en antwoorden gaan naar
het e-mailadres van het restaurant (beide uit [restaurant] van het restaurantbestand).
"""
import json
import unittest
from unittest import mock

from app import create_app
from app.services import email_service
from app.services.email_service import (_afzender, _bouw_bevestigingsmail, _bouw_herinneringsmail,
                                        _bouw_wijzigingsmail)
from tests.test_toegang import TestConfig

RESERVERING = {"id": "abc", "naam": "Siti", "email": "siti@example.com", "datum": "2030-01-05", "tijd": "19:00",
               "aantal": 4, "taal": "nl"}


class MailConfig(TestConfig):
    VERZENDER_EMAIL = "reserveringen@voorbeeld.test"
    RESEND_API_KEY = "re_test"


class AfzenderTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(MailConfig)
        self.config = self.app.config

    def drie_mails(self):
        with self.app.app_context():
            return (_bouw_bevestigingsmail(self.config, "siti@example.com", "Siti", "2030-01-05", "19:00", 4, "abc", "nl"),
                    _bouw_herinneringsmail(self.config, RESERVERING),
                    _bouw_wijzigingsmail(self.config, RESERVERING))

    def test_naam_van_het_restaurant_als_afzender(self):
        verwacht = self.config["RESTAURANT_NAAM"] + " <reserveringen@voorbeeld.test>"
        for mail in self.drie_mails():
            with self.subTest(onderwerp=mail["subject"]):
                self.assertEqual(mail["from"], verwacht)

    def test_antwoorden_gaan_naar_het_restaurant(self):
        for mail in self.drie_mails():
            with self.subTest(onderwerp=mail["subject"]):
                self.assertEqual(mail["antwoord_aan"], self.config["RESTAURANT_EMAIL"])
                self.assertEqual(mail["to"], "siti@example.com")

    def test_naam_met_komma_staat_tussen_aanhalingstekens(self):
        config = {"RESTAURANT_NAAM": "Eethuis, De Kom", "VERZENDER_EMAIL": "a@voorbeeld.test"}
        self.assertEqual(_afzender(config), '"Eethuis, De Kom" <a@voorbeeld.test>')

    def test_naam_met_accent_wordt_gecodeerd(self):
        afzender = _afzender({"RESTAURANT_NAAM": "Café Bréda", "VERZENDER_EMAIL": "a@voorbeeld.test"})
        self.assertTrue(afzender.startswith("=?utf-8?"))
        self.assertTrue(afzender.endswith(" <a@voorbeeld.test>"))


class VersturenTests(unittest.TestCase):
    BERICHT = {"from": "Eethuis <a@voorbeeld.test>", "antwoord_aan": "info@eethuis.test", "to": "gast@example.com",
               "subject": "Bevestiging", "tekst": "Hallo"}
    CONFIG = {"RESEND_API_KEY": "re_test", "VERZENDER_EMAIL": "a@voorbeeld.test", "VERZENDER_WACHTWOORD": "geheim",
              "SMTP_SERVER": "smtp.voorbeeld.test", "SMTP_PORT": 587}

    def test_resend_krijgt_reply_to(self):
        with mock.patch.object(email_service.urllib.request, "urlopen") as urlopen:
            self.assertTrue(email_service.async_send_email(self.CONFIG, self.BERICHT, "gast@example.com", "r1"))
        inhoud = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(inhoud["from"], "Eethuis <a@voorbeeld.test>")
        self.assertEqual(inhoud["reply_to"], ["info@eethuis.test"])

    def test_smtp_krijgt_reply_to(self):
        config = dict(self.CONFIG, RESEND_API_KEY="")
        with mock.patch.object(email_service.smtplib, "SMTP") as smtp:
            self.assertTrue(email_service.async_send_email(config, self.BERICHT, "gast@example.com", "r1"))
        bericht = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
        self.assertEqual(bericht["From"], "Eethuis <a@voorbeeld.test>")
        self.assertEqual(bericht["Reply-To"], "info@eethuis.test")


if __name__ == "__main__":
    unittest.main()
