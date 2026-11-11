"""Het reserveringsoverzicht op een telefoon (personeel, fase 2): de opmaak hangt aan klassen, de inhoud blijft gelijk."""
import unittest

from sqlalchemy import delete, insert

from app import create_app
from app.database import get_db, metadata, reserveringen, tafeltoewijzingen
from app.security import reset_rate_limits
from tests.hulp import log_in
from tests.test_toegang import TestConfig

DAG = "2030-01-01"  # een dinsdag


class OverzichtTelefoonTests(unittest.TestCase):
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
                    id="beide", naam="Siti Rahma", email="siti@example.com", telefoon="0612345678",
                    datum=DAG, tijd="18:00", aantal=2))
                conn.execute(insert(reserveringen).values(
                    id="alleen-tel", naam="Budi Santoso", email="", telefoon="0687654321",
                    datum=DAG, tijd="19:00", aantal=4, bron="telefoon"))
        self.client = self.app.test_client()
        log_in(self.app, self.client, naam="anna", rol="medewerker")

    def pagina(self):
        return self.client.get(f"/overzicht?datum={DAG}").get_data(as_text=True)

    def test_telefoon_en_mail_hebben_klassen_voor_de_telefoonopmaak(self):
        html = self.pagina()
        for tekst in ('class="tel" href="tel:0612345678"', 'class="mailtekst" href="mailto:siti@example.com"',
                      '<span class="scheiding"> · </span>', 'class="bel" href="tel:0612345678"',
                      'class="mail" href="mailto:siti@example.com"'):
            self.assertIn(tekst, html)

    def test_de_inhoud_blijft_compleet_voor_tablet_en_pc(self):
        html = self.pagina()
        self.assertIn("siti@example.com", html)
        self.assertIn(">Bel</a>", html)
        self.assertIn(">Mail</a>", html)

    def test_zonder_mailadres_geen_mailtekst_en_geen_scheiding(self):
        rest = self.pagina().split("Budi Santoso")[1]  # Budi staat als laatste op de dag
        wie = rest.split('<div class="acties">')[0]
        self.assertNotIn("mailtekst", wie)
        self.assertNotIn("scheiding", wie)
        self.assertIn('class="tel" href="tel:0687654321"', wie)
        self.assertNotIn('class="mail"', rest)  # geen Mail-knop zonder adres

    def test_dagknoppen_hebben_een_label_en_de_tekst_verdwijnt_alleen_op_telefoon(self):
        html = self.pagina()
        self.assertIn('aria-label="Vorige dag">‹<span class="alleen-breed"> Vorige dag</span>', html)
        self.assertIn('aria-label="Volgende dag"><span class="alleen-breed">Volgende dag </span>›', html)

    def test_alle_reserveringen_en_tellers_staan_er_nog(self):
        html = self.pagina()
        self.assertIn("Siti Rahma", html)
        self.assertIn("Budi Santoso", html)
        self.assertIn("<small>Reserveringen</small><b>2</b>", html)
        self.assertIn("<small>Gasten</small><b>6</b>", html)


if __name__ == "__main__":
    unittest.main()
