"""Add route_validations table for Google Routes API comparison results.

Phase 22: Google Routes Validation.

Creates a route_validations table to persist OSRM vs Google Routes comparison
results. Each row stores both OSRM and Google distance/duration values, computed
delta percentages, Google's re-optimized waypoint order, and cost tracking.

Revision ID: f7b2d4e19a33
Revises: e4a1c7f83b21
Create Date: 2026-03-14 23:55:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = "f7b2d4e19a33"
down_revision: Union[str, Sequence[str], None] = "e4a1c7f83b21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the route_validations table."""
    op.create_table(
        "route_validations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("route_id", UUID(as_uuid=True), sa.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("osrm_distance_km", sa.Float(), nullable=False),
        sa.Column("osrm_duration_minutes", sa.Float(), nullable=False),
        sa.Column("google_distance_km", sa.Float(), nullable=False),
        sa.Column("google_duration_minutes", sa.Float(), nullable=False),
        sa.Column("distance_delta_pct", sa.Float(), nullable=False),
        sa.Column("duration_delta_pct", sa.Float(), nullable=False),
        sa.Column("google_waypoint_order", sa.Text(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), server_default="0.01"),
        sa.Column(
            "validated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.create_index("idx_route_validations_route_id", "route_validations", ["route_id"])


def downgrade() -> None:
    """Drop the route_validations table."""
    op.drop_index("idx_route_validations_route_id", table_name="route_validations")
    op.drop_table("route_validations")
