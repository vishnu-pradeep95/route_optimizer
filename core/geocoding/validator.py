"""Geocode validation with zone checking, fallback chain, and circuit breaker.

Validates every geocoded delivery address against a configurable radius from
the depot. Out-of-zone results trigger an automatic fallback chain:

1. **Direct** (confidence 1.0): Google result within zone -- no action needed.
2. **Area-name retry** (confidence 0.7): Re-geocode with CDCMS area name
   appended with regional suffix (e.g., "EDAPPAL, Vatakara, Kozhikode, Kerala").
3. **Dictionary centroid** (confidence 0.3): Use centroid coordinates from the
   place name dictionary (data/place_names_vatakara.json).
4. **Depot fallback** (confidence 0.1): Use depot coordinates as last resort.

A circuit breaker halts Google API retries after 3 consecutive REQUEST_DENIED
responses, skipping directly to centroid/depot fallback.

Core value: Every delivery address gets coordinates -- no silent drops.

Usage:
    from core.geocoding.validator import GeocodeValidator

    validator = GeocodeValidator(
        depot_lat=11.6244,
        depot_lon=75.5796,
        dictionary_path="data/place_names_vatakara.json",
    )
    result = validator.validate(lat, lon, area_name="EDAPPAL", geocoder=geocoder)
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

from core.geocoding.duplicate_detector import haversine_meters

logger = logging.getLogger(__name__)

# Confidence scores for each fallback method
CONFIDENCE_DIRECT = 1.0
CONFIDENCE_AREA_RETRY = 0.7
CONFIDENCE_CENTROID = 0.3
CONFIDENCE_DEPOT = 0.1

# Circuit breaker threshold
CIRCUIT_BREAKER_THRESHOLD = 3


@dataclass
class ValidationResult:
    """Result of geocode validation against the delivery zone.

    Attributes:
        latitude: Validated latitude (may differ from original if fallback used).
        longitude: Validated longitude (may differ from original if fallback used).
        confidence: 0.1 to 1.0 confidence score based on fallback method.
        method: Which fallback level was used: 'direct', 'area_retry',
            'centroid', or 'depot'.
        original_lat: Pre-validation latitude (for logging/debugging).
        original_lon: Pre-validation longitude (for logging/debugging).
    """

    latitude: float
    longitude: float
    confidence: float
    method: str
    original_lat: float | None = None
    original_lon: float | None = None


class GeocodeValidator:
    """Validates geocoded coordinates against a delivery zone with fallback chain.

    The validator checks if coordinates fall within a configurable radius from
    the depot. Out-of-zone results trigger an ordered fallback chain until
    valid coordinates are found. A circuit breaker prevents excessive API calls
    when the Google Maps API key is invalid.

    Args:
        depot_lat: Depot latitude (center of delivery zone).
        depot_lon: Depot longitude (center of delivery zone).
        zone_radius_m: Maximum distance from depot in meters (default 30km).
        dictionary_path: Path to place_names_vatakara.json for centroid lookups.
        area_suffix: Regional suffix for area-name retry queries.
    """

    def __init__(
        self,
        depot_lat: float,
        depot_lon: float,
        zone_radius_m: float = 30_000,
        dictionary_path: str | None = None,
        area_suffix: str = ", Vatakara, Kozhikode, Kerala",
    ) -> None:
        self._depot_lat = depot_lat
        self._depot_lon = depot_lon
        self._zone_radius_m = zone_radius_m
        self._area_suffix = area_suffix

        # Centroid lookup index: UPPERCASE name/alias -> (lat, lon)
        self._centroids: dict[str, tuple[float, float]] = {}
        if dictionary_path:
            self._load_centroids(dictionary_path)

        # Circuit breaker state
        self._consecutive_denials: int = 0
        self._circuit_breaker_tripped: bool = False

        # Validation stats
        self._stats: dict[str, int] = {
            "direct_count": 0,
            "area_retry_count": 0,
            "centroid_count": 0,
            "depot_count": 0,
            "circuit_breaker_trips": 0,
        }

    def is_in_zone(self, lat: float, lon: float) -> bool:
        """Check if coordinates are within the delivery zone.

        Uses haversine distance from depot. Coordinates within zone_radius_m
        meters of the depot are considered in-zone.

        Args:
            lat: Latitude to check.
            lon: Longitude to check.

        Returns:
            True if within zone radius, False otherwise.
        """
        distance = haversine_meters(self._depot_lat, self._depot_lon, lat, lon)
        return distance <= self._zone_radius_m

    def get_centroid(self, area_name: str) -> tuple[float, float] | None:
        """Look up centroid coordinates for an area name.

        Case-insensitive exact match against dictionary primary names and
        aliases. Returns None if area name is not in the dictionary.

        Args:
            area_name: Area name to look up (e.g., "MUTTUNGAL", "vatakara").

        Returns:
            (latitude, longitude) tuple or None if not found.
        """
        normalized = area_name.strip().upper()
        return self._centroids.get(normalized)

    def validate(
        self,
        lat: float,
        lon: float,
        area_name: str | None,
        geocoder: Any,
    ) -> ValidationResult:
        """Validate geocoded coordinates against the delivery zone.

        Runs the full fallback chain:
        1. Check if (lat, lon) is in zone -> direct (1.0)
        2. If circuit breaker tripped, skip to centroid/depot
        3. If area_name provided, retry geocode with area suffix -> area_retry (0.7)
        4. Look up centroid for area_name -> centroid (0.3)
        5. Return depot fallback -> depot (0.1)

        Args:
            lat: Geocoded latitude to validate.
            lon: Geocoded longitude to validate.
            area_name: CDCMS area name (None for standard CSV uploads).
            geocoder: Sync Geocoder instance for area-name retry API calls.

        Returns:
            ValidationResult with validated coordinates and confidence score.
        """
        # Step 1: Direct zone check
        if self.is_in_zone(lat, lon):
            self._stats["direct_count"] += 1
            return ValidationResult(
                latitude=lat,
                longitude=lon,
                confidence=CONFIDENCE_DIRECT,
                method="direct",
            )

        # Out of zone -- all fallback paths store original coordinates
        original_lat, original_lon = lat, lon

        # Step 2: If circuit breaker tripped, skip geocoder calls
        if not self._circuit_breaker_tripped and area_name is not None:
            # Step 3: Area-name retry via geocoder
            retry_result = self._try_area_retry(area_name, geocoder)
            if retry_result is not None:
                self._stats["area_retry_count"] += 1
                return ValidationResult(
                    latitude=retry_result[0],
                    longitude=retry_result[1],
                    confidence=CONFIDENCE_AREA_RETRY,
                    method="area_retry",
                    original_lat=original_lat,
                    original_lon=original_lon,
                )

        # Step 4: Centroid fallback from dictionary
        if area_name is not None:
            centroid = self.get_centroid(area_name)
            if centroid is not None:
                self._stats["centroid_count"] += 1
                return ValidationResult(
                    latitude=centroid[0],
                    longitude=centroid[1],
                    confidence=CONFIDENCE_CENTROID,
                    method="centroid",
                    original_lat=original_lat,
                    original_lon=original_lon,
                )

        # Step 5: Depot fallback (ultimate)
        self._stats["depot_count"] += 1
        return ValidationResult(
            latitude=self._depot_lat,
            longitude=self._depot_lon,
            confidence=CONFIDENCE_DEPOT,
            method="depot",
            original_lat=original_lat,
            original_lon=original_lon,
        )

    def _try_area_retry(
        self, area_name: str, geocoder: Any
    ) -> tuple[float, float] | None:
        """Attempt area-name retry via geocoder.

        Constructs a query like "EDAPPAL, Vatakara, Kozhikode, Kerala" and
        sends it to the geocoder. If the result is in-zone, returns the
        coordinates. Also handles REQUEST_DENIED for circuit breaker.

        Args:
            area_name: CDCMS area name.
            geocoder: Sync Geocoder instance.

        Returns:
            (lat, lon) tuple if retry succeeded and result is in-zone, None otherwise.
        """
        retry_query = f"{area_name}{self._area_suffix}"
        try:
            result = geocoder.geocode(retry_query)
        except Exception:
            logger.warning("Area-name retry failed for %s", area_name, exc_info=True)
            return None

        # Check for REQUEST_DENIED in raw response
        raw_status = result.raw_response.get("status", "")
        if raw_status == "REQUEST_DENIED":
            self.record_api_denial()
        elif result.success:
            # Any successful response resets the circuit breaker
            self.record_api_success()

        # Check if the retry result is in-zone
        if result.success and result.location is not None:
            if self.is_in_zone(result.location.latitude, result.location.longitude):
                return (result.location.latitude, result.location.longitude)

        return None

    def record_api_denial(self) -> None:
        """Record a REQUEST_DENIED response for circuit breaker tracking.

        After 3 consecutive denials, the circuit breaker trips and all
        subsequent validate() calls skip geocoder API calls.
        """
        self._consecutive_denials += 1
        if self._consecutive_denials >= CIRCUIT_BREAKER_THRESHOLD:
            self._circuit_breaker_tripped = True
            self._stats["circuit_breaker_trips"] += 1
            logger.warning(
                "Circuit breaker tripped after %d consecutive REQUEST_DENIED responses",
                self._consecutive_denials,
            )

    def record_api_success(self) -> None:
        """Record a successful (non-REQUEST_DENIED) API response.

        Resets the consecutive denial counter. Does NOT un-trip a tripped
        circuit breaker (stateless per batch -- resets on new upload).
        """
        self._consecutive_denials = 0

    @property
    def is_tripped(self) -> bool:
        """Whether the circuit breaker is currently tripped."""
        return self._circuit_breaker_tripped

    @property
    def stats(self) -> dict[str, int]:
        """Validation statistics for the current batch.

        Returns:
            Dict with keys: direct_count, area_retry_count, centroid_count,
            depot_count, circuit_breaker_trips.
        """
        return self._stats

    def _load_centroids(self, path: str) -> None:
        """Load centroid coordinates from the place name dictionary.

        Indexes entries by uppercase primary name and all aliases for
        case-insensitive exact-match lookup.

        Args:
            path: Path to place_names_vatakara.json.
        """
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Failed to load place name dictionary from %s: %s", path, e)
            return

        for entry in data.get("entries", []):
            name = entry.get("name", "").strip().upper()
            lat = entry.get("lat")
            lon = entry.get("lon")
            if name and lat is not None and lon is not None:
                self._centroids[name] = (lat, lon)
                # Index aliases too
                for alias in entry.get("aliases", []):
                    alias_upper = alias.strip().upper()
                    if alias_upper:
                        self._centroids[alias_upper] = (lat, lon)

        logger.info(
            "Loaded %d centroid entries from %s", len(self._centroids), path
        )
