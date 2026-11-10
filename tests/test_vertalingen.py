"""
Vertalingen (deel 6): elke Nederlandse zin die de app via t() of vertaal() toont, staat in
vertalingen/en.toml en vertalingen/id.toml, met dezelfde plaatshouders.
"""
import ast
import re
import unittest
from pathlib import Path

from app.taal import ALLE_TALEN, BRONTAAL, laad_vertalingen, plaatshouders

PROJECTMAP = Path(__file__).resolve().parent.parent
# t("...") of t('...') in een template (of _t(...) waar t een andere betekenis heeft);
# de zin zelf mag geen eigen aanhalingsteken van dat soort bevatten.
T_IN_TEMPLATE = re.compile(r"""\b_?t\(\s*(["'])((?:(?!\1).)*?)\1""", re.S)
VERTAAL_FUNCTIES = {"t", "vertaal", "RegelFout"}


def zinnen_in_templates():
    zinnen = {}
    for pad in sorted((PROJECTMAP / "templates").glob("*.html")):
        for match in T_IN_TEMPLATE.finditer(pad.read_text(encoding="utf-8")):
            zinnen.setdefault(match.group(2), pad.name)
    return zinnen


def zinnen_in_code():
    """Letterlijke zinnen in t(...), vertaal(...) en RegelFout(...) in app/ (Python voegt "a" "b" zelf samen)."""
    zinnen = {}
    for pad in sorted((PROJECTMAP / "app").rglob("*.py")):
        boom = ast.parse(pad.read_text(encoding="utf-8"))
        for knoop in ast.walk(boom):
            if not (isinstance(knoop, ast.Call) and knoop.args):
                continue
            naam = getattr(knoop.func, "id", None) or getattr(knoop.func, "attr", None)
            eerste = knoop.args[0]
            if naam in VERTAAL_FUNCTIES and isinstance(eerste, ast.Constant) and isinstance(eerste.value, str):
                zinnen.setdefault(eerste.value, pad.name)
    return zinnen


def zinnen_via_constanten():
    """Zinnen die als constante of variabele bij t() aankomen."""
    from app import schemas
    from app.database import (
        DubbeleReserveringFout, GeenReserveringFout, KinderstoelVolFout, LaatsteBeheerderFout, OnbekendeTafelFout,
        TafelBezetFout,
    )
    from app.routes import accounts, invoeren, web
    return {zin: "constante" for zin in (
        schemas.TELEFOON_MELDING, schemas.NAAM_MELDING, schemas.OPMERKING_MELDING, schemas.ALLERGIE_MELDING,
        web.TOESTEMMING_MELDING, "Datavalidatie mislukt",
        DubbeleReserveringFout.SJABLOON, KinderstoelVolFout.bericht,
        GeenReserveringFout.bericht, LaatsteBeheerderFout.bericht, OnbekendeTafelFout.SJABLOON, TafelBezetFout.SJABLOON,
        accounts.DATABASE_DRUK, *web.STATUS_BERICHTEN.values(), *invoeren.VELDNAMEN.values(),
    )}


def alle_zinnen():
    return {**zinnen_via_constanten(), **zinnen_in_code(), **zinnen_in_templates()}


class VertalingenTests(unittest.TestCase):
    def setUp(self):
        self.vertalingen = laad_vertalingen()

    def test_elke_zin_is_vertaald(self):
        zinnen = alle_zinnen()
        self.assertGreater(len(zinnen), 50)
        for taal in ALLE_TALEN:
            if taal == BRONTAAL:
                continue
            ontbreekt = sorted(f"{bron}: {zin}" for zin, bron in zinnen.items() if zin not in self.vertalingen[taal])
            self.assertEqual(ontbreekt, [], f"Ontbreekt in vertalingen/{taal}.toml")

    def test_geen_oude_vertalingen(self):
        zinnen = alle_zinnen()
        for taal, tabel in self.vertalingen.items():
            self.assertEqual(sorted(set(tabel) - set(zinnen)), [], f"Niet meer gebruikt in vertalingen/{taal}.toml")

    def test_talen_hebben_dezelfde_zinnen(self):
        self.assertEqual(set(self.vertalingen["en"]), set(self.vertalingen["id"]))

    def test_plaatshouders_gelijk(self):
        for taal, tabel in self.vertalingen.items():
            for bron, doel in tabel.items():
                self.assertEqual(plaatshouders(bron), plaatshouders(doel), f"{taal}: {bron}")

    def test_tijden_als_24_uur(self):
        for taal, tabel in self.vertalingen.items():
            for doel in tabel.values():
                self.assertNotRegex(doel, r"\b\d{1,2}(:\d{2})?\s?(am|pm|a\.m\.|p\.m\.)", f"{taal}: {doel}")


if __name__ == "__main__":
    unittest.main()
