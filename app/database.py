import secrets
from datetime import date, timedelta
from flask import current_app, g
from werkzeug.security import generate_password_hash
from sqlalchemy.engine import make_url
from sqlalchemy import (
    MetaData, Table, Column, Text, Integer, DateTime, ForeignKey,
    create_engine, event, select, insert, delete, func, text,
)
from app.normalisatie import normaliseer_email, normaliseer_telefoon

# Eén proces-brede engine; SQLAlchemy beheert zelf de connectie-pool per dialect.
_engine = None

metadata = MetaData()

reserveringen = Table(
    'reserveringen', metadata,
    Column('id', Text, primary_key=True),
    Column('naam', Text, nullable=False),
    Column('email', Text, nullable=False),
    Column('telefoon', Text, nullable=False),
    Column('datum', Text, nullable=False),
    Column('tijd', Text, nullable=False),
    Column('aantal', Integer, nullable=False),
    Column('aangemaakt_op', DateTime, server_default=func.current_timestamp()),
)

# Welke tafel(s) bij een reservering horen. Een groep kan meerdere tafels krijgen.
# De code verwijdert toewijzingen zelf mee met een reservering, want SQLite handhaaft
# foreign keys standaard niet; ON DELETE CASCADE is een extra vangnet op Postgres.
tafeltoewijzingen = Table(
    'tafeltoewijzingen', metadata,
    Column('reservering_id', Text, ForeignKey('reserveringen.id', ondelete='CASCADE'), primary_key=True),
    Column('tafel', Text, primary_key=True),
)

personeel = Table(
    'personeel', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('gebruikersnaam', Text, unique=True, nullable=False),
    Column('wachtwoord_hash', Text, nullable=False),
)

class CapaciteitVolFout(Exception):
    """Geen ruimte meer op het gevraagde tijdslot. `vrij` is het aantal resterende plekken (kan <= 0 zijn)."""
    def __init__(self, vrij):
        self.vrij = vrij
        super().__init__(f"Geen capaciteit: nog {vrij} plek(ken) vrij.")

MAANDEN = ("januari", "februari", "maart", "april", "mei", "juni", "juli",
           "augustus", "september", "oktober", "november", "december")

class DubbeleReserveringFout(Exception):
    """Deze gast heeft al een reservering op dezelfde datum en tijd. `bericht` is geschikt voor de gast."""
    def __init__(self, datum, tijd):
        dag = date.fromisoformat(datum)
        self.bericht = (
            f"Je hebt al een reservering op {dag.day} {MAANDEN[dag.month - 1]} om {tijd}. "
            "Die staat genoteerd, je hoeft niets opnieuw te doen. Wil je iets wijzigen? "
            "Gebruik de link in je bevestigingsmail of bel het restaurant."
        )
        super().__init__(self.bericht)

def init_db_pool(app):
    """
    Maakt de SQLAlchemy-engine op basis van DATABASE_URL (sqlite:/// of postgresql://).
    Alle CRUD-queries in dit bestand zijn dialect-onafhankelijk via SQLAlchemy Core; alleen
    de capaciteitslock (hieronder) blijft per-database anders, want dat is inherent zo.
    """
    global _engine
    if _engine is not None:
        return
    _engine = create_engine(app.config['DATABASE_URL'])

    @event.listens_for(_engine, "connect")
    def _sqlite_dbapi_autocommit(dbapi_connection, connection_record):
        # Laat SQLAlchemy zelf BEGIN/COMMIT sturen i.p.v. pysqlite's eigen impliciete transacties.
        if _engine.dialect.name == 'sqlite':
            dbapi_connection.isolation_level = None

    @event.listens_for(_engine, "begin")
    def _sqlite_begin(conn):
        if conn.engine.dialect.name == 'sqlite':
            statement = "BEGIN EXCLUSIVE" if conn.info.pop('exclusieve_lock', False) else "BEGIN"
            conn.exec_driver_sql(statement)

def get_db():
    """Geeft de connectie voor de huidige Flask-appcontext (request of handmatige app_context())."""
    if _engine is None:
        raise RuntimeError("Database-engine is niet geïnitialiseerd; roep init_db_pool(app) aan in create_app().")
    if 'db' not in g:
        g.db = _engine.connect()
    return g.db

def close_db(e=None):
    """Teardown-hook: geeft de connectie terug aan de pool van de engine."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def _minuten(tijd):
    uur, minuut = str(tijd).split(':')[:2]
    return int(uur) * 60 + int(minuut)

def piekbezetting(bestaande, start, zitduur):
    """
    Hoogste aantal gasten dat tegelijk aan tafel zit tijdens [start, start + zitduur).
    `bestaande` is een lijst (begin_in_minuten, aantal) van reserveringen op dezelfde dag;
    elke reservering bezet [begin, begin + zitduur). De bezetting kan alleen stijgen op het
    begin van een reservering, dus het volstaat om op die momenten (en op `start`) te tellen.
    """
    eind = start + zitduur
    momenten = {start} | {begin for begin, _ in bestaande if start <= begin < eind}
    return max(
        sum(aantal for begin, aantal in bestaande if begin <= moment < begin + zitduur)
        for moment in momenten
    )

class OnbekendeTafelFout(Exception):
    """Een tafelnummer staat niet op de plattegrond."""
    def __init__(self, tafels):
        self.bericht = f"Onbekende tafel: {', '.join(tafels)}."
        super().__init__(self.bericht)

class TafelBezetFout(Exception):
    """De tafel hoort al bij een andere reservering die in dezelfde zitduur valt."""
    def __init__(self, tafel, tijd):
        self.bericht = f"Tafel {tafel} is al toegewezen aan een reservering van {tijd}."
        super().__init__(self.bericht)

class GeenReserveringFout(Exception):
    """De reservering bestaat niet (meer)."""
    bericht = "Deze reservering bestaat niet meer. Ververs de pagina."

def wijs_tafels_toe(conn, reservering_id, tafels, plattegrond, zitduur_minuten):
    """
    Zet de tafels van een reservering; wat er stond wordt vervangen, een lege lijst maakt haar los.
    Weigert een tafel die al bij een andere reservering hoort die in dezelfde zitduur valt.
    Geeft een waarschuwing terug als er minder stoelen zijn dan gasten, anders None.

    Draait onder dezelfde daglock als verwerk_reservering, zodat twee mensen die tegelijk
    dezelfde tafel toewijzen niet allebei slagen.
    """
    tafels = list(dict.fromkeys(tafels))  # dubbele weg, volgorde behouden
    onbekend = [tafel for tafel in tafels if plattegrond.tafel(tafel) is None]
    if onbekend:
        raise OnbekendeTafelFout(onbekend)

    dialect = conn.engine.dialect.name
    if dialect == 'sqlite':
        conn.info['exclusieve_lock'] = True

    with conn.begin():
        reservering = conn.execute(
            select(reserveringen).where(reserveringen.c.id == reservering_id)
        ).mappings().first()
        if reservering is None:
            raise GeenReserveringFout()
        if dialect == 'postgresql':
            conn.execute(text("SET LOCAL lock_timeout = '5s'"))
            conn.execute(
                text("SELECT pg_advisory_xact_lock(hashtext('reservering_slot'), hashtext(:sleutel))"),
                {'sleutel': reservering['datum']}  # zelfde sleutel als verwerk_reservering
            )

        start = _minuten(reservering['tijd'])
        anderen = conn.execute(
            select(tafeltoewijzingen.c.tafel, reserveringen.c.tijd)
            .join(reserveringen, reserveringen.c.id == tafeltoewijzingen.c.reservering_id)
            .where(
                reserveringen.c.datum == reservering['datum'],
                tafeltoewijzingen.c.reservering_id != reservering_id,
            )
        )
        for rij in anderen:
            if rij.tafel in tafels and abs(_minuten(rij.tijd) - start) < zitduur_minuten:
                raise TafelBezetFout(rij.tafel, rij.tijd)

        conn.execute(delete(tafeltoewijzingen).where(tafeltoewijzingen.c.reservering_id == reservering_id))
        if tafels:
            conn.execute(
                insert(tafeltoewijzingen),
                [{'reservering_id': reservering_id, 'tafel': tafel} for tafel in tafels],
            )

    stoelen = sum(plattegrond.tafel(tafel).stoelen for tafel in tafels)
    if tafels and stoelen < reservering['aantal']:
        return f"Let op: {stoelen} stoelen voor {reservering['aantal']} gasten."
    return None

def haal_toewijzingen_op(conn, datum):
    """Tafels per reservering op deze datum: {reservering_id: [tafel, ...]}."""
    with conn.begin():
        rijen = conn.execute(
            select(tafeltoewijzingen.c.reservering_id, tafeltoewijzingen.c.tafel)
            .join(reserveringen, reserveringen.c.id == tafeltoewijzingen.c.reservering_id)
            .where(reserveringen.c.datum == datum)
            .order_by(tafeltoewijzingen.c.reservering_id, tafeltoewijzingen.c.tafel)
        ).all()
    toewijzingen = {}
    for reservering_id, tafel in rijen:
        toewijzingen.setdefault(reservering_id, []).append(tafel)
    return toewijzingen

def is_zelfde_gast(a, b):
    """
    True als twee reserveringen (mappings met email en telefoon) bij dezelfde gast horen:
    hetzelfde e-mailadres of telefoonnummer, na normalisatie. De naam telt niet mee:
    twee verschillende gasten kunnen dezelfde naam hebben.
    """
    return (
        normaliseer_email(a['email']) == normaliseer_email(b['email'])
        or normaliseer_telefoon(a['telefoon']) == normaliseer_telefoon(b['telefoon'])
    )

def _heeft_al_reservering(conn, gast, datum, tijd):
    """
    Zoekt een bestaande reservering van dezelfde gast op exact dezelfde datum en tijd.
    Vergelijkt in Python in plaats van in SQL, zodat het op SQLite en Postgres precies gelijk werkt.
    """
    bestaande = conn.execute(
        select(reserveringen.c.naam, reserveringen.c.email, reserveringen.c.telefoon).where(
            reserveringen.c.datum == datum, reserveringen.c.tijd == tijd
        )
    ).mappings()
    return any(is_zelfde_gast(rij, gast) for rij in bestaande)

def verwerk_reservering(conn, max_capaciteit, naam, email, telefoon, datum, tijd, aantal, zitduur_minuten=None):
    """
    Enige plek waar een reservering wordt weggeschreven. Wordt door web.py (formulier)
    en api.py (AI-webhook) gebruikt zodat de capaciteitsregel maar op één plek staat.

    Met `zitduur_minuten` telt elke reservering zo lang mee: `max_capaciteit` is dan het
    maximale aantal gasten tegelijk aan tafel. Zonder zitduur (None) tellen alleen
    reserveringen op exact hetzelfde tijdstip mee (oud gedrag, nog gebruikt in tests).

    Heeft dezelfde gast al een reservering op deze datum en tijd, dan volgt DubbeleReserveringFout.
    Die controle draait binnen dezelfde lock als de capaciteit, zodat een herhaalde of gelijktijdige
    poging nooit een tweede boeking oplevert.

    De check + insert moet atomisch zijn t.o.v. gelijktijdige boekingen op hetzelfde slot.
    SQLAlchemy Core abstraheert de queries zelf, maar de serialisatie-mechanismen verschillen
    onvermijdelijk per database: SQLite grijpt een exclusieve bestandslock (BEGIN EXCLUSIVE,
    afgedwongen via de 'begin'-event in init_db_pool), Postgres gebruikt een sessie-advisory-
    lock op de datum met een lock_timeout zodat een aanvraag bij hoge contentie
    faalt in plaats van te blijven hangen. Beide geven de lock automatisch vrij bij commit of
    rollback van de transactie; bij CapaciteitVolFout rollt `with conn.begin():` terug.
    """
    dialect = conn.engine.dialect.name
    if dialect == 'sqlite':
        conn.info['exclusieve_lock'] = True

    with conn.begin():
        if dialect == 'postgresql':
            conn.execute(text("SET LOCAL lock_timeout = '5s'"))
            conn.execute(
                text("SELECT pg_advisory_xact_lock(hashtext('reservering_slot'), hashtext(:sleutel))"),
                {'sleutel': datum}  # per dag: met een zitduur overlappen tijden elkaar
            )

        if _heeft_al_reservering(conn, {'naam': naam, 'email': email, 'telefoon': telefoon}, datum, tijd):
            raise DubbeleReserveringFout(datum, tijd)

        if zitduur_minuten is None:
            huidige_gasten = conn.execute(
                select(func.sum(reserveringen.c.aantal)).where(
                    reserveringen.c.datum == datum, reserveringen.c.tijd == tijd
                )
            ).scalar() or 0
        else:
            bestaande = [
                (_minuten(rij.tijd), rij.aantal)
                for rij in conn.execute(
                    select(reserveringen.c.tijd, reserveringen.c.aantal).where(reserveringen.c.datum == datum)
                )
            ]
            huidige_gasten = piekbezetting(bestaande, _minuten(tijd), zitduur_minuten)

        if huidige_gasten + aantal > max_capaciteit:
            raise CapaciteitVolFout(max_capaciteit - huidige_gasten)

        unieke_id = secrets.token_urlsafe(16)
        conn.execute(
            insert(reserveringen).values(
                id=unieke_id, naam=naam, email=email, telefoon=telefoon,
                datum=datum, tijd=tijd, aantal=aantal
            )
        )

    return unieke_id

def zoek_dubbele_reserveringen(conn, vanaf):
    """
    Alleen lezen: groepen reserveringen vanaf `vanaf` ('YYYY-MM-DD') die bij dezelfde gast op
    dezelfde datum en tijd horen: hetzelfde e-mailadres of telefoonnummer volgens is_zelfde_gast.
    De naam telt niet mee, net als bij het boeken. Elke groep is een lijst rijen, oudste eerst.
    """
    with conn.begin():
        rijen = conn.execute(
            select(reserveringen).where(reserveringen.c.datum >= vanaf).order_by(
                reserveringen.c.datum, reserveringen.c.tijd, reserveringen.c.aangemaakt_op, reserveringen.c.id
            )
        ).mappings().all()
    per_tijdstip = {}
    for rij in rijen:
        per_tijdstip.setdefault((rij['datum'], rij['tijd']), []).append(rij)
    groepen = []
    for rijen_op_tijdstip in per_tijdstip.values():
        restant = list(rijen_op_tijdstip)
        while restant:
            groep = [restant.pop(0)]
            # Blijf aanvullen: A en C kunnen via B bij elkaar horen (zelfde mail, dan zelfde telefoon).
            gevonden = True
            while gevonden:
                gevonden = [r for r in restant if any(is_zelfde_gast(r, g) for g in groep)]
                for r in gevonden:
                    restant.remove(r)
                groep.extend(gevonden)
            if len(groep) > 1:
                groepen.append(groep)
    return groepen

def haal_personeel_op(conn, gebruikersnaam):
    with conn.begin():
        return conn.execute(
            select(personeel).where(personeel.c.gebruikersnaam == gebruikersnaam)
        ).mappings().first()

def haal_reserveringen_op(conn, datum=None):
    query = select(reserveringen)
    if datum:
        query = query.where(reserveringen.c.datum == datum).order_by(reserveringen.c.tijd.asc())
    else:
        query = query.order_by(reserveringen.c.datum.desc(), reserveringen.c.tijd.asc())
    with conn.begin():
        return conn.execute(query).mappings().all()

def haal_reservering_op(conn, reservering_id):
    with conn.begin():
        return conn.execute(
            select(reserveringen).where(reserveringen.c.id == reservering_id)
        ).mappings().first()

def verwijder_reservering(conn, reservering_id):
    with conn.begin():
        conn.execute(delete(tafeltoewijzingen).where(tafeltoewijzingen.c.reservering_id == reservering_id))
        conn.execute(delete(reserveringen).where(reserveringen.c.id == reservering_id))

def _retentiegrens():
    """
    Grensdatum voor de bewaartermijn (RETENTIE_DAGEN_AVG) als 'YYYY-MM-DD'-tekst.
    `datum` is een Text-kolom; tekst-met-tekst vergelijken werkt op SQLite en Postgres gelijk,
    en ISO-datums sorteren als tekst in de juiste volgorde.
    """
    retentie_dagen = int(current_app.config['RETENTIE_DAGEN_AVG'])
    return (date.today() - timedelta(days=retentie_dagen)).isoformat()

def _verwijder_ouder_dan(conn, grens):
    """Verwijdert reserveringen (en hun tafeltoewijzingen) met een datum voor `grens`."""
    oude_ids = select(reserveringen.c.id).where(reserveringen.c.datum < grens)
    conn.execute(delete(tafeltoewijzingen).where(tafeltoewijzingen.c.reservering_id.in_(oude_ids)))
    conn.execute(delete(reserveringen).where(reserveringen.c.datum < grens))

def schonen_oude_reserveringen():
    conn = get_db()
    grens = _retentiegrens()
    with conn.begin():
        _verwijder_ouder_dan(conn, grens)

def tel_of_schoon_oude_reserveringen(conn, uitvoeren):
    """Telt reserveringen buiten de bewaartermijn en verwijdert ze alleen als `uitvoeren` True is."""
    grens = _retentiegrens()
    with conn.begin():
        aantal = conn.execute(
            select(func.count()).select_from(reserveringen).where(reserveringen.c.datum < grens)
        ).scalar()
        if uitvoeren and aantal:
            _verwijder_ouder_dan(conn, grens)
    return aantal

def maak_gebruiker(conn, gebruikersnaam, wachtwoord):
    """Maakt een personeelsaccount aan. Geeft False terug (zonder iets te wijzigen) als de naam al bestaat."""
    with conn.begin():
        bestaat = conn.execute(
            select(personeel.c.id).where(personeel.c.gebruikersnaam == gebruikersnaam)
        ).first()
        if bestaat:
            return False
        conn.execute(
            insert(personeel).values(
                gebruikersnaam=gebruikersnaam, wachtwoord_hash=generate_password_hash(wachtwoord)
            )
        )
    return True

class ProductieVlagVereist(Exception):
    """Het commando richt zich op een niet-SQLite database en `--productie` ontbreekt."""

def controleer_dialect(dialect_naam, productie):
    """Guard op databasetype (niet op hostnaam): alleen SQLite mag zonder expliciete --productie."""
    if dialect_naam != 'sqlite' and not productie:
        raise ProductieVlagVereist(
            "Dit commando richt zich op een niet-SQLite database. Voeg --productie toe als dat bewust is."
        )

def dialect_uit_config(app):
    """Leest alleen de backend-naam uit DATABASE_URL; maakt geen verbinding en laadt geen driver."""
    return make_url(app.config['DATABASE_URL']).get_backend_name()

def init_db():
    conn = get_db()
    metadata.create_all(conn)
    conn.commit()  # create_all op een Connection begint impliciet een transactie; die sluiten we hier af
    with conn.begin():
        admin_bestaat = conn.execute(
            select(personeel.c.id).where(personeel.c.gebruikersnaam == 'admin')
        ).first()
        if not admin_bestaat:
            initial_pw = current_app.config['ADMIN_INITIAL_PASSWORD']
            if not initial_pw:
                raise RuntimeError("Configureer ADMIN_INITIAL_PASSWORD voordat de admin-gebruiker wordt aangemaakt.")
            conn.execute(
                insert(personeel).values(
                    gebruikersnaam='admin', wachtwoord_hash=generate_password_hash(initial_pw)
                )
            )
    schonen_oude_reserveringen()

