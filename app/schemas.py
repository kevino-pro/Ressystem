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
    naam: str = Field(..., description="Volledige naam van de gast. Als onbekend, gebruik 'Gast via WhatsApp'")
    email: EmailStr = Field(..., description="E-mailadres van de gast. Als onbekend, gebruik 'geen-email@restaurant.nl'")
    telefoon: str = Field(..., description="Telefoonnummer van de gast. Als onbekend, gebruik '0600000000'")
    datum: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$', description="Reserveringsdatum verplicht in YYYY-MM-DD formaat")
    tijd: str = Field(..., pattern=r'^\d{2}:\d{2}$', description="Tijdstip van reservering verplicht in HH:MM formaat (24-uurs)")
    aantal: int = Field(..., ge=1, le=50, description="Aantal personen als geheel getal")