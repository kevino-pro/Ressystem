"""Geen inline handlers (onclick=, onchange=, onsubmit=, javascript:) in de HTML: voorwaarde voor een strikte Content-Security-Policy."""
import re
import unittest
from pathlib import Path

from app import create_app
from app.security import reset_rate_limits
from tests.hulp import log_in
from tests.test_toegang import TestConfig

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
# Een attribuut dat met "on" begint, binnen een HTML-tag: onclick="...", onsubmit='...'.
HANDLER = re.compile(r"<[a-zA-Z][^<>]*\son[a-z]+\s*=", re.S)


class GeenInlineHandlersTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        log_in(self.app, self.client)

    def test_geen_handler_of_javascript_adres_in_een_template(self):
        bestanden = sorted(TEMPLATES.glob("*.html"))
        self.assertTrue(bestanden)
        for bestand in bestanden:
            tekst = bestand.read_text(encoding="utf-8")
            self.assertIsNone(HANDLER.search(tekst), bestand.name)
            self.assertNotIn("javascript:", tekst, bestand.name)

    def test_datumveld_verstuurt_via_het_script(self):
        for pad in ("/overzicht", "/plattegrond"):
            html = self.client.get(pad).get_data(as_text=True)
            self.assertIn('name="datum"', html, pad)
            self.assertIn("data-verstuur-bij-keuze>", html, pad)
            self.assertIn("input[data-verstuur-bij-keuze]", html, pad)
            self.assertIn("<noscript>", html, pad)  # zonder JavaScript blijft de knop Tonen

    def test_het_script_staat_op_elke_personeelspagina(self):
        for pad in ("/overzicht", "/plattegrond", "/cijfers", "/accounts", "/account", "/reservering/nieuw", "/zoeken"):
            html = self.client.get(pad).get_data(as_text=True)
            self.assertIn("confirm(bericht)", html, pad)
