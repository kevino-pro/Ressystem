"""
Toegang tot de personeelspagina's: wie is er ingelogd, mag die hier komen, en is het account nog actief.

De sessiecookie bevat alleen de gebruikersnaam en een stempel van het wachtwoord. Rol en `actief`
worden bij elk verzoek uit de database gelezen: een uitgezet account of een gewijzigd wachtwoord
werkt daardoor direct, ook op een telefoon die nog ingelogd is.

Rollen: een beheerder mag alles; een medewerker mag reserveringen en de plattegrond bekijken en
tafels toewijzen, maar geen reserveringen verwijderen en geen accounts beheren.
"""
import hashlib
import hmac
from functools import wraps

from flask import g, jsonify, redirect, session, url_for

from app.database import get_db, haal_personeel_op

MIN_WACHTWOORD_LENGTE = 12
MAX_WACHTWOORD_LENGTE = 128


def sessie_stempel(wachtwoord_hash):
    """Korte vingerafdruk van de wachtwoordhash; verandert het wachtwoord, dan vervalt de sessie."""
    return hashlib.sha256(wachtwoord_hash.encode('utf-8')).hexdigest()[:16]


def start_sessie(gebruiker):
    """Zet de sessie van een succesvol ingelogde gebruiker (een rij uit de tabel personeel)."""
    session.clear()
    session['ingelogd'] = True
    session['gebruiker'] = gebruiker['gebruikersnaam']
    session['stempel'] = sessie_stempel(gebruiker['wachtwoord_hash'])


def huidige_gebruiker():
    """
    De ingelogde, actieve gebruiker (een rij uit personeel) of None. Eén databasevraag per verzoek.
    Faalt dicht: een sessie zonder gebruikersnaam of stempel, een onbekend of uitgezet account of
    een stempel die niet meer klopt geeft None.
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
    g.gebruiker_geladen = gebruiker
    return gebruiker


def _niet_ingelogd(json_response):
    session.clear()
    if json_response:
        return jsonify({"status": "fout", "bericht": "Je bent uitgelogd. Log opnieuw in."}), 401
    return redirect(url_for('web.login'))


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
            return "Geen toegang.", 403
        return view(*args, **kwargs)
    return wrapper
