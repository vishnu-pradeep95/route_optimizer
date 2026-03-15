"""Add timing_json column to optimization_runs table.

Stores per-stage pipeline timing breakdown (preprocess, geocoding,
optimization, persistence) as JSON text for operational visibility.

Revision ID: a1c9e3f47b20
Revises: 3fe478515f17
Create Date: 2026-03-15 03:50:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1c9e3f47b20"
down_revision: Union[str, Sequence[str], None] = "3fe478515f17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add timing_json column to optimization_runs."""
    op.add_column("optimization_runs", sa.Column("timing_json", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove timing_json column from optimization_runs."""
    op.drop_column("optimization_runs", "timing_json")
