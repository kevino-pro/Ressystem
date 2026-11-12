"""
Controle van een restaurantbestand vóór de eerste deploy (template-kit).

Gebruik (Git Bash, vanuit de repo-root):  python -m app.controle restaurants/<naam>.toml
Leest alleen het bestand, de vertalingen en static/. Geen database, geen omgevingsvariabelen, geen geheimen.
Exitcode 0 als het bestand in productie zou starten, anders 1.
"""
import sys
import tomllib
from pathlib import Path

from app.herinnering import laad_herinnering
from app.huisstijl import laad_huisstijl
from app.plattegrond import laad_plattegrond
from app.privacy import laad_privacy
from app.reserveringsregels import laad_regels
from app.restaurant import laad_restaurant
from app.taal import BRONTAAL, laad_talen, laad_vertalingen

PROJECTMAP = Path(__file__).resolve().parent.parent
STATIC_MAP = PROJECTMAP / "static"

OK, LET_OP, FOUT = "OK", "LET OP", "FOUT"


def _melding(fout):
    """De foutmelding op één regel, zonder de kopregel met het pad en zonder de verwijzing naar de Pydantic-site."""
    regels = [regel.strip() for regel in str(fout).splitlines()
              if regel.strip() and not regel.strip().startswith("For further information")]
    return " | ".join(regels[1:]) if len(regels) > 1 else regels[0]


def _sectie(naam, laden, verplicht, uitleg_zonder):
    """Eén regel (onderdeel, status, melding) voor een sectie van het restaurantbestand."""
    try:
        waarde = laden()
    except RuntimeError as fout:
        return (naam, FOUT, _melding(fout)), None
    if waarde is None:
        if verplicht:
            return (naam, FOUT, "ontbreekt; verplicht in productie"), None
        return (naam, LET_OP, uitleg_zonder), None
    return (naam, OK, ""), waarde


def controleer(pad, static_map=STATIC_MAP):
    """
    Geeft een lijst (onderdeel, status, melding). Status FOUT betekent: de app start niet met APP_ENV=production.
    LET OP is toegestaan maar waarschijnlijk niet de bedoeling voor een echt restaurant.
    """
    pad = Path(pad)
    try:
        laad_regels(pad)  # leest het bestand en controleert [reserveringen]
    except RuntimeError as fout:
        return [("[reserveringen]", FOUT, _melding(fout))]
    uitslag = [("[reserveringen]", OK, "")]

    with pad.open("rb") as bestand:
        aanwezig = set(tomllib.load(bestand))
    secties = (
        ("[restaurant]", lambda: laad_restaurant(pad), True, ""),
        ("[privacy]", lambda: laad_privacy(pad), True, ""),
        ("[plattegrond]", lambda: laad_plattegrond(pad), False, "ontbreekt; het personeel heeft dan geen plattegrond"),
        # Zonder [huisstijl] en [talen] geven de laders een standaard terug in plaats van None.
        ("[huisstijl]", lambda: laad_huisstijl(pad, static_map) if "huisstijl" in aanwezig else None, False,
         "ontbreekt; standaardkleur en geen ondertitel"),
        ("[talen]", lambda: laad_talen(pad) if "talen" in aanwezig else None, False,
         "ontbreekt; alles in het Nederlands en geen taalkiezer"),
        ("[herinnering]", lambda: laad_herinnering(pad), False, "ontbreekt; er gaan dan geen herinneringsmails uit"),
    )
    geladen = {}
    for naam, laden, verplicht, uitleg in secties:
        regel, geladen[naam] = _sectie(naam, laden, verplicht, uitleg)
        uitslag.append(regel)
    privacy = geladen["[privacy]"]
    talen = geladen["[talen]"]  # None: alleen Nederlands, of [talen] klopt niet (al als FOUT gemeld)

    # De privacyverklaring toont doel en locatie van elke verwerker via de vertalingen.
    if privacy is not None and talen is not None:
        vertalingen = laad_vertalingen()
        ontbreekt = sorted({zin for v in privacy.verwerkers for zin in (v.doel, v.locatie)
                            for taal in talen.beschikbaar if taal != BRONTAAL
                            if zin not in vertalingen[taal]})
        if ontbreekt:
            uitslag.append(("vertalingen", FOUT, "niet vertaald: " + "; ".join(ontbreekt)))
        else:
            uitslag.append(("vertalingen", OK, ""))
    return uitslag


def main(argumenten=None):
    argumenten = sys.argv[1:] if argumenten is None else argumenten
    if len(argumenten) != 1:
        print("Gebruik: python -m app.controle restaurants/<naam>.toml")
        return 2
    pad = Path(argumenten[0])
    if not pad.is_file():
        print(f"Bestand niet gevonden: {pad}")
        return 1
    uitslag = controleer(pad)
    for onderdeel, status, melding in uitslag:
        print(f"{status:<7} {onderdeel}" + (f"  {melding}" if melding else ""))
    fouten = sum(status == FOUT for _, status, _ in uitslag)
    print(f"{fouten} fout(en)." if fouten else "Klaar voor productie.")
    return 1 if fouten else 0


if __name__ == "__main__":
    raise SystemExit(main())
