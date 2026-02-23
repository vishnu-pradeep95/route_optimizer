#!/usr/bin/env python3
"""Batch geocode addresses and populate the PostGIS cache.

Standalone script to geocode a list of addresses (from CSV or database)
and save results to the PostGIS geocode_cache table. This is the primary
tool for building the local address database during Phase 0.

Why a separate script instead of geocoding inline during upload?
  1. Upload already does geocoding, but only for newly uploaded orders.
     This script geocodes HISTORICAL addresses — recurring customers whose
     addresses were never geocoded or have low confidence scores.
  2. Allows bulk geocoding during off-peak hours to avoid API rate limits.
  3. Can be run as a cron job to periodically re-geocode low-confidence addresses.

What this script does:
  1. Reads addresses from a CSV file or from ungeocoded orders in the DB
  2. Checks PostGIS cache first (avoids re-geocoding known addresses)
  3. Geocodes unknown addresses via Google Maps API
  4. Saves results to PostGIS cache for future use
  5. Reports cache hit rate and geocoding success/failure stats

Usage:
  # Geocode addresses from a CSV file (column name: "address"):
  python scripts/geocode_batch.py --from-csv data/address_list.csv

  # Geocode ungeocoded orders already in the database:
  python scripts/geocode_batch.py --from-db

  # Geocode from CSV with a custom address column name:
  python scripts/geocode_batch.py --from-csv data/customers.csv --address-column raw_address

  # Dry run — check cache hits without calling Google API:
  python scripts/geocode_batch.py --from-csv data/addresses.csv --dry-run

Prerequisites:
  - PostgreSQL running: `docker compose up -d db`
  - Virtual env active: `source .venv/bin/activate`
  - GOOGLE_MAPS_API_KEY set in .env

Cost estimate:
  Google Maps Geocoding API = $5 per 1000 requests.
  With $200/month free credit, you get 40,000 free requests.
  At 50 unique addresses/day, that's ~800 months of free geocoding.
  But we cache aggressively — repeat customers cost $0 after first geocode.
"""

import argparse
import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("geocode_batch")

# Rate limit between Google API calls: 20 requests/second.
# Google's hard limit is 50 QPS, but we stay conservative to avoid 429 errors.
# See: https://developers.google.com/maps/documentation/geocoding/usage-and-billing
GOOGLE_API_RATE_LIMIT_SECONDS = 0.05


def read_addresses_from_csv(
    file_path: str,
    address_column: str = "address",
) -> list[str]:
    """Read unique addresses from a CSV file.

    Args:
        file_path: Path to CSV file.
        address_column: Column name containing the address text.

    Returns:
        Deduplicated list of non-empty address strings.
    """
    import pandas as pd

    df = pd.read_csv(file_path)

    if address_column not in df.columns:
        available = ", ".join(df.columns.tolist())
        raise ValueError(
            f"Column '{address_column}' not found in CSV. "
            f"Available columns: {available}"
        )

    # Deduplicate and filter empties — no point geocoding the same address twice
    addresses = (
        df[address_column]
        .dropna()
        .str.strip()
        .loc[lambda s: s.str.len() > 0]
        .unique()
        .tolist()
    )
    logger.info(
        "Read %d unique addresses from %s (column: %s)",
        len(addresses),
        file_path,
        address_column,
    )
    return addresses


async def read_addresses_from_db() -> list[str]:
    """Read ungeocoded order addresses from the database.

    Finds orders that have an address but no coordinates — these were
    imported with text addresses only and need geocoding.

    Returns:
        List of unique address strings from ungeocoded orders.
    """
    from sqlalchemy import select
    from core.database.connection import get_session
    from core.database.models import OrderDB

    addresses = []
    async for session in get_session():
        # Find orders with address text but no location (PostGIS geometry is NULL)
        # NOTE: The column is address_raw (not address) — matches OrderDB model.
        result = await session.execute(
            select(OrderDB.address_raw)
            .where(OrderDB.address_raw.isnot(None))
            .where(OrderDB.address_raw != "")
            .where(OrderDB.location.is_(None))
            .distinct()
        )
        addresses = [row[0] for row in result.all()]

    logger.info("Found %d ungeocoded addresses in database", len(addresses))
    return addresses


async def geocode_batch(
    addresses: list[str],
    dry_run: bool = False,
) -> dict:
    """Geocode a list of addresses using the cache-first strategy.

    Flow for each address:
    1. Check PostGIS cache
    2. Cache hit → skip (free)
    3. Cache miss → Google API → save to cache
    4. Track statistics

    Args:
        addresses: List of address strings to geocode.
        dry_run: If True, check cache but don't call Google API for misses.

    Returns:
        Dict with geocoding statistics.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")

    if not api_key and not dry_run:
        logger.error(
            "GOOGLE_MAPS_API_KEY not set. Set it in .env or use --dry-run."
        )
        return {"error": "Missing API key"}

    from core.database.connection import engine, get_session
    from core.database import repository as repo

    stats = {
        "total": len(addresses),
        "cache_hits": 0,
        "api_calls": 0,
        "api_success": 0,
        "api_failed": 0,
        "skipped_dry_run": 0,
    }

    # Initialize the geocoder only if not dry-running
    # Why lazy import? Avoids importing httpx and Google adapter
    # when we're only checking the cache.
    geocoder = None
    if not dry_run and api_key:
        from core.geocoding.google_adapter import GoogleGeocoder
        geocoder = GoogleGeocoder(api_key=api_key)

    async for session in get_session():
        for i, address in enumerate(addresses, 1):
            # Progress logging every 10 addresses
            if i % 10 == 0 or i == len(addresses):
                logger.info(
                    "Progress: %d/%d (%.0f%%)",
                    i, len(addresses), i / len(addresses) * 100,
                )

            # --- Check PostGIS cache ---
            cached = await repo.get_cached_geocode(session, address)
            if cached is not None:
                stats["cache_hits"] += 1
                logger.debug("  CACHE HIT: %s", address[:50])
                continue

            # --- Cache miss ---
            if dry_run:
                stats["skipped_dry_run"] += 1
                logger.debug("  CACHE MISS (dry run): %s", address[:50])
                continue

            if not geocoder:
                stats["api_failed"] += 1
                continue

            # --- Call Google Maps API ---
            # Rate-limit: 20 requests/second (well within Google's 50 QPS limit).
            # Without this, large CSVs fire requests as fast as Python can loop,
            # risking HTTP 429 (Too Many Requests) from Google.
            # Using asyncio.sleep (not time.sleep) so we don't block the event loop.
            await asyncio.sleep(GOOGLE_API_RATE_LIMIT_SECONDS)

            stats["api_calls"] += 1
            result = geocoder.geocode(address)

            if result.success and result.location:
                stats["api_success"] += 1
                await repo.save_geocode_cache(
                    session=session,
                    address_raw=address,
                    location=result.location,
                    source="google",
                    confidence=result.confidence,
                )
                logger.info(
                    "  ✓ %s → (%.6f, %.6f) [confidence: %.2f]",
                    address[:40],
                    result.location.latitude,
                    result.location.longitude,
                    result.confidence,
                )
            else:
                stats["api_failed"] += 1
                logger.warning(
                    "  ✗ Failed: %s",
                    address[:60],
                )

        # Commit all cache entries in one transaction
        await session.commit()

    return stats


def _print_stats(stats: dict) -> None:
    """Print geocoding statistics in a readable format."""
    total = stats.get("total", 0)
    hits = stats.get("cache_hits", 0)
    hit_rate = f"{hits / total * 100:.1f}%" if total > 0 else "N/A"

    print("\n" + "=" * 55)
    print("Geocoding Batch Summary")
    print("=" * 55)
    print(f"  Total addresses:     {total}")
    print(f"  Cache hits:          {hits} ({hit_rate})")
    print(f"  API calls made:      {stats.get('api_calls', 0)}")
    print(f"  API success:         {stats.get('api_success', 0)}")
    print(f"  API failed:          {stats.get('api_failed', 0)}")
    if stats.get("skipped_dry_run"):
        print(f"  Skipped (dry run):   {stats['skipped_dry_run']}")

    # Cost estimate — Google charges $5 per 1000 requests
    api_calls = stats.get("api_calls", 0)
    cost = api_calls * 0.005
    print(f"\n  Estimated API cost:  ${cost:.2f}")
    print(f"  Saved by cache:      ${hits * 0.005:.2f}")
    print("=" * 55)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Batch geocode addresses and populate the PostGIS cache. "
            "Checks cache first and only calls the Google API for unknown addresses."
        ),
        epilog=(
            "Examples:\n"
            "  python scripts/geocode_batch.py --from-csv data/sample_orders.csv\n"
            "  python scripts/geocode_batch.py --from-db\n"
            "  python scripts/geocode_batch.py --from-csv data/addresses.csv --dry-run\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--from-csv",
        metavar="FILE",
        help="Read addresses from a CSV file",
    )
    source_group.add_argument(
        "--from-db",
        action="store_true",
        help="Read ungeocoded order addresses from the database",
    )

    parser.add_argument(
        "--address-column",
        default="address",
        help="CSV column name containing addresses (default: 'address')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check cache hits without calling the geocoding API",
    )

    args = parser.parse_args()

    # Read addresses from the appropriate source
    if args.from_csv:
        if not os.path.isfile(args.from_csv):
            logger.error("File not found: %s", args.from_csv)
            sys.exit(1)
        addresses = read_addresses_from_csv(args.from_csv, args.address_column)
    else:
        # DB source requires async — handled in the async main wrapper below
        addresses = None

    # --- Run everything in a single event loop ---
    # Why a single asyncio.run()?
    # Each asyncio.run() creates and destroys an event loop. Running two
    # in sequence orphans pooled DB connections from the first loop.
    # Wrapping both the DB read and geocoding in one async function ensures
    # a single connection pool lifecycle.

    async def _async_main() -> dict | None:
        nonlocal addresses
        if addresses is None:
            # --from-db: read ungeocoded addresses from the database
            addresses = await read_addresses_from_db()
        if not addresses:
            logger.info("No addresses to geocode.")
            return None
        return await geocode_batch(addresses, dry_run=args.dry_run)

    stats = asyncio.run(_async_main())

    if stats is None:
        return
    if "error" not in stats:
        _print_stats(stats)
    else:
        logger.error("Geocoding failed: %s", stats["error"])
        sys.exit(1)


if __name__ == "__main__":
    main()
