import sqlite3
import uuid
from flask import current_app
from werkzeug.security import generate_password_hash

class CapaciteitVolFout(Exception):
    """Geen ruimte meer op het gevraagde tijdslot. `vrij` is het aantal resterende plekken (kan <= 0 zijn)."""
    def __init__(self, vrij):
        self.vrij = vrij
        super().__init__(f"Geen capaciteit: nog {vrij} plek(ken) vrij.")

def get_db_connection():
    conn = sqlite3.connect(current_app.config['DATABASE_PAD'], timeout=15.0)
    conn.row_factory = sqlite3.Row

    # Schakel WAL-mode en busy_timeout in voor betere concurrency
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn

def verwerk_reservering(conn, max_capaciteit, naam, email, telefoon, datum, tijd, aantal):
    """
    Enige plek waar een reservering wordt weggeschreven. Wordt door web.py (formulier)
    en api.py (AI-webhook) gebruikt zodat de capaciteitsregel maar op één plek staat.

    BEGIN EXCLUSIVE serialiseert de check + insert: zonder dit kunnen twee gelijktijdige
    boekingen op hetzelfde slot allebei de (verouderde) capaciteit lezen en samen over
    de limiet gaan. Bij CapaciteitVolFout rollt sqlite3's context manager de transactie
    terug, dus er wordt niets ingevoegd.
    """
    with conn:
        conn.execute('BEGIN EXCLUSIVE')
        resultaat = conn.execute(
            'SELECT SUM(aantal) as totaal FROM reserveringen WHERE datum = ? AND tijd = ?',
            (datum, tijd)
        ).fetchone()

        huidige_gasten = resultaat['totaal'] if resultaat['totaal'] else 0

        if huidige_gasten + aantal > max_capaciteit:
            raise CapaciteitVolFout(max_capaciteit - huidige_gasten)

        unieke_id = str(uuid.uuid4())[:8]
        conn.execute(
            '''INSERT INTO reserveringen (id, naam, email, telefoon, datum, tijd, aantal)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (unieke_id, naam, email, telefoon, datum, tijd, aantal)
        )

    return unieke_id

def schonen_oude_reserveringen():
    conn = get_db_connection()
    retentie_dagen = current_app.config['RETENTIE_DAGEN_AVG']
    conn.execute(f"DELETE FROM reserveringen WHERE datum < date('now', '-{retentie_dagen} days')")
    conn.commit()
    conn.close()

def init_db():
    conn = get_db_connection()
    with conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS reserveringen (
                id TEXT PRIMARY KEY,
                naam TEXT NOT NULL,
                email TEXT NOT NULL,
                telefoon TEXT NOT NULL,
                datum TEXT NOT NULL,
                tijd TEXT NOT NULL,
                aantal INTEGER NOT NULL,
                aangemaakt_op DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS personeel (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gebruikersnaam TEXT UNIQUE NOT NULL,
                wachtwoord_hash TEXT NOT NULL
            )
        ''')
        admin_user = conn.execute('SELECT id FROM personeel WHERE gebruikersnaam = ?', ('admin',)).fetchone()
        if not admin_user:
            initial_pw = current_app.config['ADMIN_INITIAL_PASSWORD']
            conn.execute(
                'INSERT INTO personeel (gebruikersnaam, wachtwoord_hash) VALUES (?, ?)',
                ('admin', generate_password_hash(initial_pw))
            )
    conn.close()
    schonen_oude_reserveringen()
