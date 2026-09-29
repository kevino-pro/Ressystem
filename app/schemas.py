from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field

class ReserveringSchema(BaseModel):
    naam: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    telefoon: str = Field(..., min_length=8, max_length=20)
    datum: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$')
    tijd: str = Field(..., pattern=r'^\d{2}:\d{2}$')
    aantal: int = Field(..., ge=1, le=50)
    website: Optional[str] = None
    privacy_akkoord: Literal[True]

class AIWebhookSchema(BaseModel):
    klant_tekst: str = Field(..., min_length=5, max_length=1000)
    bron: str = Field(default="whatsapp")

class AIReserveringExtractieSchema(BaseModel):
    naam: Optional[str] = Field(default=None, min_length=2, max_length=100, description="Volledige naam van de gast")
    email: Optional[EmailStr] = Field(default=None, description="E-mailadres van de gast")
    telefoon: Optional[str] = Field(default=None, min_length=8, max_length=20, description="Telefoonnummer van de gast")
    datum: Optional[str] = Field(default=None, pattern=r'^\d{4}-\d{2}-\d{2}$', description="Reserveringsdatum in YYYY-MM-DD formaat")
    tijd: Optional[str] = Field(default=None, pattern=r'^\d{2}:\d{2}$', description="Tijdstip in HH:MM-formaat (24-uurs)")
    aantal: Optional[int] = Field(default=None, ge=1, le=50, description="Aantal personen als geheel getal")