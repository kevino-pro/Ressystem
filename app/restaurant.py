"""
Naam, e-mailadres en telefoonnummer van het restaurant (kop, voet, mails, agenda en de AI-prompt).
Komt uit de sectie [restaurant] van het restaurantbestand. In productie is die sectie verplicht; zonder
de sectie (lokaal en in oudere tests) gelden RESTAURANT_NAAM, RESTAURANT_EMAIL en RESTAURANT_TELEFOON uit de omgeving.
"""
import re
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas import TELEFOON_PATROON, MIN_TELEFOON_CIJFERS, MAX_TELEFOON_CIJFERS

# Een gewoon e-mailadres zonder spaties of tekens die in een mailto-link of mailkop iets anders betekenen.
EMAIL_PATROON = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


class Restaurant(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    naam: str = Field(min_length=1, max_length=60)
    email: str = Field(max_length=120)
    telefoon: str = Field(max_length=20)

    @field_validator("naam")
    @classmethod
    def _naam(cls, waarde):
        if waarde != waarde.strip() or any(teken in waarde for teken in "<>\r\n"):
            raise ValueError("naam zonder spaties aan het begin of eind, zonder < > en zonder regeleinde")
        return waarde

    @field_validator("email")
    @classmethod
    def _email(cls, waarde):
        if not EMAIL_PATROON.fullmatch(waarde):
            raise ValueError("geen geldig e-mailadres")
        return waarde

    @field_validator("telefoon")
    @classmethod
    def _telefoon(cls, waarde):
        cijfers = sum(teken.isdigit() for teken in waarde)
        if not TELEFOON_PATROON.fullmatch(waarde) or not MIN_TELEFOON_CIJFERS <= cijfers <= MAX_TELEFOON_CIJFERS:
            raise ValueError("cijfers, spaties en streepjes, eventueel een + vooraan; 9 tot 15 cijfers")
        return waarde


def laad_restaurant(pad):
    """
    Leest [restaurant] uit het restaurantbestand; geeft None als die sectie ontbreekt.
    Een fout wordt een RuntimeError, zodat de app niet start met een verkeerde naam of een kapot telefoonnummer.
    """
    pad = Path(pad)
    with pad.open("rb") as bestand:
        data = tomllib.load(bestand)
    if "restaurant" not in data:
        return None
    try:
        return Restaurant.model_validate(data["restaurant"])
    except ValueError as fout:
        raise RuntimeError(f"Restaurantgegevens in {pad} kloppen niet:\n{fout}")
