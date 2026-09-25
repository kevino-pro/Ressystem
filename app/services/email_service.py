import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app

def async_send_email(app_config, msg, recipient_email):
    try:
        if not app_config['VERZENDER_WACHTWOORD'] or app_config['VERZENDER_EMAIL'] == "jouw-restaurant@gmail.com":
            print(f"[E-MAIL SIMULATIE] Bevestigingsmail virtueel verzonden naar: {recipient_email}")
            return

        server = smtplib.SMTP(app_config['SMTP_SERVER'], app_config['SMTP_PORT'], timeout=10)
        server.starttls()
        server.login(app_config['VERZENDER_EMAIL'], app_config['VERZENDER_WACHTWOORD'])
        server.send_message(msg)
        server.quit()
        print(f"[SUCCESS] E-mail succesvol verzonden naar {recipient_email}")
    except Exception as e:
        print(f"[ERROR] Asynchrone e-mail mislukt naar {recipient_email}: {str(e)}")

def stuur_bevestigingsmail_async(ontvanger_email, naam, datum, tijd, aantal, reservering_id):
    app_config = current_app.config.copy()
    annuleer_url = f"http://127.0.0.1:5000/annuleren/{reservering_id}"
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

    threading.Thread(target=async_send_email, args=(app_config, msg, ontvanger_email), daemon=True).start()
