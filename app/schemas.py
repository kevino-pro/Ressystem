import re
from datetime import date, time
from typing import Annotated, Literal, Optional

from pydantic import AliasChoices, BaseModel, BeforeValidator, ConfigDict, EmailStr, Field, PlainSerializer


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


ISODate = Annotated[date, BeforeValidator(_validate_iso_date)]
ISOTime = Annotated[
    time,
    BeforeValidator(_validate_iso_time),
    PlainSerializer(_serialize_iso_time, return_type=str, when_used="json"),
]


class DTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ReserveringSchema(DTO):
    naam: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    telefoon: str = Field(..., min_length=8, max_length=20)
    datum: ISODate
    tijd: ISOTime
    aantal: int = Field(..., ge=1, le=20, validation_alias=AliasChoices("aantal", "aantal_personen"))
    website: Optional[str] = None
    privacy_akkoord: Literal[True]


class AIWebhookSchema(DTO):
    klant_tekst: str = Field(..., min_length=5, max_length=1000)
    bron: str = Field(default="whatsapp")


class AIReserveringExtractieSchema(DTO):
    naam: Optional[str] = Field(default=None, min_length=2, max_length=100, description="Volledige naam van de gast")
    email: Optional[EmailStr] = Field(default=None, description="E-mailadres van de gast")
    telefoon: Optional[str] = Field(default=None, min_length=8, max_length=20, description="Telefoonnummer van de gast")
    datum: Optional[ISODate] = Field(default=None, description="Reserveringsdatum in YYYY-MM-DD formaat")
    tijd: Optional[ISOTime] = Field(default=None, description="Tijdstip in HH:MM-formaat (24-uurs)")
    aantal: Optional[int] = Field(default=None, ge=1, le=20, description="Aantal personen als geheel getal")