#!/usr/bin/env python3
"""Batch import orders from CSV into the database.

Standalone script to import orders without running the full API server.
Useful for:
  - Initial data seeding during Phase 0/1 testing
  - Bulk loading historical data for comparison analysis
  - Automated imports from a cron job or CI pipeline

What this script does:
  1. Reads a CSV/Excel file using CsvImporter (same parser as the API)
  2. Optionally geocodes addresses without coordinates (via Google Maps)
  3. Saves all orders to PostgreSQL via the async repository
  4. Reports import statistics (total, geocoded, failed)

Usage:
  # Basic import (orders with lat/lon already present):
  python scripts/import_orders.py data/sample_orders.csv

  # Import + geocode addresses missing coordinates:
  python scripts/import_orders.py data/sample_orders.csv --geocode

  # Dry run — parse and validate without writing to DB:
  python scripts/import_orders.py data/sample_orders.csv --dry-run

Prerequisites:
  - PostgreSQL running: `docker compose up -d db`
  - Virtual env active: `source .venv/bin/activate`
  - For geocoding: GOOGLE_MAPS_API_KEY set in .env

NOTE: This script uses async Python because the repository layer is
async (asyncpg). We run the async code via asyncio.run() in __main__.
"""

import argparse
import asyncio
import logging
import os
import sys
import time

# Add project root to path so we can import our modules.
# This is necessary when running as a script (not as a module).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from core.data_import.csv_importer import CsvImporter, ColumnMapping
from core.models.location import Location
from apps.kerala_delivery import config

# Load .env for DATABASE_URL and GOOGLE_MAPS_API_KEY
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("import_orders")

# Rate limit between Google API calls: 20 requests/second.
# Consistent with geocode_batch.py — Google's 50 QPS limit, stay conservative.
GOOGLE_API_RATE_LIMIT_SECONDS = 0.05


async def import_orders(
    file_path: str,
    geocode: bool = False,
    dry_run: bool = False,
) -> dict:
    """Import orders from CSV/Excel into the database.

    Args:
        file_path: Path to the CSV or Excel file.
        geocode: If True, geocode addresses missing coordinates.
        dry_run: If True, parse and validate but don't write to DB.

    Returns:
        Dict with import statistics.
    """
    # --- Step 1: Parse the CSV file ---
    logger.info("Reading orders from %s", file_path)

    importer = CsvImporter(
        column_mapping=ColumnMapping(),
        cylinder_weight_lookup=config.CYLINDER_WEIGHTS,
        # Reuse the India bounding box from config — DRY principle.
        # Rejects clearly wrong lat/lon values (e.g., coordinates in Europe).
        coordinate_bounds=config.INDIA_COORDINATE_BOUNDS,
    )

    orders = importer.import_orders(file_path)
    logger.info("Parsed %d orders from file", len(orders))

    if not orders:
        logger.warning("No orders found in file")
        return {"total": 0, "geocoded": 0, "already_geocoded": 0, "failed": 0}

    # --- Step 2: Geocode if requested ---
    already_geocoded = sum(1 for o in orders if o.location is not None)
    needs_geocoding = [o for o in orders if o.location is None and o.address_raw]
    geocoded_count = 0
    failed_count = 0

    if geocode and needs_geocoding:
        api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
        if not api_key:
            logger.error(
                "GOOGLE_MAPS_API_KEY not set — cannot geocode. "
                "Set it in .env or pass --no-geocode to skip."
            )
            return {
                "total": len(orders),
                "geocoded": 0,
                "already_geocoded": already_geocoded,
                "failed": len(needs_geocoding),
                "error": "Missing API key",
            }

        from core.geocoding.google_adapter import GoogleGeocoder

        geocoder = GoogleGeocoder(api_key=api_key)
        logger.info(
            "Geocoding %d addresses (of %d total, %d already have coordinates)",
            len(needs_geocoding),
            len(orders),
            already_geocoded,
        )

        for order in needs_geocoding:
            # Rate-limit to avoid Google 429 errors on large CSVs.
            # GoogleGeocoder.geocode() is synchronous (blocking HTTP) — acceptable
            # in this standalone script context since there are no concurrent tasks.
            time.sleep(GOOGLE_API_RATE_LIMIT_SECONDS)
            result = geocoder.geocode(order.address_raw)
            if result.success and result.location:
                order.location = result.location
                geocoded_count += 1
                logger.debug(
                    "  ✓ %s → (%.6f, %.6f) [confidence: %.2f]",
                    order.order_id,
                    result.location.latitude,
                    result.location.longitude,
                    result.confidence,
                )
            else:
                failed_count += 1
                logger.warning(
                    "  ✗ %s: geocoding failed for '%s'",
                    order.order_id,
                    order.address_raw[:60],
                )

    elif needs_geocoding:
        logger.info(
            "%d orders have no coordinates. Pass --geocode to geocode them.",
            len(needs_geocoding),
        )
        failed_count = len(needs_geocoding)

    stats = {
        "total": len(orders),
        "geocoded": geocoded_count,
        "already_geocoded": already_geocoded,
        "failed": failed_count,
        "has_location": already_geocoded + geocoded_count,
    }

    if dry_run:
        logger.info("DRY RUN — no database writes")
        _print_stats(stats)
        _print_sample_orders(orders[:5])
        return stats

    # --- Step 3: Save to database ---
    # Import DB components lazily to avoid import errors when DB isn't configured.
    # We import inside this function (not at module level) so --dry-run works
    # even without a running database.
    import uuid

    from core.database.connection import engine, get_session
    from core.database.models import OptimizationRunDB, OrderDB
    from geoalchemy2 import WKTElement

    def _make_point(loc: Location) -> WKTElement:
        """Convert a Location to a PostGIS WKT point."""
        return WKTElement(f"POINT({loc.longitude} {loc.latitude})", srid=4326)

    logger.info("Saving %d orders to database...", len(orders))

    # Why create an optimization run for an import?
    # OrderDB has a required FK to optimization_runs.run_id. Rather than
    # making it nullable (which would complicate queries), we create a
    # run with status='imported' to distinguish from optimizer-generated runs.
    # This also gives us an audit trail: "these orders came from this CSV on this date."
    async for session in get_session():
        run_id = uuid.uuid4()
        run_db = OptimizationRunDB(
            id=run_id,
            total_orders=len(orders),
            orders_assigned=0,
            orders_unassigned=len(orders),
            vehicles_used=0,
            source_filename=os.path.basename(file_path),
            status="imported",
            notes="Bulk CSV import via scripts/import_orders.py",
        )
        session.add(run_db)

        for order in orders:
            order_db = OrderDB(
                id=uuid.uuid4(),
                run_id=run_id,
                order_id=order.order_id,
                customer_ref=order.customer_ref,
                address_raw=order.address_raw,
                address_display=(
                    order.location.address_text if order.location else None
                ),
                weight_kg=order.weight_kg,
                quantity=order.quantity,
                priority=order.priority,
                service_time_min=order.service_time_minutes,
                notes=order.notes,
                delivery_window_start=order.delivery_window_start,
                delivery_window_end=order.delivery_window_end,
                status="pending",
                geocode_confidence=(
                    order.location.geocode_confidence if order.location else None
                ),
            )
            if order.location:
                order_db.location = _make_point(order.location)
            session.add(order_db)

        await session.commit()
        logger.info(
            "Saved %d orders under import run %s", len(orders), run_id
        )

    logger.info("Import complete!")
    _print_stats(stats)

    return stats


def _print_stats(stats: dict) -> None:
    """Print import statistics in a readable format."""
    print("\n" + "=" * 50)
    print("Import Summary")
    print("=" * 50)
    print(f"  Total orders:      {stats['total']}")
    print(f"  Already geocoded:  {stats['already_geocoded']}")
    print(f"  Newly geocoded:    {stats['geocoded']}")
    print(f"  Failed geocoding:  {stats['failed']}")
    print(f"  With coordinates:  {stats.get('has_location', 'N/A')}")
    print("=" * 50)


def _print_sample_orders(orders: list) -> None:
    """Print first N orders so the operator can visually verify parsing.

    Why? CSV column mapping bugs are subtle — this lets a human confirm
    that order IDs, addresses, and coordinates look correct before
    committing to a bulk import.
    """
    print("\nSample orders:")
    for o in orders:
        loc = (
            f"({o.location.latitude:.4f}, {o.location.longitude:.4f})"
            if o.location
            else "NO COORDS"
        )
        print(f"  {o.order_id}: {o.address_raw[:40]} → {loc} [{o.weight_kg} kg]")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import delivery orders from CSV/Excel into the database.",
        epilog=(
            "Examples:\n"
            "  python scripts/import_orders.py data/sample_orders.csv\n"
            "  python scripts/import_orders.py data/sample_orders.csv --geocode\n"
            "  python scripts/import_orders.py data/sample_orders.csv --dry-run\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "file",
        help="Path to CSV or Excel file with delivery orders",
    )
    parser.add_argument(
        "--geocode",
        action="store_true",
        help="Geocode addresses that don't have lat/lon coordinates",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate without writing to database",
    )

    args = parser.parse_args()

    if not os.path.isfile(args.file):
        logger.error("File not found: %s", args.file)
        sys.exit(1)

    asyncio.run(import_orders(args.file, geocode=args.geocode, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
