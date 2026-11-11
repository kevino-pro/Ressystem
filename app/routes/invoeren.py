"""
Reserveringen die het personeel zelf invoert: telefonisch of aan de deur (binnenloper).
Een binnenloper staat meteen op "nu", zodat de capaciteit voor online gasten direct klopt.

Het personeel mag buiten de online regels boeken (een grote groep, een tijd na de laatste online
begintijd). Wordt het voller dan het restaurant aankan, zijn alle kinderstoelen al bezet of is het
restaurant die dag gesloten, dan toont de pagina eerst een waarschuwing. Pas na "Toch opslaan"
wordt de reservering bewaard. Er wordt nooit iets geblokkeerd behalve een dag in het verleden,
een ongeldig veld of een dubbele boeking.
"""
from datetime import date, time
from types import SimpleNamespace

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.database import DubbeleReserveringFout, drukte_bij, get_db, verwerk_reservering
from app.schemas import MAX_PERSONEN_PERSONEEL, PersoneelReserveringSchema
from app.security import rate_limit, valideer_csrf
from app.services.email_service import stuur_bevestigingsmail_async
from app.taal import TAALNAMEN, huidige_taal, vertaal as t
from app.toegang import huidige_gebruiker, login_vereist

invoeren_bp = Blueprint('invoeren', __name__, url_prefix='/reservering')

BINNENLOPER_NAAM = "Binnenloper"
invoeren_bp.before_request(valideer_csrf)

VELDNAMEN = {  # Nederlands; vertaald bij het tonen
    'naam': "de naam", 'telefoon': "het telefoonnummer", 'email': "het e-mailadres", 'datum': "de datum",
    'tijd': "de tijd", 'aantal': f"het aantal personen (1 tot {MAX_PERSONEN_PERSONEEL})",
    'opmerking': "de opmerking (maximaal 300 tekens)", 'kinderstoelen': "het aantal kinderstoelen",
    'allergieen': "de allergieën (maximaal 200 tekens)", 'bron': "de soort reservering",
    'taal': "de taal van de gast",
}


def _formulier(waarden, status=200, fout=None, waarschuwingen=None):
    regels = current_app.config['REGELS']
    return render_template(
        'reservering_nieuw.html', actief='overzicht', w=waarden, fout=fout, waarschuwingen=waarschuwingen or [],
        regels=regels, vandaag=regels.nu().date(), max_personen=MAX_PERSONEN_PERSONEEL, taalnamen=TAALNAMEN,
    ), status


def _waarschuwingen(regels, gegevens):
    """Wat het personeel moet weten voordat het opslaat. Een lege lijst betekent: zonder vragen opslaan."""
    datum, tijd = gegevens.datum.isoformat(), gegevens.tijd.strftime("%H:%M")
    gasten, stoelen = drukte_bij(get_db(), datum, tijd, regels.zitduur_minuten)
    lijst = []
    if gegevens.datum in regels.sluitingsdagen or not regels.blokken_op(gegevens.datum):
        lijst.append(t("Het restaurant is op deze dag gesloten."))
    if gasten + gegevens.aantal > regels.max_gasten_tegelijk:
        lijst.append(t("Rond {tijd} zitten er dan {gasten} gasten tegelijk; het maximum is {maximum}.",
                       tijd=tijd, gasten=gasten + gegevens.aantal, maximum=regels.max_gasten_tegelijk))
    if gegevens.kinderstoelen and stoelen + gegevens.kinderstoelen > regels.kinderstoelen:
        lijst.append(t("Er zijn dan {nodig} kinderstoelen nodig; het restaurant heeft er {aantal}.",
                       nodig=stoelen + gegevens.kinderstoelen, aantal=regels.kinderstoelen))
    return lijst


def _ruimtetekst(regels, dag, tijdstip, aantal, kinderstoelen):
    """
    De zin onder het formulier: past deze groep, of wat het personeel anders moet weten. Dezelfde controle als
    bij het opslaan (_waarschuwingen); geeft (tekst, let_op) terug en bewaart niets.
    """
    waarschuwingen = _waarschuwingen(regels, SimpleNamespace(datum=dag, tijd=tijdstip, aantal=aantal, kinderstoelen=kinderstoelen))
    if waarschuwingen:
        return " ".join(waarschuwingen), True
    gasten, _ = drukte_bij(get_db(), dag.isoformat(), tijdstip.strftime("%H:%M"), regels.zitduur_minuten)
    return t("Rond {tijd} is er plek; er blijven {vrij} van {maximum} plekken vrij.", tijd=tijdstip.strftime("%H:%M"),
             vrij=regels.max_gasten_tegelijk - gasten - aantal, maximum=regels.max_gasten_tegelijk), False


@invoeren_bp.route('/ruimte', methods=['GET'])
@login_vereist(json_response=True)
@rate_limit('personeel-ruimte', 120, 600, json_response=True)
def ruimte():
    """Hulp voor het formulier: is er plek op deze dag en tijd? GET /reservering/ruimte?datum=...&tijd=...&aantal=..."""
    regels = current_app.config['REGELS']
    try:
        dag = date.fromisoformat(request.args.get('datum', ''))
        tijdstip = time.fromisoformat(request.args.get('tijd', ''))
        aantal = int(request.args.get('aantal', ''))
        kinderstoelen = int(request.args.get('kinderstoelen') or 0)
    except ValueError:
        return jsonify({"status": "fout"}), 400
    if not 1 <= aantal <= MAX_PERSONEN_PERSONEEL or not 0 <= kinderstoelen <= 20:
        return jsonify({"status": "fout"}), 400
    tekst, let_op = _ruimtetekst(regels, dag, tijdstip, aantal, kinderstoelen)
    return jsonify({"status": "succes", "tekst": tekst, "let_op": let_op})


@invoeren_bp.route('/nieuw', methods=['GET'])
@login_vereist
def nieuw():
    regels = current_app.config['REGELS']
    if request.args.get('bron') == 'binnenloper':
        nu = regels.nu()
        afgerond = nu.minute - nu.minute % 5  # het tijdveld werkt per 5 minuten
        waarden = {'bron': 'binnenloper', 'datum': nu.date().isoformat(), 'tijd': f"{nu.hour:02d}:{afgerond:02d}",
                   'aantal': '2'}
    else:
        waarden = {'bron': 'telefoon', 'datum': request.args.get('datum') or regels.nu().date().isoformat(),
                   'aantal': '2'}
    waarden['taal'] = huidige_taal()  # de taal waarin het personeel de site nu ziet; aan te passen per gast
    return _formulier(waarden)


@invoeren_bp.route('/nieuw', methods=['POST'])
@login_vereist
@rate_limit('personeel-reservering', 60, 600)
def opslaan():
    regels = current_app.config['REGELS']
    waarden = request.form.to_dict()
    waarden.pop('csrf_token', None)
    gegevens = {k: v for k, v in waarden.items() if k in PersoneelReserveringSchema.model_fields}
    if gegevens.get('bron') == 'binnenloper' and not (gegevens.get('naam') or '').strip():
        gegevens['naam'] = BINNENLOPER_NAAM  # aan de deur is een naam niet nodig
    gegevens['allergie_toestemming'] = waarden.get('allergie_toestemming') == '1'
    gegevens['bevestigd'] = waarden.get('bevestigd') == '1'
    try:
        g = PersoneelReserveringSchema(**gegevens)
    except ValidationError as fout:
        velden = [str(issue['loc'][0]) for issue in fout.errors() if issue.get('loc')]
        namen = [t(VELDNAMEN[v]) if v in VELDNAMEN else v for v in dict.fromkeys(velden)]
        return _formulier(waarden, 400, t("Controleer {velden}.", velden=", ".join(namen)))

    if g.datum < regels.nu().date():
        return _formulier(waarden, 400, t("Deze datum ligt in het verleden."))
    if g.bron == 'telefoon' and not g.telefoon:
        return _formulier(waarden, 400, t("Vul het telefoonnummer in; dat is nodig als we de gast moeten bellen."))
    allergieen = g.allergieen if regels.vraag_allergieen else None
    if allergieen and not g.allergie_toestemming:
        return _formulier(waarden, 400, t("Vraag de gast of we de allergieën mogen bewaren en vink dat aan, "
                                         "of laat het veld leeg."))

    if not g.bevestigd:
        waarschuwingen = _waarschuwingen(regels, g)
        if waarschuwingen:
            return _formulier(waarden, 200, waarschuwingen=waarschuwingen)

    datum, tijd = g.datum.isoformat(), g.tijd.strftime("%H:%M")
    talen = current_app.config['TALEN']
    taal = g.taal if g.taal in talen.beschikbaar else talen.standaard  # zonder keuze: de standaard
    try:
        reservering_id = verwerk_reservering(
            get_db(), None, naam=g.naam, email=g.email or '', telefoon=g.telefoon or '',
            datum=datum, tijd=tijd, aantal=g.aantal, zitduur_minuten=regels.zitduur_minuten,
            kinderstoelen=g.kinderstoelen, opmerking=g.opmerking, allergieen=allergieen,
            bron=g.bron, ingevoerd_door=huidige_gebruiker()['gebruikersnaam'], taal=taal,
        )
    except DubbeleReserveringFout:
        return _formulier(waarden, 409, t("Deze gast heeft op deze dag en tijd al een reservering."))
    except OperationalError:
        return _formulier(waarden, 503, t("Het lukte niet om op te slaan. Probeer het opnieuw."))

    bericht = t("Reservering voor {naam} om {tijd} ({aantal} p.) is opgeslagen.", naam=g.naam, tijd=tijd, aantal=g.aantal)
    if g.email:
        stuur_bevestigingsmail_async(ontvanger_email=g.email, naam=g.naam, datum=datum, tijd=tijd,
                                     aantal=g.aantal, reservering_id=reservering_id, taal=taal)
        bericht += " " + t("De gast krijgt een bevestigingsmail.")
    flash(bericht, 'ok')
    if g.bron == 'binnenloper' and current_app.config.get('PLATTEGROND') is not None:
        # Aan de deur is de volgende stap een tafel kiezen: meteen naar de plattegrond op dat moment.
        return redirect(url_for('web.plattegrond', datum=datum, tijd=tijd))
    return redirect(url_for('web.overzicht', datum=datum))
