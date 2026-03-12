"""Tests for GeocodingResult.method field and related model/config changes.

Phase 13 Plan 02 Task 1: Verifies that:
- GeocodingResult has a method field defaulting to "direct"
- GeocodingResult accepts any string method value
- OrderDB has geocode_method column (String(20), nullable)
- config.GEOCODE_ZONE_RADIUS_KM == 30
"""

import pytest

from core.geocoding.interfaces import GeocodingResult


class TestGeocodingResultMethod:
    """Verify the method field on GeocodingResult."""

    def test_method_defaults_to_direct(self):
        """Default method should be 'direct' for normal geocode results."""
        result = GeocodingResult()
        assert result.method == "direct"

    def test_method_accepts_area_retry(self):
        """Method should accept 'area_retry' for area-name retry results."""
        result = GeocodingResult(method="area_retry")
        assert result.method == "area_retry"

    def test_method_accepts_centroid(self):
        """Method should accept 'centroid' for dictionary centroid fallback."""
        result = GeocodingResult(method="centroid")
        assert result.method == "centroid"

    def test_method_accepts_depot(self):
        """Method should accept 'depot' for depot fallback."""
        result = GeocodingResult(method="depot")
        assert result.method == "depot"

    def test_method_accepts_arbitrary_string(self):
        """Method is a plain string, not an enum -- any value accepted."""
        result = GeocodingResult(method="some_custom_value")
        assert result.method == "some_custom_value"

    def test_method_present_in_model_fields(self):
        """Method should be a declared field, not a dynamic attribute."""
        assert "method" in GeocodingResult.model_fields


class TestOrderDBGeocodMethod:
    """Verify OrderDB has geocode_method column."""

    def test_orderdb_has_geocode_method_column(self):
        """OrderDB should have geocode_method as a mapped column."""
        from core.database.models import OrderDB

        # Check the column exists in the table metadata
        columns = OrderDB.__table__.columns
        assert "geocode_method" in columns
        col = columns["geocode_method"]
        assert col.nullable is True
        assert str(col.type) == "VARCHAR(20)"


class TestGeocodZoneRadiusConfig:
    """Verify GEOCODE_ZONE_RADIUS_KM config constant."""

    def test_zone_radius_exists(self):
        """Config should export GEOCODE_ZONE_RADIUS_KM."""
        from apps.kerala_delivery.config import GEOCODE_ZONE_RADIUS_KM

        assert GEOCODE_ZONE_RADIUS_KM == 30

    def test_zone_radius_is_numeric(self):
        """Zone radius should be a number (int or float)."""
        from apps.kerala_delivery.config import GEOCODE_ZONE_RADIUS_KM

        assert isinstance(GEOCODE_ZONE_RADIUS_KM, (int, float))
