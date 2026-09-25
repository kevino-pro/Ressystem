import os
import re
import time
from datetime import datetime, timedelta
import anthropic
from flask import current_app
from app.schemas import AIReserveringExtractieSchema

MAX_POGINGEN = 3
BASIS_WACHTTIJD_SECONDEN = 1

def sanitize_user_input(text: str) -> str:
    clean_text = re.sub(r'[\r\n\t]+', ' ', text)
    clean_text = re.sub(r'```|\[system\]|<system>', '', clean_text, flags=re.IGNORECASE)
    return clean_text.strip()

def _anthropic_aanroep_met_retry(client, **kwargs):
    """
    Retryt op tijdelijke 429 (RateLimitError) en 5xx (InternalServerError, o.a. 503) fouten
    en op verbindingsproblemen, met exponentiële backoff (1s, 2s). client.max_retries staat
    op 0 zodat deze lus de enige retry-laag is, anders vermenigvuldigen wachttijden zich.
    """
    for poging in range(1, MAX_POGINGEN + 1):
        try:
            return client.messages.create(**kwargs)
        except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError):
            if poging == MAX_POGINGEN:
                raise
            time.sleep(BASIS_WACHTTIJD_SECONDEN * (2 ** (poging - 1)))

def verwerk_tekst_met_anthropic(klant_tekst: str) -> AIReserveringExtractieSchema:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY ontbreekt in .env configuratie!")

    client = anthropic.Anthropic(api_key=api_key, max_retries=0)
    vandaag = datetime.now()
    vandaag_str = vandaag.strftime("%Y-%m-%d (%A)")
    morgen_str = (vandaag + timedelta(days=1)).strftime("%Y-%m-%d")

    system_prompt = f"""
    Je bent de reserverings-assistent voor het restaurant '{current_app.config['RESTAURANT_NAAM']}'.
    Jouw taak is om klantteksten te analyseren en de verplichte tool 'extract_reservering' uit te voeren.

    EXACTE DATUM EN TIJD CONTEXT:
    - Vandaag is: {vandaag_str}
    - Morgen is exact: {morgen_str}
    - Reken relatieve dagen ALTIJD exact om naar het formaat YYYY-MM-DD t.o.v. vandaag.
    - Het veld 'datum' MOET strikt het YYYY-MM-DD formaat hebben.
    - Het veld 'tijd' MOET strikt het HH:MM (24-uurs) formaat hebben.
    """

    tool_definition = {
        "name": "extract_reservering",
        "description": "Exporteer de geëxtraheerde reserveringsgegevens in strikt YYYY-MM-DD en HH:MM formaat.",
        "input_schema": AIReserveringExtractieSchema.model_json_schema()
    }

    model_naam = current_app.config.get('ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001')

    response = _anthropic_aanroep_met_retry(
        client,
        model=model_naam,
        max_tokens=1000,
        system=system_prompt,
        tools=[tool_definition],
        tool_choice={"type": "tool", "name": "extract_reservering"},
        messages=[{"role": "user", "content": klant_tekst}]
    )

    for content in response.content:
        if content.type == "tool_use" and content.name == "extract_reservering":
            return AIReserveringExtractieSchema(**content.input)

    raise ValueError("Anthropic Claude heeft geen geldige structuur teruggegeven.")