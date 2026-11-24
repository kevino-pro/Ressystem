"""
Toegang tot de personeelspagina's: wie is er ingelogd, mag die hier komen, en is het account nog actief.

De sessiecookie bevat alleen de gebruikersnaam en een stempel van het wachtwoord. Rol en `actief`
worden bij elk verzoek uit de database gelezen: een uitgezet account of een gewijzigd wachtwoord
werkt daardoor direct, ook op een telefoon die nog ingelogd is.

Rollen: een beheerder mag alles; een medewerker mag reserveringen en de plattegrond bekijken en
tafelvoorstellen accepteren, maar geen tafels wijzigen, geen reserveringen verwijderen en geen
accounts beheren.

Automatisch uitloggen: een sessie die langer dan INACTIEF_MINUTEN_BEHEERDER (beheerder) of
INACTIEF_MINUTEN_MEDEWERKER (medewerker) minuten niets deed, vervalt. De gebruiker ziet op de
inlogpagina dat hij automatisch is uitgelogd.
"""
import hashlib
import hmac
import time
from functools import wraps

from flask import current_app, flash, g, jsonify, redirect, session, url_for

from app.database import get_db, haal_personeel_op
from app.taal import vertaal as t

MIN_WACHTWOORD_LENGTE = 12
MAX_WACHTWOORD_LENGTE = 128


def wachtwoord_fout(wachtwoord):
    """Melding voor een onbruikbaar nieuw wachtwoord, of None als het goed is."""
    if len(wachtwoord) < MIN_WACHTWOORD_LENGTE:
        return t("Het wachtwoord moet minstens {aantal} tekens hebben.", aantal=MIN_WACHTWOORD_LENGTE)
    if len(wachtwoord) > MAX_WACHTWOORD_LENGTE:
        return t("Het wachtwoord mag hoogstens {aantal} tekens hebben.", aantal=MAX_WACHTWOORD_LENGTE)
    return None


def sessie_stempel(wachtwoord_hash):
    """Korte vingerafdruk van de wachtwoordhash; verandert het wachtwoord, dan vervalt de sessie."""
    return hashlib.sha256(wachtwoord_hash.encode('utf-8')).hexdigest()[:16]


def start_sessie(gebruiker):
    """Zet de sessie van een succesvol ingelogde gebruiker (een rij uit de tabel personeel)."""
    session.clear()
    session['ingelogd'] = True
    session['gebruiker'] = gebruiker['gebruikersnaam']
    session['stempel'] = sessie_stempel(gebruiker['wachtwoord_hash'])
    session['laatst_actief'] = int(time.time())


def huidige_gebruiker():
    """
    De ingelogde, actieve gebruiker (een rij uit personeel) of None. Eén databasevraag per verzoek.
    Faalt dicht: een sessie zonder gebruikersnaam of stempel, een onbekend of uitgezet account of
    een stempel die niet meer klopt geeft None. Deed de sessie langer niets dan de grens van de rol
    (INACTIEF_MINUTEN_BEHEERDER of INACTIEF_MINUTEN_MEDEWERKER), dan geeft hij ook None en zet hij
    g.sessie_verlopen, zodat de inlogpagina kan zeggen dat de gebruiker automatisch is uitgelogd.
    """
    if 'gebruiker_geladen' in g:
        return g.gebruiker_geladen
    gebruiker = None
    naam = session.get('gebruiker')
    stempel = session.get('stempel')
    if session.get('ingelogd') and isinstance(naam, str) and isinstance(stempel, str):
        rij = haal_personeel_op(get_db(), naam)
        if (rij is not None and rij['actief']
                and hmac.compare_digest(stempel, sessie_stempel(rij['wachtwoord_hash']))):
            gebruiker = rij
            nu = int(time.time())
            grens = (current_app.config['INACTIEF_MINUTEN_BEHEERDER'] if rij['rol'] == 'beheerder'
                     else current_app.config['INACTIEF_MINUTEN_MEDEWERKER'])
            laatst = session.get('laatst_actief')
            if not isinstance(laatst, int):
                # Een sessie van voor deze fase: er is geen tijd bekend, dus niet meteen uitloggen.
                session['laatst_actief'] = nu
            elif nu - laatst > grens * 60:
                gebruiker = None
                g.sessie_verlopen = True
            elif nu - laatst >= 60:
                # Niet bij elk verzoek: dan verandert de cookie steeds en dat is nergens voor nodig.
                session['laatst_actief'] = nu
    g.gebruiker_geladen = gebruiker
    return gebruiker


def _niet_ingelogd(json_response):
    session.clear()
    if not json_response:
        if g.get('sessie_verlopen'):
            flash(t("Je bent automatisch uitgelogd omdat je een tijd niets deed. Log opnieuw in."), 'fout')
        return redirect(url_for('web.login'))
    return jsonify({"status": "fout", "bericht": t("Je bent uitgelogd. Log opnieuw in.")}), 401


def login_vereist(view=None, *, json_response=False):
    """Alleen voor ingelogd personeel. Te gebruiken als @login_vereist of @login_vereist(json_response=True)."""
    def decorator(functie):
        @wraps(functie)
        def wrapper(*args, **kwargs):
            if huidige_gebruiker() is None:
                return _niet_ingelogd(json_response)
            return functie(*args, **kwargs)
        return wrapper
    return decorator(view) if view is not None else decorator


def beheerder_vereist(view):
    """Alleen voor een ingelogde beheerder; een medewerker krijgt 403."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        gebruiker = huidige_gebruiker()
        if gebruiker is None:
            return _niet_ingelogd(False)
        if gebruiker['rol'] != 'beheerder':
            return t("Geen toegang."), 403
        return view(*args, **kwargs)
    return wrapper
