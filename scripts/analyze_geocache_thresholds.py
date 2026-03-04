"""Analyze geocode_cache confidence distribution for threshold validation.

Reference script for the duplicate detection threshold analysis (Phase 12, DATA-01).
Contains the SQL queries used to analyze the production geocode_cache table and
validate the DUPLICATE_THRESHOLDS values in apps/kerala_delivery/config.py.

Usage:
    # Run queries directly via Docker:
    docker compose exec -T db psql -U routing -d routing_opt -f scripts/analyze_geocache_thresholds.sql

    # Or run this Python script (requires psycopg2 and a running PostgreSQL):
    python scripts/analyze_geocache_thresholds.py

Schema context:
    The geocode_cache table stores `source` (varchar) and `confidence` (float).
    It does NOT store Google's `location_type` directly. The mapping is:

      Google location_type     -> confidence -> tier name         -> threshold
      ──────────────────────────────────────────────────────────────────────────
      ROOFTOP                  -> 0.95       -> "rooftop"         -> 10m
      RANGE_INTERPOLATED       -> 0.80       -> "interpolated"    -> 20m
      GEOMETRIC_CENTER         -> 0.60       -> "geometric_center"-> 50m
      APPROXIMATE              -> 0.40       -> "approximate"     -> 100m

    Translation happens in:
      - core/geocoding/google_adapter.py (confidence_map: location_type -> float)
      - core/geocoding/duplicate_detector.py (_confidence_tier: float -> tier name)

See also:
    - .planning/phases/12-data-wiring-validation/12-THRESHOLD-REPORT.md
    - apps/kerala_delivery/config.py (DUPLICATE_THRESHOLDS)
"""

import os
import sys

# ---------------------------------------------------------------------------
# SQL Queries — these are the exact queries used for the threshold analysis.
# They can be run via psql or through the Python connection below.
# ---------------------------------------------------------------------------

QUERY_SOURCE_DISTRIBUTION = """
-- Query 1: Source distribution with confidence statistics
SELECT source, COUNT(*) as count,
       ROUND(AVG(confidence)::numeric, 3) as avg_confidence,
       ROUND(MIN(confidence)::numeric, 3) as min_confidence,
       ROUND(MAX(confidence)::numeric, 3) as max_confidence
FROM geocode_cache
GROUP BY source
ORDER BY count DESC;
"""

QUERY_TIER_DISTRIBUTION = """
-- Query 2: Confidence tier distribution (matching _confidence_tier logic)
-- Tiers correspond to Google's location_type via the confidence_map in
-- google_adapter.py. The CASE boundaries match duplicate_detector.py.
SELECT
  CASE
    WHEN confidence >= 0.90 THEN 'rooftop (>=0.90)'
    WHEN confidence >= 0.70 THEN 'interpolated (>=0.70)'
    WHEN confidence >= 0.50 THEN 'geometric_center (>=0.50)'
    ELSE 'approximate (<0.50)'
  END as tier,
  COUNT(*) as count,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as pct
FROM geocode_cache
GROUP BY tier
ORDER BY MIN(confidence) DESC;
"""

QUERY_EXACT_CONFIDENCE = """
-- Query 3: Exact confidence value distribution
-- Shows the actual discrete confidence values stored, grouped by source.
-- Because google_adapter.py maps location_type to fixed floats (0.95, 0.80,
-- 0.60, 0.40), we expect to see only these values for source='google'.
SELECT confidence, source, COUNT(*) as count
FROM geocode_cache
GROUP BY confidence, source
ORDER BY confidence DESC, count DESC;
"""

QUERY_CACHE_METADATA = """
-- Query 4: Cache utilization metadata
SELECT
  COUNT(*) as total_entries,
  ROUND(AVG(hit_count)::numeric, 1) as avg_hit_count,
  MAX(hit_count) as max_hit_count,
  MIN(created_at) as earliest_entry,
  MAX(created_at) as latest_entry
FROM geocode_cache;
"""


def main() -> None:
    """Run all analysis queries and print results."""
    try:
        import psycopg2  # noqa: F811
    except ImportError:
        print("psycopg2 not installed. Run queries via docker exec instead:")
        print("  docker compose exec -T db psql -U routing -d routing_opt")
        print()
        print("Queries to run:")
        for name, query in [
            ("Source Distribution", QUERY_SOURCE_DISTRIBUTION),
            ("Tier Distribution", QUERY_TIER_DISTRIBUTION),
            ("Exact Confidence Values", QUERY_EXACT_CONFIDENCE),
            ("Cache Metadata", QUERY_CACHE_METADATA),
        ]:
            print(f"\n--- {name} ---")
            print(query)
        sys.exit(0)

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://routing:routing_dev_pass@localhost:5432/routing_opt",
    )

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    queries = [
        ("Source Distribution", QUERY_SOURCE_DISTRIBUTION),
        ("Tier Distribution", QUERY_TIER_DISTRIBUTION),
        ("Exact Confidence Values", QUERY_EXACT_CONFIDENCE),
        ("Cache Metadata", QUERY_CACHE_METADATA),
    ]

    for name, query in queries:
        print(f"\n{'='*60}")
        print(f"  {name}")
        print(f"{'='*60}")
        cur.execute(query)
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

        # Print header
        widths = [max(len(str(c)), max((len(str(r[i])) for r in rows), default=0)) for i, c in enumerate(cols)]
        header = " | ".join(c.ljust(w) for c, w in zip(cols, widths))
        print(header)
        print("-+-".join("-" * w for w in widths))
        for row in rows:
            print(" | ".join(str(v).ljust(w) for v, w in zip(row, widths)))

    cur.close()
    conn.close()
    print("\nAnalysis complete. See 12-THRESHOLD-REPORT.md for interpretation.")


if __name__ == "__main__":
    main()
