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
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient

from apps.kerala_delivery.api.main import app
from core.database.connection import get_session
from core.models.location import Location
from core.models.route import Route, RouteAssignment, RouteStop


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
    """
    async def override_get_session():
        yield mock_session

    with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "false"}):
        # Re-apply the enabled flag on the limiter instance.
        # slowapi reads the enabled flag at init time, so we must
        # toggle it directly for the test session.
        from apps.kerala_delivery.api.main import limiter
        limiter.enabled = False

        app.dependency_overrides[get_session] = override_get_session
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


@pytest.fixture
def sample_csv_file():
    """A minimal valid CSV file as bytes, for upload testing.

    Includes latitude/longitude so orders are geocoded without Google API.
    """
    csv_content = (
        "order_id,address,customer_id,cylinder_type,quantity,priority,latitude,longitude\n"
        'ORD-001,"Edappally Junction, Kochi",CUST-001,domestic,1,2,9.9816,76.2996\n'
        'ORD-002,"Palarivattom, Kochi",CUST-002,domestic,2,1,9.9567,76.2998\n'
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
                    {"type": "start", "location": [76.2846, 9.9716], "arrival": 0,
                     "distance": 0, "duration": 0},
                    {"type": "job", "id": 0, "location": [76.2996, 9.9816],
                     "arrival": 200, "duration": 200, "distance": 1500, "service": 300},
                    {"type": "job", "id": 1, "location": [76.2998, 9.9567],
                     "arrival": 400, "duration": 400, "distance": 3000, "service": 300},
                    {"type": "end", "location": [76.2846, 9.9716], "arrival": 600,
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
    """Tests for GET /health."""

    def test_health_returns_ok(self, client):
        """Health check should return 200 with status 'ok'."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


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
        mock_stop.location = from_shape(Point(76.2996, 9.9816), srid=4326)
        mock_stop.address_display = "Edappally Junction"
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
                    "latitude": 9.9816,
                    "longitude": 76.2996,
                },
            )

        assert resp.status_code == 200
        # Verify delivery_location was passed to the repo
        call_kwargs = mock_repo.update_stop_status.call_args.kwargs
        assert call_kwargs["delivery_location"] is not None
        assert call_kwargs["delivery_location"].latitude == pytest.approx(9.9816)
        assert call_kwargs["delivery_location"].longitude == pytest.approx(76.2996)

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
            mock_repo.get_active_vehicles = AsyncMock(return_value=[])
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

    def test_upload_all_geocoding_failures_returns_400(self, client):
        """CSV where no orders can be geocoded should return 400.

        When the CSV has no lat/lon columns and the geocoder can't resolve
        any addresses, the system should return a clear error message
        instead of silently producing empty routes.
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

        assert resp.status_code == 400
        assert "geocoded" in resp.json()["detail"].lower()


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
            mock_repo.get_active_vehicles = AsyncMock(return_value=[])
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
                    "latitude": 9.9716,
                    "longitude": 76.2846,
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
                    "latitude": 9.9716,
                    "longitude": 76.2846,
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
                    "latitude": 9.9716,
                    "longitude": 76.2846,
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
        mock_ping.location = from_shape(Point(76.2846, 9.9716), srid=4326)
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
        assert data["pings"][0]["latitude"] == pytest.approx(9.9716, abs=0.001)
        assert data["pings"][0]["longitude"] == pytest.approx(76.2846, abs=0.001)

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
            'ORD-001,"Edappally Junction, Kochi",CUST-001,domestic,1,2\n'
            'ORD-002,"Palarivattom, Kochi",CUST-002,domestic,2,1\n'
        )

        # The cache will return a Location for both addresses
        cached_location = Location(
            latitude=9.9816, longitude=76.2996, address_text="Cached address"
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
            mock_repo.get_active_vehicles = AsyncMock(return_value=[])
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
    """Tests for API key authentication on mutating endpoints.

    When the API_KEY environment variable is set, all POST endpoints
    must include a valid X-API-Key header. GET endpoints remain open
    (read-only, non-sensitive data for the dashboard).

    Security requirement from Code Review #6 — Critical finding C1.
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

        app.dependency_overrides[get_session] = override_get_session
        with patch.dict(os.environ, {"API_KEY": "test-secret-key-123"}):
            yield TestClient(app)
        app.dependency_overrides.clear()

    def test_upload_rejects_missing_key(self, auth_client, sample_csv_file):
        """POST /api/upload-orders without X-API-Key header returns 401."""
        resp = auth_client.post(
            "/api/upload-orders",
            files={"file": ("orders.csv", sample_csv_file, "text/csv")},
        )
        assert resp.status_code == 401
        assert "API key" in resp.json()["detail"]

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
                "latitude": 9.9716,
                "longitude": 76.2846,
                "speed_kmh": 30.0,
            },
        )
        assert resp.status_code == 401

    def test_get_endpoints_open_without_key(self, auth_client):
        """GET endpoints should work without API key even when API_KEY is set.

        GET /api/routes returns 404 (no routes), not 401 — proving that
        authentication was not enforced on the read-only endpoint.
        """
        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_latest_run = AsyncMock(return_value=None)
            resp = auth_client.get("/api/routes")
        assert resp.status_code == 404  # No routes, but auth passed

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
            mock_repo.get_active_vehicles = AsyncMock(return_value=[])
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
    """Tests for upload file validation — extension and size checks.

    SECURITY: prevents uploading executable files, scripts, or
    excessively large files that could exhaust server memory.
    Added after Code Review #6 — Warning W1.
    """

    def test_rejects_unsupported_extension(self, client):
        """Uploading a .txt file should return 400."""
        resp = client.post(
            "/api/upload-orders",
            files={"file": ("orders.txt", b"some data", "text/plain")},
        )
        assert resp.status_code == 400
        assert "unsupported" in resp.json()["detail"].lower()

    def test_rejects_exe_file(self, client):
        """Uploading an .exe should return 400."""
        resp = client.post(
            "/api/upload-orders",
            files={"file": ("malware.exe", b"\x00" * 100, "application/octet-stream")},
        )
        assert resp.status_code == 400

    def test_rejects_filename_without_extension(self, client):
        """Upload with no file extension should return 400."""
        resp = client.post(
            "/api/upload-orders",
            files={"file": ("orders_noext", b"data", "text/csv")},
        )
        assert resp.status_code == 400

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
        assert "too large" in resp.json()["detail"].lower()


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
            mock_point = MagicMock(y=9.97, x=76.28)
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
                        {"vehicle_id": "VEH-01", "latitude": 9.97, "longitude": 76.28},
                        {"vehicle_id": "VEH-01", "latitude": 9.975, "longitude": 76.285},
                        {"vehicle_id": "VEH-01", "latitude": 9.98, "longitude": 76.29},
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
                        {"vehicle_id": "VEH-01", "latitude": 9.97, "longitude": 76.28},
                        {"vehicle_id": "VEH-01", "latitude": 9.975, "longitude": 76.285, "accuracy_m": 100},
                        {"vehicle_id": "VEH-01", "latitude": 9.98, "longitude": 76.29, "speed_kmh": 55},
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
            {"vehicle_id": "VEH-01", "latitude": 9.97, "longitude": 76.28}
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
            mock_to_shape.return_value = MagicMock(y=9.97, x=76.28)
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
            mock_to_shape.return_value = MagicMock(y=9.97, x=76.28)
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
            mock_to_shape.return_value = MagicMock(y=9.97, x=76.28)
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
            mock_to_shape.return_value = MagicMock(y=9.97, x=76.28)

            resp = client.post(
                "/api/vehicles",
                json={
                    "vehicle_id": "VEH-14",
                    "depot_latitude": 9.97,
                    "depot_longitude": 76.28,
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
                json={"vehicle_id": "VEH-01", "depot_latitude": 9.97, "depot_longitude": 76.28},
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
                "depot_latitude": 9.9312,
                "depot_longitude": 76.2673,
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
            latitude=9.97, longitude=76.28,
            geocode_confidence=0.9, address_text="Test"
        )
        mock_order.weight_kg = 14.2
        mock_order.quantity = 1
        mock_order.customer_ref = None
        mock_order.address_raw = "123 Test St"

        with patch("apps.kerala_delivery.api.main.CsvImporter") as mock_importer_cls, \
             patch("apps.kerala_delivery.api.main._get_geocoder", return_value=None), \
             patch("apps.kerala_delivery.api.main.VroomAdapter") as mock_optimizer_cls, \
             patch("apps.kerala_delivery.api.main.repo") as mock_repo, \
             patch("apps.kerala_delivery.api.main._build_fleet") as mock_fleet:

            mock_importer = MagicMock()
            mock_importer.import_orders.return_value = [mock_order]
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
            mock_fleet.return_value = []

            resp = client.post(
                "/api/upload-orders",
                files={"file": ("orders.csv", b"dummy", "text/csv")},
            )

        # The window should have been widened: 09:00 → 09:30
        assert mock_order.delivery_window_end == dt_time(9, 30)

    def test_valid_window_is_not_modified(self, client):
        """A 60-minute window should not be modified (already >= 30 min)."""
        from datetime import time as dt_time

        mock_order = MagicMock()
        mock_order.is_geocoded = True
        mock_order.delivery_window_start = dt_time(9, 0)
        mock_order.delivery_window_end = dt_time(10, 0)  # 60 min — valid
        mock_order.order_id = "ORD-001"
        mock_order.location = MagicMock(
            latitude=9.97, longitude=76.28,
            geocode_confidence=0.9, address_text="Test"
        )
        mock_order.weight_kg = 14.2
        mock_order.quantity = 1
        mock_order.customer_ref = None
        mock_order.address_raw = "123 Test St"

        with patch("apps.kerala_delivery.api.main.CsvImporter") as mock_importer_cls, \
             patch("apps.kerala_delivery.api.main._get_geocoder", return_value=None), \
             patch("apps.kerala_delivery.api.main.VroomAdapter") as mock_optimizer_cls, \
             patch("apps.kerala_delivery.api.main.repo") as mock_repo, \
             patch("apps.kerala_delivery.api.main._build_fleet") as mock_fleet:

            mock_importer = MagicMock()
            mock_importer.import_orders.return_value = [mock_order]
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
            mock_fleet.return_value = []

            client.post(
                "/api/upload-orders",
                files={"file": ("orders.csv", b"dummy", "text/csv")},
            )

        # Window should be unchanged — 60 min > 30 min minimum
        assert mock_order.delivery_window_end == dt_time(10, 0)


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

        limiter.enabled = True
        app.dependency_overrides[get_session] = override_get_session
        yield TestClient(app)
        app.dependency_overrides.clear()
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
