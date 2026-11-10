"""
Deel 7, fase 2: de geplande taak voor de herinneringen, de melding in het overzicht en de zin in de
privacyverklaring.
"""
import re
import unittest
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app import create_app
from tests.hulp import log_in
from tests.test_herinnering import Basis, GISTEREN_UTC, MORGEN, ZonderHerinneringConfig

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "herinneringen.yml"
PRIVACY_ZIN = "De dag voor je bezoek sturen we je een herinnering per e-mail"


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tekst = WORKFLOW.read_text(encoding="utf-8")

    def uren(self):
        return [int(u) for u in re.search(r"cron: '0 ([\d,]+) \* \* \*'", self.tekst).group(1).split(",")]

    def test_roept_de_route_aan_met_de_geheime_sleutel(self):
        self.assertIn("/beheer/herinneringen", self.tekst)
        self.assertIn("${{ secrets.BEHEER_API_KEY }}", self.tekst)
        self.assertIn("${{ vars.RENDER_APP_URL }}", self.tekst)
        self.assertIn("workflow_dispatch", self.tekst)

    def test_tien_uur_in_winter_en_zomer(self):
        for dag in (datetime(2026, 1, 15), datetime(2026, 7, 15)):
            lokaal = [datetime(dag.year, dag.month, dag.day, uur, tzinfo=timezone.utc)
                      .astimezone(ZoneInfo("Europe/Amsterdam")).hour for uur in self.uren()]
            with self.subTest(dag=dag.date()):
                self.assertIn(10, lokaal)
                self.assertTrue(all(uur >= 9 for uur in lokaal))  # nooit uren te vroeg

    def test_herhaalt_beperkt_en_faalt_bij_mislukte_mail(self):
        self.assertIn("for poging in 1 2 3 4 5", self.tekst)
        self.assertIn(".resterend", self.tekst)
        self.assertRegex(self.tekst, r'\[ "\$mislukt" -eq 0 \] \|\| \{.*exit 1; \}')


class OverzichtTests(Basis):
    def html(self):
        log_in(self.app, self.client, naam="anna", rol="medewerker")
        return self.client.get(f"/overzicht?datum={MORGEN}").get_data(as_text=True)

    def test_melding_bij_herinnerde_reservering(self):
        self.voeg_toe("a", herinnering_verstuurd=datetime(2026, 11, 17, 9, 0))
        self.assertIn("Herinnering verstuurd", self.html())

    def test_geen_melding_zonder_herinnering(self):
        self.voeg_toe("a")
        self.assertNotIn("Herinnering verstuurd", self.html())

    def test_geen_melding_bij_no_show(self):
        self.voeg_toe("a", status="no_show", herinnering_verstuurd=datetime(2026, 11, 17, 9, 0))
        html = self.html()
        self.assertIn("Niet gekomen", html)
        self.assertNotIn("Herinnering verstuurd", html)

    def test_na_versturen_in_overzicht(self):
        self.voeg_toe("a", aangemaakt_op=GISTEREN_UTC)
        self.client.post("/beheer/herinneringen", headers={"X-Beheer-Key": "s" * 40})
        self.assertIn("Herinnering verstuurd", self.html())


class PrivacyTests(unittest.TestCase):
    def pagina(self, config, taal="nl"):
        return create_app(config).test_client().get("/privacy", headers={"Accept-Language": taal}).get_data(as_text=True)

    def test_herinnering_genoemd(self):
        from tests.test_herinnering import TestConfig
        self.assertIn(PRIVACY_ZIN, self.pagina(TestConfig))
        self.assertIn("The day before your visit we send you a reminder by email", self.pagina(TestConfig, "en"))

    def test_niet_genoemd_zonder_herinnering(self):
        self.assertNotIn(PRIVACY_ZIN, self.pagina(ZonderHerinneringConfig))


if __name__ == "__main__":
    unittest.main()
