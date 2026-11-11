"""Reserveerformulier, compacte opzet (reserveringspagina, fase 1)."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app import create_app
from tests.test_formulier import TestConfig
from tests.test_toegang import TestConfig as TalenConfig


class CompactFormulierTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.html = self.pagina()

    def pagina(self, taal="nl"):
        return self.client.get("/", headers={"Accept-Language": taal}).get_data(as_text=True)

    def test_aantal_is_een_keuzelijst_met_twee_als_start(self):
        keuzelijst = self.html.split('<select id="aantal">')[1].split("</select>")[0]
        opties = re.findall(r'<option value="(\d+)"( selected)?>([^<]+)</option>', keuzelijst)
        self.assertEqual([o[0] for o in opties], [str(n) for n in range(1, 9)])
        self.assertEqual([o[0] for o in opties if o[1]], ["2"])
        self.assertEqual(opties[0][2], "1 persoon")
        self.assertEqual(opties[1][2], "2 personen")
        self.assertNotIn("data-aantal", self.html)

    def test_geen_nummerbadges(self):
        self.assertNotIn('class="nr"', self.html)

    def test_extras_staan_in_een_uitklapblok(self):
        begin = self.html.index('<details class="meer" id="meer">')
        einde = self.html.index("</details>", begin)
        self.assertIn("Nog iets dat we moeten weten?", self.html[begin:einde])
        self.assertIn('id="opmerking"', self.html[begin:einde])
        self.assertNotIn(" open", self.html[begin:begin + 40])  # standaard dicht

    def test_knop_staat_uit_tot_er_een_tijd_is(self):
        self.assertIn('id="submitBtn" class="knop" disabled', self.html)
        self.assertIn('id="samen"', self.html)
        self.assertIn("Kies een tijd", self.html)

    def test_personeel_alleen_in_de_voet(self):
        self.assertEqual(self.html.count('href="/login"'), 1)
        self.assertGreater(self.html.index('href="/login"'), self.html.index("<footer"))

    def test_naam_en_email_zonder_placeholder(self):
        for veld in ("naam", "email"):
            tag = re.search(rf'<input[^>]*id="{veld}"[^>]*>', self.html).group(0)
            self.assertNotIn("placeholder", tag, veld)

    def test_meldingen_per_veld_en_uitleg_bij_telefoon(self):
        for veld in ("naam", "email", "telefoon"):
            self.assertIn(f'id="fout-{veld}" role="alert" hidden', self.html)
        self.assertIn("Alleen voor als we je moeten bereiken", self.html)

    def test_bel_ons_staat_bij_het_aantal(self):
        self.assertIn("Met meer dan 8 personen? Bel", self.html)
        self.assertNotIn("Online tot", self.html)

    def test_geen_privacyvinkje_meer(self):
        self.assertNotIn('id="privacy_akkoord"', self.html)


class MeertaligFormulierTests(unittest.TestCase):
    """Met [talen] in het restaurantbestand (restaurants/wpl.toml) kiest de gast Nederlands, Engels of Indonesisch."""

    def setUp(self):
        self.client = create_app(TalenConfig).test_client()

    def pagina(self, taal):
        return self.client.get("/", headers={"Accept-Language": taal}).get_data(as_text=True)

    def test_nieuwe_teksten_in_alle_talen(self):
        verwacht = {
            "nl": ("Kies een tijd", "Vul een geldig e-mailadres in."),
            "en": ("Choose a time", "Please enter a valid email address."),
            "id": ("Pilih waktu", "Masukkan alamat email yang valid."),
        }
        for taal, teksten in verwacht.items():
            html = self.pagina(taal)
            for tekst in teksten:
                self.assertTrue(tekst in html, f"{taal}: {tekst}")

    @unittest.skipUnless(shutil.which("node"), "node is niet geïnstalleerd")
    def test_script_is_geldig_javascript(self):
        for taal in ("nl", "en", "id"):
            script = self.pagina(taal).split("<script>")[-1].split("</script>")[0]
            with tempfile.TemporaryDirectory() as map_:
                pad = Path(map_) / "formulier.js"
                pad.write_text(script, encoding="utf-8")
                resultaat = subprocess.run(["node", "--check", str(pad)], capture_output=True, text=True)
            self.assertEqual(resultaat.returncode, 0, f"{taal}: {resultaat.stderr}")


if __name__ == "__main__":
    unittest.main()
