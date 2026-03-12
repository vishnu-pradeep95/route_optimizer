"""Add address_original column and backfill address_display from address_raw.

Adds `address_original` TEXT column to `orders` and `route_stops` tables
for storing completely unprocessed CDCMS ConsumerAddress text.

Also backfills `address_display` from `address_raw` for all existing orders
and route_stops, fixing the ADDR-01 bug where address_display was incorrectly
populated from Google's formatted_address instead of the CDCMS cleaned text.

Revision ID: 9c370459587f
Revises: deb08e55c8a2
Create Date: 2026-03-11 11:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c370459587f"
down_revision: Union[str, Sequence[str], None] = "deb08e55c8a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. Add address_original column to orders table ---
    # Use IF NOT EXISTS for idempotency: init.sql may already define this column
    # on fresh databases, while Alembic still needs to run for existing databases.
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS address_original TEXT")

    # --- 2. Add address_original column to route_stops table ---
    op.execute("ALTER TABLE route_stops ADD COLUMN IF NOT EXISTS address_original TEXT")

    # --- 3. Backfill address_display from address_raw for all existing orders ---
    # This fixes the ADDR-01 bug: existing orders have address_display set to
    # Google's formatted_address. We overwrite with address_raw (cleaned CDCMS text).
    op.execute(
        "UPDATE orders SET address_display = address_raw WHERE address_raw IS NOT NULL"
    )

    # --- 4. Backfill address_display in route_stops from orders.address_raw ---
    # Route stops have the same bug: their address_display came from Google text.
    # Join through orders to get the correct CDCMS text.
    op.execute(
        """
        UPDATE route_stops rs
        SET address_display = o.address_raw
        FROM orders o
        WHERE rs.order_id = o.id
          AND o.address_raw IS NOT NULL
        """
    )

    # NOTE: We do NOT backfill address_original. The original unprocessed CDCMS
    # text was never stored before this migration. Only new uploads will populate it.


def downgrade() -> None:
    # Drop the address_original columns.
    # NOTE: The address_display backfill is NOT reversible -- we cannot recover
    # the original Google formatted_address values. This is intentional: the
    # Google text was incorrect data that we're fixing.
    op.drop_column("route_stops", "address_original")
    op.drop_column("orders", "address_original")
