from sqlalchemy.exc import OperationalError
from flask import Blueprint, request, jsonify, current_app
from pydantic import ValidationError

from app.database import get_db, verwerk_reservering, CapaciteitVolFout
from app.schemas import AIWebhookSchema
from app.services.ai_service import sanitize_user_input, verwerk_tekst_met_anthropic
from app.services.email_service import stuur_bevestigingsmail_async

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

@api_bp.before_request
def valideer_api_key():
    """Geldt voor elke route onder /api/v1, niet alleen de huidige — geen decorator die je kunt vergeten."""
    api_key = request.headers.get("X-API-Key")
    if not api_key or api_key != current_app.config['WEBHOOK_API_KEY']:
        return jsonify({"status": "fout", "bericht": "Unauthorized"}), 401

@api_bp.route('/ai-reservering', methods=['POST'])
def ai_webhook_reservering():
    json_data = request.get_json(silent=True)
    if not json_data:
        return jsonify({"status": "fout", "bericht": "Ongeldige JSON payload"}), 400

    try:
        payload = AIWebhookSchema(**json_data)
    except ValidationError as e:
        return jsonify({"status": "fout", "details": e.errors()}), 400

    clean_text = sanitize_user_input(payload.klant_tekst)

    try:
        geparsed_reservering = verwerk_tekst_met_anthropic(clean_text)
    except ValidationError as e:
        return jsonify({
            "status": "fout",
            "bericht": "AI extractie voldeed niet aan het datum/tijd formaat (YYYY-MM-DD HH:MM)",
            "details": e.errors()
        }), 400
    except ValueError as e:
        return jsonify({"status": "fout", "details": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "fout", "bericht": f"AI Verwerking mislukt: {str(e)}"}), 500

    max_capaciteit = current_app.config['MAX_CAPACITEIT_PER_SLOT']
    conn = get_db()
    try:
        unieke_id = verwerk_reservering(
            conn, max_capaciteit,
            naam=geparsed_reservering.naam, email=geparsed_reservering.email,
            telefoon=geparsed_reservering.telefoon, datum=geparsed_reservering.datum,
            tijd=geparsed_reservering.tijd, aantal=geparsed_reservering.aantal
        )
    except CapaciteitVolFout as e:
        return jsonify({
            "status": "fout",
            "bericht": f"Geen capaciteit op {geparsed_reservering.datum} om {geparsed_reservering.tijd}. Nog {e.vrij} plek(ken) vrij.",
            "geparsed_data": geparsed_reservering.model_dump()
        }), 400
    except OperationalError:
        return jsonify({"status": "fout", "bericht": "Database druk, probeer opnieuw."}), 503

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