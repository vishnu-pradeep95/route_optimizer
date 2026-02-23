"""Drop duplicate _orm-suffix telemetry indexes.

Revision ID: 4228dedc0975
Revises: ccbb9fc2db2c
Create Date: 2026-02-22 12:00:00.000000

What this migration does and why (Code Review #6, finding W1):
--------------------------------------------------------------
The previous migration (ccbb9fc2db2c) created telemetry indexes with an "_orm"
suffix to avoid name collisions with the identical indexes already created by
init.sql.  This meant the database had TWO copies of each index:

    init.sql:       idx_telemetry_location        (gist on location)
    ccbb9fc2db2c:   idx_telemetry_location_orm    (gist on location)   <-- duplicate

Duplicate indexes waste disk space, slow down writes (every INSERT updates
both), and confuse the query planner.

Resolution:
  1. The ORM model (TelemetryDB.__table_args__) was updated to use the SAME
     index names as init.sql (dropping the _orm suffix).  This tells Alembic
     "these indexes already exist — don't recreate them."
  2. This migration drops the now-orphaned _orm duplicates from the live DB.

After this migration:
  - Only the init.sql-created indexes remain (one copy each).
  - ORM model names match init.sql names, so future autogenerate is clean.

See also:
  - core/database/models.py  TelemetryDB.__table_args__
  - infra/postgres/init.sql   lines 187-195
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "4228dedc0975"
down_revision: Union[str, Sequence[str], None] = "ccbb9fc2db2c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the three duplicate _orm-suffix telemetry indexes."""
    # These are exact duplicates of init.sql indexes — safe to drop.
    op.drop_index("idx_telemetry_location_orm", table_name="telemetry", postgresql_using="gist")
    op.drop_index("idx_telemetry_recorded_at_orm", table_name="telemetry")
    op.drop_index("idx_telemetry_vehicle_time_orm", table_name="telemetry")


def downgrade() -> None:
    """Recreate the _orm-suffix indexes (they're duplicates, but reversibility matters)."""
    import sqlalchemy as sa

    op.create_index(
        "idx_telemetry_vehicle_time_orm",
        "telemetry",
        ["vehicle_id", sa.literal_column("recorded_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_telemetry_recorded_at_orm",
        "telemetry",
        [sa.literal_column("recorded_at DESC")],
        unique=False,
    )
    op.create_index(
        "idx_telemetry_location_orm",
        "telemetry",
        ["location"],
        unique=False,
        postgresql_using="gist",
    )
