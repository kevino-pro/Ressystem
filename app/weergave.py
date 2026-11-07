"""Kleine hulpjes om datums en tijden voor gasten en personeel in gewoon Nederlands te tonen."""
from datetime import date, datetime, timedelta

DAGEN = ("maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag")
MAANDEN = ("januari", "februari", "maart", "april", "mei", "juni", "juli",
           "augustus", "september", "oktober", "november", "december")


def nl_datum(waarde, met_jaar=False):
    """'2026-11-07' of een date -> 'zaterdag 7 november' (met_jaar: '... 2026')."""
    dag = date.fromisoformat(waarde) if isinstance(waarde, str) else waarde
    tekst = f"{DAGEN[dag.weekday()]} {dag.day} {MAANDEN[dag.month - 1]}"
    return f"{tekst} {dag.year}" if met_jaar else tekst


def eindtijd(tijd, minuten):
    """'19:00' en 90 -> '20:30'. Over middernacht heen telt gewoon door (00:30)."""
    begin = datetime.strptime(tijd, "%H:%M")
    return (begin + timedelta(minutes=minuten)).strftime("%H:%M")


def voornaam(naam):
    """'Jan Jansen' -> 'Jan'. Zo staat er op openbare pagina's nooit een volledige naam."""
    delen = (naam or "").split()
    return delen[0] if delen else ""


def dag_kort(dag):
    """date -> 'za'."""
    return DAGEN[dag.weekday()][:2]


def maand_kort(dag):
    """date -> 'nov'."""
    return MAANDEN[dag.month - 1][:3]


def registreer(app):
    app.jinja_env.filters["nl_datum"] = nl_datum
    app.jinja_env.filters["eindtijd"] = eindtijd
    app.jinja_env.filters["voornaam"] = voornaam
    app.jinja_env.filters["dag_kort"] = dag_kort
    app.jinja_env.filters["maand_kort"] = maand_kort
