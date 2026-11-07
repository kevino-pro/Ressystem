import unittest
from pathlib import Path

from app.config import Config

PROJECTMAP = Path(__file__).resolve().parent.parent


class OpruimenTests(unittest.TestCase):
    def test_geen_tailwind_meer(self):
        for pad in sorted((PROJECTMAP / "templates").glob("*.html")):
            with self.subTest(pagina=pad.name):
                tekst = pad.read_text(encoding="utf-8")
                self.assertNotIn("tailwind", tekst.lower())
                self.assertNotIn('extends "base.html"', tekst)

    def test_oude_layout_en_variabelen_weg(self):
        self.assertFalse((PROJECTMAP / "templates" / "base.html").exists())
        self.assertFalse(hasattr(Config, "PRIMARY_COLOR"))
        self.assertFalse(hasattr(Config, "RESTAURANT_TAGLINE"))


if __name__ == "__main__":
    unittest.main()
