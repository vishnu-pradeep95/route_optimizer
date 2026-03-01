#!/usr/bin/env python3
"""One-time migration: import google_cache.json entries into PostgreSQL.

Run this BEFORE removing the file cache code from GoogleGeocoder.
After successful migration, the JSON file can be archived or deleted.

Usage:
    python scripts/migrate_file_cache.py [--dry-run]
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.geocoding.normalize import normalize_address
from core.models.location import Location

logger = logging.getLogger(__name__)

CACHE_FILE = Path("data/geocode_cache/google_cache.json")


async def migrate_file_cache(dry_run: bool = False) -> dict:
    """Read google_cache.json and insert entries into geocode_cache DB table.

    Uses the original_address field (NOT the hash key) as address_raw.
    Normalizes using normalize_address() for consistency with new code paths.

    Returns:
        dict with counts: total, migrated, skipped, errors
    """
    from core.database.connection import get_session
    from core.database import repository as repo

    if not CACHE_FILE.exists():
        logger.warning("Cache file not found: %s", CACHE_FILE)
        return {"total": 0, "migrated": 0, "skipped": 0, "errors": 0}

    data = json.loads(CACHE_FILE.read_text())
    stats = {"total": len(data), "migrated": 0, "skipped": 0, "errors": 0}

    logger.info("Found %d entries in %s", len(data), CACHE_FILE)

    async for session in get_session():
        for hash_key, entry in data.items():
            # Use original_address, NOT the hash key
            address_raw = entry.get("original_address", "")
            if not address_raw:
                logger.warning("Entry %s has no original_address, skipping", hash_key)
                stats["skipped"] += 1
                continue

            lat = entry.get("lat")
            lon = entry.get("lon")
            confidence = entry.get("confidence", 0.5)

            if lat is None or lon is None:
                logger.warning("Entry %s missing coordinates, skipping", hash_key)
                stats["skipped"] += 1
                continue

            if dry_run:
                norm = normalize_address(address_raw)
                logger.info(
                    "  [DRY RUN] Would migrate: '%s' -> '%s' (%.6f, %.6f, conf=%.2f)",
                    address_raw[:60], norm, lat, lon, confidence,
                )
                stats["migrated"] += 1
                continue

            try:
                location = Location(latitude=lat, longitude=lon, address_text=address_raw)
                await repo.save_geocode_cache(
                    session=session,
                    address_raw=address_raw,
                    location=location,
                    source="google",
                    confidence=confidence,
                )
                stats["migrated"] += 1
                logger.debug("  Migrated: %s", address_raw[:60])
            except Exception as e:
                logger.error("  Failed to migrate '%s': %s", address_raw[:60], e)
                stats["errors"] += 1

        if not dry_run:
            await session.commit()

    return stats


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        logger.info("=== DRY RUN MODE ===")

    stats = asyncio.run(migrate_file_cache(dry_run=dry_run))
    logger.info(
        "Migration complete: %d total, %d migrated, %d skipped, %d errors",
        stats["total"], stats["migrated"], stats["skipped"], stats["errors"],
    )


if __name__ == "__main__":
    main()
