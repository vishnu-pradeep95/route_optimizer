"""Tests for Kerala delivery business configuration.

Verifies that config.py contains correct values for:
- Vehicle specifications (Piaggio Ape Xtra LDX)
- Safety constraints (MVD compliance, speed limits)
- Routing parameters (multipliers, service times)
- Operational bounds (delivery windows, shifts)
- External service URLs

These tests serve as a safety net: if someone accidentally changes a
non-negotiable constant (e.g., the speed limit or safety multiplier),
the test suite will catch it immediately.
"""

import pytest

from apps.kerala_delivery import config


class TestVehicleConfig:
    """Vehicle specification constants."""

    def test_max_weight_kg_is_90_percent_of_rated(self):
        """446 kg = 90% of Piaggio Ape Xtra LDX rated payload (496 kg).

        Using 90% leaves a safety margin for driver + fuel weight variance.
        This is a well-researched value — don't change without vehicle testing.
        """
        assert config.VEHICLE_MAX_WEIGHT_KG == 446.0
        # Verify it really is ~90% of 496
        assert config.VEHICLE_MAX_WEIGHT_KG == pytest.approx(496.0 * 0.9, abs=1.0)

    def test_max_cylinders_reasonable(self):
        """Max cylinders should be 25-35 for Ape Xtra LDX cargo bed."""
        assert 25 <= config.VEHICLE_MAX_CYLINDERS <= 35

    def test_num_vehicles_positive(self):
        """Fleet size must be positive."""
        assert config.NUM_VEHICLES > 0


class TestCylinderWeights:
    """LPG cylinder weight specifications."""

    def test_domestic_cylinder_weight(self):
        """Standard HPCL domestic cylinder = 14.2 kg."""
        assert config.DOMESTIC_CYLINDER_KG == 14.2

    def test_commercial_cylinder_weight(self):
        """Commercial cylinder = 19.0 kg."""
        assert config.COMMERCIAL_CYLINDER_KG == 19.0

    def test_small_cylinder_weight(self):
        """FTL (Free Trade LPG) small cylinder = 5.0 kg."""
        assert config.SMALL_CYLINDER_KG == 5.0

    def test_cylinder_weight_lookup_covers_all_types(self):
        """CYLINDER_WEIGHTS should map all known cylinder type strings."""
        lookup = config.CYLINDER_WEIGHTS
        # Must resolve "domestic" → 14.2
        assert lookup["domestic"] == 14.2
        # Must resolve "commercial" → 19.0
        assert lookup["commercial"] == 19.0
        # Must resolve numeric strings too (CDCMS exports use these)
        assert lookup["14.2"] == 14.2
        assert lookup["19"] == 19.0
        assert lookup["5"] == 5.0

    def test_default_cylinder_is_domestic(self):
        """Default cylinder type should be domestic (most common)."""
        assert config.DEFAULT_CYLINDER_KG == config.DOMESTIC_CYLINDER_KG


class TestSafetyConstraints:
    """Non-negotiable safety and regulatory parameters."""

    def test_speed_limit_40_kmh(self):
        """Urban Kerala speed limit for three-wheelers = 40 km/h.

        This is a Kerala MVD directive. Changing this value would
        violate regulatory compliance. See: design doc Section 5.
        """
        assert config.SPEED_LIMIT_KMH == 40.0

    def test_safety_multiplier_at_least_1_3(self):
        """Travel time safety multiplier must be >= 1.3.

        1.3× accounts for Kerala road conditions, three-wheeler speed,
        and traffic. This creates realistic ETAs and prevents drivers
        from being put under time pressure (MVD concern).
        """
        assert config.SAFETY_MULTIPLIER >= 1.3

    def test_min_delivery_window_at_least_30_minutes(self):
        """Delivery windows must be >= 30 minutes.

        Kerala MVD directive: no "instant" or "10-minute" delivery promises.
        Windows shorter than this are forcibly widened by the API.
        """
        assert config.MIN_DELIVERY_WINDOW_MINUTES >= 30

    def test_gps_accuracy_threshold(self):
        """GPS threshold for discarding inaccurate pings = 50m.

        Pings with worse accuracy are GPS drift, not real positions.
        50m is conservative — can tune down to 30m with real data.
        """
        assert config.GPS_ACCURACY_THRESHOLD_M == 50.0


class TestRoutingConfig:
    """Routing and timing parameters."""

    def test_monsoon_months_june_through_september(self):
        """Monsoon season = June (6) through September (9)."""
        assert config.MONSOON_MONTHS == {6, 7, 8, 9}

    def test_monsoon_multiplier_greater_than_safety(self):
        """Monsoon multiplier (1.5×) should exceed base safety multiplier (1.3×).

        During monsoon, roads flood and travel times increase 30-50%.
        The monsoon multiplier REPLACES (not stacks on top of) the
        base safety multiplier in the upload-and-optimize endpoint.
        """
        assert config.MONSOON_MULTIPLIER > config.SAFETY_MULTIPLIER

    def test_service_time_reasonable(self):
        """Service time at each stop should be 3-10 minutes.

        This is the time for unloading cylinder, getting signature,
        and replacing the empty cylinder. 5 minutes is the default.
        """
        assert 3 <= config.SERVICE_TIME_MINUTES <= 10

    def test_free_delivery_radius(self):
        """Free delivery radius = 5 km (HPCL policy)."""
        assert config.FREE_DELIVERY_RADIUS_KM == 5.0


class TestDepotLocation:
    """Depot (godown) location validation."""

    def test_depot_in_kerala(self):
        """Depot coordinates should be within Kerala's lat/lon bounds.

        Kerala: ~8.2°N to ~12.8°N latitude, ~74.8°E to ~77.4°E longitude.
        """
        depot = config.DEPOT_LOCATION
        assert 8.0 <= depot.latitude <= 13.0, f"Depot lat {depot.latitude} outside Kerala"
        assert 74.0 <= depot.longitude <= 78.0, f"Depot lon {depot.longitude} outside Kerala"

    def test_depot_has_address_text(self):
        """Depot should have a human-readable address for display."""
        assert config.DEPOT_LOCATION.address_text is not None
        assert len(config.DEPOT_LOCATION.address_text) > 0


class TestCoordinateBounds:
    """India-wide coordinate sanity check bounds."""

    def test_india_bounds_cover_full_country(self):
        """Bounds should cover from Kanyakumari to Kashmir, Kutch to Arunachal."""
        lat_min, lat_max, lon_min, lon_max = config.INDIA_COORDINATE_BOUNDS
        # Kanyakumari: ~8.1°N
        assert lat_min <= 8.1
        # Kashmir: ~36.5°N
        assert lat_max >= 36.5
        # Kutch: ~68.5°E
        assert lon_min <= 68.5
        # Arunachal Pradesh: ~97.4°E
        assert lon_max >= 97.4

    def test_india_bounds_exclude_extremes(self):
        """Bounds should not accept coordinates outside India."""
        lat_min, lat_max, lon_min, lon_max = config.INDIA_COORDINATE_BOUNDS
        # Point in Antarctica
        assert not (lat_min <= -85.0 <= lat_max)
        # Point in Pacific Ocean
        assert not (lon_min <= 170.0 <= lon_max)


class TestExternalServiceUrls:
    """Service URL defaults."""

    def test_vroom_url_defaults_to_localhost(self):
        """VROOM URL should default to localhost:3000 for local dev."""
        assert "3000" in config.VROOM_URL


class TestCdcmsConfig:
    """CDCMS preprocessor configuration."""

    def test_area_suffix_includes_kerala(self):
        """CDCMS area suffix should include Kerala for geocoding context.

        CDCMS addresses are bare street names — geocoders need the
        city/state context to resolve them accurately.
        """
        assert "Kerala" in config.CDCMS_AREA_SUFFIX
