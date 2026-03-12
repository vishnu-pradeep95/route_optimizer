"""Add geocode_method column to orders.

Adds `geocode_method` String(20) column to the `orders` table for tracking
which fallback level was used during geocode validation: 'direct',
'area_retry', 'centroid', or 'depot'.

Existing orders will have NULL for this column, which downstream code
(Phase 14) treats as "pre-validation data" with no badge/warning shown.

IMPORTANT: Does NOT add geocode_confidence -- that column already exists
on the orders table from a previous migration.

Revision ID: 54c27825e8df
Revises: 9c370459587f
Create Date: 2026-03-12 02:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "54c27825e8df"
down_revision: Union[str, Sequence[str], None] = "9c370459587f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders", sa.Column("geocode_method", sa.String(20), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("orders", "geocode_method")
