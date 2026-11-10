"""Reserveringen die het personeel invoert: telefonisch (deel 4, fase 1)."""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

from sqlalchemy import create_engine, inspect, select

from app import create_app
from app.database import (
    get_db, init_db, is_zelfde_gast, reserveringen, verwerk_reservering,
)
from app.security import reset_rate_limits
from tests.hulp import log_in
from tests.test_toegang import TestConfig

PROJECTMAP = Path(__file__).resolve().parent.parent


class MetCsrfConfig(TestConfig):
    CSRF_ENABLED = True


class Basis(unittest.TestCase):
    def setUp(self):
        reset_rate_limits()
        self.app = create_app(TestConfig)  # restaurants/wpl.toml: 69 gasten, 2 kinderstoelen, maandag dicht
        self.regels = self.app.config["REGELS"]
        with self.app.app_context():
            init_db()
            conn = get_db()
            with conn.begin():
                conn.execute(reserveringen.delete())
        self.client = self.app.test_client()
        log_in(self.app, self.client, naam="anna", rol="medewerker")
        dag = self.regels.nu().date() + timedelta(days=7)
        self.dinsdag = dag + timedelta(days=(1 - dag.weekday()) % 7)
        patcher = mock.patch("app.routes.invoeren.stuur_bevestigingsmail_async")
        self.mail = patcher.start()
        self.addCleanup(patcher.stop)

    def invoeren(self, **velden):
        data = {"bron": "telefoon", "naam": "Siti Rahma", "telefoon": "0612345678",
                "datum": self.dinsdag.isoformat(), "tijd": "18:00", "aantal": "4", **velden}
        return self.client.post("/reservering/nieuw", data=data)

    def rijen(self):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                return conn.execute(select(reserveringen).order_by(reserveringen.c.tijd)).mappings().all()

    def bestaande(self, tijd, aantal, kinderstoelen=0, telefoon="0699999999"):
        with self.app.app_context():
            verwerk_reservering(get_db(), None, f"Bestaand {tijd}", "", telefoon, self.dinsdag.isoformat(), tijd,
                                aantal, zitduur_minuten=60, kinderstoelen=kinderstoelen, bron="telefoon")


class ToegangTests(Basis):
    def test_niet_ingelogd_naar_login(self):
        client = self.app.test_client()
        for antwoord in (client.get("/reservering/nieuw"), client.post("/reservering/nieuw", data={})):
            self.assertEqual(antwoord.status_code, 302)
            self.assertTrue(antwoord.headers["Location"].endswith("/login"))
        self.assertEqual(self.rijen(), [])

    def test_formulier_en_knop_in_overzicht(self):
        html = self.client.get(f"/reservering/nieuw?datum={self.dinsdag}").get_data(as_text=True)
        for veld in ("naam", "telefoon", "aantal", "datum", "tijd", "email", "kinderstoelen", "allergieen", "opmerking"):
            self.assertIn(f'name="{veld}"', html)
        self.assertIn(f'value="{self.dinsdag}"', html)
        overzicht = self.client.get(f"/overzicht?datum={self.dinsdag}").get_data(as_text=True)
        self.assertIn(f'href="/reservering/nieuw?datum={self.dinsdag}"', overzicht)

    def test_csrf_vereist(self):
        reset_rate_limits()
        app = create_app(MetCsrfConfig)
        client = app.test_client()
        log_in(app, client, naam="anna", rol="medewerker")
        data = {"naam": "Siti", "telefoon": "0612345678", "datum": self.dinsdag.isoformat(), "tijd": "18:00",
                "aantal": "2"}
        self.assertEqual(client.post("/reservering/nieuw", data=data).status_code, 400)
        html = client.get("/reservering/nieuw").get_data(as_text=True)
        data["csrf_token"] = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        self.assertEqual(client.post("/reservering/nieuw", data=data).status_code, 302)


class OpslaanTests(Basis):
    def test_telefonische_reservering_zonder_email(self):
        antwoord = self.invoeren()
        self.assertEqual(antwoord.status_code, 302)
        self.assertEqual(antwoord.headers["Location"], f"/overzicht?datum={self.dinsdag}")
        rij = self.rijen()[0]
        self.assertEqual((rij["naam"], rij["email"], rij["aantal"], rij["bron"], rij["ingevoerd_door"]),
                         ("Siti Rahma", "", 4, "telefoon", "anna"))
        self.mail.assert_not_called()
        html = self.client.get(f"/overzicht?datum={self.dinsdag}").get_data(as_text=True)
        self.assertIn("Reservering voor Siti Rahma om 18:00 (4 p.) is opgeslagen.", html)
        self.assertIn("Telefonisch · anna", html)
        self.assertNotIn('href="mailto:"', html)

    def test_met_email_krijgt_de_gast_een_mail(self):
        self.invoeren(email="siti@example.com")
        self.mail.assert_called_once()
        self.assertEqual(self.mail.call_args.kwargs["ontvanger_email"], "siti@example.com")
        self.assertIn("bevestigingsmail", self.client.get(f"/overzicht?datum={self.dinsdag}").get_data(as_text=True))

    def test_buiten_de_online_regels_mag(self):
        antwoord = self.invoeren(aantal="20", tijd="21:15")
        self.assertEqual(antwoord.status_code, 302)
        self.assertEqual((self.rijen()[0]["aantal"], self.rijen()[0]["tijd"]), (20, "21:15"))

    def test_extra_velden(self):
        self.invoeren(kinderstoelen="1", opmerking="  Bij het raam  ", allergieen="pinda",
                      allergie_toestemming="1")
        rij = self.rijen()[0]
        self.assertEqual((rij["kinderstoelen"], rij["opmerking"], rij["allergieen"]), (1, "Bij het raam", "pinda"))

    def test_online_reservering_blijft_bron_online(self):
        with self.app.app_context():
            verwerk_reservering(get_db(), 69, "Eva", "eva@example.com", "0611111111", self.dinsdag.isoformat(),
                                "18:00", 2, zitduur_minuten=60)
        rij = self.rijen()[0]
        self.assertEqual((rij["bron"], rij["ingevoerd_door"]), ("online", None))
        self.assertNotIn("Telefonisch", self.client.get(f"/overzicht?datum={self.dinsdag}").get_data(as_text=True))


class WaarschuwingTests(Basis):
    def test_te_vol_eerst_waarschuwing_dan_toch_opslaan(self):
        self.bestaande("19:00", 60)
        antwoord = self.invoeren(tijd="19:00", aantal="15", telefoon="0611111111")
        self.assertEqual(antwoord.status_code, 200)
        html = antwoord.get_data(as_text=True)
        self.assertIn("Rond 19:00 zitten er dan 75 gasten tegelijk; het maximum is 69.", html)
        self.assertIn('name="bevestigd" value="1"', html)
        self.assertEqual(len(self.rijen()), 1)
        antwoord = self.invoeren(tijd="19:00", aantal="15", telefoon="0611111111", bevestigd="1")
        self.assertEqual(antwoord.status_code, 302)
        self.assertEqual(len(self.rijen()), 2)

    def test_overlap_telt_over_de_zitduur(self):
        self.bestaande("18:30", 60)
        self.assertIn("gasten tegelijk", self.invoeren(tijd="18:00", aantal="10").get_data(as_text=True))
        self.assertEqual(self.invoeren(tijd="17:30", aantal="10").status_code, 302)

    def test_kinderstoelen_op(self):
        self.bestaande("18:00", 4, kinderstoelen=2)
        html = self.invoeren(kinderstoelen="1").get_data(as_text=True)
        self.assertIn("Er zijn dan 3 kinderstoelen nodig; het restaurant heeft er 2.", html)
        self.assertEqual(len(self.rijen()), 1)

    def test_gesloten_dag(self):
        maandag = self.dinsdag - timedelta(days=1)
        html = self.invoeren(datum=maandag.isoformat()).get_data(as_text=True)
        self.assertIn("Het restaurant is op deze dag gesloten.", html)
        self.assertEqual(self.rijen(), [])
        self.assertEqual(self.invoeren(datum=maandag.isoformat(), bevestigd="1").status_code, 302)


class FoutTests(Basis):
    def test_ongeldige_velden(self):
        gevallen = [
            (dict(aantal="0"), "het aantal personen"),
            (dict(aantal="201"), "het aantal personen"),
            (dict(tijd="25:00"), "de tijd"),
            (dict(email="geen-email"), "het e-mailadres"),
            (dict(telefoon="abc"), "het telefoonnummer"),
            (dict(naam=""), "de naam"),
            (dict(opmerking="x" * 301), "de opmerking"),
            (dict(bron="online"), "de soort reservering"),
        ]
        for velden, tekst in gevallen:
            with self.subTest(velden=velden):
                antwoord = self.invoeren(**velden)
                self.assertEqual(antwoord.status_code, 400)
                self.assertIn(tekst, antwoord.get_data(as_text=True))
        self.assertEqual(self.rijen(), [])

    def test_ingevulde_waarden_blijven_staan(self):
        html = self.invoeren(aantal="0", opmerking="<b>raam</b>").get_data(as_text=True)
        self.assertIn('value="Siti Rahma"', html)
        self.assertIn("&lt;b&gt;raam&lt;/b&gt;", html)

    def test_datum_in_het_verleden(self):
        gisteren = self.regels.nu().date() - timedelta(days=1)
        antwoord = self.invoeren(datum=gisteren.isoformat())
        self.assertEqual(antwoord.status_code, 400)
        self.assertIn("verleden", antwoord.get_data(as_text=True))

    def test_telefoon_verplicht_bij_telefonische_reservering(self):
        antwoord = self.invoeren(telefoon="")
        self.assertEqual(antwoord.status_code, 400)
        self.assertIn("telefoonnummer", antwoord.get_data(as_text=True))

    def test_allergie_zonder_toestemming(self):
        antwoord = self.invoeren(allergieen="pinda")
        self.assertEqual(antwoord.status_code, 400)
        self.assertIn("toestemming", antwoord.get_data(as_text=True))
        self.assertEqual(self.rijen(), [])

    def test_dubbele_boeking(self):
        self.invoeren()
        antwoord = self.invoeren(naam="Iemand Anders")
        self.assertEqual(antwoord.status_code, 409)
        self.assertEqual(len(self.rijen()), 1)


class ZelfdeGastTests(unittest.TestCase):
    def test_lege_velden_tellen_niet_als_gelijk(self):
        a = {"email": "", "telefoon": "0612345678"}
        b = {"email": "", "telefoon": "0687654321"}
        self.assertFalse(is_zelfde_gast(a, b))
        self.assertFalse(is_zelfde_gast({"email": "x@example.com", "telefoon": ""},
                                        {"email": "y@example.com", "telefoon": ""}))
        self.assertTrue(is_zelfde_gast({"email": "", "telefoon": "06-12345678"}, {"email": "", "telefoon": "0612345678"}))
        self.assertTrue(is_zelfde_gast({"email": "X@example.com", "telefoon": ""}, {"email": "x@example.com", "telefoon": ""}))


class MigratieTests(unittest.TestCase):
    def test_bestaande_reserveringen_worden_online(self):
        with tempfile.TemporaryDirectory() as map_:
            url = f"sqlite:///{Path(map_) / 'migratie.db'}"
            omgeving = {**os.environ, "MIGRATION_DATABASE_URL": url}
            omgeving.pop("ALLOW_PROD_MIGRATE", None)

            def alembic(*args):
                resultaat = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=PROJECTMAP,
                                           env=omgeving, capture_output=True, text=True)
                self.assertEqual(resultaat.returncode, 0, resultaat.stderr)

            engine = create_engine(url)
            try:
                alembic("upgrade", "a8d3f5b2c7e1")
                with engine.begin() as conn:
                    conn.exec_driver_sql(
                        "INSERT INTO reserveringen (id, naam, email, telefoon, datum, tijd, aantal) "
                        "VALUES ('oud', 'Oud', 'o@example.com', '0612345678', '2030-01-01', '18:00', 4)")
                alembic("upgrade", "head")
                with engine.connect() as conn:
                    rij = conn.exec_driver_sql("SELECT bron, ingevoerd_door FROM reserveringen").one()
                self.assertEqual(tuple(rij), ("online", None))
                alembic("downgrade", "a8d3f5b2c7e1")
                kolommen = {k["name"] for k in inspect(engine).get_columns("reserveringen")}
                self.assertFalse({"bron", "ingevoerd_door"} & kolommen)
                with engine.connect() as conn:
                    self.assertEqual(conn.exec_driver_sql("SELECT count(*) FROM reserveringen").scalar(), 1)
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
