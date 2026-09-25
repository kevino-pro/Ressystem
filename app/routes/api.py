import uuid
import sqlite3
from functools import wraps
from flask import Blueprint, request, jsonify, current_app
from pydantic import ValidationError

from app.database import get_db_connection
from app.schemas import AIWebhookSchema
from app.services.ai_service import sanitize_user_input, verwerk_tekst_met_anthropic
from app.services.email_service import stuur_bevestigingsmail_async

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get("X-API-Key")
        if not api_key or api_key != current_app.config['WEBHOOK_API_KEY']:
            return jsonify({"status": "fout", "bericht": "Ongeldige of ontbrekende API-sleutel"}), 401
        return f(*args, **kwargs)
    return decorated

@api_bp.route('/ai-reservering', methods=['POST'])
@require_api_key
def ai_webhook_reservering():
    json_data = request.get_json(silent=True)
    if not json_data:
        return jsonify({"status": "fout", "bericht": "Ongeldige JSON payload"}), 400

    try:
        payload = AIWebhookSchema(**json_data)
    except ValidationError as e:
        return jsonify({"status": "fout", "bericht": "Payload validatie mislukt", "details": e.errors()}), 422

    clean_text = sanitize_user_input(payload.klant_tekst)

    try:
        geparsed_reservering = verwerk_tekst_met_anthropic(clean_text)
    except ValidationError as e:
        return jsonify({
            "status": "fout", 
            "bericht": "AI extractie voldeed niet aan het datum/tijd formaat (YYYY-MM-DD HH:MM)",
            "details": e.errors()
        }), 422
    except Exception as e:
        return jsonify({"status": "fout", "bericht": f"AI Verwerking mislukt: {str(e)}"}), 500

    max_capaciteit = current_app.config['MAX_CAPACITEIT_PER_SLOT']
    conn = get_db_connection()
    try:
        with conn:
            conn.execute('BEGIN EXCLUSIVE')
            resultaat = conn.execute(
                'SELECT SUM(aantal) as totaal FROM reserveringen WHERE datum = ? AND tijd = ?',
                (geparsed_reservering.datum, geparsed_reservering.tijd)
            ).fetchone()

            huidige_gasten = resultaat['totaal'] if resultaat['totaal'] else 0

            if huidige_gasten + geparsed_reservering.aantal > max_capaciteit:
                vrij = max_capaciteit - huidige_gasten
                return jsonify({
                    "status": "fout",
                    "bericht": f"Geen capaciteit op {geparsed_reservering.datum} om {geparsed_reservering.tijd}. Nog {vrij} plek(ken) vrij.",
                    "geparsed_data": geparsed_reservering.model_dump()
                }), 400

            unieke_id = str(uuid.uuid4())[:8]
            conn.execute(
                '''INSERT INTO reserveringen (id, naam, email, telefoon, datum, tijd, aantal)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (unieke_id, geparsed_reservering.naam, geparsed_reservering.email, 
                 geparsed_reservering.telefoon, geparsed_reservering.datum, 
                 geparsed_reservering.tijd, geparsed_reservering.aantal)
            )

        if "@" in geparsed_reservering.email and "geen-email" not in geparsed_reservering.email:
            stuur_bevestigingsmail_async(
                ontvanger_email=geparsed_reservering.email,
                naam=geparsed_reservering.naam,
                datum=geparsed_reservering.datum,
                tijd=geparsed_reservering.tijd,
                aantal=geparsed_reservering.aantal,
                reservering_id=unieke_id
            )

        return jsonify({
            "status": "succes", 
            "bericht": "AI-reservering succesvol verwerkt en opgeslagen",
            "reservering_id": unieke_id,
            "geextracted_data": geparsed_reservering.model_dump()
        }), 200

    except sqlite3.OperationalError:
        return jsonify({"status": "fout", "bericht": "Database druk, probeer opnieuw."}), 503
    finally:
        conn.close()