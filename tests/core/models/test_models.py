"""Tests for core data models: Location, Order, Vehicle, Route."""

import pytest
from pydantic import ValidationError

from core.models.location import Location
from core.models.order import Order, OrderStatus
from core.models.vehicle import Vehicle
from core.models.route import Route, RouteStop, RouteAssignment


class TestLocation:
    """Location model validation and coordinate handling."""

    def test_valid_kerala_location(self):
        """Kerala coordinates within valid range are accepted."""
        loc = Location(latitude=9.9716, longitude=76.2846)
        assert loc.latitude == 9.9716
        assert loc.longitude == 76.2846

    def test_lon_lat_tuple_returns_geoformat(self):
        """to_lon_lat_tuple returns (lon, lat) for OSRM/GeoJSON compatibility."""
        loc = Location(latitude=9.9716, longitude=76.2846)
        assert loc.to_lon_lat_tuple() == (76.2846, 9.9716)

    def test_invalid_latitude_rejected(self):
        """Latitude outside -90..90 is rejected by Pydantic validation."""
        with pytest.raises(ValidationError):
            Location(latitude=91.0, longitude=76.0)

    def test_invalid_longitude_rejected(self):
        """Longitude outside -180..180 is rejected by Pydantic validation."""
        with pytest.raises(ValidationError):
            Location(latitude=9.0, longitude=181.0)

    def test_optional_fields_default_none(self):
        """Optional metadata fields default to None."""
        loc = Location(latitude=9.0, longitude=76.0)
        assert loc.address_text is None
        assert loc.place_id is None
        assert loc.geocode_confidence is None


class TestOrder:
    """Order model validation and business logic."""

    def test_create_lpg_order(self):
        """Standard domestic LPG cylinder order."""
        order = Order(
            order_id="ORD-001",
            address_raw="Kalamassery, Kochi",
            customer_ref="CUST-001",
            weight_kg=14.2,
        )
        assert order.weight_kg == 14.2
        assert order.status == OrderStatus.PENDING
        assert not order.is_geocoded  # No location set

    def test_geocoded_order(self):
        """Order with GPS coordinates reports as geocoded."""
        order = Order(
            order_id="ORD-002",
            address_raw="Marine Drive, Kochi",
            customer_ref="CUST-002",
            weight_kg=14.2,
            location=Location(latitude=9.9312, longitude=76.2673),
        )
        assert order.is_geocoded

    def test_zero_weight_rejected(self):
        """Weight must be positive — zero/negative weight is invalid."""
        with pytest.raises(ValidationError):
            Order(
                order_id="ORD-BAD",
                address_raw="Nowhere",
                customer_ref="CUST-BAD",
                weight_kg=0,
            )

    def test_priority_range(self):
        """Priority must be 1-3."""
        order = Order(
            order_id="ORD-003",
            address_raw="Test",
            customer_ref="CUST-003",
            weight_kg=14.2,
            priority=1,
        )
        assert order.priority == 1

        with pytest.raises(ValidationError):
            Order(
                order_id="ORD-004",
                address_raw="Test",
                customer_ref="CUST-004",
                weight_kg=14.2,
                priority=5,
            )


class TestVehicle:
    """Vehicle model validation."""

    def test_create_ape_xtra(self, kochi_depot):
        """Create a Piaggio Ape Xtra LDX with Kerala config values."""
        vehicle = Vehicle(
            vehicle_id="VEH-01",
            max_weight_kg=446.0,
            max_items=30,
            depot=kochi_depot,
        )
        assert vehicle.max_weight_kg == 446.0
        assert vehicle.speed_limit_kmh == 40.0  # default

    def test_weight_must_be_positive(self, kochi_depot):
        """Vehicle weight capacity must be positive."""
        with pytest.raises(ValidationError):
            Vehicle(
                vehicle_id="BAD",
                max_weight_kg=0,
                depot=kochi_depot,
            )


class TestRoute:
    """Route and RouteAssignment model tests."""

    def test_route_stop_count(self):
        """stop_count returns the number of delivery stops."""
        route = Route(
            route_id="R-001",
            vehicle_id="VEH-01",
            stops=[
                RouteStop(
                    order_id=f"ORD-{i}",
                    location=Location(latitude=9.97, longitude=76.28),
                    sequence=i,
                )
                for i in range(1, 4)
            ],
        )
        assert route.stop_count == 3

    def test_assignment_totals(self):
        """RouteAssignment correctly aggregates across routes."""
        assignment = RouteAssignment(
            assignment_id="A-001",
            routes=[
                Route(
                    route_id="R-1",
                    vehicle_id="VEH-01",
                    stops=[
                        RouteStop(
                            order_id="ORD-1",
                            location=Location(latitude=9.97, longitude=76.28),
                            sequence=1,
                        ),
                    ],
                ),
                Route(
                    route_id="R-2",
                    vehicle_id="VEH-02",
                    stops=[
                        RouteStop(
                            order_id="ORD-2",
                            location=Location(latitude=9.95, longitude=76.27),
                            sequence=1,
                        ),
                        RouteStop(
                            order_id="ORD-3",
                            location=Location(latitude=9.93, longitude=76.26),
                            sequence=2,
                        ),
                    ],
                ),
            ],
        )
        assert assignment.total_orders_assigned == 3
        assert assignment.vehicles_used == 2
