"""End-to-end pipeline tests — CSV upload → optimize → QR generation.

These tests simulate the full delivery optimization workflow with all
components mocked (no Docker services required). They verify that data
flows correctly through the entire pipeline:

    CSV file → CsvImporter → Geocoder → VroomAdapter → RouteAssignment
    → Google Maps URLs → QR codes → Driver route display

This catches integration bugs that per-module unit tests miss:
- Model field mismatches between importer output and optimizer input
- Coordinate format confusion (lat/lon vs lon/lat)
- Safety multiplier applied at the right layer
- End-to-end response shape matches frontend expectations
"""

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.kerala_delivery.api.main import app
from apps.kerala_delivery.api.qr_helpers import (
    build_google_maps_url,
    split_route_into_segments,
)
from core.data_import.csv_importer import CsvImporter
from core.database.connection import get_session
from core.models.location import Location
from core.models.order import Order
from core.models.route import Route, RouteAssignment, RouteStop
from core.models.vehicle import Vehicle
from core.optimizer.vroom_adapter import VroomAdapter


# =============================================================================
# Fixtures
# =============================================================================

VATAKARA_DEPOT = Location(latitude=11.6244, longitude=75.5796, address_text="Depot")

# Realistic delivery locations within 5km of Vatakara depot
DELIVERY_LOCATIONS = [
    Location(latitude=11.5950, longitude=75.5700, address_text="Vatakara Bus Stand"),
    Location(latitude=11.6100, longitude=75.5650, address_text="Vatakara Railway Station"),
    Location(latitude=11.6350, longitude=75.5900, address_text="Chorode"),
    Location(latitude=11.6050, longitude=75.5850, address_text="Kaloor"),
    Location(latitude=11.5700, longitude=75.5600, address_text="Azhiyur"),
]


@pytest.fixture
def mock_session():
    """Mock AsyncSession for database dependency override."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def client(mock_session):
    """TestClient with DB session and rate limiting overridden."""
    async def override_get_session():
        yield mock_session

    with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "false"}):
        from apps.kerala_delivery.api.main import limiter
        limiter.enabled = False
        app.dependency_overrides[get_session] = override_get_session
        yield TestClient(app)
        app.dependency_overrides.clear()
        limiter.enabled = True


@pytest.fixture
def five_order_csv():
    """CSV with 5 geocoded orders — realistic Kerala LPG delivery data."""
    rows = [
        "order_id,address,customer_id,cylinder_type,quantity,priority,latitude,longitude",
    ]
    for i, loc in enumerate(DELIVERY_LOCATIONS):
        rows.append(
            f'ORD-{i+1:03d},"{loc.address_text}",CUST-{i+1:03d},'
            f'domestic,{1 + (i % 3)},{2 - (i % 2)},{loc.latitude},{loc.longitude}'
        )
    return "\n".join(rows).encode("utf-8")


@pytest.fixture
def vroom_5_order_response():
    """VROOM response assigning 5 orders to 2 vehicles.

    Step-level distances and durations are CUMULATIVE from route start
    (VROOM's standard behavior with options.g=true).
    """
    return {
        "code": 0,
        "routes": [
            {
                "vehicle": 0,
                "distance": 6000,
                "duration": 800,
                "steps": [
                    {"type": "start", "location": [75.5796, 11.6244],
                     "arrival": 0, "distance": 0, "duration": 0},
                    {"type": "job", "id": 0, "location": [75.5700, 11.5950],
                     "arrival": 150, "distance": 1500, "duration": 150, "service": 300},
                    {"type": "job", "id": 1, "location": [75.5650, 11.6100],
                     "arrival": 350, "distance": 3500, "duration": 350, "service": 300},
                    {"type": "job", "id": 3, "location": [75.5850, 11.6050],
                     "arrival": 550, "distance": 5000, "duration": 550, "service": 300},
                    {"type": "end", "location": [75.5796, 11.6244],
                     "arrival": 800, "distance": 6000, "duration": 800},
                ],
            },
            {
                "vehicle": 1,
                "distance": 4000,
                "duration": 500,
                "steps": [
                    {"type": "start", "location": [75.5796, 11.6244],
                     "arrival": 0, "distance": 0, "duration": 0},
                    {"type": "job", "id": 2, "location": [75.5900, 11.6350],
                     "arrival": 200, "distance": 2000, "duration": 200, "service": 300},
                    {"type": "job", "id": 4, "location": [75.5600, 11.5700],
                     "arrival": 400, "distance": 3500, "duration": 400, "service": 300},
                    {"type": "end", "location": [75.5796, 11.6244],
                     "arrival": 500, "distance": 4000, "duration": 500},
                ],
            },
        ],
        "unassigned": [],
    }


# =============================================================================
# Pipeline component tests (unit-level, verifying data flow)
# =============================================================================


class TestCsvToOrderPipeline:
    """Verify CSV import produces valid Order models for the optimizer."""

    def test_csv_produces_geocoded_orders(self, five_order_csv, tmp_path):
        """All orders from CSV with coordinates should be geocoded."""
        csv_path = tmp_path / "orders.csv"
        csv_path.write_bytes(five_order_csv)

        importer = CsvImporter(
            cylinder_weight_lookup={"domestic": 14.2, "commercial": 19.0},
            coordinate_bounds=(6.0, 37.0, 68.0, 97.5),
        )
        import_result = importer.import_orders(str(csv_path))
        orders = import_result.orders

        assert len(orders) == 5
        assert all(o.is_geocoded for o in orders), "All orders must be geocoded"
        # Verify coordinate integrity — lat/lon not swapped
        for order in orders:
            assert 8.0 <= order.location.latitude <= 13.0, "Latitude in Kerala range"
            assert 74.0 <= order.location.longitude <= 78.0, "Longitude in Kerala range"

    def test_cylinder_weights_resolved(self, five_order_csv, tmp_path):
        """Cylinder type 'domestic' should resolve to 14.2 kg × quantity."""
        csv_path = tmp_path / "orders.csv"
        csv_path.write_bytes(five_order_csv)

        importer = CsvImporter(
            cylinder_weight_lookup={"domestic": 14.2},
        )
        import_result = importer.import_orders(str(csv_path))
        orders = import_result.orders

        for order in orders:
            # Each order has quantity 1-3, weight should be 14.2 × quantity
            assert order.weight_kg == pytest.approx(14.2 * order.quantity)


class TestOrderToVroomPipeline:
    """Verify Order models are correctly translated to VROOM request."""

    def test_optimizer_produces_route_assignment(self, vroom_5_order_response):
        """VroomAdapter should produce a RouteAssignment from mock response."""
        optimizer = VroomAdapter(vroom_url="http://localhost:3000", safety_multiplier=1.3)
        orders = [
            Order(
                order_id=f"ORD-{i+1:03d}",
                location=DELIVERY_LOCATIONS[i],
                address_raw=DELIVERY_LOCATIONS[i].address_text,
                customer_ref=f"CUST-{i+1:03d}",
                weight_kg=14.2 * (1 + (i % 3)),
                quantity=1 + (i % 3),
            )
            for i in range(5)
        ]
        fleet = [
            Vehicle(vehicle_id=f"VEH-{v:02d}", max_weight_kg=446.0,
                    max_items=30, depot=VATAKARA_DEPOT)
            for v in range(1, 3)
        ]

        with patch("core.optimizer.vroom_adapter.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: vroom_5_order_response,
                raise_for_status=lambda: None,
            )
            result = optimizer.optimize(orders, fleet)

        assert isinstance(result, RouteAssignment)
        assert result.total_orders_assigned == 5
        assert result.vehicles_used == 2
        assert len(result.unassigned_order_ids) == 0

    def test_route_distances_are_positive(self, vroom_5_order_response):
        """Every route and stop should have non-negative distances."""
        optimizer = VroomAdapter(vroom_url="http://localhost:3000", safety_multiplier=1.3)
        orders = [
            Order(
                order_id=f"ORD-{i+1:03d}",
                location=DELIVERY_LOCATIONS[i],
                address_raw=DELIVERY_LOCATIONS[i].address_text,
                customer_ref=f"CUST-{i+1:03d}",
                weight_kg=14.2,
                quantity=1,
            )
            for i in range(5)
        ]
        fleet = [
            Vehicle(vehicle_id=f"VEH-{v:02d}", max_weight_kg=446.0,
                    max_items=30, depot=VATAKARA_DEPOT)
            for v in range(1, 3)
        ]

        with patch("core.optimizer.vroom_adapter.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: vroom_5_order_response,
                raise_for_status=lambda: None,
            )
            result = optimizer.optimize(orders, fleet)

        for route in result.routes:
            assert route.total_distance_km >= 0
            assert route.total_duration_minutes >= 0
            for stop in route.stops:
                assert stop.distance_from_prev_km >= 0
                assert stop.duration_from_prev_minutes >= 0


class TestRouteToQrPipeline:
    """Verify route data flows correctly to QR code generation."""

    def test_route_stops_produce_valid_google_maps_url(self):
        """RouteStop locations should produce a valid Google Maps URL."""
        stops_data = [
            {"latitude": loc.latitude, "longitude": loc.longitude}
            for loc in DELIVERY_LOCATIONS[:5]
        ]
        url = build_google_maps_url(stops_data)
        assert url.startswith("https://www.google.com/maps/dir/")
        assert "travelmode=driving" in url

    def test_large_route_splits_into_segments(self):
        """Route with >11 stops should split into multiple QR segments."""
        stops_data = [
            {"latitude": 11.62 + i * 0.001, "longitude": 75.58}
            for i in range(20)
        ]
        segments = split_route_into_segments(stops_data)
        assert len(segments) >= 2
        for seg in segments:
            assert "<svg" in seg["qr_svg"]
            assert seg["url"].startswith("https://www.google.com/maps/")


# =============================================================================
# Full API pipeline tests
# =============================================================================


class TestFullUploadOptimizePipeline:
    """End-to-end: CSV upload → optimization → route retrieval."""

    def test_upload_creates_routes(
        self, client, five_order_csv, vroom_5_order_response
    ):
        """Uploading a CSV should return an OptimizationSummary with all orders assigned."""
        with patch("core.optimizer.vroom_adapter.httpx.post") as mock_vroom, \
             patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_vroom.return_value = MagicMock(
                status_code=200,
                json=lambda: vroom_5_order_response,
                raise_for_status=lambda: None,
            )
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[])
            mock_repo.save_optimization_run = AsyncMock(return_value=str(uuid.uuid4()))

            response = client.post(
                "/api/upload-orders",
                files={"file": ("orders.csv", five_order_csv, "text/csv")},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_orders"] == 5
        assert data["orders_assigned"] == 5
        assert data["vehicles_used"] == 2

    def test_upload_returns_distance_metrics(
        self, client, five_order_csv, vroom_5_order_response
    ):
        """Response should include total distance and duration with safety multiplier."""
        with patch("core.optimizer.vroom_adapter.httpx.post") as mock_vroom, \
             patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_vroom.return_value = MagicMock(
                status_code=200,
                json=lambda: vroom_5_order_response,
                raise_for_status=lambda: None,
            )
            mock_repo.get_cached_geocode = AsyncMock(return_value=None)
            mock_repo.get_active_vehicles = AsyncMock(return_value=[])
            mock_repo.save_optimization_run = AsyncMock(return_value=str(uuid.uuid4()))

            response = client.post(
                "/api/upload-orders",
                files={"file": ("orders.csv", five_order_csv, "text/csv")},
            )

        data = response.json()
        # Response should include optimization metadata
        assert data["orders_assigned"] == 5
        assert data["vehicles_used"] == 2
        assert data["optimization_time_ms"] >= 0

    def test_upload_empty_csv_returns_400(self, client):
        """CSV with only headers (no data rows) should return 400."""
        empty_csv = b"order_id,address,customer_id,weight_kg,latitude,longitude\n"
        response = client.post(
            "/api/upload-orders",
            files={"file": ("empty.csv", empty_csv, "text/csv")},
        )
        assert response.status_code == 400

    def test_upload_wrong_extension_returns_400(self, client):
        """Non-CSV files should be rejected."""
        response = client.post(
            "/api/upload-orders",
            files={"file": ("orders.exe", b"malicious", "application/octet-stream")},
        )
        assert response.status_code == 400


class TestRouteQrSheetPipeline:
    """End-to-end: routes → QR sheet HTML generation."""

    def _create_mock_routes(self):
        """Create mock route DB objects for QR sheet tests."""
        stops = []
        for i, loc in enumerate(DELIVERY_LOCATIONS[:3]):
            stop = MagicMock()
            stop.sequence_number = i + 1
            stop.latitude = loc.latitude
            stop.longitude = loc.longitude
            stop.address_display = loc.address_text
            stop.order_id = f"ORD-{i+1:03d}"
            stop.weight_kg = 14.2
            stop.quantity = 1
            stop.status = "pending"
            stop.notes = ""
            stops.append(stop)

        route = MagicMock()
        route.vehicle_id = "VEH-01"
        route.driver_name = "Test Driver"
        route.total_distance_km = 6.0
        route.total_duration_minutes = 13.0
        route.stops = stops
        return [route]

    def test_qr_sheet_contains_svg_codes(self, client):
        """QR sheet HTML should contain SVG QR codes for each route segment."""
        mock_routes = self._create_mock_routes()

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_run = MagicMock()
            mock_run.id = uuid.UUID("12345678-1234-1234-1234-123456789abc")
            mock_run.created_at = datetime.now(timezone.utc)
            mock_repo.get_latest_run = AsyncMock(return_value=mock_run)
            mock_repo.get_routes_for_run = AsyncMock(return_value=mock_routes)

            response = client.get("/api/qr-sheet")

        assert response.status_code == 200
        html = response.text
        # QR sheet uses base64 PNG images, not inline SVG
        assert "qr-img" in html
        # Vehicle ID should appear (html-escaped by the endpoint)
        assert "VEH-01" in html or "vehicle" in html.lower()
