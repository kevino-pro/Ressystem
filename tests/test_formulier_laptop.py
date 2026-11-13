"""Het formulier op een laptop: de keuzelijst is leesbaar en "Andere dag" opent de kalender ook met een muis."""
import re
import unittest
from pathlib import Path

from app import create_app
from tests.hulp import scripts
from tests.test_formulier import TestConfig
from tests.test_gast_wijzigen import Basis

CSS = Path(__file__).resolve().parent.parent / "static" / "css" / "huisstijl.css"


def klik_op_datumveld(html):
    """Het stuk script dat op een klik op het datumveld reageert."""
    script = next(s for s in scripts(html) if "datumVeld" in s)
    gevonden = re.search(r"datumVeld\.addEventListener\('click', function \(\) \{(.*?)\n    \}\);", script, re.S)
    return gevonden.group(1) if gevonden else None


class KeuzelijstTests(unittest.TestCase):
    def test_opties_hebben_een_donkere_achtergrond_en_lichte_letters(self):
        css = CSS.read_text(encoding="utf-8")
        regel = re.search(r"^select option \{([^}]*)\}", css, re.M)
        self.assertIsNotNone(regel)
        self.assertIn("background: #1d1813;", regel.group(1))
        self.assertIn("color: var(--tekst);", regel.group(1))

    def test_de_regel_geldt_op_elk_schermformaat(self):
        css = CSS.read_text(encoding="utf-8")
        self.assertLess(css.index("select option {"), css.index("@media"))


class AndereDagTests(unittest.TestCase):
    def controleer(self, html):
        self.assertIn('<input type="date" id="datum" class="datumveld"', html)
        klik = klik_op_datumveld(html)
        self.assertIsNotNone(klik)
        self.assertIn("datumVeld.showPicker()", klik)
        self.assertIn("typeof datumVeld.showPicker !== 'function'", klik)   # oude browser: niets doen
        self.assertIn("(pointer: fine)", klik)                               # alleen met een muis
        self.assertIn("try {", klik)                                         # een weigering breekt het formulier niet

    def test_reserveerformulier(self):
        client = create_app(TestConfig).test_client()
        self.controleer(client.get("/").get_data(as_text=True))


class AndereDagWijzigpaginaTests(Basis):
    def test_wijzigpagina(self):
        rid = self.voeg_toe(tijd="18:30", aantal=3)
        AndereDagTests.controleer(self, self.client.get(f"/annuleren/{rid}").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
