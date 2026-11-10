"""Allergieen: alleen met aparte toestemming, alleen voor personeel, de dag na het bezoek gewist (deel 2, fase 2)."""
import re
import unittest
from datetime import timedelta
from unittest import mock

from sqlalchemy import insert, select

from app import create_app
from app.database import get_db, reserveringen, wis_allergieen_voor
from app.schemas import ReserveringSchema
from tests.test_extra_wensen import Basis, TestConfig

SLEUTEL = "s" * 40


class AllergieConfig(TestConfig):
    BEHEER_API_KEY = SLEUTEL


class FormulierTests(Basis):
    def test_veld_en_verborgen_toestemming(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn('<input type="text" id="allergieen" maxlength="200"', html)
        self.assertIn('id="allergie_akkoord" hidden', html)
        self.assertIn('<input type="checkbox" id="allergie_toestemming">', html)  # nooit vooraf aangevinkt

    def test_restaurant_zonder_allergievraag(self):
        class ZonderConfig(TestConfig):
            RESTAURANT_CONFIG = "tests/restaurant_vast.toml"
        app = create_app(ZonderConfig)
        self.assertNotIn('id="allergieen"', app.test_client().get("/").get_data(as_text=True))
        self.assertNotIn("Allergieën", app.test_client().get("/privacy").get_data(as_text=True))


class OpslaanTests(Basis):
    def test_met_toestemming_bewaard(self):
        r = self.opgeslagen(self.boek(allergieen="pinda", allergie_toestemming=True))
        self.assertEqual(r["allergieen"], "pinda")

    def test_zonder_toestemming_geweigerd(self):
        antwoord = self.boek(allergieen="pinda")
        self.assertEqual(antwoord.status_code, 422)
        self.assertIn("allergie-informatie mogen bewaren", antwoord.get_json()["bericht"])
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                self.assertEqual(conn.execute(select(reserveringen)).all(), [])

    def test_leeg_veld_zonder_toestemming_mag(self):
        r = self.opgeslagen(self.boek(allergieen="  ", allergie_toestemming=False))
        self.assertIsNone(r["allergieen"])

    def test_te_lang(self):
        antwoord = self.boek(allergieen="x" * 201, allergie_toestemming=True)
        self.assertEqual(antwoord.status_code, 422)
        self.assertIn("200 tekens", antwoord.get_json()["bericht"])

    def test_restaurant_zonder_allergievraag_bewaart_niets(self):
        class ZonderConfig(TestConfig):
            RESTAURANT_CONFIG = "tests/restaurant_vast.toml"
        self.app = create_app(ZonderConfig)
        self.client = self.app.test_client()
        html = self.client.get("/").get_data(as_text=True)
        self.headers = {"X-CSRF-Token": re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)}
        r = self.opgeslagen(self.boek(allergieen="pinda", allergie_toestemming=True))
        self.assertIsNone(r["allergieen"])

    def test_zichtbaar_voor_personeel_niet_voor_gast(self):
        self.boek(allergieen="<b>pinda</b>", allergie_toestemming=True)
        bevestiging = self.client.get("/bevestiging").get_data(as_text=True)
        self.assertIn("Doorgegeven aan de keuken", bevestiging)
        self.assertNotIn("pinda", bevestiging)
        with self.client.session_transaction() as sessie:
            sessie["ingelogd"] = True
        overzicht = self.client.get(f"/overzicht?datum={self.dinsdag}").get_data(as_text=True)
        self.assertIn("Allergie: &lt;b&gt;pinda&lt;/b&gt;", overzicht)
        plattegrond = self.client.get(f"/plattegrond?datum={self.dinsdag}&tijd=18:00").get_data(as_text=True)
        self.assertIn("· allergie", plattegrond)

    def test_niet_in_de_mail(self):
        with mock.patch("app.routes.web.stuur_bevestigingsmail_async") as mail:
            self.boek(allergieen="pinda", allergie_toestemming=True)
        self.assertNotIn("pinda", repr(mail.call_args))

    def test_schema(self):
        basis = {"naam": "Jan", "email": "jan@example.com", "telefoon": "0612345678",
                 "datum": "2030-01-01", "tijd": "18:00", "aantal": 2, "privacy_akkoord": True}
        schema = ReserveringSchema(**basis)
        self.assertEqual((schema.allergieen, schema.allergie_toestemming), (None, False))


class WissenTests(Basis):
    def setUp(self):
        super().setUp()
        self.app = create_app(AllergieConfig)
        self.vandaag = self.app.config["REGELS"].nu().date()
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                for rid, dagen in (("gisteren", -1), ("vandaag", 0), ("morgen", 1)):
                    conn.execute(insert(reserveringen).values(
                        id=rid, naam="Gast", email=f"{rid}@example.com", telefoon="0612345678",
                        datum=(self.vandaag + timedelta(days=dagen)).isoformat(), tijd="18:00", aantal=2,
                        allergieen="pinda", opmerking="blijft"))

    def stand(self):
        with self.app.app_context():
            conn = get_db()
            with conn.begin():
                return {r.id: (r.allergieen, r.opmerking) for r in conn.execute(select(reserveringen))}

    def test_alleen_na_het_bezoek(self):
        with self.app.app_context():
            self.assertEqual(wis_allergieen_voor(get_db(), self.vandaag.isoformat()), 1)
            self.assertEqual(wis_allergieen_voor(get_db(), self.vandaag.isoformat()), 0)
        self.assertEqual(self.stand(), {"gisteren": (None, "blijft"), "vandaag": ("pinda", "blijft"),
                                        "morgen": ("pinda", "blijft")})

    def test_nachtelijke_opschoning(self):
        antwoord = self.app.test_client().post("/beheer/opschonen", headers={"X-Beheer-Key": SLEUTEL})
        self.assertEqual(antwoord.get_json(), {"status": "succes", "verwijderd": 0, "allergieen_gewist": 1})
        self.assertIsNone(self.stand()["gisteren"][0])

    def test_commando(self):
        resultaat = self.app.test_cli_runner().invoke(args=["purge-retention", "--uitvoeren"])
        self.assertEqual(resultaat.exit_code, 0, resultaat.output)
        self.assertIn("Bij 1 reservering(en) van voor vandaag de allergieën gewist.", resultaat.output)
        zonder = self.app.test_cli_runner().invoke(args=["purge-retention"])
        self.assertNotIn("allergieën", zonder.output)  # alleen tellen: niets wissen
        self.assertEqual(self.stand()["morgen"][0], "pinda")


class PrivacyTests(Basis):
    def test_tekst_over_allergieen(self):
        html = self.client.get("/privacy").get_data(as_text=True)
        for tekst in ("artikel 9 lid 2 onder a AVG", "de dag na je bezoek gewist", "in de nacht na je bezoek",
                      "toestemming altijd intrekken", "het aantal kinderstoelen"):
            with self.subTest(tekst=tekst):
                self.assertIn(tekst, html)


if __name__ == "__main__":
    unittest.main()
