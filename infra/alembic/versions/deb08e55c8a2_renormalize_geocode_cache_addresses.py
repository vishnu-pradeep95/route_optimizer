"""Renormalize geocode_cache address_norm values.

Re-processes all address_norm values using the new normalize_address()
function and deduplicates entries that collapse to the same key.
Backs up original values for reversibility.

Revision ID: deb08e55c8a2
Revises: 4228dedc0975
Create Date: 2026-03-01 17:41:42.025754
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# Import the pure function directly -- no ORM dependency
from core.geocoding.normalize import normalize_address


# revision identifiers, used by Alembic.
revision: str = 'deb08e55c8a2'
down_revision: Union[str, Sequence[str], None] = '4228dedc0975'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Re-normalize address_norm values and deduplicate collapsed entries."""
    # Step 1: Add backup column for reversibility
    op.add_column('geocode_cache',
        sa.Column('address_norm_old', sa.Text(), nullable=True))

    # Step 2: Backup current values
    op.execute("UPDATE geocode_cache SET address_norm_old = address_norm")

    # Step 3: Drop the unique constraint BEFORE updating address_norm.
    # Re-normalization can collapse different address_raw values to the same
    # address_norm, which would violate the constraint during row-by-row updates.
    # We dedup after updating, then re-add the constraint.
    op.drop_constraint('geocode_cache_address_norm_source_key', 'geocode_cache', type_='unique')

    # Step 4: Re-normalize using Python function
    # Fetch all rows, compute new normalization, update
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, address_raw FROM geocode_cache")
    ).fetchall()

    for row_id, address_raw in rows:
        new_norm = normalize_address(address_raw)
        conn.execute(
            sa.text("UPDATE geocode_cache SET address_norm = :norm WHERE id = :id"),
            {"norm": new_norm, "id": row_id},
        )

    # Step 5: Deduplicate -- for entries that now share the same (address_norm, source),
    # keep highest confidence, sum hit_counts.
    # First: update the keeper's hit_count to the sum
    conn.execute(sa.text("""
        WITH totals AS (
            SELECT address_norm, source, SUM(hit_count) AS total_hits
            FROM geocode_cache
            GROUP BY address_norm, source
            HAVING COUNT(*) > 1
        )
        UPDATE geocode_cache gc
        SET hit_count = t.total_hits
        FROM totals t
        WHERE gc.address_norm = t.address_norm
          AND gc.source = t.source
          AND gc.id = (
              SELECT id FROM geocode_cache sub
              WHERE sub.address_norm = gc.address_norm
                AND sub.source = gc.source
              ORDER BY confidence DESC, hit_count DESC, last_used_at DESC
              LIMIT 1
          )
    """))

    # Then: delete non-keeper duplicates
    conn.execute(sa.text("""
        DELETE FROM geocode_cache
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY address_norm, source
                           ORDER BY confidence DESC, hit_count DESC, last_used_at DESC
                       ) AS rn
                FROM geocode_cache
            ) ranked
            WHERE rn > 1
        )
    """))

    # Step 6: Re-add the unique constraint now that duplicates are resolved
    op.create_unique_constraint(
        'geocode_cache_address_norm_source_key',
        'geocode_cache',
        ['address_norm', 'source']
    )


def downgrade() -> None:
    """Restore original address_norm values from backup column."""
    op.execute(
        "UPDATE geocode_cache SET address_norm = address_norm_old "
        "WHERE address_norm_old IS NOT NULL"
    )
    op.drop_column('geocode_cache', 'address_norm_old')
