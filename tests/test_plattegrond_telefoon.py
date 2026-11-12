"""De plattegrond op een telefoon (personeel, fase 3): tafelknoppen in een vaste balk en een strook met tijden."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import insert

from app.database import get_db, init_db, reserveringen, tafeltoewijzingen, wijs_tafels_toe
from tests.hulp import scripts
from tests.test_plattegrond_pagina import TestConfig, maak_client


class PlattegrondTelefoonTests(unittest.TestCase):
    def setUp(self):
        self.app, self.client = maak_client(TestConfig)
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():  # de in-memory database wordt gedeeld tussen tests
                conn.execute(tafeltoewijzingen.delete())
                conn.execute(reserveringen.delete())

    def reservering(self, rid, tijd="19:00", aantal=2, tafels=()):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id=rid, naam="Jan", email=f"{rid}@example.com", telefoon="0612345678",
                    datum="2030-01-01", tijd=tijd, aantal=aantal))
            if tafels:
                wijs_tafels_toe(conn, rid, list(tafels), self.app.config["PLATTEGROND"], 90)

    def pagina(self, query="?datum=2030-01-01&tijd=19:30"):
        antwoord = self.client.get("/plattegrond" + query)
        return antwoord.status_code, antwoord.get_data(as_text=True)

    def test_bezette_tafel_krijgt_het_kenmerk_van_haar_reservering(self):
        self.reservering("r1", tijd="19:00", aantal=2, tafels=["1a"])
        _, html = self.pagina("?datum=2030-01-01&tijd=19:30")
        kenmerk = re.search(r'data-tafel="1a" data-stoelen="\d+" data-bezet="([0-9a-f]+)"', html).group(1)
        self.assertEqual(len(kenmerk), 24)
        self.assertIn(f'data-kenmerk="{kenmerk}"', html)  # dezelfde waarde staat op de reservering in de lijst

    def test_vrije_tafel_heeft_een_leeg_kenmerk(self):
        self.reservering("r1", tijd="19:00", aantal=2, tafels=["1a"])
        _, html = self.pagina("?datum=2030-01-01&tijd=19:30")
        self.assertRegex(html, r'data-tafel="10a" data-stoelen="\d+" data-bezet=""')

    def test_het_id_van_de_reservering_staat_niet_op_de_tekening(self):
        self.reservering("geheim-id-123", tijd="19:00", aantal=2, tafels=["1a"])
        _, html = self.pagina("?datum=2030-01-01&tijd=19:30")
        self.assertNotIn("geheim-id-123", html)

    def test_toewijsbalk_heeft_een_plek_voor_tafelknoppen_en_geen_vaste_stijl_meer(self):
        _, html = self.pagina()
        self.assertIn('id="toewijzen" class="toewijzen" hidden', html)
        self.assertIn('id="tafelkeuze"', html)
        self.assertNotIn('style="margin-top: 12px; border-top', html)

    def test_dagknoppen_hebben_een_label_en_de_tekst_verdwijnt_alleen_op_telefoon(self):
        _, html = self.pagina()
        self.assertIn('aria-label="Vorige dag">‹<span class="alleen-breed"> Vorige dag</span>', html)
        self.assertIn('aria-label="Volgende dag"><span class="alleen-breed">Volgende dag </span>›', html)

    def test_tijdbalk_toont_de_gekozen_tijd(self):
        _, html = self.pagina("?datum=2030-01-01&tijd=19:30")
        self.assertIn('class="pil aan" href="/plattegrond?datum=2030-01-01&amp;tijd=19:30"', html)

    def test_meldingen_nooit_als_html(self):
        _, html = self.pagina()
        self.assertNotIn("innerHTML", html)

    @unittest.skipUnless(shutil.which("node"), "node is niet geïnstalleerd")
    def test_script_is_geldig_javascript(self):
        _, html = self.pagina()
        script = next(s for s in scripts(html) if "tafelkeuze" in s)
        with tempfile.TemporaryDirectory() as map_:
            pad = Path(map_) / "plattegrond.js"
            pad.write_text(script, encoding="utf-8")
            resultaat = subprocess.run(["node", "--check", str(pad)], capture_output=True, text=True)
        self.assertEqual(resultaat.returncode, 0, resultaat.stderr)

if __name__ == "__main__":
    unittest.main()
