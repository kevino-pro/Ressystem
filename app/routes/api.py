import logging
import anthropic
from flask import Blueprint, request, jsonify, current_app
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.database import get_db, verwerk_reservering, CapaciteitVolFout
from app.schemas import AIWebhookSchema, AIReserveringExtractieSchema
from app.services.ai_service import sanitize_user_input, verwerk_tekst_met_anthropic
from app.services.email_service import stuur_bevestigingsmail_async

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
    if not api_key or api_key != current_app.config['WEBHOOK_API_KEY']:
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
        logger.critical("Anthropic-authenticatie mislukt.", exc_info=True)
        return jsonify({"status": "fout", "bericht": "AI-service authenticatiefout."}), 500
    except anthropic.RateLimitError:
        logger.exception("Anthropic rate limit bereikt.")
        return jsonify({"status": "fout", "bericht": "AI-service tijdelijk overbelast."}), 503
    except (anthropic.APIConnectionError, anthropic.InternalServerError):
        logger.exception("Anthropic upstream service is tijdelijk onbereikbaar.")
        return jsonify({"status": "fout", "bericht": "AI-service tijdelijk onbereikbaar."}), 503
    except anthropic.BadRequestError:
        logger.exception("Anthropic heeft het extractieverzoek afgewezen.")
        return jsonify({"status": "fout", "bericht": "AI-service kon de invoer niet verwerken."}), 400
    except anthropic.APIStatusError as error:
        logger.exception("Anthropic API-statusfout (%s).", error.status_code)
        if error.status_code >= 500:
            return jsonify({"status": "fout", "bericht": "AI-service tijdelijk onbereikbaar."}), 503
        return jsonify({"status": "fout", "bericht": "AI-service kon het verzoek niet verwerken."}), 400
    except anthropic.APIError:
        logger.exception("Onverwachte Anthropic API-fout.")
        return jsonify({"status": "fout", "bericht": "AI-service tijdelijk onbereikbaar."}), 503
    except ValidationError as error:
        logger.exception("Anthropic retourneerde ongeldige reserveringsgegevens.")
        return jsonify({
            "status": "fout",
            "bericht": "AI retourneerde ongeldige reserveringsgegevens.",
            "ontbrekende_velden": _validation_fields(error),
        }), 400
    except ValueError:
        logger.exception("AI-verwerking kon geen geldige reservering opleveren.")
        return jsonify({"status": "fout", "bericht": "AI-verwerking is mislukt."}), 500
    except Exception:
        logger.exception("Uncaught exception tijdens AI-verwerking")
        return jsonify({"status": "fout", "bericht": "AI-verwerking is mislukt."}), 500

    ontbrekende_velden = _missing_reservation_fields(geparsed_reservering)

    if ontbrekende_velden:
        return jsonify({
            "status": "fout",
            "bericht": "Vul de ontbrekende reserveringsgegevens aan.",
            "ontbrekende_velden": ontbrekende_velden,
        }), 400

    max_capaciteit = current_app.config['MAX_CAPACITEIT_PER_SLOT']
    try:
        conn = get_db()
        unieke_id = verwerk_reservering(
            conn,
            max_capaciteit,
            naam=geparsed_reservering.naam,
            email=geparsed_reservering.email,
            telefoon=geparsed_reservering.telefoon,
            datum=geparsed_reservering.datum,
            tijd=geparsed_reservering.tijd,
            aantal=geparsed_reservering.aantal
        )
    except CapaciteitVolFout as error:
        return jsonify({
            "status": "fout",
            "bericht": f"Geen capaciteit op {geparsed_reservering.datum} om {geparsed_reservering.tijd}. Nog {error.vrij} plek(ken) vrij.",
            "geparsed_data": geparsed_reservering.model_dump()
        }), 400
    except OperationalError:
        logger.exception("Databaseverbinding of reserveringsquery is mislukt.")
        return jsonify({"status": "fout", "bericht": "Database tijdelijk onbereikbaar."}), 503

    try:
        stuur_bevestigingsmail_async(
            ontvanger_email=geparsed_reservering.email,
            naam=geparsed_reservering.naam,
            datum=geparsed_reservering.datum,
            tijd=geparsed_reservering.tijd,
            aantal=geparsed_reservering.aantal,
            reservering_id=unieke_id
        )
    except Exception:
        logger.exception("Reservering %s opgeslagen, maar e-mail kon niet worden gestart.", unieke_id)

    return jsonify({
        "status": "succes",
        "bericht": "AI-reservering succesvol verwerkt en opgeslagen",
        "reservering_id": unieke_id,
        "geextracted_data": geparsed_reservering.model_dump()
    }), 201