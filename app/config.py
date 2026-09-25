import os
import importlib

# Optionele dotenv lader voor lokale ontwikkeling
try:
    load_dotenv = importlib.import_module('dotenv').load_dotenv
    load_dotenv()
except (ImportError, AttributeError):
    pass

# --- AI SERVICEMODELS ---
ANTHROPIC_MODEL = os.getenv('ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001')

class Config:
    """
    Centrale configuratieklasse voor Whitelabel Agency Templates.
    Bij een nieuwe klant pas je alleen de waarden in .env aan.
    """

    # ==========================================
    # 1. BRANDING & RESTAURANT GEGEVENS
    # ==========================================
    RESTAURANT_NAAM = os.getenv('RESTAURANT_NAAM', 'Mijn Restaurant')
    RESTAURANT_TAGLINE = os.getenv('RESTAURANT_TAGLINE', 'Authentiek & Vers')
    RESTAURANT_EMAIL = os.getenv('RESTAURANT_EMAIL', 'info@restaurant.nl')
    RESTAURANT_TELEFOON = os.getenv('RESTAURANT_TELEFOON', '0612345678')
    PRIMARY_COLOR = os.getenv('PRIMARY_COLOR', '#d97706') # Tailwind Amber-600 default
    APP_BASE_URL = os.getenv('APP_BASE_URL', 'http://127.0.0.1:5000') # Voor links in e-mails (annuleren)

    # ==========================================
    # 2. CAPACITEIT & BUSINESS LOGIC
    # ==========================================
    MAX_CAPACITEIT_PER_SLOT = int(os.getenv('MAX_CAPACITEIT_PER_SLOT', 10))
    MAX_PERSONEN_PER_BOEKING = int(os.getenv('MAX_PERSONEN_PER_BOEKING', 20))
    RETENTIE_DAGEN_AVG = int(os.getenv('RETENTIE_DAGEN_AVG', 60))

    # ==========================================
    # 3. BEVEILIGING & DATABASE
    # ==========================================
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        SECRET_KEY = "DEV_ONLY_CHANGE_IN_PRODUCTION_SECRET_KEY"
        print("[SECURITY WARNING] Geen SECRET_KEY ingesteld in .env!")

    DATABASE_PAD = os.getenv('DATABASE_PAD', 'restaurant.db')
    WEBHOOK_API_KEY = os.getenv('WEBHOOK_API_KEY', 'default_agency_secret_key')
    ADMIN_INITIAL_PASSWORD = os.getenv('ADMIN_INITIAL_PASSWORD', 'VeiligWachtwoord123!')

    # ==========================================
    # 4. SMTP / E-MAIL SERVERS
    # ==========================================
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    VERZENDER_EMAIL = os.getenv('VERZENDER_EMAIL', 'jouw-restaurant@gmail.com')
    VERZENDER_WACHTWOORD = os.getenv('VERZENDER_WACHTWOORD', '')