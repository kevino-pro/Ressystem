"""De pagina Cijfers: alleen voor beheerders (deel 10)."""
from datetime import date, timedelta

from flask import Blueprint, current_app, render_template, request

from app import cijfers
from app.database import bezoeken_tussen, get_db, tellingen_per_dag
from app.taal import vertaal as t
from app.toegang import beheerder_vereist

cijfers_bp = Blueprint('cijfers', __name__)


@cijfers_bp.route('/cijfers')
@beheerder_vereist
def overzicht():
    """
    GET /cijfers?week=JJJJ-MM-DD (een dag in de week; standaard deze week). Alleen aantallen, geen namen.
    Oudere weken komen uit de dagtellingen, want reserveringen worden na de bewaartermijn verwijderd.
    """
    regels = current_app.config['REGELS']
    vandaag = regels.nu().date()
    try:
        gekozen = date.fromisoformat(request.args['week']) if request.args.get('week') else vandaag
    except ValueError:
        return t("Ongeldige datum."), 400
    maandag = cijfers.maandag_van(gekozen)
    zondag = maandag + timedelta(days=6)

    conn = get_db()
    eerste = maandag - timedelta(weeks=cijfers.WEKEN_TERUG - 1)
    tellingen = tellingen_per_dag(conn, eerste.isoformat(), zondag.isoformat())
    dagen = cijfers.week(tellingen, maandag)
    totaal = {kolom: sum(d[kolom] for d in dagen) for kolom in ('reserveringen', 'gasten', 'no_shows', 'vorige')}

    # De laatste 4 weken t/m gisteren: die dagen zijn voorbij, dus no-shows en drukte zijn bekend.
    gisteren = vandaag - timedelta(days=1)
    periode_van = gisteren - timedelta(days=cijfers.PERIODE_DAGEN - 1)
    periode = tellingen_per_dag(conn, periode_van.isoformat(), gisteren.isoformat())
    bezoeken = bezoeken_tussen(conn, periode_van.isoformat(), gisteren.isoformat())

    return render_template(
        'cijfers.html', actief='cijfers', maandag=maandag, zondag=zondag, vandaag=vandaag,
        vorige_week=(maandag - timedelta(weeks=1)).isoformat(), volgende_week=(maandag + timedelta(weeks=1)).isoformat(),
        deze_week=cijfers.maandag_van(vandaag), dagen=dagen, totaal=totaal,
        verschil=cijfers.verschil(totaal['gasten'], totaal['vorige']),
        weken=cijfers.weektotalen(tellingen, maandag),
        periode_van=periode_van, periode_tot=gisteren,
        drukte=cijfers.drukste_tijden(regels, bezoeken, periode_van, gisteren),
        no_shows=cijfers.no_shows(periode), bronnen=cijfers.per_bron(periode),
    )
