"""
Huisstijl per restaurant: accentkleur, achtergrondfoto en ondertitel.
Komt uit de sectie [huisstijl] van het restaurantbestand. Zonder die sectie gelden nette standaardwaarden,
zodat een nieuw restaurant ook zonder foto direct werkt.
"""
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Huisstijl(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    # Kleur van knoppen, gekozen tijden en de naam bovenaan. Alleen #rrggbb, zodat er niets anders in de CSS komt.
    accentkleur: str = Field(default="#d9a441", pattern=r"^#[0-9a-fA-F]{6}$")
    # Pad binnen de map static/, bijvoorbeeld "restaurants/wpl/achtergrond.webp". Geen punten in de mapnamen.
    achtergrond: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_\-/]{0,119}\.(jpg|jpeg|png|webp)$")
    # Regel onder de naam, bijvoorbeeld het adres.
    ondertitel: str = Field(default="", max_length=80)

    @property
    def accent_tekst(self):
        """Donkere of witte tekst op de accentkleur, afhankelijk van hoe licht die kleur is."""
        r, g, b = (int(self.accentkleur[i:i + 2], 16) for i in (1, 3, 5))
        return "#1a1306" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"


def laad_huisstijl(pad, static_map):
    """
    Leest [huisstijl] uit het restaurantbestand; zonder die sectie de standaard.
    Een fout of een ontbrekende foto wordt een RuntimeError, zodat de app niet start met een kapotte pagina.
    """
    pad = Path(pad)
    with pad.open("rb") as bestand:
        data = tomllib.load(bestand)
    try:
        huisstijl = Huisstijl.model_validate(data.get("huisstijl", {}))
    except ValueError as fout:
        raise RuntimeError(f"Huisstijl in {pad} klopt niet:\n{fout}")
    if huisstijl.achtergrond and not (Path(static_map) / huisstijl.achtergrond).is_file():
        raise RuntimeError(f"Achtergrondfoto static/{huisstijl.achtergrond} uit {pad.name} bestaat niet.")
    return huisstijl
