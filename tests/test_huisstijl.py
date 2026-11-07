import re
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.config import Config
from app.huisstijl import Huisstijl, laad_huisstijl

PROJECTMAP = Path(__file__).resolve().parent.parent


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    API_KEY = "test-key"
    WEBHOOK_API_KEY = "test-key"
    DATABASE_URL = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    TRUSTED_PROXY_COUNT = 0
    RESTAURANT_CONFIG = "restaurants/wpl.toml"


class ZonderHuisstijlConfig(TestConfig):
    RESTAURANT_CONFIG = "tests/fixtures/restaurant_test.toml"


def schrijf_toml(tekst):
    bestand = tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False, encoding="utf-8")
    bestand.write(tekst)
    bestand.close()
    return bestand.name


class HuisstijlValidatieTests(unittest.TestCase):
    def test_standaard_zonder_sectie(self):
        stijl = laad_huisstijl(schrijf_toml("[reserveringen]\n"), PROJECTMAP / "static")
        self.assertEqual(stijl.accentkleur, "#d9a441")
        self.assertIsNone(stijl.achtergrond)

    def test_alleen_hexkleur(self):
        for kleur in ("red", "#fff", "#12345g", "#123456;}", "url(x)"):
            with self.subTest(kleur=kleur), self.assertRaises(ValueError):
                Huisstijl(accentkleur=kleur)

    def test_achtergrond_alleen_veilig_pad(self):
        for pad in ("../geheim.jpg", "/etc/foto.jpg", "foto.gif", 'a".jpg', "map/../foto.png"):
            with self.subTest(pad=pad), self.assertRaises(ValueError):
                Huisstijl(achtergrond=pad)
        self.assertEqual(Huisstijl(achtergrond="restaurants/wpl/foto.webp").achtergrond, "restaurants/wpl/foto.webp")

    def test_onbekend_veld(self):
        with self.assertRaises(ValueError):
            Huisstijl(kleur="#000000")

    def test_tekstkleur_op_accent(self):
        self.assertEqual(Huisstijl(accentkleur="#d9a441").accent_tekst, "#1a1306")
        self.assertEqual(Huisstijl(accentkleur="#0f766e").accent_tekst, "#ffffff")

    def test_ontbrekende_foto_stopt_de_app(self):
        pad = schrijf_toml('[huisstijl]\nachtergrond = "bestaat/niet.webp"\n')
        with self.assertRaises(RuntimeError) as fout:
            laad_huisstijl(pad, PROJECTMAP / "static")
        self.assertIn("bestaat niet", str(fout.exception))

    def test_bestaande_foto(self):
        with tempfile.TemporaryDirectory() as map_:
            (Path(map_) / "r").mkdir()
            (Path(map_) / "r" / "foto.webp").write_bytes(b"x")
            pad = schrijf_toml('[huisstijl]\nachtergrond = "r/foto.webp"\n')
            self.assertEqual(laad_huisstijl(pad, map_).achtergrond, "r/foto.webp")

    def test_restaurantbestanden_zijn_geldig(self):
        for naam in ("wpl.toml", "voorbeeld.toml"):
            with self.subTest(naam=naam):
                laad_huisstijl(PROJECTMAP / "restaurants" / naam, PROJECTMAP / "static")


class HuisstijlPaginaTests(unittest.TestCase):
    def test_css_wordt_geserveerd(self):
        client = create_app(TestConfig).test_client()
        antwoord = client.get("/static/css/huisstijl.css")
        self.assertEqual(antwoord.status_code, 200)
        self.assertIn("--accent", antwoord.get_data(as_text=True))
        antwoord.close()

    def test_login_in_nieuwe_stijl(self):
        app = create_app(TestConfig)
        html = app.test_client().get("/login").get_data(as_text=True)
        self.assertIn("/static/css/huisstijl.css", html)
        self.assertIn(f"--accent: {app.config['HUISSTIJL'].accentkleur}", html)
        self.assertIn(app.config["HUISSTIJL"].ondertitel, html)
        self.assertIn('autocomplete="current-password"', html)
        self.assertNotIn("cdn.tailwindcss.com", html)

    def test_foutmelding_bij_verkeerd_wachtwoord(self):
        class ZonderCsrf(TestConfig):
            CSRF_ENABLED = False
        app = create_app(ZonderCsrf)
        from app.database import get_db, metadata
        with app.app_context():
            conn = get_db()
            metadata.create_all(conn)
            conn.commit()
        html = app.test_client().post("/login", data={"gebruikersnaam": "x", "wachtwoord": "y"}).get_data(as_text=True)
        self.assertIn('class="melding fout"', html)

    def test_zonder_huisstijl_standaardkleur(self):
        html = create_app(ZonderHuisstijlConfig).test_client().get("/login").get_data(as_text=True)
        self.assertIn("--accent: #d9a441", html)
        self.assertNotIn("background-image", html)

    def test_foto_in_css(self):
        app = create_app(TestConfig)
        app.config["HUISSTIJL"] = Huisstijl(achtergrond="restaurants/wpl/foto.webp")
        html = app.test_client().get("/login").get_data(as_text=True)
        self.assertIn('url("/static/restaurants/wpl/foto.webp")', html)


if __name__ == "__main__":
    unittest.main()
