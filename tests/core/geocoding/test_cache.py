"""Tests for the PostGIS-backed geocoding cache module.

Verifies that CachedGeocoder correctly:
- Returns cached results on cache hits (no upstream API call)
- Falls through to upstream on cache misses
- Saves upstream results to PostGIS cache
- Handles cache lookup failures gracefully
- Handles upstream geocoding errors gracefully
- Tracks cache statistics (hits, misses, errors)
- Saves driver-verified locations with correct confidence

All tests mock the repository layer and upstream geocoder —
no real database or API calls.

Design pattern:
CachedGeocoder is a Decorator (GoF) — it wraps an upstream Geocoder
and adds caching behavior. Tests verify the decorator's behavior,
not the upstream provider or the database layer.
See: https://refactoring.guru/design-patterns/decorator

Patching strategy:
cache.py lazily imports ``from core.database import repository as repo``
inside each method. We patch the source functions on ``core.database.repository``
so the lazy import picks up the mocks.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.geocoding.cache import CachedGeocoder
from core.geocoding.interfaces import GeocodingResult
from core.models.location import Location

# Paths to the repository functions we need to mock.
# cache.py does ``from core.database import repository as repo`` lazily,
# so we patch where the functions are defined, not where they're imported.
PATCH_GET_CACHED = "core.database.repository.get_cached_geocode"
PATCH_SAVE_CACHED = "core.database.repository.save_geocode_cache"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_session():
    """Mock async DB session — no real database connection needed."""
    return AsyncMock()


@pytest.fixture
def kochi_location():
    """A geocoded location in central Vatakara for cache test data."""
    return Location(
        latitude=11.5950,
        longitude=75.5700,
        address_text="Vatakara Bus Stand, Vatakara",
        geocode_confidence=0.95,
    )


@pytest.fixture
def mock_upstream(kochi_location):
    """Mock upstream geocoder (e.g., GoogleGeocoder) that always succeeds.

    Returns a GeocodingResult with the Vatakara location for any address.
    In production, this would be GoogleGeocoder calling the real API.
    """
    upstream = MagicMock()
    upstream.geocode.return_value = GeocodingResult(
        location=kochi_location,
        confidence=0.95,
        formatted_address="Vatakara Bus Stand, Vatakara, Kerala 682024",
    )
    return upstream


@pytest.fixture
def mock_upstream_failure():
    """Mock upstream geocoder that always fails to find a location."""
    upstream = MagicMock()
    upstream.geocode.return_value = GeocodingResult(
        location=None,
        confidence=0.0,
        raw_response={"status": "ZERO_RESULTS"},
    )
    return upstream


@pytest.fixture
def cached_geocoder(mock_upstream, mock_session):
    """CachedGeocoder instance with mock upstream and session."""
    return CachedGeocoder(
        upstream=mock_upstream,
        session=mock_session,
        default_source="google",
    )


# =============================================================================
# Cache Hit Tests
# =============================================================================


class TestCacheHit:
    """Verify that cache hits return immediately without calling upstream."""

    @pytest.mark.asyncio
    async def test_returns_cached_location(
        self, cached_geocoder, mock_upstream, kochi_location
    ):
        """A cached address should return the PostGIS result, not call Google.

        This is the core value proposition of the cache: repeat customers
        cost $0 for geocoding after the first lookup.
        """
        with patch(
            PATCH_GET_CACHED,
            new_callable=AsyncMock,
            return_value=kochi_location,
        ):
            result = await cached_geocoder.geocode("Vatakara Bus Stand, Vatakara")

        assert result.success is True
        assert result.location.latitude == pytest.approx(11.5950)
        assert result.location.longitude == pytest.approx(75.5700)
        # Upstream should NOT have been called
        mock_upstream.geocode.assert_not_called()

    @pytest.mark.asyncio
    async def test_increments_hit_counter(self, cached_geocoder, kochi_location):
        """Cache hit should increment the stats.hits counter.

        We track hits to monitor cache value over time — if hit rate is
        high, the cache is saving significant API costs.
        """
        with patch(
            PATCH_GET_CACHED,
            new_callable=AsyncMock,
            return_value=kochi_location,
        ):
            await cached_geocoder.geocode("Vatakara Bus Stand, Vatakara")

        assert cached_geocoder.stats["hits"] == 1
        assert cached_geocoder.stats["misses"] == 0

    @pytest.mark.asyncio
    async def test_cache_hit_uses_stored_confidence(
        self, cached_geocoder
    ):
        """Cache hit should use the stored geocode_confidence, not default.

        Different sources have different confidence levels:
        - Google ROOFTOP: 0.95
        - Driver verified: 0.95
        - Google APPROXIMATE: 0.5
        The cache preserves the original confidence.
        """
        low_confidence_location = Location(
            latitude=11.6350,
            longitude=75.5900,
            address_text="Near Temple, Vatakara",
            geocode_confidence=0.5,
        )
        with patch(
            PATCH_GET_CACHED,
            new_callable=AsyncMock,
            return_value=low_confidence_location,
        ):
            result = await cached_geocoder.geocode("Near Temple, Vatakara")

        assert result.confidence == 0.5


# =============================================================================
# Cache Miss Tests
# =============================================================================


class TestCacheMiss:
    """Verify that cache misses call the upstream provider and save results."""

    @pytest.mark.asyncio
    async def test_calls_upstream_on_miss(self, cached_geocoder, mock_upstream):
        """Cache miss must fall through to the upstream geocoder.

        This is how the cache grows: unknown addresses hit Google Maps,
        and the result is saved for future lookups.
        """
        with patch(
            PATCH_GET_CACHED,
            new_callable=AsyncMock,
            return_value=None,  # Cache miss
        ), patch(
            PATCH_SAVE_CACHED,
            new_callable=AsyncMock,
        ):
            result = await cached_geocoder.geocode("New Address, Vatakara")

        assert result.success is True
        mock_upstream.geocode.assert_called_once_with("New Address, Vatakara")

    @pytest.mark.asyncio
    async def test_saves_result_to_cache(self, cached_geocoder, kochi_location):
        """Successful upstream result should be persisted to PostGIS cache.

        After this, the same address will be a cache hit next time.
        """
        with patch(
            PATCH_GET_CACHED,
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            PATCH_SAVE_CACHED,
            new_callable=AsyncMock,
        ) as save_mock:
            await cached_geocoder.geocode("New Address, Vatakara")

        save_mock.assert_called_once()
        call_kwargs = save_mock.call_args.kwargs
        assert call_kwargs["source"] == "google"
        assert call_kwargs["confidence"] == 0.95
        assert call_kwargs["address_raw"] == "New Address, Vatakara"
        assert call_kwargs["location"] == kochi_location

    @pytest.mark.asyncio
    async def test_increments_miss_counter(self, cached_geocoder):
        """Cache miss should increment stats.misses counter."""
        with patch(
            PATCH_GET_CACHED,
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            PATCH_SAVE_CACHED,
            new_callable=AsyncMock,
        ):
            await cached_geocoder.geocode("Unknown Address")

        assert cached_geocoder.stats["misses"] == 1
        assert cached_geocoder.stats["hits"] == 0


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Verify graceful degradation when cache or upstream fails."""

    @pytest.mark.asyncio
    async def test_cache_lookup_failure_falls_through(
        self, cached_geocoder, mock_upstream
    ):
        """If PostGIS cache is unreachable, still try the upstream provider.

        The cache is an optimization, not a requirement. If the DB is
        temporarily unavailable (connection drop, maintenance), we should
        still successfully geocode via the API — we just pay for the call.
        """
        with patch(
            PATCH_GET_CACHED,
            new_callable=AsyncMock,
            side_effect=Exception("DB connection failed"),
        ), patch(
            PATCH_SAVE_CACHED,
            new_callable=AsyncMock,
        ):
            result = await cached_geocoder.geocode("Memunda, Vatakara")

        assert result.success is True
        mock_upstream.geocode.assert_called_once()

    @pytest.mark.asyncio
    async def test_upstream_failure_returns_empty_result(
        self, mock_upstream_failure, mock_session
    ):
        """If upstream geocoder fails, return GeocodingResult with location=None.

        The calling code (CSV importer, API endpoint) handles the failure —
        it should log the address for manual correction, not crash.
        """
        geocoder = CachedGeocoder(
            upstream=mock_upstream_failure, session=mock_session
        )
        with patch(
            PATCH_GET_CACHED,
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await geocoder.geocode("Nonexistent Place, Mars")

        assert result.success is False
        assert result.location is None

    @pytest.mark.asyncio
    async def test_upstream_exception_returns_error(self, mock_session):
        """If upstream geocoder raises an exception, catch it gracefully.

        This protects against HTTP timeouts, API key issues, rate limits,
        etc. The geocoding should never crash the import pipeline.
        """
        upstream = MagicMock()
        upstream.geocode.side_effect = Exception("API timeout")

        geocoder = CachedGeocoder(upstream=upstream, session=mock_session)
        with patch(
            PATCH_GET_CACHED,
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await geocoder.geocode("Some Address")

        assert result.success is False
        assert geocoder.stats["errors"] == 1

    @pytest.mark.asyncio
    async def test_cache_save_failure_returns_result_anyway(
        self, cached_geocoder
    ):
        """If saving to cache fails, still return the geocoded result.

        The upstream gave us a valid result — don't throw it away just
        because we couldn't cache it. We'll just re-geocode next time.
        """
        with patch(
            PATCH_GET_CACHED,
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            PATCH_SAVE_CACHED,
            new_callable=AsyncMock,
            side_effect=Exception("DB write failed"),
        ):
            result = await cached_geocoder.geocode("Memunda, Vatakara")

        # Result should still be successful despite cache save failure
        assert result.success is True


# =============================================================================
# Driver-Verified Location Tests
# =============================================================================


class TestDriverVerified:
    """Verify driver-verified geocoding saves high-confidence entries.

    Driver-verified locations are the most valuable geocoding source.
    When a driver confirms delivery at a GPS location, we save it with
    confidence=0.95 — almost as good as Google ROOFTOP (0.95).
    Over time, this builds the most accurate local address database.
    """

    @pytest.mark.asyncio
    async def test_saves_with_driver_verified_source(self, cached_geocoder):
        """Driver-verified saves should use source='driver_verified'."""
        with patch(
            PATCH_SAVE_CACHED,
            new_callable=AsyncMock,
        ) as save_mock:
            location = Location(latitude=11.6244, longitude=75.5796)
            await cached_geocoder.save_driver_verified(
                "Memunda, Vatakara", location
            )

        save_mock.assert_called_once()
        call_kwargs = save_mock.call_args.kwargs
        assert call_kwargs["source"] == "driver_verified"
        assert call_kwargs["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_driver_verified_location_coordinates(self, cached_geocoder):
        """Driver GPS coordinates should be saved exactly as provided.

        The driver's GPS is the ground truth — don't modify the
        coordinates before saving.
        """
        with patch(
            PATCH_SAVE_CACHED,
            new_callable=AsyncMock,
        ) as save_mock:
            location = Location(latitude=11.6244, longitude=75.5796)
            await cached_geocoder.save_driver_verified(
                "Memunda, Vatakara", location
            )

        call_kwargs = save_mock.call_args.kwargs
        assert call_kwargs["location"].latitude == pytest.approx(11.6244)
        assert call_kwargs["location"].longitude == pytest.approx(75.5796)


# =============================================================================
# Stats & Batch Tests
# =============================================================================


class TestStatsAndBatch:
    """Verify cache statistics tracking and batch geocoding."""

    @pytest.mark.asyncio
    async def test_batch_geocode_calls_each_address(self, cached_geocoder):
        """Batch geocoding should process each address individually."""
        with patch(
            PATCH_GET_CACHED,
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            PATCH_SAVE_CACHED,
            new_callable=AsyncMock,
        ):
            results = await cached_geocoder.geocode_batch(
                ["Address A", "Address B", "Address C"]
            )

        assert len(results) == 3
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_batch_tracks_cumulative_stats(self, cached_geocoder, kochi_location):
        """Batch geocoding should accumulate stats across all addresses.

        After a batch of 3 where 1 is cached and 2 are misses,
        stats should show hits=1, misses=2.
        """
        # First call: cache hit, second & third: cache miss
        get_mock = AsyncMock(side_effect=[kochi_location, None, None])
        with patch(
            PATCH_GET_CACHED,
            new=get_mock,
        ), patch(
            PATCH_SAVE_CACHED,
            new_callable=AsyncMock,
        ):
            results = await cached_geocoder.geocode_batch(
                ["Cached Addr", "New Addr 1", "New Addr 2"]
            )

        assert len(results) == 3
        assert cached_geocoder.stats["hits"] == 1
        assert cached_geocoder.stats["misses"] == 2

    def test_stats_summary_format(self, cached_geocoder):
        """Stats summary should be a readable string with hit rate.

        Useful for logging: "Geocode cache: 38 hits, 12 misses (76.0%)"
        """
        cached_geocoder.stats = {"hits": 38, "misses": 12, "errors": 0}
        summary = cached_geocoder.get_stats_summary()

        assert "38 hits" in summary
        assert "12 misses" in summary
        assert "76.0%" in summary

    def test_stats_summary_empty(self, cached_geocoder):
        """Stats summary with zero total should show N/A for hit rate."""
        summary = cached_geocoder.get_stats_summary()
        assert "N/A" in summary
