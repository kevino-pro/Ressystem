"""
Deel 6, fase 4: de privacyverklaring in het Engels, Nederlands en Indonesisch.
Bij een vertaling staat erbij dat bij twijfel de Nederlandse tekst geldt.
"""
import unittest

from markupsafe import Markup

from app import create_app
from app.privacy import Privacy
from app.taal import vertaal_html
from tests.test_privacy_pagina import KWAADAARDIG, TestConfig, ZonderPrivacyConfig

TWIJFEL_NL = "Bij twijfel geldt de Nederlandse tekst."


def pagina(config, taal, privacy=None):
    app = create_app(config)
    if privacy is not None:
        app.config["PRIVACY"] = privacy
    antwoord = app.test_client().get("/privacy", headers={"Accept-Language": taal})
    return antwoord.status_code, antwoord.get_data(as_text=True)


class PrivacyInDrieTalenTests(unittest.TestCase):
    def test_engels(self):
        status, html = pagina(TestConfig, "en")
        self.assertEqual(status, 200)
        for tekst in ("Privacy statement", "Who is responsible?", "Your rights", "60 days",
                      "In case of doubt, the Dutch text applies."):
            with self.subTest(tekst=tekst):
                self.assertIn(tekst, html)
        self.assertNotIn("Wie is verantwoordelijk?", html)

    def test_indonesisch(self):
        _, html = pagina(TestConfig, "id")
        self.assertIn("Pernyataan privasi", html)
        self.assertIn("Jika ada keraguan, teks bahasa Belanda yang berlaku.", html)
        self.assertIn('lang="id"', html)

    def test_vertaling_linkt_naar_de_nederlandse_tekst(self):
        _, html = pagina(TestConfig, "en")
        self.assertIn('href="/taal/nl?terug=/privacy"', html)

    def test_nederlands_zonder_twijfelregel(self):
        _, html = pagina(TestConfig, "nl")
        self.assertIn("Privacyverklaring", html)
        self.assertNotIn("Dit is een vertaling", html)

    def test_restaurant_met_alleen_nederlands(self):
        _, html = pagina(ZonderPrivacyConfig, "en")
        self.assertIn("Privacyverklaring", html)
        self.assertNotIn("Dit is een vertaling", html)
        self.assertNotIn("taalcode", html)  # geen taalkiezer, dus ook geen taalcookie

    def test_taalcookie_genoemd(self):
        _, html = pagina(TestConfig, "nl")
        self.assertIn("een tweede functionele cookie die keuze een jaar lang", html)
        _, html = pagina(TestConfig, "en")
        self.assertIn("a second functional cookie remembers that choice for one year", html)

    def test_verwerkers_vertaald(self):
        _, html = pagina(TestConfig, "en")
        self.assertIn("sending the confirmation email", html)
        self.assertIn("United States", html)
        self.assertNotIn("Verenigde Staten", html)

    def test_eigen_verwerker_blijft_nederlands(self):
        p = create_app(TestConfig).config["PRIVACY"].model_dump()
        p["verwerkers"] = [{"naam": "Eigen dienst", "doel": "iets wat niet in vertalingen/ staat", "locatie": "Europese Unie"}]
        _, html = pagina(TestConfig, "en", Privacy.model_validate(p))
        self.assertIn("iets wat niet in vertalingen/ staat", html)
        self.assertIn("European Union", html)

    def test_links_blijven_links_en_tekst_wordt_ge_escaped(self):
        config = create_app(TestConfig).config
        p = config["PRIVACY"].model_copy(update={"verantwoordelijke": KWAADAARDIG})
        mail = config["RESTAURANT_EMAIL"]  # uit [restaurant] in restaurants/wpl.toml
        for taal in ("en", "nl", "id"):
            with self.subTest(taal=taal):
                _, html = pagina(TestConfig, taal, p)
                self.assertNotIn(KWAADAARDIG, html)
                self.assertIn("&lt;script&gt;", html)
                self.assertIn(f'<a href="mailto:{mail}">{mail}</a>', html)
                self.assertIn('<a href="https://www.autoriteitpersoonsgegevens.nl" rel="noopener">', html)
                self.assertIn("<strong>", html)

    def test_datum_overal_als_dag_maand_jaar(self):
        datum = create_app(TestConfig).config["PRIVACY"].bijgewerkt
        _, html = pagina(TestConfig, "en")
        self.assertIn(f"last updated on {datum:%d-%m-%Y}", html)


class VertaalHtmlTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)

    def test_alleen_markup_blijft_html(self):
        with self.app.test_request_context(headers={"Accept-Language": "nl"}):
            uit = vertaal_html("Mail naar {email}.", email=Markup('<a href="x">x</a>'))
            self.assertEqual(str(uit), 'Mail naar <a href="x">x</a>.')
            uit = vertaal_html("Mail naar {email}.", email="<b>")
            self.assertEqual(str(uit), "Mail naar &lt;b&gt;.")

    def test_vertaling_zelf_wordt_ge_escaped(self):
        self.app.config["VERTALINGEN"]["en"]["Mail naar {email}."] = "<i>Email</i> {email}."
        with self.app.test_request_context(headers={"Accept-Language": "en"}):
            self.assertEqual(str(vertaal_html("Mail naar {email}.", email="a")), "&lt;i&gt;Email&lt;/i&gt; a.")


if __name__ == "__main__":
    unittest.main()
