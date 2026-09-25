import sqlite3
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session, current_app
from werkzeug.security import check_password_hash
from pydantic import ValidationError

from app.database import get_db_connection, verwerk_reservering, CapaciteitVolFout
from app.schemas import ReserveringSchema
from app.services.email_service import stuur_bevestigingsmail_async

web_bp = Blueprint('web', __name__)

@web_bp.route('/')
def home():
    return render_template('index.html')

@web_bp.route('/privacy')
def privacy():
    return render_template('privacy.html')

@web_bp.route('/bevestiging')
def bevestiging():
    return render_template('bevestiging.html')

@web_bp.route('/login', methods=['GET', 'POST'])
def login():
    foutmelding = None
    if request.method == 'POST':
        gebruikersnaam = request.form.get('gebruikersnaam', '').strip()
        wachtwoord = request.form.get('wachtwoord', '')

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM personeel WHERE gebruikersnaam = ?', (gebruikersnaam,)).fetchone()
        conn.close()

        if user and check_password_hash(user['wachtwoord_hash'], wachtwoord):
            session['ingelogd'] = True
            session['gebruiker'] = user['gebruikersnaam']
            return redirect(url_for('web.overzicht'))
        else:
            foutmelding = "Ongeldige gebruikersnaam of wachtwoord!"

    return render_template('login.html', foutmelding=foutmelding)

@web_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('web.login'))

@web_bp.route('/overzicht')
def overzicht():
    if not session.get('ingelogd'):
        return redirect(url_for('web.login'))

    conn = get_db_connection()
    gekozen_datum = request.args.get('datum')

    if gekozen_datum:
        reserveringen = conn.execute(
            'SELECT * FROM reserveringen WHERE datum = ? ORDER BY tijd ASC', (gekozen_datum,)
        ).fetchall()
    else:
        reserveringen = conn.execute('SELECT * FROM reserveringen ORDER BY datum DESC, tijd ASC').fetchall()

    conn.close()
    return render_template('overzicht.html', reserveringen=reserveringen, gekozen_datum=gekozen_datum)

@web_bp.route('/reservering', methods=['POST'])
def nieuwe_reservering():
    json_data = request.get_json(silent=True)
    if not json_data:
        return jsonify({"status": "fout", "bericht": "Ongeldige JSON payload"}), 400

    try:
        valid_data = ReserveringSchema(**json_data)
    except ValidationError as e:
        return jsonify({"status": "fout", "bericht": "Datavalidatie mislukt", "details": e.errors()}), 422

    if valid_data.website:
        return jsonify({"status": "fout", "bericht": "Spam gedetecteerd."}), 400

    max_capaciteit = current_app.config['MAX_CAPACITEIT_PER_SLOT']
    conn = get_db_connection()
    try:
        unieke_id = verwerk_reservering(
            conn, max_capaciteit,
            naam=valid_data.naam, email=valid_data.email, telefoon=valid_data.telefoon,
            datum=valid_data.datum, tijd=valid_data.tijd, aantal=valid_data.aantal
        )
    except CapaciteitVolFout as e:
        return jsonify({
            "status": "fout",
            "bericht": f"Geen plek meer op dit tijdstip. Nog {e.vrij} plek(ken) beschikbaar."
        }), 400
    except sqlite3.OperationalError:
        return jsonify({"status": "fout", "bericht": "Database is momenteel druk, probeer het opnieuw."}), 503
    finally:
        conn.close()

    stuur_bevestigingsmail_async(
        ontvanger_email=valid_data.email,
        naam=valid_data.naam,
        datum=valid_data.datum,
        tijd=valid_data.tijd,
        aantal=valid_data.aantal,
        reservering_id=unieke_id
    )

    return jsonify({"status": "succes", "bericht": "Reservering opgeslagen!", "id": unieke_id}), 200

@web_bp.route('/verwijder/<reservering_id>', methods=['POST'])
def verwijder_reservering(reservering_id):
    if not session.get('ingelogd'):
        return redirect(url_for('web.login'))

    conn = get_db_connection()
    conn.execute('DELETE FROM reserveringen WHERE id = ?', (reservering_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('web.overzicht'))

@web_bp.route('/annuleren/<reservering_id>', methods=['GET', 'POST'])
def annuleren_klant(reservering_id):
    conn = get_db_connection()
    reservering = conn.execute('SELECT * FROM reserveringen WHERE id = ?', (reservering_id,)).fetchone()

    if not reservering:
        conn.close()
        return "Reservering niet gevonden of reeds geannuleerd.", 404

    if request.method == 'POST':
        conn.execute('DELETE FROM reserveringen WHERE id = ?', (reservering_id,))
        conn.commit()
        conn.close()
        return render_template('annuleren_bevestigd.html')

    conn.close()
    return render_template('annuleren_bevestigen.html', reservering=reservering)