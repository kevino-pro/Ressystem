"""
Herinneringsmail de dag voor het bezoek (deel 7). Staat aan met de sectie [herinnering] in het
restaurantbestand; zonder die sectie gaan er geen herinneringen uit.

Een geplande taak (GitHub Actions) roept POST /beheer/herinneringen aan. Die verstuurt pas vanaf `uur`
(tijdzone van het restaurant) en elke reservering hoogstens een keer, dus vaker aanroepen kan geen kwaad.
"""
import logging
import time
import tomllib
from datetime import datetime, time as tijdstip, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from app.database import claim_herinnering, herinnering_terugzetten, te_herinneren
from app.services.email_service import stuur_herinnering

logger = logging.getLogger(__name__)

MAX_PER_KEER = 20     # per aanroep; blijft zo ruim binnen de time-out van gunicorn (30 seconden)
PAUZE_SECONDEN = 0.6  # tussen twee mails; Resend staat 2 verzoeken per seconde toe


class Herinnering(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    uur: int = Field(default=10, ge=0, le=23)  # vanaf dit uur (tijdzone van het restaurant) gaan de mails uit


def laad_herinnering(pad):
    """Leest [herinnering] uit het restaurantbestand; None als die sectie ontbreekt (dan geen herinneringen)."""
    pad = Path(pad)
    with pad.open("rb") as bestand:
        data = tomllib.load(bestand)
    if "herinnering" not in data:
        return None
    try:
        return Herinnering.model_validate(data["herinnering"])
    except ValueError as fout:
        raise RuntimeError(f"Instellingen voor de herinnering in {pad} kloppen niet:\n{fout}")


def morgen_en_grens(regels):
    """
    De datum van morgen ('YYYY-MM-DD') en het begin van vandaag als UTC-tijd zonder tijdzone,
    om te vergelijken met aangemaakt_op (die de database in UTC zet).
    """
    nu = regels.nu()
    begin_vandaag = datetime.combine(nu.date(), tijdstip(0), tzinfo=nu.tzinfo)
    grens = begin_vandaag.astimezone(timezone.utc).replace(tzinfo=None)
    return (nu.date() + timedelta(days=1)).isoformat(), grens


def verstuur_herinneringen(conn, app_config, max_aantal=MAX_PER_KEER, pauze=PAUZE_SECONDEN):
    """
    Verstuurt hoogstens `max_aantal` herinneringen voor morgen. Een mislukte mail wordt teruggezet,
    zodat een volgende aanroep hem opnieuw probeert. Geeft (verstuurd, mislukt, resterend).
    """
    morgen, grens = morgen_en_grens(app_config['REGELS'])
    lijst = te_herinneren(conn, morgen, grens)
    verstuurd = mislukt = 0
    for reservering in lijst[:max_aantal]:
        if not claim_herinnering(conn, reservering['id']):
            continue  # een andere run was net eerder
        if (verstuurd or mislukt) and pauze:
            time.sleep(pauze)
        if stuur_herinnering(app_config, reservering):
            verstuurd += 1
        else:
            herinnering_terugzetten(conn, reservering['id'])
            mislukt += 1
    return verstuurd, mislukt, max(len(lijst) - max_aantal, 0)
