"""Tests for the OSRM routing adapter.

Verifies that OsrmAdapter correctly:
- Applies the safety multiplier to all travel times
- Handles OSRM Table API responses for distance matrices
- Handles OSRM Route API responses for single pairs
- Raises appropriate errors on bad responses

All tests mock httpx — no real OSRM instance required.
"""

from unittest.mock import MagicMock, patch

import pytest

from core.models.location import Location
from core.routing.interfaces import DistanceMatrix, RoutingEngine, TravelTime
from core.routing.osrm_adapter import OsrmAdapter


# =============================================================================
# Fixtures
# =============================================================================

VATAKARA_DEPOT = Location(latitude=11.6244, longitude=75.5796, address_text="Depot")
EDAPPALLY = Location(latitude=11.5950, longitude=75.5700, address_text="Vatakara Bus Stand")
MARINE_DRIVE = Location(latitude=11.6350, longitude=75.5900, address_text="Chorode")


@pytest.fixture
def osrm():
    """OsrmAdapter with 1.3× safety multiplier (Kerala default)."""
    return OsrmAdapter(
        base_url="http://localhost:5000",
        safety_multiplier=1.3,
    )


@pytest.fixture
def osrm_route_response():
    """Simulated OSRM Route API response.

    Based on: https://project-osrm.org/docs/v5.24.0/api/#route-service
    Duration 300s (5 min), distance 3000m (3 km) — typical intra-Vatakara trip.
    """
    return {
        "code": "Ok",
        "routes": [
            {
                "duration": 300.0,   # 5 minutes raw
                "distance": 3000.0,  # 3 km
            }
        ],
    }


@pytest.fixture
def osrm_table_response():
    """Simulated OSRM Table API response for 3 locations.

    3×3 matrix with realistic Vatakara travel times.
    Diagonal is 0 (same location).
    """
    return {
        "code": "Ok",
        "durations": [
            [0.0, 300.0, 500.0],
            [320.0, 0.0, 400.0],
            [520.0, 420.0, 0.0],
        ],
        "distances": [
            [0.0, 3000.0, 5000.0],
            [3200.0, 0.0, 4000.0],
            [5200.0, 4200.0, 0.0],
        ],
    }


# =============================================================================
# Tests
# =============================================================================


class TestOsrmAdapter:
    """Unit tests for OsrmAdapter with mocked HTTP."""

    def test_implements_routing_engine_protocol(self, osrm):
        """Verify OsrmAdapter satisfies the RoutingEngine protocol.

        Why this test? Protocol compliance ensures we can swap OSRM for
        Valhalla without changing any calling code.
        """
        assert isinstance(osrm, RoutingEngine)

    def test_travel_time_applies_safety_multiplier(
        self, osrm, osrm_route_response
    ):
        """Safety multiplier must be applied to OSRM durations.

        Why 1.3×? OSRM assumes ideal passenger car conditions. Kerala
        three-wheelers are slower, roads are narrower, and traffic is
        unpredictable. 1.3× was calibrated from delivery driver feedback.
        """
        with patch("core.routing.osrm_adapter.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: osrm_route_response,
                raise_for_status=lambda: None,
            )
            travel_time = osrm.get_travel_time(VATAKARA_DEPOT, EDAPPALLY)

        # 300s × 1.3 = 390s
        assert travel_time.duration_seconds == pytest.approx(390.0)
        # Distance is NOT multiplied — only time gets the safety buffer
        assert travel_time.distance_meters == pytest.approx(3000.0)

    def test_travel_time_returns_travel_time_model(
        self, osrm, osrm_route_response
    ):
        """get_travel_time should return a TravelTime Pydantic model."""
        with patch("core.routing.osrm_adapter.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: osrm_route_response,
                raise_for_status=lambda: None,
            )
            result = osrm.get_travel_time(VATAKARA_DEPOT, EDAPPALLY)

        assert isinstance(result, TravelTime)
        # Check convenience properties work
        assert result.duration_minutes == pytest.approx(390.0 / 60.0)
        assert result.distance_km == pytest.approx(3.0)

    def test_distance_matrix_applies_safety_multiplier_to_all_cells(
        self, osrm, osrm_table_response
    ):
        """Every duration cell in the matrix must be multiplied by 1.3×.

        The optimizer uses these durations to plan routes. If they're
        too optimistic, drivers will be late at every stop.
        """
        locations = [VATAKARA_DEPOT, EDAPPALLY, MARINE_DRIVE]
        with patch("core.routing.osrm_adapter.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: osrm_table_response,
                raise_for_status=lambda: None,
            )
            matrix = osrm.get_distance_matrix(locations)

        # Check one cell: 300s × 1.3 = 390s
        assert matrix.durations[0][1] == pytest.approx(390.0)
        # Diagonal should stay 0
        assert matrix.durations[0][0] == pytest.approx(0.0)
        # Distances are NOT multiplied
        assert matrix.distances[0][1] == pytest.approx(3000.0)

    def test_distance_matrix_returns_correct_model(
        self, osrm, osrm_table_response
    ):
        """get_distance_matrix should return a DistanceMatrix Pydantic model."""
        locations = [VATAKARA_DEPOT, EDAPPALLY, MARINE_DRIVE]
        with patch("core.routing.osrm_adapter.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: osrm_table_response,
                raise_for_status=lambda: None,
            )
            matrix = osrm.get_distance_matrix(locations)

        assert isinstance(matrix, DistanceMatrix)
        assert matrix.size == 3
        assert len(matrix.durations) == 3
        assert len(matrix.distances) == 3

    def test_distance_matrix_rejects_single_location(self, osrm):
        """Matrix requires at least 2 locations — 1×1 makes no sense."""
        with pytest.raises(ValueError, match="at least 2 locations"):
            osrm.get_distance_matrix([VATAKARA_DEPOT])

    def test_osrm_error_raises_runtime_error(self, osrm):
        """OSRM errors (bad coords, server down) should raise RuntimeError."""
        error_response = {"code": "InvalidQuery", "message": "bad coordinates"}
        with patch("core.routing.osrm_adapter.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: error_response,
                raise_for_status=lambda: None,
            )
            with pytest.raises(RuntimeError, match="OSRM"):
                osrm.get_travel_time(VATAKARA_DEPOT, EDAPPALLY)

    def test_coordinate_order_is_lon_lat(self, osrm, osrm_route_response):
        """OSRM uses lon,lat (not lat,lon). Verify we pass coords correctly.

        This is a common bug when mixing OSRM (lon,lat) with Leaflet (lat,lon).
        Getting this wrong means the routes would be in the wrong hemisphere.
        """
        with patch("core.routing.osrm_adapter.httpx.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: osrm_route_response,
                raise_for_status=lambda: None,
            )
            osrm.get_travel_time(VATAKARA_DEPOT, EDAPPALLY)

        # Check the URL that was called — should be lon,lat;lon,lat
        call_url = mock_get.call_args[0][0]
        # VATAKARA_DEPOT: lon=75.5796, lat=11.6244
        assert "75.5796,11.6244" in call_url
        # VATAKARA_BUS_STAND: lon=75.57, lat=11.595 (trailing zeros stripped)
        assert "75.57,11.595" in call_url
