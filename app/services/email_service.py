import json
import smtplib
import socket
import threading
import logging
import urllib.error
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app

from app.taal import BRONTAAL, datum_tekst, hoofdletter, vertaal

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"

def _verstuur_via_resend(app_config, bericht):
    verzoek = urllib.request.Request(
        RESEND_URL,
        data=json.dumps({
            "from": bericht['from'],
            "to": [bericht['to']],
            "subject": bericht['subject'],
            "text": bericht['tekst'],
        }).encode('utf-8'),
        headers={
            "Authorization": f"Bearer {app_config['RESEND_API_KEY']}",
            "Content-Type": "application/json",
            # Zonder eigen User-Agent wordt het verzoek door Resend geweigerd.
            "User-Agent": "WPL-reserveringssysteem/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(verzoek, timeout=10):
        pass

def _verstuur_via_smtp(app_config, bericht):
    msg = MIMEMultipart()
    msg['From'] = bericht['from']
    msg['To'] = bericht['to']
    msg['Subject'] = bericht['subject']
    msg.attach(MIMEText(bericht['tekst'], 'plain'))
    with smtplib.SMTP(app_config['SMTP_SERVER'], app_config['SMTP_PORT'], timeout=10) as server:
        server.starttls()
        server.login(app_config['VERZENDER_EMAIL'], app_config['VERZENDER_WACHTWOORD'])
        server.send_message(msg)

def async_send_email(app_config, bericht, recipient_email, reservering_id):
    # Deze functie draait op een losse thread, ná het versturen van de HTTP-response.
    # De reservering is dan al in de database gezet en de klant heeft al een antwoord
    # gekregen -- we kunnen de klant hier niets meer laten weten. Het enige wat we nog
    # kunnen doen is duidelijk loggen (met reservering_id) zodat personeel een gemiste
    # bevestigingsmail kan terugvinden (grep op MAIL_FAILED) en de klant zelf kan benaderen,
    # of `flask resend-mail <reservering_id>` kan draaien.
    # Geeft True als de mail echt is verstuurd (de herinnering gebruikt dat); False bij een fout of simulatie.
    try:
        if app_config.get('RESEND_API_KEY'):
            _verstuur_via_resend(app_config, bericht)
        elif not app_config['VERZENDER_WACHTWOORD'] or app_config['VERZENDER_EMAIL'] == "jouw-restaurant@gmail.com":
            logger.info("[MAIL_SIMULATIE] reservering_id=%s", reservering_id)
            return False
        else:
            _verstuur_via_smtp(app_config, bericht)

        logger.info("[MAIL_SENT] reservering_id=%s", reservering_id)
        return True
    except urllib.error.HTTPError as error:
        logger.error("[MAIL_FAILED] reservering_id=%s error_type=%s status=%s", reservering_id, type(error).__name__, error.code)
        return False
    except (smtplib.SMTPException, socket.error, OSError) as error:
        logger.error("[MAIL_FAILED] reservering_id=%s error_type=%s", reservering_id, type(error).__name__)
        return False

def _bouw_bevestigingsmail(app_config, ontvanger_email, naam, datum, tijd, aantal, reservering_id, taal=BRONTAAL):
    """De bevestigingsmail in de taal van de gast (`taal`: 'en', 'nl' of 'id')."""
    annuleer_url = f"{app_config['APP_BASE_URL']}/annuleren/{reservering_id}"
    restaurant = app_config['RESTAURANT_NAAM']
    onderwerp = vertaal("Bevestiging van je reservering - {restaurant}", taal=taal, restaurant=restaurant)

    regels = [
        vertaal("Beste {naam},", taal=taal, naam=naam),
        "",
        vertaal("Bedankt voor je reservering bij {restaurant}!", taal=taal, restaurant=restaurant),
        "",
        vertaal("Hier zijn de gegevens van je reservering:", taal=taal),
        "- " + vertaal("Datum: {datum}", taal=taal, datum=hoofdletter(datum_tekst(datum, met_jaar=True, taal=taal))),
        "- " + vertaal("Tijdstip: {tijd}", taal=taal, tijd=tijd),
        "- " + vertaal("Aantal personen: {aantal}", taal=taal, aantal=aantal),
        "",
        vertaal("Wil je de reservering wijzigen of annuleren? Klik op deze link:", taal=taal),
        annuleer_url,
        "",
        vertaal("Met vriendelijke groet,", taal=taal),
        vertaal("Het team van {restaurant}", taal=taal, restaurant=restaurant),
    ]
    bericht_inhoud = "\n".join(regels) + "\n"
    return {
        'from': app_config['VERZENDER_EMAIL'],
        'to': ontvanger_email,
        'subject': onderwerp,
        'tekst': bericht_inhoud,
    }

def stuur_bevestigingsmail_async(ontvanger_email, naam, datum, tijd, aantal, reservering_id, taal=BRONTAAL):
    app_config = current_app.config.copy()
    bericht = _bouw_bevestigingsmail(app_config, ontvanger_email, naam, datum, tijd, aantal, reservering_id, taal)
    threading.Thread(target=async_send_email, args=(app_config, bericht, ontvanger_email, reservering_id), daemon=True).start()

def stuur_bevestigingsmail_sync(ontvanger_email, naam, datum, tijd, aantal, reservering_id, taal=BRONTAAL):
    """Blokkerende variant van stuur_bevestigingsmail_async, voor de `flask resend-mail` CLI."""
    app_config = current_app.config.copy()
    bericht = _bouw_bevestigingsmail(app_config, ontvanger_email, naam, datum, tijd, aantal, reservering_id, taal)
    async_send_email(app_config, bericht, ontvanger_email, reservering_id)

def _bouw_herinneringsmail(app_config, reservering):
    """De herinnering de dag voor het bezoek, in de taal van de gast (kolom `taal`)."""
    taal = reservering['taal']
    restaurant = app_config['RESTAURANT_NAAM']
    privacy = app_config.get('PRIVACY')
    annuleer_url = f"{app_config['APP_BASE_URL']}/annuleren/{reservering['id']}"
    onderwerp = vertaal("Herinnering: je reservering morgen om {tijd} - {restaurant}", taal=taal,
                        tijd=reservering['tijd'], restaurant=restaurant)
    datum = hoofdletter(datum_tekst(reservering['datum'], met_jaar=True, taal=taal))
    regels = [
        vertaal("Beste {naam},", taal=taal, naam=reservering['naam']),
        "",
        vertaal("Morgen ben je welkom bij {restaurant}. We kijken ernaar uit!", taal=taal, restaurant=restaurant),
        "",
        "- " + vertaal("Datum: {datum}", taal=taal, datum=datum),
        "- " + vertaal("Tijdstip: {tijd}", taal=taal, tijd=reservering['tijd']),
        "- " + vertaal("Aantal personen: {aantal}", taal=taal, aantal=reservering['aantal']),
    ]
    if privacy is not None:
        regels.append("- " + vertaal("Adres: {adres}", taal=taal, adres=privacy.adres))
    regels += [
        "",
        vertaal("Kun je toch niet komen? Annuleer dan via deze link, dan geven we je plek aan een andere gast:", taal=taal),
        annuleer_url,
        vertaal("Wil je iets wijzigen? Bel ons op {telefoon}.", taal=taal, telefoon=app_config['RESTAURANT_TELEFOON']),
        "",
        vertaal("Met vriendelijke groet,", taal=taal),
        vertaal("Het team van {restaurant}", taal=taal, restaurant=restaurant),
    ]
    return {
        'from': app_config['VERZENDER_EMAIL'],
        'to': reservering['email'],
        'subject': onderwerp,
        'tekst': "\n".join(regels) + "\n",
    }

def stuur_herinnering(app_config, reservering):
    """Verstuurt de herinnering meteen (geen losse thread). True als de mail is verstuurd."""
    bericht = _bouw_herinneringsmail(app_config, reservering)
    return async_send_email(app_config, bericht, reservering['email'], reservering['id']) is True
