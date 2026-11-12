"""Het menu van de personeelspagina's (personeel, fase 1): op een telefoon alleen de hoofdpagina's, de rest onder Menu."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.security import reset_rate_limits
from tests.hulp import log_in, scripts
from tests.test_toegang import TestConfig


class PersoneelsmenuTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)

    def pagina(self, rol, pad="/overzicht", taal="nl"):
        client = self.app.test_client()
        log_in(self.app, client, naam="kevin" if rol == "beheerder" else "anna", rol=rol)
        return client.get(pad, headers={"Accept-Language": taal}).get_data(as_text=True)

    def menu(self, html):
        """Alleen het stuk tussen id="menu" en het einde van het menu."""
        begin = html.index('<div class="menu-lijst" id="menu">')
        return html[begin:html.index("</nav>", html.index("Uitloggen", begin))]

    def test_menuknop_staat_dicht_en_wijst_naar_het_menu(self):
        html = self.pagina("beheerder")
        self.assertIn('id="menuknop" aria-expanded="false" aria-controls="menu"', html)
        self.assertIn(">Menu</button>", html)

    def test_hoofdpagina_s_staan_buiten_het_menu(self):
        html = self.pagina("beheerder")
        menu_begin = html.index('<div class="menu-lijst"')
        for tekst in ('href="/overzicht?', 'href="/plattegrond?'):  # met ?datum=, dus zonder sluitaanhalingsteken
            self.assertLess(html.index(tekst, html.index('class="tabs"')), menu_begin, tekst)

    def test_beheerder_heeft_beheer_formulier_account_en_uitloggen_in_het_menu(self):
        menu = self.menu(self.pagina("beheerder"))
        for tekst in ('href="/accounts"', 'href="/cijfers"', 'href="/"', 'href="/account"', 'action="/logout"'):
            self.assertIn(tekst, menu)

    def test_medewerker_ziet_geen_beheerpagina_s(self):
        menu = self.menu(self.pagina("medewerker"))
        self.assertNotIn('href="/accounts"', menu)
        self.assertNotIn('href="/cijfers"', menu)
        self.assertIn('action="/logout"', menu)
        self.assertIn('href="/account"', menu)

    def test_taalkeuze_staat_in_het_menu(self):
        html = self.pagina("medewerker")
        menu = self.menu(html)
        for code in ("en", "nl", "id"):
            self.assertIn(f'href="/taal/{code}?terug=', menu)
        self.assertEqual(html.count('class="talen"'), 1)

    def test_menu_op_elke_personeelspagina(self):
        for pad in ("/overzicht", "/plattegrond", "/cijfers", "/accounts", "/account", "/reservering/nieuw"):
            self.assertIn('id="menuknop"', self.pagina("beheerder", pad), pad)

    def test_menu_volgt_de_taal_van_het_account(self):
        # Personeel ziet de taal van het eigen account (kolom taal), niet die van de browser.
        client = self.app.test_client()
        log_in(self.app, client, naam="anna", rol="medewerker")
        html = client.get("/overzicht").get_data(as_text=True)
        self.assertIn(">Menu</button>", html)
        self.assertIn("Uitloggen", html)

    def test_menuknop_is_alleen_op_een_telefoon_zichtbaar(self):
        # De knop heeft ook de klasse pil, die display aanzet; de regel moet dus specifieker zijn (nav.staf .menuknop).
        css = (Path(__file__).resolve().parent.parent / "static" / "css" / "huisstijl.css").read_text(encoding="utf-8")
        self.assertIn("nav.staf .menuknop { display: none;", css)
        self.assertIn("nav.staf .menuknop { display: inline-flex;", css)
        self.assertLess(css.index("nav.staf .menuknop { display: none;"), css.index("max-width: 700px"))

    @unittest.skipUnless(shutil.which("node"), "node is niet geïnstalleerd")
    def test_menuscript_is_geldig_javascript(self):
        html = self.pagina("beheerder")
        script = next(s for s in scripts(html) if "menuknop" in s)
        with tempfile.TemporaryDirectory() as map_:
            pad = Path(map_) / "menu.js"
            pad.write_text(script, encoding="utf-8")
            resultaat = subprocess.run(["node", "--check", str(pad)], capture_output=True, text=True)
        self.assertEqual(resultaat.returncode, 0, resultaat.stderr)


if __name__ == "__main__":
    unittest.main()
