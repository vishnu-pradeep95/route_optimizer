"""Reshape drivers table to standalone entity, add driver_id FK to routes.

Phase 16: Driver Database Foundation.

Changes to drivers table:
- ADD: name_normalized VARCHAR(100) -- uppercase, trimmed for fuzzy matching
- ADD: updated_at TIMESTAMPTZ DEFAULT NOW() -- track edits
- DROP: phone column -- CDCMS doesn't provide it
- DROP: vehicle_id FK column -- drivers are standalone entities
- ADD: idx_drivers_name_normalized index
- ADD: idx_drivers_name_normalized_unique unique index

Changes to routes table:
- ADD: driver_id UUID REFERENCES drivers(id) -- nullable FK

All operations use IF NOT EXISTS / IF EXISTS for idempotency: init.sql
may already define these columns on fresh databases, while Alembic needs
to run for existing databases.

Revision ID: a7f3b1d92e01
Revises: 54c27825e8df
Create Date: 2026-03-13 03:25:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7f3b1d92e01"
down_revision: Union[str, Sequence[str], None] = "54c27825e8df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add name_normalized column to drivers
    op.execute(
        "ALTER TABLE drivers ADD COLUMN IF NOT EXISTS "
        "name_normalized VARCHAR(100)"
    )

    # 2. Add updated_at column to drivers
    op.execute(
        "ALTER TABLE drivers ADD COLUMN IF NOT EXISTS "
        "updated_at TIMESTAMPTZ DEFAULT NOW()"
    )

    # 3. Drop phone column from drivers
    op.execute(
        "ALTER TABLE drivers DROP COLUMN IF EXISTS phone"
    )

    # 4. Drop vehicle_id FK column from drivers
    op.execute(
        "ALTER TABLE drivers DROP COLUMN IF EXISTS vehicle_id"
    )

    # 5. Add driver_id FK to routes
    op.execute(
        "ALTER TABLE routes ADD COLUMN IF NOT EXISTS "
        "driver_id UUID REFERENCES drivers(id)"
    )

    # 6. Backfill name_normalized for any existing drivers
    op.execute(
        "UPDATE drivers SET name_normalized = UPPER(TRIM(name)) "
        "WHERE name_normalized IS NULL"
    )

    # 7. Set name_normalized NOT NULL after backfill
    op.execute(
        "ALTER TABLE drivers ALTER COLUMN name_normalized SET NOT NULL"
    )

    # 8. Create index for fast name lookups
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_drivers_name_normalized "
        "ON drivers(name_normalized)"
    )

    # 9. Create unique index to prevent exact duplicate names at DB level
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_drivers_name_normalized_unique "
        "ON drivers(name_normalized)"
    )


def downgrade() -> None:
    # Remove unique index
    op.execute("DROP INDEX IF EXISTS idx_drivers_name_normalized_unique")

    # Remove regular index
    op.execute("DROP INDEX IF EXISTS idx_drivers_name_normalized")

    # Remove driver_id from routes
    op.execute("ALTER TABLE routes DROP COLUMN IF EXISTS driver_id")

    # Re-add vehicle_id to drivers
    op.execute(
        "ALTER TABLE drivers ADD COLUMN IF NOT EXISTS "
        "vehicle_id UUID REFERENCES vehicles(id)"
    )

    # Re-add phone to drivers
    op.execute(
        "ALTER TABLE drivers ADD COLUMN IF NOT EXISTS "
        "phone VARCHAR(20)"
    )

    # Remove updated_at from drivers
    op.execute("ALTER TABLE drivers DROP COLUMN IF EXISTS updated_at")

    # Remove name_normalized from drivers
    op.execute("ALTER TABLE drivers DROP COLUMN IF EXISTS name_normalized")
