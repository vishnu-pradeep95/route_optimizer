"""Widen vehicle_id columns from VARCHAR(20) to VARCHAR(100) for driver names.

Phase 19: Per-Driver TSP Optimization.

The vehicle_id column on routes and telemetry tables now stores driver names
(e.g., "Suresh Kumar Nair P") instead of vehicle registration IDs (e.g., "VEH-01").
Driver names can exceed the previous 20-character limit, so we widen to 100.

The vehicles.vehicle_id column is NOT changed -- it still stores vehicle IDs
and the vehicles table is no longer used for optimization.

Revision ID: b3e8f4a17c02
Revises: a7f3b1d92e01
Create Date: 2026-03-14 04:50:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3e8f4a17c02"
down_revision: Union[str, Sequence[str], None] = "a7f3b1d92e01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Widen vehicle_id from VARCHAR(20) to VARCHAR(100) on routes and telemetry."""
    op.alter_column(
        "routes",
        "vehicle_id",
        type_=sa.String(100),
        existing_type=sa.String(20),
    )
    op.alter_column(
        "telemetry",
        "vehicle_id",
        type_=sa.String(100),
        existing_type=sa.String(20),
    )


def downgrade() -> None:
    """Revert vehicle_id back to VARCHAR(20) on routes and telemetry."""
    op.alter_column(
        "routes",
        "vehicle_id",
        type_=sa.String(20),
        existing_type=sa.String(100),
    )
    op.alter_column(
        "telemetry",
        "vehicle_id",
        type_=sa.String(20),
        existing_type=sa.String(100),
    )
