"""De wijzigpagina in dezelfde stijl als het reserveerformulier (reserveringspagina, fase 4)."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.hulp import scripts
from tests.test_gast_wijzigen import MORGEN, VANDAAG, Basis


class WijzigPaginaStijlTests(Basis):
    def setUp(self):
        super().setUp()
        self.rid = self.voeg_toe(tijd="18:30", aantal=3)

    def pagina(self, taal="nl", rid=None):
        return self.client.get(f"/annuleren/{rid or self.rid}", headers={"Accept-Language": taal}).get_data(as_text=True)

    def test_aantal_is_een_keuzelijst_met_het_huidige_aantal(self):
        html = self.pagina()
        keuzelijst = html.split('<select id="aantal">')[1].split("</select>")[0]
        opties = re.findall(r'<option value="(\d+)"( selected)?>', keuzelijst)
        self.assertEqual([o[0] for o in opties], [str(n) for n in range(1, 16)])
        self.assertEqual([o[0] for o in opties if o[1]], ["3"])
        self.assertNotIn("data-aantal", html)

    def test_geen_nummerbadges_en_geen_losse_samenvatting(self):
        html = self.pagina()
        self.assertNotIn('class="nr"', html)
        self.assertNotIn('id="samenvatting"', html)

    def test_dagstrook_met_andere_dag(self):
        html = self.pagina()
        self.assertIn('class="dagrij" id="dagen"', html)
        self.assertIn("<small>Vandaag</small><b>1</b>", html)
        self.assertIn("<small>Morgen</small><b>2</b>", html)
        self.assertIn('class="andere-wrap"', html)
        self.assertIn('id="datum" class="datumveld"', html)
        self.assertNotIn("showPicker", html)
        self.assertNotIn('class="keuzes dagen"', html)

    def test_vaste_balk_met_knop_die_uit_staat_tot_er_iets_verandert(self):
        html = self.pagina()
        self.assertIn('class="actiebalk"', html)
        self.assertIn("Nog niets veranderd", html)
        self.assertIn('id="submitBtn" class="knop" disabled>Wijziging opslaan', html)

    def test_bestaande_velden_blijven(self):
        html = self.pagina()
        for tekst in (f'action="/wijzigen/{self.rid}"', 'name="aantal" id="veld_aantal" value="3"',
                      f'name="datum" id="veld_datum" value="{MORGEN}"', 'name="tijd" id="veld_tijd" value="18:30"',
                      "&behalve=", "Ja, annuleer mijn reservering", "Nee, ik kom gewoon",
                      "Wijzigen kan tot 2 uur van tevoren."):
            self.assertTrue(tekst in html, tekst)

    def test_pagina_zonder_wijzigen_toont_geen_formulier(self):
        rid = self.voeg_toe(datum=VANDAAG, tijd="12:30")  # begint binnen 2 uur: wijzigen kan niet meer
        html = self.pagina(rid=rid)
        self.assertNotIn("wijzigForm", html)
        self.assertNotIn('class="actiebalk"', html)
        self.assertIn("Ja, annuleer mijn reservering", html)

    def test_nieuwe_tekst_in_alle_talen(self):
        for taal, tekst in {"nl": "Nog niets veranderd", "en": "Nothing changed yet", "id": "Belum ada perubahan"}.items():
            self.assertTrue(tekst in self.pagina(taal), taal)

    def test_meldingen_nooit_als_html(self):
        self.assertNotIn("innerHTML", self.pagina())

    @unittest.skipUnless(shutil.which("node"), "node is niet geïnstalleerd")
    def test_script_is_geldig_javascript(self):
        for taal in ("nl", "en", "id"):
            script = scripts(self.pagina(taal))[-1]
            with tempfile.TemporaryDirectory() as map_:
                pad = Path(map_) / "wijzigen.js"
                pad.write_text(script, encoding="utf-8")
                resultaat = subprocess.run(["node", "--check", str(pad)], capture_output=True, text=True)
            self.assertEqual(resultaat.returncode, 0, f"{taal}: {resultaat.stderr}")


if __name__ == "__main__":
    unittest.main()
