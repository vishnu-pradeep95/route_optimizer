"""Add settings table for runtime configuration (key-value store).

Phase 21: Dashboard Settings & Cache Management.

Creates a simple key-value settings table for storing runtime configuration
such as the Google Maps API key. The key column is the primary key (VARCHAR 100),
value is free-form text, and updated_at tracks when each setting was last modified.

Revision ID: e4a1c7f83b21
Revises: deb08e55c8a2
Create Date: 2026-03-14 22:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4a1c7f83b21"
down_revision: Union[str, Sequence[str], None] = "deb08e55c8a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the settings table."""
    op.create_table(
        "settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Drop the settings table."""
    op.drop_table("settings")
