"""Google Maps Geocoding API adapter — pure API caller.

Google Maps is the most accurate geocoder for Indian addresses (~63% accuracy).
Caching is handled by CachedGeocoder (decorator pattern) backed by PostgreSQL,
not by this adapter. This keeps GoogleGeocoder stateless and testable.

API docs: https://developers.google.com/maps/documentation/geocoding
Pricing: $5 per 1000 requests. With $200/month free credit, that's 40,000
free requests — more than enough for this scale.
"""

import logging

import httpx

from core.geocoding.interfaces import GeocodingResult
from core.models.location import Location

logger = logging.getLogger(__name__)


class GoogleGeocoder:
    """Geocode addresses using Google Maps Geocoding API.

    This is a pure, stateless API caller — no file cache, no hashing, no I/O
    beyond HTTP requests. All caching is handled by CachedGeocoder, which
    wraps this adapter and checks/writes the PostGIS geocode_cache table.

    Usage:
        geocoder = GoogleGeocoder(api_key="your-key")
        result = geocoder.geocode("MG Road, Kochi, Kerala")
        if result.success:
            print(result.location.latitude, result.location.longitude)
    """

    # Google Maps Geocoding API endpoint
    API_URL = "https://maps.googleapis.com/maps/api/geocode/json"

    def __init__(
        self,
        api_key: str,
        region_bias: str = "in",  # Bias results toward India
    ):
        """Initialize Google geocoder.

        Args:
            api_key: Google Maps API key.
            region_bias: ISO 3166-1 country code to bias results. Default "in" (India).
        """
        self.api_key = api_key
        self.region_bias = region_bias

    def geocode(self, address: str) -> GeocodingResult:
        """Geocode a single address via Google Maps API.

        No caching -- caching is handled by CachedGeocoder (decorator pattern).
        """
        return self._call_api(address)

    def geocode_batch(self, addresses: list[str]) -> list[GeocodingResult]:
        """Geocode multiple addresses sequentially via Google Maps API."""
        return [self._call_api(addr) for addr in addresses]

    def _call_api(self, address: str) -> GeocodingResult:
        """Make a single request to Google Maps Geocoding API.

        Returns a GeocodingResult even on failure (with location=None).
        """
        try:
            response = httpx.get(
                self.API_URL,
                params={
                    "address": address,
                    "key": self.api_key,
                    "region": self.region_bias,
                },
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            if data["status"] != "OK" or not data.get("results"):
                # Log actionable details for common Google API errors:
                # - REQUEST_DENIED: API key invalid, Geocoding API not enabled,
                #   or billing not set up in Google Cloud Console.
                # - OVER_QUERY_LIMIT: billing cap hit or too many requests/sec.
                # - ZERO_RESULTS: valid request but no match for this address.
                # Passing raw_response through so callers can inspect the reason.
                if data.get("error_message"):
                    logger.warning(
                        "Google Geocoding API error for '%s': %s — %s",
                        address[:60],
                        data["status"],
                        data["error_message"],
                    )
                return GeocodingResult(
                    location=None,
                    confidence=0.0,
                    raw_response=data,
                )

            # Take the first (most relevant) result
            result = data["results"][0]
            geo = result["geometry"]["location"]

            # Map Google's location_type to a confidence score:
            # ROOFTOP = exact building → 0.95
            # RANGE_INTERPOLATED = between two points → 0.80
            # GEOMETRIC_CENTER = center of area → 0.60
            # APPROXIMATE = rough area → 0.40
            confidence_map = {
                "ROOFTOP": 0.95,
                "RANGE_INTERPOLATED": 0.80,
                "GEOMETRIC_CENTER": 0.60,
                "APPROXIMATE": 0.40,
            }
            loc_type = result["geometry"].get("location_type", "APPROXIMATE")
            confidence = confidence_map.get(loc_type, 0.40)

            location = Location(
                latitude=geo["lat"],
                longitude=geo["lng"],
                address_text=result.get("formatted_address", address),
                place_id=result.get("place_id"),
                geocode_confidence=confidence,
            )

            return GeocodingResult(
                location=location,
                confidence=confidence,
                formatted_address=result.get("formatted_address", ""),
                raw_response=data,
            )

        except (httpx.HTTPError, KeyError, IndexError) as e:
            return GeocodingResult(
                location=None,
                confidence=0.0,
                raw_response={"error": str(e)},
            )
