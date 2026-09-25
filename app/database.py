import uuid
from flask import current_app, g
from werkzeug.security import generate_password_hash
from sqlalchemy import (
    MetaData, Table, Column, Text, Integer, DateTime,
    create_engine, event, select, insert, delete, func, text,
)

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

def verwerk_reservering(conn, max_capaciteit, naam, email, telefoon, datum, tijd, aantal):
    """
    Enige plek waar een reservering wordt weggeschreven. Wordt door web.py (formulier)
    en api.py (AI-webhook) gebruikt zodat de capaciteitsregel maar op één plek staat.

    De check + insert moet atomisch zijn t.o.v. gelijktijdige boekingen op hetzelfde slot.
    SQLAlchemy Core abstraheert de queries zelf, maar de serialisatie-mechanismen verschillen
    onvermijdelijk per database: SQLite grijpt een exclusieve bestandslock (BEGIN EXCLUSIVE,
    afgedwongen via de 'begin'-event in init_db_pool), Postgres gebruikt een sessie-advisory-
    lock op de (datum, tijd)-sleutel met een lock_timeout zodat een aanvraag bij hoge contentie
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
                {'sleutel': f'{datum}|{tijd}'}
            )

        huidige_gasten = conn.execute(
            select(func.sum(reserveringen.c.aantal)).where(
                reserveringen.c.datum == datum, reserveringen.c.tijd == tijd
            )
        ).scalar() or 0

        if huidige_gasten + aantal > max_capaciteit:
            raise CapaciteitVolFout(max_capaciteit - huidige_gasten)

        unieke_id = str(uuid.uuid4())[:8]
        conn.execute(
            insert(reserveringen).values(
                id=unieke_id, naam=naam, email=email, telefoon=telefoon,
                datum=datum, tijd=tijd, aantal=aantal
            )
        )

    return unieke_id

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
        conn.execute(delete(reserveringen).where(reserveringen.c.id == reservering_id))

def schonen_oude_reserveringen():
    """Enige plek met dialect-specifieke SQL buiten de lock: datum-rekenkunde verschilt per database."""
    conn = get_db()
    retentie_dagen = int(current_app.config['RETENTIE_DAGEN_AVG'])
    if conn.engine.dialect.name == 'sqlite':
        grens = text("date('now', :offset)").bindparams(offset=f'-{retentie_dagen} days')
    else:
        grens = text("CURRENT_DATE - (:dagen * INTERVAL '1 day')").bindparams(dagen=retentie_dagen)
    with conn.begin():
        conn.execute(delete(reserveringen).where(reserveringen.c.datum < grens))

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
            conn.execute(
                insert(personeel).values(
                    gebruikersnaam='admin', wachtwoord_hash=generate_password_hash(initial_pw)
                )
            )
    schonen_oude_reserveringen()

