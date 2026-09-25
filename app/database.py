import sqlite3
from flask import current_app
from werkzeug.security import generate_password_hash

def get_db_connection():
    conn = sqlite3.connect(current_app.config['DATABASE_PAD'], timeout=15.0)
    conn.row_factory = sqlite3.Row

    # Schakel WAL-mode en busy_timeout in voor betere concurrency
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn

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
