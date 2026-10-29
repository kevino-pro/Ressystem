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
    try:
        if app_config.get('RESEND_API_KEY'):
            _verstuur_via_resend(app_config, bericht)
        elif not app_config['VERZENDER_WACHTWOORD'] or app_config['VERZENDER_EMAIL'] == "jouw-restaurant@gmail.com":
            logger.info("[MAIL_SIMULATIE] reservering_id=%s", reservering_id)
            return
        else:
            _verstuur_via_smtp(app_config, bericht)

        logger.info("[MAIL_SENT] reservering_id=%s", reservering_id)
    except urllib.error.HTTPError as error:
        logger.error("[MAIL_FAILED] reservering_id=%s error_type=%s status=%s", reservering_id, type(error).__name__, error.code)
    except (smtplib.SMTPException, socket.error, OSError) as error:
        logger.error("[MAIL_FAILED] reservering_id=%s error_type=%s", reservering_id, type(error).__name__)

def _bouw_bevestigingsmail(app_config, ontvanger_email, naam, datum, tijd, aantal, reservering_id):
    annuleer_url = f"{app_config['APP_BASE_URL']}/annuleren/{reservering_id}"
    onderwerp = f"Bevestiging van je reservering - {app_config['RESTAURANT_NAAM']}"

    bericht_inhoud = f"""Beste {naam},

Bedankt voor je reservering bij {app_config['RESTAURANT_NAAM']}!

Hier zijn de gegevens van je reservering:
- Datum: {datum}
- Tijdstip: {tijd}
- Aantal personen: {aantal}

Wil je de reservering wijzigen of annuleren? Klik op deze link:
{annuleer_url}

Met vriendelijke groet,
Het team van {app_config['RESTAURANT_NAAM']}
"""
    return {
        'from': app_config['VERZENDER_EMAIL'],
        'to': ontvanger_email,
        'subject': onderwerp,
        'tekst': bericht_inhoud,
    }

def stuur_bevestigingsmail_async(ontvanger_email, naam, datum, tijd, aantal, reservering_id):
    app_config = current_app.config.copy()
    bericht = _bouw_bevestigingsmail(app_config, ontvanger_email, naam, datum, tijd, aantal, reservering_id)
    threading.Thread(target=async_send_email, args=(app_config, bericht, ontvanger_email, reservering_id), daemon=True).start()

def stuur_bevestigingsmail_sync(ontvanger_email, naam, datum, tijd, aantal, reservering_id):
    """Blokkerende variant van stuur_bevestigingsmail_async, voor de `flask resend-mail` CLI."""
    app_config = current_app.config.copy()
    bericht = _bouw_bevestigingsmail(app_config, ontvanger_email, naam, datum, tijd, aantal, reservering_id)
    async_send_email(app_config, bericht, ontvanger_email, reservering_id)
