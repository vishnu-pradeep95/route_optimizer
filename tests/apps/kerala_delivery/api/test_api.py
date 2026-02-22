"""Tests for the Kerala LPG Delivery FastAPI endpoints.

Verifies the API layer:
- Health check returns correctly
- Routes 404 when no optimization has been run
- Status updates validate input and update state
- Response models match expected shapes
- Upload-and-optimize endpoint handles the full pipeline
- Monsoon multiplier activates June–September

Uses FastAPI's TestClient — no real OSRM/VROOM/Google calls needed.
"""

import os
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

import apps.kerala_delivery.api.main as api_module
from apps.kerala_delivery.api.main import app
from core.models.location import Location
from core.models.route import Route, RouteAssignment, RouteStop


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def client():
    """FastAPI TestClient — no real server started."""
    return TestClient(app)


@pytest.fixture
def sample_assignment():
    """A pre-built RouteAssignment for testing route retrieval endpoints.

    Simulates what upload_and_optimize() would store after optimization.
    """
    stops = [
        RouteStop(
            order_id="ORD-001",
            location=Location(latitude=9.9816, longitude=76.2996, address_text="Edappally"),
            address_display="Edappally Junction",
            sequence=1,
            distance_from_prev_km=2.5,
            duration_from_prev_minutes=5.0,
            weight_kg=14.2,
            quantity=1,
        ),
        RouteStop(
            order_id="ORD-002",
            location=Location(latitude=9.9567, longitude=76.2998, address_text="Palarivattom"),
            address_display="Palarivattom Junction",
            sequence=2,
            distance_from_prev_km=3.0,
            duration_from_prev_minutes=6.0,
            weight_kg=28.4,
            quantity=2,
        ),
    ]
    route = Route(
        route_id="R-test-VEH-01",
        vehicle_id="VEH-01",
        driver_name="Driver 1",
        stops=stops,
        total_distance_km=5.5,
        total_duration_minutes=11.0,
        total_weight_kg=42.6,
        total_items=3,
    )
    return RouteAssignment(
        assignment_id="test-assign",
        routes=[route],
        unassigned_order_ids=[],
        optimization_time_ms=42.0,
    )


@pytest.fixture
def with_assignment(sample_assignment):
    """Inject a sample assignment into API state, clean up after test.

    Why a fixture instead of manual try/finally in every test?
    - DRY: eliminates 7× repeated save/restore boilerplate
    - Safer: yield-based cleanup always runs, even on assertion failures
    - Clearer: test methods focus on behaviour, not state management
    """
    original = api_module._current_assignment
    api_module._current_assignment = sample_assignment
    yield sample_assignment
    api_module._current_assignment = original


@pytest.fixture
def no_assignment():
    """Ensure no assignment is loaded — simulates a fresh API start."""
    original = api_module._current_assignment
    api_module._current_assignment = None
    yield
    api_module._current_assignment = original


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
    """Tests for route retrieval and status update endpoints."""

    def test_list_routes_404_when_no_optimization(self, client, no_assignment):
        """GET /api/routes should 404 if no optimization has been run yet.

        This is the normal state when the API first starts — no CSV uploaded.
        """
        resp = client.get("/api/routes")
        assert resp.status_code == 404

    def test_list_routes_returns_route_summaries(self, client, with_assignment):
        """GET /api/routes should return a list of route summaries."""
        resp = client.get("/api/routes")
        assert resp.status_code == 200
        data = resp.json()
        assert "routes" in data
        assert len(data["routes"]) == 1
        route = data["routes"][0]
        assert route["vehicle_id"] == "VEH-01"
        assert route["total_stops"] == 2

    def test_get_driver_route_returns_stops(self, client, with_assignment):
        """GET /api/routes/{vehicle_id} should return stops with details."""
        resp = client.get("/api/routes/VEH-01")
        assert resp.status_code == 200
        data = resp.json()
        assert data["vehicle_id"] == "VEH-01"
        assert len(data["stops"]) == 2
        assert data["stops"][0]["sequence"] == 1
        assert data["stops"][0]["order_id"] == "ORD-001"
        # Verify coordinates are present (needed for map display)
        assert "latitude" in data["stops"][0]
        assert "longitude" in data["stops"][0]

    def test_get_driver_route_404_wrong_vehicle(self, client, with_assignment):
        """GET /api/routes/WRONG-ID should 404."""
        resp = client.get("/api/routes/VEH-99")
        assert resp.status_code == 404

    def test_update_stop_status_delivered(self, client, with_assignment):
        """POST status update should change stop status to 'delivered'.

        This is what the driver app calls when they complete a delivery.
        The request body must be JSON with a 'status' field.
        """
        resp = client.post(
            "/api/routes/VEH-01/stops/ORD-001/status",
            json={"status": "delivered"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "delivered"

        # Verify the state was actually updated
        stop = with_assignment.routes[0].stops[0]
        assert stop.status == "delivered"

    def test_update_stop_status_rejects_invalid(self, client, with_assignment):
        """Invalid status values should be rejected.

        With Literal type validation, Pydantic returns 422 (not our manual 400).
        This is more correct — it's a validation error, not a business logic error.
        """
        resp = client.post(
            "/api/routes/VEH-01/stops/ORD-001/status",
            json={"status": "invalid_status"},
        )
        # Pydantic Literal validation returns 422 Unprocessable Entity
        assert resp.status_code == 422

    def test_update_stop_status_404_wrong_order(self, client, with_assignment):
        """Status update for nonexistent order should 404."""
        resp = client.post(
            "/api/routes/VEH-01/stops/NONEXISTENT/status",
            json={"status": "delivered"},
        )
        assert resp.status_code == 404


class TestUploadAndOptimize:
    """Tests for POST /api/upload-orders — the main workflow endpoint.

    These mock VROOM since we're testing the API layer,
    not the actual optimization. CSV includes lat/lon so geocoding is skipped.
    """

    def test_upload_csv_triggers_optimization(
        self, client, sample_csv_file, mock_vroom_2_orders
    ):
        """Uploading a valid CSV should parse orders and run VROOM.

        Flow: CSV upload → CsvImporter → (geocoding skipped, coords in CSV)
              → VroomAdapter.optimize() → store result → return summary.
        """
        with patch("core.optimizer.vroom_adapter.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_vroom_2_orders,
                raise_for_status=lambda: None,
            )
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

    def test_upload_empty_csv_returns_400(self, client):
        """CSV with no valid orders should return 400."""
        # CSV with header only — no data rows
        empty_csv = b"order_id,address,customer_id,weight_kg\n"
        resp = client.post(
            "/api/upload-orders",
            files={"file": ("empty.csv", empty_csv, "text/csv")},
        )
        assert resp.status_code == 400


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
        self, client, sample_csv_file, fake_now
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
        ):
            # datetime.now() returns our fake date; datetime(...) constructor
            # still works for Pydantic model default_factory via side_effect
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            # The mock VroomAdapter instance's optimize() returns our fake
            MockVroom.return_value.optimize.return_value = fake_assignment

            resp = client.post(
                "/api/upload-orders",
                files={"file": ("orders.csv", sample_csv_file, "text/csv")},
            )

            # Extract the safety_multiplier kwarg passed to VroomAdapter(...)
            multiplier = MockVroom.call_args.kwargs.get("safety_multiplier")

        return resp, multiplier

    def test_monsoon_multiplier_applied_in_july(
        self, client, sample_csv_file
    ):
        """During July (monsoon), effective multiplier = 1.3 × 1.5 = 1.95."""
        resp, multiplier = self._upload_with_mocked_datetime(
            client, sample_csv_file,
            fake_now=datetime(2026, 7, 15, 10, 0, 0),
        )
        assert resp.status_code == 200
        assert multiplier == pytest.approx(1.3 * 1.5)

    def test_no_monsoon_multiplier_in_february(
        self, client, sample_csv_file
    ):
        """Outside monsoon (February), only base 1.3× multiplier is used."""
        resp, multiplier = self._upload_with_mocked_datetime(
            client, sample_csv_file,
            fake_now=datetime(2026, 2, 15, 10, 0, 0),
        )
        assert resp.status_code == 200
        assert multiplier == pytest.approx(1.3)
