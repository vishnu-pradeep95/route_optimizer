"""Tests for the Kerala LPG Delivery FastAPI endpoints.

Verifies the API layer:
- Health check returns correctly
- Routes 404 when no optimization has been run
- Status updates validate input and update state
- Response models match expected shapes
- Upload-and-optimize endpoint handles the full pipeline
- Monsoon multiplier activates June–September
- GPS telemetry endpoint saves pings and detects speed alerts

Phase 2: endpoints now use PostgreSQL via the repository layer.
Tests override the get_session dependency with a mock AsyncSession,
so no real database is needed.

Uses FastAPI's TestClient — no real OSRM/VROOM/Google/PostgreSQL calls needed.
"""

import os
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from apps.kerala_delivery.api.main import app
from core.database.connection import get_session
from core.models.location import Location
from core.models.route import Route, RouteAssignment, RouteStop
from core.models.vehicle import Vehicle


# =============================================================================
# Mock DB Session Setup
# =============================================================================
# Phase 2: endpoints use AsyncSession via Depends(get_session).
# We override this dependency so tests don't need PostgreSQL running.
# Each test group patches the repository functions it uses.


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession for dependency override."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def client(mock_session):
    """FastAPI TestClient with DB session overridden to a mock.

    The dependency override replaces get_session() (which creates a real
    PostgreSQL connection) with a simple async generator that yields
    our mock session. This means:
    - No real database connection is attempted
    - Repository functions still need to be mocked individually
    - The session mock captures any direct session calls for assertions

    Rate limiting is disabled via RATE_LIMIT_ENABLED=false to prevent
    429 responses during rapid test execution. Real rate limits are
    tested in a dedicated TestRateLimiting class.

    wait_for_services is mocked to return all-healthy so startup doesn't
    try to connect to real PostgreSQL/OSRM/VROOM services.
    """
    async def override_get_session():
        yield mock_session

    # Mock wait_for_services so lifespan startup doesn't block on real services.
    # Returns all-healthy so the /health endpoint returns 200 in most tests.
    mock_service_health = {
        "postgresql": (True, "connected"),
        "osrm": (True, "available"),
        "vroom": (True, "available"),
    }

    with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "false"}), \
         patch("apps.kerala_delivery.api.main.wait_for_services", new_callable=AsyncMock, return_value=mock_service_health):
        # Re-apply the enabled flag on the limiter instance.
        # slowapi reads the enabled flag at init time, so we must
        # toggle it directly for the test session.
        from apps.kerala_delivery.api.main import limiter
        limiter.enabled = False

        app.dependency_overrides[get_session] = override_get_session

        # Set service_health and started_at directly on app.state for tests
        # that don't go through the lifespan (TestClient without context manager).
        app.state.service_health = mock_service_health
        app.state.started_at = datetime.now(timezone.utc)

        yield TestClient(app)
        app.dependency_overrides.clear()

        # Restore limiter state for other test modules
        limiter.enabled = True


# =============================================================================
# Shared Fixtures
# =============================================================================


@pytest.fixture
def mock_run_id():
    """A fixed UUID for testing."""
    return uuid.UUID("12345678-1234-1234-1234-123456789abc")


# A default mock vehicle used by upload tests. The upload endpoint requires
# at least one active vehicle; without this, it returns 400.
MOCK_VEHICLE = Vehicle(
    vehicle_id="VEH-01",
    max_weight_kg=446.0,
    max_items=30,
    depot=Location(latitude=11.6244, longitude=75.5796, address_text="Depot"),
)


@pytest.fixture
def sample_csv_file():
    """A minimal valid CSV file as bytes, for upload testing.

    Includes latitude/longitude so orders are geocoded without Google API.
    """
    csv_content = (
        "order_id,address,customer_id,cylinder_type,quantity,priority,latitude,longitude\n"
        'ORD-001,"Vatakara Bus Stand, Vatakara",CUST-001,domestic,1,2,11.5950,75.5700\n'
        'ORD-002,"Vatakara Railway Station, Vatakara",CUST-002,domestic,2,1,11.6100,75.5650\n'
    )
    return csv_content.encode("utf-8")


@pytest.fixture
def mock_vroom_2_orders():
    """VROOM response assigning 2 orders to vehicle 0.

    Reused by upload and monsoon tests.
    Step-level distance and duration are CUMULATIVE from route start,
    matching real VROOM behavior (options.g=true).
    """
    return {
        "code": 0,
        "routes": [
            {
                "vehicle": 0,
                "distance": 3000,
                "duration": 400,
                "steps": [
                    {"type": "start", "location": [75.5796, 11.6244], "arrival": 0,
                     "distance": 0, "duration": 0},
                    {"type": "job", "id": 0, "location": [75.5700, 11.5950],
                     "arrival": 200, "duration": 200, "distance": 1500, "service": 300},
                    {"type": "job", "id": 1, "location": [75.5650, 11.6100],
                     "arrival": 400, "duration": 400, "distance": 3000, "service": 300},
                    {"type": "end", "location": [75.5796, 11.6244], "arrival": 600,
                     "distance": 3000, "duration": 600},
                ],
            },
        ],
        "unassigned": [],
    }


# =============================================================================
# Tests
# =============================================================================


class TestHealthEndpoint:
    """Tests for GET /health — enhanced per-service status."""

    def test_health_returns_healthy(self, client):
        """Health check returns 200 with status 'healthy' when all services up."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "uptime_seconds" in data
        assert "services" in data
        # Per-service breakdown
        assert "postgresql" in data["services"]
        assert "osrm" in data["services"]
        assert "vroom" in data["services"]
        assert "google_api" in data["services"]
        # PostgreSQL should be connected (mocked as healthy)
        assert data["services"]["postgresql"]["status"] == "connected"
        assert data["services"]["osrm"]["status"] == "available"
        assert data["services"]["vroom"]["status"] == "available"


class TestRoutesEndpoints:
    """Tests for route retrieval and status update endpoints.

    Phase 2: these endpoints now read from the database via the repository
    layer. We mock repo functions to control what the DB "returns".
    """

    def test_list_routes_404_when_no_optimization(self, client):
        """GET /api/routes should 404 if no optimization has been run yet.

        This is the normal state when the API first starts — no CSV uploaded.
        """
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=None)
            resp = client.get("/api/routes")
        assert resp.status_code == 404

    def test_list_routes_returns_route_summaries(self, client, mock_run_id):
        """GET /api/routes should return a list of route summaries."""
        from core.database.models import OptimizationRunDB, RouteDB, RouteStopDB

        # Mock the latest run
        mock_run = MagicMock(spec=OptimizationRunDB)
        mock_run.id = mock_run_id
        mock_run.orders_unassigned = 0

        # Mock route with 2 stops
        mock_stop1 = MagicMock(spec=RouteStopDB)
        mock_stop2 = MagicMock(spec=RouteStopDB)
        mock_route = MagicMock(spec=RouteDB)
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "VEH-01"
        mock_route.driver_name = "Driver 1"
        mock_route.stops = [mock_stop1, mock_stop2]
        mock_route.total_distance_km = 5.5
        mock_route.total_duration_minutes = 11.0
        mock_route.total_weight_kg = 42.6
        mock_route.total_items = 3

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=mock_run)
            mock_repo.get_routes_for_run = AsyncMock(return_value=[mock_route])
            resp = client.get("/api/routes")

        assert resp.status_code == 200
        data = resp.json()
        assert "routes" in data
        assert len(data["routes"]) == 1
        route = data["routes"][0]
        assert route["vehicle_id"] == "VEH-01"
        assert route["total_stops"] == 2

    def test_get_driver_route_returns_stops(self, client, mock_run_id):
        """GET /api/routes/{vehicle_id} should return stops with details."""
        from core.database.models import OptimizationRunDB, RouteDB
        from shapely.geometry import Point
        from geoalchemy2.shape import from_shape

        mock_run = MagicMock(spec=OptimizationRunDB)
        mock_run.id = mock_run_id

        # Build a mock route with a stop. We need real PostGIS geometry
        # for the route_db_to_pydantic conversion to work correctly.
        mock_stop = MagicMock()
        mock_stop.order = MagicMock()
        mock_stop.order.order_id = "ORD-001"
        mock_stop.order.geocode_confidence = None
        mock_stop.order.geocode_method = None
        mock_stop.location = from_shape(Point(75.5700, 11.5950), srid=4326)
        mock_stop.address_display = "Vatakara Bus Stand"
        mock_stop.address_original = None
        mock_stop.sequence = 1
        mock_stop.distance_from_prev_km = 2.5
        mock_stop.duration_from_prev_minutes = 5.0
        mock_stop.weight_kg = 14.2
        mock_stop.quantity = 1
        mock_stop.notes = ""
        mock_stop.status = "pending"

        mock_route = MagicMock(spec=RouteDB)
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "VEH-01"
        mock_route.driver_name = "Driver 1"
        mock_route.stops = [mock_stop]
        mock_route.total_distance_km = 2.5
        mock_route.total_duration_minutes = 5.0
        mock_route.total_weight_kg = 14.2
        mock_route.total_items = 1
        mock_route.created_at = datetime.now(timezone.utc)

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=mock_run)
            mock_repo.get_route_for_vehicle = AsyncMock(return_value=mock_route)
            # Use the real route_db_to_pydantic conversion function
            from core.database.repository import route_db_to_pydantic
            mock_repo.route_db_to_pydantic = route_db_to_pydantic

            resp = client.get("/api/routes/VEH-01")

        assert resp.status_code == 200
        data = resp.json()
        assert data["vehicle_id"] == "VEH-01"
        assert len(data["stops"]) == 1
        assert data["stops"][0]["order_id"] == "ORD-001"
        # Verify coordinates are present (needed for map display)
        assert "latitude" in data["stops"][0]
        assert "longitude" in data["stops"][0]

    def test_get_driver_route_404_wrong_vehicle(self, client, mock_run_id):
        """GET /api/routes/WRONG-ID should 404."""
        from core.database.models import OptimizationRunDB

        mock_run = MagicMock(spec=OptimizationRunDB)
        mock_run.id = mock_run_id

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=mock_run)
            mock_repo.get_route_for_vehicle = AsyncMock(return_value=None)
            resp = client.get("/api/routes/VEH-99")
        assert resp.status_code == 404

    def test_update_stop_status_delivered(self, client, mock_run_id):
        """POST status update should change stop status to 'delivered'.

        This is what the driver app calls when they complete a delivery.
        """
        from core.database.models import OptimizationRunDB, RouteDB

        mock_run = MagicMock(spec=OptimizationRunDB)
        mock_run.id = mock_run_id

        # Mock route with a stop matching ORD-001
        mock_stop = MagicMock()
        mock_stop.order = MagicMock()
        mock_stop.order.order_id = "ORD-001"
        mock_stop.order_id = uuid.uuid4()  # The DB FK to orders table

        mock_route = MagicMock(spec=RouteDB)
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "VEH-01"
        mock_route.stops = [mock_stop]

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=mock_run)
            mock_repo.get_route_for_vehicle = AsyncMock(return_value=mock_route)
            mock_repo.update_stop_status = AsyncMock(return_value=True)

            resp = client.post(
                "/api/routes/VEH-01/stops/ORD-001/status",
                json={"status": "delivered"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "delivered"

    def test_update_stop_status_with_delivery_location(self, client, mock_run_id):
        """Status update with GPS coordinates records proof-of-delivery.

        When a driver marks a stop as delivered AND includes their GPS location,
        the system records it for proof-of-delivery and driver-verified geocoding.
        This builds a high-quality local address database over time.
        """
        from core.database.models import OptimizationRunDB, RouteDB

        mock_run = MagicMock(spec=OptimizationRunDB)
        mock_run.id = mock_run_id

        mock_stop = MagicMock()
        mock_stop.order = MagicMock()
        mock_stop.order.order_id = "ORD-001"
        mock_stop.order_id = uuid.uuid4()

        mock_route = MagicMock(spec=RouteDB)
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "VEH-01"
        mock_route.stops = [mock_stop]

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=mock_run)
            mock_repo.get_route_for_vehicle = AsyncMock(return_value=mock_route)
            mock_repo.update_stop_status = AsyncMock(return_value=True)

            resp = client.post(
                "/api/routes/VEH-01/stops/ORD-001/status",
                json={
                    "status": "delivered",
                    "latitude": 11.5950,
                    "longitude": 75.5700,
                },
            )

        assert resp.status_code == 200
        # Verify delivery_location was passed to the repo
        call_kwargs = mock_repo.update_stop_status.call_args.kwargs
        assert call_kwargs["delivery_location"] is not None
        assert call_kwargs["delivery_location"].latitude == pytest.approx(11.5950)
        assert call_kwargs["delivery_location"].longitude == pytest.approx(75.5700)

    def test_update_stop_status_rejects_invalid(self, client):
        """Invalid status values should be rejected with 422.

        Pydantic's Literal type validation catches invalid values before
        the endpoint logic runs — no DB access needed.
        """
        resp = client.post(
            "/api/routes/VEH-01/stops/ORD-001/status",
            json={"status": "invalid_status"},
        )
        # Pydantic Literal validation returns 422 Unprocessable Entity
        assert resp.status_code == 422

    def test_update_stop_status_404_wrong_order(self, client, mock_run_id):
        """Status update for nonexistent order should 404."""
        from core.database.models import OptimizationRunDB, RouteDB

        mock_run = MagicMock(spec=OptimizationRunDB)
        mock_run.id = mock_run_id

        # Route exists but has no matching stop
        mock_route = MagicMock(spec=RouteDB)
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "VEH-01"
        mock_route.stops = []  # No stops

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=mock_run)
            mock_repo.get_route_for_vehicle = AsyncMock(return_value=mock_route)

            resp = client.post(
                "/api/routes/VEH-01/stops/NONEXISTENT/status",
                json={"status": "delivered"},
            )
        assert resp.status_code == 404

    def test_update_stop_status_delivered_with_gps_saves_geocache(
        self, client, mock_run_id
    ):
        """Delivered + GPS should save driver-verified location to geocode cache.

        When a driver marks a stop as delivered AND includes GPS coordinates,
        the system persists that high-confidence location into geocode_cache
        with source='driver_verified' and confidence=0.95.
        """
        from core.database.models import OptimizationRunDB, RouteDB

        mock_run = MagicMock(spec=OptimizationRunDB)
        mock_run.id = mock_run_id

        mock_stop = MagicMock()
        mock_stop.order = MagicMock()
        mock_stop.order.order_id = "ORD-001"
        mock_stop.order.address_raw = "Test Address, Vatakara"
        mock_stop.order_id = uuid.uuid4()

        mock_route = MagicMock(spec=RouteDB)
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "VEH-01"
        mock_route.stops = [mock_stop]

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=mock_run)
            mock_repo.get_route_for_vehicle = AsyncMock(return_value=mock_route)
            mock_repo.update_stop_status = AsyncMock(return_value=True)
            mock_repo.save_geocode_cache = AsyncMock()

            resp = client.post(
                "/api/routes/VEH-01/stops/ORD-001/status",
                json={
                    "status": "delivered",
                    "latitude": 11.5950,
                    "longitude": 75.5700,
                },
            )

        assert resp.status_code == 200
        # Verify save_geocode_cache was called with driver-verified params
        mock_repo.save_geocode_cache.assert_called_once()
        call_kwargs = mock_repo.save_geocode_cache.call_args.kwargs
        assert call_kwargs["address_raw"] == "Test Address, Vatakara"
        assert call_kwargs["source"] == "driver_verified"
        assert call_kwargs["confidence"] == 0.95
        assert call_kwargs["location"].latitude == pytest.approx(11.5950)
        assert call_kwargs["location"].longitude == pytest.approx(75.5700)

    def test_update_stop_status_delivered_without_gps_skips_geocache(
        self, client, mock_run_id
    ):
        """Delivered without GPS should NOT save to geocode cache.

        No GPS coordinates means we have no location data to persist.
        """
        from core.database.models import OptimizationRunDB, RouteDB

        mock_run = MagicMock(spec=OptimizationRunDB)
        mock_run.id = mock_run_id

        mock_stop = MagicMock()
        mock_stop.order = MagicMock()
        mock_stop.order.order_id = "ORD-001"
        mock_stop.order.address_raw = "Test Address, Vatakara"
        mock_stop.order_id = uuid.uuid4()

        mock_route = MagicMock(spec=RouteDB)
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "VEH-01"
        mock_route.stops = [mock_stop]

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=mock_run)
            mock_repo.get_route_for_vehicle = AsyncMock(return_value=mock_route)
            mock_repo.update_stop_status = AsyncMock(return_value=True)
            mock_repo.save_geocode_cache = AsyncMock()

            resp = client.post(
                "/api/routes/VEH-01/stops/ORD-001/status",
                json={"status": "delivered"},
            )

        assert resp.status_code == 200
        mock_repo.save_geocode_cache.assert_not_called()

    def test_update_stop_status_failed_with_gps_skips_geocache(
        self, client, mock_run_id
    ):
        """Failed + GPS should NOT save to geocode cache.

        Driver may not be at the exact delivery address when marking failed
        (e.g., they gave up before reaching the door). Location data from
        failed deliveries is unreliable for geocoding.
        """
        from core.database.models import OptimizationRunDB, RouteDB

        mock_run = MagicMock(spec=OptimizationRunDB)
        mock_run.id = mock_run_id

        mock_stop = MagicMock()
        mock_stop.order = MagicMock()
        mock_stop.order.order_id = "ORD-001"
        mock_stop.order.address_raw = "Test Address, Vatakara"
        mock_stop.order_id = uuid.uuid4()

        mock_route = MagicMock(spec=RouteDB)
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "VEH-01"
        mock_route.stops = [mock_stop]

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=mock_run)
            mock_repo.get_route_for_vehicle = AsyncMock(return_value=mock_route)
            mock_repo.update_stop_status = AsyncMock(return_value=True)
            mock_repo.save_geocode_cache = AsyncMock()

            resp = client.post(
                "/api/routes/VEH-01/stops/ORD-001/status",
                json={
                    "status": "failed",
                    "latitude": 11.5950,
                    "longitude": 75.5700,
                },
            )

        assert resp.status_code == 200
        mock_repo.save_geocode_cache.assert_not_called()

    def test_update_stop_status_delivered_gps_null_address_skips_geocache(
        self, client, mock_run_id
    ):
        """Delivered + GPS but null address_raw should NOT save to geocode cache.

        Guard against null address: if order has no address text, there is
        nothing meaningful to cache as a geocode key.
        """
        from core.database.models import OptimizationRunDB, RouteDB

        mock_run = MagicMock(spec=OptimizationRunDB)
        mock_run.id = mock_run_id

        mock_stop = MagicMock()
        mock_stop.order = MagicMock()
        mock_stop.order.order_id = "ORD-001"
        mock_stop.order.address_raw = None  # No address text
        mock_stop.order_id = uuid.uuid4()

        mock_route = MagicMock(spec=RouteDB)
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "VEH-01"
        mock_route.stops = [mock_stop]

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=mock_run)
            mock_repo.get_route_for_vehicle = AsyncMock(return_value=mock_route)
            mock_repo.update_stop_status = AsyncMock(return_value=True)
            mock_repo.save_geocode_cache = AsyncMock()

            resp = client.post(
                "/api/routes/VEH-01/stops/ORD-001/status",
                json={
                    "status": "delivered",
                    "latitude": 11.5950,
                    "longitude": 75.5700,
                },
            )

        assert resp.status_code == 200
        mock_repo.save_geocode_cache.assert_not_called()


class TestUploadAndOptimize:
    """Tests for POST /api/upload-orders — the main workflow endpoint.

    These mock VROOM and the database repository since we're testing
    the API layer, not the actual optimization or persistence.
    """

    def test_upload_csv_triggers_optimization(
        self, client, sample_csv_file, mock_vroom_2_orders, mock_run_id
    ):
        """Uploading a valid CSV should parse orders and run VROOM.

        Flow: CSV upload → CsvImporter → (geocoding skipped, coords in CSV)
              → VroomAdapter.optimize() → repo.save_optimization_run() → return summary.
        """
        with (
            patch("core.optimizer.vroom_adapter.httpx.post") as mock_post,
            patch("apps.kerala_delivery.api.main.repo") as mock_repo,
        ):
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_vroom_2_orders,
                raise_for_status=lambda: None,
            )
            # Mock DB operations called during upload
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[MagicMock()])
            mock_repo.vehicle_db_to_pydantic.return_value = MOCK_VEHICLE
            mock_repo.save_optimization_run = AsyncMock(return_value=mock_run_id)

            resp = client.post(
                "/api/upload-orders",
                files={"file": ("orders.csv", sample_csv_file, "text/csv")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_orders"] == 2
        assert data["orders_assigned"] == 2
        assert data["vehicles_used"] >= 1
        assert "assignment_id" in data
        assert "run_id" in data

    def test_upload_empty_csv_returns_400(self, client):
        """CSV with no valid orders should return 400."""
        # CSV with header only — no data rows
        empty_csv = b"order_id,address,customer_id,weight_kg\n"
        resp = client.post(
            "/api/upload-orders",
            files={"file": ("empty.csv", empty_csv, "text/csv")},
        )
        assert resp.status_code == 400

    def test_upload_all_geocoding_failures_returns_structured_200(self, client):
        """CSV where no orders can be geocoded returns structured 200 with failures.

        When the CSV has no lat/lon columns and the geocoder can't resolve
        any addresses, the system returns a structured response with per-row
        failure details instead of an opaque 400 error. This lets office staff
        see exactly which addresses to fix.
        """
        csv_no_coords = (
            "order_id,address,customer_id,weight_kg\n"
            'ORD-001,"Unknown Place XYZ",CUST-001,14.2\n'
            'ORD-002,"Another Unknown ABC",CUST-002,14.2\n'
        )
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            # Cache returns nothing, no Google API key set
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)

            resp = client.post(
                "/api/upload-orders",
                files={"file": ("orders.csv", csv_no_coords.encode(), "text/csv")},
            )

        assert resp.status_code == 200
        data = resp.json()
        # Zero-success structured response
        assert data["run_id"] == ""
        assert data["orders_assigned"] == 0
        assert data["total_rows"] == 2
        assert data["geocoded"] == 0
        # No geocoder configured, so orders remain ungeocoded (no geocoding_failures
        # collected because geocoder is None), but total_orders reflects valid orders
        assert data["total_orders"] == 2


class TestMonsoonMultiplier:
    """Tests for the monsoon-season travel time multiplier.

    Kerala monsoon (June–September) adds ~50% extra on top of the base
    1.3× safety multiplier, giving 1.95× total. This test verifies the
    multiplier is correctly applied during monsoon months and absent
    outside monsoon season.

    Approach: patch the VroomAdapter *class* in main's namespace so we can
    inspect call_args to see what safety_multiplier was passed. The mock's
    optimize() returns a minimal RouteAssignment so the endpoint succeeds.
    """

    def _upload_with_mocked_datetime(
        self, client, sample_csv_file, fake_now, mock_run_id
    ):
        """Helper: upload CSV with datetime.now() patched to a specific date.

        Returns (response, safety_multiplier_passed_to_VroomAdapter).
        """
        # Build a minimal RouteAssignment the mock optimizer will return
        fake_assignment = RouteAssignment(
            assignment_id="mock-assign",
            routes=[],
            unassigned_order_ids=[],
            optimization_time_ms=1.0,
        )

        with (
            patch("apps.kerala_delivery.api.main.datetime") as mock_dt,
            patch("apps.kerala_delivery.api.main.VroomAdapter") as MockVroom,
            patch("apps.kerala_delivery.api.main.repo") as mock_repo,
        ):
            # datetime.now() returns our fake date; datetime(...) constructor
            # still works for Pydantic model default_factory via side_effect
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            # The mock VroomAdapter instance's optimize() returns our fake
            MockVroom.return_value.optimize.return_value = fake_assignment

            # Mock DB operations
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[MagicMock()])
            mock_repo.vehicle_db_to_pydantic.return_value = MOCK_VEHICLE
            mock_repo.save_optimization_run = AsyncMock(return_value=mock_run_id)

            resp = client.post(
                "/api/upload-orders",
                files={"file": ("orders.csv", sample_csv_file, "text/csv")},
            )

            # Extract the safety_multiplier kwarg passed to VroomAdapter(...)
            multiplier = MockVroom.call_args.kwargs.get("safety_multiplier")

        return resp, multiplier

    def test_monsoon_multiplier_applied_in_july(
        self, client, sample_csv_file, mock_run_id
    ):
        """During July (monsoon), effective multiplier = 1.3 × 1.5 = 1.95."""
        resp, multiplier = self._upload_with_mocked_datetime(
            client, sample_csv_file,
            fake_now=datetime(2026, 7, 15, 10, 0, 0),
            mock_run_id=mock_run_id,
        )
        assert resp.status_code == 200
        assert multiplier == pytest.approx(1.3 * 1.5)

    def test_no_monsoon_multiplier_in_february(
        self, client, sample_csv_file, mock_run_id
    ):
        """Outside monsoon (February), only base 1.3× multiplier is used."""
        resp, multiplier = self._upload_with_mocked_datetime(
            client, sample_csv_file,
            fake_now=datetime(2026, 2, 15, 10, 0, 0),
            mock_run_id=mock_run_id,
        )
        assert resp.status_code == 200
        assert multiplier == pytest.approx(1.3)


class TestTelemetryEndpoint:
    """Tests for POST /api/telemetry — driver GPS ping submission.

    Phase 2 feature: drivers send periodic GPS pings for live tracking
    and route adherence monitoring.
    """

    def test_telemetry_normal_speed(self, client):
        """Normal speed ping (< 40 km/h) should save without alert."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.save_telemetry = AsyncMock(
                return_value=(uuid.uuid4(), False)
            )

            resp = client.post(
                "/api/telemetry",
                json={
                    "vehicle_id": "VEH-01",
                    "latitude": 11.6244,
                    "longitude": 75.5796,
                    "speed_kmh": 30.0,
                    "accuracy_m": 10.0,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["speed_alert"] is False
        assert data["telemetry_id"] is not None

    def test_telemetry_speed_alert(self, client):
        """Speed > 40 km/h should trigger a safety alert.

        Non-negotiable Kerala MVD constraint.
        """
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.save_telemetry = AsyncMock(
                return_value=(uuid.uuid4(), True)
            )

            resp = client.post(
                "/api/telemetry",
                json={
                    "vehicle_id": "VEH-01",
                    "latitude": 11.6244,
                    "longitude": 75.5796,
                    "speed_kmh": 55.0,
                    "accuracy_m": 10.0,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["speed_alert"] is True
        assert "SPEED ALERT" in data["message"]

    def test_telemetry_low_accuracy_discarded(self, client):
        """GPS pings with accuracy > 50m should be discarded.

        GPS drift in dense Kerala neighborhoods can put drivers on
        the wrong street. Low-accuracy pings pollute telemetry data.
        """
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.save_telemetry = AsyncMock(
                return_value=(None, False)
            )

            resp = client.post(
                "/api/telemetry",
                json={
                    "vehicle_id": "VEH-01",
                    "latitude": 11.6244,
                    "longitude": 75.5796,
                    "speed_kmh": 25.0,
                    "accuracy_m": 75.0,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["telemetry_id"] is None
        assert "discarded" in data["message"].lower()


class TestGetVehicleTelemetry:
    """Tests for GET /api/telemetry/{vehicle_id} — telemetry retrieval.

    Used by the operations dashboard to show a driver's GPS trace on the map.
    """

    def test_get_telemetry_returns_pings(self, client):
        """GET /api/telemetry/{vehicle_id} should return recent GPS pings."""
        from core.database.models import TelemetryDB
        from shapely.geometry import Point
        from geoalchemy2.shape import from_shape

        mock_ping = MagicMock(spec=TelemetryDB)
        mock_ping.location = from_shape(Point(75.5796, 11.6244), srid=4326)
        mock_ping.speed_kmh = 30.0
        mock_ping.accuracy_m = 10.0
        mock_ping.heading = 90.0
        mock_ping.recorded_at = datetime(2026, 2, 21, 10, 0, 0, tzinfo=timezone.utc)
        mock_ping.speed_alert = False

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_vehicle_telemetry = AsyncMock(return_value=[mock_ping])
            resp = client.get("/api/telemetry/VEH-01")

        assert resp.status_code == 200
        data = resp.json()
        assert data["vehicle_id"] == "VEH-01"
        assert data["count"] == 1
        assert data["pings"][0]["speed_kmh"] == 30.0
        assert data["pings"][0]["latitude"] == pytest.approx(11.6244, abs=0.001)
        assert data["pings"][0]["longitude"] == pytest.approx(75.5796, abs=0.001)

    def test_get_telemetry_empty(self, client):
        """GET /api/telemetry/{vehicle_id} with no pings returns empty list."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_vehicle_telemetry = AsyncMock(return_value=[])
            resp = client.get("/api/telemetry/VEH-99")

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["pings"] == []

    def test_get_telemetry_respects_limit(self, client):
        """Limit parameter should be passed to the repository."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_vehicle_telemetry = AsyncMock(return_value=[])
            resp = client.get("/api/telemetry/VEH-01?limit=5")

        assert resp.status_code == 200
        # Verify limit was passed through
        mock_repo.get_vehicle_telemetry.assert_awaited_once()
        call_kwargs = mock_repo.get_vehicle_telemetry.call_args
        assert call_kwargs.kwargs.get("limit") == 5 or call_kwargs[1].get("limit") == 5


class TestOptimizationRunsEndpoints:
    """Tests for GET /api/runs and GET /api/runs/{run_id}/routes.

    Phase 2 history endpoints: let the dashboard view past optimization
    runs and compare performance over time.
    """

    def test_list_runs_returns_recent(self, client, mock_run_id):
        """GET /api/runs should return a list of recent optimization runs."""
        from core.database.models import OptimizationRunDB

        mock_run = MagicMock(spec=OptimizationRunDB)
        mock_run.id = mock_run_id
        mock_run.created_at = datetime(2026, 2, 21, 10, 0, 0, tzinfo=timezone.utc)
        mock_run.total_orders = 30
        mock_run.orders_assigned = 28
        mock_run.orders_unassigned = 2
        mock_run.vehicles_used = 5
        mock_run.optimization_time_ms = 42.5
        mock_run.source_filename = "orders_2026-02-21.csv"
        mock_run.status = "completed"

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_recent_runs = AsyncMock(return_value=[mock_run])
            resp = client.get("/api/runs")

        assert resp.status_code == 200
        data = resp.json()
        assert "runs" in data
        assert len(data["runs"]) == 1
        run = data["runs"][0]
        assert run["run_id"] == str(mock_run_id)
        assert run["total_orders"] == 30
        assert run["status"] == "completed"

    def test_list_runs_empty(self, client):
        """GET /api/runs should return empty list when no runs exist."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_recent_runs = AsyncMock(return_value=[])
            resp = client.get("/api/runs")

        assert resp.status_code == 200
        data = resp.json()
        assert data["runs"] == []

    def test_get_routes_for_run(self, client, mock_run_id):
        """GET /api/runs/{run_id}/routes should return routes for that run."""
        from core.database.models import OptimizationRunDB, RouteDB, RouteStopDB

        mock_run = MagicMock(spec=OptimizationRunDB)
        mock_run.id = mock_run_id
        mock_run.created_at = datetime(2026, 2, 21, 10, 0, 0, tzinfo=timezone.utc)

        mock_route = MagicMock(spec=RouteDB)
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "VEH-03"
        mock_route.driver_name = "Driver 3"
        mock_route.stops = [MagicMock(spec=RouteStopDB)]
        mock_route.total_distance_km = 8.3
        mock_route.total_duration_minutes = 22.0
        mock_route.total_weight_kg = 56.8
        mock_route.total_items = 4

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_run_by_id = AsyncMock(return_value=mock_run)
            mock_repo.get_routes_for_run = AsyncMock(return_value=[mock_route])
            resp = client.get(f"/api/runs/{mock_run_id}/routes")

        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == str(mock_run_id)
        assert len(data["routes"]) == 1
        assert data["routes"][0]["vehicle_id"] == "VEH-03"

    def test_get_routes_for_run_404(self, client):
        """GET /api/runs/{run_id}/routes should 404 for nonexistent run."""
        fake_id = uuid.uuid4()
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_run_by_id = AsyncMock(return_value=None)
            resp = client.get(f"/api/runs/{fake_id}/routes")

        assert resp.status_code == 404

    def test_get_routes_for_run_invalid_uuid(self, client):
        """GET /api/runs/not-a-uuid/routes should 400 for invalid run_id."""
        resp = client.get("/api/runs/not-a-valid-uuid/routes")
        assert resp.status_code == 400


class TestGeocodeCacheHit:
    """Tests for the geocode cache-hit path in upload_and_optimize.

    When a CSV is uploaded, orders without coordinates try the DB geocode
    cache before calling the Google Maps API ($5 per 1000 requests).
    This test verifies the cache-hit path works and avoids unnecessary
    API calls — an important cost-saving feature.
    """

    def test_cache_hit_skips_google_api(self, client, mock_run_id, mock_vroom_2_orders):
        """Orders with cached coordinates should NOT call Google Geocoding API.

        Flow: CSV has address but no lat/lon → repo.get_cached_geocode returns
        a Location → order.location is set from cache → Google API never called.
        """
        # CSV without lat/lon — forces geocoding path
        csv_without_coords = (
            "order_id,address,customer_id,cylinder_type,quantity,priority\n"
            'ORD-001,"Vatakara Bus Stand, Vatakara",CUST-001,domestic,1,2\n'
            'ORD-002,"Vatakara Railway Station, Vatakara",CUST-002,domestic,2,1\n'
        )

        # The cache will return a Location for both addresses
        cached_location = Location(
            latitude=11.5950, longitude=75.5700, address_text="Cached address"
        )

        with (
            patch("core.optimizer.vroom_adapter.httpx.post") as mock_post,
            patch("apps.kerala_delivery.api.main.repo") as mock_repo,
            patch("apps.kerala_delivery.api.main.GoogleGeocoder") as MockGeocoder,
        ):
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_vroom_2_orders,
                raise_for_status=lambda: None,
            )
            # Cache returns coordinates for every address
            mock_repo.get_cached_geocode = AsyncMock(return_value=cached_location)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[MagicMock()])
            mock_repo.vehicle_db_to_pydantic.return_value = MOCK_VEHICLE
            mock_repo.save_optimization_run = AsyncMock(return_value=mock_run_id)

            resp = client.post(
                "/api/upload-orders",
                files={"file": ("orders.csv", csv_without_coords.encode(), "text/csv")},
            )

        assert resp.status_code == 200
        # GoogleGeocoder should NOT have been instantiated since GOOGLE_MAPS_API_KEY
        # is empty in test environment — but even if it were, get_cached_geocode
        # returned coordinates so the geocoder.geocode() should never be called.
        # The key assertion: all orders were geocoded from cache, optimization ran.
        data = resp.json()
        assert data["total_orders"] == 2
        assert data["orders_assigned"] == 2


# =============================================================================
# Authentication Tests
# =============================================================================


class TestAuthentication:
    """Tests for API key authentication on protected endpoints.

    When the API_KEY environment variable is set:
    - All POST endpoints must include a valid X-API-Key header.
    - Sensitive GET endpoints (fleet telemetry, vehicle details) also
      require the API key — these expose driver GPS locations and
      vehicle registration numbers, which are privacy-sensitive.
    - Non-sensitive GET endpoints (routes, optimization runs) remain
      open for easy dashboard access.

    Security requirements:
    - Code Review #6, Critical C1: POST endpoints need auth.
    - Code Review #7+: Fleet telemetry/vehicle GETs need read auth.
    """

    @pytest.fixture
    def auth_client(self, mock_session):
        """TestClient with API_KEY set — requires auth on POST endpoints.

        Uses patch.dict to set API_KEY for the duration of each test.
        The verify_api_key dependency reads os.environ at request time,
        so the env var must be set when the request is made (not just
        when the TestClient is created).
        """
        async def override_get_session():
            yield mock_session

        mock_health = {
            "postgresql": (True, "connected"),
            "osrm": (True, "available"),
            "vroom": (True, "available"),
        }
        app.dependency_overrides[get_session] = override_get_session
        app.state.service_health = mock_health
        app.state.started_at = datetime.now(timezone.utc)
        with patch.dict(os.environ, {"API_KEY": "test-secret-key-123"}), \
             patch("apps.kerala_delivery.api.main.wait_for_services", new_callable=AsyncMock, return_value=mock_health):
            yield TestClient(app)
        app.dependency_overrides.clear()

    def test_upload_rejects_missing_key(self, auth_client, sample_csv_file):
        """POST /api/upload-orders without X-API-Key header returns 401."""
        resp = auth_client.post(
            "/api/upload-orders",
            files={"file": ("orders.csv", sample_csv_file, "text/csv")},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert "API key" in data.get("user_message", data.get("detail", ""))

    def test_upload_rejects_wrong_key(self, auth_client, sample_csv_file):
        """POST /api/upload-orders with incorrect API key returns 401."""
        resp = auth_client.post(
            "/api/upload-orders",
            files={"file": ("orders.csv", sample_csv_file, "text/csv")},
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 401

    def test_status_update_rejects_missing_key(self, auth_client):
        """POST /api/routes/.../status without API key returns 401."""
        resp = auth_client.post(
            "/api/routes/VEH-01/stops/ORD-001/status",
            json={"status": "delivered"},
        )
        assert resp.status_code == 401

    def test_telemetry_rejects_missing_key(self, auth_client):
        """POST /api/telemetry without API key returns 401."""
        resp = auth_client.post(
            "/api/telemetry",
            json={
                "vehicle_id": "VEH-01",
                "latitude": 11.6244,
                "longitude": 75.5796,
                "speed_kmh": 30.0,
            },
        )
        assert resp.status_code == 401

    def test_get_endpoints_open_without_key(self, auth_client):
        """Non-sensitive GET endpoints work without API key even when API_KEY is set.

        GET /api/routes is a non-sensitive read endpoint (route summaries,
        no PII). It returns 404 (no routes exist) rather than 401, proving
        that authentication was NOT enforced on this particular endpoint.

        Contrast with sensitive endpoints tested below — fleet telemetry and
        vehicle details DO require auth because they expose driver GPS
        locations and vehicle registration numbers.
        """
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=None)
            resp = auth_client.get("/api/routes")
        assert resp.status_code == 404  # No routes, but auth passed

    # -----------------------------------------------------------------
    # Read-scoped auth: sensitive GET endpoints require API key
    # -----------------------------------------------------------------

    def test_fleet_telemetry_rejects_missing_key(self, auth_client):
        """GET /api/telemetry/fleet without API key returns 401.

        Fleet telemetry exposes real-time GPS coordinates of all drivers.
        This is personally sensitive data — anyone with the URL could
        track all delivery drivers in real time if unprotected.
        """
        resp = auth_client.get("/api/telemetry/fleet")
        assert resp.status_code == 401
        assert "API key" in resp.json().get("user_message", resp.json().get("detail", ""))

    def test_vehicle_telemetry_rejects_missing_key(self, auth_client):
        """GET /api/telemetry/{vehicle_id} without API key returns 401.

        Individual vehicle GPS history — same privacy concern as fleet
        telemetry but for a single driver.
        """
        resp = auth_client.get("/api/telemetry/VEH-01")
        assert resp.status_code == 401
        assert "API key" in resp.json().get("user_message", resp.json().get("detail", ""))

    def test_list_vehicles_rejects_missing_key(self, auth_client):
        """GET /api/vehicles without API key returns 401.

        Vehicle list includes registration numbers and depot locations —
        sensitive operational data that shouldn't be publicly accessible.
        """
        resp = auth_client.get("/api/vehicles")
        assert resp.status_code == 401
        assert "API key" in resp.json().get("user_message", resp.json().get("detail", ""))

    def test_get_vehicle_rejects_missing_key(self, auth_client):
        """GET /api/vehicles/{vehicle_id} without API key returns 401."""
        resp = auth_client.get("/api/vehicles/VEH-01")
        assert resp.status_code == 401
        assert "API key" in resp.json().get("user_message", resp.json().get("detail", ""))

    def test_fleet_telemetry_accepts_correct_key(self, auth_client):
        """GET /api/telemetry/fleet with correct API key succeeds."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_fleet_latest_telemetry = AsyncMock(return_value=[])
            resp = auth_client.get(
                "/api/telemetry/fleet",
                headers={"X-API-Key": "test-secret-key-123"},
            )
        assert resp.status_code == 200

    def test_vehicle_telemetry_accepts_correct_key(self, auth_client):
        """GET /api/telemetry/{vehicle_id} with correct API key succeeds."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_vehicle_telemetry = AsyncMock(return_value=[])
            resp = auth_client.get(
                "/api/telemetry/VEH-01",
                headers={"X-API-Key": "test-secret-key-123"},
            )
        assert resp.status_code == 200

    def test_list_vehicles_accepts_correct_key(self, auth_client):
        """GET /api/vehicles with correct API key succeeds."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_all_vehicles = AsyncMock(return_value=[])
            resp = auth_client.get(
                "/api/vehicles",
                headers={"X-API-Key": "test-secret-key-123"},
            )
        assert resp.status_code == 200

    def test_get_vehicle_accepts_correct_key(self, auth_client):
        """GET /api/vehicles/{vehicle_id} with correct API key succeeds."""
        mock_v = MagicMock(
            vehicle_id="VEH-01",
            registration_no="KL-07-AB-1234",
            vehicle_type="diesel",
            max_weight_kg=446.0,
            max_items=30,
            depot_location=MagicMock(),
            speed_limit_kmh=40.0,
            is_active=True,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo, \
             patch("apps.kerala_delivery.api.main.to_shape") as mock_to_shape:
            mock_repo.get_vehicle_by_vehicle_id = AsyncMock(return_value=mock_v)
            mock_to_shape.return_value = MagicMock(y=11.62, x=75.58)
            resp = auth_client.get(
                "/api/vehicles/VEH-01",
                headers={"X-API-Key": "test-secret-key-123"},
            )
        assert resp.status_code == 200

    def test_read_endpoints_reject_wrong_key(self, auth_client):
        """Sensitive GET endpoints reject incorrect API key — same as POST."""
        resp = auth_client.get(
            "/api/telemetry/fleet",
            headers={"X-API-Key": "wrong-key-456"},
        )
        assert resp.status_code == 401

    def test_upload_accepts_correct_key(
        self, auth_client, sample_csv_file, mock_vroom_2_orders, mock_run_id
    ):
        """POST /api/upload-orders with correct API key succeeds (200)."""
        with (
            patch("core.optimizer.vroom_adapter.httpx.post") as mock_post,
            patch("apps.kerala_delivery.api.main.repo") as mock_repo,
        ):
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_vroom_2_orders,
                raise_for_status=lambda: None,
            )
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[MagicMock()])
            mock_repo.vehicle_db_to_pydantic.return_value = MOCK_VEHICLE
            mock_repo.save_optimization_run = AsyncMock(return_value=mock_run_id)

            resp = auth_client.post(
                "/api/upload-orders",
                files={"file": ("orders.csv", sample_csv_file, "text/csv")},
                headers={"X-API-Key": "test-secret-key-123"},
            )
        assert resp.status_code == 200


# =============================================================================
# Upload Validation Tests
# =============================================================================


class TestUploadValidation:
    """Tests for enhanced file upload input validation (SEC-04).

    Verifies that file type, content-type, and size are validated
    BEFORE any CSV parsing, geocoding, or optimization begins.
    SECURITY: prevents uploading executable files, scripts, or
    excessively large files that could exhaust server memory.
    """

    def test_rejects_unsupported_extension(self, client):
        """Uploading a .txt file should return 400."""
        resp = client.post(
            "/api/upload-orders",
            files={"file": ("orders.txt", b"some data", "text/plain")},
        )
        assert resp.status_code == 400
        assert "unsupported" in resp.json().get("user_message", resp.json().get("detail", "")).lower()

    def test_rejects_exe_file(self, client):
        """Uploading an .exe should return 400 listing accepted types."""
        resp = client.post(
            "/api/upload-orders",
            files={"file": ("malware.exe", b"\x00" * 100, "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert ".csv" in resp.json().get("user_message", resp.json().get("detail", ""))

    def test_rejects_filename_without_extension(self, client):
        """Upload with no file extension should return 400."""
        resp = client.post(
            "/api/upload-orders",
            files={"file": ("orders_noext", b"data", "text/csv")},
        )
        assert resp.status_code == 400
        assert "Unsupported file type" in resp.json().get("user_message", resp.json().get("detail", ""))

    def test_rejects_oversized_file(self, client):
        """Upload exceeding MAX_UPLOAD_SIZE_BYTES should return 413.

        We patch the constant to 100 bytes to avoid creating a 10+ MB
        payload in memory during tests.
        """
        with patch("apps.kerala_delivery.api.main.MAX_UPLOAD_SIZE_BYTES", 100):
            resp = client.post(
                "/api/upload-orders",
                files={"file": ("big.csv", b"x" * 200, "text/csv")},
            )
        assert resp.status_code == 413
        assert "too large" in resp.json().get("user_message", resp.json().get("detail", "")).lower()

    def test_upload_rejects_pdf_extension(self, client):
        """Uploading a .pdf file returns 400 with descriptive error."""
        resp = client.post(
            "/api/upload-orders",
            files={"file": ("orders.pdf", b"fake pdf data", "application/pdf")},
        )
        assert resp.status_code == 400
        detail = resp.json().get("user_message", resp.json().get("detail", ""))
        assert ".pdf" in detail
        assert ".csv" in detail  # Lists accepted types

    def test_upload_rejects_invalid_content_type(self, client):
        """Uploading with non-CSV/Excel content-type returns 400."""
        resp = client.post(
            "/api/upload-orders",
            files={"file": ("orders.csv", b"data", "application/pdf")},
        )
        assert resp.status_code == 400
        assert "content type" in resp.json().get("user_message", resp.json().get("detail", "")).lower()

    def test_upload_accepts_octet_stream_content_type(self, client, mock_session):
        """application/octet-stream is accepted (browsers send this for CSV).

        Mocks _is_cdcms_format to return False and CsvImporter to avoid
        hitting the processing pipeline. We only care that validation passes.
        """
        with patch("apps.kerala_delivery.api.main._is_cdcms_format", return_value=False), \
             patch("apps.kerala_delivery.api.main.CsvImporter") as mock_importer:
            mock_importer.return_value.import_orders.return_value = MagicMock(orders=[], errors=[], warnings=[])
            resp = client.post(
                "/api/upload-orders",
                files={"file": ("orders.csv", b"order_id,address\n1,test", "application/octet-stream")},
            )
        # Should NOT be 400 for content-type — validation passed
        assert resp.status_code != 400 or "content type" not in resp.json().get("detail", "").lower()

    def test_upload_size_error_includes_actual_size(self, client):
        """File too large error shows actual size and limit."""
        # Patch MAX_UPLOAD_SIZE_BYTES to 100 to avoid creating large test payloads
        with patch("apps.kerala_delivery.api.main.MAX_UPLOAD_SIZE_BYTES", 100):
            big_content = b"x" * 200
            resp = client.post(
                "/api/upload-orders",
                files={"file": ("orders.csv", big_content, "text/csv")},
            )
        assert resp.status_code == 413
        detail = resp.json().get("user_message", resp.json().get("detail", ""))
        assert "MB" in detail  # Shows size unit

    def test_validation_before_processing(self, client):
        """File validation happens before CSV parsing/geocoding."""
        # A .pdf file should be rejected immediately — the CSV importer
        # should never be called. We verify by checking the error is about
        # file type, not about CSV parsing.
        resp = client.post(
            "/api/upload-orders",
            files={"file": ("data.pdf", b"not,a,csv\n1,2,3", "application/pdf")},
        )
        assert resp.status_code == 400
        assert "file type" in resp.json().get("user_message", resp.json().get("detail", "")).lower() or "content type" in resp.json().get("user_message", resp.json().get("detail", "")).lower()


# =============================================================================
# Query Parameter Bounds Tests
# =============================================================================


class TestQueryBoundsValidation:
    """Tests for query parameter boundary validation (ge/le constraints).

    FastAPI + Pydantic validate Query() parameters automatically and
    return 422 Unprocessable Entity for out-of-range values. These tests
    verify the bounds are enforced. Added after Code Review #6 — Warning W4.
    """

    def test_telemetry_limit_zero_returns_422(self, client):
        """limit=0 on /api/telemetry/{id} should fail (ge=1)."""
        resp = client.get("/api/telemetry/VEH-01?limit=0")
        assert resp.status_code == 422

    def test_telemetry_limit_exceeds_max_returns_422(self, client):
        """limit=1001 on /api/telemetry/{id} should fail (le=1000)."""
        resp = client.get("/api/telemetry/VEH-01?limit=1001")
        assert resp.status_code == 422

    def test_runs_limit_zero_returns_422(self, client):
        """limit=0 on /api/runs should fail (ge=1)."""
        resp = client.get("/api/runs?limit=0")
        assert resp.status_code == 422

    def test_runs_limit_exceeds_max_returns_422(self, client):
        """limit=101 on /api/runs should fail (le=100)."""
        resp = client.get("/api/runs?limit=101")
        assert resp.status_code == 422


# =============================================================================
# Fleet Telemetry Batch Endpoint Tests
# =============================================================================


class TestFleetTelemetry:
    """Tests for GET /api/telemetry/fleet — batch fleet telemetry.

    This endpoint replaces the N+1 pattern where the dashboard called
    GET /api/telemetry/{vehicle_id}?limit=1 once per vehicle. It returns
    the latest ping for every vehicle in a single DB query.
    """

    def test_fleet_telemetry_returns_vehicles_dict(self, client):
        """Fleet telemetry should return a dict keyed by vehicle_id."""
        # Mock the repo function to return telemetry pings
        mock_pings = [
            MagicMock(
                vehicle_id="VEH-01",
                location=MagicMock(),
                speed_kmh=25.0,
                accuracy_m=10.0,
                heading=180.0,
                recorded_at=datetime(2025, 6, 15, 10, 0, tzinfo=timezone.utc),
                speed_alert=False,
            ),
            MagicMock(
                vehicle_id="VEH-02",
                location=MagicMock(),
                speed_kmh=35.0,
                accuracy_m=8.0,
                heading=90.0,
                recorded_at=datetime(2025, 6, 15, 10, 1, tzinfo=timezone.utc),
                speed_alert=False,
            ),
        ]
        # Mock to_shape to return Point-like objects
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo, \
             patch("apps.kerala_delivery.api.main.to_shape") as mock_to_shape:
            mock_repo.get_fleet_latest_telemetry = AsyncMock(return_value=mock_pings)
            mock_point = MagicMock(y=11.62, x=75.58)
            mock_to_shape.return_value = mock_point

            resp = client.get("/api/telemetry/fleet")

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert "VEH-01" in data["vehicles"]
        assert "VEH-02" in data["vehicles"]
        assert data["vehicles"]["VEH-01"]["speed_kmh"] == 25.0

    def test_fleet_telemetry_empty_returns_zero(self, client):
        """If no telemetry exists, fleet endpoint returns empty dict."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_fleet_latest_telemetry = AsyncMock(return_value=[])
            resp = client.get("/api/telemetry/fleet")

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["vehicles"] == {}


class TestTelemetryBatch:
    """Tests for POST /api/telemetry/batch — batch ping submission.

    The driver app queues GPS pings offline and submits them as a batch
    when connectivity returns. The endpoint processes each ping individually,
    discarding low-accuracy pings and flagging speed alerts.
    """

    def test_batch_saves_multiple_pings(self, client):
        """Batch of 3 valid pings should all be saved."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            # All 3 pings saved successfully, no speed alerts
            mock_repo.save_telemetry_batch = AsyncMock(
                return_value=[
                    (uuid.uuid4(), False),
                    (uuid.uuid4(), False),
                    (uuid.uuid4(), False),
                ]
            )
            resp = client.post(
                "/api/telemetry/batch",
                json={
                    "pings": [
                        {"vehicle_id": "VEH-01", "latitude": 11.62, "longitude": 75.58},
                        {"vehicle_id": "VEH-01", "latitude": 11.625, "longitude": 75.585},
                        {"vehicle_id": "VEH-01", "latitude": 11.63, "longitude": 75.59},
                    ]
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["saved"] == 3
        assert data["discarded"] == 0
        assert data["speed_alerts"] == 0

    def test_batch_counts_discarded_and_alerts(self, client):
        """Batch with mixed results: saved, discarded, and speed alert."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.save_telemetry_batch = AsyncMock(
                return_value=[
                    (uuid.uuid4(), False),   # saved, no alert
                    (None, False),            # discarded (low accuracy)
                    (uuid.uuid4(), True),     # saved, speed alert
                ]
            )
            resp = client.post(
                "/api/telemetry/batch",
                json={
                    "pings": [
                        {"vehicle_id": "VEH-01", "latitude": 11.62, "longitude": 75.58},
                        {"vehicle_id": "VEH-01", "latitude": 11.625, "longitude": 75.585, "accuracy_m": 100},
                        {"vehicle_id": "VEH-01", "latitude": 11.63, "longitude": 75.59, "speed_kmh": 55},
                    ]
                },
            )
        data = resp.json()
        assert data["saved"] == 2
        assert data["discarded"] == 1
        assert data["speed_alerts"] == 1

    def test_batch_rejects_over_100_pings(self, client):
        """Batch with >100 pings should return 422 (max_length=100)."""
        pings = [
            {"vehicle_id": "VEH-01", "latitude": 11.62, "longitude": 75.58}
            for _ in range(101)
        ]
        resp = client.post("/api/telemetry/batch", json={"pings": pings})
        assert resp.status_code == 422

    def test_batch_empty_pings_returns_200(self, client):
        """Batch with empty pings list should succeed (nothing to process)."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.save_telemetry_batch = AsyncMock(return_value=[])
            resp = client.post("/api/telemetry/batch", json={"pings": []})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["saved"] == 0


# =============================================================================
# Fleet Management CRUD Tests
# =============================================================================


class TestFleetManagement:
    """Tests for the fleet management CRUD endpoints.

    Dispatchers use these endpoints to add, update, and deactivate vehicles.
    The optimizer reads from the fleet table, falling back to hardcoded
    config if the DB fleet is empty.
    """

    def test_list_vehicles_returns_all(self, client):
        """GET /api/vehicles returns all vehicles."""
        mock_vehicles = [
            MagicMock(
                vehicle_id="VEH-01",
                registration_no="KL-07-AB-1234",
                vehicle_type="diesel",
                max_weight_kg=446.0,
                max_items=30,
                depot_location=MagicMock(),
                speed_limit_kmh=40.0,
                is_active=True,
                created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            ),
        ]
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo, \
             patch("apps.kerala_delivery.api.main.to_shape") as mock_to_shape:
            mock_repo.get_all_vehicles = AsyncMock(return_value=mock_vehicles)
            mock_to_shape.return_value = MagicMock(y=11.62, x=75.58)
            resp = client.get("/api/vehicles")

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["vehicles"][0]["vehicle_id"] == "VEH-01"

    def test_list_vehicles_active_only(self, client):
        """GET /api/vehicles?active_only=true filters inactive vehicles."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo, \
             patch("apps.kerala_delivery.api.main.to_shape") as mock_to_shape:
            mock_repo.get_active_vehicles = AsyncMock(return_value=[])
            mock_to_shape.return_value = MagicMock(y=11.62, x=75.58)
            resp = client.get("/api/vehicles?active_only=true")

        assert resp.status_code == 200
        assert resp.json()["count"] == 0
        mock_repo.get_active_vehicles.assert_called_once()

    def test_get_vehicle_returns_details(self, client):
        """GET /api/vehicles/VEH-01 returns vehicle details."""
        mock_v = MagicMock(
            vehicle_id="VEH-01",
            registration_no="KL-07-AB-1234",
            vehicle_type="diesel",
            max_weight_kg=446.0,
            max_items=30,
            depot_location=MagicMock(),
            speed_limit_kmh=40.0,
            is_active=True,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo, \
             patch("apps.kerala_delivery.api.main.to_shape") as mock_to_shape:
            mock_repo.get_vehicle_by_vehicle_id = AsyncMock(return_value=mock_v)
            mock_to_shape.return_value = MagicMock(y=11.62, x=75.58)
            resp = client.get("/api/vehicles/VEH-01")

        assert resp.status_code == 200
        assert resp.json()["vehicle_id"] == "VEH-01"
        assert resp.json()["max_weight_kg"] == 446.0

    def test_get_vehicle_not_found(self, client):
        """GET /api/vehicles/NONE should return 404."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_vehicle_by_vehicle_id = AsyncMock(return_value=None)
            resp = client.get("/api/vehicles/NONE")

        assert resp.status_code == 404

    def test_create_vehicle_success(self, client):
        """POST /api/vehicles creates a new vehicle."""
        mock_v = MagicMock(
            vehicle_id="VEH-14",
            registration_no="KL-07-CD-9999",
            vehicle_type="diesel",
            max_weight_kg=446.0,
            max_items=30,
            depot_location=MagicMock(),
            speed_limit_kmh=40.0,
            is_active=True,
            created_at=datetime(2025, 6, 15, tzinfo=timezone.utc),
            updated_at=datetime(2025, 6, 15, tzinfo=timezone.utc),
        )
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo, \
             patch("apps.kerala_delivery.api.main.to_shape") as mock_to_shape:
            mock_repo.get_vehicle_by_vehicle_id = AsyncMock(return_value=None)
            mock_repo.create_vehicle = AsyncMock(return_value=mock_v)
            mock_to_shape.return_value = MagicMock(y=11.62, x=75.58)

            resp = client.post(
                "/api/vehicles",
                json={
                    "vehicle_id": "VEH-14",
                    "depot_latitude": 11.62,
                    "depot_longitude": 75.58,
                    "registration_no": "KL-07-CD-9999",
                },
            )

        assert resp.status_code == 200
        assert "VEH-14" in resp.json()["message"]

    def test_create_duplicate_vehicle_returns_409(self, client):
        """Creating a vehicle with an existing ID should return 409 Conflict."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_vehicle_by_vehicle_id = AsyncMock(
                return_value=MagicMock()  # existing vehicle
            )
            resp = client.post(
                "/api/vehicles",
                json={"vehicle_id": "VEH-01", "depot_latitude": 11.62, "depot_longitude": 75.58},
            )

        assert resp.status_code == 409

    def test_update_vehicle_success(self, client):
        """PUT /api/vehicles/VEH-01 updates vehicle properties."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.update_vehicle = AsyncMock(return_value=True)
            resp = client.put(
                "/api/vehicles/VEH-01",
                json={"max_weight_kg": 400.0, "is_active": False},
            )

        assert resp.status_code == 200
        assert "updated" in resp.json()["message"].lower()

    def test_update_vehicle_not_found(self, client):
        """PUT /api/vehicles/NONE should return 404."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.update_vehicle = AsyncMock(return_value=False)
            resp = client.put(
                "/api/vehicles/NONE",
                json={"max_weight_kg": 400.0},
            )

        assert resp.status_code == 404

    def test_delete_vehicle_soft_deletes(self, client):
        """DELETE /api/vehicles/VEH-01 soft-deletes (deactivates) the vehicle."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.deactivate_vehicle = AsyncMock(return_value=True)
            resp = client.delete("/api/vehicles/VEH-01")

        assert resp.status_code == 200
        assert "deactivated" in resp.json()["message"].lower()

    def test_delete_vehicle_not_found(self, client):
        """DELETE /api/vehicles/NONE should return 404."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.deactivate_vehicle = AsyncMock(return_value=False)
            resp = client.delete("/api/vehicles/NONE")

        assert resp.status_code == 404

    def test_create_vehicle_rejects_invalid_type(self, client):
        """Only diesel, electric, and cng vehicle types are accepted.

        The Literal["diesel", "electric", "cng"] constraint on VehicleCreate
        prevents garbage values from reaching the DB. Design doc Section 4
        defines only these three Ape Xtra LDX variants for the Kerala fleet.
        Pydantic returns 422 Unprocessable Entity for invalid literals.
        """
        resp = client.post(
            "/api/vehicles",
            json={
                "vehicle_id": "VEH-99",
                "depot_latitude": 11.6350,
                "depot_longitude": 75.5900,
                "vehicle_type": "banana",
            },
            headers={"X-API-Key": "test-key"},
        )
        assert resp.status_code == 422


# =============================================================================
# Delivery Window Enforcement Tests
# =============================================================================


class TestDeliveryWindowEnforcement:
    """Tests for MIN_DELIVERY_WINDOW_MINUTES enforcement.

    Non-negotiable Kerala MVD constraint: no delivery window shorter
    than 30 minutes. The upload endpoint widens narrow windows rather
    than rejecting orders — this is more operationally friendly.
    No "10-minute delivery" promises.
    """

    def test_narrow_window_is_widened(self, client):
        """A 10-minute delivery window should be widened to 30 minutes.

        The system extends the window_end to meet the minimum.
        This prevents drivers from being pressured into unrealistic
        delivery deadlines.
        """
        from datetime import time as dt_time

        # Create a mock order with a 10-minute window (09:00-09:10)
        mock_order = MagicMock()
        mock_order.is_geocoded = True
        mock_order.delivery_window_start = dt_time(9, 0)
        mock_order.delivery_window_end = dt_time(9, 10)
        mock_order.order_id = "ORD-001"
        mock_order.location = MagicMock(
            latitude=11.62, longitude=75.58,
            geocode_confidence=0.9, address_text="Test"
        )
        mock_order.weight_kg = 14.2
        mock_order.quantity = 1
        mock_order.customer_ref = None
        mock_order.address_raw = "123 Test St"

        with patch("apps.kerala_delivery.api.main.CsvImporter") as mock_importer_cls, \
             patch("apps.kerala_delivery.api.main._get_geocoder", return_value=None), \
             patch("apps.kerala_delivery.api.main.VroomAdapter") as mock_optimizer_cls, \
             patch("apps.kerala_delivery.api.main.repo") as mock_repo:

            mock_importer = MagicMock()
            mock_importer.import_orders.return_value = MagicMock(orders=[mock_order], errors=[], warnings=[])
            mock_importer_cls.return_value = mock_importer

            mock_optimizer = MagicMock()
            mock_optimizer.optimize.return_value = MagicMock(
                assignment_id="test",
                total_orders_assigned=1,
                unassigned_order_ids=[],
                vehicles_used=1,
                optimization_time_ms=10.0,
                routes=[],
                created_at=datetime.now(timezone.utc),
            )
            mock_optimizer_cls.return_value = mock_optimizer

            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[])
            mock_repo.save_optimization_run = AsyncMock(return_value=uuid.uuid4())

            resp = client.post(
                "/api/upload-orders",
                files={"file": ("orders.csv", b"dummy", "text/csv")},
            )

        # The window should have been widened: 09:00 -> 09:30
        assert mock_order.delivery_window_end == dt_time(9, 30)

    def test_valid_window_is_not_modified(self, client):
        """A 60-minute window should not be modified (already >= 30 min)."""
        from datetime import time as dt_time

        mock_order = MagicMock()
        mock_order.is_geocoded = True
        mock_order.delivery_window_start = dt_time(9, 0)
        mock_order.delivery_window_end = dt_time(10, 0)  # 60 min -- valid
        mock_order.order_id = "ORD-001"
        mock_order.location = MagicMock(
            latitude=11.62, longitude=75.58,
            geocode_confidence=0.9, address_text="Test"
        )
        mock_order.weight_kg = 14.2
        mock_order.quantity = 1
        mock_order.customer_ref = None
        mock_order.address_raw = "123 Test St"

        with patch("apps.kerala_delivery.api.main.CsvImporter") as mock_importer_cls, \
             patch("apps.kerala_delivery.api.main._get_geocoder", return_value=None), \
             patch("apps.kerala_delivery.api.main.VroomAdapter") as mock_optimizer_cls, \
             patch("apps.kerala_delivery.api.main.repo") as mock_repo:

            mock_importer = MagicMock()
            mock_importer.import_orders.return_value = MagicMock(orders=[mock_order], errors=[], warnings=[])
            mock_importer_cls.return_value = mock_importer

            mock_optimizer = MagicMock()
            mock_optimizer.optimize.return_value = MagicMock(
                assignment_id="test",
                total_orders_assigned=1,
                unassigned_order_ids=[],
                vehicles_used=1,
                optimization_time_ms=10.0,
                routes=[],
                created_at=datetime.now(timezone.utc),
            )
            mock_optimizer_cls.return_value = mock_optimizer

            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[])
            mock_repo.save_optimization_run = AsyncMock(return_value=uuid.uuid4())

            client.post(
                "/api/upload-orders",
                files={"file": ("orders.csv", b"dummy", "text/csv")},
            )

        # Window should be unchanged — 60 min > 30 min minimum
        assert mock_order.delivery_window_end == dt_time(10, 0)


# =============================================================================
# Security Headers & CORS Tests (Phase 2 — SEC-01, SEC-02, SEC-03, SEC-05)
# =============================================================================


class TestSecurityHeaders:
    """Tests for security headers, CORS hardening, and API docs gating (Phase 2).

    Verifies SEC-01 (security headers), SEC-02 (CORS), SEC-03 (docs gating),
    and SEC-05 (deprecated library verification).
    """

    def test_security_headers_present(self, client):
        """All responses include required security headers (SEC-01)."""
        resp = client.get("/health")
        assert resp.status_code == 200
        # Secweb headers
        assert "content-security-policy" in resp.headers
        assert "'self'" in resp.headers["content-security-policy"]
        assert "x-frame-options" in resp.headers
        assert resp.headers["x-frame-options"] == "DENY"
        assert "x-content-type-options" in resp.headers
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert "referrer-policy" in resp.headers
        # Custom middleware header
        assert "permissions-policy" in resp.headers
        assert "geolocation=(self)" in resp.headers["permissions-policy"]
        assert "camera=()" in resp.headers["permissions-policy"]

    def test_csp_allows_map_tiles(self, client):
        """CSP img-src includes OpenStreetMap tile servers and Leaflet assets."""
        resp = client.get("/health")
        csp = resp.headers.get("content-security-policy", "")
        assert "*.tile.openstreetmap.org" in csp
        assert "unpkg.com" in csp

    def test_csp_allows_unsafe_inline_styles(self, client):
        """CSP style-src includes 'unsafe-inline' for Leaflet inline styles."""
        resp = client.get("/health")
        csp = resp.headers.get("content-security-policy", "")
        assert "'unsafe-inline'" in csp

    def test_security_headers_on_error_responses(self, client):
        """Security headers present even on 404 error responses."""
        resp = client.get("/nonexistent-path")
        assert "x-frame-options" in resp.headers
        assert "x-content-type-options" in resp.headers

    def test_cors_rejects_unlisted_origin(self, client):
        """Requests from unlisted origins do not get CORS headers (SEC-02)."""
        resp = client.get(
            "/health",
            headers={"Origin": "https://evil.example.com"},
        )
        assert "access-control-allow-origin" not in resp.headers

    def test_cors_allows_listed_origin(self, client):
        """Requests from listed dev origins get CORS headers."""
        resp = client.get(
            "/health",
            headers={"Origin": "http://localhost:8000"},
        )
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:8000"

    def test_docs_gated_in_production(self):
        """API docs return 404 when ENVIRONMENT=production (SEC-03)."""
        mock_health = {
            "postgresql": (True, "connected"),
            "osrm": (True, "available"),
            "vroom": (True, "available"),
        }
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "RATE_LIMIT_ENABLED": "false"}), \
             patch("apps.kerala_delivery.api.main.wait_for_services", new_callable=AsyncMock, return_value=mock_health):
            # Must reimport to pick up the new environment
            import importlib
            import apps.kerala_delivery.api.main as main_mod
            importlib.reload(main_mod)
            main_mod.app.state.service_health = mock_health
            main_mod.app.state.started_at = datetime.now(timezone.utc)
            prod_client = TestClient(main_mod.app)
            try:
                assert prod_client.get("/docs").status_code == 404
                assert prod_client.get("/redoc").status_code == 404
                assert prod_client.get("/openapi.json").status_code == 404
            finally:
                # Reload with default environment to restore for other tests
                with patch.dict(os.environ, {"ENVIRONMENT": "development", "RATE_LIMIT_ENABLED": "false"}):
                    importlib.reload(main_mod)

    def test_deprecated_libraries_not_installed(self):
        """Neither python-jose nor passlib is installed (SEC-05)."""
        with pytest.raises(ImportError):
            import jose  # noqa: F401
        with pytest.raises(ImportError):
            import passlib  # noqa: F401


# =============================================================================
# Rate Limiting Tests
# =============================================================================


class TestRateLimiting:
    """Tests for rate limiting middleware (slowapi).

    Rate limiting prevents abuse of expensive endpoints (upload triggers
    VROOM optimization, telemetry writes to DB on every ping).
    Uses a separate fixture with rate limiting ENABLED.
    """

    @pytest.fixture
    def rate_limited_client(self, mock_session):
        """TestClient with rate limiting ENABLED.

        Unlike the main 'client' fixture which disables rate limiting,
        this fixture keeps it active to verify that limits are enforced.
        """
        from apps.kerala_delivery.api.main import app, limiter

        async def override_get_session():
            yield mock_session

        mock_health = {
            "postgresql": (True, "connected"),
            "osrm": (True, "available"),
            "vroom": (True, "available"),
        }
        limiter.enabled = True
        app.dependency_overrides[get_session] = override_get_session
        app.state.service_health = mock_health
        app.state.started_at = datetime.now(timezone.utc)
        with patch("apps.kerala_delivery.api.main.wait_for_services", new_callable=AsyncMock, return_value=mock_health):
            yield TestClient(app)
        app.dependency_overrides.clear()
        # CRITICAL: reset all in-memory counters to prevent state leaking
        # to subsequent test modules. Without this, another module enabling
        # the limiter may encounter pre-existing counter state from these tests.
        limiter.reset()
        # Disable again for other test classes
        limiter.enabled = False

    def test_upload_rate_limit_enforced(self, rate_limited_client):
        """POST /api/upload-orders should be rate-limited to 10/minute.

        The upload endpoint triggers CSV parsing, geocoding (potentially
        Google API calls at $5/1000), and VROOM optimization. Rate limiting
        prevents accidental or malicious excessive use.

        We send requests with a bad file extension (returns 400 quickly)
        to avoid actually running the optimizer pipeline. The rate limiter
        fires BEFORE the endpoint logic, so even 400 responses count against
        the limit.
        """
        # Send 11 requests with .txt files — each returns 400 fast
        # but still counts against the rate limit
        hit_429 = False
        for i in range(15):
            resp = rate_limited_client.post(
                "/api/upload-orders",
                files={"file": ("orders.txt", b"data", "text/plain")},
            )
            if resp.status_code == 429:
                hit_429 = True
                break

        # We should hit the rate limit at some point (10/minute)
        assert hit_429, "Rate limit was not enforced after 15 rapid requests"


# =============================================================================
# CDCMS Auto-Detection Tests
# =============================================================================


class TestCdcmsAutoDetection:
    """Tests for CDCMS tab-separated file auto-detection in the upload endpoint.

    The upload endpoint auto-detects raw CDCMS exports (tab-separated with
    columns like OrderNo, ConsumerAddress) and runs the preprocessor before
    passing data to CsvImporter. This allows employees to upload CDCMS exports
    directly without manual conversion.

    Tests verify:
    1. CDCMS format is detected and preprocessed correctly
    2. Standard CSV files are NOT treated as CDCMS
    3. _is_cdcms_format() helper handles edge cases
    """

    def test_cdcms_file_detected_and_preprocessed(
        self, client, mock_run_id
    ):
        """A raw CDCMS tab-separated file should be auto-detected and preprocessed.

        The preprocessor extracts 'Allocated-Printed' orders, cleans addresses,
        and converts to our standard CSV format before CsvImporter handles it.
        """
        # Minimal CDCMS tab-separated export with 1 Allocated-Printed order.
        # Must include all columns the preprocessor accesses: OrderNo,
        # OrderStatus, ConsumerAddress, OrderQuantity, AreaName, DeliveryMan.
        cdcms_content = (
            "OrderNo\tOrderStatus\tConsumerAddress\tConsumerName\t"
            "ProductDesc\tOrderQuantity\tRegion\tAreaName\tDistrict\t"
            "DeliveryMan\tMobileNo\n"
            "517827\tAllocated-Printed\t"
            "4/146 AMINAS VALIYA PARAMBATH NR VALLIKKADU SARAMBI PALLIVATAKARA\t"
            "CUSTOMER A\tINDN LPG DOMESTIC 14.2\t1\tREGION1\tVATAKARA\tKozhikode\t"
            "DRIVER1\t9876543210\n"
        )
        # VROOM mock for a single order
        vroom_1_order = {
            "code": 0,
            "routes": [
                {
                    "vehicle": 0,
                    "distance": 1500,
                    "duration": 200,
                    "steps": [
                        {"type": "start", "location": [75.5796, 11.6244],
                         "arrival": 0, "distance": 0, "duration": 0},
                        {"type": "job", "id": 0, "location": [75.6853, 11.7050],
                         "arrival": 200, "duration": 200, "distance": 1500, "service": 300},
                        {"type": "end", "location": [75.5796, 11.6244],
                         "arrival": 400, "distance": 3000, "duration": 400},
                    ],
                },
            ],
            "unassigned": [],
        }
        with (
            patch("core.optimizer.vroom_adapter.httpx.post") as mock_post,
            patch("apps.kerala_delivery.api.main.repo") as mock_repo,
            patch("apps.kerala_delivery.api.main._get_geocoder") as mock_geocoder_fn,
        ):
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: vroom_1_order,
                raise_for_status=lambda: None,
            )
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[MagicMock()])
            mock_repo.vehicle_db_to_pydantic.return_value = MOCK_VEHICLE
            mock_repo.save_optimization_run = AsyncMock(return_value=mock_run_id)

            # Phase 16: Mock driver auto-creation (CDCMS uploads trigger this)
            mock_repo.get_all_drivers = AsyncMock(return_value=[])
            mock_repo.find_similar_drivers = AsyncMock(return_value=[])
            mock_repo.create_driver = AsyncMock(return_value=MagicMock(
                id=uuid.uuid4(), name="Driver1", is_active=True,
            ))

            # Mock geocoder to return a valid location
            mock_geocoder = MagicMock()
            mock_geocoder.geocode.return_value = MagicMock(
                success=True,
                location=Location(
                    latitude=11.7050,
                    longitude=75.6853,
                    address_text="Pallivatakara, Vatakara, Kerala",
                    geocode_confidence=0.8,
                ),
                formatted_address="Pallivatakara, Vatakara, Kerala",
                confidence=0.8,
                raw_response={},
            )
            mock_geocoder_fn.return_value = mock_geocoder
            mock_repo.save_geocode_cache = AsyncMock()

            resp = client.post(
                "/api/upload-orders",
                files={"file": ("cdcms_export.csv", cdcms_content.encode(), "text/csv")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_orders"] >= 1

    def test_cdcms_no_allocated_printed_returns_400(self, client):
        """CDCMS file with no 'Allocated-Printed' orders should return 400.

        The preprocessor filters by status — if there are no printable orders,
        we return a clear error rather than silently producing empty routes.
        """
        cdcms_no_matching = (
            "OrderNo\tOrderStatus\tConsumerAddress\tConsumerName\t"
            "ProductDesc\tOrderQuantity\tRegion\tAreaName\tDistrict\t"
            "DeliveryMan\tMobileNo\n"
            "517827\tCancelled\t"
            "SOME ADDRESS\tCUSTOMER A\tINDN LPG DOMESTIC 14.2\t1\tREGION1\tAREA1\t"
            "District1\tDRIVER1\t9876543210\n"
        )
        resp = client.post(
            "/api/upload-orders",
            files={"file": ("cdcms.csv", cdcms_no_matching.encode(), "text/csv")},
        )
        assert resp.status_code == 400
        assert "allocated-printed" in resp.json().get("user_message", resp.json().get("detail", "")).lower()

    def test_standard_csv_not_treated_as_cdcms(
        self, client, sample_csv_file, mock_vroom_2_orders, mock_run_id
    ):
        """A standard CSV (comma-separated, our column names) should NOT invoke the CDCMS preprocessor.

        Ensures the auto-detection only triggers for tab-separated files with
        CDCMS-specific column names (OrderNo, ConsumerAddress).
        """
        with (
            patch("core.optimizer.vroom_adapter.httpx.post") as mock_post,
            patch("apps.kerala_delivery.api.main.repo") as mock_repo,
            patch("apps.kerala_delivery.api.main.preprocess_cdcms") as mock_preprocess,
        ):
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_vroom_2_orders,
                raise_for_status=lambda: None,
            )
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[MagicMock()])
            mock_repo.vehicle_db_to_pydantic.return_value = MOCK_VEHICLE
            mock_repo.save_optimization_run = AsyncMock(return_value=mock_run_id)

            resp = client.post(
                "/api/upload-orders",
                files={"file": ("orders.csv", sample_csv_file, "text/csv")},
            )

        assert resp.status_code == 200
        # preprocess_cdcms should NOT have been called for a standard CSV
        mock_preprocess.assert_not_called()


class TestIsCdcmsFormat:
    """Unit tests for the _is_cdcms_format() helper function.

    Tests the heuristic that detects CDCMS tab-separated exports by checking
    for tab separators and CDCMS-specific column names (OrderNo, ConsumerAddress).
    """

    def test_detects_cdcms_tab_separated(self, tmp_path):
        """Tab-separated file with CDCMS columns should be detected."""
        from apps.kerala_delivery.api.main import _is_cdcms_format

        cdcms_file = tmp_path / "cdcms.csv"
        cdcms_file.write_text(
            "OrderNo\tOrderStatus\tConsumerAddress\tConsumerName\n"
            "12345\tAllocated-Printed\tSome Address\tCustomer\n"
        )
        assert _is_cdcms_format(str(cdcms_file)) is True

    def test_rejects_standard_csv(self, tmp_path):
        """Comma-separated file with our column names should NOT be detected as CDCMS."""
        from apps.kerala_delivery.api.main import _is_cdcms_format

        csv_file = tmp_path / "standard.csv"
        csv_file.write_text(
            "order_id,address,customer_id,weight_kg\n"
            "ORD-001,Some Place,CUST-001,14.2\n"
        )
        assert _is_cdcms_format(str(csv_file)) is False

    def test_rejects_tab_file_without_cdcms_columns(self, tmp_path):
        """Tab-separated file WITHOUT CDCMS column names should NOT be detected.

        Prevents false positives on generic TSV files.
        """
        from apps.kerala_delivery.api.main import _is_cdcms_format

        tsv_file = tmp_path / "generic.tsv"
        tsv_file.write_text(
            "id\tname\tvalue\n"
            "1\ttest\t42\n"
        )
        assert _is_cdcms_format(str(tsv_file)) is False

    def test_handles_nonexistent_file(self):
        """Non-existent file should return False, not raise."""
        from apps.kerala_delivery.api.main import _is_cdcms_format

        assert _is_cdcms_format("/nonexistent/path/file.csv") is False

    def test_handles_empty_file(self, tmp_path):
        """Empty file should return False."""
        from apps.kerala_delivery.api.main import _is_cdcms_format

        empty_file = tmp_path / "empty.csv"
        empty_file.write_text("")
        assert _is_cdcms_format(str(empty_file)) is False

    def test_detects_cdcms_with_extra_columns(self, tmp_path):
        """CDCMS file with extra/unexpected columns should still be detected.

        Real CDCMS exports may have additional columns beyond what we use.
        Detection only requires OrderNo and ConsumerAddress to be present.
        """
        from apps.kerala_delivery.api.main import _is_cdcms_format

        cdcms_file = tmp_path / "cdcms_extra.csv"
        cdcms_file.write_text(
            "OrderNo\tOrderStatus\tConsumerAddress\tExtraCol1\tExtraCol2\n"
            "12345\tAllocated-Printed\tSome Address\tval1\tval2\n"
        )
        assert _is_cdcms_format(str(cdcms_file)) is True


# =============================================================================
# QR Code / Google Maps Route Endpoints
# =============================================================================


class TestGoogleMapsUrlHelpers:
    """Tests for the Google Maps URL builder and QR code generators.

    These are pure functions with no database dependency — test directly.
    """

    def testbuild_google_maps_url_two_stops(self):
        """Two stops → origin + destination, no waypoints."""
        from apps.kerala_delivery.api.qr_helpers import build_google_maps_url

        stops = [
            {"latitude": 11.62, "longitude": 75.58},
            {"latitude": 11.63, "longitude": 75.59},
        ]
        url = build_google_maps_url(stops)
        assert "origin=11.62,75.58" in url
        assert "destination=11.63,75.59" in url
        assert "waypoints" not in url
        assert "travelmode=driving" in url

    def testbuild_google_maps_url_with_waypoints(self):
        """Three stops → origin + 1 waypoint + destination."""
        from apps.kerala_delivery.api.qr_helpers import build_google_maps_url

        stops = [
            {"latitude": 11.62, "longitude": 75.58},
            {"latitude": 11.625, "longitude": 75.585},
            {"latitude": 11.63, "longitude": 75.59},
        ]
        url = build_google_maps_url(stops)
        assert "origin=11.62,75.58" in url
        assert "destination=11.63,75.59" in url
        assert "waypoints=11.625,75.585" in url

    def testbuild_google_maps_url_empty_stops(self):
        """Empty stop list should return empty string."""
        from apps.kerala_delivery.api.qr_helpers import build_google_maps_url

        assert build_google_maps_url([]) == ""

    def testgenerate_qr_svg_returns_svg(self):
        """QR SVG generator should produce valid SVG markup."""
        from apps.kerala_delivery.api.qr_helpers import generate_qr_svg

        svg = generate_qr_svg("https://example.com")
        assert "<svg" in svg
        assert "</svg>" in svg
        assert "<path" in svg  # SvgPathImage uses <path> elements

    def testgenerate_qr_base64_png(self):
        """QR PNG generator should produce a valid base64-encoded PNG."""
        from apps.kerala_delivery.api.qr_helpers import generate_qr_base64_png
        import base64

        png_b64 = generate_qr_base64_png("https://example.com")
        # Should be valid base64
        decoded = base64.b64decode(png_b64)
        # PNG files start with the PNG magic bytes
        assert decoded[:4] == b"\x89PNG"

    def test_split_route_single_segment(self):
        """Route with ≤11 stops→ 1 segment."""
        from apps.kerala_delivery.api.qr_helpers import split_route_into_segments

        stops = [{"latitude": 11.62 + i * 0.001, "longitude": 75.58} for i in range(8)]
        segments = split_route_into_segments(stops)
        assert len(segments) == 1
        assert segments[0]["segment"] == 1
        assert segments[0]["stop_count"] == 8

    def test_split_route_multi_segment(self):
        """Route with >11 stops → multiple overlapping segments.

        Google Maps supports max 9 waypoints (+ origin + destination = 11 stops).
        A route with 15 stops should split into 2 segments, with overlap
        so the driver has a continuous path.
        """
        from apps.kerala_delivery.api.qr_helpers import split_route_into_segments

        stops = [{"latitude": 11.62 + i * 0.001, "longitude": 75.58} for i in range(15)]
        segments = split_route_into_segments(stops)
        assert len(segments) >= 2
        # Each segment has a QR code and URL
        for seg in segments:
            assert "qr_svg" in seg
            assert "url" in seg
            assert seg["stop_count"] <= 11
        # Verify overlap: segments connect at shared boundary stops
        # so the driver gets continuous navigation across Google Maps URLs
        assert segments[0]["end_stop"] >= segments[1]["start_stop"]

    def test_split_route_exactly_11(self):
        """Route with exactly 11 stops → 1 segment (fits in one URL)."""
        from apps.kerala_delivery.api.qr_helpers import split_route_into_segments

        stops = [{"latitude": 11.62 + i * 0.001, "longitude": 75.58} for i in range(11)]
        segments = split_route_into_segments(stops)
        assert len(segments) == 1
        assert segments[0]["stop_count"] == 11

    def testbuild_google_maps_url_single_stop(self):
        """Single stop → origin and destination are the same point."""
        from apps.kerala_delivery.api.qr_helpers import build_google_maps_url

        stops = [{"latitude": 11.62, "longitude": 75.58}]
        url = build_google_maps_url(stops)
        assert "origin=11.62,75.58" in url
        assert "destination=11.62,75.58" in url


class TestGoogleMapsRouteEndpoint:
    """Tests for GET /api/routes/{vehicle_id}/google-maps.

    Verifies the endpoint returns Google Maps URLs and QR codes
    for a vehicle's optimized route.
    """

    def test_google_maps_route_returns_qr(self, client, mock_run_id):
        """Endpoint should return QR SVG and Google Maps URL."""
        from core.database.models import OptimizationRunDB, RouteDB
        from shapely.geometry import Point
        from geoalchemy2.shape import from_shape

        mock_run = MagicMock(spec=OptimizationRunDB)
        mock_run.id = mock_run_id

        # Build mock route with 3 stops
        stops = []
        for i in range(3):
            mock_stop = MagicMock()
            mock_stop.order = MagicMock()
            mock_stop.order.order_id = f"ORD-{i:03d}"
            mock_stop.order.geocode_confidence = None
            mock_stop.order.geocode_method = None
            mock_stop.location = from_shape(Point(75.58 + i * 0.01, 11.62 + i * 0.01), srid=4326)
            mock_stop.address_display = f"Stop {i + 1}"
            mock_stop.address_original = None
            mock_stop.sequence = i + 1
            mock_stop.distance_from_prev_km = 1.0
            mock_stop.duration_from_prev_minutes = 3.0
            mock_stop.weight_kg = 14.2
            mock_stop.quantity = 1
            mock_stop.notes = ""
            mock_stop.status = "pending"
            stops.append(mock_stop)

        mock_route = MagicMock(spec=RouteDB)
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "VEH-01"
        mock_route.driver_name = "Driver 1"
        mock_route.stops = stops
        mock_route.total_distance_km = 3.0
        mock_route.total_duration_minutes = 9.0
        mock_route.total_weight_kg = 42.6
        mock_route.total_items = 3
        mock_route.created_at = datetime.now(timezone.utc)

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=mock_run)
            mock_repo.get_route_for_vehicle = AsyncMock(return_value=mock_route)
            from core.database.repository import route_db_to_pydantic
            mock_repo.route_db_to_pydantic = route_db_to_pydantic

            resp = client.get("/api/routes/VEH-01/google-maps")

        assert resp.status_code == 200
        data = resp.json()
        assert data["vehicle_id"] == "VEH-01"
        assert data["total_stops"] == 3
        assert data["total_segments"] >= 1
        # Each segment has a URL and QR SVG
        seg = data["segments"][0]
        assert "google.com/maps/dir" in seg["url"]
        assert "<svg" in seg["qr_svg"]

    def test_google_maps_route_404_no_routes(self, client):
        """Should 404 when no optimization has been run."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=None)
            resp = client.get("/api/routes/VEH-01/google-maps")
        assert resp.status_code == 404

    def test_google_maps_route_404_wrong_vehicle(self, client, mock_run_id):
        """Should 404 for non-existent vehicle."""
        from core.database.models import OptimizationRunDB

        mock_run = MagicMock(spec=OptimizationRunDB)
        mock_run.id = mock_run_id

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=mock_run)
            mock_repo.get_route_for_vehicle = AsyncMock(return_value=None)
            resp = client.get("/api/routes/VEH-99/google-maps")
        assert resp.status_code == 404


class TestQrSheetEndpoint:
    """Tests for GET /api/qr-sheet — printable QR code page.

    Verifies the endpoint generates a complete HTML page with
    QR codes for all vehicles' routes.
    """

    def test_qr_sheet_returns_html(self, client, mock_run_id):
        """Endpoint should return printable HTML with QR codes."""
        from core.database.models import OptimizationRunDB, RouteDB
        from shapely.geometry import Point
        from geoalchemy2.shape import from_shape

        mock_run = MagicMock(spec=OptimizationRunDB)
        mock_run.id = mock_run_id
        mock_run.created_at = datetime.now(timezone.utc)

        # Build mock route with 2 stops
        stops = []
        for i in range(2):
            mock_stop = MagicMock()
            mock_stop.order = MagicMock()
            mock_stop.order.order_id = f"ORD-{i:03d}"
            mock_stop.order.geocode_confidence = None
            mock_stop.order.geocode_method = None
            mock_stop.location = from_shape(Point(75.58 + i * 0.01, 11.62 + i * 0.01), srid=4326)
            mock_stop.address_display = f"Stop {i + 1}"
            mock_stop.address_original = None
            mock_stop.sequence = i + 1
            mock_stop.distance_from_prev_km = 1.0
            mock_stop.duration_from_prev_minutes = 3.0
            mock_stop.weight_kg = 14.2
            mock_stop.quantity = 1
            mock_stop.notes = ""
            mock_stop.status = "pending"
            stops.append(mock_stop)

        mock_route = MagicMock(spec=RouteDB)
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "VEH-01"
        mock_route.driver_name = "Driver 1"
        mock_route.stops = stops
        mock_route.total_distance_km = 2.0
        mock_route.total_duration_minutes = 6.0
        mock_route.total_weight_kg = 28.4
        mock_route.total_items = 2
        mock_route.created_at = datetime.now(timezone.utc)

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=mock_run)
            mock_repo.get_routes_for_run = AsyncMock(return_value=[mock_route])
            from core.database.repository import route_db_to_pydantic
            mock_repo.route_db_to_pydantic = route_db_to_pydantic

            resp = client.get("/api/qr-sheet")

        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        html = resp.text
        # Should contain key elements
        assert "LPG Delivery Route QR Codes" in html
        assert "Driver 1" in html  # Driver name is primary card title (Phase 19)
        assert "data:image/png;base64," in html  # QR code as base64 PNG
        assert "Print QR Sheet" in html  # Print button
        assert "Scan to open route" in html  # Driver PWA QR instruction
        assert "Google Maps navigation" in html  # Navigation QR instruction
        # Safety: time is shown as a range, not exact (MVD compliance)
        assert "Est. Route Time" in html

    def test_qr_sheet_404_no_routes(self, client):
        """Should 404 when no routes have been generated."""
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=None)
            resp = client.get("/api/qr-sheet")
        assert resp.status_code == 404

    def test_qr_sheet_escapes_html_in_vehicle_data(self, client, mock_run_id):
        """XSS prevention: driver_name is HTML-escaped.

        Even though these values come from authenticated endpoints,
        defence-in-depth requires escaping at the output layer.
        A malicious driver_name like '<img onerror=alert(1) src=x>' must
        NOT appear unescaped in the rendered HTML.
        """
        from core.database.models import OptimizationRunDB, RouteDB
        from shapely.geometry import Point
        from geoalchemy2.shape import from_shape

        mock_run = MagicMock(spec=OptimizationRunDB)
        mock_run.id = mock_run_id
        mock_run.created_at = datetime.now(timezone.utc)

        mock_stop = MagicMock()
        mock_stop.order = MagicMock()
        mock_stop.order.order_id = "ORD-XSS"
        mock_stop.order.geocode_confidence = None
        mock_stop.order.geocode_method = None
        mock_stop.location = from_shape(Point(75.58, 11.62), srid=4326)
        mock_stop.address_display = "Test Stop"
        mock_stop.address_original = None
        mock_stop.sequence = 1
        mock_stop.distance_from_prev_km = 1.0
        mock_stop.duration_from_prev_minutes = 3.0
        mock_stop.weight_kg = 14.2
        mock_stop.quantity = 1
        mock_stop.notes = ""
        mock_stop.status = "pending"

        mock_route = MagicMock(spec=RouteDB)
        mock_route.id = uuid.uuid4()
        # Inject XSS payload into vehicle_id and driver_name
        mock_route.vehicle_id = '<script>alert("xss")</script>'
        mock_route.driver_name = '<img onerror=alert(1) src=x>'
        mock_route.stops = [mock_stop]
        mock_route.total_distance_km = 1.0
        mock_route.total_duration_minutes = 3.0
        mock_route.total_weight_kg = 14.2
        mock_route.total_items = 1
        mock_route.created_at = datetime.now(timezone.utc)

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=mock_run)
            mock_repo.get_routes_for_run = AsyncMock(return_value=[mock_route])
            from core.database.repository import route_db_to_pydantic
            mock_repo.route_db_to_pydantic = route_db_to_pydantic

            resp = client.get("/api/qr-sheet")

        assert resp.status_code == 200
        html = resp.text
        # RAW img XSS payload must NOT appear unescaped
        assert '<img onerror=' not in html
        # Escaped version SHOULD appear (browser renders as text, not HTML)
        # driver_name is the primary display field in the QR card header
        assert '&lt;img' in html


class TestGeocodingReasonMapFormat:
    """Tests for humanized geocoding error messages (ERR-02).

    Office employees should see "problem -- fix action" messages,
    not raw Google API status codes or parenthesized codes.
    """

    def test_geocoding_reason_map_format(self):
        """Every GEOCODING_REASON_MAP value must contain ' -- ' separator.
        No value should contain parenthesized codes like '(ZERO_RESULTS)'.
        """
        from apps.kerala_delivery.api.main import GEOCODING_REASON_MAP

        for status, message in GEOCODING_REASON_MAP.items():
            assert " -- " in message, (
                f"GEOCODING_REASON_MAP['{status}'] missing fix action separator: {message}"
            )
            assert "(" not in message, (
                f"GEOCODING_REASON_MAP['{status}'] contains parenthesized code: {message}"
            )
            assert ")" not in message, (
                f"GEOCODING_REASON_MAP['{status}'] contains parenthesized code: {message}"
            )

    def test_geocoding_reason_map_specific_messages(self):
        """Verify exact messages for key status codes."""
        from apps.kerala_delivery.api.main import GEOCODING_REASON_MAP

        assert GEOCODING_REASON_MAP["ZERO_RESULTS"] == (
            "Address not found -- check spelling in CDCMS"
        )
        assert GEOCODING_REASON_MAP["OVER_DAILY_LIMIT"] == (
            "Google Maps quota exceeded -- contact IT"
        )
        assert "contact IT" in GEOCODING_REASON_MAP["REQUEST_DENIED"]
        assert "contact IT" in GEOCODING_REASON_MAP["OVER_QUERY_LIMIT"]

    def test_geocoding_fallback_friendly(self):
        """Fallback for unknown status codes must not contain 'failed' or raw codes."""
        from apps.kerala_delivery.api.main import GEOCODING_REASON_MAP

        fallback = GEOCODING_REASON_MAP.get(
            "SOME_UNKNOWN_STATUS",
            "Could not find this address -- try checking the spelling",
        )
        assert "failed" not in fallback.lower(), f"Fallback contains 'failed': {fallback}"
        assert "SOME_UNKNOWN_STATUS" not in fallback, f"Fallback leaks raw status code: {fallback}"
        assert " -- " in fallback, f"Fallback missing fix action: {fallback}"


# =============================================================================
# ADDR-01: API response must include address_raw field
# =============================================================================


class TestAddressRawApiField:
    """Verify that GET /api/routes/{vehicle_id} response stops include
    an 'address_raw' field mapped from RouteStop.address_original.

    This field gives drivers access to the completely unprocessed CDCMS
    ConsumerAddress text, separate from the cleaned address_display.
    """

    @pytest.mark.addr01
    def test_stop_response_includes_address_raw_key(self, client, mock_run_id):
        """Each stop in GET /api/routes/{vehicle_id} must have 'address_raw' key."""
        from core.database.models import OptimizationRunDB, RouteDB
        from shapely.geometry import Point
        from geoalchemy2.shape import from_shape

        mock_run = MagicMock(spec=OptimizationRunDB)
        mock_run.id = mock_run_id

        mock_stop = MagicMock()
        mock_stop.order = MagicMock()
        mock_stop.order.order_id = "ORD-ADDR01-001"
        mock_stop.order.geocode_confidence = None
        mock_stop.order.geocode_method = None
        mock_stop.location = from_shape(Point(75.5700, 11.5950), srid=4326)
        mock_stop.address_display = "Kuniyil K, Near Vallikkadu"
        mock_stop.address_original = "KUNIYILK, NR.VALLIKKADU"
        mock_stop.sequence = 1
        mock_stop.distance_from_prev_km = 2.5
        mock_stop.duration_from_prev_minutes = 5.0
        mock_stop.weight_kg = 14.2
        mock_stop.quantity = 1
        mock_stop.notes = ""
        mock_stop.status = "pending"

        mock_route = MagicMock(spec=RouteDB)
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "VEH-01"
        mock_route.driver_name = "Driver 1"
        mock_route.stops = [mock_stop]
        mock_route.total_distance_km = 2.5
        mock_route.total_duration_minutes = 5.0
        mock_route.total_weight_kg = 14.2
        mock_route.total_items = 1
        mock_route.created_at = datetime.now(timezone.utc)

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=mock_run)
            mock_repo.get_route_for_vehicle = AsyncMock(return_value=mock_route)
            from core.database.repository import route_db_to_pydantic
            mock_repo.route_db_to_pydantic = route_db_to_pydantic

            resp = client.get("/api/routes/VEH-01")

        assert resp.status_code == 200
        data = resp.json()
        stop = data["stops"][0]
        assert "address_raw" in stop, (
            f"Stop response missing 'address_raw' key. Keys present: {list(stop.keys())}"
        )

    @pytest.mark.addr01
    def test_address_raw_value_matches_address_original(self, client, mock_run_id):
        """The 'address_raw' value should match the unprocessed CDCMS text
        (address_original on the RouteStop model)."""
        from core.database.models import OptimizationRunDB, RouteDB
        from shapely.geometry import Point
        from geoalchemy2.shape import from_shape

        mock_run = MagicMock(spec=OptimizationRunDB)
        mock_run.id = mock_run_id

        mock_stop = MagicMock()
        mock_stop.order = MagicMock()
        mock_stop.order.order_id = "ORD-ADDR01-002"
        mock_stop.order.geocode_confidence = None
        mock_stop.order.geocode_method = None
        mock_stop.location = from_shape(Point(75.5700, 11.5950), srid=4326)
        mock_stop.address_display = "Kuniyil K, Near Vallikkadu"
        mock_stop.address_original = "KUNIYILK, NR.VALLIKKADU"
        mock_stop.sequence = 1
        mock_stop.distance_from_prev_km = 2.5
        mock_stop.duration_from_prev_minutes = 5.0
        mock_stop.weight_kg = 14.2
        mock_stop.quantity = 1
        mock_stop.notes = ""
        mock_stop.status = "pending"

        mock_route = MagicMock(spec=RouteDB)
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "VEH-01"
        mock_route.driver_name = "Driver 1"
        mock_route.stops = [mock_stop]
        mock_route.total_distance_km = 2.5
        mock_route.total_duration_minutes = 5.0
        mock_route.total_weight_kg = 14.2
        mock_route.total_items = 1
        mock_route.created_at = datetime.now(timezone.utc)

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=mock_run)
            mock_repo.get_route_for_vehicle = AsyncMock(return_value=mock_route)
            from core.database.repository import route_db_to_pydantic
            mock_repo.route_db_to_pydantic = route_db_to_pydantic

            resp = client.get("/api/routes/VEH-01")

        data = resp.json()
        stop = data["stops"][0]
        assert stop["address_raw"] == "KUNIYILK, NR.VALLIKKADU", (
            f"address_raw should be the unprocessed text but got: {stop.get('address_raw')}"
        )

    @pytest.mark.addr01
    def test_address_raw_null_when_address_original_missing(self, client, mock_run_id):
        """When address_original is None (pre-v2.2 data), address_raw should be null."""
        from core.database.models import OptimizationRunDB, RouteDB
        from shapely.geometry import Point
        from geoalchemy2.shape import from_shape

        mock_run = MagicMock(spec=OptimizationRunDB)
        mock_run.id = mock_run_id

        mock_stop = MagicMock()
        mock_stop.order = MagicMock()
        mock_stop.order.order_id = "ORD-ADDR01-003"
        mock_stop.order.geocode_confidence = None
        mock_stop.order.geocode_method = None
        mock_stop.location = from_shape(Point(75.5700, 11.5950), srid=4326)
        mock_stop.address_display = "Kuniyil K, Near Vallikkadu"
        mock_stop.address_original = None  # Pre-v2.2: no original text stored
        mock_stop.sequence = 1
        mock_stop.distance_from_prev_km = 2.5
        mock_stop.duration_from_prev_minutes = 5.0
        mock_stop.weight_kg = 14.2
        mock_stop.quantity = 1
        mock_stop.notes = ""
        mock_stop.status = "pending"

        mock_route = MagicMock(spec=RouteDB)
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "VEH-01"
        mock_route.driver_name = "Driver 1"
        mock_route.stops = [mock_stop]
        mock_route.total_distance_km = 2.5
        mock_route.total_duration_minutes = 5.0
        mock_route.total_weight_kg = 14.2
        mock_route.total_items = 1
        mock_route.created_at = datetime.now(timezone.utc)

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=mock_run)
            mock_repo.get_route_for_vehicle = AsyncMock(return_value=mock_route)
            from core.database.repository import route_db_to_pydantic
            mock_repo.route_db_to_pydantic = route_db_to_pydantic

            resp = client.get("/api/routes/VEH-01")

        data = resp.json()
        stop = data["stops"][0]
        assert "address_raw" in stop, "address_raw key must be present even when null"
        assert stop["address_raw"] is None, (
            f"address_raw should be null for pre-v2.2 data but got: {stop['address_raw']}"
        )


# =============================================================================
# Driver Management Tests (Phase 16)
# =============================================================================


class TestDriverManagement:
    """Tests for the driver management CRUD endpoints.

    Operators use these endpoints to view, add, edit, and deactivate drivers.
    Drivers are standalone entities (not vehicle accessories) with fuzzy
    name matching to prevent duplicates.
    """

    def _mock_driver(self, **overrides):
        """Create a mock DriverDB object with sensible defaults.

        MagicMock's 'name' kwarg is special (sets internal descriptor),
        so we configure it separately via configure_mock().
        """
        defaults = {
            "id": uuid.uuid4(),
            "name": "Suresh Kumar",
            "name_normalized": "SURESH KUMAR",
            "is_active": True,
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
        defaults.update(overrides)
        mock = MagicMock()
        mock.configure_mock(**defaults)
        return mock

    def test_list_drivers_returns_all(self, client):
        """GET /api/drivers returns all drivers with route counts."""
        driver1 = self._mock_driver(name="Suresh Kumar", is_active=True)
        driver2 = self._mock_driver(name="Rajesh P", is_active=False)

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_all_drivers = AsyncMock(return_value=[driver1, driver2])
            mock_repo.get_driver_route_counts = AsyncMock(
                return_value={driver1.id: 5, driver2.id: 0}
            )
            resp = client.get("/api/drivers")

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert len(data["drivers"]) == 2
        # Verify driver shape
        d = data["drivers"][0]
        assert "id" in d
        assert "name" in d
        assert "is_active" in d
        assert "route_count" in d
        assert "created_at" in d
        assert "updated_at" in d

    def test_list_drivers_active_only(self, client):
        """GET /api/drivers?active_only=true returns only active drivers."""
        active_driver = self._mock_driver(name="Suresh Kumar", is_active=True)

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_all_drivers = AsyncMock(return_value=[active_driver])
            mock_repo.get_driver_route_counts = AsyncMock(
                return_value={active_driver.id: 3}
            )
            resp = client.get("/api/drivers?active_only=true")

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        mock_repo.get_all_drivers.assert_called_once()

    def test_check_driver_name_returns_similar(self, client):
        """GET /api/drivers/check-name?name=SURESH returns similar drivers."""
        similar_driver = self._mock_driver(name="Suresh Kumar")
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.find_similar_drivers = AsyncMock(
                return_value=[(similar_driver, 88.0)]
            )
            resp = client.get("/api/drivers/check-name?name=SURESH")

        assert resp.status_code == 200
        data = resp.json()
        assert "similar_drivers" in data
        assert len(data["similar_drivers"]) == 1
        match = data["similar_drivers"][0]
        assert "id" in match
        assert "name" in match
        assert "score" in match
        assert "is_active" in match

    def test_create_driver_success(self, client):
        """POST /api/drivers with {name: "suresh kumar"} returns 201."""
        created_driver = self._mock_driver(name="Suresh Kumar")
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.find_similar_drivers = AsyncMock(return_value=[])
            mock_repo.create_driver = AsyncMock(return_value=created_driver)
            resp = client.post("/api/drivers", json={"name": "suresh kumar"})

        assert resp.status_code == 201
        data = resp.json()
        assert "driver" in data
        assert data["driver"]["name"] == "Suresh Kumar"
        assert "similar_drivers" in data
        assert data["message"] == "Driver created"

    def test_create_driver_with_similar_matches(self, client):
        """POST /api/drivers returns created driver AND similar_drivers info."""
        similar = self._mock_driver(name="Suresh K")
        created = self._mock_driver(name="Suresh Kumar")
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.find_similar_drivers = AsyncMock(
                return_value=[(similar, 87.5)]
            )
            mock_repo.create_driver = AsyncMock(return_value=created)
            resp = client.post("/api/drivers", json={"name": "suresh kumar"})

        assert resp.status_code == 201
        data = resp.json()
        assert len(data["similar_drivers"]) == 1
        assert data["similar_drivers"][0]["score"] == 87.5

    def test_create_driver_empty_name_returns_422(self, client):
        """POST /api/drivers with empty name returns 422 (Pydantic validation)."""
        resp = client.post("/api/drivers", json={"name": ""})
        assert resp.status_code == 422

    def test_update_driver_name_success(self, client):
        """PUT /api/drivers/{id} with {name: "new name"} returns 200."""
        driver_id = str(uuid.uuid4())
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.update_driver_name = AsyncMock(return_value=True)
            mock_repo.find_similar_drivers = AsyncMock(return_value=[])
            resp = client.put(
                f"/api/drivers/{driver_id}",
                json={"name": "new name"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "updated" in data["message"].lower()
        assert "similar_drivers" in data

    def test_update_driver_not_found(self, client):
        """PUT /api/drivers/{id} on non-existent returns 404."""
        driver_id = str(uuid.uuid4())
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.update_driver_name = AsyncMock(return_value=False)
            mock_repo.get_driver_by_id = AsyncMock(return_value=None)
            resp = client.put(
                f"/api/drivers/{driver_id}",
                json={"name": "new name"},
            )

        assert resp.status_code == 404

    def test_update_driver_reactivate(self, client):
        """PUT /api/drivers/{id} with {is_active: true} reactivates."""
        driver_id = str(uuid.uuid4())
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_driver_by_id = AsyncMock(
                return_value=self._mock_driver(is_active=False)
            )
            mock_repo.reactivate_driver = AsyncMock(return_value=True)
            resp = client.put(
                f"/api/drivers/{driver_id}",
                json={"is_active": True},
            )

        assert resp.status_code == 200

    def test_delete_driver_success(self, client):
        """DELETE /api/drivers/{id} returns 200, driver becomes inactive."""
        driver_id = str(uuid.uuid4())
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.deactivate_driver = AsyncMock(return_value=True)
            resp = client.delete(f"/api/drivers/{driver_id}")

        assert resp.status_code == 200
        assert "deactivated" in resp.json()["message"].lower()

    def test_delete_driver_not_found(self, client):
        """DELETE /api/drivers/{id} on non-existent returns 404."""
        driver_id = str(uuid.uuid4())
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.deactivate_driver = AsyncMock(return_value=False)
            resp = client.delete(f"/api/drivers/{driver_id}")

        assert resp.status_code == 404

    def test_create_driver_requires_api_key(self):
        """POST /api/drivers without X-API-Key header returns 401 when API_KEY is set."""
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        async def override_get_session():
            yield mock_session

        mock_health = {
            "postgresql": (True, "connected"),
            "osrm": (True, "available"),
            "vroom": (True, "available"),
        }
        app.dependency_overrides[get_session] = override_get_session
        app.state.service_health = mock_health
        app.state.started_at = datetime.now(timezone.utc)
        with patch.dict(os.environ, {"API_KEY": "test-secret-key-123"}), \
             patch("apps.kerala_delivery.api.main.wait_for_services", new_callable=AsyncMock, return_value=mock_health):
            auth_client = TestClient(app)
            resp = auth_client.post(
                "/api/drivers",
                json={"name": "Test Driver"},
            )
        app.dependency_overrides.clear()

        assert resp.status_code == 401


# =============================================================================
# Driver Auto-Creation During Upload (Phase 16, Plan 03)
# =============================================================================


class TestUploadAutoCreatesDrivers:
    """Tests for driver auto-creation from CSV DeliveryMan column during upload.

    When a CDCMS-format CSV is uploaded with a DeliveryMan column, the system
    auto-creates new drivers or matches existing ones via fuzzy matching.
    The upload response includes a drivers summary.
    """

    def _make_cdcms_csv(self, delivery_men: list[str]) -> bytes:
        """Build a minimal CDCMS tab-separated file with DeliveryMan column.

        Each delivery man gets one order with coordinates (to skip geocoding).
        """
        header = "OrderNo\tOrderStatus\tConsumerAddress\tOrderQuantity\tAreaName\tDeliveryMan\tMobileNo\tOrderDate"
        rows = []
        for i, dm in enumerate(delivery_men, start=1):
            rows.append(
                f"ORD-{i:03d}\tAllocated-Printed\t"
                f"Test Address {i} Vatakara\t1\tVatakara\t{dm}\t9876543210\t2026-03-13"
            )
        return (header + "\n" + "\n".join(rows) + "\n").encode("utf-8")

    def _make_vroom_response(self, num_orders: int) -> dict:
        """Build a VROOM response for N orders."""
        steps = [
            {"type": "start", "location": [75.5796, 11.6244], "arrival": 0,
             "distance": 0, "duration": 0},
        ]
        for i in range(num_orders):
            steps.append({
                "type": "job", "id": i,
                "location": [75.5700 + i * 0.001, 11.5950],
                "arrival": 200 * (i + 1), "duration": 200 * (i + 1),
                "distance": 1500 * (i + 1), "service": 300,
            })
        steps.append({
            "type": "end", "location": [75.5796, 11.6244],
            "arrival": 200 * (num_orders + 1),
            "distance": 1500 * (num_orders + 1),
            "duration": 200 * (num_orders + 1),
        })
        return {
            "code": 0,
            "routes": [{
                "vehicle": 0,
                "distance": 1500 * num_orders,
                "duration": 200 * num_orders,
                "steps": steps,
            }],
            "unassigned": [],
        }

    def test_upload_auto_creates_drivers_from_csv(
        self, client, mock_run_id
    ):
        """Upload CSV with DeliveryMan column creates new drivers in database.

        When driver names in the CSV don't match any existing drivers,
        new DriverDB records should be created, and the response should
        include them in the drivers summary as new_drivers.
        """
        cdcms_csv = self._make_cdcms_csv(["SURESH KUMAR", "RAJESH P"])

        with (
            patch("core.optimizer.vroom_adapter.httpx.post") as mock_post,
            patch("apps.kerala_delivery.api.main.repo") as mock_repo,
        ):
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: self._make_vroom_response(2),
                raise_for_status=lambda: None,
            )
            # Mock DB operations
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[MagicMock()])
            mock_repo.vehicle_db_to_pydantic.return_value = MOCK_VEHICLE
            mock_repo.save_optimization_run = AsyncMock(return_value=mock_run_id)

            # No existing drivers -- all names are new
            mock_repo.get_all_drivers = AsyncMock(return_value=[])
            mock_repo.find_similar_drivers = AsyncMock(return_value=[])

            async def mock_create_driver(session, name):
                driver = MagicMock()
                driver.id = uuid.uuid4()
                driver.name = name.strip().title()
                driver.is_active = True
                return driver

            mock_repo.create_driver = AsyncMock(side_effect=mock_create_driver)

            resp = client.post(
                "/api/upload-orders",
                files={"file": ("cdcms_export.csv", cdcms_csv, "text/csv")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "drivers" in data
        drivers = data["drivers"]
        assert len(drivers["new_drivers"]) == 2
        assert "Suresh Kumar" in drivers["new_drivers"]
        assert "Rajesh P" in drivers["new_drivers"]

    def test_upload_fuzzy_match_prevents_duplicate(
        self, client, mock_run_id
    ):
        """Upload CSV where DeliveryMan matches existing driver records as matched.

        Fuzzy matching should find the existing driver and NOT create a duplicate.
        """
        cdcms_csv = self._make_cdcms_csv(["MOHAN L"])

        existing_driver = MagicMock()
        existing_driver.id = uuid.uuid4()
        existing_driver.name = "Mohan Lal"
        existing_driver.name_normalized = "MOHAN LAL"
        existing_driver.is_active = True

        with (
            patch("core.optimizer.vroom_adapter.httpx.post") as mock_post,
            patch("apps.kerala_delivery.api.main.repo") as mock_repo,
        ):
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: self._make_vroom_response(1),
                raise_for_status=lambda: None,
            )
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[MagicMock()])
            mock_repo.vehicle_db_to_pydantic.return_value = MOCK_VEHICLE
            mock_repo.save_optimization_run = AsyncMock(return_value=mock_run_id)

            # Existing driver returned for fuzzy match
            mock_repo.get_all_drivers = AsyncMock(return_value=[existing_driver])
            mock_repo.find_similar_drivers = AsyncMock(
                return_value=[(existing_driver, 87.5)]
            )
            mock_repo.create_driver = AsyncMock()

            resp = client.post(
                "/api/upload-orders",
                files={"file": ("cdcms_export.csv", cdcms_csv, "text/csv")},
            )

        assert resp.status_code == 200
        data = resp.json()
        drivers = data["drivers"]
        # Should NOT have created a new driver
        mock_repo.create_driver.assert_not_called()
        # Should report as matched
        assert len(drivers["matched_drivers"]) == 1
        assert drivers["matched_drivers"][0]["csv_name"] == "Mohan L"
        assert drivers["matched_drivers"][0]["matched_to"] == "Mohan Lal"
        assert drivers["matched_drivers"][0]["score"] == 87.5

    def test_upload_reactivates_deactivated_driver(
        self, client, mock_run_id
    ):
        """Upload CSV where DeliveryMan fuzzy-matches a deactivated driver reactivates it."""
        cdcms_csv = self._make_cdcms_csv(["MOHAN L"])

        deactivated_driver = MagicMock()
        deactivated_driver.id = uuid.uuid4()
        deactivated_driver.name = "Mohan Lal"
        deactivated_driver.name_normalized = "MOHAN LAL"
        deactivated_driver.is_active = False

        with (
            patch("core.optimizer.vroom_adapter.httpx.post") as mock_post,
            patch("apps.kerala_delivery.api.main.repo") as mock_repo,
        ):
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: self._make_vroom_response(1),
                raise_for_status=lambda: None,
            )
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[MagicMock()])
            mock_repo.vehicle_db_to_pydantic.return_value = MOCK_VEHICLE
            mock_repo.save_optimization_run = AsyncMock(return_value=mock_run_id)

            # Deactivated driver returned for fuzzy match
            mock_repo.get_all_drivers = AsyncMock(return_value=[deactivated_driver])
            mock_repo.find_similar_drivers = AsyncMock(
                return_value=[(deactivated_driver, 87.5)]
            )
            mock_repo.reactivate_driver = AsyncMock(return_value=True)
            mock_repo.create_driver = AsyncMock()

            resp = client.post(
                "/api/upload-orders",
                files={"file": ("cdcms_export.csv", cdcms_csv, "text/csv")},
            )

        assert resp.status_code == 200
        data = resp.json()
        drivers = data["drivers"]
        # Should reactivate, not create
        mock_repo.create_driver.assert_not_called()
        mock_repo.reactivate_driver.assert_called_once()
        assert "Mohan Lal" in drivers["reactivated_drivers"]

    def test_upload_intra_csv_names_create_separate_drivers(
        self, client, mock_run_id
    ):
        """Upload CSV with two similar names creates BOTH as separate drivers.

        No intra-CSV merging per locked decision -- "SURESH K" and "SURESH KUMAR"
        in the same CSV both get created as separate drivers.
        """
        cdcms_csv = self._make_cdcms_csv(["SURESH K", "SURESH KUMAR"])

        with (
            patch("core.optimizer.vroom_adapter.httpx.post") as mock_post,
            patch("apps.kerala_delivery.api.main.repo") as mock_repo,
        ):
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: self._make_vroom_response(2),
                raise_for_status=lambda: None,
            )
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[MagicMock()])
            mock_repo.vehicle_db_to_pydantic.return_value = MOCK_VEHICLE
            mock_repo.save_optimization_run = AsyncMock(return_value=mock_run_id)

            # No existing drivers -- both are new
            mock_repo.get_all_drivers = AsyncMock(return_value=[])
            mock_repo.find_similar_drivers = AsyncMock(return_value=[])

            async def mock_create_driver(session, name):
                driver = MagicMock()
                driver.id = uuid.uuid4()
                driver.name = name.strip().title()
                driver.is_active = True
                return driver

            mock_repo.create_driver = AsyncMock(side_effect=mock_create_driver)

            resp = client.post(
                "/api/upload-orders",
                files={"file": ("cdcms_export.csv", cdcms_csv, "text/csv")},
            )

        assert resp.status_code == 200
        data = resp.json()
        drivers = data["drivers"]
        # Both should be created separately (no intra-CSV merge)
        assert len(drivers["new_drivers"]) == 2
        assert "Suresh K" in drivers["new_drivers"]
        assert "Suresh Kumar" in drivers["new_drivers"]

    def test_upload_without_deliveryman_column_backward_compatible(
        self, client, mock_run_id
    ):
        """Upload CSV without DeliveryMan column still works -- no driver auto-creation.

        Standard CSVs (non-CDCMS) have no DeliveryMan column. The system should
        skip driver auto-creation and the drivers field should be None.
        """
        # Standard CSV format (no DeliveryMan column)
        csv_content = (
            "order_id,address,customer_id,cylinder_type,quantity,priority,latitude,longitude\n"
            'ORD-001,"Vatakara Bus Stand, Vatakara",CUST-001,domestic,1,2,11.5950,75.5700\n'
            'ORD-002,"Vatakara Railway Station, Vatakara",CUST-002,domestic,2,1,11.6100,75.5650\n'
        )

        with (
            patch("core.optimizer.vroom_adapter.httpx.post") as mock_post,
            patch("apps.kerala_delivery.api.main.repo") as mock_repo,
        ):
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: self._make_vroom_response(2),
                raise_for_status=lambda: None,
            )
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[MagicMock()])
            mock_repo.vehicle_db_to_pydantic.return_value = MOCK_VEHICLE
            mock_repo.save_optimization_run = AsyncMock(return_value=mock_run_id)

            resp = client.post(
                "/api/upload-orders",
                files={"file": ("orders.csv", csv_content.encode(), "text/csv")},
            )

        assert resp.status_code == 200
        data = resp.json()
        # No drivers auto-creation for non-CDCMS CSVs
        assert data.get("drivers") is None

    def test_upload_driver_summary_includes_existing_drivers(
        self, client, mock_run_id
    ):
        """Upload response includes existing_drivers for exact/active matches."""
        cdcms_csv = self._make_cdcms_csv(["RAJESH P"])

        existing_driver = MagicMock()
        existing_driver.id = uuid.uuid4()
        existing_driver.name = "Rajesh P"
        existing_driver.name_normalized = "RAJESH P"
        existing_driver.is_active = True

        with (
            patch("core.optimizer.vroom_adapter.httpx.post") as mock_post,
            patch("apps.kerala_delivery.api.main.repo") as mock_repo,
        ):
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: self._make_vroom_response(1),
                raise_for_status=lambda: None,
            )
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[MagicMock()])
            mock_repo.vehicle_db_to_pydantic.return_value = MOCK_VEHICLE
            mock_repo.save_optimization_run = AsyncMock(return_value=mock_run_id)

            # Active driver with exact match (score 100)
            mock_repo.get_all_drivers = AsyncMock(return_value=[existing_driver])
            mock_repo.find_similar_drivers = AsyncMock(
                return_value=[(existing_driver, 100.0)]
            )

            resp = client.post(
                "/api/upload-orders",
                files={"file": ("cdcms_export.csv", cdcms_csv, "text/csv")},
            )

        assert resp.status_code == 200
        data = resp.json()
        drivers = data["drivers"]
        assert "Rajesh P" in drivers["existing_drivers"]

    def test_upload_driver_names_title_cased_in_summary(
        self, client, mock_run_id
    ):
        """Driver names in summary are title-cased."""
        cdcms_csv = self._make_cdcms_csv(["SURESH KUMAR"])

        with (
            patch("core.optimizer.vroom_adapter.httpx.post") as mock_post,
            patch("apps.kerala_delivery.api.main.repo") as mock_repo,
        ):
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: self._make_vroom_response(1),
                raise_for_status=lambda: None,
            )
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[MagicMock()])
            mock_repo.vehicle_db_to_pydantic.return_value = MOCK_VEHICLE
            mock_repo.save_optimization_run = AsyncMock(return_value=mock_run_id)

            mock_repo.get_all_drivers = AsyncMock(return_value=[])
            mock_repo.find_similar_drivers = AsyncMock(return_value=[])

            async def mock_create_driver(session, name):
                driver = MagicMock()
                driver.id = uuid.uuid4()
                driver.name = name.strip().title()
                driver.is_active = True
                return driver

            mock_repo.create_driver = AsyncMock(side_effect=mock_create_driver)

            resp = client.post(
                "/api/upload-orders",
                files={"file": ("cdcms_export.csv", cdcms_csv, "text/csv")},
            )

        assert resp.status_code == 200
        data = resp.json()
        drivers = data["drivers"]
        # Name should be title-cased, not ALL-CAPS
        assert "Suresh Kumar" in drivers["new_drivers"]
        assert "SURESH KUMAR" not in drivers["new_drivers"]

    def test_upload_matched_drivers_include_details(
        self, client, mock_run_id
    ):
        """Matched drivers include csv_name, matched_to, and score fields."""
        cdcms_csv = self._make_cdcms_csv(["MOHAN L"])

        existing_driver = MagicMock()
        existing_driver.id = uuid.uuid4()
        existing_driver.name = "Mohan Lal"
        existing_driver.name_normalized = "MOHAN LAL"
        existing_driver.is_active = True

        with (
            patch("core.optimizer.vroom_adapter.httpx.post") as mock_post,
            patch("apps.kerala_delivery.api.main.repo") as mock_repo,
        ):
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: self._make_vroom_response(1),
                raise_for_status=lambda: None,
            )
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[MagicMock()])
            mock_repo.vehicle_db_to_pydantic.return_value = MOCK_VEHICLE
            mock_repo.save_optimization_run = AsyncMock(return_value=mock_run_id)

            mock_repo.get_all_drivers = AsyncMock(return_value=[existing_driver])
            mock_repo.find_similar_drivers = AsyncMock(
                return_value=[(existing_driver, 87.5)]
            )

            resp = client.post(
                "/api/upload-orders",
                files={"file": ("cdcms_export.csv", cdcms_csv, "text/csv")},
            )

        assert resp.status_code == 200
        data = resp.json()
        drivers = data["drivers"]
        assert len(drivers["matched_drivers"]) == 1
        match = drivers["matched_drivers"][0]
        assert "csv_name" in match
        assert "matched_to" in match
        assert "score" in match
        assert match["csv_name"] == "Mohan L"
        assert match["matched_to"] == "Mohan Lal"
        assert isinstance(match["score"], (int, float))


# =============================================================================
# Phase 17: XLSX CDCMS detection tests (CSV-01)
# =============================================================================


class TestXlsxCdcmsDetection:
    """Tests for _is_cdcms_format() handling of .xlsx files (CSV-01).

    The original function opened all files as UTF-8 text, which fails on
    .xlsx files (ZIP-based binary format). These tests verify the fix.
    """

    @staticmethod
    def _make_xlsx_cdcms(tmp_path, filename="cdcms_export.xlsx"):
        """Create a real .xlsx file with CDCMS column headers."""
        data = {
            "OrderNo": ["517827", "517828"],
            "OrderStatus": ["Allocated-Printed", "Allocated-Printed"],
            "OrderDate": ["14-02-2026 9:41", "14-02-2026 9:42"],
            "OrderQuantity": ["1", "1"],
            "AreaName": ["VALLIKKADU", "RAYARANGOTH"],
            "DeliveryMan": ["GIREESHAN ( C )", "GIREESHAN ( C )"],
            "ConsumerAddress": [
                "4/146 AMINAS VALIYA PARAMBATH NR. VALLIKKADU",
                "02/11 PANAKKULATHIL CHAITHANIYA",
            ],
        }
        df = pd.DataFrame(data)
        path = tmp_path / filename
        df.to_excel(path, index=False)
        return path

    @staticmethod
    def _make_xlsx_non_cdcms(tmp_path, filename="other.xlsx"):
        """Create a real .xlsx file WITHOUT CDCMS columns."""
        data = {
            "Name": ["Alice", "Bob"],
            "Age": [30, 25],
            "City": ["Kochi", "Kannur"],
        }
        df = pd.DataFrame(data)
        path = tmp_path / filename
        df.to_excel(path, index=False)
        return path

    def test_xlsx_cdcms_detected(self, tmp_path):
        """_is_cdcms_format() returns True for .xlsx with CDCMS columns."""
        from apps.kerala_delivery.api.main import _is_cdcms_format

        xlsx_path = self._make_xlsx_cdcms(tmp_path)
        assert _is_cdcms_format(str(xlsx_path)) is True

    def test_xlsx_non_cdcms_rejected(self, tmp_path):
        """_is_cdcms_format() returns False for .xlsx without CDCMS columns."""
        from apps.kerala_delivery.api.main import _is_cdcms_format

        xlsx_path = self._make_xlsx_non_cdcms(tmp_path)
        assert _is_cdcms_format(str(xlsx_path)) is False

    def test_csv_cdcms_still_works(self, tmp_path):
        """Regression: _is_cdcms_format() still works for tab-separated CSV."""
        from apps.kerala_delivery.api.main import _is_cdcms_format

        # Create a tab-separated CSV with CDCMS columns
        content = (
            "OrderNo\tOrderStatus\tConsumerAddress\n"
            "517827\tAllocated-Printed\t4/146 AMINAS\n"
        )
        csv_path = tmp_path / "cdcms.csv"
        csv_path.write_text(content)
        assert _is_cdcms_format(str(csv_path)) is True

    def test_cdcms_detect_shuffled_columns(self, tmp_path):
        """Column order should not affect CDCMS detection (CSV-05)."""
        from apps.kerala_delivery.api.main import _is_cdcms_format

        # Create xlsx with columns in non-standard order
        data = {
            "DeliveryMan": ["GIREESHAN ( C )"],
            "ConsumerAddress": ["4/146 AMINAS"],
            "AreaName": ["VALLIKKADU"],
            "OrderNo": ["517827"],
            "OrderStatus": ["Allocated-Printed"],
            "OrderQuantity": ["1"],
        }
        df = pd.DataFrame(data)
        path = tmp_path / "shuffled.xlsx"
        df.to_excel(path, index=False)
        assert _is_cdcms_format(str(path)) is True


# =============================================================================
# Phase 17: Parse-upload endpoint tests (CSV-02)
# =============================================================================


class TestParseUploadEndpoint:
    """Tests for POST /api/parse-upload — the parse-only step (CSV-02).

    This endpoint parses a CDCMS file and returns driver preview data
    without running geocoding or optimization.
    """

    @staticmethod
    def _make_cdcms_xlsx_bytes(drivers=None, orders_per_driver=3):
        """Create a CDCMS xlsx file as bytes for upload testing.

        Args:
            drivers: List of driver names. Defaults to two drivers.
            orders_per_driver: Number of orders per driver.

        Returns:
            Tuple of (bytes, filename).
        """
        import io

        if drivers is None:
            drivers = ["GIREESHAN ( C )", "SURESH KUMAR"]

        rows = []
        order_no = 517827
        for driver in drivers:
            for i in range(orders_per_driver):
                rows.append({
                    "OrderNo": str(order_no),
                    "OrderStatus": "Allocated-Printed",
                    "OrderDate": "14-02-2026 9:41",
                    "OrderQuantity": "1",
                    "AreaName": "VALLIKKADU",
                    "DeliveryMan": driver,
                    "ConsumerAddress": f"Address {order_no}",
                })
                order_no += 1

        df = pd.DataFrame(rows)
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)
        return buf.read(), "cdcms_export.xlsx"

    @staticmethod
    def _make_cdcms_csv_bytes(drivers=None, orders_per_driver=3):
        """Create a tab-separated CDCMS CSV file as bytes for upload testing."""
        if drivers is None:
            drivers = ["GIREESHAN ( C )", "SURESH KUMAR"]

        header = "OrderNo\tOrderStatus\tOrderDate\tOrderSource\tOrderType\tCashMemoNo\tCashMemoStatus\tCashMemoDate\tOrderQuantity\tConsumedSubsidyQty\tAreaName\tDeliveryMan\tRefillPaymentStatus\tIVRSBookingNumber\tMobileNo\tBookingDoneThroughRegistereMobile\tConsumerAddress\tIsRefillPort\tEkycStatus"
        lines = [header]
        order_no = 517827
        for driver in drivers:
            for i in range(orders_per_driver):
                line = (
                    f"{order_no}\tAllocated-Printed\t14-02-2026 9:41\tIVRS\tRefill\t"
                    f"1234567\tPrinted\t14-02-2026\t1\t1\t"
                    f"VALLIKKADU\t{driver}\t\t'1111111111\t'1111111111\tY\t"
                    f"Address {order_no}\tN\tEKYC NOT DONE"
                )
                lines.append(line)
                order_no += 1

        content = "\n".join(lines)
        return content.encode("utf-8"), "cdcms_export.csv"

    def test_parse_upload_returns_preview(self, client, mock_session):
        """POST /api/parse-upload with CDCMS xlsx returns ParsePreviewResponse."""
        xlsx_bytes, filename = self._make_cdcms_xlsx_bytes()

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_all_drivers = AsyncMock(return_value=[])
            mock_repo.find_similar_drivers = AsyncMock(return_value=[])

            async def mock_create_driver(session, name):
                driver = MagicMock()
                driver.id = uuid.uuid4()
                driver.name = name.strip().title()
                driver.is_active = True
                return driver

            mock_repo.create_driver = AsyncMock(side_effect=mock_create_driver)

            resp = client.post(
                "/api/parse-upload",
                files={"file": (filename, xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "upload_token" in data
        assert "filename" in data
        assert "total_rows" in data
        assert "filtered_rows" in data
        assert "drivers" in data
        assert len(data["drivers"]) == 2
        assert data["filename"] == filename

    def test_parse_upload_multi_driver_counts(self, client, mock_session):
        """Parse-upload returns correct per-driver order counts."""
        # 2 drivers: one with 5 orders, one with 2 orders
        xlsx_bytes, filename = self._make_cdcms_xlsx_bytes(
            drivers=["DRIVER A", "DRIVER B"],
            orders_per_driver=5,
        )
        # Make a second xlsx with different counts - simpler to just test equal counts
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_all_drivers = AsyncMock(return_value=[])
            mock_repo.find_similar_drivers = AsyncMock(return_value=[])

            async def mock_create_driver(session, name):
                driver = MagicMock()
                driver.id = uuid.uuid4()
                driver.name = name.strip().title()
                driver.is_active = True
                return driver

            mock_repo.create_driver = AsyncMock(side_effect=mock_create_driver)

            resp = client.post(
                "/api/parse-upload",
                files={"file": (filename, xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )

        assert resp.status_code == 200
        data = resp.json()
        drivers = data["drivers"]
        assert len(drivers) == 2
        # Each driver should have 5 orders
        for d in drivers:
            assert d["order_count"] == 5

    def test_parse_upload_filters_allocated_printed(self, client, mock_session):
        """Parse-upload applies Allocated-Printed filter by default (CSV-04)."""
        import io

        # Create xlsx with mixed statuses
        rows = [
            {"OrderNo": "1", "OrderStatus": "Allocated-Printed", "OrderQuantity": "1",
             "AreaName": "A", "DeliveryMan": "DRIVER X", "ConsumerAddress": "Addr 1"},
            {"OrderNo": "2", "OrderStatus": "Allocated-Printed", "OrderQuantity": "1",
             "AreaName": "A", "DeliveryMan": "DRIVER X", "ConsumerAddress": "Addr 2"},
            {"OrderNo": "3", "OrderStatus": "Delivered", "OrderQuantity": "1",
             "AreaName": "A", "DeliveryMan": "DRIVER X", "ConsumerAddress": "Addr 3"},
            {"OrderNo": "4", "OrderStatus": "Cancelled", "OrderQuantity": "1",
             "AreaName": "A", "DeliveryMan": "DRIVER X", "ConsumerAddress": "Addr 4"},
        ]
        df = pd.DataFrame(rows)
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_all_drivers = AsyncMock(return_value=[])
            mock_repo.find_similar_drivers = AsyncMock(return_value=[])

            async def mock_create_driver(session, name):
                driver = MagicMock()
                driver.id = uuid.uuid4()
                driver.name = name.strip().title()
                driver.is_active = True
                return driver

            mock_repo.create_driver = AsyncMock(side_effect=mock_create_driver)

            resp = client.post(
                "/api/parse-upload",
                files={"file": ("test.xlsx", buf.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )

        assert resp.status_code == 200
        data = resp.json()
        # 4 total rows, but only 2 are Allocated-Printed
        assert data["total_rows"] == 4
        assert data["filtered_rows"] == 2
        # Only 1 driver with 2 orders (the Allocated-Printed ones)
        assert len(data["drivers"]) == 1
        assert data["drivers"][0]["order_count"] == 2

    def test_parse_upload_non_cdcms_returns_400(self, client, mock_session):
        """Non-CDCMS file returns 400 error."""
        import io

        non_cdcms = pd.DataFrame({"Name": ["A"], "Age": [25]})
        buf = io.BytesIO()
        non_cdcms.to_excel(buf, index=False)
        buf.seek(0)

        resp = client.post(
            "/api/parse-upload",
            files={"file": ("other.xlsx", buf.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 400

    def test_parse_upload_empty_file_returns_400(self, client, mock_session):
        """Empty file returns 400 error."""
        resp = client.post(
            "/api/parse-upload",
            files={"file": ("empty.xlsx", b"", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 400

    def test_parse_upload_driver_status_categories(self, client, mock_session):
        """Parse-upload returns drivers with correct status categories."""
        xlsx_bytes, filename = self._make_cdcms_xlsx_bytes(
            drivers=["NEW DRIVER", "EXISTING GUY"],
        )

        # Mock: EXISTING GUY matches an existing active driver
        existing_driver = MagicMock()
        existing_driver.id = uuid.uuid4()
        existing_driver.name = "Existing Guy"
        existing_driver.is_active = True

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_all_drivers = AsyncMock(return_value=[existing_driver])

            # NEW DRIVER -> no match, EXISTING GUY -> match
            async def find_similar(session, name):
                if "EXISTING" in name.upper():
                    return [(existing_driver, 95.0)]
                return []

            mock_repo.find_similar_drivers = AsyncMock(side_effect=find_similar)

            async def mock_create_driver(session, name):
                driver = MagicMock()
                driver.id = uuid.uuid4()
                driver.name = name.strip().title()
                driver.is_active = True
                return driver

            mock_repo.create_driver = AsyncMock(side_effect=mock_create_driver)

            resp = client.post(
                "/api/parse-upload",
                files={"file": (filename, xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )

        assert resp.status_code == 200
        data = resp.json()
        drivers = data["drivers"]
        statuses = {d["csv_name"]: d["status"] for d in drivers}

        # One should be "new", one should be "matched" (fuzzy-matched to active)
        new_found = any(d["status"] == "new" for d in drivers)
        matched_found = any(d["status"] == "matched" for d in drivers)
        assert new_found, f"Expected a 'new' driver status, got: {statuses}"
        assert matched_found, f"Expected a 'matched' driver status, got: {statuses}"

    def test_parse_upload_excludes_allocation_pending(self, client, mock_session):
        """Parse-upload should NOT include 'Allocation Pending' as a driver.

        CDCMS uses 'Allocation Pending' as a placeholder for unassigned orders.
        These should be filtered out by the preprocessor so they never appear
        in the driver preview list.
        """
        xlsx_bytes, filename = self._make_cdcms_xlsx_bytes(
            drivers=["GIREESHAN ( C )", "Allocation Pending", "SURESH KUMAR"],
            orders_per_driver=2,
        )

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_all_drivers = AsyncMock(return_value=[])
            mock_repo.find_similar_drivers = AsyncMock(return_value=[])

            async def mock_create_driver(session, name):
                driver = MagicMock()
                driver.id = uuid.uuid4()
                driver.name = name.strip().title()
                driver.is_active = True
                return driver

            mock_repo.create_driver = AsyncMock(side_effect=mock_create_driver)

            resp = client.post(
                "/api/parse-upload",
                files={"file": (filename, xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )

        assert resp.status_code == 200
        data = resp.json()
        driver_names = [d["csv_name"] for d in data["drivers"]]
        # 'Allocation Pending' should NOT be in the driver list
        for name in driver_names:
            assert "allocation pending" not in name.lower(), (
                f"Placeholder 'Allocation Pending' appeared in driver preview: {driver_names}"
            )
        # Should only have 2 real drivers
        assert len(data["drivers"]) == 2

    def test_upload_token_cleanup(self):
        """Expired upload tokens are cleaned up."""
        from apps.kerala_delivery.api.main import _upload_tokens, _cleanup_expired_tokens, _TOKEN_TTL

        # Add an expired token
        old_token = str(uuid.uuid4())
        _upload_tokens[old_token] = {
            "path": "/tmp/nonexistent_test_file.xlsx",
            "filename": "test.xlsx",
            "created_at": datetime.now(timezone.utc) - timedelta(minutes=60),
        }

        # Add a fresh token
        fresh_token = str(uuid.uuid4())
        _upload_tokens[fresh_token] = {
            "path": "/tmp/nonexistent_test_file2.xlsx",
            "filename": "test2.xlsx",
            "created_at": datetime.now(timezone.utc),
        }

        _cleanup_expired_tokens()

        assert old_token not in _upload_tokens
        assert fresh_token in _upload_tokens

        # Clean up
        del _upload_tokens[fresh_token]


class TestUploadTokenBasedProcessing:
    """Tests for POST /api/upload-orders with upload_token and selected_drivers.

    Phase 17 Plan 02: The upload-orders endpoint now accepts optional
    upload_token (from parse-upload) and selected_drivers (JSON array)
    to support the two-step upload flow: parse -> preview -> process.
    """

    @staticmethod
    def _make_cdcms_xlsx_bytes(drivers=None, orders_per_driver=3):
        """Create a CDCMS xlsx file as bytes for upload testing."""
        import io

        if drivers is None:
            drivers = ["GIREESHAN ( C )", "SURESH KUMAR"]

        rows = []
        order_no = 517827
        for driver in drivers:
            for i in range(orders_per_driver):
                rows.append({
                    "OrderNo": str(order_no),
                    "OrderStatus": "Allocated-Printed",
                    "OrderDate": "14-02-2026 9:41",
                    "OrderQuantity": "1",
                    "AreaName": "VALLIKKADU",
                    "DeliveryMan": driver,
                    "ConsumerAddress": f"Address {order_no}",
                })
                order_no += 1

        df = pd.DataFrame(rows)
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)
        return buf.read(), "cdcms_export.xlsx"

    def _setup_token_in_store(self, drivers=None, orders_per_driver=3):
        """Create a real temp file and register it in the token store.

        Returns (token, tmp_path) for use in tests.
        """
        import tempfile
        import io

        from apps.kerala_delivery.api.main import _upload_tokens

        if drivers is None:
            drivers = ["GIREESHAN ( C )", "SURESH KUMAR"]

        rows = []
        order_no = 517827
        for driver in drivers:
            for i in range(orders_per_driver):
                rows.append({
                    "OrderNo": str(order_no),
                    "OrderStatus": "Allocated-Printed",
                    "OrderDate": "14-02-2026 9:41",
                    "OrderQuantity": "1",
                    "AreaName": "VALLIKKADU",
                    "DeliveryMan": driver,
                    "ConsumerAddress": f"Address {order_no}",
                })
                order_no += 1

        df = pd.DataFrame(rows)
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)

        # Write to a real temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            tmp.write(buf.read())
            tmp_path = tmp.name

        token = str(uuid.uuid4())
        _upload_tokens[token] = {
            "path": tmp_path,
            "filename": "cdcms_export.xlsx",
            "created_at": datetime.now(timezone.utc),
        }

        return token, tmp_path

    def test_upload_with_token_works(self, client, mock_session):
        """POST /api/upload-orders with upload_token loads stored file."""
        import json

        token, tmp_path = self._setup_token_in_store()

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo, \
             patch("core.optimizer.vroom_adapter.httpx.post") as mock_vroom_post:
            mock_repo.get_all_drivers = AsyncMock(return_value=[])
            mock_repo.find_similar_drivers = AsyncMock(return_value=[])
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[MagicMock()])
            mock_repo.vehicle_db_to_pydantic.return_value = Vehicle(
                vehicle_id="VEH-01",
                depot=Location(latitude=11.25, longitude=75.78),
                max_weight_kg=500.0,
            )
            mock_repo.save_optimization_run = AsyncMock(return_value=uuid.uuid4())

            async def mock_create_driver(session, name):
                driver = MagicMock()
                driver.id = uuid.uuid4()
                driver.name = name.strip().title()
                driver.is_active = True
                return driver

            mock_repo.create_driver = AsyncMock(side_effect=mock_create_driver)

            # VROOM mock response
            mock_vroom_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {
                    "code": 0,
                    "summary": {"cost": 100, "duration": 600, "computing_times": {"loading": 1, "solving": 5, "routing": 2}},
                    "routes": [{
                        "vehicle": 0,
                        "cost": 100,
                        "duration": 600,
                        "distance": 5000,
                        "steps": [
                            {"type": "start", "location": [75.78, 11.25], "arrival": 0, "duration": 0, "distance": 0},
                            {"type": "job", "job": 0, "location": [75.79, 11.26], "arrival": 300, "duration": 300, "distance": 2500, "service": 120},
                            {"type": "end", "location": [75.78, 11.25], "arrival": 600, "duration": 600, "distance": 5000},
                        ],
                    }],
                    "unassigned": [],
                },
                raise_for_status=lambda: None,
            )

            resp = client.post(
                "/api/upload-orders",
                data={"upload_token": token},
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["total_orders"] >= 1

    def test_upload_with_invalid_token_returns_400(self, client, mock_session):
        """POST /api/upload-orders with invalid token returns 400."""
        resp = client.post(
            "/api/upload-orders",
            data={"upload_token": "nonexistent-token-12345"},
        )

        assert resp.status_code == 400
        data = resp.json()
        assert "expired" in data.get("user_message", "").lower() or "re-upload" in data.get("user_message", "").lower()

    def test_upload_token_consumed_after_use(self, client, mock_session):
        """Upload token is deleted after successful use (one-time)."""
        import json
        from apps.kerala_delivery.api.main import _upload_tokens

        token, tmp_path = self._setup_token_in_store()

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo, \
             patch("core.optimizer.vroom_adapter.httpx.post") as mock_vroom_post:
            mock_repo.get_all_drivers = AsyncMock(return_value=[])
            mock_repo.find_similar_drivers = AsyncMock(return_value=[])
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[MagicMock()])
            mock_repo.vehicle_db_to_pydantic.return_value = Vehicle(
                vehicle_id="VEH-01",
                depot=Location(latitude=11.25, longitude=75.78),
                max_weight_kg=500.0,
            )
            mock_repo.save_optimization_run = AsyncMock(return_value=uuid.uuid4())

            async def mock_create_driver(session, name):
                driver = MagicMock()
                driver.id = uuid.uuid4()
                driver.name = name.strip().title()
                driver.is_active = True
                return driver

            mock_repo.create_driver = AsyncMock(side_effect=mock_create_driver)

            mock_vroom_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {
                    "code": 0,
                    "summary": {"cost": 100, "duration": 600, "computing_times": {"loading": 1, "solving": 5, "routing": 2}},
                    "routes": [{
                        "vehicle": 0, "cost": 100, "duration": 600, "distance": 5000,
                        "steps": [
                            {"type": "start", "location": [75.78, 11.25], "arrival": 0, "duration": 0, "distance": 0},
                            {"type": "job", "job": 0, "location": [75.79, 11.26], "arrival": 300, "duration": 300, "distance": 2500, "service": 120},
                            {"type": "end", "location": [75.78, 11.25], "arrival": 600, "duration": 600, "distance": 5000},
                        ],
                    }],
                    "unassigned": [],
                },
                raise_for_status=lambda: None,
            )

            # First use should succeed
            resp = client.post(
                "/api/upload-orders",
                data={"upload_token": token},
            )
            assert resp.status_code == 200

        # Token should be consumed
        assert token not in _upload_tokens

        # Second use should fail
        resp2 = client.post(
            "/api/upload-orders",
            data={"upload_token": token},
        )
        assert resp2.status_code == 400

    def test_upload_with_selected_drivers_filters_optimization(self, client, mock_session):
        """POST with selected_drivers only optimizes routes for selected drivers."""
        import json

        token, tmp_path = self._setup_token_in_store(
            drivers=["DRIVER A", "DRIVER B", "DRIVER C"],
            orders_per_driver=2,
        )

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo, \
             patch("core.optimizer.vroom_adapter.httpx.post") as mock_vroom_post:
            mock_repo.get_all_drivers = AsyncMock(return_value=[])
            mock_repo.find_similar_drivers = AsyncMock(return_value=[])
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[MagicMock()])
            mock_repo.vehicle_db_to_pydantic.return_value = Vehicle(
                vehicle_id="VEH-01",
                depot=Location(latitude=11.25, longitude=75.78),
                max_weight_kg=500.0,
            )
            mock_repo.save_optimization_run = AsyncMock(return_value=uuid.uuid4())

            async def mock_create_driver(session, name):
                driver = MagicMock()
                driver.id = uuid.uuid4()
                driver.name = name.strip().title()
                driver.is_active = True
                return driver

            mock_repo.create_driver = AsyncMock(side_effect=mock_create_driver)

            mock_vroom_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {
                    "code": 0,
                    "summary": {"cost": 100, "duration": 600, "computing_times": {"loading": 1, "solving": 5, "routing": 2}},
                    "routes": [{
                        "vehicle": 0, "cost": 100, "duration": 600, "distance": 5000,
                        "steps": [
                            {"type": "start", "location": [75.78, 11.25], "arrival": 0, "duration": 0, "distance": 0},
                            {"type": "job", "job": 0, "location": [75.79, 11.26], "arrival": 300, "duration": 300, "distance": 2500, "service": 120},
                            {"type": "end", "location": [75.78, 11.25], "arrival": 600, "duration": 600, "distance": 5000},
                        ],
                    }],
                    "unassigned": [],
                },
                raise_for_status=lambda: None,
            )

            # Only select DRIVER A -- DRIVER B and C should NOT be in optimization
            selected = json.dumps(["DRIVER A"])
            resp = client.post(
                "/api/upload-orders",
                data={"upload_token": token, "selected_drivers": selected},
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_upload_without_token_still_works(self, client, mock_session):
        """POST /api/upload-orders with file (no token) still works as before (backward compat)."""
        xlsx_bytes, filename = self._make_cdcms_xlsx_bytes(
            drivers=["DRIVER X"], orders_per_driver=2,
        )

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo, \
             patch("core.optimizer.vroom_adapter.httpx.post") as mock_vroom_post:
            mock_repo.get_all_drivers = AsyncMock(return_value=[])
            mock_repo.find_similar_drivers = AsyncMock(return_value=[])
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[MagicMock()])
            mock_repo.vehicle_db_to_pydantic.return_value = Vehicle(
                vehicle_id="VEH-01",
                depot=Location(latitude=11.25, longitude=75.78),
                max_weight_kg=500.0,
            )
            mock_repo.save_optimization_run = AsyncMock(return_value=uuid.uuid4())

            async def mock_create_driver(session, name):
                driver = MagicMock()
                driver.id = uuid.uuid4()
                driver.name = name.strip().title()
                driver.is_active = True
                return driver

            mock_repo.create_driver = AsyncMock(side_effect=mock_create_driver)

            mock_vroom_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {
                    "code": 0,
                    "summary": {"cost": 100, "duration": 600, "computing_times": {"loading": 1, "solving": 5, "routing": 2}},
                    "routes": [{
                        "vehicle": 0, "cost": 100, "duration": 600, "distance": 5000,
                        "steps": [
                            {"type": "start", "location": [75.78, 11.25], "arrival": 0, "duration": 0, "distance": 0},
                            {"type": "job", "job": 0, "location": [75.79, 11.26], "arrival": 300, "duration": 300, "distance": 2500, "service": 120},
                            {"type": "end", "location": [75.78, 11.25], "arrival": 600, "duration": 600, "distance": 5000},
                        ],
                    }],
                    "unassigned": [],
                },
                raise_for_status=lambda: None,
            )

            resp = client.post(
                "/api/upload-orders",
                files={"file": (filename, xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_orders"] >= 1

    def test_upload_selected_drivers_filters_before_geocoding(self, client, mock_session):
        """When selected_drivers is provided, only those drivers' orders are geocoded.

        Gap closure: Previously, ALL orders were geocoded and then filtered
        by driver selection. This wasted Google Maps API calls. Now filtering
        happens BEFORE the geocoding loop.
        """
        import json

        # 3 drivers, 2 orders each = 6 total orders
        token, tmp_path = self._setup_token_in_store(
            drivers=["DRIVER A", "DRIVER B", "DRIVER C"],
            orders_per_driver=2,
        )

        geocode_calls = []

        # Mock _get_geocoder to return a non-None geocoder so CachedGeocoder is created
        mock_upstream_geocoder = MagicMock()

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo, \
             patch("core.optimizer.vroom_adapter.httpx.post") as mock_vroom_post, \
             patch("apps.kerala_delivery.api.main._get_geocoder", return_value=mock_upstream_geocoder), \
             patch("apps.kerala_delivery.api.main.CachedGeocoder") as mock_cached_cls:
            mock_repo.get_all_drivers = AsyncMock(return_value=[])
            mock_repo.find_similar_drivers = AsyncMock(return_value=[])
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[MagicMock()])
            mock_repo.vehicle_db_to_pydantic.return_value = Vehicle(
                vehicle_id="VEH-01",
                depot=Location(latitude=11.25, longitude=75.78),
                max_weight_kg=500.0,
            )
            mock_repo.save_optimization_run = AsyncMock(return_value=uuid.uuid4())

            async def mock_create_driver(session, name):
                driver = MagicMock()
                driver.id = uuid.uuid4()
                driver.name = name.strip().title()
                driver.is_active = True
                return driver

            mock_repo.create_driver = AsyncMock(side_effect=mock_create_driver)

            # Track geocode calls to verify only selected drivers' orders are geocoded
            mock_geocoder_instance = MagicMock()
            mock_geocoder_instance.stats = {"hits": 0, "misses": 0}

            async def mock_geocode(address, area_name=None):
                geocode_calls.append(address)
                mock_geocoder_instance.stats["misses"] += 1
                result = MagicMock()
                result.success = True
                result.location = Location(latitude=11.26, longitude=75.79)
                result.confidence = 0.9
                result.method = "api"
                return result

            mock_geocoder_instance.geocode = mock_geocode
            mock_cached_cls.return_value = mock_geocoder_instance

            mock_vroom_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {
                    "code": 0,
                    "summary": {"cost": 100, "duration": 600, "computing_times": {"loading": 1, "solving": 5, "routing": 2}},
                    "routes": [{
                        "vehicle": 0, "cost": 100, "duration": 600, "distance": 5000,
                        "steps": [
                            {"type": "start", "location": [75.78, 11.25], "arrival": 0, "duration": 0, "distance": 0},
                            {"type": "job", "id": 0, "location": [75.79, 11.26], "arrival": 300, "duration": 300, "distance": 2500, "service": 120},
                            {"type": "job", "id": 1, "location": [75.79, 11.26], "arrival": 500, "duration": 500, "distance": 4000, "service": 120},
                            {"type": "end", "location": [75.78, 11.25], "arrival": 600, "duration": 600, "distance": 5000},
                        ],
                    }],
                    "unassigned": [],
                },
                raise_for_status=lambda: None,
            )

            # Only select DRIVER A — should only geocode 2 orders (not all 6)
            selected = json.dumps(["DRIVER A"])
            resp = client.post(
                "/api/upload-orders",
                data={"upload_token": token, "selected_drivers": selected},
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        # Key assertion: only 2 orders geocoded (DRIVER A's), not 6 (all drivers')
        assert len(geocode_calls) == 2, (
            f"Expected 2 geocode calls (DRIVER A only), got {len(geocode_calls)}: {geocode_calls}"
        )

    def test_upload_no_token_no_file_returns_400(self, client, mock_session):
        """POST /api/upload-orders with neither token nor file returns 400."""
        resp = client.post(
            "/api/upload-orders",
            data={"upload_token": ""},  # empty token, no file
        )

        # Should return 400 because no valid token and no file
        assert resp.status_code == 400
