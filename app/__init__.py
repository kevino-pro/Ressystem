# app/__init__.py
import logging
import click
from flask import Flask
from sqlalchemy.exc import SQLAlchemyError
from app.config import Config
from app.database import init_db_pool, close_db, init_db, get_db, haal_reservering_op
from app.services.email_service import stuur_bevestigingsmail_sync

def create_app(config_class=Config):
    # Enige plek die dit configureert: geldt zo voor run.py, wsgi.py (gunicorn) en `flask` CLI-commands.
    # basicConfig is een no-op als er al handlers staan, dus dubbel aanroepen is onschadelijk.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app = Flask(__name__, template_folder='../templates')
    app.config.from_object(config_class)
    if not app.config.get('SECRET_KEY'):
        raise RuntimeError("Configureer SECRET_KEY via de omgeving voordat de app start.")
    if not (app.config.get('API_KEY') or app.config.get('WEBHOOK_API_KEY')):
        raise RuntimeError("Configureer API_KEY of WEBHOOK_API_KEY via de omgeving voordat de app start.")

    init_db_pool(app)
    app.teardown_appcontext(close_db)

    from app.routes.web import web_bp
    from app.routes.api import api_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)

    @app.cli.command('init-db')
    def init_db_command():
        """Initialiseer het databaseschema en de admin-gebruiker."""
        try:
            init_db()
        except SQLAlchemyError:
            app.logger.exception("Database-initialisatie mislukt: kon geen verbinding maken of query uitvoeren.")
            raise click.ClickException("Database-initialisatie mislukt, zie logs voor details.")
        else:
            app.logger.info("Database succesvol geïnitialiseerd.")
            click.echo("Database succesvol geïnitialiseerd.")

    @app.cli.command('resend-mail')
    @click.argument('reservering_id')
    def resend_mail_command(reservering_id):
        """Verstuur de bevestigingsmail opnieuw voor een bestaande reservering (na een [MAIL_FAILED] logregel)."""
        conn = get_db()
        reservering = haal_reservering_op(conn, reservering_id)
        if not reservering:
            raise click.ClickException(f"Geen reservering gevonden met id {reservering_id}")
        stuur_bevestigingsmail_sync(
            ontvanger_email=reservering['email'], naam=reservering['naam'],
            datum=reservering['datum'], tijd=reservering['tijd'],
            aantal=reservering['aantal'], reservering_id=reservering['id'],
        )
        click.echo(f"Mail opnieuw geprobeerd voor reservering {reservering_id} — zie logs voor [MAIL_SENT]/[MAIL_FAILED].")

    return app


    return app