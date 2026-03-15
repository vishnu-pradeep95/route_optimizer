"""Merge settings and validation branches.

Revision ID: 3fe478515f17
Revises: e4a1c7f83b21, f7b2d4e19a33
Create Date: 2026-03-15 00:30:00.000000
"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "3fe478515f17"
down_revision: tuple[str, ...] = ("e4a1c7f83b21", "f7b2d4e19a33")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge point -- no schema changes."""
    pass


def downgrade() -> None:
    """Merge point -- no schema changes."""
    pass
