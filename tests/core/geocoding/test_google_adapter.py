"""Tests for the Google Maps geocoding adapter.

Verifies that GoogleGeocoder correctly:
- Implements the Geocoder protocol
- Calls the Google Maps API and parses responses
- Handles API errors gracefully
- Maps Google's location_type to our confidence scores

GoogleGeocoder is now a pure stateless API caller -- no file cache.
Caching is handled by CachedGeocoder (see test_cache.py).

All tests mock the HTTP layer -- no real Google API calls.
"""

from unittest.mock import MagicMock, patch

import pytest

from core.geocoding.google_adapter import GoogleGeocoder
from core.geocoding.interfaces import GeocodingResult


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def geocoder():
    """GoogleGeocoder instance (no real API calls)."""
    return GoogleGeocoder(
        api_key="test-key-not-real",
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
                    "location": {"lat": 11.5950, "lng": 75.5700},
                    "location_type": "ROOFTOP",
                },
                "formatted_address": "Vatakara Bus Stand, Vatakara, Kerala 682024, India",
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
                    "location": {"lat": 11.6350, "lng": 75.5900},
                    "location_type": "APPROXIMATE",
                },
                "formatted_address": "Chorode, Vatakara, Kerala, India",
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
            result = geocoder.geocode("Vatakara Bus Stand, Vatakara")

        assert isinstance(result, GeocodingResult)
        assert result.success is True

    def test_rooftop_accuracy_gives_high_confidence(
        self, geocoder, google_rooftop_response
    ):
        """ROOFTOP location_type should map to 0.95 confidence.

        Why this mapping? ROOFTOP means Google resolved to a specific
        building -- the highest accuracy level. We use 0.95 (not 1.0)
        because even ROOFTOP can have ~10m error in Indian addresses.
        """
        with patch("core.geocoding.google_adapter.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: google_rooftop_response,
                raise_for_status=lambda: None,
            )
            result = geocoder.geocode("Vatakara Bus Stand, Vatakara")

        assert result.confidence == 0.95
        assert result.location is not None
        assert result.location.latitude == pytest.approx(11.5950)
        assert result.location.longitude == pytest.approx(75.5700)

    def test_approximate_accuracy_gives_low_confidence(
        self, geocoder, google_approximate_response
    ):
        """APPROXIMATE location_type maps to 0.40 -- lowest confidence.

        APPROXIMATE means Google only resolved to a general area.
        Many Kerala addresses (e.g., "near temple, Vatakara") get this.
        """
        with patch("core.geocoding.google_adapter.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: google_approximate_response,
                raise_for_status=lambda: None,
            )
            result = geocoder.geocode("Chorode, Vatakara")

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

    def test_each_geocode_call_hits_api(
        self, geocoder, google_rooftop_response
    ):
        """Every geocode() call should hit the API since GoogleGeocoder is stateless.

        Caching is handled by CachedGeocoder at a higher level.
        """
        with patch("core.geocoding.google_adapter.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: google_rooftop_response,
                raise_for_status=lambda: None,
            )
            # Both calls hit API -- no file cache
            result1 = geocoder.geocode("Vatakara Bus Stand, Vatakara")
            result2 = geocoder.geocode("Vatakara Bus Stand, Vatakara")

        # API was called twice (no caching in GoogleGeocoder)
        assert mock_get.call_count == 2
        # Both results are the same
        assert result1.location.latitude == result2.location.latitude
        assert result1.location.longitude == result2.location.longitude

    def test_network_error_returns_failed_result(self, geocoder):
        """HTTP errors should not crash -- return a failed GeocodingResult.

        This happens when the driver's phone has no signal. The caller
        can decide what to do (skip this order, retry later, etc.).
        """
        import httpx

        with patch("core.geocoding.google_adapter.httpx.get") as mock_get:
            mock_get.side_effect = httpx.ConnectError("No network")
            result = geocoder.geocode("Some Address, Vatakara")

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
            result = geocoder.geocode("Vatakara Bus Stand")

        assert "Vatakara Bus Stand" in result.formatted_address

    def test_constructor_accepts_only_api_key_and_region_bias(self):
        """GoogleGeocoder is a pure API caller -- no cache_dir parameter."""
        import inspect

        sig = inspect.signature(GoogleGeocoder.__init__)
        params = set(sig.parameters.keys()) - {"self"}
        assert params == {"api_key", "region_bias"}

    def test_no_file_cache_methods(self):
        """Verify file cache methods have been removed."""
        assert not hasattr(GoogleGeocoder, "_load_cache")
        assert not hasattr(GoogleGeocoder, "_save_cache")
        assert not hasattr(GoogleGeocoder, "_address_hash")
