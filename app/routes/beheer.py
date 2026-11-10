"""
Beheerroutes die door een geplande taak worden aangeroepen, niet door mensen.
Beveiligd met een eigen sleutel (BEHEER_API_KEY), los van de n8n-sleutel. Zonder sleutel bestaat
de route niet (404), zodat een installatie zonder geplande taak niets openzet.
"""
import logging

from flask import Blueprint, abort, current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db, tel_of_schoon_oude_reserveringen, wis_allergieen_voor
from app.herinnering import verstuur_herinneringen
from app.security import constant_time_equals, rate_limit_check

logger = logging.getLogger(__name__)

MIN_SLEUTEL_LENGTE = 32

beheer_bp = Blueprint('beheer', __name__, url_prefix='/beheer')


@beheer_bp.before_request
def valideer_beheer_key():
    verwacht = current_app.config.get('BEHEER_API_KEY') or ''
    if len(verwacht) < MIN_SLEUTEL_LENGTE:
        if verwacht:
            logger.error("[BEHEER] BEHEER_API_KEY is korter dan %s tekens; beheerroutes staan uit.", MIN_SLEUTEL_LENGTE)
        abort(404)
    if not rate_limit_check('beheer', 10, 3600):
        return jsonify({"status": "fout", "bericht": "Te veel verzoeken."}), 429
    if not constant_time_equals(request.headers.get('X-Beheer-Key'), verwacht):
        logger.warning("[BEHEER] Verzoek met ongeldige of ontbrekende sleutel geweigerd.")
        return jsonify({"status": "fout", "bericht": "Unauthorized"}), 401
    return None


@beheer_bp.post('/opschonen')
def opschonen():
    """
    Verwijdert reserveringen buiten de bewaartermijn (hetzelfde werk als `flask purge-retention --uitvoeren`)
    en wist de allergieen van reserveringen van voor vandaag (tijdzone van het restaurant).
    """
    vandaag = current_app.config['REGELS'].nu().date().isoformat()
    try:
        verwijderd = tel_of_schoon_oude_reserveringen(get_db(), True)
        allergieen_gewist = wis_allergieen_voor(get_db(), vandaag)
    except SQLAlchemyError:
        logger.error("[BEHEER] Opschonen mislukt door een databasefout.")
        return jsonify({"status": "fout", "bericht": "Opschonen mislukt door een databasefout."}), 503
    logger.info("[BEHEER] Opschonen uitgevoerd; %s reservering(en) verwijderd, %s keer allergieen gewist.",
                verwijderd, allergieen_gewist)
    return jsonify({"status": "succes", "verwijderd": verwijderd, "allergieen_gewist": allergieen_gewist})


@beheer_bp.post('/herinneringen')
def herinneringen():
    """
    Verstuurt de herinneringsmails voor morgen, vanaf het uur uit [herinnering] (tijdzone van het restaurant).
    Elke reservering krijgt er hoogstens een. Per aanroep een beperkt aantal: zolang `resterend` meer dan 0 is,
    roept de geplande taak opnieuw aan. Zonder [herinnering] doet de route niets.
    """
    leeg = {"verstuurd": 0, "mislukt": 0, "resterend": 0}
    instelling = current_app.config.get('HERINNERING')
    if instelling is None:
        return jsonify({"status": "uit", **leeg})
    if current_app.config['REGELS'].nu().hour < instelling.uur:
        return jsonify({"status": "te_vroeg", **leeg})
    try:
        verstuurd, mislukt, resterend = verstuur_herinneringen(get_db(), current_app.config)
    except SQLAlchemyError:
        logger.error("[BEHEER] Herinneringen mislukt door een databasefout.")
        return jsonify({"status": "fout", "bericht": "Herinneringen mislukt door een databasefout."}), 503
    logger.info("[BEHEER] Herinneringen: %s verstuurd, %s mislukt, %s nog te doen.", verstuurd, mislukt, resterend)
    return jsonify({"status": "succes", "verstuurd": verstuurd, "mislukt": mislukt, "resterend": resterend})
