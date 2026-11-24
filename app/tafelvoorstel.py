"""
Tafelvoorstel: welke tafel of combinatie het systeem voor een reservering voorstelt.
De rekenregel zelf praat niet met de database of met Flask, zodat hij goed te testen is.
Komt uit de sectie [tafelvoorstel] van het restaurantbestand; zonder die sectie alleen losse tafels.
De keuze is de kleinste tafel die past; bij gelijke keuze de tafel die grote groepen het minst in de weg zit.
"""
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.database import minuten_van  # alleen de tijdhulp; deze module praat zelf niet met de database

# Statussen waarvoor nog een tafel voorgesteld mag worden.
OPEN_STATUSSEN = ("verwacht", "gearriveerd")


class Tafelvoorstel(BaseModel):
    """Per aantal personen de combinaties die het systeem mag voorstellen, in voorkeursvolgorde."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    combinaties: dict[int, tuple[tuple[str, ...], ...]] = {}


def laad_tafelvoorstel(pad, plattegrond):
    """
    Leest [tafelvoorstel] uit het restaurantbestand en controleert de combinaties tegen de plattegrond.
    Zonder [plattegrond] is er geen tafelvoorstel (None); een [tafelvoorstel] zonder plattegrond is een fout.
    Een fout in het voorstel wordt een RuntimeError, zodat de app niet start met tafels die niet bestaan.
    """
    pad = Path(pad)
    with pad.open("rb") as bestand:
        data = tomllib.load(bestand)  # laad_regels heeft al gecontroleerd dat dit geldige TOML is
    if "tafelvoorstel" not in data:
        return None if plattegrond is None else Tafelvoorstel()
    if plattegrond is None:
        raise RuntimeError("[tafelvoorstel] heeft een [plattegrond] nodig")
    try:
        voorstel = Tafelvoorstel.model_validate({"combinaties": data["tafelvoorstel"]})
    except ValueError as fout:
        raise RuntimeError(f"Tafelvoorstel in {pad} klopt niet:\n{fout}")
    _controleer(pad, voorstel, plattegrond)
    return voorstel


def _controleer(pad, voorstel, plattegrond):
    """Controleert elke combinatie; een fout wordt een RuntimeError met dezelfde kop als bij het laden."""
    def fout(melding):
        raise RuntimeError(f"Tafelvoorstel in {pad} klopt niet:\n{melding}")

    for aantal, combinaties in voorstel.combinaties.items():
        if not 1 <= aantal <= 50:
            fout(f"aantal personen {aantal} valt buiten 1-50")
        if not combinaties:
            fout(f"de lijst voor {aantal} personen is leeg")
        for combinatie in combinaties:
            if len(combinatie) < 2:
                fout(f"een combinatie voor {aantal} personen heeft minstens twee tafels")
            onbekend = [nummer for nummer in combinatie if plattegrond.tafel(nummer) is None]
            if onbekend:
                fout(f"combinatie voor {aantal} personen noemt onbekende tafel(s): {', '.join(onbekend)}")
            dubbel = sorted({nummer for nummer in combinatie if combinatie.count(nummer) > 1})
            if dubbel:
                fout(f"tafel {', '.join(dubbel)} staat twee keer in een combinatie voor {aantal} personen")
            stoelen = sum(plattegrond.tafel(nummer).stoelen for nummer in combinatie)
            if stoelen < aantal:
                fout(f"combinatie {'+'.join(combinatie)} heeft {stoelen} stoelen voor {aantal} personen")


def opties(plattegrond, voorstel, aantal):
    """
    De tafels en combinaties die voor `aantal` personen in aanmerking komen, in voorkeursvolgorde:
    eerst de kleinste losse tafel die past (bij evenveel stoelen op volgorde in het bestand),
    dan de combinaties uit het voorstel. Elke optie is een tuple tafelnummers, ook een losse tafel.
    """
    if plattegrond is None:
        return []
    los = sorted(
        (tafel.nummer for tafel in plattegrond.tafels if tafel.stoelen >= aantal),
        key=lambda nummer: plattegrond.tafel(nummer).stoelen,
    )
    combinaties = voorstel.combinaties.get(aantal, ()) if voorstel is not None else ()
    return [(nummer,) for nummer in los] + list(combinaties)


def voorstellen(reserveringen, toewijzingen, plattegrond, voorstel, zitduur_minuten):
    """
    Stelt per nog niet toegewezen reservering (status verwacht of gearriveerd) een tafel of combinatie voor.
    Wie het eerst reserveerde, gaat voor, zodat een bestaand voorstel niet verschuift als er een
    reservering bij komt. Geeft {reservering_id: tuple met tafelnummers of None}.
    """
    if plattegrond is None:
        return {}
    bezet = _bezet_van_toewijzingen(reserveringen, toewijzingen)
    voorgesteld = {}
    for reservering in _in_volgorde(reserveringen):
        if not _komt_in_aanmerking(reservering, toewijzingen):
            continue
        begin = minuten_van(reservering["tijd"])
        gekozen = _eerste_vrije(plattegrond, voorstel, reservering["aantal"], begin, bezet, zitduur_minuten)
        voorgesteld[reservering["id"]] = gekozen
        if gekozen:
            bezet.extend((nummer, begin) for nummer in gekozen)
    return voorgesteld


def past_nog(reserveringen, toewijzingen, plattegrond, voorstel, zitduur_minuten, tijd, aantal, behalve=None):
    """
    Of een nieuwe groep van `aantal` personen om `tijd` ('HH:MM') nog ergens terecht kan, als de
    bestaande reserveringen voorgaan. Met `behalve` (een reservering-id) telt die reservering niet mee,
    bijvoorbeeld wanneer de gast zijn eigen reservering wijzigt.
    """
    if plattegrond is None:
        return False
    bestaand = [reservering for reservering in reserveringen if reservering["id"] != behalve]
    voorgesteld = voorstellen(bestaand, toewijzingen, plattegrond, voorstel, zitduur_minuten)
    bezet = _bezet_van_toewijzingen(bestaand, toewijzingen)
    begin_van = {reservering["id"]: minuten_van(reservering["tijd"]) for reservering in bestaand}
    for reservering_id, gekozen in voorgesteld.items():
        for nummer in gekozen or ():
            bezet.append((nummer, begin_van[reservering_id]))
    begin = minuten_van(tijd)
    return _eerste_vrije(plattegrond, voorstel, aantal, begin, bezet, zitduur_minuten) is not None


def _bezet_van_toewijzingen(reserveringen, toewijzingen):
    """(tafel, begin_in_minuten) van elke toegewezen tafel; een no-show bezet geen tafel."""
    bezet = []
    for reservering in reserveringen:
        if reservering["status"] == "no_show":
            continue
        for tafel in toewijzingen.get(reservering["id"], ()):
            bezet.append((tafel, minuten_van(reservering["tijd"])))
    return bezet


def _komt_in_aanmerking(reservering, toewijzingen):
    """Alleen een open reservering zonder tafels krijgt een voorstel."""
    return reservering["status"] in OPEN_STATUSSEN and not toewijzingen.get(reservering["id"])


def _in_volgorde(reserveringen):
    """Oudste reservering eerst; zonder aangemaakt_op telt als oudst, daarna op id."""
    return sorted(reserveringen, key=lambda reservering: (
        reservering["aangemaakt_op"] is not None,
        reservering["aangemaakt_op"] or "",
        reservering["id"],
    ))


def _eerste_vrije(plattegrond, voorstel, aantal, begin, bezet, zitduur_minuten):
    """
    De kleinste tafel of combinatie waarvan alle tafels vrij zijn, of None.
    Bij gelijke keuze de tafel die grote groepen het minst in de weg zit: van de kandidaten gaat de
    voorkeur naar wie de meeste grotere groepen (uit het voorstel) nog ruimte laat.
    """
    vrij = [
        optie for optie in opties(plattegrond, voorstel, aantal)
        if all(_is_vrij(nummer, begin, bezet, zitduur_minuten) for nummer in optie)
    ]
    if not vrij:
        return None
    if voorstel is None or not any(groter > aantal for groter in voorstel.combinaties):
        return vrij[0]
    los = [optie for optie in vrij if len(optie) == 1]
    if los:
        # Kleinste vrije losse tafel; een combinatie met evenveel stoelen mag daarvoor in de plaats.
        stoelen = min(plattegrond.tafel(optie[0]).stoelen for optie in los)
        kandidaten = [optie for optie in los if plattegrond.tafel(optie[0]).stoelen == stoelen]
        kandidaten.extend(
            optie for optie in vrij
            if len(optie) > 1
            and sum(plattegrond.tafel(nummer).stoelen for nummer in optie) <= stoelen
        )
    else:
        kandidaten = vrij
    gekozen, ruimte = None, -1
    for kandidaat in kandidaten:
        telling = _ruimte_voor_groter(plattegrond, voorstel, aantal, begin, bezet, zitduur_minuten, kandidaat)
        if telling > ruimte:
            gekozen, ruimte = kandidaat, telling
    return gekozen


def _ruimte_voor_groter(plattegrond, voorstel, aantal, begin, bezet, zitduur_minuten, kandidaat):
    """
    Hoeveel grotere groepen (elke sleutel `g` > aantal in het voorstel) nog terecht kunnen als de
    tafels van de kandidaat op `begin` bezet zijn: per aantal telt minstens één combinatie die vrij blijft.
    """
    bezet_met_kandidaat = list(bezet) + [(nummer, begin) for nummer in kandidaat]
    return sum(
        1
        for groter, combinaties in voorstel.combinaties.items()
        if groter > aantal and any(
            all(_is_vrij(nummer, begin, bezet_met_kandidaat, zitduur_minuten) for nummer in combinatie)
            for combinatie in combinaties
        )
    )


def _is_vrij(nummer, begin, bezet, zitduur_minuten):
    """Een tafel is bezet als een andere groep er binnen de zitduur zit (zelfde regel als wijs_tafels_toe)."""
    return not any(
        tafel == nummer and abs(bezet_begin - begin) < zitduur_minuten
        for tafel, bezet_begin in bezet
    )
