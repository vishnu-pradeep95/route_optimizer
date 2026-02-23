"""PostGIS-backed geocoding cache — the most valuable geocoding asset over time.

This module provides a Geocoder implementation that looks up addresses
in the PostgreSQL/PostGIS geocode_cache table before falling back to
an upstream provider (e.g., Google Maps).

Why a DB-backed cache instead of just the file-based JSON cache in GoogleGeocoder?

1. **Shared access**: Multiple processes/instances can read the same cache.
   The JSON file cache in GoogleGeocoder works for solo development, but
   in production with Docker Compose, we need a shared data store.

2. **Driver-verified coordinates**: When a driver delivers to a new address
   and their GPS confirms the location, we save that as 'driver_verified'
   with confidence=0.95. Over 6 months, this builds a Kerala address
   database more accurate than any commercial API.

3. **Hit tracking**: Every cache hit increments a counter and updates
   last_used_at. This tells us which addresses are most valuable and
   lets us prioritize cache warming.

4. **Spatial queries**: PostGIS lets us find "addresses near this point"
   for fuzzy matching — if a new address is within 50m of a cached one,
   we can suggest the cached coordinates with slightly lower confidence.

Architecture:
    CachedGeocoder wraps any upstream Geocoder (typically GoogleGeocoder).
    On geocode():
      1. Check PostGIS cache (by normalized address text)
      2. Cache hit → return immediately (cost: 0 API calls)
      3. Cache miss → call upstream provider
      4. If upstream succeeds → save to PostGIS cache
      5. Return result

    This is the **Decorator pattern** (GoF) — we add caching behavior
    without modifying the upstream provider.
    See: https://refactoring.guru/design-patterns/decorator

Data flow:
    Address text
      → normalize (lowercase, strip)
      → SHA-256 hash for cache key (in repo layer)
      → PostGIS lookup (idx_geocode_cache_address index)
      → HIT: return Location + bump hit_count
      → MISS: upstream.geocode() → save result → return

See also:
    - core/geocoding/interfaces.py — Geocoder protocol
    - core/geocoding/google_adapter.py — upstream provider
    - core/database/repository.py — get_cached_geocode(), save_geocode_cache()
    - core/database/models.py — GeocodeCacheDB ORM model
    - infra/postgres/init.sql — geocode_cache table DDL
"""

import logging
from typing import TYPE_CHECKING

from core.geocoding.interfaces import Geocoder, GeocodingResult
from core.models.location import Location

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class CachedGeocoder:
    """Async geocoder that checks a PostGIS cache before calling an upstream provider.

    Implements the AsyncGeocoder protocol (structural subtyping via Protocol).
    Note: this does NOT implement the sync Geocoder protocol — all methods
    are async because they use SQLAlchemy's async session for PostGIS lookups.
    Callers must ``await`` all method calls.

    Usage:
        from core.geocoding.google_adapter import GoogleGeocoder
        from core.geocoding.cache import CachedGeocoder

        google = GoogleGeocoder(api_key="...")
        cached = CachedGeocoder(upstream=google, session=db_session)

        # First call → cache miss → Google API → save to PostGIS
        result = await cached.geocode("MG Road, Kochi")

        # Second call → cache hit → no API call → $0 cost
        result = await cached.geocode("MG Road, Kochi")

    Why async?
        The PostGIS lookup uses SQLAlchemy's async session, which requires
        await. The upstream provider (GoogleGeocoder) is synchronous today,
        but wrapping it in an async interface means we can later swap in an
        async provider without changing callers.
    """

    def __init__(
        self,
        upstream: Geocoder,
        session: "AsyncSession",
        default_source: str = "google",
    ):
        """Initialize the cached geocoder.

        Args:
            upstream: The geocoder to call on cache misses (e.g., GoogleGeocoder).
                Any object implementing the Geocoder protocol works.
            session: SQLAlchemy async session for PostGIS cache operations.
                The caller is responsible for committing the session after
                geocoding (to persist new cache entries).
            default_source: Source label for new cache entries (e.g., 'google',
                'latlong_ai'). This tracks which provider geocoded each address,
                useful for debugging and confidence calibration.
        """
        self._upstream = upstream
        self._session = session
        self._source = default_source

        # Track cache stats for this instance's lifetime.
        # Useful for logging after batch operations:
        # "Geocoded 50 addresses: 38 cache hits, 12 API calls"
        self.stats = {"hits": 0, "misses": 0, "errors": 0}

    async def geocode(self, address: str) -> GeocodingResult:
        """Geocode an address, checking PostGIS cache first.

        Flow:
        1. Normalize address → lookup in geocode_cache table
        2. Cache HIT: return Location (hit_count incremented by repo)
        3. Cache MISS: call upstream.geocode()
        4. If upstream succeeds: save to PostGIS cache
        5. Return result

        The cache lookup is O(1) via the idx_geocode_cache_address index
        (btree on address_norm). The upstream call costs 1 API request
        (~$0.005 for Google Maps Geocoding).

        Args:
            address: Free-text address string (e.g., "Near SBI, MG Road, Kochi").

        Returns:
            GeocodingResult with location (if found) and confidence score.
        """
        # Import here to avoid circular imports at module level.
        # repository.py imports from models.py which imports from this package.
        from core.database import repository as repo

        # --- Step 1: Check PostGIS cache ---
        try:
            cached_location = await repo.get_cached_geocode(
                self._session, address
            )
            if cached_location is not None:
                self.stats["hits"] += 1
                logger.debug("Cache HIT for address: %s", address[:50])
                return GeocodingResult(
                    location=cached_location,
                    confidence=cached_location.geocode_confidence or 0.8,
                    formatted_address=cached_location.address_text or address,
                )
        except Exception as e:
            # Cache lookup failed (DB down, connection error, etc.)
            # Fall through to upstream — the cache is an optimization,
            # not a requirement. Better to pay for an API call than
            # fail the geocoding entirely.
            logger.warning(
                "Cache lookup failed for '%s': %s. Falling through to upstream.",
                address[:50],
                e,
            )

        # --- Step 2: Cache MISS → call upstream provider ---
        self.stats["misses"] += 1
        logger.debug("Cache MISS for address: %s", address[:50])

        try:
            result = self._upstream.geocode(address)
        except Exception as e:
            self.stats["errors"] += 1
            logger.error("Upstream geocoding failed for '%s': %s", address[:50], e)
            return GeocodingResult(
                location=None,
                confidence=0.0,
                raw_response={"error": str(e)},
            )

        # --- Step 3: Save successful result to cache ---
        if result.success and result.location:
            try:
                await repo.save_geocode_cache(
                    session=self._session,
                    address_raw=address,
                    location=result.location,
                    source=self._source,
                    confidence=result.confidence,
                )
                logger.debug(
                    "Cached geocode result for '%s' (confidence: %.2f)",
                    address[:50],
                    result.confidence,
                )
            except Exception as e:
                # Cache save failed — log but don't fail the geocoding.
                # The result is still valid; we'll just miss the cache
                # next time and re-geocode.
                logger.warning(
                    "Failed to cache geocode for '%s': %s", address[:50], e
                )

        return result

    async def geocode_batch(self, addresses: list[str]) -> list[GeocodingResult]:
        """Geocode multiple addresses with cache-first strategy.

        Why not a single SQL batch lookup?
        The repo's get_cached_geocode() handles one address at a time because
        each hit needs to increment hit_count individually. A bulk SELECT
        followed by a bulk UPDATE would be more efficient at >100 addresses,
        but at our scale (40-50 deliveries/day), sequential is fine and
        simpler to maintain.

        Future optimization: if batch sizes grow significantly, add a
        repo.get_cached_geocode_batch() that does a single SELECT + bulk
        UPDATE of hit counts.

        Args:
            addresses: List of address strings to geocode.

        Returns:
            List of GeocodingResult objects, one per input address.
        """
        results = []
        for addr in addresses:
            result = await self.geocode(addr)
            results.append(result)

        logger.info(
            "Batch geocoding complete: %d addresses, %d cache hits, "
            "%d API calls, %d errors",
            len(addresses),
            self.stats["hits"],
            self.stats["misses"],
            self.stats["errors"],
        )

        return results

    async def save_driver_verified(
        self,
        address: str,
        location: Location,
    ) -> None:
        """Save a driver-verified geocoding result.

        When a driver delivers to an address and their GPS coordinates
        confirm the location, this creates a high-confidence cache entry.
        Over time, this builds the most accurate Kerala address database
        possible — better than any commercial API.

        Driver-verified entries always get confidence=0.95, matching
        the 0.95 that Google gives for ROOFTOP results. GPS delivers
        approximately building-level accuracy (~5-10m), so confidence
        is comparable to Google's best geocoding tier.

        This is called from the delivery confirmation endpoint when the
        driver taps "Confirm location" after marking a stop as delivered.

        Args:
            address: The original address text for this delivery.
            location: Driver's GPS coordinates at delivery time.
        """
        from core.database import repository as repo

        await repo.save_geocode_cache(
            session=self._session,
            address_raw=address,
            location=location,
            source="driver_verified",
            confidence=0.95,
        )
        logger.info(
            "Saved driver-verified location for '%s' at (%.6f, %.6f)",
            address[:50],
            location.latitude,
            location.longitude,
        )

    def get_stats_summary(self) -> str:
        """Return a human-readable summary of cache performance.

        Useful for logging after batch operations or in admin endpoints.
        """
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = (
            f"{self.stats['hits'] / total * 100:.1f}%"
            if total > 0
            else "N/A"
        )
        return (
            f"Geocode cache: {self.stats['hits']} hits, "
            f"{self.stats['misses']} misses, "
            f"{self.stats['errors']} errors "
            f"(hit rate: {hit_rate})"
        )
