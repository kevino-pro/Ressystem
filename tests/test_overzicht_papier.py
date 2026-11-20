"""Het overzicht als het papier: elke reservering is één regel met vaste kolommen en een koprij (fase 3)."""
import re
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from sqlalchemy import delete, insert

from app import create_app
from app.database import get_db, metadata, reserveringen, tafeltoewijzingen
from app.reserveringsregels import ReserveringsRegels
from app.security import reset_rate_limits
from tests.hulp import log_in
from tests.test_toegang import TestConfig

CSS = Path(__file__).resolve().parent.parent / "static" / "css" / "huisstijl.css"
NU = datetime(2030, 1, 1, 18, 7, tzinfo=ZoneInfo("Europe/Amsterdam"))  # een dinsdag
VANDAAG = "2030-01-01"
MORGEN = "2030-01-02"
KOLOMMEN = ("kol-tijd", "kol-naam", "kol-personen", "kol-tafel", "kol-telefoon")


class OverzichtPapierTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        patcher = mock.patch.object(ReserveringsRegels, "nu", lambda self: NU)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app = create_app(TestConfig)
        with self.app.app_context():
            conn = get_db()
            metadata.create_all(conn)
            conn.commit()
            with conn.begin():  # de in-memory database wordt gedeeld tussen tests
                conn.execute(delete(tafeltoewijzingen))
                conn.execute(delete(reserveringen))
        self.client = self.app.test_client()
        log_in(self.app, self.client, naam="anna", rol="medewerker")

    def reservering(self, naam="Siti Rahma", tijd="18:00", datum=VANDAAG, aantal=2,
                    telefoon="0612345678", email="siti@example.com"):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id="een", naam=naam, email=email, telefoon=telefoon, datum=datum, tijd=tijd, aantal=aantal))

    def pagina(self, datum=VANDAAG):
        return self.client.get(f"/overzicht?datum={datum}").get_data(as_text=True)

    def eerste_rij(self, html):
        """De eerste reserveringsregel uit de lijst: van de rij zelf tot de sluitende div van die regel."""
        return html.split('<div class="res ')[1].split('<div class="res ')[0].split("\n    </div>")[0]

    def test_1_de_koprij_heeft_de_vijf_koppen_in_volgorde(self):
        self.reservering()
        html = self.pagina()
        self.assertIn('<div class="kolomkoppen">', html)
        koprij = html.split('<div class="kolomkoppen">')[1].split("</div>")[0]
        self.assertEqual(re.findall(r"<span>(.*?)</span>", koprij), ["Tijd", "Naam", "Personen", "Tafel", "Telefoon"])

    def test_2_een_rij_heeft_de_kolommen_in_volgorde(self):
        self.reservering()
        rij = self.eerste_rij(self.pagina())
        plekken = []
        for kolom in KOLOMMEN:
            self.assertIn(kolom, rij, f"kolom {kolom} ontbreekt")  # elke kolom staat er ook echt
            plekken.append(rij.index(kolom))
        self.assertEqual(plekken, sorted(plekken))

    def test_3_op_een_andere_dag_staat_de_tijd_ook_in_de_rij(self):
        self.reservering(datum=MORGEN, tijd="19:30")
        rij = self.eerste_rij(self.pagina(MORGEN))
        tijdkolom = rij.split('<span class="kol-tijd">', 1)[1].split("</span>", 1)[0]
        self.assertEqual(tijdkolom, "19:30")
        self.assertNotIn("rijtijd", rij)  # de tijd staat hier niet tussen de naam

    def test_4_het_telefoonnummer_staat_als_tel_link_in_kol_telefoon(self):
        self.reservering(telefoon="0612345678")
        rij = self.eerste_rij(self.pagina())
        telefoonkolom = rij.split('<span class="kol-telefoon">', 1)[1].split("</span>", 1)[0]
        self.assertEqual(telefoonkolom, '<a class="tel" href="tel:0612345678">0612345678</a>')

    def test_5_de_css_verbergt_de_koprij_op_een_telefoon(self):
        css = CSS.read_text(encoding="utf-8")
        blok = css[css.index("@media (max-width: 700px)",
                             css.index("/* Personeel op een telefoon, tijdens de service")):]
        self.assertTrue(blok.startswith("@media (max-width: 700px) {"))
        self.assertIn(".kolomkoppen { display: none; }", blok)

    def test_6_een_naam_met_script_wordt_ge_escaped_in_kol_naam(self):
        self.reservering(naam="<script>alert(1)</script>")
        rij = self.eerste_rij(self.pagina())
        naamkolom = rij.split('<div class="wie kol-naam">', 1)[1]
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", naamkolom)
        self.assertNotIn("<script>", rij)


if __name__ == "__main__":
    unittest.main()
