"""Het overzicht op een telefoon tijdens de service (fase 1): tellerstrook, grote statusknop rechts, Mail niet op de rij."""
import re
import unittest
from pathlib import Path

from sqlalchemy import delete, insert

from app import create_app
from app.database import STATUSSEN, get_db, metadata, reserveringen, tafeltoewijzingen
from app.security import reset_rate_limits
from tests.hulp import log_in
from tests.test_toegang import TestConfig

CSS = Path(__file__).resolve().parent.parent / "static" / "css" / "huisstijl.css"
KOP = "/* Personeel op een telefoon, tijdens de service"
DAG = "2030-01-01"  # een dinsdag


def serviceblok():
    """Het stuk van huisstijl.css met de telefoonregels van deze fase: van de kopregel tot het einde van het bestand."""
    tekst = CSS.read_text(encoding="utf-8")
    return tekst[tekst.index(KOP):]


class ServiceTelefoonTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)
        with self.app.app_context():
            conn = get_db()
            metadata.create_all(conn)
            conn.commit()
            with conn.begin():
                conn.execute(delete(tafeltoewijzingen))
                conn.execute(delete(reserveringen))
                conn.execute(insert(reserveringen).values(
                    id="een", naam="Siti Rahma", email="siti@example.com", telefoon="0612345678",
                    datum=DAG, tijd="18:00", aantal=2))
        self.client = self.app.test_client()
        log_in(self.app, self.client, naam="anna", rol="medewerker")

    def test_alleen_het_overzicht_heeft_de_tellerstrook(self):
        overzicht = self.client.get(f"/overzicht?datum={DAG}").get_data(as_text=True)
        self.assertIn('class="tellers strook"', overzicht)
        log_in(self.app, self.client, naam="kevin", rol="beheerder")
        cijfers = self.client.get("/cijfers").get_data(as_text=True)
        self.assertIn('<div class="tellers">', cijfers)  # de cijferpagina houdt haar tegels
        self.assertNotIn("strook", cijfers)

    def test_de_telefoonregels_staan_in_een_media_blok_tot_700px(self):
        blok = serviceblok()
        self.assertEqual(blok.count("@media"), 1)
        self.assertIn("@media (max-width: 700px) {", blok)
        self.assertTrue(blok.rstrip().endswith("}"))
        # Elke regel in het blok is ingesprongen: niets staat buiten de accolades van @media.
        regels = blok.split("@media (max-width: 700px) {", 1)[1].rstrip().splitlines()[1:-1]
        for regel in regels:
            self.assertTrue(regel == "" or regel.startswith("    "), regel)

    def test_statusknop_is_groot_genoeg_voor_een_vinger_en_mail_staat_niet_op_de_rij(self):
        blok = serviceblok()
        knop = re.search(r'button\[value="gearriveerd"\],\s*\.res:not\(\.zoek\) \.acties \.status button\[value="verwacht"\] \{([^}]*)\}', blok)
        self.assertIsNotNone(knop)
        hoogte = int(re.search(r"min-height: (\d+)px", knop.group(1)).group(1))
        self.assertGreaterEqual(hoogte, 44)
        self.assertIn("position: absolute; right: 0;", knop.group(1))
        self.assertIn(".res:not(.zoek) .acties .mail { display: none; }", blok)
        self.assertIn(".tellers.strook {", blok)
        self.assertIn("position: sticky; top: 0;", blok)

    def test_de_css_noemt_alleen_statussen_en_klassen_die_in_de_pagina_staan(self):
        blok = serviceblok()
        for waarde in re.findall(r'button\[value="([a-z_]+)"\]', blok):
            self.assertIn(waarde, STATUSSEN, waarde)
        # Vandaag heeft de rij een statusknop; een dag in de toekomst niet.
        with self.app.app_context():
            vandaag = self.app.config["REGELS"].nu().date().isoformat()
            conn = get_db()
            with conn.begin():
                conn.execute(insert(reserveringen).values(
                    id="nu", naam="Siti Rahma", email="siti@example.com", telefoon="0612345678",
                    datum=vandaag, tijd="18:00", aantal=2))
        html = self.client.get("/overzicht").get_data(as_text=True)
        for klasse in ("tijdkop", "res", "aantal", "wie", "tafel", "acties", "status", "mail"):
            self.assertRegex(html, rf'class="{klasse}[ "]', klasse)
        self.assertIn('class="mail" href="mailto:siti@example.com"', html)  # tablet en pc houden Mail
