"""Tests for the Google Maps geocoding adapter.

Verifies that GoogleGeocoder correctly:
- Implements the Geocoder protocol
- Caches results locally to save API costs
- Handles API errors gracefully
- Maps Google's location_type to our confidence scores

All tests mock the HTTP layer — no real Google API calls.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from core.geocoding.google_adapter import GoogleGeocoder
from core.geocoding.interfaces import GeocodingResult


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def geocoder(tmp_path):
    """GoogleGeocoder with a temp cache directory (no real API calls)."""
    return GoogleGeocoder(
        api_key="test-key-not-real",
        cache_dir=str(tmp_path / "cache"),
    )


@pytest.fixture
def google_rooftop_response():
    """Simulated Google Maps API response for a ROOFTOP-accuracy result.

    Based on real response structure from:
    https://developers.google.com/maps/documentation/geocoding/requests-geocoding
    """
    return {
        "status": "OK",
        "results": [
            {
                "geometry": {
                    "location": {"lat": 9.9816, "lng": 76.2996},
                    "location_type": "ROOFTOP",
                },
                "formatted_address": "Edappally Junction, Kochi, Kerala 682024, India",
                "place_id": "ChIJtest123",
            }
        ],
    }


@pytest.fixture
def google_approximate_response():
    """Simulated response with APPROXIMATE accuracy (area-level only)."""
    return {
        "status": "OK",
        "results": [
            {
                "geometry": {
                    "location": {"lat": 9.9312, "lng": 76.2673},
                    "location_type": "APPROXIMATE",
                },
                "formatted_address": "Marine Drive, Kochi, Kerala, India",
                "place_id": "ChIJtest456",
            }
        ],
    }


@pytest.fixture
def google_zero_results_response():
    """Simulated response when Google finds no match."""
    return {"status": "ZERO_RESULTS", "results": []}


# =============================================================================
# Tests
# =============================================================================


class TestGoogleGeocoder:
    """Unit tests for GoogleGeocoder with mocked HTTP."""

    def test_geocode_returns_geocoding_result(self, geocoder, google_rooftop_response):
        """Verify geocode() returns a GeocodingResult (Pydantic model)."""
        with patch("core.geocoding.google_adapter.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: google_rooftop_response,
                raise_for_status=lambda: None,
            )
            result = geocoder.geocode("Edappally Junction, Kochi")

        assert isinstance(result, GeocodingResult)
        assert result.success is True

    def test_rooftop_accuracy_gives_high_confidence(
        self, geocoder, google_rooftop_response
    ):
        """ROOFTOP location_type should map to 0.95 confidence.

        Why this mapping? ROOFTOP means Google resolved to a specific
        building — the highest accuracy level. We use 0.95 (not 1.0)
        because even ROOFTOP can have ~10m error in Indian addresses.
        """
        with patch("core.geocoding.google_adapter.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: google_rooftop_response,
                raise_for_status=lambda: None,
            )
            result = geocoder.geocode("Edappally Junction, Kochi")

        assert result.confidence == 0.95
        assert result.location is not None
        assert result.location.latitude == pytest.approx(9.9816)
        assert result.location.longitude == pytest.approx(76.2996)

    def test_approximate_accuracy_gives_low_confidence(
        self, geocoder, google_approximate_response
    ):
        """APPROXIMATE location_type maps to 0.40 — lowest confidence.

        APPROXIMATE means Google only resolved to a general area.
        Many Kerala addresses (e.g., "near temple, Kochi") get this.
        """
        with patch("core.geocoding.google_adapter.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: google_approximate_response,
                raise_for_status=lambda: None,
            )
            result = geocoder.geocode("Marine Drive, Kochi")

        assert result.confidence == 0.40

    def test_zero_results_returns_failed_result(
        self, geocoder, google_zero_results_response
    ):
        """When Google returns ZERO_RESULTS, we get success=False with no location."""
        with patch("core.geocoding.google_adapter.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: google_zero_results_response,
                raise_for_status=lambda: None,
            )
            result = geocoder.geocode("Nonexistent Place XYZ123")

        assert result.success is False
        assert result.location is None
        assert result.confidence == 0.0

    def test_cache_prevents_duplicate_api_calls(
        self, geocoder, google_rooftop_response
    ):
        """Second geocode for the same address should hit cache, not API.

        Why test this? At $5 per 1000 calls, caching repeat addresses
        (common for regular LPG customers) saves significant money.
        """
        with patch("core.geocoding.google_adapter.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: google_rooftop_response,
                raise_for_status=lambda: None,
            )
            # First call hits API
            result1 = geocoder.geocode("Edappally Junction, Kochi")
            # Second call should use cache
            result2 = geocoder.geocode("Edappally Junction, Kochi")

        # API was called only once
        assert mock_get.call_count == 1
        # Both results are the same
        assert result1.location.latitude == result2.location.latitude
        assert result1.location.longitude == result2.location.longitude

    def test_network_error_returns_failed_result(self, geocoder):
        """HTTP errors should not crash — return a failed GeocodingResult.

        This happens when the driver's phone has no signal. The caller
        can decide what to do (skip this order, retry later, etc.).
        """
        import httpx

        with patch("core.geocoding.google_adapter.httpx.get") as mock_get:
            mock_get.side_effect = httpx.ConnectError("No network")
            result = geocoder.geocode("Some Address, Kochi")

        assert result.success is False
        assert result.location is None

    def test_geocode_batch_processes_all_addresses(
        self, geocoder, google_rooftop_response
    ):
        """geocode_batch should return one result per address."""
        with patch("core.geocoding.google_adapter.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: google_rooftop_response,
                raise_for_status=lambda: None,
            )
            results = geocoder.geocode_batch(["Addr 1", "Addr 2", "Addr 3"])

        assert len(results) == 3
        assert all(isinstance(r, GeocodingResult) for r in results)

    def test_formatted_address_populated(self, geocoder, google_rooftop_response):
        """Verify the formatted_address from Google is stored in the result."""
        with patch("core.geocoding.google_adapter.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: google_rooftop_response,
                raise_for_status=lambda: None,
            )
            result = geocoder.geocode("Edappally")

        assert "Edappally Junction" in result.formatted_address

    def test_cache_persists_to_disk(self, geocoder, google_rooftop_response, tmp_path):
        """Cache file should be written to disk after a successful geocode.

        This ensures if the app restarts, cached results are preserved.
        """
        with patch("core.geocoding.google_adapter.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: google_rooftop_response,
                raise_for_status=lambda: None,
            )
            geocoder.geocode("Test Address")

        # Cache file should exist
        cache_file = tmp_path / "cache" / "google_cache.json"
        assert cache_file.exists()
        cache_data = json.loads(cache_file.read_text())
        assert len(cache_data) > 0

    def test_corrupt_cache_file_recovered(self, tmp_path):
        """A corrupt cache file should not crash the geocoder.

        If the app crashed mid-write (unlikely with atomic saves, but possible),
        the next startup should recover gracefully by starting with an empty cache.
        """
        cache_dir = tmp_path / "corrupt_cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "google_cache.json"
        cache_file.write_text("{invalid json content!!!}")

        # Should not raise — starts with empty cache
        geocoder = GoogleGeocoder(api_key="test-key", cache_dir=str(cache_dir))
        assert geocoder._cache == {}

    def test_cache_with_non_dict_content_recovered(self, tmp_path):
        """If cache file contains valid JSON but not a dict, start fresh.

        Edge case: a file containing a JSON array [] instead of a dict {}.
        """
        cache_dir = tmp_path / "bad_cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "google_cache.json"
        cache_file.write_text("[1, 2, 3]")

        geocoder = GoogleGeocoder(api_key="test-key", cache_dir=str(cache_dir))
        assert geocoder._cache == {}
