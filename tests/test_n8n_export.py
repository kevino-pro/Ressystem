"""
Template-kit, fase 3: een export van de n8n-workflow in n8n/ mag geen sleutel, adres van een installatie of
connection string bevatten. Zonder export (alleen n8n/README.md) is er niets te controleren.
"""
import json
import re
import unittest
from pathlib import Path

N8N_MAP = Path(__file__).resolve().parent.parent / "n8n"

VERBODEN = {
    "Anthropic-sleutel": re.compile(r"sk-ant-"),
    "Resend-sleutel": re.compile(r"\bre_[A-Za-z0-9]{8,}"),
    "connection string": re.compile(r"postgres(ql)?://", re.I),
    "Render-adres": re.compile(r"onrender\.com", re.I),
    "Neon-adres": re.compile(r"neon\.tech", re.I),
}
TOEGESTAAN_SLEUTEL = re.compile(r"^(VUL_IN|=\{\{.*\}\})$", re.S)


def kopjes(waarde):
    """Alle {name, value}-paren in de export (zo slaat n8n headers en parameters op)."""
    if isinstance(waarde, dict):
        if isinstance(waarde.get("name"), str) and "value" in waarde:
            yield waarde["name"], waarde["value"]
        for kind in waarde.values():
            yield from kopjes(kind)
    elif isinstance(waarde, list):
        for kind in waarde:
            yield from kopjes(kind)


def controleer_export(tekst):
    """Lijst met problemen in een export; leeg als hij in de repo mag."""
    try:
        data = json.loads(tekst)
    except json.JSONDecodeError:
        return ["geen geldige JSON"]
    problemen = [naam for naam, patroon in VERBODEN.items() if patroon.search(tekst)]
    for naam, waarde in kopjes(data):
        if naam.lower() == "x-api-key" and not (isinstance(waarde, str) and TOEGESTAAN_SLEUTEL.match(waarde)):
            problemen.append("waarde van X-API-Key")
    return problemen


class ExportTests(unittest.TestCase):
    def test_uitleg_aanwezig(self):
        self.assertTrue((N8N_MAP / "README.md").is_file())

    def test_exports_zijn_opgeschoond(self):
        for pad in sorted(N8N_MAP.glob("*.json")):
            with self.subTest(bestand=pad.name):
                self.assertEqual(controleer_export(pad.read_text(encoding="utf-8")), [])


class ControleTests(unittest.TestCase):
    """De controle zelf, met verzonnen voorbeelden (geen echte export)."""

    def export(self, sleutel="VUL_IN", url="https://VUL_IN/api/v1/ai-reservering"):
        return json.dumps({"nodes": [{"type": "n8n-nodes-base.httpRequest", "parameters": {
            "url": url, "headerParameters": {"parameters": [{"name": "X-API-Key", "value": sleutel}]}}}]})

    def test_opgeschoond_is_goed(self):
        self.assertEqual(controleer_export(self.export()), [])
        self.assertEqual(controleer_export(self.export(sleutel="={{ $env.WPL_API_KEY }}")), [])

    def test_sleutel_in_header(self):
        self.assertEqual(controleer_export(self.export(sleutel="abc123geheim")), ["waarde van X-API-Key"])

    def test_adres_van_een_installatie(self):
        self.assertIn("Render-adres", controleer_export(self.export(url="https://wpl.onrender.com/api/v1/ai-reservering")))

    def test_sleutels_en_connection_string(self):
        for tekst, soort in (("sk-ant-api03-x", "Anthropic-sleutel"), ("re_AbCdEfGh123", "Resend-sleutel"),
                             ("postgresql://u:p@host/db", "connection string"), ("ep-x.eu-central-1.aws.neon.tech", "Neon-adres")):
            with self.subTest(soort=soort):
                self.assertIn(soort, controleer_export(json.dumps({"notitie": tekst})))

    def test_geen_json(self):
        self.assertEqual(controleer_export("{"), ["geen geldige JSON"])


if __name__ == "__main__":
    unittest.main()
