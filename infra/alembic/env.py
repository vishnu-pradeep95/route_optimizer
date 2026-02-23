"""Alembic environment — async SQLAlchemy migration runner.

This file configures Alembic to:
1. Read DATABASE_URL from the environment (same variable FastAPI uses)
2. Use async engine (asyncpg) instead of sync
3. Import all ORM models so autogenerate can detect schema changes

Why async migrations?
Our engine uses asyncpg (async driver). Alembic's default env.py uses sync
connections which can't share the same URL format. We use Alembic's
run_async() helper to bridge the gap.
See: https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic

How autogenerate works:
Alembic compares `target_metadata` (our ORM models) against the live DB schema.
Any differences become migration operations. This is why we import Base — it
carries the metadata for all models that inherit from it.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# Alembic Config object — provides access to alembic.ini values
# ---------------------------------------------------------------------------
config = context.config

# Set up Python logging from the .ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Import ALL ORM models so Base.metadata includes every table.
# If you add a new model file, import it here too — otherwise autogenerate
# won't detect its tables.
#
# Why import models explicitly instead of just Base?
# Python only registers a model in Base.metadata when the class is *defined*
# (i.e., when its module is imported). If we only import Base, the model
# classes never get defined, and metadata is empty.
# ---------------------------------------------------------------------------
from core.database.models import Base  # noqa: E402

# This includes: VehicleDB, DriverDB, OptimizationRunDB, OrderDB,
#                RouteDB, RouteStopDB, TelemetryDB, GeocodeCacheDB

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Tables managed by our ORM — only these should appear in migrations.
# PostGIS creates many internal tables (tiger geocoder, topology, spatial_ref_sys)
# that we must exclude from autogenerate or Alembic will try to drop them.
# ---------------------------------------------------------------------------
ORM_TABLE_NAMES = set(target_metadata.tables.keys())


def include_object(
    obj: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    """Filter callback for autogenerate — only include our ORM tables.

    Why this filter?
    PostGIS 16-3.5 installs tiger geocoder and topology extensions that create
    ~30+ tables in the public schema (e.g., faces, edges, addr, state, county).
    Without this filter, Alembic's autogenerate would produce DROP TABLE for all
    of them, which would destroy PostGIS functionality.

    How it works:
    - For tables: only include if the table name is in our ORM models
    - For indexes/constraints on our tables: always include
    - For anything else (reflected-only): exclude

    See: https://alembic.sqlalchemy.org/en/latest/autogenerate.html#omitting-table-names-from-the-autogenerate-process
    """
    if type_ == "table":
        return name in ORM_TABLE_NAMES
    # For indexes, foreign keys, etc. — include only if they belong
    # to one of our ORM tables (the parent table is in compare_to
    # or the reflected object has a .table attribute)
    return not reflected

# ---------------------------------------------------------------------------
# Resolve the database URL — single source of truth.
#
# Priority: DATABASE_URL env var → core.database.connection default.
# This ensures Alembic always connects to the same DB as the FastAPI app.
# The alembic.ini sqlalchemy.url is a placeholder — never used directly.
# ---------------------------------------------------------------------------
from core.database.connection import DATABASE_URL  # noqa: E402

config.set_main_option("sqlalchemy.url", DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL without a DB connection.

    Useful for reviewing migration SQL before applying it, or for
    environments where you can't connect to the DB directly (e.g.,
    generating SQL scripts to hand to a DBA).

    Usage: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Include the schema object name in autogenerate comparisons
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure Alembic context with a live DB connection and run migrations.

    Extracted into a helper so both online sync and async paths can use it.
    compare_type=True tells autogenerate to detect column type changes
    (e.g., String(20) → String(50)), not just additions/removals.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
        # GeoAlchemy2 columns need special comparison — without this,
        # autogenerate would flag every Geometry column as "changed" on
        # every run because the default type comparator doesn't understand
        # PostGIS types.
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using an async engine.

    Why async_engine_from_config instead of create_async_engine?
    async_engine_from_config reads the [alembic] section from alembic.ini,
    which includes pool settings and the sqlalchemy.url. This keeps all
    config in one place rather than duplicating connection params.

    Why NullPool?
    Migrations are a short-lived CLI operation. A connection pool would
    create and immediately discard connections — wasteful. NullPool creates
    a fresh connection per use and closes it immediately after.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # run_sync() bridges async connection → sync callback
        # Alembic's migration operations are synchronous internally,
        # so we need this adapter to run them on an async connection.
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with an async engine.

    This replaces Alembic's default sync online runner.
    asyncio.run() creates an event loop and runs the async migration
    function to completion.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
