"""
Reserveringsregels per restaurant: openingstijden, tijdsloten, zitduur en grenzen.
De regels komen uit een TOML-bestand (RESTAURANT_CONFIG) en worden bij het opstarten
gevalideerd; een fout in het bestand laat de app niet starten.
"""
import tomllib
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.taal import BRONTAAL, DAGEN, huidige_taal, vertaal

WEEKDAGEN = ("maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag")
TOEGESTANE_SLOTLENGTES = (5, 10, 15, 20, 30, 60)


class RegelFout(Exception):
    """
    Een reserveringsverzoek valt buiten de regels. `bericht` is de Nederlandse tekst voor de gast;
    vertaald() geeft dezelfde tekst in de taal van het verzoek. Een `weekdag` (0 = maandag) wordt
    in elke taal als naam ingevuld.
    """
    def __init__(self, sjabloon, **waarden):
        self.sjabloon = sjabloon
        self.waarden = waarden
        self.bericht = sjabloon.format(**self._ingevuld(BRONTAAL))
        super().__init__(self.bericht)

    def _ingevuld(self, taal):
        waarden = dict(self.waarden)
        if "weekdag" in waarden:
            waarden["weekdag"] = DAGEN[taal][waarden["weekdag"]]
        return waarden

    def vertaald(self):
        taal = huidige_taal()
        return vertaal(self.sjabloon, taal=taal, **self._ingevuld(taal))


def _naar_tijd(waarde):
    try:
        uur, minuut = waarde.split(":")
        return time(int(uur), int(minuut))
    except (AttributeError, ValueError):
        raise ValueError(f"'{waarde}' is geen tijd in de vorm HH:MM")


class Openingsblok(BaseModel):
    """Venster waarin een reservering mag BEGINNEN (bijv. 17:00-20:30)."""
    model_config = ConfigDict(frozen=True)
    van: time
    tot: time


class ReserveringsRegels(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tijdzone: str = "Europe/Amsterdam"
    slot_minuten: int = 15
    zitduur_minuten: int = Field(default=120, ge=15, le=480)
    max_gasten_tegelijk: int = Field(default=40, ge=1)
    max_personen_per_boeking: int = Field(default=8, ge=1, le=20)  # schemas.py staat ook max. 20 toe
    min_minuten_vooraf: int = Field(default=60, ge=0)
    max_dagen_vooruit: int = Field(default=90, ge=1)
    openingstijden: dict[str, tuple[Openingsblok, ...]]
    sluitingsdagen: tuple[date, ...] = ()
    # Hoe vaak het formulier een tijdknop toont (bijv. 30 = 12:00, 12:30, ...). Leeg = slot_minuten.
    knop_minuten: int | None = None
    # Vanaf deze tijd staan de knoppen onder "Diner" in plaats van "Lunch". Leeg = geen kopjes.
    diner_vanaf: time | None = None
    # Hoeveel kinderstoelen het restaurant heeft. 0 = het formulier vraagt er niet naar.
    kinderstoelen: int = Field(default=0, ge=0, le=20)
    # Vraagt het formulier naar allergieen? Alleen met aparte toestemming, en de dag na het bezoek gewist.
    vraag_allergieen: bool = False

    @field_validator("diner_vanaf", mode="before")
    @classmethod
    def _lees_diner_vanaf(cls, waarde):
        return None if waarde is None else _naar_tijd(waarde)

    @field_validator("tijdzone")
    @classmethod
    def _tijdzone_bestaat(cls, waarde):
        try:
            ZoneInfo(waarde)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"onbekende tijdzone '{waarde}'")
        return waarde

    @field_validator("slot_minuten")
    @classmethod
    def _geldige_slotlengte(cls, waarde):
        if waarde not in TOEGESTANE_SLOTLENGTES:
            raise ValueError(f"slot_minuten moet een van {TOEGESTANE_SLOTLENGTES} zijn")
        return waarde

    @field_validator("openingstijden", mode="before")
    @classmethod
    def _lees_blokken(cls, waarde):
        if not isinstance(waarde, dict):
            raise ValueError("openingstijden moet een tabel per weekdag zijn")
        onbekend = set(waarde) - set(WEEKDAGEN)
        if onbekend:
            raise ValueError(f"onbekende weekdag(en): {', '.join(sorted(onbekend))}")
        blokken = {}
        for dag in WEEKDAGEN:
            lijst = []
            for blok in waarde.get(dag, []):
                if not (isinstance(blok, (list, tuple)) and len(blok) == 2):
                    raise ValueError(f"{dag}: elk blok is [\"HH:MM\", \"HH:MM\"]")
                van, tot = _naar_tijd(blok[0]), _naar_tijd(blok[1])
                if van >= tot:
                    raise ValueError(f"{dag}: begintijd {blok[0]} ligt niet voor eindtijd {blok[1]}")
                lijst.append(Openingsblok(van=van, tot=tot))
            blokken[dag] = tuple(lijst)
        return blokken

    @model_validator(mode="after")
    def _knoppen_op_slotgrens(self):
        if self.knop_minuten is not None and (
                self.knop_minuten not in TOEGESTANE_SLOTLENGTES or self.knop_minuten % self.slot_minuten):
            raise ValueError(f"knop_minuten moet een veelvoud van slot_minuten ({self.slot_minuten}) zijn "
                             f"en een van {TOEGESTANE_SLOTLENGTES}")
        return self

    @model_validator(mode="after")
    def _blokken_op_slotgrens(self):
        for dag, blokken in self.openingstijden.items():
            for blok in blokken:
                for t in (blok.van, blok.tot):
                    if (t.hour * 60 + t.minute) % self.slot_minuten:
                        raise ValueError(f"{dag}: {t:%H:%M} valt niet op een slot van {self.slot_minuten} minuten")
        return self

    @property
    def zone(self):
        return ZoneInfo(self.tijdzone)

    def nu(self):
        """Huidige lokale tijd van het restaurant (Render draait in UTC)."""
        return datetime.now(self.zone)

    def blokken_op(self, dag: date):
        return self.openingstijden.get(WEEKDAGEN[dag.weekday()], ())

    def knoptijden_op(self, dag: date):
        """Begintijden die het formulier als knop toont, per knop_minuten binnen de openingstijden."""
        stap = self.knop_minuten or self.slot_minuten
        tijden = []
        for blok in self.blokken_op(dag):
            minuut = blok.van.hour * 60 + blok.van.minute
            einde = blok.tot.hour * 60 + blok.tot.minute
            while minuut <= einde:
                tijden.append(time(minuut // 60, minuut % 60))
                minuut += stap
        return tijden

    def controleer(self, dag: date, tijdstip: time, aantal: int, nu: datetime | None = None, kinderstoelen: int = 0):
        """Gooit RegelFout als dit verzoek niet mag; anders None."""
        nu = nu or self.nu()
        if kinderstoelen > self.kinderstoelen:
            if not self.kinderstoelen:
                raise RegelFout("Je kunt online geen kinderstoel reserveren. Bel ons, dan regelen we het.")
            raise RegelFout("Er zijn maximaal {aantal} kinderstoelen per reservering.", aantal=self.kinderstoelen)
        if aantal > self.max_personen_per_boeking:
            raise RegelFout(
                "Online reserveren kan voor maximaal {aantal} personen. "
                "Neem voor grotere groepen contact met ons op.", aantal=self.max_personen_per_boeking
            )
        if (tijdstip.hour * 60 + tijdstip.minute) % self.slot_minuten:
            raise RegelFout("Kies een tijd per {minuten} minuten, bijvoorbeeld 19:00.", minuten=self.slot_minuten)
        gevraagd = datetime.combine(dag, tijdstip, tzinfo=self.zone)
        if gevraagd < nu + timedelta(minutes=self.min_minuten_vooraf):
            if gevraagd < nu:
                raise RegelFout("Dit tijdstip ligt in het verleden.")
            raise RegelFout("Reserveer minstens {minuten} minuten van tevoren.", minuten=self.min_minuten_vooraf)
        if dag > nu.date() + timedelta(days=self.max_dagen_vooruit):
            raise RegelFout("Je kunt maximaal {dagen} dagen vooruit reserveren.", dagen=self.max_dagen_vooruit)
        if dag in self.sluitingsdagen:
            raise RegelFout("Het restaurant is op deze dag gesloten.")
        blokken = self.blokken_op(dag)
        if not blokken:
            raise RegelFout("Het restaurant is op {weekdag} gesloten.", weekdag=dag.weekday())
        if not any(blok.van <= tijdstip <= blok.tot for blok in blokken):
            vensters = ", ".join(f"{b.van:%H:%M}-{b.tot:%H:%M}" for b in blokken)
            raise RegelFout("Op {weekdag} kun je reserveren tussen {vensters}.", weekdag=dag.weekday(), vensters=vensters)


def laad_regels(pad) -> ReserveringsRegels:
    """Leest en valideert het TOML-bestand. Fouten worden RuntimeError met een duidelijke melding."""
    pad = Path(pad)
    try:
        with pad.open("rb") as bestand:
            data = tomllib.load(bestand)
    except FileNotFoundError:
        raise RuntimeError(f"Restaurantconfiguratie niet gevonden: {pad}")
    except tomllib.TOMLDecodeError as fout:
        raise RuntimeError(f"Restaurantconfiguratie {pad} is geen geldige TOML: {fout}")
    try:
        return ReserveringsRegels.model_validate(data.get("reserveringen", {}))
    except ValueError as fout:
        raise RuntimeError(f"Restaurantconfiguratie {pad} klopt niet:\n{fout}")
