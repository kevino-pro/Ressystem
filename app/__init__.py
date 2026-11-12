# app/__init__.py
import logging
from datetime import date
from pathlib import Path
import click
from flask import Flask, has_request_context
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.middleware.proxy_fix import ProxyFix
from app.security import csrf_token
from app.toegang import MIN_WACHTWOORD_LENGTE, huidige_gebruiker
from app.config import Config
from app.database import (
    init_db_pool, close_db, init_db, get_db, haal_reservering_op,
    controleer_dialect, dialect_uit_config, maak_gebruiker, tel_of_schoon_oude_reserveringen,
    te_herinneren, wis_allergieen_voor, zoek_dubbele_reserveringen,
    ProductieVlagVereist, ROLLEN,
)
from app.services.email_service import stuur_bevestigingsmail_sync
from app.reserveringsregels import laad_regels
from app.plattegrond import laad_plattegrond
from app.privacy import laad_privacy
from app.restaurant import laad_restaurant
from app.herinnering import laad_herinnering, morgen_en_grens, verstuur_herinneringen
from app.huisstijl import laad_huisstijl
from app import kopregels, taal, weergave

def create_app(config_class=Config):
    # Enige plek die dit configureert: geldt zo voor run.py, wsgi.py (gunicorn) en `flask` CLI-commands.
    # basicConfig is een no-op als er al handlers staan, dus dubbel aanroepen is onschadelijk.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app = Flask(__name__, template_folder='../templates', static_folder='../static')
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
    app.config['PLATTEGROND'] = laad_plattegrond(regels_pad)  # None als het bestand geen [plattegrond] heeft
    app.config['PRIVACY'] = laad_privacy(regels_pad)  # None als het bestand geen [privacy] heeft
    if app.config.get('APP_ENV') == 'production' and app.config['PRIVACY'] is None:
        raise RuntimeError(f"APP_ENV=production maar {regels_pad.name} heeft geen [privacy]; de privacyverklaring is verplicht.")
    restaurant = laad_restaurant(regels_pad)  # None als het bestand geen [restaurant] heeft
    if app.config.get('APP_ENV') == 'production' and restaurant is None:
        raise RuntimeError(f"APP_ENV=production maar {regels_pad.name} heeft geen [restaurant]; zet daar naam, email en telefoon.")
    if restaurant is not None:
        # Het restaurantbestand wint van RESTAURANT_NAAM/-EMAIL/-TELEFOON uit de omgeving: één bron per installatie.
        app.config['RESTAURANT_NAAM'] = restaurant.naam
        app.config['RESTAURANT_EMAIL'] = restaurant.email
        app.config['RESTAURANT_TELEFOON'] = restaurant.telefoon
    app.config['HUISSTIJL'] = laad_huisstijl(regels_pad, app.static_folder)
    app.config['TALEN'] = taal.laad_talen(regels_pad)  # zonder [talen] alleen Nederlands
    app.config['HERINNERING'] = laad_herinnering(regels_pad)  # None: geen herinneringsmails
    app.config['VERTALINGEN'] = taal.laad_vertalingen()

    init_db_pool(app)
    app.teardown_appcontext(close_db)

    if app.config.get('TRUSTED_PROXY_COUNT'):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=app.config['TRUSTED_PROXY_COUNT'])
    app.jinja_env.globals['csrf_token'] = csrf_token
    app.context_processor(lambda: {'huisstijl': app.config['HUISSTIJL']})
    # De ingelogde gebruiker voor het menu en de knoppen; None op gastpagina's en zonder geldige sessie.
    app.context_processor(lambda: {'gebruiker': huidige_gebruiker() if has_request_context() else None})
    weergave.registreer(app)
    taal.registreer(app)
    kopregels.registreer(app)

    from app.routes.web import web_bp
    from app.routes.api import api_bp
    from app.routes.beheer import beheer_bp
    from app.routes.accounts import accounts_bp
    from app.routes.account import account_bp
    from app.routes.invoeren import invoeren_bp
    from app.routes.cijfers import cijfers_bp

    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(beheer_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(invoeren_bp)
    app.register_blueprint(cijfers_bp)

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
    @click.option('--rol', type=click.Choice(ROLLEN), default='beheerder', show_default=True)
    @click.option('--productie', is_flag=True, help='Bevestig bewust een niet-SQLite database.')
    def create_admin_command(gebruikersnaam, rol, productie):
        """Maak een personeelsaccount aan (wachtwoord via verborgen prompt). Standaard een beheerder."""
        _guard(productie)
        wachtwoord = click.prompt('Wachtwoord', hide_input=True, confirmation_prompt=True)
        if len(wachtwoord) < MIN_WACHTWOORD_LENGTE:
            raise click.ClickException(f"Wachtwoord moet minstens {MIN_WACHTWOORD_LENGTE} tekens hebben.")
        try:
            aangemaakt = maak_gebruiker(get_db(), gebruikersnaam, wachtwoord, rol)
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
        """Toon of verwijder reserveringen buiten de bewaartermijn (RETENTIE_DAGEN_AVG); wist ook oude allergieën."""
        _guard(productie)
        try:
            aantal = tel_of_schoon_oude_reserveringen(get_db(), uitvoeren)
            if uitvoeren:
                gewist = wis_allergieen_voor(get_db(), app.config['REGELS'].nu().date().isoformat())
        except SQLAlchemyError:
            app.logger.error("purge-retention mislukt door een databasefout.")
            raise click.ClickException("Opschonen mislukt door een databasefout.")
        if uitvoeren:
            click.echo(f"{aantal} reservering(en) verwijderd.")
            click.echo(f"Bij {gewist} reservering(en) van voor vandaag de allergieën gewist.")
        else:
            click.echo(f"{aantal} reservering(en) zouden worden verwijderd (gebruik --uitvoeren).")

    @app.cli.command('herinneringen')
    @click.option('--uitvoeren', is_flag=True, help='Verstuur daadwerkelijk; zonder deze vlag alleen tellen.')
    @click.option('--productie', is_flag=True, help='Bevestig bewust een niet-SQLite database.')
    def herinneringen_command(uitvoeren, productie):
        """Toon of verstuur de herinneringsmails voor morgen (zonder op het ingestelde uur te wachten)."""
        _guard(productie)
        if app.config['HERINNERING'] is None:
            raise click.ClickException("Het restaurantbestand heeft geen [herinnering]; er gaan geen herinneringen uit.")
        morgen, grens = morgen_en_grens(app.config['REGELS'])
        try:
            if not uitvoeren:
                aantal = len(te_herinneren(get_db(), morgen, grens))
                click.echo(f"{aantal} herinnering(en) voor {morgen} klaar om te versturen (gebruik --uitvoeren).")
                return
            verstuurd = mislukt = 0
            while True:
                v, m, resterend = verstuur_herinneringen(get_db(), app.config)
                verstuurd, mislukt = verstuurd + v, mislukt + m
                if not resterend or not v:
                    break
        except SQLAlchemyError:
            app.logger.error("herinneringen mislukt door een databasefout.")
            raise click.ClickException("Herinneringen versturen mislukt door een databasefout.")
        click.echo(f"{verstuurd} herinnering(en) voor {morgen} verstuurd, {mislukt} mislukt.")
        if mislukt:
            raise SystemExit(1)

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
            aantal=reservering['aantal'], reservering_id=reservering['id'], taal=reservering['taal'],
        )
        click.echo(f"Mail opnieuw geprobeerd voor reservering {reservering_id} — zie logs voor [MAIL_SENT]/[MAIL_FAILED].")

    return app
