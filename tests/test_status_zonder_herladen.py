"""De status zetten zonder de pagina te herladen (fase 2): /aankomst antwoordt met JSON als het overzicht daarom vraagt."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.hulp import scripts
from tests.test_aankomst import MORGEN, VANDAAG, Basis

JSON = {"Accept": "application/json"}


class StatusAlsJsonTests(Basis):
    def zet_json(self, reservering_id, status, datum=VANDAAG, kenmerk=None):
        data = {"datum": datum, "kenmerk": kenmerk or self.kenmerk(reservering_id), "status": status}
        return self.client.post("/aankomst", data=data, headers=JSON)

    def test_is_er_geeft_json_en_geen_doorverwijzing(self):
        rid = self.reservering()
        antwoord = self.zet_json(rid, "gearriveerd")
        self.assertEqual(antwoord.status_code, 200)
        self.assertEqual(antwoord.get_json(), {"status": "succes", "bericht": "Siti is er."})
        self.assertEqual(self.status(rid), "gearriveerd")

    def test_json_antwoord_laat_geen_melding_achter_voor_de_volgende_pagina(self):
        rid = self.reservering()
        self.zet_json(rid, "gearriveerd")
        html = self.client.get(f"/overzicht?datum={VANDAAG}").get_data(as_text=True)
        self.assertNotIn('class="melding', html)  # de melding stond al in het JSON-antwoord

    def test_terugdraaien_geeft_json(self):
        rid = self.reservering()
        self.zet_json(rid, "no_show")
        antwoord = self.zet_json(rid, "verwacht")
        self.assertEqual(antwoord.get_json(), {"status": "succes", "bericht": "Siti staat weer op verwacht."})
        self.assertEqual(self.status(rid), "verwacht")

    def test_no_show_voor_de_begintijd_geeft_409_met_de_reden(self):
        rid = self.reservering(tijd="19:00")
        antwoord = self.zet_json(rid, "no_show")
        self.assertEqual(antwoord.status_code, 409)
        self.assertEqual(antwoord.get_json(), {"status": "fout", "bericht": "Een no-show kan pas na de begintijd (19:00)."})
        self.assertEqual(self.status(rid), "verwacht")

    def test_toekomstige_dag_geeft_409(self):
        rid = self.reservering(datum=MORGEN)
        antwoord = self.zet_json(rid, "gearriveerd", datum=MORGEN)
        self.assertEqual(antwoord.status_code, 409)
        self.assertEqual(antwoord.get_json()["status"], "fout")
        self.assertEqual(self.status(rid), "verwacht")

    def test_onbekende_reservering_en_ongeldige_status_geven_json(self):
        rid = self.reservering()
        onbekend = self.zet_json(rid, "gearriveerd", kenmerk="bestaat-niet")
        self.assertEqual(onbekend.status_code, 404)
        self.assertEqual(onbekend.get_json()["status"], "fout")
        ongeldig = self.zet_json(rid, "weg")
        self.assertEqual(ongeldig.status_code, 400)
        self.assertEqual(ongeldig.get_json()["status"], "fout")
        self.assertEqual(self.status(rid), "verwacht")

    def test_zonder_json_blijft_het_een_doorverwijzing(self):
        rid = self.reservering()
        antwoord = self.zet(rid, "gearriveerd")  # zoals het formulier zonder JavaScript
        self.assertEqual(antwoord.status_code, 302)
        self.assertEqual(antwoord.headers["Location"], f"/overzicht?datum={VANDAAG}")

    def test_niet_ingelogd_krijgt_geen_json_met_gegevens(self):
        rid = self.reservering()
        kenmerk = self.kenmerk(rid)
        gast = self.app.test_client()
        antwoord = gast.post("/aankomst", data={"datum": VANDAAG, "kenmerk": kenmerk, "status": "gearriveerd"}, headers=JSON)
        self.assertEqual(antwoord.status_code, 302)
        self.assertIn("/login", antwoord.headers["Location"])
        self.assertEqual(self.status(rid), "verwacht")


class OverzichtScriptTests(Basis):
    def pagina(self):
        self.reservering(naam="Siti <b>Rahma</b>")
        return self.client.get(f"/overzicht?datum={VANDAAG}").get_data(as_text=True)

    def script(self, html):
        return next(s for s in scripts(html) if "/aankomst" in s)

    def test_lijst_tellers_en_melding_hebben_een_id(self):
        html = self.pagina()
        self.assertIn('<div class="tellers strook" id="tellers">', html)
        self.assertIn('<div class="lijst" id="lijst">', html)
        self.assertIn('<div class="toast" id="toast" role="status" aria-live="polite" hidden>', html)
        self.assertIn('<button type="button" id="toast-ongedaan" hidden>Ongedaan maken</button>', html)

    def test_het_formulier_werkt_ook_zonder_javascript(self):
        html = self.pagina()
        self.assertIn('<form class="status" action="/aankomst" method="POST">', html)
        self.assertIn('<input type="hidden" name="csrf_token"', html)
        self.assertIn('<button type="submit" name="status" value="gearriveerd">Is er</button>', html)

    def test_script_vraagt_json_stuurt_het_csrf_token_en_ververst(self):
        script = self.script(self.pagina())
        self.assertIn("'Accept': 'application/json', 'X-CSRF-Token': csrf", script)
        self.assertIn("setInterval(ververs, VERVERS_MS)", script)
        self.assertIn("visibilitychange", script)
        self.assertIn("e.submitter", script)

    def test_de_naam_van_de_gast_komt_nooit_als_html_in_de_melding(self):
        html = self.pagina()
        script = self.script(html)
        self.assertIn("toastTekst.textContent = tekst", script)
        self.assertNotIn("innerHTML", script)
        self.assertNotIn("Rahma", script)  # de naam staat alleen (ge-escaped) in de lijst, niet in het script
        self.assertNotIn("<b>Rahma</b>", html)

    @unittest.skipUnless(shutil.which("node"), "node is niet geïnstalleerd")
    def test_script_is_geldig_javascript(self):
        script = self.script(self.pagina())
        with tempfile.TemporaryDirectory() as map_:
            pad = Path(map_) / "overzicht.js"
            pad.write_text(script, encoding="utf-8")
            resultaat = subprocess.run(["node", "--check", str(pad)], capture_output=True, text=True)
        self.assertEqual(resultaat.returncode, 0, resultaat.stderr)


if __name__ == "__main__":
    unittest.main()
