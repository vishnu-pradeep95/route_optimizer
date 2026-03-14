"""Tests for GeocodeValidator: zone validation, fallback chain, and circuit breaker.

Verifies that GeocodeValidator correctly:
- Checks coordinates against 20km radius from Vatakara depot (zone check)
- Returns direct hit (confidence 1.0) for in-zone coordinates
- Triggers area-name retry via geocoder for out-of-zone results
- Falls back to dictionary centroid when area retry also fails
- Falls back to depot coordinates as ultimate fallback
- Tracks circuit breaker state (3 consecutive REQUEST_DENIED)
- Resets circuit breaker on any non-REQUEST_DENIED response
- Skips geocoder calls when circuit breaker is tripped
- Handles area_name=None gracefully (skip area retry)
- Loads centroids from dictionary (case-insensitive, aliases)
- Tracks validation stats

All tests use mock geocoders -- no real API calls or DB needed.
"""

from unittest.mock import MagicMock

import pytest

from core.geocoding.validator import GeocodeValidator, ValidationResult
from core.geocoding.interfaces import GeocodingResult
from core.models.location import Location


# Vatakara depot coordinates
DEPOT_LAT = 11.624443730714066
DEPOT_LON = 75.57964507762223

# Dictionary path for centroid tests
DICTIONARY_PATH = "data/place_names_vatakara.json"


def _make_geocoder(lat=None, lon=None, status="OK", raw_response=None):
    """Create a mock geocoder that returns specific coordinates."""
    mock = MagicMock()
    if lat is not None and lon is not None:
        result = GeocodingResult(
            location=Location(latitude=lat, longitude=lon),
            confidence=0.8,
            formatted_address="Mock Address",
            raw_response=raw_response or {"status": status},
        )
    else:
        result = GeocodingResult(
            location=None,
            confidence=0.0,
            formatted_address="",
            raw_response=raw_response or {"status": status},
        )
    mock.geocode.return_value = result
    return mock


class TestZoneCheck:
    """GVAL-01: Zone validation via haversine (20km radius)."""

    def test_depot_itself_is_in_zone(self):
        """Depot coordinates (distance 0m) should be in zone."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON)
        assert v.is_in_zone(DEPOT_LAT, DEPOT_LON) is True

    def test_nearby_coordinate_in_zone(self):
        """Coordinates ~3.5km from depot should be in zone."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON)
        assert v.is_in_zone(11.65, 75.56) is True

    def test_far_coordinate_out_of_zone(self):
        """Coordinates >20km from depot should be out of zone."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON)
        # ~47km away
        assert v.is_in_zone(12.0, 75.0) is False

    def test_very_far_coordinate_out_of_zone(self):
        """Kochi area (~200km) should be out of zone."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON)
        assert v.is_in_zone(10.0, 76.0) is False

    def test_edge_of_zone_boundary(self):
        """Coordinate right at 20km boundary."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON, zone_radius_m=20_000)
        # This point is roughly 19km from depot -- check boundary behavior
        # We use a known point just inside 20km
        # ~19km away (still in zone)
        assert v.is_in_zone(11.795, 75.58) is True

    def test_out_of_zone_address_not_accepted_as_direct(self):
        """Coordinate ~25km from depot (outside 20km zone) is NOT a direct hit.

        Per CONTEXT.md: out-of-zone addresses trigger fallback chain with UI warning.
        This verifies that coordinates between 20km and 30km (previously in-zone,
        now out-of-zone) are rejected as direct hits and fall through to
        depot fallback (confidence < 0.5, location_approximate: true).
        """
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON, zone_radius_m=20_000,
                             dictionary_path=DICTIONARY_PATH)
        # ~25km from depot -- was in-zone at 30km, now out-of-zone at 20km
        mock_geocoder = _make_geocoder(lat=11.85, lon=75.58)
        result = v.validate(
            lat=11.85, lon=75.58, area_name="SOMEZONE", geocoder=mock_geocoder
        )
        assert result.method != "direct", (
            f"Expected fallback for out-of-zone (~25km), got method={result.method}"
        )
        assert result.confidence < 0.5, (
            f"Expected confidence < 0.5 for out-of-zone (~25km), got {result.confidence}"
        )


class TestDirectHit:
    """GVAL-04: Direct hit returns confidence 1.0."""

    def test_in_zone_returns_direct(self):
        """In-zone coordinate returns direct method with confidence 1.0."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON, dictionary_path=DICTIONARY_PATH)
        mock_geocoder = _make_geocoder()

        result = v.validate(
            lat=11.65, lon=75.56, area_name="VADAKARA", geocoder=mock_geocoder
        )

        assert result.confidence == 1.0
        assert result.method == "direct"
        assert result.latitude == 11.65
        assert result.longitude == 75.56
        # No calls to geocoder for in-zone results
        mock_geocoder.geocode.assert_not_called()

    def test_depot_coordinates_are_direct(self):
        """Depot coordinates themselves return direct hit."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON)
        mock_geocoder = _make_geocoder()

        result = v.validate(
            lat=DEPOT_LAT, lon=DEPOT_LON, area_name=None, geocoder=mock_geocoder
        )

        assert result.confidence == 1.0
        assert result.method == "direct"
        mock_geocoder.geocode.assert_not_called()


class TestAreaRetry:
    """GVAL-02: Out-of-zone results trigger area-name retry."""

    def test_area_retry_returns_in_zone(self):
        """Area-name retry that returns in-zone coordinates succeeds."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON, dictionary_path=DICTIONARY_PATH)
        # Mock geocoder returns in-zone coordinates for area retry
        in_zone_lat, in_zone_lon = 11.63, 75.58
        mock_geocoder = _make_geocoder(lat=in_zone_lat, lon=in_zone_lon)

        result = v.validate(
            lat=28.6, lon=77.2, area_name="EDAPPAL", geocoder=mock_geocoder
        )

        assert result.confidence == 0.7
        assert result.method == "area_retry"
        assert result.latitude == in_zone_lat
        assert result.longitude == in_zone_lon
        # Geocoder called with area + suffix
        mock_geocoder.geocode.assert_called_once()
        call_args = mock_geocoder.geocode.call_args[0][0]
        assert "EDAPPAL" in call_args
        assert "Vatakara" in call_args
        assert "Kerala" in call_args

    def test_area_retry_preserves_original_coords(self):
        """Area retry result includes original out-of-zone coordinates."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON, dictionary_path=DICTIONARY_PATH)
        mock_geocoder = _make_geocoder(lat=11.63, lon=75.58)

        result = v.validate(
            lat=28.6, lon=77.2, area_name="EDAPPAL", geocoder=mock_geocoder
        )

        assert result.original_lat == 28.6
        assert result.original_lon == 77.2


class TestCentroidFallback:
    """GVAL-03: Failed area retry falls back to dictionary centroid."""

    def test_centroid_fallback_when_area_retry_out_of_zone(self):
        """When area retry also returns out-of-zone, fall back to centroid."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON, dictionary_path=DICTIONARY_PATH)
        # Mock geocoder returns out-of-zone for area retry too
        mock_geocoder = _make_geocoder(lat=28.7, lon=77.3)

        result = v.validate(
            lat=28.6, lon=77.2, area_name="MUTTUNGAL", geocoder=mock_geocoder
        )

        assert result.confidence == 0.3
        assert result.method == "centroid"
        # Coordinates should be from the dictionary for MUTTUNGAL
        assert result.latitude is not None
        assert result.longitude is not None

    def test_centroid_fallback_when_geocoder_fails(self):
        """When geocoder returns no location, fall back to centroid."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON, dictionary_path=DICTIONARY_PATH)
        # Mock geocoder returns failure
        mock_geocoder = _make_geocoder(lat=None, lon=None, status="ZERO_RESULTS")

        result = v.validate(
            lat=28.6, lon=77.2, area_name="MUTTUNGAL", geocoder=mock_geocoder
        )

        assert result.confidence == 0.3
        assert result.method == "centroid"


class TestDepotFallback:
    """Depot fallback when centroid not found."""

    def test_depot_fallback_unknown_area(self):
        """Unknown area name falls back to depot coordinates."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON, dictionary_path=DICTIONARY_PATH)
        # Mock geocoder returns out-of-zone
        mock_geocoder = _make_geocoder(lat=28.7, lon=77.3)

        result = v.validate(
            lat=28.6, lon=77.2, area_name="UNKNOWNPLACE", geocoder=mock_geocoder
        )

        assert result.confidence == 0.1
        assert result.method == "depot"
        assert result.latitude == DEPOT_LAT
        assert result.longitude == DEPOT_LON

    def test_depot_fallback_preserves_original_coords(self):
        """Depot fallback includes original coordinates."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON, dictionary_path=DICTIONARY_PATH)
        mock_geocoder = _make_geocoder(lat=28.7, lon=77.3)

        result = v.validate(
            lat=28.6, lon=77.2, area_name="UNKNOWNPLACE", geocoder=mock_geocoder
        )

        assert result.original_lat == 28.6
        assert result.original_lon == 77.2


class TestAreaNameNone:
    """Standard CSV uploads have no CDCMS area name."""

    def test_none_area_skips_retry_uses_depot(self):
        """area_name=None skips area retry, falls through to depot."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON)
        mock_geocoder = _make_geocoder()

        result = v.validate(
            lat=28.6, lon=77.2, area_name=None, geocoder=mock_geocoder
        )

        # No area retry call
        mock_geocoder.geocode.assert_not_called()
        # Should fall through to depot (no dictionary loaded)
        assert result.confidence == 0.1
        assert result.method == "depot"

    def test_none_area_with_dictionary_goes_to_depot(self):
        """area_name=None with dictionary loaded still goes to depot (no area to look up)."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON, dictionary_path=DICTIONARY_PATH)
        mock_geocoder = _make_geocoder()

        result = v.validate(
            lat=28.6, lon=77.2, area_name=None, geocoder=mock_geocoder
        )

        mock_geocoder.geocode.assert_not_called()
        assert result.method == "depot"
        assert result.confidence == 0.1


class TestCircuitBreaker:
    """Circuit breaker: 3 consecutive REQUEST_DENIED trips it."""

    def test_trips_after_3_consecutive_denials(self):
        """Circuit breaker trips after 3 consecutive REQUEST_DENIED."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON)

        v.record_api_denial()
        assert v.is_tripped is False
        v.record_api_denial()
        assert v.is_tripped is False
        v.record_api_denial()
        assert v.is_tripped is True

    def test_resets_on_success(self):
        """Any non-REQUEST_DENIED response resets the counter."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON)

        v.record_api_denial()
        v.record_api_denial()
        # 2 consecutive, then a success
        v.record_api_success()
        # Counter reset
        v.record_api_denial()
        assert v.is_tripped is False

    def test_tripped_skips_geocoder(self):
        """When tripped, validate() skips geocoder calls."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON, dictionary_path=DICTIONARY_PATH)
        mock_geocoder = _make_geocoder(lat=11.63, lon=75.58)

        # Trip the breaker
        v.record_api_denial()
        v.record_api_denial()
        v.record_api_denial()
        assert v.is_tripped is True

        result = v.validate(
            lat=28.6, lon=77.2, area_name="MUTTUNGAL", geocoder=mock_geocoder
        )

        # Geocoder NOT called (circuit breaker active)
        mock_geocoder.geocode.assert_not_called()
        # Falls through to centroid for MUTTUNGAL
        assert result.method == "centroid"
        assert result.confidence == 0.3

    def test_tripped_falls_to_depot_when_no_centroid(self):
        """When tripped and no centroid available, falls to depot."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON, dictionary_path=DICTIONARY_PATH)
        mock_geocoder = _make_geocoder()

        # Trip the breaker
        for _ in range(3):
            v.record_api_denial()

        result = v.validate(
            lat=28.6, lon=77.2, area_name="UNKNOWNPLACE", geocoder=mock_geocoder
        )

        mock_geocoder.geocode.assert_not_called()
        assert result.method == "depot"
        assert result.confidence == 0.1

    def test_request_denied_during_area_retry_recorded(self):
        """REQUEST_DENIED from area-name retry increments circuit breaker."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON, dictionary_path=DICTIONARY_PATH)
        # Mock geocoder returns REQUEST_DENIED
        mock_geocoder = _make_geocoder(
            lat=None, lon=None,
            status="REQUEST_DENIED",
            raw_response={"status": "REQUEST_DENIED"},
        )

        # First validate with out-of-zone coords
        v.validate(lat=28.6, lon=77.2, area_name="SOMEPLACE", geocoder=mock_geocoder)
        # Should have recorded one denial
        v.validate(lat=28.6, lon=77.2, area_name="SOMEPLACE2", geocoder=mock_geocoder)
        v.validate(lat=28.6, lon=77.2, area_name="SOMEPLACE3", geocoder=mock_geocoder)

        # After 3 denials, circuit breaker should be tripped
        assert v.is_tripped is True


class TestCentroidLookup:
    """Centroid loading and lookup from dictionary."""

    def test_exact_match(self):
        """Exact name match returns centroid."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON, dictionary_path=DICTIONARY_PATH)
        result = v.get_centroid("MUTTUNGAL")
        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_case_insensitive(self):
        """Lowercase name matches."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON, dictionary_path=DICTIONARY_PATH)
        result = v.get_centroid("muttungal")
        assert result is not None

    def test_alias_match(self):
        """Alias name returns same centroid as primary."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON, dictionary_path=DICTIONARY_PATH)
        primary = v.get_centroid("VADAKARA")
        alias = v.get_centroid("VATAKARA")
        assert primary is not None
        assert alias is not None
        assert primary == alias

    def test_nonexistent_returns_none(self):
        """Unknown name returns None."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON, dictionary_path=DICTIONARY_PATH)
        result = v.get_centroid("NONEXISTENT")
        assert result is None

    def test_no_dictionary_returns_none(self):
        """Without dictionary loaded, centroid lookup returns None."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON)
        result = v.get_centroid("VADAKARA")
        assert result is None


class TestStatsTracking:
    """Stats tracking across multiple validations."""

    def test_tracks_direct_count(self):
        """Direct in-zone hits are counted."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON)
        mock_geocoder = _make_geocoder()

        v.validate(lat=11.65, lon=75.56, area_name=None, geocoder=mock_geocoder)
        v.validate(lat=11.63, lon=75.58, area_name=None, geocoder=mock_geocoder)

        assert v.stats["direct_count"] == 2

    def test_tracks_area_retry_count(self):
        """Area retry successes are counted."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON, dictionary_path=DICTIONARY_PATH)
        mock_geocoder = _make_geocoder(lat=11.63, lon=75.58)

        v.validate(lat=28.6, lon=77.2, area_name="EDAPPAL", geocoder=mock_geocoder)

        assert v.stats["area_retry_count"] == 1

    def test_tracks_depot_count(self):
        """Depot fallbacks are counted."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON)
        mock_geocoder = _make_geocoder(lat=28.7, lon=77.3)

        v.validate(lat=28.6, lon=77.2, area_name="UNKNOWN", geocoder=mock_geocoder)

        assert v.stats["depot_count"] == 1

    def test_tracks_centroid_count(self):
        """Centroid fallbacks are counted."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON, dictionary_path=DICTIONARY_PATH)
        mock_geocoder = _make_geocoder(lat=28.7, lon=77.3)

        v.validate(lat=28.6, lon=77.2, area_name="MUTTUNGAL", geocoder=mock_geocoder)

        assert v.stats["centroid_count"] == 1

    def test_tracks_circuit_breaker_trips(self):
        """Circuit breaker trips are counted."""
        v = GeocodeValidator(DEPOT_LAT, DEPOT_LON)

        for _ in range(3):
            v.record_api_denial()

        assert v.stats["circuit_breaker_trips"] == 1


class TestValidationResult:
    """ValidationResult dataclass behavior."""

    def test_has_required_fields(self):
        """ValidationResult has all required fields."""
        result = ValidationResult(
            latitude=11.65,
            longitude=75.56,
            confidence=1.0,
            method="direct",
        )
        assert result.latitude == 11.65
        assert result.longitude == 75.56
        assert result.confidence == 1.0
        assert result.method == "direct"
        assert result.original_lat is None
        assert result.original_lon is None

    def test_with_original_coords(self):
        """ValidationResult can store original coordinates."""
        result = ValidationResult(
            latitude=11.65,
            longitude=75.56,
            confidence=0.7,
            method="area_retry",
            original_lat=28.6,
            original_lon=77.2,
        )
        assert result.original_lat == 28.6
        assert result.original_lon == 77.2
