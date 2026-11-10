"""Deel 9 fase 2: een mail na het wijzigen, en de markering "Gewijzigd door de gast" voor het personeel."""
import unittest
from unittest import mock

from app.services.email_service import _bouw_herinneringsmail, _bouw_wijzigingsmail, stuur_wijzigingsmail_async
from tests.hulp import log_in
from tests.test_gast_wijzigen import MORGEN, Basis


class WijzigingsmailTests(Basis):
    def mail(self, taal):
        rid = self.voeg_toe(tijd="19:30", aantal=4)
        rij = dict(self.lees(rid), taal=taal)
        with self.app.app_context():
            return rid, _bouw_wijzigingsmail(self.app.config, rij)

    def test_nederlands(self):
        rid, mail = self.mail("nl")
        self.assertEqual(mail["subject"], "Je reservering is gewijzigd - " + self.app.config["RESTAURANT_NAAM"])
        self.assertTrue(mail["to"].endswith("@example.com"))
        for tekst in ("Beste Siti Rahma,", "is gewijzigd. Dit zijn de nieuwe gegevens:", "Woensdag 2 januari 2030",
                      "Tijdstip: 19:30", "Aantal personen: 4", f"/annuleren/{rid}", "Heb je dit niet zelf gedaan?"):
            with self.subTest(tekst=tekst):
                self.assertIn(tekst, mail["tekst"])

    def test_engels_en_indonesisch(self):
        _, engels = self.mail("en")
        self.assertTrue(engels["subject"].startswith("Your booking has been changed"))
        self.assertIn("Wednesday 2 January 2030", engels["tekst"])
        self.assertNotRegex(engels["tekst"], r"\b(am|pm)\b")
        _, indonesisch = self.mail("id")
        self.assertTrue(indonesisch["subject"].startswith("Reservasi Anda sudah diubah"))
        self.assertIn("Rabu 2 Januari 2030", indonesisch["tekst"])

    def test_geen_allergie_of_opmerking_in_de_mail(self):
        rid = self.voeg_toe()
        rij = dict(self.lees(rid), allergieen="pinda", opmerking="verjaardag")
        tekst = _bouw_wijzigingsmail(self.app.config, rij)["tekst"]
        self.assertNotIn("pinda", tekst)
        self.assertNotIn("verjaardag", tekst)

    def test_zonder_e_mailadres_geen_mail(self):
        rid = self.voeg_toe()
        with self.app.app_context(), mock.patch("app.services.email_service.threading.Thread") as thread:
            stuur_wijzigingsmail_async(dict(self.lees(rid), email=""))
            thread.assert_not_called()
            stuur_wijzigingsmail_async(self.lees(rid))
            thread.assert_called_once()


class NaHetWijzigenTests(Basis):
    def post(self, rid, taal="nl", **velden):
        data = {"datum": MORGEN, "tijd": "19:00", "aantal": "2", **velden}
        return self.client.post(f"/wijzigen/{rid}", data=data, headers={"Accept-Language": taal})

    def test_mail_met_de_nieuwe_gegevens(self):
        rid = self.voeg_toe()
        self.assertEqual(self.post(rid, tijd="19:30", aantal="3").status_code, 200)
        self.wijzigingsmail.assert_called_once()
        rij = self.wijzigingsmail.call_args.args[0]
        self.assertEqual((rij["id"], rij["tijd"], rij["aantal"]), (rid, "19:30", 3))

    def test_geen_mail_als_het_niet_lukt(self):
        rid = self.voeg_toe()
        self.assertEqual(self.post(rid, datum="2030-01-07").status_code, 400)  # maandag dicht
        self.wijzigingsmail.assert_not_called()

    def test_mail_in_de_taal_van_de_pagina(self):
        rid = self.voeg_toe()  # taal nl
        self.post(rid, taal="en")
        self.assertEqual(self.lees(rid)["taal"], "en")  # ook de herinnering gaat nu in het Engels
        self.assertEqual(self.wijzigingsmail.call_args.args[0]["taal"], "en")


class MarkeringTests(Basis):
    def setUp(self):
        super().setUp()
        log_in(self.app, self.client, naam="anna", rol="medewerker")

    def test_overzicht_toont_gewijzigd(self):
        gewijzigd, gewoon = self.voeg_toe(), self.voeg_toe(tijd="18:30")
        self.client.post(f"/wijzigen/{gewijzigd}", data={"datum": MORGEN, "tijd": "19:00", "aantal": "2"})
        html = self.client.get("/overzicht", query_string={"datum": MORGEN}).get_data(as_text=True)
        self.assertEqual(html.count("Gewijzigd door de gast"), 1)
        self.assertLess(html.index("19:00"), html.index("Gewijzigd door de gast"))

    def test_niet_meer_na_aankomst(self):
        rid = self.voeg_toe()
        self.client.post(f"/wijzigen/{rid}", data={"datum": MORGEN, "tijd": "19:00", "aantal": "2"})
        from app.database import get_db, zet_status
        with self.app.app_context():
            zet_status(get_db(), rid, "gearriveerd")
        html = self.client.get("/overzicht", query_string={"datum": MORGEN}).get_data(as_text=True)
        self.assertNotIn("Gewijzigd door de gast", html)

    def test_zoeken_toont_gewijzigd(self):
        rid = self.voeg_toe()
        self.client.post(f"/wijzigen/{rid}", data={"datum": MORGEN, "tijd": "19:00", "aantal": "2"})
        html = self.client.get("/zoeken", query_string={"q": "siti"}).get_data(as_text=True)
        self.assertIn("Gewijzigd door de gast", html)

    def test_in_het_engels(self):
        rid = self.voeg_toe()
        self.client.post(f"/wijzigen/{rid}", data={"datum": MORGEN, "tijd": "19:00", "aantal": "2"})
        self.client.get("/taal/en")  # personeel: de taal hoort bij het account
        html = self.client.get("/overzicht", query_string={"datum": MORGEN}).get_data(as_text=True)
        self.assertIn("Changed by the guest", html)


class TekstenTests(Basis):
    def test_herinnering_noemt_wijzigen(self):
        rid = self.voeg_toe()
        tekst = _bouw_herinneringsmail(self.app.config, self.lees(rid))["tekst"]
        self.assertIn("Wil je iets wijzigen, of kun je toch niet komen? Dat regel je via deze link:", tekst)
        self.assertIn(f"/annuleren/{rid}", tekst)
        self.assertIn("Liever bellen? Bel ons op", tekst)

    def test_bevestigingspagina_noemt_wijzigen(self):
        html = self.client.get("/bevestiging").get_data(as_text=True)
        self.assertIn("Wil je iets wijzigen of kun je toch niet komen? Gebruik de link in je mail, of bel", html)


if __name__ == "__main__":
    unittest.main()
