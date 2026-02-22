"""Google Maps Geocoding API adapter.

Google Maps is the most accurate geocoder for Indian addresses (~63% accuracy).
We cache every result to minimize API costs — at 40-50 deliveries/day with
repeat customers, cache hit rates should be >70% within a month.

API docs: https://developers.google.com/maps/documentation/geocoding
Pricing: $5 per 1000 requests. With $200/month free credit, that's 40,000
free requests — more than enough for this scale.
"""

import hashlib
import json
import logging
from pathlib import Path

import httpx

from core.geocoding.interfaces import GeocodingResult
from core.models.location import Location

logger = logging.getLogger(__name__)


class GoogleGeocoder:
    """Geocode addresses using Google Maps Geocoding API with local file cache.

    Why file-based cache first (not PostGIS)?
    - Zero infrastructure needed to start — just a JSON file
    - We'll move to PostGIS cache once the database is running
    - The cache format is simple: address_hash → {lat, lon, formatted_address}

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
        cache_dir: str = "data/geocode_cache",
        region_bias: str = "in",  # Bias results toward India
    ):
        """Initialize Google geocoder.

        Args:
            api_key: Google Maps API key.
            cache_dir: Directory for the local geocode cache file.
            region_bias: ISO 3166-1 country code to bias results. Default "in" (India).
        """
        self.api_key = api_key
        self.region_bias = region_bias
        self.cache_path = Path(cache_dir) / "google_cache.json"
        self._cache: dict[str, dict] = self._load_cache()

    def geocode(self, address: str) -> GeocodingResult:
        """Geocode a single address, checking cache first.

        Flow:
        1. Normalize address → compute hash
        2. Check local cache → return if found
        3. Call Google Maps API
        4. Save to cache
        5. Return result
        """
        cache_key = self._address_hash(address)

        # Check cache first — saves API calls and money
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            return GeocodingResult(
                location=Location(
                    latitude=cached["lat"],
                    longitude=cached["lon"],
                    address_text=cached.get("formatted_address", address),
                    geocode_confidence=cached.get("confidence", 0.8),
                ),
                confidence=cached.get("confidence", 0.8),
                formatted_address=cached.get("formatted_address", ""),
            )

        # Cache miss — call Google Maps API
        result = self._call_api(address)

        # Cache successful results
        if result.success and result.location:
            self._cache[cache_key] = {
                "lat": result.location.latitude,
                "lon": result.location.longitude,
                "formatted_address": result.formatted_address,
                "confidence": result.confidence,
                "original_address": address,
            }
            self._save_cache()

        return result

    def geocode_batch(self, addresses: list[str]) -> list[GeocodingResult]:
        """Geocode multiple addresses sequentially.

        Google's Geocoding API doesn't have a true batch endpoint,
        so we call one at a time. The cache minimizes actual API calls.
        """
        return [self.geocode(addr) for addr in addresses]

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

    def _address_hash(self, address: str) -> str:
        """Generate a stable cache key from an address string.

        Normalizes whitespace and casing so "MG Road, Kochi" and
        "mg road,  kochi" hit the same cache entry.
        """
        normalized = " ".join(address.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _load_cache(self) -> dict[str, dict]:
        """Load the geocode cache from disk.

        Resilient to corruption: if the file exists but can't be parsed
        (e.g., process crashed mid-write), we start fresh. The atomic
        _save_cache() minimizes this risk, but belt-and-suspenders.
        """
        if self.cache_path.exists():
            try:
                data = json.loads(self.cache_path.read_text())
                if isinstance(data, dict):
                    return data
                # File exists but isn't a dict — corrupt
                logger.warning("Geocode cache is not a dict, starting fresh")
                return {}
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Geocode cache corrupt, starting fresh: %s", e)
                return {}
        return {}

    def _save_cache(self) -> None:
        """Persist the geocode cache to disk atomically.

        Why atomic write (write to temp, then rename)?
        If the process crashes mid-write, a direct write_text() would leave
        a corrupt/partial JSON file. Writing to a temp file first and then
        renaming ensures the cache is either fully written or absent.
        On POSIX systems, rename() is atomic within the same filesystem.
        """
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.cache_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(self._cache, indent=2))
        tmp_path.rename(self.cache_path)
