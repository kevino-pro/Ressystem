"""
Talen voor gasten (en later het personeel). De teksten in de code en de templates zijn Nederlands;
vertalingen/en.toml en vertalingen/id.toml zetten elke Nederlandse zin om. Geen extra package nodig.

Welke talen een restaurant aanbiedt staat in de sectie [talen] van het restaurantbestand. Zonder die
sectie is alles Nederlands en is er geen taalkiezer, zodat een restaurant met alleen Nederlands
gewoon blijft werken.
"""
import string
import tomllib
from datetime import date
from pathlib import Path
from typing import Literal

from flask import current_app, g, has_request_context, request
from pydantic import BaseModel, ConfigDict, Field, model_validator

BRONTAAL = "nl"  # de taal van de teksten in de code
ALLE_TALEN = ("en", "nl", "id")
TAAL_COOKIE = "taal"
VERTALINGEN_MAP = Path(__file__).resolve().parent.parent / "vertalingen"

Taalcode = Literal["en", "nl", "id"]
# Zo heet elke taal in die taal zelf; voor keuzelijsten.
TAALNAMEN = {"en": "English", "nl": "Nederlands", "id": "Bahasa Indonesia"}

# Voor datums: maandag is 0, net als date.weekday().
DAGEN = {
    "nl": ("maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"),
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
    "id": ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"),
}
DAGEN_KORT = {
    "nl": ("ma", "di", "wo", "do", "vr", "za", "zo"),
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    "id": ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"),
}
MAANDEN = {
    "nl": ("januari", "februari", "maart", "april", "mei", "juni", "juli",
           "augustus", "september", "oktober", "november", "december"),
    "en": ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"),
    "id": ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
           "Agustus", "September", "Oktober", "November", "Desember"),
}


class Talen(BaseModel):
    """[talen] uit het restaurantbestand: welke talen er zijn en welke geldt als niets anders past."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    beschikbaar: list[Taalcode] = Field(default_factory=lambda: [BRONTAAL], min_length=1)
    standaard: Taalcode = BRONTAAL

    @model_validator(mode="after")
    def _standaard_beschikbaar(self):
        if len(set(self.beschikbaar)) != len(self.beschikbaar):
            raise ValueError("beschikbaar bevat een taal dubbel")
        if self.standaard not in self.beschikbaar:
            raise ValueError(f"standaard '{self.standaard}' staat niet in beschikbaar")
        return self


def laad_talen(pad):
    """Leest [talen] uit het restaurantbestand; zonder die sectie alleen Nederlands."""
    pad = Path(pad)
    with pad.open("rb") as bestand:
        data = tomllib.load(bestand)
    try:
        return Talen.model_validate(data.get("talen", {}))
    except ValueError as fout:
        raise RuntimeError(f"Talen in {pad} kloppen niet:\n{fout}")


def laad_vertalingen(map_=VERTALINGEN_MAP):
    """
    {taal: {nederlandse_zin: vertaling}} voor elke taal behalve het Nederlands.
    Een vertaling moet dezelfde {plaatshouders} hebben als de Nederlandse zin; anders start de app niet.
    """
    vertalingen = {}
    for taal in ALLE_TALEN:
        if taal == BRONTAAL:
            continue
        pad = Path(map_) / f"{taal}.toml"
        with pad.open("rb") as bestand:
            data = tomllib.load(bestand)
        for bron, doel in data.items():
            if not isinstance(doel, str) or not doel.strip():
                raise RuntimeError(f"{pad.name}: lege of ongeldige vertaling voor {bron!r}")
            if plaatshouders(bron) != plaatshouders(doel):
                raise RuntimeError(f"{pad.name}: andere plaatshouders in de vertaling van {bron!r}")
        vertalingen[taal] = data
    return vertalingen


def plaatshouders(tekst):
    """{'naam', 'tijd'} voor 'Hallo {naam} om {tijd}'."""
    return {veld for _, veld, _, _ in string.Formatter().parse(tekst) if veld}


def huidige_taal():
    """
    De taal voor dit verzoek: voor ingelogd personeel de taal van het account; anders de keuze
    in de cookie, de beste taal uit de browser of de standaard van het restaurant.
    Buiten een verzoek: de brontaal.
    """
    if not has_request_context():
        return BRONTAAL
    if "taal" in g:
        return g.taal
    from app.toegang import huidige_gebruiker  # hier, want app.toegang gebruikt deze module ook
    talen = current_app.config["TALEN"]
    gebruiker = huidige_gebruiker()
    keuze = gebruiker["taal"] if gebruiker is not None else request.cookies.get(TAAL_COOKIE)
    if keuze not in talen.beschikbaar:
        keuze = request.cookies.get(TAAL_COOKIE)
    if keuze not in talen.beschikbaar:
        keuze = request.accept_languages.best_match(talen.beschikbaar) or talen.standaard
    g.taal = keuze
    return keuze


def vertaal(tekst, taal=None, **waarden):
    """Zet een Nederlandse zin om naar de taal van dit verzoek (of `taal`) en vult de {plaatshouders} in."""
    taal = taal or huidige_taal()
    if taal != BRONTAAL:
        tekst = current_app.config["VERTALINGEN"].get(taal, {}).get(tekst, tekst)
    return tekst.format(**waarden) if waarden else tekst


def datum_tekst(waarde, met_jaar=False, taal=None):
    """'2026-11-07' of een date -> 'zaterdag 7 november' / 'Saturday 7 November' / 'Sabtu 7 November'."""
    taal = taal or huidige_taal()
    dag = date.fromisoformat(waarde) if isinstance(waarde, str) else waarde
    tekst = f"{DAGEN[taal][dag.weekday()]} {dag.day} {MAANDEN[taal][dag.month - 1]}"
    return f"{tekst} {dag.year}" if met_jaar else tekst


def hoofdletter(tekst):
    """Alleen de eerste letter groot; anders dan |capitalize blijft 'Januari' ook 'Januari'."""
    return tekst[:1].upper() + tekst[1:]


def dag_kort(dag):
    return DAGEN_KORT[huidige_taal()][dag.weekday()]


def maand_kort(dag):
    return MAANDEN[huidige_taal()][dag.month - 1][:3]


def registreer(app):
    """Zet `t` en de datumfilters klaar voor de templates."""
    app.jinja_env.globals["t"] = vertaal
    app.jinja_env.filters["datum_tekst"] = datum_tekst
    app.jinja_env.filters["hoofdletter"] = hoofdletter
    app.jinja_env.filters["dag_kort"] = dag_kort
    app.jinja_env.filters["maand_kort"] = maand_kort
    app.context_processor(lambda: {
        "taal": huidige_taal(),
        "talen": app.config["TALEN"].beschikbaar,
    })
