"""Async database engine and session factory.

Provides the SQLAlchemy async engine + session maker that FastAPI endpoints
use via dependency injection. Each request gets its own session, committed
on success, rolled back on error.

Why async?
- FastAPI is async-native. Blocking DB calls in an async endpoint would
  stall the event loop and degrade throughput for all concurrent requests.
- asyncpg is the fastest Python PostgreSQL driver and speaks the PG wire
  protocol natively (no libpq dependency).
See: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

Usage in FastAPI:
    from core.database.connection import get_session
    from sqlalchemy.ext.asyncio import AsyncSession

    @app.get("/items")
    async def list_items(session: AsyncSession = Depends(get_session)):
        result = await session.execute(select(Item))
        return result.scalars().all()
"""

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ---------------------------------------------------------------------------
# Default DATABASE_URL for local development (outside Docker).
# Inside Docker, the URL comes from the docker-compose.yml environment block.
# Format: postgresql+asyncpg://user:password@host:port/dbname
# The '+asyncpg' dialect tells SQLAlchemy to use the asyncpg driver.
# ---------------------------------------------------------------------------
_DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://routing:routing_dev_pass@localhost:5432/routing_opt"
)

DATABASE_URL: str = os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL)

# ---------------------------------------------------------------------------
# Engine — manages the connection pool to PostgreSQL.
# echo=False in production; set to True for SQL debugging.
#
# Why pool_size=5 and max_overflow=10?
# With 13 drivers + 1 dashboard, peak concurrent DB queries are ~15.
# 5 base connections + 10 overflow = 15 handles, which covers the worst case.
# asyncpg creates lightweight connections, so this is cheap.
# ---------------------------------------------------------------------------
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    # Recycle connections every 30 min to avoid stale connections
    # (e.g., after a PostgreSQL restart or network hiccup)
    pool_recycle=1800,
)

# ---------------------------------------------------------------------------
# Session factory — creates one AsyncSession per request.
# expire_on_commit=False: after commit, attributes stay loaded in memory.
# This avoids lazy-load errors in async context (a common gotcha with
# SQLAlchemy async — accessing a relationship after commit would trigger
# a sync lazy-load, which fails in async).
# ---------------------------------------------------------------------------
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async DB session per request.

    Usage:
        @app.get("/items")
        async def list_items(session: AsyncSession = Depends(get_session)):
            ...

    The session is automatically:
    - Created at request start
    - Yielded to the endpoint
    - Rolled back and closed on error
    - Closed after the response is sent

    IMPORTANT: This generator does NOT auto-commit. Every write endpoint
    must call `await session.commit()` explicitly after mutations. This is
    the "explicit commit" pattern — it forces you to think about transaction
    boundaries rather than accidentally committing partial state.

    Why a generator (yield) instead of return?
    The code after `yield` runs as cleanup, even if the endpoint raises.
    This is FastAPI's dependency lifecycle pattern.
    See: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
