"""
Personeelsaccounts beheren: alleen voor beheerders. Aanmaken, aan- en uitzetten en een nieuw
wachtwoord instellen. Een account wordt nooit verwijderd, alleen uitgezet.
"""
import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import OperationalError

from app.database import (
    ROLLEN, LaatsteBeheerderFout, get_db, haal_alle_personeel, haal_gebruiker_op_id, maak_gebruiker,
    zet_actief, zet_wachtwoord,
)
from app.security import rate_limit, valideer_csrf
from app.taal import vertaal as t
from app.toegang import MIN_WACHTWOORD_LENGTE, beheerder_vereist, huidige_gebruiker, wachtwoord_fout

accounts_bp = Blueprint('accounts', __name__, url_prefix='/accounts')
accounts_bp.before_request(valideer_csrf)

GEBRUIKERSNAAM_PATROON = re.compile(r'[a-z0-9._-]{3,30}')
DATABASE_DRUK = "Het lukte niet om op te slaan. Probeer het opnieuw."  # vertaald bij het tonen


def _terug():
    return redirect(url_for('accounts.overzicht'))


@accounts_bp.route('')
@beheerder_vereist
def overzicht():
    return render_template(
        'accounts.html', actief='accounts', accounts=haal_alle_personeel(get_db()),
        ik=huidige_gebruiker(), rollen=ROLLEN, min_lengte=MIN_WACHTWOORD_LENGTE,
    )


@accounts_bp.post('/nieuw')
@beheerder_vereist
@rate_limit('accounts', 20, 600)
def nieuw():
    naam = request.form.get('gebruikersnaam', '').strip().lower()
    wachtwoord = request.form.get('wachtwoord', '')
    rol = request.form.get('rol', 'medewerker')
    if not GEBRUIKERSNAAM_PATROON.fullmatch(naam):
        flash(t("De gebruikersnaam mag 3 tot 30 tekens hebben: kleine letters, cijfers, punt, streepje en underscore."), 'fout')
    elif rol not in ROLLEN:
        flash(t("Kies een rol."), 'fout')
    elif (fout := wachtwoord_fout(wachtwoord)) is not None:
        flash(fout, 'fout')
    else:
        try:
            aangemaakt = maak_gebruiker(get_db(), naam, wachtwoord, rol)
        except OperationalError:
            flash(t(DATABASE_DRUK), 'fout')
        else:
            if aangemaakt:
                flash(t("Account {naam} is aangemaakt. Geef de gebruikersnaam en het wachtwoord zelf door.", naam=naam), 'ok')
            else:
                flash(t("De gebruikersnaam {naam} bestaat al.", naam=naam), 'fout')
    return _terug()


@accounts_bp.post('/<int:gebruiker_id>/actief')
@beheerder_vereist
def actief(gebruiker_id):
    aan = request.form.get('actief') == '1'
    conn = get_db()
    doel = haal_gebruiker_op_id(conn, gebruiker_id)
    if doel is None:
        flash(t("Dit account bestaat niet."), 'fout')
    elif doel['id'] == huidige_gebruiker()['id'] and not aan:
        flash(t("Je kunt je eigen account niet uitzetten."), 'fout')
    else:
        try:
            zet_actief(conn, gebruiker_id, aan)
        except LaatsteBeheerderFout as fout:
            flash(t(fout.bericht), 'fout')
        except OperationalError:
            flash(t(DATABASE_DRUK), 'fout')
        else:
            flash(t("Account {naam} staat nu aan.", naam=doel['gebruikersnaam']) if aan
                  else t("Account {naam} staat nu uit.", naam=doel['gebruikersnaam']), 'ok')
    return _terug()


@accounts_bp.post('/<int:gebruiker_id>/wachtwoord')
@beheerder_vereist
@rate_limit('accounts', 20, 600)
def wachtwoord(gebruiker_id):
    nieuw_wachtwoord = request.form.get('wachtwoord', '')
    conn = get_db()
    doel = haal_gebruiker_op_id(conn, gebruiker_id)
    if doel is None:
        flash(t("Dit account bestaat niet."), 'fout')
    elif doel['id'] == huidige_gebruiker()['id']:
        flash(t("Wijzig je eigen wachtwoord via je eigen account."), 'fout')
    elif (fout := wachtwoord_fout(nieuw_wachtwoord)) is not None:
        flash(fout, 'fout')
    else:
        try:
            zet_wachtwoord(conn, gebruiker_id, nieuw_wachtwoord)
        except OperationalError:
            flash(t(DATABASE_DRUK), 'fout')
        else:
            flash(t("Nieuw wachtwoord voor {naam} is ingesteld. Alle apparaten van {naam} zijn uitgelogd. "
                    "Geef het wachtwoord zelf door.", naam=doel['gebruikersnaam']), 'ok')
    return _terug()
