"""Hulpjes voor tests die als personeel ingelogd moeten zijn."""
from sqlalchemy import delete, func, insert
from werkzeug.security import generate_password_hash

from app.database import get_db, metadata, personeel
from app.toegang import sessie_stempel

WACHTWOORD = "testwachtwoord-123"
_HASH = generate_password_hash(WACHTWOORD)  # eenmalig: hashen is bewust traag


def zet_gebruiker(app, naam="tester", rol="beheerder", actief=True, wachtwoord_hash=None):
    """Maakt (of vervangt) een account in de database van `app`; geeft de wachtwoordhash terug."""
    wachtwoord_hash = wachtwoord_hash or _HASH
    with app.app_context():
        conn = get_db()
        metadata.create_all(conn)
        conn.commit()
        with conn.begin():
            conn.execute(delete(personeel).where(func.lower(personeel.c.gebruikersnaam) == naam.lower()))
            conn.execute(insert(personeel).values(
                gebruikersnaam=naam, wachtwoord_hash=wachtwoord_hash, rol=rol, actief=actief))
    return wachtwoord_hash


def log_in(app, client, naam="tester", rol="beheerder"):
    """Maakt een account aan en zet de sessie van `client` zoals /login dat doet."""
    wachtwoord_hash = zet_gebruiker(app, naam, rol)
    with client.session_transaction() as sessie:
        sessie["ingelogd"] = True
        sessie["gebruiker"] = naam
        sessie["stempel"] = sessie_stempel(wachtwoord_hash)
