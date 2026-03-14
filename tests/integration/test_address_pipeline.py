"""Integration tests for the v2.2 address preprocessing pipeline.

Verifies the complete address pipeline end-to-end with real CDCMS data
and mock geocoding. Covers:

- TEST-01: All CDCMS addresses processed through cleaning + validation
  pipeline without errors, each either geocodes within 20km of depot
  or is flagged with location_approximate: true.
- TEST-02: The HDFC ERGO bug scenario is explicitly tested: out-of-zone
  Google result falls to centroid/depot, never silently used.

All geocoding is mocked -- no live Google API calls. The Google Maps API
key is currently invalid (REQUEST_DENIED), and these tests verify pipeline
logic, not geocoding accuracy.

Test data source: data/sample_cdcms_export.csv (27 real CDCMS addresses
across 9 distinct area names in the Vatakara delivery zone).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.data_import.cdcms_preprocessor import clean_cdcms_address, preprocess_cdcms
from core.geocoding.interfaces import GeocodingResult
from core.geocoding.validator import GeocodeValidator
from core.models.location import Location

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEPOT_LAT = 11.6244
DEPOT_LON = 75.5796
DICTIONARY_PATH = "data/place_names_vatakara.json"
SAMPLE_CSV = "data/sample_cdcms_export.csv"
AREA_SUFFIX = ", Vatakara, Kozhikode, Kerala"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_area_geocoder(dictionary_path: str) -> MagicMock:
    """Create a mock geocoder that returns dictionary centroids for known areas.

    Loads the place name dictionary and builds a lookup table. When
    ``geocode(address)`` is called, it searches for known area names in
    the address text and returns the centroid coordinates. For addresses
    that don't match any known area, returns out-of-zone coordinates
    (Delhi: 28.6, 77.2) to simulate a bad Google geocoding result.

    Args:
        dictionary_path: Path to place_names_vatakara.json.

    Returns:
        MagicMock with ``geocode`` side_effect returning GeocodingResult.
    """
    with open(dictionary_path) as f:
        data = json.load(f)

    centroids: dict[str, tuple[float, float]] = {}
    for entry in data["entries"]:
        name = entry["name"].upper()
        lat, lon = entry.get("lat"), entry.get("lon")
        if lat is not None and lon is not None:
            centroids[name] = (lat, lon)
            for alias in entry.get("aliases", []):
                centroids[alias.upper()] = (lat, lon)

    def geocode_fn(address: str) -> GeocodingResult:
        addr_upper = address.upper()
        for name, (lat, lon) in centroids.items():
            if name in addr_upper:
                return GeocodingResult(
                    location=Location(latitude=lat, longitude=lon),
                    confidence=0.8,
                    formatted_address=f"Mock: {name}",
                    raw_response={"status": "OK"},
                )
        # Default: out-of-zone (Delhi) to trigger fallback
        return GeocodingResult(
            location=Location(latitude=28.6, longitude=77.2),
            confidence=0.5,
            formatted_address="Mock: Unknown Area (Delhi)",
            raw_response={"status": "OK"},
        )

    mock = MagicMock()
    mock.geocode.side_effect = geocode_fn
    return mock


def _make_out_of_zone_geocoder(
    lat: float = 11.26, lon: float = 75.78
) -> MagicMock:
    """Create a mock geocoder that always returns out-of-zone coordinates.

    Defaults to Kozhikode coordinates (~40km from Vatakara depot),
    simulating the exact HDFC ERGO bug where Google matched an address
    to a business listing far from the delivery zone.

    Args:
        lat: Latitude to return (default: Kozhikode).
        lon: Longitude to return (default: Kozhikode).

    Returns:
        MagicMock with ``geocode`` returning out-of-zone GeocodingResult.
    """
    mock = MagicMock()
    result = GeocodingResult(
        location=Location(latitude=lat, longitude=lon),
        confidence=0.8,
        formatted_address="Mock: Out of Zone (Kozhikode)",
        raw_response={"status": "OK"},
    )
    mock.geocode.return_value = result
    return mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def cdcms_df():
    """Load and preprocess the real CDCMS sample CSV (read-only, shared).

    Returns a DataFrame with columns: order_id, address, quantity,
    area_name, delivery_man, address_original.
    """
    return preprocess_cdcms(SAMPLE_CSV, area_suffix=AREA_SUFFIX)


@pytest.fixture()
def validator():
    """Create a fresh GeocodeValidator for each test.

    Fresh instance ensures stats are reset between tests.
    """
    return GeocodeValidator(
        depot_lat=DEPOT_LAT,
        depot_lon=DEPOT_LON,
        dictionary_path=DICTIONARY_PATH,
    )


# ---------------------------------------------------------------------------
# TEST-01: Full pipeline integration tests
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """TEST-01: All CDCMS addresses processed through the pipeline correctly.

    Verifies that every address from sample_cdcms_export.csv can be:
    1. Loaded via preprocess_cdcms (no parsing errors)
    2. Cleaned via clean_cdcms_address (readable output)
    3. Validated via GeocodeValidator (in-zone or flagged approximate)
    """

    def test_all_cdcms_addresses_processed(self, cdcms_df):
        """All rows from sample_cdcms_export.csv are loaded with valid fields."""
        assert len(cdcms_df) > 0, "No rows loaded from CDCMS CSV"

        for idx, row in cdcms_df.iterrows():
            assert row["address"], f"Row {idx}: empty address"
            assert row["area_name"], f"Row {idx}: empty area_name"
            assert row["order_id"], f"Row {idx}: empty order_id"

    def test_address_cleaning_produces_readable_output(self, cdcms_df):
        """Every cleaned address is longer than 10 chars and has area suffix."""
        for idx, row in cdcms_df.iterrows():
            cleaned = row["address"]
            assert len(cleaned) > 10, (
                f"Row {idx}: cleaned address too short ({len(cleaned)} chars): "
                f"{cleaned!r}"
            )
            assert "Vatakara" in cleaned, (
                f"Row {idx}: area suffix missing from cleaned address: "
                f"{cleaned!r}"
            )

    def test_all_addresses_in_zone_or_flagged_approximate(
        self, cdcms_df, validator
    ):
        """Every address geocodes within 20km of depot or gets confidence < 0.5.

        Uses a mock geocoder that returns dictionary centroids for known
        area names. Out-of-zone results trigger the validator's fallback
        chain (area_retry -> centroid -> depot).

        For each address, either:
          (a) validator.is_in_zone is True (direct hit), or
          (b) confidence < 0.5 (location_approximate: true in the API)
        """
        geocoder = _make_area_geocoder(DICTIONARY_PATH)

        for idx, row in cdcms_df.iterrows():
            # Simulate initial geocoding with the area-aware geocoder
            area_name = row["area_name"]
            geo_result = geocoder.geocode(row["address"])

            if geo_result.location is None:
                # Failed geocode -- validator will use depot fallback
                lat, lon = DEPOT_LAT, DEPOT_LON
            else:
                lat = geo_result.location.latitude
                lon = geo_result.location.longitude

            result = validator.validate(
                lat=lat,
                lon=lon,
                area_name=area_name,
                geocoder=geocoder,
            )

            in_zone = validator.is_in_zone(result.latitude, result.longitude)
            is_approximate = result.confidence < 0.5

            assert in_zone or is_approximate, (
                f"Row {idx} (order {row['order_id']}, area {area_name}): "
                f"method={result.method}, confidence={result.confidence}, "
                f"in_zone={in_zone} -- must be in-zone or approximate"
            )

    def test_validator_stats_cover_all_methods(self, cdcms_df, validator):
        """After processing all addresses, validator.stats has direct_count > 0."""
        geocoder = _make_area_geocoder(DICTIONARY_PATH)

        for _, row in cdcms_df.iterrows():
            geo_result = geocoder.geocode(row["address"])
            if geo_result.location is None:
                lat, lon = DEPOT_LAT, DEPOT_LON
            else:
                lat = geo_result.location.latitude
                lon = geo_result.location.longitude

            validator.validate(
                lat=lat,
                lon=lon,
                area_name=row["area_name"],
                geocoder=geocoder,
            )

        stats = validator.stats
        assert stats["direct_count"] > 0, (
            f"Expected at least one direct hit. Stats: {stats}"
        )

    def test_dictionary_covers_all_area_names(self, cdcms_df, validator):
        """Every distinct area_name in the CDCMS data has a centroid in the dictionary."""
        area_names = cdcms_df["area_name"].unique()
        assert len(area_names) == 9, (
            f"Expected 9 distinct area names, got {len(area_names)}: "
            f"{sorted(area_names)}"
        )

        missing = []
        for name in area_names:
            centroid = validator.get_centroid(name)
            if centroid is None:
                missing.append(name)

        assert not missing, (
            f"Dictionary missing centroids for: {missing}. "
            f"These CDCMS area names have no fallback centroid."
        )


# ---------------------------------------------------------------------------
# TEST-02: HDFC ERGO regression tests
# ---------------------------------------------------------------------------


class TestHdfcErgoBug:
    """TEST-02: HDFC ERGO out-of-zone geocode bug is fixed.

    The HDFC ERGO bug: a CDCMS address geocoded to "HDFC ERGO Insurance
    Agent, Palayam, Kozhikode" (~40km from depot) because Google matched
    a landmark or business name in the address text to a commercial listing
    far away. The fix: the validator detects out-of-zone results, triggers
    the fallback chain, and returns in-zone coordinates with
    location_approximate: true (confidence < 0.5).
    """

    def test_address_cleaning_handles_concatenated_text(self):
        """CDCMS concatenated address is cleaned to readable text with suffix.

        Uses the real CDCMS address from row 3 (0-indexed row 2):
        "8/542SREESHYLAMMUTTUNGAL-POBALAVADI" -- a heavily concatenated
        address with no spaces between house number and house name.
        """
        raw = "8/542SREESHYLAMMUTTUNGAL-POBALAVADI"
        cleaned = clean_cdcms_address(raw, area_suffix=AREA_SUFFIX)

        # Must be readable (not empty or truncated)
        assert len(cleaned) > 10, (
            f"Cleaned address too short: {cleaned!r}"
        )
        # Must contain area suffix
        assert "Vatakara" in cleaned, (
            f"Area suffix missing from cleaned address: {cleaned!r}"
        )

    def test_out_of_zone_geocode_triggers_fallback(self, validator):
        """Out-of-zone geocode (Kozhikode, ~40km) triggers fallback chain.

        Simulates the HDFC ERGO bug: Google returns coordinates ~40km from
        depot. The validator must NOT silently accept these. It must fall
        back to area_retry, centroid, or depot -- never use 'direct'.
        """
        # Kozhikode coordinates (~40km from Vatakara depot)
        out_of_zone_geocoder = _make_out_of_zone_geocoder(lat=11.26, lon=75.78)

        result = validator.validate(
            lat=11.26,
            lon=75.78,
            area_name="VALLIKKADU",
            geocoder=out_of_zone_geocoder,
        )

        assert result.method != "direct", (
            f"Out-of-zone coordinates silently accepted as 'direct'. "
            f"Expected fallback to area_retry/centroid/depot. "
            f"Got method={result.method}, confidence={result.confidence}"
        )
        assert result.method in ("area_retry", "centroid", "depot"), (
            f"Unexpected fallback method: {result.method}"
        )
        assert result.confidence < 1.0, (
            f"Fallback result should have confidence < 1.0, "
            f"got {result.confidence}"
        )

    def test_fallback_produces_in_zone_coordinates(self, validator):
        """Fallback chain returns coordinates within 20km of depot.

        After detecting out-of-zone, the validator falls through to
        centroid or depot -- both of which are guaranteed in-zone.
        """
        out_of_zone_geocoder = _make_out_of_zone_geocoder(lat=11.26, lon=75.78)

        result = validator.validate(
            lat=11.26,
            lon=75.78,
            area_name="VALLIKKADU",
            geocoder=out_of_zone_geocoder,
        )

        assert validator.is_in_zone(result.latitude, result.longitude), (
            f"Fallback coordinates ({result.latitude}, {result.longitude}) "
            f"are NOT within 20km of depot. Method: {result.method}"
        )

    def test_location_approximate_flag_for_centroid(self, validator):
        """Centroid fallback (confidence=0.3) maps to location_approximate: true.

        When the validator falls back to centroid, confidence is 0.3.
        The API maps confidence < 0.5 to location_approximate: true,
        warning the driver that the pin may not be exact.
        """
        out_of_zone_geocoder = _make_out_of_zone_geocoder(lat=11.26, lon=75.78)

        result = validator.validate(
            lat=11.26,
            lon=75.78,
            area_name="VALLIKKADU",
            geocoder=out_of_zone_geocoder,
        )

        # The out-of-zone geocoder returns out-of-zone for area retry too,
        # so the validator should fall through to centroid (confidence 0.3)
        # or depot (confidence 0.1). Both have confidence < 0.5.
        assert result.confidence < 0.5, (
            f"Expected confidence < 0.5 (location_approximate: true), "
            f"got {result.confidence} via method={result.method}"
        )
