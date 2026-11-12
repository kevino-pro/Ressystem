"""
Template-kit, fase 1: python -m app.controle restaurants/<naam>.toml controleert een restaurantbestand
vóór de eerste deploy, zonder database en zonder geheimen.
"""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from app.controle import FOUT, LET_OP, OK, controleer, main

PROJECTMAP = Path(__file__).resolve().parent.parent
WPL = PROJECTMAP / "restaurants" / "wpl.toml"
FIXTURE = PROJECTMAP / "tests" / "fixtures" / "restaurant_test.toml"


def statussen(uitslag):
    return {onderdeel: status for onderdeel, status, _ in uitslag}


class ControleTests(unittest.TestCase):
    def setUp(self):
        self.map = tempfile.TemporaryDirectory()
        self.addCleanup(self.map.cleanup)

    def variant(self, oud, nieuw):
        """Een kopie van wpl.toml met één tekst vervangen."""
        tekst = WPL.read_text(encoding="utf-8")
        self.assertIn(oud, tekst)
        pad = Path(self.map.name) / "variant.toml"
        pad.write_text(tekst.replace(oud, nieuw, 1), encoding="utf-8")
        return pad

    def test_wpl_alles_ok(self):
        uitslag = controleer(WPL)
        self.assertEqual(set(statussen(uitslag).values()), {OK})
        self.assertIn("vertalingen", statussen(uitslag))

    def test_geen_restaurantbestand_heeft_een_fout(self):
        for pad in sorted((PROJECTMAP / "restaurants").glob("*.toml")):
            with self.subTest(bestand=pad.name):
                self.assertNotIn(FOUT, statussen(controleer(pad)).values())

    def test_zonder_verplichte_secties(self):
        s = statussen(controleer(FIXTURE))
        self.assertEqual(s["[reserveringen]"], OK)
        self.assertEqual((s["[restaurant]"], s["[privacy]"]), (FOUT, FOUT))
        for sectie in ("[plattegrond]", "[huisstijl]", "[talen]", "[herinnering]"):
            with self.subTest(sectie=sectie):
                self.assertEqual(s[sectie], LET_OP)

    def test_fout_in_een_sectie_noemt_de_reden(self):
        uitslag = controleer(self.variant('email = "reserveringen@waroengpadang.nl"', 'email = "geen-adres"'))
        regel = next(r for r in uitslag if r[0] == "[restaurant]")
        self.assertEqual(regel[1], FOUT)
        self.assertIn("geen geldig e-mailadres", regel[2])
        self.assertNotIn("For further information", regel[2])

    def test_ontbrekende_foto(self):
        pad = self.variant('accentkleur = "#d9a441"', 'accentkleur = "#d9a441"\nachtergrond = "restaurants/bestaat/niet.webp"')
        self.assertEqual(statussen(controleer(pad))["[huisstijl]"], FOUT)

    def test_niet_vertaalde_verwerker(self):
        pad = self.variant('doel = "hosting van de reserveringswebsite"', 'doel = "een dienst die nergens vertaald is"')
        regel = next(r for r in controleer(pad) if r[0] == "vertalingen")
        self.assertEqual(regel[1], FOUT)
        self.assertIn("een dienst die nergens vertaald is", regel[2])

    def test_geen_geldige_toml(self):
        pad = Path(self.map.name) / "kapot.toml"
        pad.write_text("x = [", encoding="utf-8")
        self.assertEqual(controleer(pad), [("[reserveringen]", FOUT, controleer(pad)[0][2])])
        self.assertIn("geen geldige TOML", controleer(pad)[0][2])

    def test_exitcodes_en_uitvoer(self):
        for argumenten, code, tekst in (([str(WPL)], 0, "Klaar voor productie."), ([str(FIXTURE)], 1, "2 fout(en)."),
                                        ([], 2, "Gebruik:"), (["restaurants/bestaat-niet.toml"], 1, "niet gevonden")):
            uitvoer = io.StringIO()
            with self.subTest(argumenten=argumenten), contextlib.redirect_stdout(uitvoer):
                self.assertEqual(main(argumenten), code)
            self.assertIn(tekst, uitvoer.getvalue())


if __name__ == "__main__":
    unittest.main()
