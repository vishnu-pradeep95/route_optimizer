"""Database module — SQLAlchemy async engine, session, and ORM models.

Provides the persistence layer for the routing optimization platform.
Core module: business-agnostic. Kerala-specific seed data lives in
infra/postgres/init.sql, not here.

Architecture overview (3 layers):

    ┌────────────────────┐
    │  FastAPI endpoints  │  ← HTTP layer (main.py): validation, serialization
    └──────────┬─────────┘
               │
    ┌──────────┴─────────┐
    │ Repository layer   │  ← THIS MODULE: Pydantic ↔ ORM conversion + queries
    └──────────┬─────────┘
               │
    ┌──────────┴─────────┐
    │ PostgreSQL+PostGIS │  ← Database: tables, indexes, spatial functions
    └────────────────────┘

Files in this module:
    connection.py  — Async engine + session factory (pool management)
    models.py      — ORM classes mapping Python objects to SQL tables
    repository.py  — CRUD operations converting between layers

Why SQLAlchemy 2.0 + asyncpg?
- Async-native: FastAPI is async, so blocking DB calls would stall the
  event loop and hurt throughput for all concurrent requests
- Type-safe: mapped_column() with Python types gives IDE autocomplete
  and catches type errors at development time, not runtime
- PostGIS support via GeoAlchemy2 for spatial queries ("find all orders
  within 2 km of the depot")
- Alembic integration for schema migrations (add columns without losing data)
- asyncpg is the fastest Python PostgreSQL driver — speaks the PG wire
  protocol natively without a C library (libpq) dependency
See: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

Why NOT SQLite for development?
- PostGIS geometry types don't exist in SQLite
- We use PostgreSQL-specific features: UUID columns, GiST spatial indexes,
  timestamptz, and ST_MakePoint/ST_SetSRID functions
- Docker makes running PostgreSQL locally trivial: `docker compose up db`
"""
