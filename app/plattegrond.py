"""
Plattegrond van het restaurant voor het personeel: tafels en vaste elementen op een raster.
Komt uit de sectie [plattegrond] van het restaurantbestand; zonder die sectie is er geen plattegrond.
"""
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Vak(BaseModel):
    """Rechthoek op het raster; kolom en rij tellen vanaf 0 linksboven."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    kolom: int = Field(ge=0)
    rij: int = Field(ge=0)
    breedte: int = Field(default=1, ge=1)
    hoogte: int = Field(default=1, ge=1)

    def hokjes(self):
        return {
            (kolom, rij)
            for kolom in range(self.kolom, self.kolom + self.breedte)
            for rij in range(self.rij, self.rij + self.hoogte)
        }


class Tafel(Vak):
    nummer: str = Field(pattern=r"^[0-9A-Za-z]{1,10}$")
    stoelen: int = Field(ge=1, le=20)
    vorm: Literal["vierkant", "rond"] = "vierkant"


class Element(Vak):
    """Vast onderdeel zonder stoelen, zoals de bar of een paal; alleen voor de tekening."""
    naam: str = Field(min_length=1, max_length=30)


class Plattegrond(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kolommen: int = Field(ge=1, le=60)
    rijen: int = Field(ge=1, le=60)
    tafels: tuple[Tafel, ...] = Field(min_length=1)
    elementen: tuple[Element, ...] = ()
    combinaties: tuple[tuple[str, ...], ...] = ()

    @model_validator(mode="after")
    def _controleer(self):
        nummers = [tafel.nummer for tafel in self.tafels]
        dubbel = sorted({nummer for nummer in nummers if nummers.count(nummer) > 1})
        if dubbel:
            raise ValueError(f"tafelnummer(s) komen dubbel voor: {', '.join(dubbel)}")
        bezet = {}
        for vak in (*self.tafels, *self.elementen):
            label = f"tafel {vak.nummer}" if isinstance(vak, Tafel) else vak.naam
            if vak.kolom + vak.breedte > self.kolommen or vak.rij + vak.hoogte > self.rijen:
                raise ValueError(f"{label} valt buiten het raster van {self.kolommen} bij {self.rijen}")
            for hokje in vak.hokjes():
                if hokje in bezet:
                    raise ValueError(f"{label} overlapt met {bezet[hokje]}")
                bezet[hokje] = label
        gezien = set()
        for groep in self.combinaties:
            if len(groep) < 2:
                raise ValueError("een combinatie heeft minstens twee tafels")
            for nummer in groep:
                if nummer not in nummers:
                    raise ValueError(f"combinatie noemt onbekende tafel {nummer}")
                if nummer in gezien:
                    raise ValueError(f"tafel {nummer} staat in meer dan een combinatie")
                gezien.add(nummer)
        return self

    @property
    def totaal_stoelen(self):
        return sum(tafel.stoelen for tafel in self.tafels)

    def tafel(self, nummer):
        return next((tafel for tafel in self.tafels if tafel.nummer == nummer), None)


def laad_plattegrond(pad):
    """
    Leest [plattegrond] uit het restaurantbestand; geeft None als die sectie ontbreekt.
    Een fout in de plattegrond wordt een RuntimeError, zodat de app niet start met een kapotte indeling.
    """
    pad = Path(pad)
    with pad.open("rb") as bestand:
        data = tomllib.load(bestand)  # laad_regels heeft al gecontroleerd dat dit geldige TOML is
    if "plattegrond" not in data:
        return None
    try:
        return Plattegrond.model_validate(data["plattegrond"])
    except ValueError as fout:
        raise RuntimeError(f"Plattegrond in {pad} klopt niet:\n{fout}")
