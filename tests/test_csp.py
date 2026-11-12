"""Content-Security-Policy: scripts draaien alleen met de nonce van het verzoek; alles komt van de eigen site."""
import re
import unittest
from pathlib import Path

from app import create_app
from app.security import reset_rate_limits
from tests.hulp import log_in
from tests.test_toegang import TestConfig

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
VAST = ("default-src 'self'", "style-src 'self' 'unsafe-inline'", "img-src 'self' data:", "object-src 'none'",
        "base-uri 'self'", "form-action 'self'", "frame-ancestors 'none'")


class CspTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def beleid(self, antwoord):
        """De kopregel als lijst van richtlijnen."""
        return antwoord.headers["Content-Security-Policy"].split("; ")

    def nonce(self, antwoord):
        script = next(r for r in self.beleid(antwoord) if r.startswith("script-src "))
        gevonden = re.fullmatch(r"script-src 'self' 'nonce-([A-Za-z0-9_-]{16,})'", script)
        self.assertIsNotNone(gevonden, script)
        return gevonden.group(1)

    def test_vaste_richtlijnen_op_een_pagina_en_op_de_api(self):
        for pad in ("/", "/health", "/bestaat-niet"):
            beleid = self.beleid(self.client.get(pad))
            for richtlijn in VAST:
                self.assertIn(richtlijn, beleid, f"{pad}: {richtlijn}")
            self.assertEqual(len(beleid), len(VAST) + 1, pad)  # de vaste richtlijnen plus script-src

    def test_zonder_script_geen_nonce_en_nergens_unsafe_inline_voor_scripts(self):
        beleid = self.beleid(self.client.get("/health"))
        self.assertIn("script-src 'self'", beleid)
        for pad in ("/", "/health"):
            script = next(r for r in self.beleid(self.client.get(pad)) if r.startswith("script-src "))
            self.assertNotIn("unsafe", script, pad)

    def test_elk_script_op_gast_en_personeelspagina_heeft_de_nonce_van_het_verzoek(self):
        log_in(self.app, self.client)
        for pad in ("/", "/login", "/overzicht", "/plattegrond", "/reservering/nieuw", "/cijfers"):
            antwoord = self.client.get(pad)
            self.assertEqual(antwoord.status_code, 200, pad)
            html = antwoord.get_data(as_text=True)
            tags = re.findall(r"<script[^>]*>", html)
            self.assertTrue(tags, pad)
            for tag in tags:
                self.assertEqual(tag, f'<script nonce="{self.nonce(antwoord)}">', pad)

    def test_nonce_verschilt_per_verzoek(self):
        self.assertNotEqual(self.nonce(self.client.get("/")), self.nonce(self.client.get("/")))

    def test_elk_script_in_een_template_vraagt_de_nonce(self):
        for bestand in sorted(TEMPLATES.glob("*.html")):
            for tag in re.findall(r"<script[^>]*>", bestand.read_text(encoding="utf-8")):
                self.assertEqual(tag, '<script nonce="{{ csp_nonce() }}">', bestand.name)
