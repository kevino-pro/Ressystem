import hashlib
import hmac
import re
import unicodedata
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from flask import (
    Blueprint, Response, abort, flash, render_template, request, jsonify, redirect, url_for, session, current_app,
)
from werkzeug.security import check_password_hash
from pydantic import ValidationError

from app.database import (
    bezetting_op, get_db, piekbezetting, verwerk_reservering, CapaciteitVolFout, DubbeleReserveringFout,
    KinderstoelVolFout, NIET_GEKOMEN, NietMeerWijzigbaarFout, STATUSSEN, wijzig_reservering, zet_status,
    GeenReserveringFout, OnbekendeTafelFout, TafelBezetFout,
    haal_personeel_op, haal_reserveringen_op, haal_reserveringen_vanaf, haal_reservering_op, haal_toewijzingen_op,
    minuten_van, verwijder_reservering as db_verwijder_reservering, wijs_tafels_toe, zet_taal,
)
from app.normalisatie import normaliseer_naam, normaliseer_telefoon
from app.schemas import ALLERGIE_MELDING, NAAM_MELDING, OPMERKING_MELDING, TELEFOON_MELDING, ReserveringSchema

TOESTEMMING_MELDING = ("Vink aan dat we je allergie-informatie mogen bewaren, of laat het veld leeg. "
                       "Je kunt het ook bij aankomst aan ons doorgeven.")
from app.services.email_service import stuur_bevestigingsmail_async
from app.security import constant_time_equals, rate_limit, rate_limit_check_adres, valideer_csrf
from app.reserveringsregels import RegelFout
from app.taal import DAGEN, MAANDEN, TAAL_COOKIE, huidige_taal, vertaal as t
from app.toegang import beheerder_vereist, huidige_gebruiker, login_vereist, start_sessie

web_bp = Blueprint('web', __name__)
web_bp.before_request(valideer_csrf)

TIJD_PATROON = re.compile(r'\d{2}:\d{2}')
HOKJE = 48  # pixels per hokje op de plattegrond
STRAKS_MINUTEN = 30  # zo ver vooruit kijkt de plattegrond naar tafels die bijna bezet zijn

DAGEN_IN_STRIP = 7  # zoveel dagen staan als knop boven de kalender
ZOEK_MIN_TEKENS = 2
ZOEK_MAX_RESULTATEN = 50
TELEFOON_ZOEKTERM = re.compile(r'[\d\s+()\-]+')  # alleen cijfers en wat je in een telefoonnummer typt

def _zitduur_tekst(minuten):
    """60 -> '1 uur', 90 -> '1,5 uur', 75 -> '75 minuten' (in de taal van het verzoek)."""
    if minuten % 30:
        return t("{minuten} minuten", minuten=minuten)
    if minuten == 60:
        return t("1 uur")
    uren = f"{minuten / 60:g}"
    if huidige_taal() != "en":
        uren = uren.replace(".", ",")  # 1,5 in het Nederlands en Indonesisch, 1.5 in het Engels
    return t("{uren} uur", uren=uren)

TAAL_COOKIE_DAGEN = 365

@web_bp.route('/taal/<code>')
def kies_taal(code):
    """
    Onthoudt de gekozen taal in een cookie en gaat terug naar de pagina waar de gast was.
    `terug` moet een pad op deze site zijn; al het andere wordt de startpagina.
    """
    terug = request.args.get('terug', '')
    # Ook geen stuurtekens: een browser haalt tab en regeleinde weg, dan wordt '/\t/x' alsnog '//x'.
    if not terug.startswith('/') or terug.startswith('//') or '\\' in terug or not terug.isprintable():
        terug = '/'
    antwoord = redirect(terug)
    if code in current_app.config['TALEN'].beschikbaar:
        gebruiker = huidige_gebruiker()
        if gebruiker is not None:
            zet_taal(get_db(), gebruiker['id'], code)  # personeel: de keuze hoort bij het account
        antwoord.set_cookie(
            TAAL_COOKIE, code, max_age=TAAL_COOKIE_DAGEN * 24 * 3600, samesite='Lax',
            secure=current_app.config.get('SESSION_COOKIE_SECURE', True), httponly=True,
        )
    return antwoord

def _kiezer(regels):
    """Wat de knoppen voor personen, dag en tijd nodig hebben (reserveren en wijzigen)."""
    vandaag = regels.nu().date()
    dagen = []
    for i in range(DAGEN_IN_STRIP):
        dag = vandaag + timedelta(days=i)
        dagen.append({'datum': dag.isoformat(), 'dag': dag,
                      'open': bool(regels.blokken_op(dag)) and dag not in regels.sluitingsdagen})
    laatste = vandaag + timedelta(days=regels.max_dagen_vooruit)
    taal = huidige_taal()
    return {'regels': regels, 'dagen': dagen, 'vandaag': vandaag.isoformat(), 'laatste': laatste.isoformat(),
            'dagnamen': [DAGEN[taal][6], *DAGEN[taal][:6]], 'maandnamen': MAANDEN[taal]}

@web_bp.route('/')
def home():
    regels = current_app.config['REGELS']
    return render_template('index.html', zitduur_tekst=_zitduur_tekst(regels.zitduur_minuten), **_kiezer(regels))

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
        f"SUMMARY:{_ics_tekst(t('Tafel bij {naam} ({aantal} p.)', naam=current_app.config['RESTAURANT_NAAM'], aantal=reservering['aantal']))}",
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

        # Een uitgezet account krijgt dezelfde melding als een fout wachtwoord.
        if user and check_password_hash(user['wachtwoord_hash'], wachtwoord) and user['actief']:
            start_sessie(user)
            return redirect(url_for('web.overzicht'))
        else:
            foutmelding = t("Ongeldige gebruikersnaam of wachtwoord!")

    return render_template('login.html', foutmelding=foutmelding)

@web_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('web.login'))

@web_bp.route('/overzicht')
@login_vereist
def overzicht():
    regels = current_app.config['REGELS']
    vandaag = regels.nu().date()
    try:
        dag = date.fromisoformat(request.args['datum']) if request.args.get('datum') else vandaag
    except ValueError:
        return t("Ongeldige datum."), 400
    datum = dag.isoformat()

    conn = get_db()
    lijst = haal_reserveringen_op(conn, datum)
    plattegrond_aan = current_app.config.get('PLATTEGROND') is not None
    toewijzingen = haal_toewijzingen_op(conn, datum) if plattegrond_aan else {}
    gekomen = [r for r in lijst if r['status'] != NIET_GEKOMEN]  # een no-show telt niet mee

    # Per begintijd groeperen; de lijst is al op tijd gesorteerd.
    groepen = {}
    for r in lijst:
        groepen.setdefault(r['tijd'], []).append(r)

    # Drukste moment: de bezetting kan alleen stijgen op het begin van een reservering.
    bestaande = [(minuten_van(r['tijd']), r['aantal']) for r in gekomen]
    piek, piek_tijd = 0, None
    for tijd in groepen:
        moment = minuten_van(tijd)
        gasten = sum(aantal for begin, aantal in bestaande if begin <= moment < begin + regels.zitduur_minuten)
        if gasten > piek:
            piek, piek_tijd = gasten, tijd
    tellers = {
        'reserveringen': len(lijst),
        'gasten': sum(r['aantal'] for r in gekomen),
        'piek': piek, 'piek_tijd': piek_tijd, 'max': regels.max_gasten_tegelijk,
        'zonder_tafel': sum(1 for r in gekomen if not toewijzingen.get(r['id'])),
        'verwacht': sum(1 for r in lijst if r['status'] == 'verwacht'),
    }
    nu = regels.nu()
    return render_template(
        'overzicht.html', actief='overzicht', datum=datum, dag=dag, vandaag=vandaag,
        vorige=(dag - timedelta(days=1)).isoformat(), volgende=(dag + timedelta(days=1)).isoformat(),
        groepen=groepen, toewijzingen=toewijzingen, tellers=tellers, plattegrond_aan=plattegrond_aan,
        kenmerken={r['id']: _kenmerk(r['id']) for r in lijst}, nu_tijd=f"{nu:%H:%M}",
    )

def _zoekvorm(tekst):
    """Kleine letters, zonder accenten en dubbele spaties: 'José  de Vries' en 'jose de vries' zijn gelijk."""
    tekst = unicodedata.normalize('NFKD', normaliseer_naam(tekst))
    return ''.join(teken for teken in tekst if not unicodedata.combining(teken))

def zoek_reserveringen(lijst, zoekterm):
    """
    De reserveringen uit `lijst` die bij de zoekterm passen. Bestaat de zoekterm alleen uit cijfers (en +, spaties,
    haakjes of streepjes) met minstens 3 cijfers, dan op telefoonnummer: 0612, +31 612 en 612 vinden 06-12345678.
    Anders op een deel van de naam, zonder op hoofdletters of accenten te letten.
    """
    zoekterm = zoekterm.strip()
    cijfers = normaliseer_telefoon(zoekterm)
    if TELEFOON_ZOEKTERM.fullmatch(zoekterm) and len(cijfers) >= 3:
        return [r for r in lijst if r['telefoon'] and cijfers in normaliseer_telefoon(r['telefoon'])]
    naam = _zoekvorm(zoekterm)
    return [r for r in lijst if naam in _zoekvorm(r['naam'])]

@web_bp.route('/zoeken')
@login_vereist
def zoeken():
    """Zoeken op naam of telefoonnummer in de reserveringen van vandaag en later; oude reserveringen niet."""
    vandaag = current_app.config['REGELS'].nu().date()
    zoekterm = request.args.get('q', '').strip()[:100]
    gevonden = []
    if len(zoekterm) >= ZOEK_MIN_TEKENS:
        gevonden = zoek_reserveringen(haal_reserveringen_vanaf(get_db(), vandaag.isoformat()), zoekterm)
    groepen = {}
    for r in gevonden[:ZOEK_MAX_RESULTATEN]:
        groepen.setdefault(r['datum'], []).append(r)
    return render_template(
        'zoeken.html', actief='overzicht', zoekterm=zoekterm, groepen=groepen, vandaag=vandaag,
        te_kort=0 < len(zoekterm) < ZOEK_MIN_TEKENS, min_tekens=ZOEK_MIN_TEKENS,
        meer=len(gevonden) > ZOEK_MAX_RESULTATEN, max_resultaten=ZOEK_MAX_RESULTATEN,
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

def _kenmerk(reservering_id):
    """
    Kenmerk van een reservering op de plattegrond. Het id zelf is ook de annuleerlink van de gast;
    daarom staat op de plattegrond (die ook een medewerker ziet) alleen dit afgeleide kenmerk.
    """
    sleutel = str(current_app.config['SECRET_KEY']).encode('utf-8')
    return hmac.new(sleutel, f"plattegrond:{reservering_id}".encode('utf-8'), hashlib.sha256).hexdigest()[:24]

@web_bp.route('/plattegrond')
@login_vereist
def plattegrond():
    indeling = current_app.config.get('PLATTEGROND')
    if indeling is None:
        abort(404)

    regels = current_app.config['REGELS']
    moment = _kies_moment(regels, request.args.get('datum'), request.args.get('tijd'))
    if moment is None:
        return t("Ongeldige datum of tijd."), 400
    datum, tijd = moment

    conn = get_db()
    lijst = haal_reserveringen_op(conn, datum)
    toewijzingen = haal_toewijzingen_op(conn, datum)
    start = minuten_van(tijd)
    zitduur = regels.zitduur_minuten
    gekomen = [r for r in lijst if r['status'] != NIET_GEKOMEN]  # een no-show bezet geen tafel
    aan_tafel = [r for r in gekomen if minuten_van(r['tijd']) <= start < minuten_van(r['tijd']) + zitduur]
    bezet = {tafel: r for r in aan_tafel for tafel in toewijzingen.get(r['id'], [])}
    # Tafels die binnen een half uur na dit moment gereserveerd zijn: niet meer weggeven.
    binnenkort = [r for r in gekomen if start < minuten_van(r['tijd']) <= start + STRAKS_MINUTEN]
    straks = {tafel: r for r in binnenkort for tafel in toewijzingen.get(r['id'], []) if tafel not in bezet}

    dag = date.fromisoformat(datum)
    return render_template(
        'plattegrond.html', actief='plattegrond', indeling=indeling, datum=datum, dag=dag, tijd=tijd,
        zitduur=zitduur, reserveringen=gekomen, niet_gekomen=[r for r in lijst if r['status'] == NIET_GEKOMEN],
        toewijzingen=toewijzingen, bezet=bezet, straks=straks, nu_tijd=f"{regels.nu():%H:%M}",
        kenmerken={r['id']: _kenmerk(r['id']) for r in lijst},
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
@login_vereist(json_response=True)
def tafels_toewijzen():
    indeling = current_app.config.get('PLATTEGROND')
    if indeling is None:
        abort(404)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    kenmerk = data.get('kenmerk')
    tafels = data.get('tafels')
    try:
        datum = date.fromisoformat(data.get('datum')).isoformat()
    except (TypeError, ValueError):
        datum = None
    if (datum is None or not isinstance(kenmerk, str) or not isinstance(tafels, list)
            or len(tafels) > len(indeling.tafels) or not all(isinstance(t, str) for t in tafels)):
        return jsonify({"status": "fout", "bericht": t("Ongeldig verzoek.")}), 400

    # De plattegrond kent alleen het kenmerk, niet het id (zie _kenmerk); zoek het id op die dag op.
    reservering_id = next((r['id'] for r in haal_reserveringen_op(get_db(), datum)
                           if constant_time_equals(_kenmerk(r['id']), kenmerk)), None)
    if reservering_id is None:
        return jsonify({"status": "fout", "bericht": t(GeenReserveringFout.bericht)}), 404

    try:
        waarschuwing = wijs_tafels_toe(
            get_db(), reservering_id, tafels, indeling, current_app.config['REGELS'].zitduur_minuten
        )
    except OnbekendeTafelFout as fout:
        return jsonify({"status": "fout", "bericht": fout.vertaald()}), 400
    except GeenReserveringFout as fout:
        return jsonify({"status": "fout", "bericht": t(fout.bericht)}), 404
    except TafelBezetFout as fout:
        return jsonify({"status": "fout", "bericht": fout.vertaald()}), 409
    except OperationalError:
        current_app.logger.exception("Tafels toewijzen mislukt door een databasefout")
        return jsonify({"status": "fout", "bericht": t("Het lukte niet om op te slaan. Probeer het opnieuw.")}), 503
    return jsonify({"status": "succes", "bericht": t("Opgeslagen."), "waarschuwing": waarschuwing}), 200

STATUS_BERICHTEN = {
    'gearriveerd': "{naam} is er.",
    'no_show': "{naam} is niet gekomen.",
    'verwacht': "{naam} staat weer op verwacht.",
}

@web_bp.route('/aankomst', methods=['POST'])
@login_vereist
def aankomst():
    """
    Zet een reservering op gearriveerd, niet gekomen (no-show) of terug op verwacht.
    Beheerder en medewerker mogen dit. Net als de plattegrond werkt dit met het kenmerk, niet met het id.
    """
    regels = current_app.config['REGELS']
    status = request.form.get('status')
    kenmerk = request.form.get('kenmerk')
    try:
        dag = date.fromisoformat(request.form.get('datum') or '')
    except ValueError:
        dag = None
    if dag is None or status not in STATUSSEN or not kenmerk:
        return t("Ongeldig verzoek."), 400

    datum = dag.isoformat()
    reservering = next((r for r in haal_reserveringen_op(get_db(), datum)
                        if constant_time_equals(_kenmerk(r['id']), kenmerk)), None)
    if reservering is None:
        return t(GeenReserveringFout.bericht), 404

    if request.form.get('terug') == 'plattegrond' and current_app.config.get('PLATTEGROND') is not None:
        terug = url_for('web.plattegrond', datum=datum, tijd=reservering['tijd'])
    else:
        terug = url_for('web.overzicht', datum=datum)

    nu = regels.nu()
    if status != 'verwacht' and dag > nu.date():
        flash(t("Dat kan pas op de dag van de reservering."), 'fout')
        return redirect(terug)
    if status == NIET_GEKOMEN and dag == nu.date() and f"{nu:%H:%M}" < reservering['tijd']:
        flash(t("Een no-show kan pas na de begintijd ({tijd}).", tijd=reservering['tijd']), 'fout')
        return redirect(terug)

    zet_status(get_db(), reservering['id'], status)
    flash(t(STATUS_BERICHTEN[status], naam=reservering['naam']), 'ok')
    return redirect(terug)

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
        return jsonify({"status": "fout", "bericht": t("Geef een datum (JJJJ-MM-DD) en een aantal personen.")}), 400
    if not 1 <= aantal <= regels.max_personen_per_boeking:
        return jsonify({"status": "fout", "bericht": t(
            "Online reserveren kan voor 1 tot {aantal} personen. Neem voor grotere groepen contact met ons op.",
            aantal=regels.max_personen_per_boeking)}), 400

    # Bij wijzigen telt de eigen reservering niet mee (zie wijzigen_klant); /wijzigen controleert opnieuw.
    behalve = request.args.get('behalve', '')[:64] or None
    bestaande = bezetting_op(get_db(), dag.isoformat(), behalve=behalve)
    nu = regels.nu()
    tijden, eerste_fout = [], None
    for tijdstip in regels.knoptijden_op(dag):
        try:
            regels.controleer(dag, tijdstip, aantal, nu=nu)
        except RegelFout as fout:
            eerste_fout = eerste_fout or fout.vertaald()
            continue  # te vroeg, te ver vooruit of een sluitingsdag: geen knop
        vrij = regels.max_gasten_tegelijk - piekbezetting(
            bestaande, minuten_van(f"{tijdstip:%H:%M}"), regels.zitduur_minuten)
        tijden.append({"tijd": f"{tijdstip:%H:%M}", "vrij": max(vrij, 0), "beschikbaar": vrij >= aantal})

    if not tijden:
        if eerste_fout is None:  # geen openingstijden op deze dag
            try:
                regels.controleer(dag, time(12, 0), aantal, nu=nu)
            except RegelFout as fout:
                eerste_fout = fout.vertaald()
        return jsonify({"status": "succes", "open": False, "tijden": [],
                        "bericht": eerste_fout or t("Op deze dag kun je niet online reserveren.")}), 200
    return jsonify({"status": "succes", "open": True, "tijden": tijden,
                    "diner_vanaf": f"{regels.diner_vanaf:%H:%M}" if regels.diner_vanaf else None}), 200

@web_bp.route('/reservering', methods=['POST'])
@rate_limit('reservering', 10, 600, json_response=True)
def nieuwe_reservering():
    json_data = request.get_json(silent=True)
    if not json_data:
        return jsonify({"status": "fout", "bericht": t("Ongeldige JSON payload")}), 400

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
        return jsonify({"status": "fout", "bericht": t(bericht), "velden": fields}), 422

    if valid_data.website:
        return jsonify({"status": "fout", "bericht": t("Spam gedetecteerd.")}), 400

    # Allergieen zijn gezondheidsgegevens: alleen bewaren met aparte toestemming, en alleen als dit
    # restaurant erom vraagt. Zonder vinkje weigeren we, zodat de gast niet denkt dat het is doorgegeven.
    allergieen = valid_data.allergieen if current_app.config['REGELS'].vraag_allergieen else None
    if allergieen and not valid_data.allergie_toestemming:
        return jsonify({"status": "fout", "bericht": t(TOESTEMMING_MELDING), "velden": ["allergie_toestemming"]}), 422

    try:
        current_app.config['REGELS'].controleer(valid_data.datum, valid_data.tijd, valid_data.aantal,
                                                kinderstoelen=valid_data.kinderstoelen)
    except RegelFout as fout:
        return jsonify({"status": "fout", "bericht": fout.vertaald()}), 400

    if not rate_limit_check_adres(valid_data.email):
        return jsonify({"status": "fout", "bericht": t("Te veel verzoeken, probeer het later opnieuw.")}), 429

    regels = current_app.config['REGELS']
    conn = get_db()
    try:
        unieke_id = verwerk_reservering(
            conn, regels.max_gasten_tegelijk,
            naam=valid_data.naam, email=valid_data.email, telefoon=valid_data.telefoon,
            datum=valid_data.datum.isoformat(), tijd=valid_data.tijd.strftime("%H:%M"), aantal=valid_data.aantal,
            zitduur_minuten=regels.zitduur_minuten,
            kinderstoelen=valid_data.kinderstoelen, max_kinderstoelen=regels.kinderstoelen,
            opmerking=valid_data.opmerking, allergieen=allergieen, taal=huidige_taal(),
        )
    except DubbeleReserveringFout as fout:
        return jsonify({"status": "fout", "bericht": fout.vertaald()}), 409
    except KinderstoelVolFout as fout:
        return jsonify({"status": "fout", "bericht": fout.vertaald()}), 400
    except CapaciteitVolFout as e:
        return jsonify({
            "status": "fout",
            "bericht": t("Geen plek meer op dit tijdstip. Nog {vrij} plek(ken) beschikbaar.", vrij=max(e.vrij, 0))
        }), 400
    except OperationalError:
        return jsonify({"status": "fout", "bericht": t("Database is momenteel druk, probeer het opnieuw.")}), 503

    session['laatste_reservering'] = unieke_id  # voor de bevestigingspagina
    stuur_bevestigingsmail_async(
        ontvanger_email=valid_data.email,
        naam=valid_data.naam,
            datum=valid_data.datum.isoformat(),
            tijd=valid_data.tijd.strftime("%H:%M"),
        aantal=valid_data.aantal,
        reservering_id=unieke_id,
        taal=huidige_taal(),
    )

    return jsonify({"status": "succes", "bericht": t("Reservering opgeslagen!"), "id": unieke_id}), 200

@web_bp.route('/verwijder/<reservering_id>', methods=['POST'])
@beheerder_vereist
def verwijder_reservering(reservering_id):
    # Alleen een beheerder: een medewerker mag reserveringen bekijken, maar niet verwijderen.
    conn = get_db()
    db_verwijder_reservering(conn, reservering_id)

    return redirect(url_for('web.overzicht'))

@web_bp.route('/annuleren/<reservering_id>', methods=['GET', 'POST'])
@rate_limit('annuleren', 20, 600)
def annuleren_klant(reservering_id):
    conn = get_db()
    reservering = haal_reservering_op(conn, reservering_id)

    if not reservering:
        return t("Reservering niet gevonden of reeds geannuleerd."), 404
    if reservering['status'] != 'verwacht':
        # Na aankomst of een no-show blijft de reservering staan voor de cijfers.
        return t("Deze reservering kan niet meer online worden geannuleerd."), 409

    if request.method == 'POST':
        db_verwijder_reservering(conn, reservering_id)
        return render_template('annuleren_bevestigd.html')

    return _wijzigpagina(reservering)

def _waarom_niet_wijzigen(regels, reservering):
    """None als de gast deze reservering (status verwacht) nog zelf mag wijzigen, anders de reden voor de gast."""
    if reservering['aantal'] > regels.max_personen_per_boeking:
        return t("Een reservering voor zoveel personen kun je niet online wijzigen. Bel ons, dan regelen we het.")
    if not regels.kan_nog_wijzigen(date.fromisoformat(reservering['datum']), time.fromisoformat(reservering['tijd'])):
        return t("Je reservering begint binnen {duur}. Wijzigen kan nu niet meer online. Je kunt nog annuleren, of bel ons.",
                 duur=_zitduur_tekst(regels.wijzigen_minuten_vooraf))
    return None

def _wijzigpagina(reservering, fout=None, status=200, keuze=None):
    """De pagina 'Wijzig of annuleer'. `keuze` is wat de gast probeerde; standaard de huidige reservering."""
    regels = current_app.config['REGELS']
    keuze = keuze or {'datum': reservering['datum'], 'tijd': reservering['tijd'], 'aantal': reservering['aantal']}
    return render_template('annuleren_bevestigen.html', reservering=reservering, fout=fout, keuze=keuze,
                           niet_wijzigen=_waarom_niet_wijzigen(regels, reservering),
                           wijzigen_tot=_zitduur_tekst(regels.wijzigen_minuten_vooraf), **_kiezer(regels)), status

@web_bp.route('/wijzigen/<reservering_id>', methods=['GET', 'POST'])
@rate_limit('wijzigen', 20, 600)
def wijzigen_klant(reservering_id):
    """
    De gast zet zijn reservering op een andere dag, tijd of aantal personen, met dezelfde regels als bij
    reserveren. Kan tot wijzigen_minuten_vooraf voor de huidige begintijd; daarna alleen annuleren of bellen.
    GET (bijvoorbeeld een taallink na een mislukte poging) gaat terug naar de pagina Wijzig of annuleer.
    """
    if request.method == 'GET':
        return redirect(url_for('web.annuleren_klant', reservering_id=reservering_id))
    conn = get_db()
    reservering = haal_reservering_op(conn, reservering_id)
    if not reservering:
        return t("Reservering niet gevonden of reeds geannuleerd."), 404
    if reservering['status'] != 'verwacht':
        return t("Deze reservering kan niet meer online worden gewijzigd."), 409

    regels = current_app.config['REGELS']
    if _waarom_niet_wijzigen(regels, reservering):
        return _wijzigpagina(reservering, status=409)

    datum_tekst, tijd_tekst = request.form.get('datum', ''), request.form.get('tijd', '')
    try:
        dag = date.fromisoformat(datum_tekst)
        aantal = int(request.form.get('aantal', ''))
        if not TIJD_PATROON.fullmatch(tijd_tekst):
            raise ValueError(tijd_tekst)
        tijdstip = time.fromisoformat(tijd_tekst)
    except ValueError:
        return _wijzigpagina(reservering, t("Kies een dag en een tijd."), 400)
    keuze = {'datum': dag.isoformat(), 'tijd': tijd_tekst, 'aantal': aantal}

    if not 1 <= aantal <= regels.max_personen_per_boeking:
        return _wijzigpagina(reservering, t(
            "Online reserveren kan voor 1 tot {aantal} personen. Neem voor grotere groepen contact met ons op.",
            aantal=regels.max_personen_per_boeking), 400, keuze)
    if (keuze['datum'], keuze['tijd'], aantal) == (reservering['datum'], reservering['tijd'], reservering['aantal']):
        return _wijzigpagina(reservering, t("Je hebt niets veranderd. Kies een andere dag, tijd of aantal personen."),
                             400, keuze)
    try:
        regels.controleer(dag, tijdstip, aantal, kinderstoelen=reservering['kinderstoelen'])
    except RegelFout as fout:
        return _wijzigpagina(reservering, fout.vertaald(), 400, keuze)

    try:
        nieuw = wijzig_reservering(conn, reservering_id, regels.max_gasten_tegelijk, keuze['datum'], tijd_tekst,
                                   aantal, regels.zitduur_minuten, max_kinderstoelen=regels.kinderstoelen)
    except NietMeerWijzigbaarFout:
        return t("Deze reservering kan niet meer online worden gewijzigd."), 409
    except DubbeleReserveringFout:
        return _wijzigpagina(reservering, t("Je hebt op deze dag en tijd al een andere reservering."), 409, keuze)
    except KinderstoelVolFout as fout:
        return _wijzigpagina(reservering, fout.vertaald(), 400, keuze)
    except CapaciteitVolFout as e:
        return _wijzigpagina(reservering, t("Geen plek meer op dit tijdstip. Nog {vrij} plek(ken) beschikbaar.",
                                            vrij=max(e.vrij, 0)), 400, keuze)
    except OperationalError:
        return _wijzigpagina(reservering, t("Database is momenteel druk, probeer het opnieuw."), 503, keuze)

    return render_template('wijziging_opgeslagen.html', reservering=nieuw)