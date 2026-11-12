"""
Template-kit, fase 2: installaties.json noemt per installatie (vestiging of restaurant) de NAMEN van de
GitHub-variabelen en het secret; de geplande taken draaien voor elke installatie.
"""
import json
import re
import unittest
from pathlib import Path

from app.controle import FOUT, controleer

PROJECTMAP = Path(__file__).resolve().parent.parent
INSTALLATIES = PROJECTMAP / "installaties.json"
WORKFLOWS = PROJECTMAP / ".github" / "workflows"
VELDEN = {"naam", "restaurantbestand", "app_url", "health_url", "service_id", "beheer_sleutel"}
GITHUB_NAAM = re.compile(r"[A-Z][A-Z0-9_]*")


class InstallatiesTests(unittest.TestCase):
    def setUp(self):
        self.lijst = json.loads(INSTALLATIES.read_text(encoding="utf-8"))

    def test_vorm(self):
        self.assertIsInstance(self.lijst, list)
        self.assertGreaterEqual(len(self.lijst), 1)
        for installatie in self.lijst:
            with self.subTest(installatie=installatie.get("naam")):
                self.assertEqual(set(installatie), VELDEN)
                self.assertRegex(installatie["naam"], r"^[a-z0-9]+(-[a-z0-9]+)*$")
                for veld in VELDEN - {"naam", "restaurantbestand"}:
                    self.assertRegex(installatie[veld], GITHUB_NAAM, veld)

    def test_alleen_namen_geen_waarden(self):
        tekst = INSTALLATIES.read_text(encoding="utf-8")
        for verboden in ("http", "srv-", "onrender.com", "neon.tech", "@"):
            with self.subTest(verboden=verboden):
                self.assertNotIn(verboden, tekst)

    def test_elke_installatie_eigen_namen(self):
        for veld in VELDEN - {"restaurantbestand"}:
            waarden = [i[veld] for i in self.lijst]
            with self.subTest(veld=veld):
                self.assertEqual(len(waarden), len(set(waarden)))

    def test_restaurantbestand_klopt(self):
        for installatie in self.lijst:
            pad = PROJECTMAP / installatie["restaurantbestand"]
            with self.subTest(installatie=installatie["naam"]):
                self.assertTrue(pad.is_file(), pad)
                self.assertEqual(pad.parent.name, "restaurants")
                self.assertNotIn(FOUT, [status for _, status, _ in controleer(pad)])

    def test_den_haag_gebruikt_de_bestaande_namen(self):
        """Zo hoeft er voor Den Haag in GitHub niets te veranderen."""
        den_haag = next(i for i in self.lijst if i["restaurantbestand"] == "restaurants/wpl.toml")
        self.assertEqual((den_haag["app_url"], den_haag["health_url"], den_haag["service_id"], den_haag["beheer_sleutel"]),
                         ("RENDER_APP_URL", "RENDER_HEALTH_URL", "RENDER_SERVICE_ID", "BEHEER_API_KEY"))


class WorkflowTests(unittest.TestCase):
    def tekst(self, naam):
        return (WORKFLOWS / naam).read_text(encoding="utf-8")

    def test_matrix_per_installatie(self):
        for naam in ("opschonen.yml", "herinneringen.yml", "render-deployment-health.yml"):
            tekst = self.tekst(naam)
            with self.subTest(workflow=naam):
                self.assertIn("jq -c . installaties.json", tekst)
                self.assertIn("fromJSON(needs.lijst.outputs.installaties)", tekst)
                self.assertIn("fail-fast: false", tekst)
                self.assertNotIn("vars.RENDER_", tekst)

    def test_geheime_sleutel_per_installatie(self):
        for naam in ("opschonen.yml", "herinneringen.yml"):
            with self.subTest(workflow=naam):
                self.assertIn("${{ secrets[matrix.installatie.beheer_sleutel] }}", self.tekst(naam))
                self.assertNotIn("secrets.BEHEER_API_KEY", self.tekst(naam))

    def test_keep_alive_een_job_en_geen_secrets(self):
        tekst = self.tekst("keep-alive.yml")
        self.assertIn("jq -r '.[].health_url' installaties.json", tekst)
        self.assertNotIn("strategy:", tekst)
        self.assertNotIn("${{ secrets", tekst)

    def test_nergens_alle_secrets_tegelijk(self):
        for pad in sorted(WORKFLOWS.glob("*.yml")):
            with self.subTest(workflow=pad.name):
                self.assertNotIn("toJSON(secrets)", pad.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
