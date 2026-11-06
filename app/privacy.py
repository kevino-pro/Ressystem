"""
Gegevens voor de privacyverklaring: wie verantwoordelijk is en welke partijen gastgegevens verwerken.
Komt uit de sectie [privacy] van het restaurantbestand. In productie is die sectie verplicht.
"""
import tomllib
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Verwerker(BaseModel):
    """Een partij die gastgegevens voor het restaurant verwerkt (hosting, mail, AI)."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    naam: str = Field(min_length=1, max_length=60)
    doel: str = Field(min_length=1, max_length=200)
    locatie: str = Field(min_length=1, max_length=60)


class Privacy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    verantwoordelijke: str = Field(min_length=1, max_length=100)  # naam van de onderneming
    adres: str = Field(min_length=1, max_length=200)
    kvk: str | None = Field(default=None, pattern=r"^[0-9]{8}$")
    bijgewerkt: date  # datum waarop de verklaring voor het laatst inhoudelijk is gewijzigd
    verwerkers: tuple[Verwerker, ...] = Field(min_length=1)


def laad_privacy(pad):
    """
    Leest [privacy] uit het restaurantbestand; geeft None als die sectie ontbreekt.
    Een fout wordt een RuntimeError, zodat de app niet start met een onvolledige verklaring.
    """
    pad = Path(pad)
    with pad.open("rb") as bestand:
        data = tomllib.load(bestand)
    if "privacy" not in data:
        return None
    try:
        return Privacy.model_validate(data["privacy"])
    except ValueError as fout:
        raise RuntimeError(f"Privacygegevens in {pad} kloppen niet:\n{fout}")
