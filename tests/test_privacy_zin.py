"""Reserveerformulier: een zin over de privacyverklaring in plaats van een vinkje (reserveringspagina, fase 3)."""
import unittest

from tests.test_talen import ZATERDAG, Basis


class PrivacyZinTests(Basis):
    def boek(self, **velden):
        data = {"naam": "Siti Rahma", "email": "siti@example.com", "telefoon": "0612345678", "datum": ZATERDAG,
                "tijd": "19:00", "aantal": 2, **velden}
        return self.client.post("/reservering", json=data)

    def test_zin_met_link_in_alle_talen(self):
        verwacht = {
            "nl": "Door te reserveren ga je akkoord met onze",
            "en": "By booking you agree to our",
            "id": "Dengan memesan, Anda menyetujui",
        }
        for taal, begin in verwacht.items():
            html = self.pagina(**{"Accept-Language": taal})
            self.assertTrue(begin in html, taal)
            self.assertTrue('<a href="/privacy" target="_blank">' in html, taal)
            self.assertFalse('id="privacy_akkoord"' in html, taal)

    def test_zin_staat_onder_de_knop_en_niet_in_de_vaste_balk(self):
        html = self.pagina(**{"Accept-Language": "nl"})
        balk_einde = html.index("</div>", html.index('id="submitBtn"'))
        self.assertGreater(html.index('class="juridisch"'), balk_einde)

    def test_reserveren_zonder_privacy_akkoord(self):
        antwoord = self.boek()
        self.assertEqual(antwoord.status_code, 200, antwoord.get_json())
        self.assertEqual(antwoord.get_json()["status"], "succes")

    def test_oudere_pagina_met_privacy_akkoord_blijft_werken(self):
        for waarde, email in ((True, "a@example.com"), (False, "b@example.com")):
            antwoord = self.boek(privacy_akkoord=waarde, email=email, telefoon=f"06{abs(hash(email)) % 10**8:08d}")
            self.assertEqual(antwoord.status_code, 200, antwoord.get_json())

    def test_onzin_in_privacy_akkoord_wordt_geweigerd(self):
        antwoord = self.boek(privacy_akkoord="misschien")
        self.assertEqual(antwoord.status_code, 422)

    def test_onbekend_veld_blijft_geweigerd(self):
        self.assertEqual(self.boek(iets_anders=1).status_code, 422)


if __name__ == "__main__":
    unittest.main()
