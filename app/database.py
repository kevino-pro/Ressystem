import secrets
from datetime import date, timedelta
from flask import current_app, g
from werkzeug.security import generate_password_hash
from sqlalchemy.engine import make_url
from sqlalchemy import (
    MetaData, Table, Column, Text, Integer, Boolean, DateTime, ForeignKey,
    create_engine, event, select, insert, delete, update, func, text, true,
)
from app.normalisatie import normaliseer_email, normaliseer_telefoon
from app.taal import MAANDEN as MAANDEN_PER_TAAL, huidige_taal, vertaal

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
    Column('opmerking', Text, nullable=True),
    Column('kinderstoelen', Integer, nullable=False, server_default='0'),
    # Gezondheidsgegevens: alleen met aparte toestemming, en de dag na het bezoek gewist.
    Column('allergieen', Text, nullable=True),
    # Waar de reservering vandaan komt (zie BRONNEN) en welk personeelsaccount hem invoerde.
    Column('bron', Text, nullable=False, server_default='online'),
    Column('ingevoerd_door', Text, nullable=True),
    # verwacht, gearriveerd of no_show (zie STATUSSEN); een no-show telt niet mee in de bezetting.
    Column('status', Text, nullable=False, server_default='verwacht'),
    Column('taal', Text, nullable=False, server_default='nl'),  # taal van de gast, voor de mails
)

BRONNEN = ('online', 'ai', 'telefoon', 'binnenloper')

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
    Column('rol', Text, nullable=False, server_default='medewerker'),
    Column('actief', Boolean, nullable=False, server_default=true()),
)

ROLLEN = ('beheerder', 'medewerker')
STATUSSEN = ('verwacht', 'gearriveerd', 'no_show')
NIET_GEKOMEN = 'no_show'

class CapaciteitVolFout(Exception):
    """Geen ruimte meer op het gevraagde tijdslot. `vrij` is het aantal resterende plekken (kan <= 0 zijn)."""
    def __init__(self, vrij):
        self.vrij = vrij
        super().__init__(f"Geen capaciteit: nog {vrij} plek(ken) vrij.")

class KinderstoelVolFout(Exception):
    """Alle kinderstoelen zijn tijdens (een deel van) de zitduur al gereserveerd."""
    bericht = ("Op deze tijd zijn alle kinderstoelen al gereserveerd. "
               "Kies een andere tijd, of bel ons, dan zoeken we samen een oplossing.")

    def __init__(self):
        super().__init__(self.bericht)

    def vertaald(self):
        return vertaal(self.bericht)

MAANDEN = ("januari", "februari", "maart", "april", "mei", "juni", "juli",
           "augustus", "september", "oktober", "november", "december")

class DubbeleReserveringFout(Exception):
    """
    Deze gast heeft al een reservering op dezelfde datum en tijd. `bericht` is geschikt voor de gast
    (Nederlands); vertaald() geeft hem in de taal van het verzoek.
    """
    SJABLOON = ("Je hebt al een reservering op {datum} om {tijd}. "
                "Die staat genoteerd, je hoeft niets opnieuw te doen. Wil je iets wijzigen? "
                "Gebruik de link in je bevestigingsmail of bel het restaurant.")

    def __init__(self, datum, tijd):
        self.dag = date.fromisoformat(datum)
        self.tijd = tijd
        self.bericht = self.SJABLOON.format(datum=f"{self.dag.day} {MAANDEN[self.dag.month - 1]}", tijd=tijd)
        super().__init__(self.bericht)

    def vertaald(self):
        taal = huidige_taal()
        datum = f"{self.dag.day} {MAANDEN_PER_TAAL[taal][self.dag.month - 1]}"
        return vertaal(self.SJABLOON, taal=taal, datum=datum, tijd=self.tijd)

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

def minuten_van(tijd):
    """'19:30' wordt 1170: minuten sinds middernacht."""
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

def drukte_bij(conn, datum, tijd, zitduur_minuten):
    """
    Hoeveel gasten en kinderstoelen er al tegelijk zijn tijdens [tijd, tijd + zitduur) op `datum`.
    Alleen lezen; voor de waarschuwing bij een reservering door het personeel.
    """
    with conn.begin():
        rijen = conn.execute(
            select(reserveringen.c.tijd, reserveringen.c.aantal, reserveringen.c.kinderstoelen)
            .where(reserveringen.c.datum == datum, reserveringen.c.status != NIET_GEKOMEN)
        ).all()
    start = minuten_van(tijd)
    gasten = piekbezetting([(minuten_van(r.tijd), r.aantal) for r in rijen], start, zitduur_minuten)
    stoelen = piekbezetting([(minuten_van(r.tijd), r.kinderstoelen) for r in rijen], start, zitduur_minuten)
    return gasten, stoelen

def bezetting_op(conn, datum):
    """
    Lijst (begin_in_minuten, aantal) van alle reserveringen op deze dag, voor piekbezetting().
    Een no-show telt niet mee: zijn plaatsen komen weer vrij.
    """
    with conn.begin():
        return [
            (minuten_van(rij.tijd), rij.aantal)
            for rij in conn.execute(
                select(reserveringen.c.tijd, reserveringen.c.aantal).where(
                    reserveringen.c.datum == datum, reserveringen.c.status != NIET_GEKOMEN
                )
            )
        ]

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

        start = minuten_van(reservering['tijd'])
        anderen = conn.execute(
            select(tafeltoewijzingen.c.tafel, reserveringen.c.tijd)
            .join(reserveringen, reserveringen.c.id == tafeltoewijzingen.c.reservering_id)
            .where(
                reserveringen.c.datum == reservering['datum'],
                tafeltoewijzingen.c.reservering_id != reservering_id,
                reserveringen.c.status != NIET_GEKOMEN,  # een no-show bezet geen tafel meer
            )
        )
        for rij in anderen:
            if rij.tafel in tafels and abs(minuten_van(rij.tijd) - start) < zitduur_minuten:
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

def haal_toewijzingen_op(conn, datum=None):
    """Tafels per reservering op deze datum (of alle datums bij None): {reservering_id: [tafel, ...]}."""
    query = (
        select(tafeltoewijzingen.c.reservering_id, tafeltoewijzingen.c.tafel)
        .join(reserveringen, reserveringen.c.id == tafeltoewijzingen.c.reservering_id)
        .order_by(tafeltoewijzingen.c.reservering_id, tafeltoewijzingen.c.tafel)
    )
    if datum:
        query = query.where(reserveringen.c.datum == datum)
    with conn.begin():
        rijen = conn.execute(query).all()
    toewijzingen = {}
    for reservering_id, tafel in rijen:
        toewijzingen.setdefault(reservering_id, []).append(tafel)
    return toewijzingen

def is_zelfde_gast(a, b):
    """
    True als twee reserveringen (mappings met email en telefoon) bij dezelfde gast horen:
    hetzelfde e-mailadres of telefoonnummer, na normalisatie. De naam telt niet mee:
    twee verschillende gasten kunnen dezelfde naam hebben. Een leeg e-mailadres of telefoonnummer
    (mogelijk bij een reservering door het personeel) telt nooit als gelijk.
    """
    email_a, email_b = normaliseer_email(a['email'] or ''), normaliseer_email(b['email'] or '')
    tel_a, tel_b = normaliseer_telefoon(a['telefoon'] or ''), normaliseer_telefoon(b['telefoon'] or '')
    return bool((email_a and email_a == email_b) or (tel_a and tel_a == tel_b))

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

def verwerk_reservering(conn, max_capaciteit, naam, email, telefoon, datum, tijd, aantal, zitduur_minuten=None,
                        kinderstoelen=0, max_kinderstoelen=None, opmerking=None, allergieen=None,
                        bron='online', ingevoerd_door=None, taal='nl'):
    """
    Enige plek waar een reservering wordt weggeschreven. Wordt door web.py (formulier)
    en api.py (AI-webhook) gebruikt zodat de capaciteitsregel maar op één plek staat.

    Met `zitduur_minuten` telt elke reservering zo lang mee: `max_capaciteit` is dan het
    maximale aantal gasten tegelijk aan tafel. Zonder zitduur (None) tellen alleen
    reserveringen op exact hetzelfde tijdstip mee (oud gedrag, nog gebruikt in tests).

    Met `max_kinderstoelen` (het aantal in het restaurant) telt het systeem ook de kinderstoelen
    over de zitduur. Passen ze niet meer, dan volgt KinderstoelVolFout. Zonder `max_kinderstoelen`
    (None) wordt dat niet gecontroleerd.

    Een no-show (status 'no_show') telt niet mee voor gasten en kinderstoelen.

    `taal` is de taal van de gast ('en', 'nl' of 'id'); daarin gaan de mails.

    Met `max_capaciteit` None (reservering door het personeel) wordt de capaciteit niet afgedwongen;
    het personeel krijgt vooraf een waarschuwing via drukte_bij().

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
                    reserveringen.c.datum == datum, reserveringen.c.tijd == tijd,
                    reserveringen.c.status != NIET_GEKOMEN,
                )
            ).scalar() or 0
        else:
            bestaande = [
                (minuten_van(rij.tijd), rij.aantal)
                for rij in conn.execute(
                    select(reserveringen.c.tijd, reserveringen.c.aantal).where(
                        reserveringen.c.datum == datum, reserveringen.c.status != NIET_GEKOMEN
                    )
                )
            ]
            huidige_gasten = piekbezetting(bestaande, minuten_van(tijd), zitduur_minuten)

        if max_capaciteit is not None and huidige_gasten + aantal > max_capaciteit:
            raise CapaciteitVolFout(max_capaciteit - huidige_gasten)

        if kinderstoelen and max_kinderstoelen is not None:
            stoelen = [
                (minuten_van(rij.tijd), rij.kinderstoelen)
                for rij in conn.execute(
                    select(reserveringen.c.tijd, reserveringen.c.kinderstoelen).where(
                        reserveringen.c.datum == datum, reserveringen.c.kinderstoelen > 0,
                        reserveringen.c.status != NIET_GEKOMEN,
                    )
                )
            ]
            in_gebruik = piekbezetting(stoelen, minuten_van(tijd), zitduur_minuten or 1) if stoelen else 0
            if in_gebruik + kinderstoelen > max_kinderstoelen:
                raise KinderstoelVolFout()

        unieke_id = secrets.token_urlsafe(16)
        conn.execute(
            insert(reserveringen).values(
                id=unieke_id, naam=naam, email=email, telefoon=telefoon,
                datum=datum, tijd=tijd, aantal=aantal,
                kinderstoelen=kinderstoelen, opmerking=opmerking or None, allergieen=allergieen or None,
                bron=bron, ingevoerd_door=ingevoerd_door, taal=taal,
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

def zet_status(conn, reservering_id, status):
    """Zet de status van een reservering (zie STATUSSEN). Geeft GeenReserveringFout als die niet bestaat."""
    if status not in STATUSSEN:
        raise ValueError(f"Onbekende status: {status}")
    with conn.begin():
        resultaat = conn.execute(
            update(reserveringen).where(reserveringen.c.id == reservering_id).values(status=status)
        )
    if resultaat.rowcount == 0:
        raise GeenReserveringFout()

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

def wis_allergieen_voor(conn, datum):
    """
    Wist de allergieen van reserveringen met een datum voor `datum` ('YYYY-MM-DD'): na het bezoek zijn
    ze niet meer nodig. De rest van de reservering blijft tot de gewone bewaartermijn. Geeft het aantal terug.
    """
    voorwaarde = (reserveringen.c.datum < datum, reserveringen.c.allergieen.is_not(None))
    with conn.begin():
        aantal = conn.execute(select(func.count()).select_from(reserveringen).where(*voorwaarde)).scalar()
        if aantal:
            conn.execute(update(reserveringen).where(*voorwaarde).values(allergieen=None))
    return aantal

def schonen_oude_reserveringen():
    conn = get_db()
    grens = _retentiegrens()
    with conn.begin():
        _verwijder_ouder_dan(conn, grens)
    wis_allergieen_voor(conn, date.today().isoformat())

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

def maak_gebruiker(conn, gebruikersnaam, wachtwoord, rol='medewerker'):
    """
    Maakt een personeelsaccount aan. Geeft False terug (zonder iets te wijzigen) als de naam al bestaat;
    hoofdletters tellen daarbij niet mee, zodat 'Anna' en 'anna' niet naast elkaar kunnen bestaan.
    """
    if rol not in ROLLEN:
        raise ValueError(f"Onbekende rol: {rol}")
    with conn.begin():
        bestaat = conn.execute(
            select(personeel.c.id).where(func.lower(personeel.c.gebruikersnaam) == gebruikersnaam.lower())
        ).first()
        if bestaat:
            return False
        conn.execute(
            insert(personeel).values(
                gebruikersnaam=gebruikersnaam, wachtwoord_hash=generate_password_hash(wachtwoord), rol=rol
            )
        )
    return True

class LaatsteBeheerderFout(Exception):
    """Dit account is de laatste actieve beheerder; uitzetten laat niemand over om accounts te beheren."""
    bericht = "Er moet minstens één actieve beheerder overblijven."

def haal_alle_personeel(conn):
    with conn.begin():
        return conn.execute(
            select(personeel).order_by(func.lower(personeel.c.gebruikersnaam))
        ).mappings().all()

def haal_gebruiker_op_id(conn, gebruiker_id):
    with conn.begin():
        return conn.execute(select(personeel).where(personeel.c.id == gebruiker_id)).mappings().first()

def zet_actief(conn, gebruiker_id, actief):
    """
    Zet een account aan of uit. Geeft False terug als het account niet bestaat.
    Gooit LaatsteBeheerderFout als dit de enige actieve beheerder is en hij uit moet.
    """
    with conn.begin():
        rij = conn.execute(select(personeel).where(personeel.c.id == gebruiker_id)).mappings().first()
        if rij is None:
            return False
        if not actief and rij['rol'] == 'beheerder' and rij['actief']:
            anderen = conn.execute(
                select(func.count()).select_from(personeel).where(
                    personeel.c.rol == 'beheerder', personeel.c.actief == true(), personeel.c.id != gebruiker_id
                )
            ).scalar()
            if not anderen:
                raise LaatsteBeheerderFout()
        conn.execute(update(personeel).where(personeel.c.id == gebruiker_id).values(actief=bool(actief)))
    return True

def zet_wachtwoord(conn, gebruiker_id, wachtwoord):
    """Vervangt het wachtwoord van een account. Geeft False terug als het account niet bestaat."""
    with conn.begin():
        resultaat = conn.execute(
            update(personeel).where(personeel.c.id == gebruiker_id)
            .values(wachtwoord_hash=generate_password_hash(wachtwoord))
        )
    return resultaat.rowcount > 0

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
                    gebruikersnaam='admin', wachtwoord_hash=generate_password_hash(initial_pw), rol='beheerder'
                )
            )
    schonen_oude_reserveringen()

