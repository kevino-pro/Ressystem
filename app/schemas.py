import re
import unicodedata
from datetime import date, time
from typing import Annotated, Literal, Optional

from pydantic import AliasChoices, BaseModel, BeforeValidator, ConfigDict, EmailStr, Field, PlainSerializer

from app.normalisatie import telefoon_cijfers

TELEFOON_PATROON = re.compile(r"\+?[0-9][0-9 \-]*")
MIN_TELEFOON_CIJFERS = 9
MAX_TELEFOON_CIJFERS = 15
TELEFOON_MELDING = "Vul een geldig telefoonnummer in, bijvoorbeeld 0612345678 of +31 6 12345678."
NAAM_MELDING = "Vul je naam in."
MAX_OPMERKING = 300
OPMERKING_MELDING = f"Je opmerking mag maximaal {MAX_OPMERKING} tekens zijn."
MAX_ALLERGIEEN = 200
ALLERGIE_MELDING = f"Vul je allergieën in met maximaal {MAX_ALLERGIEEN} tekens."


def _validate_iso_date(value: object) -> object:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Datum moet de vorm YYYY-MM-DD hebben.")
    return value


def _validate_iso_time(value: object) -> object:
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise ValueError("Tijd moet de vorm HH:MM hebben.")
    return value


def _serialize_iso_time(value: time) -> str:
    return value.strftime("%H:%M")


def _validate_telefoon(value: object) -> object:
    """Cijfers, spaties en koppeltekens, optioneel een + vooraan; 9 tot 15 cijfers."""
    if not isinstance(value, str):
        raise ValueError(TELEFOON_MELDING)
    value = value.strip()
    aantal_cijfers = len(telefoon_cijfers(value))
    if not TELEFOON_PATROON.fullmatch(value) or not MIN_TELEFOON_CIJFERS <= aantal_cijfers <= MAX_TELEFOON_CIJFERS:
        raise ValueError(TELEFOON_MELDING)
    return value


def _validate_naam(value: object) -> object:
    """Spaties aan de randen en dubbele spaties weg; minstens een letter, geen stuurtekens."""
    if not isinstance(value, str):
        raise ValueError(NAAM_MELDING)
    value = " ".join(value.split())
    if not any(teken.isalpha() for teken in value):
        raise ValueError(NAAM_MELDING)
    if any(unicodedata.category(teken).startswith("C") for teken in value):
        raise ValueError(NAAM_MELDING)
    return value


def _vrije_tekst(maximum: int, melding: str):
    """Optioneel vrij veld: leeg wordt None; regeleinden en stuurtekens worden een spatie."""
    def valideer(value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(melding)
        value = " ".join("".join(" " if unicodedata.category(t).startswith("C") else t for t in value).split())
        if len(value) > maximum:
            raise ValueError(melding)
        return value or None
    return valideer


ISODate = Annotated[date, BeforeValidator(_validate_iso_date)]
ISOTime = Annotated[
    time,
    BeforeValidator(_validate_iso_time),
    PlainSerializer(_serialize_iso_time, return_type=str, when_used="json"),
]
Telefoon = Annotated[str, BeforeValidator(_validate_telefoon), Field(max_length=20)]
Naam = Annotated[str, BeforeValidator(_validate_naam), Field(min_length=2, max_length=100)]
Opmerking = Annotated[Optional[str], BeforeValidator(_vrije_tekst(MAX_OPMERKING, OPMERKING_MELDING))]
Allergieen = Annotated[Optional[str], BeforeValidator(_vrije_tekst(MAX_ALLERGIEEN, ALLERGIE_MELDING))]


class DTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ReserveringSchema(DTO):
    naam: Naam
    email: EmailStr
    telefoon: Telefoon
    datum: ISODate
    tijd: ISOTime
    aantal: int = Field(..., ge=1, le=20, validation_alias=AliasChoices("aantal", "aantal_personen"))
    website: Optional[str] = None
    privacy_akkoord: Literal[True]
    opmerking: Opmerking = None
    kinderstoelen: int = Field(default=0, ge=0, le=20)
    allergieen: Allergieen = None
    allergie_toestemming: bool = False  # aparte, uitdrukkelijke toestemming (artikel 9 AVG)


def _leeg_is_none(value: object) -> object:
    """Een leeg of alleen-spaties formulierveld telt als niet ingevuld."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


MAX_PERSONEN_PERSONEEL = 200


class PersoneelReserveringSchema(DTO):
    """
    Een reservering die het personeel invoert (telefoon of binnenloper). Ruimer dan online:
    e-mail is niet verplicht en het aantal mag boven de online grens. Capaciteit en openingstijden
    worden niet hier gecontroleerd; de route waarschuwt daarvoor.
    """
    bron: Literal["telefoon", "binnenloper"] = "telefoon"
    naam: Naam
    telefoon: Annotated[Optional[Telefoon], BeforeValidator(_leeg_is_none)] = None
    email: Annotated[Optional[EmailStr], BeforeValidator(_leeg_is_none)] = None
    datum: ISODate
    tijd: ISOTime
    aantal: int = Field(..., ge=1, le=MAX_PERSONEN_PERSONEEL)
    opmerking: Opmerking = None
    kinderstoelen: int = Field(default=0, ge=0, le=20)
    allergieen: Allergieen = None
    allergie_toestemming: bool = False
    bevestigd: bool = False  # het personeel heeft de waarschuwing gezien en wil toch opslaan
    taal: Optional[Literal["en", "nl", "id"]] = None  # taal van de gast, voor de bevestigingsmail


class AIWebhookSchema(DTO):
    klant_tekst: str = Field(..., min_length=5, max_length=1000)
    bron: str = Field(default="whatsapp")


class AIReserveringExtractieSchema(DTO):
    naam: Optional[Naam] = Field(default=None, description="Volledige naam van de gast")
    email: Optional[EmailStr] = Field(default=None, description="E-mailadres van de gast")
    telefoon: Optional[Telefoon] = Field(default=None, description="Telefoonnummer van de gast")
    datum: Optional[ISODate] = Field(default=None, description="Reserveringsdatum in YYYY-MM-DD formaat")
    tijd: Optional[ISOTime] = Field(default=None, description="Tijdstip in HH:MM-formaat (24-uurs)")
    aantal: Optional[int] = Field(default=None, ge=1, le=20, description="Aantal personen als geheel getal")