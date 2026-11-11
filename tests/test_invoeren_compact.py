"""Het formulier voor telefonische reserveringen en binnenlopers (personeel, fase 4): minder velden vooraf, direct zien of er plek is."""
import shutil
import subprocess
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from sqlalchemy import update

from app.database import get_db, personeel
from tests.test_personeel_reserveren import Basis


class FormulierOpbouwTests(Basis):
    def pagina(self, query=""):
        return self.client.get("/reservering/nieuw" + query).get_data(as_text=True)

    def test_telefonisch_naam_telefoon_aantal_tijd_en_datum_staan_bovenaan(self):
        html = self.pagina(f"?datum={self.dinsdag}")
        meer = html.index('<details class="meer" id="meer"')
        for veld in ("naam", "telefoon", "aantal", "tijd", "datum"):
            self.assertLess(html.index(f'id="{veld}"'), meer, veld)
        for veld in ("email", "taal", "kinderstoelen", "allergieen", "opmerking"):
            self.assertGreater(html.index(f'id="{veld}"'), meer, veld)

    def test_personen_en_tijd_staan_naast_elkaar(self):
        self.assertIn('<div class="twee naast">', self.pagina())

    def test_binnenloper_heeft_naam_en_telefoon_onder_meer_gegevens(self):
        html = self.pagina("?bron=binnenloper")
        meer = html.index('<details class="meer" id="meer"')
        for veld in ("aantal", "tijd", "datum"):
            self.assertLess(html.index(f'id="{veld}"'), meer, veld)
        for veld in ("naam", "telefoon", "email"):
            self.assertGreater(html.index(f'id="{veld}"'), meer, veld)
        self.assertEqual(html.count('id="naam"'), 1)  # nooit twee velden met dezelfde naam

    def test_uitklapblok_is_standaard_dicht(self):
        self.assertNotRegex(self.pagina(f"?datum={self.dinsdag}"), r'<details class="meer" id="meer"\s+open')

    def test_uitklapblok_gaat_open_bij_een_melding(self):
        antwoord = self.invoeren(email="geen-mail")
        self.assertEqual(antwoord.status_code, 400)
        self.assertRegex(antwoord.get_data(as_text=True), r'<details class="meer" id="meer"\s+open')

    def test_uitklapblok_gaat_open_als_er_iets_in_staat(self):
        self.bestaande("18:00", 69)  # vol: waarschuwing
        antwoord = self.invoeren(opmerking="Raamtafel")
        html = antwoord.get_data(as_text=True)
        self.assertIn("Toch opslaan", html)
        self.assertRegex(html, r'<details class="meer" id="meer"\s+open')
        self.assertIn("Raamtafel", html)

    def test_veld_voor_de_ruimtezin_en_nieuwe_tekst_in_de_taal_van_het_account(self):
        self.assertIn('id="ruimte"', self.pagina())
        self.assertIn("Meer gegevens", self.pagina())
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(update(personeel).where(personeel.c.gebruikersnaam == "anna").values(taal="id"))
        self.assertIn("Data lainnya", self.pagina())


class RuimteHulpTests(Basis):
    def ruimte(self, **query):
        vraag = {"datum": self.dinsdag.isoformat(), "tijd": "18:00", "aantal": "4", **query}
        return self.client.get("/reservering/ruimte", query_string=vraag)

    def test_alleen_voor_ingelogd_personeel(self):
        antwoord = self.app.test_client().get("/reservering/ruimte", query_string={
            "datum": self.dinsdag.isoformat(), "tijd": "18:00", "aantal": "4"})
        self.assertEqual(antwoord.status_code, 401)
        self.assertEqual(antwoord.get_json()["status"], "fout")

    def test_er_is_plek(self):
        self.bestaande("18:00", 20)
        data = self.ruimte().get_json()
        self.assertEqual(data["status"], "succes")
        self.assertFalse(data["let_op"])
        self.assertEqual(data["tekst"], "Rond 18:00 is er plek; er blijven 45 van 69 plekken vrij.")

    def test_te_vol_gebruikt_dezelfde_waarschuwing_als_bij_het_opslaan(self):
        self.bestaande("18:00", 68)
        data = self.ruimte().get_json()
        self.assertTrue(data["let_op"])
        self.assertEqual(data["tekst"], "Rond 18:00 zitten er dan 72 gasten tegelijk; het maximum is 69.")
        self.client.post("/reservering/nieuw", data={
            "bron": "telefoon", "naam": "Siti", "telefoon": "0612345678", "datum": self.dinsdag.isoformat(),
            "tijd": "18:00", "aantal": "4"})
        self.assertEqual(len(self.rijen()), 1)  # de hulproute bewaart niets

    def test_gesloten_dag_en_kinderstoelen(self):
        maandag = self.dinsdag - timedelta(days=1)
        self.assertIn("gesloten", self.ruimte(datum=maandag.isoformat()).get_json()["tekst"])
        self.bestaande("18:00", 2, kinderstoelen=2)
        tekst = self.ruimte(kinderstoelen="1").get_json()["tekst"]
        self.assertIn("kinderstoelen nodig", tekst)

    def test_ongeldige_invoer_geeft_400(self):
        for vraag in ({"datum": "morgen"}, {"tijd": "laat"}, {"aantal": "veel"}, {"aantal": "0"}, {"aantal": "201"},
                      {"kinderstoelen": "-1"}, {"datum": ""}):
            self.assertEqual(self.ruimte(**vraag).status_code, 400, vraag)

    def test_in_het_indonesisch(self):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(update(personeel).where(personeel.c.gebruikersnaam == "anna").values(taal="id"))
        self.assertIn("masih ada tempat", self.ruimte().get_json()["tekst"])


class ScriptTests(Basis):
    @unittest.skipUnless(shutil.which("node"), "node is niet geïnstalleerd")
    def test_script_is_geldig_javascript(self):
        html = self.client.get("/reservering/nieuw").get_data(as_text=True)
        script = next(s.split("</script>")[0] for s in html.split("<script>")[1:] if "ruimte" in s.split("</script>")[0])
        with tempfile.TemporaryDirectory() as map_:
            pad = Path(map_) / "invoeren.js"
            pad.write_text(script, encoding="utf-8")
            resultaat = subprocess.run(["node", "--check", str(pad)], capture_output=True, text=True)
        self.assertEqual(resultaat.returncode, 0, resultaat.stderr)
        self.assertNotIn("innerHTML", html)


# De basisklasse zelf heeft geen tests; deze regel voorkomt dat de tests van test_personeel_reserveren hier opnieuw draaien.
del Basis

if __name__ == "__main__":
    unittest.main()
