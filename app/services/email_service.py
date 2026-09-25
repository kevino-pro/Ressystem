import smtplib
import socket
import threading
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app

logger = logging.getLogger(__name__)

def async_send_email(app_config, msg, recipient_email, reservering_id):
    # Deze functie draait op een losse thread, ná het versturen van de HTTP-response.
    # De reservering is dan al in de database gezet en de klant heeft al een antwoord
    # gekregen -- we kunnen de klant hier niets meer laten weten. Het enige wat we nog
    # kunnen doen is duidelijk loggen (met reservering_id) zodat personeel een gemiste
    # bevestigingsmail kan terugvinden en de klant zelf kan benaderen.
    try:
        if not app_config['VERZENDER_WACHTWOORD'] or app_config['VERZENDER_EMAIL'] == "jouw-restaurant@gmail.com":
            logger.info(f"[E-MAIL SIMULATIE] Bevestigingsmail virtueel verzonden naar: {recipient_email} (reservering {reservering_id})")
            return

        with smtplib.SMTP(app_config['SMTP_SERVER'], app_config['SMTP_PORT'], timeout=10) as server:
            server.starttls()
            server.login(app_config['VERZENDER_EMAIL'], app_config['VERZENDER_WACHTWOORD'])
            server.send_message(msg)

        logger.info(f"E-mail succesvol verzonden naar {recipient_email} (reservering {reservering_id})")
    except (smtplib.SMTPException, socket.error, OSError) as e:
        logger.error(
            f"Bevestigingsmail mislukt naar {recipient_email} voor reservering {reservering_id}: {e}",
            exc_info=True
        )

def stuur_bevestigingsmail_async(ontvanger_email, naam, datum, tijd, aantal, reservering_id):
    app_config = current_app.config.copy()
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
    msg = MIMEMultipart()
    msg['From'] = app_config['VERZENDER_EMAIL']
    msg['To'] = ontvanger_email
    msg['Subject'] = onderwerp
    msg.attach(MIMEText(bericht_inhoud, 'plain'))

    threading.Thread(target=async_send_email, args=(app_config, msg, ontvanger_email, reservering_id), daemon=True).start()
