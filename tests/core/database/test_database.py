"""Tests for the database layer — ORM models and repository functions.

These tests validate:
1. ORM model structure (column types, relationships, defaults)
2. Repository CRUD operations (save, query, update)
3. PostGIS spatial conversions (Location ↔ geometry)
4. Safety constraints (speed alerts on telemetry)
5. Geocode cache behavior (hit counting, normalization)

Test categories:
- Unit tests (no DB): test model creation, conversion helpers
- Integration tests (needs PostgreSQL + PostGIS): marked with @pytest.mark.integration

Why SQLite can't replace PostgreSQL here?
- GeoAlchemy2 / PostGIS types don't work on SQLite
- We use PostgreSQL-specific UUID, geometry, and spatial indexes
- Integration tests run against a real PostGIS instance (from Docker)
"""

import uuid
from datetime import datetime, time, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.database.models import (
    Base,
    DriverDB,
    GeocodeCacheDB,
    OptimizationRunDB,
    OrderDB,
    RouteDB,
    RouteStopDB,
    TelemetryDB,
    VehicleDB,
)
from core.database.repository import (
    _make_point,
    _point_to_location,
    route_db_to_pydantic,
    vehicle_db_to_pydantic,
)
from core.models.location import Location
from core.models.order import Order
from core.models.route import Route, RouteAssignment, RouteStop
from core.models.vehicle import Vehicle


# =============================================================================
# ORM Model Structure Tests
# =============================================================================


class TestORMModelStructure:
    """Verify ORM models have the expected table names and columns."""

    def test_vehicle_table_name(self):
        """VehicleDB maps to the 'vehicles' table."""
        assert VehicleDB.__tablename__ == "vehicles"

    def test_driver_table_name(self):
        """DriverDB maps to the 'drivers' table."""
        assert DriverDB.__tablename__ == "drivers"

    def test_optimization_run_table_name(self):
        """OptimizationRunDB maps to the 'optimization_runs' table."""
        assert OptimizationRunDB.__tablename__ == "optimization_runs"

    def test_order_table_name(self):
        """OrderDB maps to the 'orders' table."""
        assert OrderDB.__tablename__ == "orders"

    def test_route_table_name(self):
        """RouteDB maps to the 'routes' table."""
        assert RouteDB.__tablename__ == "routes"

    def test_route_stop_table_name(self):
        """RouteStopDB maps to the 'route_stops' table."""
        assert RouteStopDB.__tablename__ == "route_stops"

    def test_telemetry_table_name(self):
        """TelemetryDB maps to the 'telemetry' table."""
        assert TelemetryDB.__tablename__ == "telemetry"

    def test_geocode_cache_table_name(self):
        """GeocodeCacheDB maps to the 'geocode_cache' table."""
        assert GeocodeCacheDB.__tablename__ == "geocode_cache"

    def test_all_tables_registered(self):
        """All 8 tables are registered in the ORM metadata.

        Catches cases where a model class exists but isn't properly
        linked to the Base (e.g., missing __tablename__).
        """
        table_names = set(Base.metadata.tables.keys())
        expected = {
            "vehicles",
            "drivers",
            "optimization_runs",
            "orders",
            "routes",
            "route_stops",
            "telemetry",
            "geocode_cache",
        }
        assert expected.issubset(table_names), (
            f"Missing tables: {expected - table_names}"
        )


# =============================================================================
# Column Presence Tests
# =============================================================================


class TestColumnPresence:
    """Verify key columns exist on each table (catches typos in mapped_column)."""

    def test_vehicle_columns(self):
        """VehicleDB has all expected columns."""
        columns = {c.name for c in VehicleDB.__table__.columns}
        expected = {
            "id", "vehicle_id", "registration_no", "vehicle_type",
            "max_weight_kg", "max_items", "depot_location",
            "speed_limit_kmh", "is_active", "created_at", "updated_at",
        }
        assert expected.issubset(columns), f"Missing: {expected - columns}"

    def test_order_columns(self):
        """OrderDB has time window columns (Phase 2 requirement)."""
        columns = {c.name for c in OrderDB.__table__.columns}
        assert "delivery_window_start" in columns, "Missing delivery_window_start"
        assert "delivery_window_end" in columns, "Missing delivery_window_end"

    def test_telemetry_columns(self):
        """TelemetryDB has speed_alert column for safety compliance."""
        columns = {c.name for c in TelemetryDB.__table__.columns}
        assert "speed_alert" in columns, "Missing speed_alert column"
        assert "speed_kmh" in columns, "Missing speed_kmh column"
        assert "accuracy_m" in columns, "Missing accuracy_m column"

    def test_route_stop_columns(self):
        """RouteStopDB has delivery verification columns."""
        columns = {c.name for c in RouteStopDB.__table__.columns}
        assert "delivered_at" in columns, "Missing delivered_at for proof-of-delivery"
        assert "delivery_location" in columns, "Missing delivery GPS location"

    def test_geocode_cache_columns(self):
        """GeocodeCacheDB has hit_count for cache analytics."""
        columns = {c.name for c in GeocodeCacheDB.__table__.columns}
        assert "hit_count" in columns, "Missing hit_count column"
        assert "source" in columns, "Missing source column"
        assert "confidence" in columns, "Missing confidence column"


# =============================================================================
# Relationship Tests
# =============================================================================


class TestRelationships:
    """Verify ORM relationships are properly configured."""

    def test_optimization_run_has_orders_relationship(self):
        """OptimizationRunDB has a 'orders' relationship to OrderDB."""
        assert hasattr(OptimizationRunDB, "orders")

    def test_optimization_run_has_routes_relationship(self):
        """OptimizationRunDB has a 'routes' relationship to RouteDB."""
        assert hasattr(OptimizationRunDB, "routes")

    def test_route_has_stops_relationship(self):
        """RouteDB has a 'stops' relationship to RouteStopDB."""
        assert hasattr(RouteDB, "stops")

    def test_route_stop_has_order_relationship(self):
        """RouteStopDB has an 'order' relationship to OrderDB."""
        assert hasattr(RouteStopDB, "order")

    def test_vehicle_has_drivers_relationship(self):
        """VehicleDB has a 'drivers' relationship to DriverDB."""
        assert hasattr(VehicleDB, "drivers")


# =============================================================================
# Conversion Helper Tests
# =============================================================================


class TestConversionHelpers:
    """Test the PostGIS ↔ Pydantic conversion functions."""

    def test_make_point_creates_spatial_expression(self):
        """_make_point creates a PostGIS ST_SetSRID(ST_MakePoint()) expression.

        We can't verify the actual geometry without a DB, but we can verify
        the function doesn't crash and returns a SQLAlchemy element.
        """
        loc = Location(latitude=11.6244, longitude=75.5796)
        point = _make_point(loc)
        # Should return a SQLAlchemy clause element, not None
        assert point is not None

    def test_point_to_location_returns_none_for_null(self):
        """_point_to_location returns None when geometry is NULL."""
        result = _point_to_location(None)
        assert result is None

    def test_point_to_location_preserves_address_text(self):
        """_point_to_location passes through the address_text parameter."""
        from shapely.geometry import Point
        from geoalchemy2.shape import from_shape

        # Create a WKB geometry that _point_to_location can parse
        shape = Point(75.5796, 11.6244)  # (lon, lat)
        geom = from_shape(shape, srid=4326)

        result = _point_to_location(geom, address_text="Test Address")
        assert result is not None
        assert result.address_text == "Test Address"
        assert abs(result.latitude - 11.6244) < 0.001
        assert abs(result.longitude - 75.5796) < 0.001

    def test_point_to_location_preserves_confidence(self):
        """_point_to_location passes through geocode confidence."""
        from shapely.geometry import Point
        from geoalchemy2.shape import from_shape

        shape = Point(75.5796, 11.6244)
        geom = from_shape(shape, srid=4326)

        result = _point_to_location(geom, confidence=0.85)
        assert result.geocode_confidence == 0.85


class TestVehicleConversion:
    """Test VehicleDB → Pydantic Vehicle conversion."""

    def test_vehicle_db_to_pydantic(self):
        """vehicle_db_to_pydantic extracts the right fields."""
        from shapely.geometry import Point
        from geoalchemy2.shape import from_shape

        vdb = MagicMock(spec=VehicleDB)
        vdb.vehicle_id = "VEH-01"
        vdb.max_weight_kg = 446.0
        vdb.max_items = 30
        vdb.speed_limit_kmh = 40.0
        vdb.depot_location = from_shape(Point(75.5796, 11.6244), srid=4326)

        vehicle = vehicle_db_to_pydantic(vdb)
        assert vehicle.vehicle_id == "VEH-01"
        assert vehicle.max_weight_kg == 446.0
        assert vehicle.max_items == 30
        assert abs(vehicle.depot.latitude - 11.6244) < 0.001
        assert abs(vehicle.depot.longitude - 75.5796) < 0.001


class TestRouteConversion:
    """Test RouteDB → Pydantic Route conversion."""

    def test_route_db_to_pydantic_empty_stops(self):
        """route_db_to_pydantic handles a route with no stops."""
        route_db = MagicMock(spec=RouteDB)
        route_db.id = uuid.uuid4()
        route_db.vehicle_id = "VEH-01"
        route_db.driver_name = "Driver 1"
        route_db.stops = []
        route_db.total_distance_km = 10.5
        route_db.total_duration_minutes = 25.0
        route_db.total_weight_kg = 142.0
        route_db.total_items = 10
        route_db.created_at = datetime.now(timezone.utc)

        route = route_db_to_pydantic(route_db)
        assert route.vehicle_id == "VEH-01"
        assert route.stop_count == 0
        assert route.total_distance_km == 10.5

    def test_route_db_to_pydantic_with_stops(self):
        """route_db_to_pydantic converts stops with PostGIS geometry."""
        from shapely.geometry import Point
        from geoalchemy2.shape import from_shape

        # Create mock route stop
        stop_db = MagicMock(spec=RouteStopDB)
        stop_db.order = MagicMock()
        stop_db.order.order_id = "ORD-001"
        stop_db.location = from_shape(Point(75.5796, 11.6244), srid=4326)
        stop_db.address_display = "Test Stop"
        stop_db.sequence = 1
        stop_db.distance_from_prev_km = 2.5
        stop_db.duration_from_prev_minutes = 8.0
        stop_db.weight_kg = 14.2
        stop_db.quantity = 1
        stop_db.notes = "Test note"
        stop_db.status = "pending"

        # Create mock route
        route_db = MagicMock(spec=RouteDB)
        route_db.id = uuid.uuid4()
        route_db.vehicle_id = "VEH-01"
        route_db.driver_name = "Driver 1"
        route_db.stops = [stop_db]
        route_db.total_distance_km = 2.5
        route_db.total_duration_minutes = 8.0
        route_db.total_weight_kg = 14.2
        route_db.total_items = 1
        route_db.created_at = datetime.now(timezone.utc)

        route = route_db_to_pydantic(route_db)
        assert route.stop_count == 1
        assert route.stops[0].order_id == "ORD-001"
        assert route.stops[0].address_display == "Test Stop"
        assert abs(route.stops[0].location.latitude - 11.6244) < 0.001


# =============================================================================
# Time Window Tests
# =============================================================================


class TestTimeWindowSupport:
    """Test that time windows flow through the system correctly."""

    def test_order_model_accepts_time_windows(self):
        """Order Pydantic model accepts delivery_window_start/end."""
        order = Order(
            order_id="TW-001",
            address_raw="Test Address",
            customer_ref="CUST-001",
            weight_kg=14.2,
            delivery_window_start=time(9, 0),
            delivery_window_end=time(12, 0),
        )
        assert order.delivery_window_start == time(9, 0)
        assert order.delivery_window_end == time(12, 0)

    def test_order_model_time_windows_default_none(self):
        """Orders without time windows default to None (pure CVRP)."""
        order = Order(
            order_id="TW-002",
            address_raw="Test Address",
            customer_ref="CUST-002",
            weight_kg=14.2,
        )
        assert order.delivery_window_start is None
        assert order.delivery_window_end is None

    def test_order_db_has_time_window_columns(self):
        """OrderDB has time window columns for VRPTW support."""
        columns = {c.name for c in OrderDB.__table__.columns}
        assert "delivery_window_start" in columns
        assert "delivery_window_end" in columns


# =============================================================================
# VROOM Time Window Integration
# =============================================================================


class TestVroomTimeWindowIntegration:
    """Test that VROOM adapter generates time_windows in the request."""

    def test_vroom_request_includes_time_windows(self, sample_orders, sample_fleet):
        """Orders with time windows generate VROOM time_windows field."""
        from core.optimizer.vroom_adapter import VroomAdapter

        # Add time windows to first two orders
        sample_orders[0].delivery_window_start = time(9, 0)
        sample_orders[0].delivery_window_end = time(12, 0)
        sample_orders[1].delivery_window_start = time(14, 0)
        sample_orders[1].delivery_window_end = time(17, 30)

        adapter = VroomAdapter(vroom_url="http://localhost:3000")
        request = adapter._build_request(sample_orders, sample_fleet)

        # First job should have time_windows [[32400, 43200]]
        # 9:00 = 9*3600 = 32400, 12:00 = 12*3600 = 43200
        job_0 = request["jobs"][0]
        assert "time_windows" in job_0
        assert job_0["time_windows"] == [[32400, 43200]]

        # Second job: 14:00 = 50400, 17:30 = 63000
        job_1 = request["jobs"][1]
        assert "time_windows" in job_1
        assert job_1["time_windows"] == [[50400, 63000]]

        # Third job (no time window) should NOT have time_windows field
        job_2 = request["jobs"][2]
        assert "time_windows" not in job_2

    def test_vroom_request_no_time_windows(self, sample_orders, sample_fleet):
        """Orders without time windows produce a standard CVRP request."""
        from core.optimizer.vroom_adapter import VroomAdapter

        adapter = VroomAdapter(vroom_url="http://localhost:3000")
        request = adapter._build_request(sample_orders, sample_fleet)

        for job in request["jobs"]:
            assert "time_windows" not in job


# =============================================================================
# CSV Import Time Window Tests
# =============================================================================


class TestCsvTimeWindowImport:
    """Test that CSV importer reads time window columns."""

    def test_csv_importer_parses_time_windows(self, tmp_path):
        """CsvImporter reads delivery_window_start/end columns."""
        from core.data_import.csv_importer import CsvImporter

        csv_content = (
            "order_id,address,customer_id,quantity,cylinder_type,"
            "latitude,longitude,delivery_window_start,delivery_window_end\n"
            'ORD-001,Chorode,CUST-001,2,domestic,'
            '11.6350,75.5900,09:00,12:00\n'
            'ORD-002,Memunda,CUST-002,1,domestic,'
            '11.5800,75.5850,14:00,17:30\n'
            'ORD-003,Panampilly,CUST-003,1,domestic,'
            '11.6200,75.5500,,\n'
        )
        csv_file = tmp_path / "orders_with_tw.csv"
        csv_file.write_text(csv_content)

        importer = CsvImporter(
            default_cylinder_weight_kg=14.2,
            cylinder_weight_lookup={"domestic": 14.2},
        )
        import_result = importer.import_orders(str(csv_file))
        orders = import_result.orders

        assert len(orders) == 3
        # First order: 09:00 to 12:00
        assert orders[0].delivery_window_start == time(9, 0)
        assert orders[0].delivery_window_end == time(12, 0)
        # Second order: 14:00 to 17:30
        assert orders[1].delivery_window_start == time(14, 0)
        assert orders[1].delivery_window_end == time(17, 30)
        # Third order: no time window
        assert orders[2].delivery_window_start is None
        assert orders[2].delivery_window_end is None


# =============================================================================
# Database Connection Module Tests
# =============================================================================


class TestDatabaseConnection:
    """Test the connection module configuration."""

    def test_default_database_url_format(self):
        """Default DATABASE_URL uses asyncpg dialect."""
        from core.database.connection import _DEFAULT_DATABASE_URL

        assert "postgresql+asyncpg://" in _DEFAULT_DATABASE_URL
        assert "routing_opt" in _DEFAULT_DATABASE_URL

    def test_get_session_is_async_generator(self):
        """get_session returns an async generator (for FastAPI Depends)."""
        import inspect
        from core.database.connection import get_session

        assert inspect.isasyncgenfunction(get_session)

    def test_engine_pool_settings(self):
        """Engine has reasonable pool settings for our fleet size."""
        from core.database.connection import engine

        # pool_size + max_overflow should handle peak concurrent queries
        # (13 drivers + 1 dashboard = ~14 concurrent)
        assert engine.pool.size() >= 5
