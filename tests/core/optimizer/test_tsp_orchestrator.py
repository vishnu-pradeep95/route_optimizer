"""Tests for per-driver TSP orchestration module.

Verifies that the tsp_orchestrator correctly:
- Groups orders by driver name using an order-driver map
- Excludes unmapped orders from grouping
- Calls VroomAdapter.optimize once per driver with uncapped capacity
- Merges per-driver results into a single RouteAssignment
- Sets route_id format as R-{assignment_id}-{driver_name}
- Sets vehicle_id AND driver_name to driver name on each Route
- Handles partial failure (one driver VROOM call fails) gracefully
- Skips drivers with 0 orders
- Validates no order overlap across routes
- Detects geographic anomalies via convex hull overlap

All tests mock VroomAdapter -- no real VROOM server required.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from core.models.location import Location
from core.models.order import Order
from core.models.route import Route, RouteAssignment, RouteStop
from core.models.vehicle import Vehicle
from core.optimizer.tsp_orchestrator import (
    detect_geographic_anomalies,
    group_orders_by_driver,
    optimize_per_driver,
    validate_no_overlap,
)


# =============================================================================
# Fixtures
# =============================================================================

DEPOT = Location(latitude=11.6244, longitude=75.5796, address_text="Depot")


def _make_order(order_id: str, lat: float = 11.60, lon: float = 75.57) -> Order:
    """Create a test order with given ID and coordinates."""
    return Order(
        order_id=order_id,
        location=Location(latitude=lat, longitude=lon),
        address_raw=f"Address for {order_id}",
        customer_ref=f"CUST-{order_id}",
        weight_kg=14.2,
        quantity=1,
    )


def _make_stop(order_id: str, sequence: int, lat: float = 11.60, lon: float = 75.57) -> RouteStop:
    """Create a test RouteStop."""
    return RouteStop(
        order_id=order_id,
        location=Location(latitude=lat, longitude=lon),
        sequence=sequence,
        weight_kg=14.2,
        quantity=1,
    )


def _make_route(
    vehicle_id: str,
    stops: list[RouteStop],
    route_id: str = "R-test-route",
) -> Route:
    """Create a test Route."""
    return Route(
        route_id=route_id,
        vehicle_id=vehicle_id,
        driver_name=vehicle_id,
        stops=stops,
        total_distance_km=10.0,
        total_duration_minutes=30.0,
        total_weight_kg=sum(s.weight_kg for s in stops),
        total_items=sum(s.quantity for s in stops),
    )


# =============================================================================
# group_orders_by_driver tests
# =============================================================================


class TestGroupOrdersByDriver:
    """Tests for group_orders_by_driver function."""

    def test_groups_orders_by_driver_name(self):
        """Orders are correctly grouped by their assigned driver."""
        orders = [_make_order("ORD-001"), _make_order("ORD-002"), _make_order("ORD-003")]
        order_driver_map = {
            "ORD-001": "Suresh Kumar",
            "ORD-002": "Suresh Kumar",
            "ORD-003": "Anil P",
        }

        result = group_orders_by_driver(orders, order_driver_map)

        assert len(result) == 2
        assert len(result["Suresh Kumar"]) == 2
        assert len(result["Anil P"]) == 1
        assert result["Suresh Kumar"][0].order_id == "ORD-001"
        assert result["Suresh Kumar"][1].order_id == "ORD-002"
        assert result["Anil P"][0].order_id == "ORD-003"

    def test_excludes_orders_with_no_driver_mapping(self):
        """Orders not in the order_driver_map are excluded from results."""
        orders = [_make_order("ORD-001"), _make_order("ORD-002"), _make_order("ORD-003")]
        order_driver_map = {
            "ORD-001": "Suresh Kumar",
            # ORD-002 has no mapping
            "ORD-003": "Anil P",
        }

        result = group_orders_by_driver(orders, order_driver_map)

        assert len(result) == 2
        all_order_ids = [o.order_id for group in result.values() for o in group]
        assert "ORD-002" not in all_order_ids

    def test_empty_orders_returns_empty_dict(self):
        """Empty orders list produces empty grouping."""
        result = group_orders_by_driver([], {"ORD-001": "Suresh Kumar"})
        assert result == {}

    def test_empty_map_returns_empty_dict(self):
        """Empty order_driver_map excludes all orders."""
        orders = [_make_order("ORD-001")]
        result = group_orders_by_driver(orders, {})
        assert result == {}


# =============================================================================
# optimize_per_driver tests
# =============================================================================


class TestOptimizePerDriver:
    """Tests for optimize_per_driver function."""

    def test_calls_optimizer_once_per_driver(self):
        """VroomAdapter.optimize is called once per driver group."""
        mock_optimizer = MagicMock()
        mock_optimizer.optimize.return_value = RouteAssignment(
            assignment_id="mock",
            routes=[],
            unassigned_order_ids=[],
            optimization_time_ms=5.0,
        )

        orders_by_driver = {
            "Suresh Kumar": [_make_order("ORD-001")],
            "Anil P": [_make_order("ORD-002")],
        }

        result, warnings = optimize_per_driver(
            orders_by_driver=orders_by_driver,
            driver_uuids={},
            depot=DEPOT,
            optimizer=mock_optimizer,
        )

        assert mock_optimizer.optimize.call_count == 2

    def test_vehicle_has_uncapped_capacity(self):
        """Each per-driver Vehicle has uncapped capacity (99999 kg, 999 items)."""
        mock_optimizer = MagicMock()
        mock_optimizer.optimize.return_value = RouteAssignment(
            assignment_id="mock",
            routes=[],
            unassigned_order_ids=[],
            optimization_time_ms=5.0,
        )

        orders_by_driver = {"Suresh Kumar": [_make_order("ORD-001")]}

        optimize_per_driver(
            orders_by_driver=orders_by_driver,
            driver_uuids={},
            depot=DEPOT,
            optimizer=mock_optimizer,
        )

        call_args = mock_optimizer.optimize.call_args
        vehicles = call_args[0][1]  # second positional arg
        assert len(vehicles) == 1
        assert vehicles[0].max_weight_kg == 99999.0
        assert vehicles[0].max_items == 999
        assert vehicles[0].depot == DEPOT

    def test_merges_results_into_single_assignment(self):
        """All per-driver routes merge into one RouteAssignment with one assignment_id."""
        mock_optimizer = MagicMock()
        # Return different routes for each driver
        route_suresh = _make_route(
            "Suresh Kumar",
            [_make_stop("ORD-001", 1)],
            route_id="R-temp-Suresh Kumar",
        )
        route_anil = _make_route(
            "Anil P",
            [_make_stop("ORD-002", 1)],
            route_id="R-temp-Anil P",
        )

        mock_optimizer.optimize.side_effect = [
            RouteAssignment(
                assignment_id="a1",
                routes=[route_suresh],
                unassigned_order_ids=[],
                optimization_time_ms=5.0,
            ),
            RouteAssignment(
                assignment_id="a2",
                routes=[route_anil],
                unassigned_order_ids=[],
                optimization_time_ms=3.0,
            ),
        ]

        orders_by_driver = {
            "Suresh Kumar": [_make_order("ORD-001")],
            "Anil P": [_make_order("ORD-002")],
        }

        result, warnings = optimize_per_driver(
            orders_by_driver=orders_by_driver,
            driver_uuids={},
            depot=DEPOT,
            optimizer=mock_optimizer,
        )

        # Single assignment with both routes
        assert len(result.routes) == 2
        # Total optimization time is summed
        assert result.optimization_time_ms == 8.0

    def test_route_id_format(self):
        """Route IDs follow the R-{assignment_id}-{driver_name} format."""
        mock_optimizer = MagicMock()
        route = _make_route(
            "Suresh Kumar",
            [_make_stop("ORD-001", 1)],
        )
        mock_optimizer.optimize.return_value = RouteAssignment(
            assignment_id="temp",
            routes=[route],
            unassigned_order_ids=[],
            optimization_time_ms=5.0,
        )

        orders_by_driver = {"Suresh Kumar": [_make_order("ORD-001")]}

        result, warnings = optimize_per_driver(
            orders_by_driver=orders_by_driver,
            driver_uuids={},
            depot=DEPOT,
            optimizer=mock_optimizer,
        )

        route_id = result.routes[0].route_id
        assert route_id.startswith("R-")
        assert route_id.endswith("-Suresh Kumar")
        # Extract assignment_id (middle part)
        parts = route_id.split("-", 2)
        assert len(parts[1]) == 8  # short UUID

    def test_vehicle_id_and_driver_name_set_to_driver_name(self):
        """Both vehicle_id and driver_name on each Route contain the driver name."""
        mock_optimizer = MagicMock()
        route = _make_route(
            "Suresh Kumar",
            [_make_stop("ORD-001", 1)],
        )
        mock_optimizer.optimize.return_value = RouteAssignment(
            assignment_id="temp",
            routes=[route],
            unassigned_order_ids=[],
            optimization_time_ms=5.0,
        )

        orders_by_driver = {"Suresh Kumar": [_make_order("ORD-001")]}

        result, warnings = optimize_per_driver(
            orders_by_driver=orders_by_driver,
            driver_uuids={},
            depot=DEPOT,
            optimizer=mock_optimizer,
        )

        assert result.routes[0].vehicle_id == "Suresh Kumar"
        assert result.routes[0].driver_name == "Suresh Kumar"

    def test_handles_partial_failure(self):
        """When one driver's VROOM call fails, other drivers still get routes."""
        mock_optimizer = MagicMock()
        route_anil = _make_route(
            "Anil P",
            [_make_stop("ORD-002", 1)],
        )

        # First call fails, second succeeds
        mock_optimizer.optimize.side_effect = [
            Exception("VROOM connection error"),
            RouteAssignment(
                assignment_id="a2",
                routes=[route_anil],
                unassigned_order_ids=[],
                optimization_time_ms=3.0,
            ),
        ]

        orders_by_driver = {
            "Suresh Kumar": [_make_order("ORD-001")],
            "Anil P": [_make_order("ORD-002")],
        }

        result, warnings = optimize_per_driver(
            orders_by_driver=orders_by_driver,
            driver_uuids={},
            depot=DEPOT,
            optimizer=mock_optimizer,
        )

        # Only Anil P's route succeeded
        assert len(result.routes) == 1
        assert result.routes[0].vehicle_id == "Anil P"
        # Suresh's order is unassigned
        assert "ORD-001" in result.unassigned_order_ids
        # Warning about the failure
        assert len(warnings) >= 1
        assert "Suresh Kumar" in warnings[0]

    def test_skips_drivers_with_zero_orders(self):
        """Drivers with empty order lists are skipped (no VROOM call)."""
        mock_optimizer = MagicMock()
        mock_optimizer.optimize.return_value = RouteAssignment(
            assignment_id="mock",
            routes=[],
            unassigned_order_ids=[],
            optimization_time_ms=5.0,
        )

        orders_by_driver = {
            "Suresh Kumar": [_make_order("ORD-001")],
            "Empty Driver": [],  # No orders
        }

        result, warnings = optimize_per_driver(
            orders_by_driver=orders_by_driver,
            driver_uuids={},
            depot=DEPOT,
            optimizer=mock_optimizer,
        )

        # Only one call (for Suresh, not for Empty Driver)
        assert mock_optimizer.optimize.call_count == 1


# =============================================================================
# validate_no_overlap tests
# =============================================================================


class TestValidateNoOverlap:
    """Tests for validate_no_overlap function."""

    def test_no_overlap_returns_empty_list(self):
        """When no orders overlap between routes, returns empty error list."""
        assignment = RouteAssignment(
            assignment_id="test",
            routes=[
                _make_route("Suresh Kumar", [_make_stop("ORD-001", 1), _make_stop("ORD-002", 2)]),
                _make_route("Anil P", [_make_stop("ORD-003", 1), _make_stop("ORD-004", 2)]),
            ],
        )

        errors = validate_no_overlap(assignment)
        assert errors == []

    def test_detects_overlap(self):
        """Detects when an order appears in two routes."""
        assignment = RouteAssignment(
            assignment_id="test",
            routes=[
                _make_route("Suresh Kumar", [_make_stop("ORD-001", 1), _make_stop("ORD-002", 2)]),
                _make_route("Anil P", [_make_stop("ORD-002", 1), _make_stop("ORD-003", 2)]),
            ],
        )

        errors = validate_no_overlap(assignment)

        assert len(errors) == 1
        assert "ORD-002" in errors[0]
        assert "Suresh Kumar" in errors[0]
        assert "Anil P" in errors[0]


# =============================================================================
# detect_geographic_anomalies tests
# =============================================================================


class TestDetectGeographicAnomalies:
    """Tests for detect_geographic_anomalies function."""

    def test_no_overlap_returns_empty(self):
        """Non-overlapping delivery areas produce no warnings."""
        # Driver A: stops in north area
        stops_a = [
            _make_stop("ORD-001", 1, lat=11.70, lon=75.50),
            _make_stop("ORD-002", 2, lat=11.72, lon=75.52),
            _make_stop("ORD-003", 3, lat=11.71, lon=75.54),
        ]
        # Driver B: stops in south area (well separated)
        stops_b = [
            _make_stop("ORD-004", 1, lat=11.50, lon=75.50),
            _make_stop("ORD-005", 2, lat=11.52, lon=75.52),
            _make_stop("ORD-006", 3, lat=11.51, lon=75.54),
        ]

        assignment = RouteAssignment(
            assignment_id="test",
            routes=[
                _make_route("Suresh Kumar", stops_a),
                _make_route("Anil P", stops_b),
            ],
        )

        warnings = detect_geographic_anomalies(assignment)
        assert warnings == []

    def test_flags_significant_overlap(self):
        """Flags >30% overlap with warning naming both drivers and percentage."""
        # Driver A: large area
        stops_a = [
            _make_stop("ORD-001", 1, lat=11.60, lon=75.50),
            _make_stop("ORD-002", 2, lat=11.60, lon=75.60),
            _make_stop("ORD-003", 3, lat=11.70, lon=75.55),
        ]
        # Driver B: mostly inside A's area
        stops_b = [
            _make_stop("ORD-004", 1, lat=11.62, lon=75.52),
            _make_stop("ORD-005", 2, lat=11.62, lon=75.58),
            _make_stop("ORD-006", 3, lat=11.67, lon=75.55),
        ]

        assignment = RouteAssignment(
            assignment_id="test",
            routes=[
                _make_route("Suresh Kumar", stops_a),
                _make_route("Anil P", stops_b),
            ],
        )

        warnings = detect_geographic_anomalies(assignment)

        assert len(warnings) == 1
        assert "Suresh Kumar" in warnings[0]
        assert "Anil P" in warnings[0]
        assert "%" in warnings[0]
        assert "consider reassigning orders in CDCMS" in warnings[0]

    def test_skips_drivers_with_fewer_than_3_stops(self):
        """Drivers with <3 stops are skipped for hull computation."""
        stops_a = [
            _make_stop("ORD-001", 1, lat=11.60, lon=75.50),
            _make_stop("ORD-002", 2, lat=11.60, lon=75.60),
            _make_stop("ORD-003", 3, lat=11.70, lon=75.55),
        ]
        # Driver B: only 2 stops (no hull possible)
        stops_b = [
            _make_stop("ORD-004", 1, lat=11.62, lon=75.52),
            _make_stop("ORD-005", 2, lat=11.62, lon=75.58),
        ]

        assignment = RouteAssignment(
            assignment_id="test",
            routes=[
                _make_route("Suresh Kumar", stops_a),
                _make_route("Anil P", stops_b),
            ],
        )

        warnings = detect_geographic_anomalies(assignment)
        # No warnings because only 1 driver has enough stops for a hull
        assert warnings == []

    def test_handles_degenerate_hull_collinear_points(self):
        """Collinear points (producing LineString, not Polygon) are handled gracefully."""
        # All points on a line -- convex hull is a LineString, not Polygon
        stops_a = [
            _make_stop("ORD-001", 1, lat=11.60, lon=75.50),
            _make_stop("ORD-002", 2, lat=11.61, lon=75.51),
            _make_stop("ORD-003", 3, lat=11.62, lon=75.52),
        ]
        # Normal triangle
        stops_b = [
            _make_stop("ORD-004", 1, lat=11.60, lon=75.50),
            _make_stop("ORD-005", 2, lat=11.60, lon=75.60),
            _make_stop("ORD-006", 3, lat=11.70, lon=75.55),
        ]

        assignment = RouteAssignment(
            assignment_id="test",
            routes=[
                _make_route("Suresh Kumar", stops_a),
                _make_route("Anil P", stops_b),
            ],
        )

        # Should not raise -- collinear hull is gracefully skipped
        warnings = detect_geographic_anomalies(assignment)
        # Collinear hull is not a Polygon, so it's skipped
        assert isinstance(warnings, list)
