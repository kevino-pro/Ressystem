# app/__init__.py
import logging
from datetime import date
from pathlib import Path
import click
from flask import Flask
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.middleware.proxy_fix import ProxyFix
from app.security import csrf_token
from app.config import Config
from app.database import (
    init_db_pool, close_db, init_db, get_db, haal_reservering_op,
    controleer_dialect, dialect_uit_config, maak_gebruiker, tel_of_schoon_oude_reserveringen,
    zoek_dubbele_reserveringen,
    ProductieVlagVereist,
)
from app.services.email_service import stuur_bevestigingsmail_sync
from app.reserveringsregels import laad_regels

MIN_WACHTWOORD_LENGTE = 12

def create_app(config_class=Config):
    # Enige plek die dit configureert: geldt zo voor run.py, wsgi.py (gunicorn) en `flask` CLI-commands.
    # basicConfig is een no-op als er al handlers staan, dus dubbel aanroepen is onschadelijk.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app = Flask(__name__, template_folder='../templates')
    app.config.from_object(config_class)
    if not app.config.get('SECRET_KEY'):
        raise RuntimeError("Configureer SECRET_KEY via de omgeving voordat de app start.")
    if not any(str(app.config.get(k) or '').strip() for k in ('API_KEY', 'WEBHOOK_API_KEY')):
        raise RuntimeError("Configureer API_KEY of WEBHOOK_API_KEY via de omgeving voordat de app start.")
    if app.config.get('APP_ENV') == 'production' and app.config.get('DATABASE_URL_IS_DEFAULT'):
        raise RuntimeError("APP_ENV=production maar DATABASE_URL ontbreekt; de app valt niet terug op SQLite.")
    if app.config.get('APP_ENV') == 'production' and app.config.get('RESTAURANT_CONFIG_IS_DEFAULT'):
        raise RuntimeError("APP_ENV=production maar RESTAURANT_CONFIG ontbreekt; zet het pad naar restaurants/<naam>.toml.")
    # Relatieve paden gelden vanaf de projectmap, zodat het niet uitmaakt waar gunicorn of flask start.
    regels_pad = Path(app.config['RESTAURANT_CONFIG'])
    if not regels_pad.is_absolute():
        regels_pad = Path(app.root_path).parent / regels_pad
    app.config['REGELS'] = laad_regels(regels_pad)

    init_db_pool(app)
    app.teardown_appcontext(close_db)

    if app.config.get('TRUSTED_PROXY_COUNT'):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=app.config['TRUSTED_PROXY_COUNT'])
    app.jinja_env.globals['csrf_token'] = csrf_token

    from app.routes.web import web_bp
    from app.routes.api import api_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)

    def _guard(productie):
        try:
            controleer_dialect(dialect_uit_config(app), productie)
        except ProductieVlagVereist as e:
            raise click.ClickException(str(e))

    @app.cli.command('init-db')
    @click.option('--productie', is_flag=True, help='Bevestig bewust een niet-SQLite database.')
    def init_db_command(productie):
        """Initialiseer het databaseschema en de admin-gebruiker."""
        _guard(productie)
        try:
            init_db()
        except SQLAlchemyError:
            app.logger.exception("Database-initialisatie mislukt: kon geen verbinding maken of query uitvoeren.")
            raise click.ClickException("Database-initialisatie mislukt, zie logs voor details.")
        else:
            app.logger.info("Database succesvol geïnitialiseerd.")
            click.echo("Database succesvol geïnitialiseerd.")

    @app.cli.command('create-admin')
    @click.option('--gebruikersnaam', default='admin', show_default=True)
    @click.option('--productie', is_flag=True, help='Bevestig bewust een niet-SQLite database.')
    def create_admin_command(gebruikersnaam, productie):
        """Maak een personeelsaccount aan (wachtwoord via verborgen prompt)."""
        _guard(productie)
        wachtwoord = click.prompt('Wachtwoord', hide_input=True, confirmation_prompt=True)
        if len(wachtwoord) < MIN_WACHTWOORD_LENGTE:
            raise click.ClickException(f"Wachtwoord moet minstens {MIN_WACHTWOORD_LENGTE} tekens hebben.")
        try:
            aangemaakt = maak_gebruiker(get_db(), gebruikersnaam, wachtwoord)
        except SQLAlchemyError:
            app.logger.error("create-admin mislukt door een databasefout.")
            raise click.ClickException("Aanmaken mislukt door een databasefout.")
        click.echo("aangemaakt" if aangemaakt else "bestaat al")
        if not aangemaakt:
            raise SystemExit(1)

    @app.cli.command('purge-retention')
    @click.option('--uitvoeren', is_flag=True, help='Verwijder daadwerkelijk; zonder deze vlag alleen tellen.')
    @click.option('--productie', is_flag=True, help='Bevestig bewust een niet-SQLite database.')
    def purge_retention_command(uitvoeren, productie):
        """Toon of verwijder reserveringen buiten de bewaartermijn (RETENTIE_DAGEN_AVG)."""
        _guard(productie)
        try:
            aantal = tel_of_schoon_oude_reserveringen(get_db(), uitvoeren)
        except SQLAlchemyError:
            app.logger.error("purge-retention mislukt door een databasefout.")
            raise click.ClickException("Opschonen mislukt door een databasefout.")
        if uitvoeren:
            click.echo(f"{aantal} reservering(en) verwijderd.")
        else:
            click.echo(f"{aantal} reservering(en) zouden worden verwijderd (gebruik --uitvoeren).")

    @app.cli.command('dubbele-reserveringen')
    @click.option('--productie', is_flag=True, help='Bevestig bewust een niet-SQLite database.')
    def dubbele_reserveringen_command(productie):
        """Toon (alleen lezen) toekomstige reserveringen die dubbel lijken. Verwijdert niets."""
        _guard(productie)
        try:
            groepen = zoek_dubbele_reserveringen(get_db(), date.today().isoformat())
        except SQLAlchemyError:
            app.logger.error("dubbele-reserveringen mislukt door een databasefout.")
            raise click.ClickException("Zoeken mislukt door een databasefout.")
        if not groepen:
            click.echo("Geen dubbele reserveringen gevonden.")
            return
        for groep in groepen:
            eerste = groep[0]
            click.echo(f"{eerste['datum']} {eerste['tijd']}: {len(groep)} reserveringen")
            for rij in groep:
                # Geen volledige persoonsgegevens in de terminal of logs: voornaam en begin van het e-mailadres.
                voornaam = rij['naam'].split()[0] if rij['naam'].split() else '?'
                click.echo(
                    f"  id={rij['id']}  {voornaam}  {rij['email'][:3]}***  {rij['aantal']} pers.  "
                    f"aangemaakt {rij['aangemaakt_op']}"
                )
        click.echo(f"{len(groepen)} groep(en). Houd per groep de oudste; verwijder de rest via het personeelsoverzicht.")

    @app.cli.command('resend-mail')
    @click.argument('reservering_id')
    @click.option('--productie', is_flag=True, help='Bevestig bewust een niet-SQLite database.')
    def resend_mail_command(reservering_id, productie):
        """Verstuur de bevestigingsmail opnieuw voor een bestaande reservering (na een [MAIL_FAILED] logregel)."""
        _guard(productie)
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
