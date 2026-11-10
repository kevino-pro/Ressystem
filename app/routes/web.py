import re
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from flask import Blueprint, Response, abort, render_template, request, jsonify, redirect, url_for, session, current_app
from werkzeug.security import check_password_hash
from pydantic import ValidationError

from app.database import (
    bezetting_op, get_db, piekbezetting, verwerk_reservering, CapaciteitVolFout, DubbeleReserveringFout,
    KinderstoelVolFout,
    GeenReserveringFout, OnbekendeTafelFout, TafelBezetFout,
    haal_personeel_op, haal_reserveringen_op, haal_reservering_op, haal_toewijzingen_op,
    minuten_van, verwijder_reservering as db_verwijder_reservering, wijs_tafels_toe,
)
from app.schemas import ALLERGIE_MELDING, NAAM_MELDING, OPMERKING_MELDING, TELEFOON_MELDING, ReserveringSchema

TOESTEMMING_MELDING = ("Vink aan dat we je allergie-informatie mogen bewaren, of laat het veld leeg. "
                       "Je kunt het ook bij aankomst aan ons doorgeven.")
from app.services.email_service import stuur_bevestigingsmail_async
from app.security import rate_limit, rate_limit_check_adres, valideer_csrf
from app.reserveringsregels import RegelFout

web_bp = Blueprint('web', __name__)
web_bp.before_request(valideer_csrf)

TIJD_PATROON = re.compile(r'\d{2}:\d{2}')
HOKJE = 48  # pixels per hokje op de plattegrond
STRAKS_MINUTEN = 30  # zo ver vooruit kijkt de plattegrond naar tafels die bijna bezet zijn

DAGEN_IN_STRIP = 7  # zoveel dagen staan als knop boven de kalender

def _zitduur_tekst(minuten):
    """60 -> '1 uur', 90 -> '1,5 uur', 75 -> '75 minuten'."""
    if minuten % 30:
        return f"{minuten} minuten"
    uren = minuten / 60
    return f"{uren:g} uur".replace(".", ",")

@web_bp.route('/')
def home():
    regels = current_app.config['REGELS']
    vandaag = regels.nu().date()
    dagen = []
    for i in range(DAGEN_IN_STRIP):
        dag = vandaag + timedelta(days=i)
        dagen.append({'datum': dag.isoformat(), 'dag': dag,
                      'open': bool(regels.blokken_op(dag)) and dag not in regels.sluitingsdagen})
    laatste = vandaag + timedelta(days=regels.max_dagen_vooruit)
    return render_template('index.html', regels=regels, dagen=dagen, vandaag=vandaag.isoformat(),
                           laatste=laatste.isoformat(), zitduur_tekst=_zitduur_tekst(regels.zitduur_minuten))

def _db_foutdetails(fout):
    """
    Vat een databasefout samen voor het logboek: driverklasse en SQLSTATE.
    De melding van de driver kan host, gebruikersnaam en een connectiestring bevatten en blijft
    daarom buiten de log. De SQLSTATE is voor de diagnose toereikend: 28P01 is een onjuist
    wachtwoord, 3D000 een database die niet bestaat en 08006 een verbindingsfout.
    """
    origineel = getattr(fout, 'orig', None)
    bron = fout if origineel is None else origineel
    sqlstate = getattr(bron, 'pgcode', None) or getattr(bron, 'sqlstate', None)
    return type(bron).__name__, sqlstate


@web_bp.route('/health')
def health():
    """Publiek, geen API-key vereist: doet een echte DB-round-trip zodat Neon wakker blijft."""
    try:
        get_db().execute(text('SELECT 1'))
    except OperationalError as fout:
        # Zonder deze logregel is een storing niet te diagnosticeren. Alleen de driverklasse en de
        # SQLSTATE komen in het logboek; de melding van de driver kan host en gebruikersnaam
        # bevatten en blijft er dus buiten. Het antwoord aan de client blijft generiek.
        driver, sqlstate = _db_foutdetails(fout)
        current_app.logger.error(
            "Healthcheck: database niet bereikbaar (driver=%s, sqlstate=%s)",
            driver, sqlstate,
        )
        return jsonify({"status": "fout", "bericht": "Database niet bereikbaar"}), 503
    return jsonify({"status": "ok"}), 200

@web_bp.route('/privacy')
def privacy():
    return render_template('privacy.html', regels=current_app.config['REGELS'])

def _laatste_reservering():
    """De reservering die deze bezoeker net heeft gemaakt (id staat in de sessiecookie), of None."""
    reservering_id = session.get('laatste_reservering')
    return haal_reservering_op(get_db(), reservering_id) if reservering_id else None

@web_bp.route('/bevestiging')
def bevestiging():
    return render_template('bevestiging.html', reservering=_laatste_reservering(),
                           zitduur=current_app.config['REGELS'].zitduur_minuten)

@web_bp.route('/bevestiging/agenda.ics')
def bevestiging_agenda():
    """Agenda-afspraak voor de reservering van deze bezoeker. Tijden in de tijdzone van het restaurant."""
    reservering = _laatste_reservering()
    if not reservering:
        abort(404)
    regels = current_app.config['REGELS']
    begin = datetime.combine(date.fromisoformat(reservering['datum']), time.fromisoformat(reservering['tijd']))
    eind = begin + timedelta(minutes=regels.zitduur_minuten)
    privacy = current_app.config.get('PRIVACY')
    naam = _ics_tekst(current_app.config['RESTAURANT_NAAM'])
    regels_ics = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Reserveringen//NL", "BEGIN:VEVENT",
        f"UID:{reservering['id']}@reserveringen",
        f"DTSTAMP:{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}",
        f"DTSTART;TZID={regels.tijdzone}:{begin:%Y%m%dT%H%M%S}",
        f"DTEND;TZID={regels.tijdzone}:{eind:%Y%m%dT%H%M%S}",
        f"SUMMARY:Tafel bij {naam} ({reservering['aantal']} p.)",
    ]
    if privacy:
        regels_ics.append(f"LOCATION:{_ics_tekst(privacy.adres)}")
    regels_ics += ["END:VEVENT", "END:VCALENDAR"]
    return Response("\r\n".join(regels_ics) + "\r\n", mimetype="text/calendar",
                    headers={"Content-Disposition": "attachment; filename=reservering.ics"})

def _ics_tekst(tekst):
    """Tekst veilig in een ICS-regel: geen regeleinden, en komma's en puntkomma's ge-escaped."""
    return (tekst.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r", " ").replace("\n", " "))

@web_bp.route('/login', methods=['GET', 'POST'])
@rate_limit('login', 10, 300)
def login():
    foutmelding = None
    if request.method == 'POST':
        gebruikersnaam = request.form.get('gebruikersnaam', '').strip()
        wachtwoord = request.form.get('wachtwoord', '')

        conn = get_db()
        user = haal_personeel_op(conn, gebruikersnaam)

        if user and check_password_hash(user['wachtwoord_hash'], wachtwoord):
            session.clear()
            session['ingelogd'] = True
            session['gebruiker'] = user['gebruikersnaam']
            return redirect(url_for('web.overzicht'))
        else:
            foutmelding = "Ongeldige gebruikersnaam of wachtwoord!"

    return render_template('login.html', foutmelding=foutmelding)

@web_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('web.login'))

@web_bp.route('/overzicht')
def overzicht():
    if not session.get('ingelogd'):
        return redirect(url_for('web.login'))

    regels = current_app.config['REGELS']
    vandaag = regels.nu().date()
    try:
        dag = date.fromisoformat(request.args['datum']) if request.args.get('datum') else vandaag
    except ValueError:
        return "Ongeldige datum.", 400
    datum = dag.isoformat()

    conn = get_db()
    lijst = haal_reserveringen_op(conn, datum)
    plattegrond_aan = current_app.config.get('PLATTEGROND') is not None
    toewijzingen = haal_toewijzingen_op(conn, datum) if plattegrond_aan else {}

    # Per begintijd groeperen; de lijst is al op tijd gesorteerd.
    groepen = {}
    for r in lijst:
        groepen.setdefault(r['tijd'], []).append(r)

    # Drukste moment: de bezetting kan alleen stijgen op het begin van een reservering.
    bestaande = [(minuten_van(r['tijd']), r['aantal']) for r in lijst]
    piek, piek_tijd = 0, None
    for tijd in groepen:
        moment = minuten_van(tijd)
        gasten = sum(aantal for begin, aantal in bestaande if begin <= moment < begin + regels.zitduur_minuten)
        if gasten > piek:
            piek, piek_tijd = gasten, tijd
    tellers = {
        'reserveringen': len(lijst),
        'gasten': sum(r['aantal'] for r in lijst),
        'piek': piek, 'piek_tijd': piek_tijd, 'max': regels.max_gasten_tegelijk,
        'zonder_tafel': sum(1 for r in lijst if not toewijzingen.get(r['id'])),
    }
    return render_template(
        'overzicht.html', actief='overzicht', datum=datum, dag=dag, vandaag=vandaag,
        vorige=(dag - timedelta(days=1)).isoformat(), volgende=(dag + timedelta(days=1)).isoformat(),
        groepen=groepen, toewijzingen=toewijzingen, tellers=tellers, plattegrond_aan=plattegrond_aan,
    )

def _kies_moment(regels, datum_tekst, tijd_tekst):
    """
    Datum en tijd voor de plattegrond. Zonder datum: vandaag (in de tijdzone van het restaurant).
    Zonder tijd: nu als het vandaag is, anders het begin van de eerste openingstijd die dag.
    Geeft None bij een ongeldige datum of tijd.
    """
    nu = regels.nu()
    try:
        dag = date.fromisoformat(datum_tekst) if datum_tekst else nu.date()
        if tijd_tekst:
            if not TIJD_PATROON.fullmatch(tijd_tekst):
                return None
            tijdstip = time.fromisoformat(tijd_tekst)
        elif dag == nu.date():
            tijdstip = time(nu.hour, nu.minute)
        else:
            blokken = regels.blokken_op(dag)
            tijdstip = blokken[0].van if blokken else time(12, 0)
    except ValueError:
        return None
    return dag.isoformat(), f"{tijdstip:%H:%M}"

@web_bp.route('/plattegrond')
def plattegrond():
    if not session.get('ingelogd'):
        return redirect(url_for('web.login'))
    indeling = current_app.config.get('PLATTEGROND')
    if indeling is None:
        abort(404)

    regels = current_app.config['REGELS']
    moment = _kies_moment(regels, request.args.get('datum'), request.args.get('tijd'))
    if moment is None:
        return "Ongeldige datum of tijd.", 400
    datum, tijd = moment

    conn = get_db()
    lijst = haal_reserveringen_op(conn, datum)
    toewijzingen = haal_toewijzingen_op(conn, datum)
    start = minuten_van(tijd)
    zitduur = regels.zitduur_minuten
    aan_tafel = [r for r in lijst if minuten_van(r['tijd']) <= start < minuten_van(r['tijd']) + zitduur]
    bezet = {tafel: r for r in aan_tafel for tafel in toewijzingen.get(r['id'], [])}
    # Tafels die binnen een half uur na dit moment gereserveerd zijn: niet meer weggeven.
    binnenkort = [r for r in lijst if start < minuten_van(r['tijd']) <= start + STRAKS_MINUTEN]
    straks = {tafel: r for r in binnenkort for tafel in toewijzingen.get(r['id'], []) if tafel not in bezet}

    dag = date.fromisoformat(datum)
    return render_template(
        'plattegrond.html', actief='plattegrond', indeling=indeling, datum=datum, dag=dag, tijd=tijd,
        zitduur=zitduur, reserveringen=lijst, toewijzingen=toewijzingen, bezet=bezet, straks=straks,
        aan_tafel_ids={r['id'] for r in aan_tafel}, hokje=HOKJE, vandaag=regels.nu().date(),
        tijdknoppen=_tijdknoppen(regels, dag), vorige=(dag - timedelta(days=1)).isoformat(),
        volgende=(dag + timedelta(days=1)).isoformat(),
    )

def _tijdknoppen(regels, dag):
    """Tijden om de bezetting te bekijken: van de eerste begintijd tot de laatste gast weg is."""
    blokken = regels.blokken_op(dag)
    if not blokken:
        return []
    stap = regels.knop_minuten or 30
    minuut = minuten_van(f"{blokken[0].van:%H:%M}")
    einde = min(minuten_van(f"{blokken[-1].tot:%H:%M}") + regels.zitduur_minuten - stap, 24 * 60 - stap)
    tijden = []
    while minuut <= einde:
        tijden.append(f"{minuut // 60:02d}:{minuut % 60:02d}")
        minuut += stap
    return tijden

@web_bp.route('/plattegrond/toewijzen', methods=['POST'])
def tafels_toewijzen():
    if not session.get('ingelogd'):
        return jsonify({"status": "fout", "bericht": "Je bent uitgelogd. Log opnieuw in."}), 401
    indeling = current_app.config.get('PLATTEGROND')
    if indeling is None:
        abort(404)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    reservering_id = data.get('reservering_id')
    tafels = data.get('tafels')
    if (not isinstance(reservering_id, str) or not isinstance(tafels, list)
            or len(tafels) > len(indeling.tafels) or not all(isinstance(t, str) for t in tafels)):
        return jsonify({"status": "fout", "bericht": "Ongeldig verzoek."}), 400

    try:
        waarschuwing = wijs_tafels_toe(
            get_db(), reservering_id, tafels, indeling, current_app.config['REGELS'].zitduur_minuten
        )
    except OnbekendeTafelFout as fout:
        return jsonify({"status": "fout", "bericht": fout.bericht}), 400
    except GeenReserveringFout as fout:
        return jsonify({"status": "fout", "bericht": fout.bericht}), 404
    except TafelBezetFout as fout:
        return jsonify({"status": "fout", "bericht": fout.bericht}), 409
    except OperationalError:
        current_app.logger.exception("Tafels toewijzen mislukt door een databasefout")
        return jsonify({"status": "fout", "bericht": "Het lukte niet om op te slaan. Probeer het opnieuw."}), 503
    return jsonify({"status": "succes", "bericht": "Opgeslagen.", "waarschuwing": waarschuwing}), 200

@web_bp.route('/beschikbaarheid')
@rate_limit('beschikbaarheid', 120, 600, json_response=True)
def beschikbaarheid():
    """
    Welke tijden op een dag nog kunnen voor een groep: GET /beschikbaarheid?datum=2026-11-07&aantal=2.
    Alleen een hulp voor het formulier; bij het versturen controleert /reservering alles opnieuw.
    """
    regels = current_app.config['REGELS']
    try:
        dag = date.fromisoformat(request.args.get('datum', ''))
        aantal = int(request.args.get('aantal', ''))
    except ValueError:
        return jsonify({"status": "fout", "bericht": "Geef een datum (JJJJ-MM-DD) en een aantal personen."}), 400
    if not 1 <= aantal <= regels.max_personen_per_boeking:
        return jsonify({"status": "fout", "bericht": (
            f"Online reserveren kan voor 1 tot {regels.max_personen_per_boeking} personen. "
            "Neem voor grotere groepen contact met ons op.")}), 400

    bestaande = bezetting_op(get_db(), dag.isoformat())
    nu = regels.nu()
    tijden, eerste_fout = [], None
    for tijdstip in regels.knoptijden_op(dag):
        try:
            regels.controleer(dag, tijdstip, aantal, nu=nu)
        except RegelFout as fout:
            eerste_fout = eerste_fout or fout.bericht
            continue  # te vroeg, te ver vooruit of een sluitingsdag: geen knop
        vrij = regels.max_gasten_tegelijk - piekbezetting(
            bestaande, minuten_van(f"{tijdstip:%H:%M}"), regels.zitduur_minuten)
        tijden.append({"tijd": f"{tijdstip:%H:%M}", "vrij": max(vrij, 0), "beschikbaar": vrij >= aantal})

    if not tijden:
        if eerste_fout is None:  # geen openingstijden op deze dag
            try:
                regels.controleer(dag, time(12, 0), aantal, nu=nu)
            except RegelFout as fout:
                eerste_fout = fout.bericht
        return jsonify({"status": "succes", "open": False, "tijden": [],
                        "bericht": eerste_fout or "Op deze dag kun je niet online reserveren."}), 200
    return jsonify({"status": "succes", "open": True, "tijden": tijden,
                    "diner_vanaf": f"{regels.diner_vanaf:%H:%M}" if regels.diner_vanaf else None}), 200

@web_bp.route('/reservering', methods=['POST'])
@rate_limit('reservering', 10, 600, json_response=True)
def nieuwe_reservering():
    json_data = request.get_json(silent=True)
    if not json_data:
        return jsonify({"status": "fout", "bericht": "Ongeldige JSON payload"}), 400

    try:
        valid_data = ReserveringSchema(**json_data)
    except ValidationError as error:
        fields = sorted({str(issue["loc"][0]) for issue in error.errors() if issue.get("loc")})
        bericht = "Datavalidatie mislukt"
        if "telefoon" in fields:
            bericht = TELEFOON_MELDING
        elif "naam" in fields:
            bericht = NAAM_MELDING
        elif "opmerking" in fields:
            bericht = OPMERKING_MELDING
        elif "allergieen" in fields:
            bericht = ALLERGIE_MELDING
        return jsonify({"status": "fout", "bericht": bericht, "velden": fields}), 422

    if valid_data.website:
        return jsonify({"status": "fout", "bericht": "Spam gedetecteerd."}), 400

    # Allergieen zijn gezondheidsgegevens: alleen bewaren met aparte toestemming, en alleen als dit
    # restaurant erom vraagt. Zonder vinkje weigeren we, zodat de gast niet denkt dat het is doorgegeven.
    allergieen = valid_data.allergieen if current_app.config['REGELS'].vraag_allergieen else None
    if allergieen and not valid_data.allergie_toestemming:
        return jsonify({"status": "fout", "bericht": TOESTEMMING_MELDING, "velden": ["allergie_toestemming"]}), 422

    try:
        current_app.config['REGELS'].controleer(valid_data.datum, valid_data.tijd, valid_data.aantal,
                                                kinderstoelen=valid_data.kinderstoelen)
    except RegelFout as fout:
        return jsonify({"status": "fout", "bericht": fout.bericht}), 400

    if not rate_limit_check_adres(valid_data.email):
        return jsonify({"status": "fout", "bericht": "Te veel verzoeken, probeer het later opnieuw."}), 429

    regels = current_app.config['REGELS']
    conn = get_db()
    try:
        unieke_id = verwerk_reservering(
            conn, regels.max_gasten_tegelijk,
            naam=valid_data.naam, email=valid_data.email, telefoon=valid_data.telefoon,
            datum=valid_data.datum.isoformat(), tijd=valid_data.tijd.strftime("%H:%M"), aantal=valid_data.aantal,
            zitduur_minuten=regels.zitduur_minuten,
            kinderstoelen=valid_data.kinderstoelen, max_kinderstoelen=regels.kinderstoelen,
            opmerking=valid_data.opmerking, allergieen=allergieen,
        )
    except DubbeleReserveringFout as fout:
        return jsonify({"status": "fout", "bericht": fout.bericht}), 409
    except KinderstoelVolFout as fout:
        return jsonify({"status": "fout", "bericht": fout.bericht}), 400
    except CapaciteitVolFout as e:
        return jsonify({
            "status": "fout",
            "bericht": f"Geen plek meer op dit tijdstip. Nog {e.vrij} plek(ken) beschikbaar."
        }), 400
    except OperationalError:
        return jsonify({"status": "fout", "bericht": "Database is momenteel druk, probeer het opnieuw."}), 503

    session['laatste_reservering'] = unieke_id  # voor de bevestigingspagina
    stuur_bevestigingsmail_async(
        ontvanger_email=valid_data.email,
        naam=valid_data.naam,
            datum=valid_data.datum.isoformat(),
            tijd=valid_data.tijd.strftime("%H:%M"),
        aantal=valid_data.aantal,
        reservering_id=unieke_id
    )

    return jsonify({"status": "succes", "bericht": "Reservering opgeslagen!", "id": unieke_id}), 200

@web_bp.route('/verwijder/<reservering_id>', methods=['POST'])
def verwijder_reservering(reservering_id):
    if not session.get('ingelogd'):
        return redirect(url_for('web.login'))

    conn = get_db()
    db_verwijder_reservering(conn, reservering_id)

    return redirect(url_for('web.overzicht'))

@web_bp.route('/annuleren/<reservering_id>', methods=['GET', 'POST'])
@rate_limit('annuleren', 20, 600)
def annuleren_klant(reservering_id):
    conn = get_db()
    reservering = haal_reservering_op(conn, reservering_id)

    if not reservering:
        return "Reservering niet gevonden of reeds geannuleerd.", 404

    if request.method == 'POST':
        db_verwijder_reservering(conn, reservering_id)
        return render_template('annuleren_bevestigd.html')

    return render_template('annuleren_bevestigen.html', reservering=reservering)