"""Het overzicht van vandaag op urgentie (fase 3): Te laat, Komt zo, Later, Binnen en Niet gekomen."""
import re
import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from app.reserveringsregels import ReserveringsRegels
from app.routes.web import KOMT_ZO_MINUTEN, _urgentie
from tests.test_aankomst import MORGEN, VANDAAG, Basis  # in Basis is het "nu" dinsdag 1 januari 2030, 18:07


def koppen(html):
    """De groepskoppen in volgorde, als (soort, tekst)."""
    return re.findall(r'<div class="tijdkop ([a-z]*)">\s*<b>([^<]*)</b>', html)


class UrgentieTests(Basis):
    def pagina(self, datum=None):
        return self.client.get("/overzicht" + (f"?datum={datum}" if datum else "")).get_data(as_text=True)

    def test_groepen_in_vaste_volgorde(self):
        self.reservering(naam="Later", tijd="19:30")
        self.reservering(naam="Laat", tijd="17:45")
        self.reservering(naam="Zo", tijd="18:30")
        self.zet(self.reservering(naam="Binnen", tijd="18:00"), "gearriveerd")
        self.zet(self.reservering(naam="Weg", tijd="17:00"), "no_show")
        html = self.pagina()
        self.assertEqual(koppen(html), [("laat", "Te laat"), ("zo", "Komt zo"), ("later", "Later"),
                                        ("binnen", "Binnen"), ("niet", "Niet gekomen")])
        volgorde = [html.index(f"<b>{naam}</b>") for naam in ("Laat", "Zo", "Later", "Binnen", "Weg")]
        self.assertEqual(volgorde, sorted(volgorde))

    def test_grenzen_begintijd_en_een_half_uur(self):
        self.assertEqual(KOMT_ZO_MINUTEN, 30)
        self.reservering(naam="OpTijd", tijd="18:07")     # de begintijd is er: zelfde grens als de knop Niet gekomen
        self.reservering(naam="NogNet", tijd="18:37")     # precies een half uur
        self.reservering(naam="Daarna", tijd="18:38")
        html = self.pagina()
        delen = re.split(r'<div class="tijdkop [a-z]*">', html)[1:]
        self.assertEqual(len(delen), 3)
        self.assertIn("<b>OpTijd</b>", delen[0])
        self.assertIn("<b>NogNet</b>", delen[1])
        self.assertIn("<b>Daarna</b>", delen[2])
        self.assertIn('value="no_show"', delen[0])        # wie te laat is, kan op Niet gekomen
        self.assertNotIn('value="no_show"', delen[1])

    def test_lege_groepen_staan_er_niet(self):
        self.reservering(naam="Later", tijd="20:00")
        self.assertEqual(koppen(self.pagina()), [("later", "Later")])

    def test_kop_telt_reserveringen_en_gasten_en_elke_rij_toont_de_tijd(self):
        self.reservering(naam="Een", tijd="19:00", aantal=2)
        self.reservering(naam="Twee", tijd="19:30", aantal=4)
        html = self.pagina()
        self.assertIn("2 reserveringen · 6 gasten", html)
        self.assertEqual(re.findall(r'<span class="rijtijd">([0-9:]+)</span>\s*<b>([^<]*)</b>', html),
                         [("19:00", "Een"), ("19:30", "Twee")])

    def test_na_is_er_staat_de_gast_onder_binnen(self):
        rid = self.reservering(naam="Siti", tijd="18:00")
        self.assertEqual(koppen(self.pagina()), [("laat", "Te laat")])
        self.zet(rid, "gearriveerd")
        self.assertEqual(koppen(self.pagina()), [("binnen", "Binnen")])

    def test_andere_dag_blijft_per_begintijd_zonder_tijd_op_de_rij(self):
        self.reservering(naam="Morgen1", tijd="18:00", datum=MORGEN)
        self.reservering(naam="Morgen2", tijd="19:00", datum=MORGEN)
        html = self.pagina(MORGEN)
        self.assertEqual(koppen(html), [("", "18:00"), ("", "19:00")])
        self.assertNotIn("rijtijd", html)
        self.assertNotIn("Te laat", html)

    def test_vandaag_met_datum_in_de_url_is_ook_op_urgentie(self):
        self.reservering(naam="Later", tijd="20:00")
        self.assertEqual(koppen(self.pagina(VANDAAG)), [("later", "Later")])

    def test_vlak_voor_middernacht_loopt_komt_zo_tot_het_einde_van_de_dag(self):
        laat = datetime(2030, 1, 1, 23, 45, tzinfo=ZoneInfo("Europe/Amsterdam"))
        self.reservering(naam="Nacht", tijd="23:55")
        with mock.patch.object(ReserveringsRegels, "nu", lambda self: laat):
            self.assertEqual(koppen(self.pagina()), [("zo", "Komt zo")])


class UrgentieFunctieTests(unittest.TestCase):
    def soort(self, status, tijd):
        return _urgentie({"status": status, "tijd": tijd}, "18:07", "18:37")

    def test_status_gaat_voor_de_tijd(self):
        self.assertEqual(self.soort("gearriveerd", "20:00"), "binnen")
        self.assertEqual(self.soort("no_show", "17:00"), "niet")

    def test_verwacht_naar_tijd(self):
        self.assertEqual(self.soort("verwacht", "17:00"), "laat")
        self.assertEqual(self.soort("verwacht", "18:07"), "laat")
        self.assertEqual(self.soort("verwacht", "18:08"), "zo")
        self.assertEqual(self.soort("verwacht", "18:37"), "zo")
        self.assertEqual(self.soort("verwacht", "18:38"), "later")


if __name__ == "__main__":
    unittest.main()
