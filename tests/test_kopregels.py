"""Beveiligingskopregels: elk antwoord van de app krijgt ze, ook de API, static en een foutpagina."""
import unittest

from app import create_app
from app.kopregels import KOPREGELS
from app.security import reset_rate_limits
from tests.test_toegang import TestConfig

VERWACHT = {
    "Strict-Transport-Security": "max-age=31536000",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
}


class KopregelTests(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.client = create_app(TestConfig).test_client()

    def controleer(self, pad, status):
        antwoord = self.client.get(pad)
        self.assertEqual(antwoord.status_code, status, pad)
        for naam, waarde in VERWACHT.items():
            self.assertEqual(antwoord.headers.get(naam), waarde, f"{pad}: {naam}")
        antwoord.close()  # een static-antwoord houdt anders het bestand open

    def test_de_vier_kopregels_en_hun_waarden(self):
        self.assertEqual(KOPREGELS, VERWACHT)

    def test_gastpagina_en_inlogpagina(self):
        self.controleer("/", 200)
        self.controleer("/login", 200)

    def test_health_en_static(self):
        self.controleer("/health", 200)
        self.controleer("/static/css/huisstijl.css", 200)

    def test_foutpagina_en_doorverwijzing(self):
        self.controleer("/bestaat-niet", 404)
        self.controleer("/overzicht", 302)  # niet ingelogd: naar /login
