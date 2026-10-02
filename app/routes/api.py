import logging
import anthropic
from flask import Blueprint, request, jsonify, current_app
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.database import get_db, verwerk_reservering, CapaciteitVolFout
from app.schemas import AIWebhookSchema, AIReserveringExtractieSchema
from app.services.ai_service import sanitize_user_input, verwerk_tekst_met_anthropic
from app.services.email_service import stuur_bevestigingsmail_async
from app.security import constant_time_equals, rate_limit_check

logger = logging.getLogger(__name__)
_REQUIRED_RESERVATION_FIELDS = ("naam", "email", "telefoon", "datum", "tijd", "aantal")

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')


def _validation_fields(error: ValidationError) -> list[str]:
    return sorted({str(issue["loc"][0]) for issue in error.errors() if issue.get("loc")})


def _missing_reservation_fields(reservation: AIReserveringExtractieSchema) -> list[str]:
    missing_fields = []
    for field in _REQUIRED_RESERVATION_FIELDS:
        value = getattr(reservation, field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing_fields.append(field)
    return missing_fields


@api_bp.before_request
def valideer_api_key():
    """Beveiligings-guard voor alle API-routes."""
    api_key = request.headers.get("X-API-Key")
    if not rate_limit_check('api', 120, 60):
        return jsonify({"status": "fout", "bericht": "Te veel verzoeken."}), 429
    if not constant_time_equals(api_key, current_app.config.get('WEBHOOK_API_KEY')):
        if not rate_limit_check('api-fout', 10, 300):
            return jsonify({"status": "fout", "bericht": "Te veel verzoeken."}), 429
        return jsonify({"status": "fout", "bericht": "Unauthorized"}), 401


@api_bp.route('/ai-reservering', methods=['POST'])
def ai_webhook_reservering():
    json_data = request.get_json(silent=True)
    if not isinstance(json_data, dict):
        return jsonify({"status": "fout", "bericht": "Ongeldige JSON payload"}), 400

    try:
        payload = AIWebhookSchema(**json_data)
    except ValidationError as error:
        return jsonify({
            "status": "fout",
            "bericht": "Webhook bevat ongeldige invoer.",
            "velden": _validation_fields(error),
        }), 400

    clean_text = sanitize_user_input(payload.klant_tekst)

    try:
        geparsed_reservering = verwerk_tekst_met_anthropic(clean_text)
    except anthropic.AuthenticationError:
        logger.critical("Anthropic-authenticatie mislukt; status=500.")
        return jsonify({"status": "fout", "bericht": "AI-service authenticatiefout."}), 500
    except anthropic.RateLimitError:
        logger.warning("Anthropic rate limit bereikt; status=503.")
        return jsonify({"status": "fout", "bericht": "AI-service tijdelijk overbelast."}), 503
    except anthropic.APITimeoutError:
        logger.warning("Timeout bij Anthropic; status=503.")
        return jsonify({"status": "fout", "bericht": "AI-service tijdelijk onbereikbaar."}), 503
    except (anthropic.APIConnectionError, anthropic.InternalServerError):
        logger.warning("Anthropic upstream service is tijdelijk onbereikbaar; status=503.")
        return jsonify({"status": "fout", "bericht": "AI-service tijdelijk onbereikbaar."}), 503
    except anthropic.BadRequestError:
        logger.error("Anthropic heeft het extractieverzoek afgewezen; status=400.")
        return jsonify({"status": "fout", "bericht": "AI-service kon de invoer niet verwerken."}), 400
    except anthropic.APIStatusError as error:
        logger.error("Anthropic API-statusfout; upstream_status=%s.", error.status_code)
        if error.status_code >= 500:
            return jsonify({"status": "fout", "bericht": "AI-service tijdelijk onbereikbaar."}), 503
        return jsonify({"status": "fout", "bericht": "AI-service kon het verzoek niet verwerken."}), 400
    except anthropic.APIError:
        logger.error("Onverwachte Anthropic API-fout; status=503.")
        return jsonify({"status": "fout", "bericht": "AI-service tijdelijk onbereikbaar."}), 503
    except ValidationError as error:
        logger.warning("Anthropic retourneerde ongeldige reserveringsgegevens; status=400.")
        return jsonify({
            "status": "fout",
            "bericht": "AI retourneerde ongeldige reserveringsgegevens.",
            "ontbrekende_velden": _validation_fields(error),
        }), 400
    except ValueError:
        logger.error("AI-verwerking kon geen geldige reservering opleveren; status=500.")
        return jsonify({"status": "fout", "bericht": "AI-verwerking is mislukt."}), 500
    except Exception:
        logger.error("Onverwachte AI-verwerkingsfout; status=500.")
        return jsonify({"status": "fout", "bericht": "AI-verwerking is mislukt."}), 500

    ontbrekende_velden = _missing_reservation_fields(geparsed_reservering)

    if ontbrekende_velden:
        return jsonify({
            "status": "fout",
            "bericht": "Vul de ontbrekende reserveringsgegevens aan.",
            "ontbrekende_velden": ontbrekende_velden,
        }), 400

    max_capaciteit = current_app.config['MAX_CAPACITEIT_PER_SLOT']
    reservation_data = geparsed_reservering.model_dump(mode="json")
    try:
        conn = get_db()
        unieke_id = verwerk_reservering(
            conn,
            max_capaciteit,
            naam=reservation_data["naam"],
            email=reservation_data["email"],
            telefoon=reservation_data["telefoon"],
            datum=reservation_data["datum"],
            tijd=reservation_data["tijd"],
            aantal=reservation_data["aantal"]
        )
    except CapaciteitVolFout as error:
        return jsonify({
            "status": "fout",
            "bericht": f"Geen capaciteit op {geparsed_reservering.datum} om {geparsed_reservering.tijd}. Nog {error.vrij} plek(ken) vrij.",
            "geparsed_data": reservation_data
        }), 400
    except OperationalError:
        logger.error("Databasebewerking mislukt; status=503.")
        return jsonify({"status": "fout", "bericht": "Database tijdelijk onbereikbaar."}), 503

    try:
        stuur_bevestigingsmail_async(
            ontvanger_email=reservation_data["email"],
            naam=reservation_data["naam"],
            datum=reservation_data["datum"],
            tijd=reservation_data["tijd"],
            aantal=reservation_data["aantal"],
            reservering_id=unieke_id
        )
    except Exception:
        logger.error("Reservering opgeslagen; e-mailstart mislukt; reservering_id=%s.", unieke_id)

    return jsonify({
        "status": "succes",
        "bericht": "AI-reservering succesvol verwerkt en opgeslagen",
        "reservering_id": unieke_id,
        "geextracted_data": reservation_data
    }), 201