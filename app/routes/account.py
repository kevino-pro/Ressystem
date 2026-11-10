"""Het eigen account van ingelogd personeel: nu alleen het eigen wachtwoord wijzigen."""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy.exc import OperationalError
from werkzeug.security import check_password_hash

from app.database import get_db, haal_gebruiker_op_id, zet_wachtwoord
from app.security import rate_limit, valideer_csrf
from app.toegang import MIN_WACHTWOORD_LENGTE, huidige_gebruiker, login_vereist, sessie_stempel, wachtwoord_fout

account_bp = Blueprint('account', __name__, url_prefix='/account')
account_bp.before_request(valideer_csrf)


@account_bp.route('')
@login_vereist
def mijn_account():
    return render_template('account.html', actief='account', ik=huidige_gebruiker(), min_lengte=MIN_WACHTWOORD_LENGTE)


@account_bp.post('/wachtwoord')
@login_vereist
@rate_limit('eigen-wachtwoord', 10, 600)
def wijzig_wachtwoord():
    ik = huidige_gebruiker()
    huidig = request.form.get('huidig', '')
    nieuw = request.form.get('nieuw', '')
    herhaal = request.form.get('herhaal', '')
    if not check_password_hash(ik['wachtwoord_hash'], huidig):
        flash("Je huidige wachtwoord klopt niet.", 'fout')
    elif (fout := wachtwoord_fout(nieuw)) is not None:
        flash(fout, 'fout')
    elif nieuw != herhaal:
        flash("De twee nieuwe wachtwoorden zijn niet hetzelfde.", 'fout')
    elif nieuw == huidig:
        flash("Kies een ander wachtwoord dan je huidige.", 'fout')
    else:
        conn = get_db()
        try:
            zet_wachtwoord(conn, ik['id'], nieuw)
        except OperationalError:
            flash("Het lukte niet om op te slaan. Probeer het opnieuw.", 'fout')
        else:
            # Het stempel hoort bij het wachtwoord: werk het bij, anders logt deze wijziging jezelf uit.
            # Andere apparaten met dit account blijven met het oude stempel achter en zijn dus uitgelogd.
            session['stempel'] = sessie_stempel(haal_gebruiker_op_id(conn, ik['id'])['wachtwoord_hash'])
            flash("Je wachtwoord is gewijzigd. Op je andere apparaten moet je opnieuw inloggen.", 'ok')
    return redirect(url_for('account.mijn_account'))
