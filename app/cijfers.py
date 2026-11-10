"""
Cijfers voor de beheerder (deel 10): gasten per dag en week, drukste tijden, no-shows en bronnen.
Alleen rekenwerk op aantallen; de route staat in app/routes/cijfers.py.
"""
from datetime import date, timedelta

from app.database import BRONNEN

WEKEN_TERUG = 8  # zoveel weken in het overzicht per week
PERIODE_DAGEN = 28  # drukste tijden, no-shows en bronnen: de laatste 4 weken t/m gisteren
STAP_MINUTEN = 30  # de drukste tijden per half uur


def maandag_van(dag: date) -> date:
    return dag - timedelta(days=dag.weekday())


def _leeg():
    return {'reserveringen': 0, 'gasten': 0, 'no_shows': 0}


def per_dag(tellingen):
    """{(datum, bron): telling} -> {datum: telling} (alle bronnen opgeteld)."""
    dagen = {}
    for (datum, _bron), telling in tellingen.items():
        totaal = dagen.setdefault(datum, _leeg())
        for kolom, waarde in telling.items():
            totaal[kolom] += waarde
    return dagen


def week(tellingen, maandag: date):
    """Zeven rijen (ma t/m zo) met de cijfers van die dag en van dezelfde dag een week eerder."""
    dagen = per_dag(tellingen)
    rijen = []
    for i in range(7):
        dag = maandag + timedelta(days=i)
        rijen.append({'dag': dag, **dagen.get(dag.isoformat(), _leeg()),
                      'vorige': dagen.get((dag - timedelta(days=7)).isoformat(), _leeg())['gasten']})
    return rijen


def weektotalen(tellingen, laatste_maandag: date, aantal=WEKEN_TERUG):
    """Per week (oudste eerst) het aantal gasten en reserveringen, met de breedte van de balk in procenten."""
    dagen = per_dag(tellingen)
    weken = []
    for i in range(aantal - 1, -1, -1):
        maandag = laatste_maandag - timedelta(weeks=i)
        totaal = _leeg()
        for d in range(7):
            for kolom, waarde in dagen.get((maandag + timedelta(days=d)).isoformat(), _leeg()).items():
                totaal[kolom] += waarde
        weken.append({'maandag': maandag, **totaal})
    hoogste = max((w['gasten'] for w in weken), default=0)
    for w in weken:
        w['balk'] = round(100 * w['gasten'] / hoogste) if hoogste else 0
    return weken


def procent(deel, geheel):
    return round(100 * deel / geheel) if geheel else 0


def verschil(nu, vorige):
    """Verschil in procenten met de vorige week, of None als de vorige week leeg was."""
    return round(100 * (nu - vorige) / vorige) if vorige else None


def no_shows(tellingen):
    totaal = _leeg()
    for telling in tellingen.values():
        for kolom, waarde in telling.items():
            totaal[kolom] += waarde
    return {'reserveringen': totaal['reserveringen'], 'no_shows': totaal['no_shows'],
            'procent': procent(totaal['no_shows'], totaal['reserveringen'])}


def per_bron(tellingen):
    """Reserveringen per bron (in de volgorde van BRONNEN, plus onbekende), met het aandeel in procenten."""
    aantallen = {bron: 0 for bron in BRONNEN}
    for (_datum, bron), telling in tellingen.items():
        aantallen[bron] = aantallen.get(bron, 0) + telling['reserveringen']
    totaal = sum(aantallen.values())
    return [{'bron': bron, 'reserveringen': n, 'procent': procent(n, totaal)} for bron, n in aantallen.items()]


def drukste_tijden(regels, bezoeken, van: date, tot: date):
    """
    Per half uur het gemiddelde aantal gasten aan tafel op de open dagen van van t/m tot.
    Een reservering zit aan tafel van haar begintijd tot begintijd + zitduur. Geeft een lijst
    {'tijd', 'gasten', 'balk'}; leeg als er in die periode geen open dag was.
    """
    open_dagen = [van + timedelta(days=i) for i in range((tot - van).days + 1)]
    open_dagen = [d for d in open_dagen if regels.blokken_op(d) and d not in regels.sluitingsdagen]
    blokken = [b for d in open_dagen for b in regels.blokken_op(d)]
    if not blokken:
        return []
    begin = min(b.van.hour * 60 + b.van.minute for b in blokken)
    begin -= begin % STAP_MINUTEN
    einde = max(b.tot.hour * 60 + b.tot.minute for b in blokken) + regels.zitduur_minuten
    per_dag_lijst = {}
    for datum, tijd, aantal in bezoeken:
        uur, minuut = str(tijd).split(':')[:2]
        per_dag_lijst.setdefault(datum, []).append((int(uur) * 60 + int(minuut), aantal))
    rijen = []
    for moment in range(begin, einde, STAP_MINUTEN):
        totaal = sum(
            aantal
            for d in open_dagen
            for start, aantal in per_dag_lijst.get(d.isoformat(), [])
            if start <= moment < start + regels.zitduur_minuten
        )
        rijen.append({'tijd': f"{moment // 60:02d}:{moment % 60:02d}", 'gasten': round(totaal / len(open_dagen), 1)})
    hoogste = max(r['gasten'] for r in rijen)
    for r in rijen:
        r['balk'] = round(100 * r['gasten'] / hoogste) if hoogste else 0
    return rijen
