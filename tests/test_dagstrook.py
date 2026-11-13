"""Reserveerformulier: de dagen boven de tijden (reserveringspagina, fase 2)."""
import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from app import create_app
from app.reserveringsregels import ReserveringsRegels
from tests.test_toegang import TestConfig  # restaurants/wpl.toml: di t/m zo 12:00 tot 20:00, maandag dicht, 60 min vooruit

AMS = ZoneInfo("Europe/Amsterdam")
DINSDAG = "2030-01-01"
WOENSDAG = "2030-01-02"


class DagstrookTests(unittest.TestCase):
    def pagina(self, nu, taal="nl"):
        patcher = mock.patch.object(ReserveringsRegels, "nu", lambda self: nu)
        patcher.start()
        self.addCleanup(patcher.stop)
        client = create_app(TestConfig).test_client()
        return client.get("/", headers={"Accept-Language": taal}).get_data(as_text=True)

    def knop(self, datum, html):
        """De openingstag van de dagknop met deze datum, bijvoorbeeld 'aria-pressed="false" disabled'."""
        begin = html.index(f'data-datum="{datum}"')
        return html[begin:html.index(">", begin)]

    def test_vandaag_en_morgen_als_label(self):
        html = self.pagina(datetime(2030, 1, 1, 10, 0, tzinfo=AMS))
        self.assertIn("<small>Vandaag</small><b>1</b>", html)
        self.assertIn("<small>Morgen</small><b>2</b>", html)
        self.assertIn("<small>vr</small><b>4</b>", html)  # daarna de weekdag

    def test_labels_in_alle_talen(self):
        nu = datetime(2030, 1, 1, 10, 0, tzinfo=AMS)
        for taal, (vandaag, morgen) in {"en": ("Today", "Tomorrow"), "id": ("Hari ini", "Besok")}.items():
            html = self.pagina(nu, taal)
            self.assertTrue(f"<small>{vandaag}</small><b>1</b>" in html, taal)
            self.assertTrue(f"<small>{morgen}</small><b>2</b>" in html, taal)

    def test_vandaag_is_open_overdag(self):
        html = self.pagina(datetime(2030, 1, 1, 10, 0, tzinfo=AMS))
        self.assertNotIn("disabled", self.knop(DINSDAG, html))

    def test_vandaag_dicht_als_er_niets_meer_kan(self):
        html = self.pagina(datetime(2030, 1, 1, 21, 0, tzinfo=AMS))
        self.assertIn("disabled", self.knop(DINSDAG, html))
        self.assertNotIn("disabled", self.knop(WOENSDAG, html))

    def test_grens_een_uur_voor_de_laatste_tijd(self):
        # De laatste tijd is 20:00 en je moet 60 minuten van tevoren boeken.
        open_ = self.pagina(datetime(2030, 1, 1, 18, 59, tzinfo=AMS))
        dicht = self.pagina(datetime(2030, 1, 1, 19, 1, tzinfo=AMS))
        self.assertNotIn("disabled", self.knop(DINSDAG, open_))
        self.assertIn("disabled", self.knop(DINSDAG, dicht))

    def test_maandag_blijft_dicht(self):
        html = self.pagina(datetime(2030, 1, 5, 10, 0, tzinfo=AMS))  # zaterdag; maandag 7 januari valt in de strook
        self.assertIn("disabled", self.knop("2030-01-07", html))

    def test_andere_dag_met_verborgen_datumveld(self):
        html = self.pagina(datetime(2030, 1, 1, 10, 0, tzinfo=AMS))
        self.assertIn('id="andere"', html)
        self.assertIn('id="datum" class="datumveld"', html)
        self.assertIn('class="andere-wrap"', html)
        # showPicker alleen als hulp voor de muis; op iPhone werkt het niet, daar ligt het veld zelf over de knop.
        self.assertEqual(html.count("showPicker"), 2)
        self.assertIn("!window.matchMedia('(pointer: fine)').matches) { return; }", html)
        self.assertIn('min="2030-01-01"', html)
        self.assertNotIn("innerHTML", html)
        self.assertNotIn('class="keuzes dagen"', html)


if __name__ == "__main__":
    unittest.main()
