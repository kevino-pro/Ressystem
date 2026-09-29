import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

load_dotenv()

from app.database import metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


def resolve_database_url() -> str:
    database_url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url or not database_url.strip():
        raise RuntimeError(
            "Database-URL ontbreekt. Stel MIGRATION_DATABASE_URL of DATABASE_URL in de "
            "shell-/Render-omgeving of in het lokale .env-bestand in."
        )

    try:
        parsed_url = make_url(database_url)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("MIGRATION_DATABASE_URL/DATABASE_URL is geen geldige SQLAlchemy-URL.") from exc

    host = (parsed_url.host or "").lower().rstrip(".")
    if "-pooler" in host:
        raise RuntimeError(
            "Migraties weigeren een pooler-host. Gebruik de directe Neon-connection string; "
            "de hostnaam bevat dan geen '-pooler'."
        )

    is_neon_host = host == "neon.tech" or host.endswith(".neon.tech")
    if is_neon_host and os.environ.get("ALLOW_PROD_MIGRATE") != "1":
        raise RuntimeError(
            "Migraties naar Neon zijn lokaal geblokkeerd. Gebruik alleen voor een expliciet "
            "goedgekeurde opdracht ALLOW_PROD_MIGRATE=1 met een directe Neon-URL."
        )

    return database_url


database_url = resolve_database_url()
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
