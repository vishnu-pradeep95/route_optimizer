"""Tests for the VROOM route optimizer adapter.

Verifies that VroomAdapter correctly:
- Builds VROOM-compatible JSON from our Order/Vehicle models
- Parses VROOM responses into RouteAssignment
- Applies the safety multiplier to response durations
- Handles unassigned orders
- Rejects ungeocoded orders

All tests mock httpx — no real VROOM server required.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from core.models.location import Location
from core.models.order import Order
from core.models.route import RouteAssignment
from core.models.vehicle import Vehicle
from core.optimizer.interfaces import RouteOptimizer
from core.optimizer.vroom_adapter import VroomAdapter


# =============================================================================
# Fixtures
# =============================================================================

KOCHI_DEPOT = Location(latitude=11.6244, longitude=75.5796, address_text="Depot")


@pytest.fixture
def optimizer():
    """VroomAdapter with 1.3× safety multiplier."""
    return VroomAdapter(
        vroom_url="http://localhost:3000",
        safety_multiplier=1.3,
    )


@pytest.fixture
def geocoded_orders():
    """3 geocoded LPG delivery orders in Vatakara."""
    locations = [
        Location(latitude=11.5950, longitude=75.5700, address_text="Vatakara Bus Stand"),
        Location(latitude=11.6100, longitude=75.5650, address_text="Vatakara Railway Station"),
        Location(latitude=11.6350, longitude=75.5900, address_text="Chorode"),
    ]
    return [
        Order(
            order_id=f"ORD-{i:03d}",
            location=locations[i],
            address_raw=locations[i].address_text,
            customer_ref=f"CUST-{i:03d}",
            weight_kg=14.2,
            quantity=1,
        )
        for i in range(3)
    ]


@pytest.fixture
def fleet():
    """2 delivery vehicles."""
    return [
        Vehicle(
            vehicle_id=f"VEH-{i:02d}",
            driver_name=f"Driver {i}",
            max_weight_kg=446.0,
            max_items=30,
            depot=KOCHI_DEPOT,
        )
        for i in range(1, 3)
    ]


@pytest.fixture
def vroom_success_response():
    """Simulated VROOM response assigning all 3 orders to 2 vehicles.

    Based on: https://github.com/VROOM-Project/vroom/blob/master/docs/API.md
    """
    # Step-level `distance` and `duration` are CUMULATIVE from route start,
    # matching real VROOM behavior. See the _parse_response() code that
    # computes incremental per-leg values by subtracting previous step values.
    return {
        "code": 0,
        "summary": {
            "cost": 1234,
            "duration": 900,
            "distance": 8000,
        },
        "routes": [
            {
                "vehicle": 0,
                "distance": 5000,
                "duration": 600,
                "steps": [
                    {"type": "start", "location": [75.5796, 11.6244], "arrival": 0, "distance": 0, "duration": 0},
                    {
                        "type": "job",
                        "id": 0,
                        "location": [75.5700, 11.5950],
                        "arrival": 200,
                        "duration": 200,       # cumulative: 200s from start
                        "distance": 2000,      # cumulative: 2000m from start
                        "service": 300,
                    },
                    {
                        "type": "job",
                        "id": 1,
                        "location": [75.5650, 11.6100],
                        "arrival": 400,
                        "duration": 400,       # cumulative: 400s from start
                        "distance": 4000,      # cumulative: 4000m from start
                        "service": 300,
                    },
                    {"type": "end", "location": [75.5796, 11.6244], "arrival": 600, "distance": 5000, "duration": 600},
                ],
            },
            {
                "vehicle": 1,
                "distance": 3000,
                "duration": 300,
                "steps": [
                    {"type": "start", "location": [75.5796, 11.6244], "arrival": 0, "distance": 0, "duration": 0},
                    {
                        "type": "job",
                        "id": 2,
                        "location": [75.5900, 11.6350],
                        "arrival": 150,
                        "duration": 150,       # cumulative: 150s from start
                        "distance": 1500,      # cumulative: 1500m from start
                        "service": 300,
                    },
                    {"type": "end", "location": [75.5796, 11.6244], "arrival": 300, "distance": 3000, "duration": 300},
                ],
            },
        ],
        "unassigned": [],
    }


@pytest.fixture
def vroom_partial_response():
    """VROOM response with 1 unassigned order (capacity exceeded).

    Step-level values are cumulative from route start.
    """
    return {
        "code": 0,
        "routes": [
            {
                "vehicle": 0,
                "distance": 2500,
                "duration": 200,
                "steps": [
                    {"type": "start", "location": [75.5796, 11.6244], "arrival": 0, "distance": 0, "duration": 0},
                    {
                        "type": "job",
                        "id": 0,
                        "location": [75.5700, 11.5950],
                        "arrival": 200,
                        "duration": 200,       # cumulative
                        "distance": 1200,      # cumulative
                        "service": 300,
                    },
                    {"type": "end", "location": [75.5796, 11.6244], "arrival": 400, "distance": 2500, "duration": 400},
                ],
            },
        ],
        "unassigned": [{"id": 1, "type": "job"}, {"id": 2, "type": "job"}],
    }


# =============================================================================
# Tests
# =============================================================================


class TestVroomAdapter:
    """Unit tests for VroomAdapter with mocked HTTP."""

    def test_implements_route_optimizer_protocol(self, optimizer):
        """Verify VroomAdapter satisfies the RouteOptimizer protocol.

        Protocol compliance lets us swap VROOM for OR-Tools later
        without changing the API layer.
        """
        assert isinstance(optimizer, RouteOptimizer)

    def test_optimize_returns_route_assignment(
        self, optimizer, geocoded_orders, fleet, vroom_success_response
    ):
        """optimize() should return a RouteAssignment model."""
        with patch("core.optimizer.vroom_adapter.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: vroom_success_response,
                raise_for_status=lambda: None,
            )
            result = optimizer.optimize(geocoded_orders, fleet)

        assert isinstance(result, RouteAssignment)

    def test_all_orders_assigned_to_routes(
        self, optimizer, geocoded_orders, fleet, vroom_success_response
    ):
        """When VROOM assigns all orders, total_orders_assigned matches input."""
        with patch("core.optimizer.vroom_adapter.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: vroom_success_response,
                raise_for_status=lambda: None,
            )
            result = optimizer.optimize(geocoded_orders, fleet)

        assert result.total_orders_assigned == 3
        assert len(result.unassigned_order_ids) == 0
        assert result.vehicles_used == 2

    def test_unassigned_orders_reported(
        self, optimizer, geocoded_orders, fleet, vroom_partial_response
    ):
        """When VROOM can't assign all orders, unassigned IDs are tracked.

        This happens when vehicle capacity is exceeded. The office needs
        to know which orders couldn't be delivered today.
        """
        with patch("core.optimizer.vroom_adapter.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: vroom_partial_response,
                raise_for_status=lambda: None,
            )
            result = optimizer.optimize(geocoded_orders, fleet)

        assert len(result.unassigned_order_ids) == 2
        assert result.total_orders_assigned == 1

    def test_safety_multiplier_applied_to_route_durations(
        self, optimizer, geocoded_orders, fleet, vroom_success_response
    ):
        """Route total_duration_minutes should include the 1.3× safety multiplier.

        VROOM gets raw OSRM times. We multiply for realistic Kerala estimates.
        """
        with patch("core.optimizer.vroom_adapter.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: vroom_success_response,
                raise_for_status=lambda: None,
            )
            result = optimizer.optimize(geocoded_orders, fleet)

        # Route 0: 600s raw → 600 × 1.3 / 60 = 13.0 minutes
        route_0 = result.routes[0]
        assert route_0.total_duration_minutes == pytest.approx(600 * 1.3 / 60.0)

    def test_stop_sequences_are_ordered(
        self, optimizer, geocoded_orders, fleet, vroom_success_response
    ):
        """Each route's stops should have sequential sequence numbers."""
        with patch("core.optimizer.vroom_adapter.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: vroom_success_response,
                raise_for_status=lambda: None,
            )
            result = optimizer.optimize(geocoded_orders, fleet)

        for route in result.routes:
            sequences = [s.sequence for s in route.stops]
            assert sequences == list(range(1, len(sequences) + 1))

    def test_rejects_ungeocoded_orders(self, optimizer, fleet):
        """Orders without GPS coordinates should be rejected.

        VROOM needs coordinates for every job. If we pass ungeocoded
        orders, the solution would be meaningless.
        """
        ungeocoded_orders = [
            Order(
                order_id="BAD-001",
                address_raw="Some address without GPS",
                customer_ref="CUST-BAD",
                weight_kg=14.2,
                quantity=1,
                # No location set — is_geocoded will be False
            ),
        ]
        with pytest.raises(ValueError, match="not geocoded"):
            optimizer.optimize(ungeocoded_orders, fleet)

    def test_vroom_request_uses_lon_lat_order(
        self, optimizer, geocoded_orders, fleet, vroom_success_response
    ):
        """VROOM (like OSRM) expects [longitude, latitude] — GeoJSON order.

        Getting this wrong means routes planned for the wrong locations.
        """
        with patch("core.optimizer.vroom_adapter.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: vroom_success_response,
                raise_for_status=lambda: None,
            )
            optimizer.optimize(geocoded_orders, fleet)

        # Inspect the request body sent to VROOM
        call_kwargs = mock_post.call_args
        request_body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")

        # First job: Vatakara Bus Stand (lat=11.595, lon=75.57)
        # VROOM expects [lon, lat] = [75.57, 11.595]
        first_job = request_body["jobs"][0]
        assert first_job["location"] == [75.57, 11.595]

    def test_request_includes_geometry_option(
        self, optimizer, geocoded_orders, fleet, vroom_success_response
    ):
        """Request must include options.g=true so VROOM returns distance data.

        Without this flag, VROOM omits distance from both route-level and
        step-level responses, making it impossible to compute route distances.
        """
        with patch("core.optimizer.vroom_adapter.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: vroom_success_response,
                raise_for_status=lambda: None,
            )
            optimizer.optimize(geocoded_orders, fleet)

        call_kwargs = mock_post.call_args
        request_body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert request_body.get("options", {}).get("g") is True

    def test_per_stop_distances_are_incremental(
        self, optimizer, geocoded_orders, fleet, vroom_success_response
    ):
        """Stop distances should be per-leg (incremental), not cumulative.

        VROOM returns cumulative distances/durations at each step. Our adapter
        must subtract the previous step's cumulative value to get the leg distance.
        Mock data: job 0 at 2000m cumulative, job 1 at 4000m cumulative.
        Expected: job 0 leg = 2.0 km, job 1 leg = 2.0 km.
        """
        with patch("core.optimizer.vroom_adapter.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: vroom_success_response,
                raise_for_status=lambda: None,
            )
            result = optimizer.optimize(geocoded_orders, fleet)

        route_0 = result.routes[0]
        assert len(route_0.stops) == 2
        # Job 0: cumulative 2000m → leg = 2000-0 = 2.0 km
        assert route_0.stops[0].distance_from_prev_km == pytest.approx(2.0)
        # Job 1: cumulative 4000m → leg = 4000-2000 = 2.0 km
        assert route_0.stops[1].distance_from_prev_km == pytest.approx(2.0)

    def test_per_stop_durations_are_incremental(
        self, optimizer, geocoded_orders, fleet, vroom_success_response
    ):
        """Stop durations should be per-leg with safety multiplier applied.

        Mock data: job 0 at 200s cumulative, job 1 at 400s cumulative.
        Expected with 1.3× multiplier:
          job 0 leg = (200-0) × 1.3 / 60 = 4.33 min
          job 1 leg = (400-200) × 1.3 / 60 = 4.33 min
        """
        with patch("core.optimizer.vroom_adapter.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: vroom_success_response,
                raise_for_status=lambda: None,
            )
            result = optimizer.optimize(geocoded_orders, fleet)

        route_0 = result.routes[0]
        expected_minutes = 200 * 1.3 / 60.0  # 4.333...
        assert route_0.stops[0].duration_from_prev_minutes == pytest.approx(expected_minutes)
        assert route_0.stops[1].duration_from_prev_minutes == pytest.approx(expected_minutes)

    def test_priority_inversion(
        self, optimizer, fleet,
    ):
        """Our priority 1=high should map to VROOM's higher numeric value.

        VROOM: higher number = more important (0-100)
        Our model: 1=high, 2=normal, 3=low
        Mapping: priority 1 → 70, priority 2 → 40, priority 3 → 10
        """
        orders = [
            Order(
                order_id="PRI-001",
                location=Location(latitude=11.63, longitude=75.57),
                address_raw="Priority 1",
                customer_ref="CUST-PRI1",
                weight_kg=14.2,
                quantity=1,
                priority=1,  # High priority
            ),
            Order(
                order_id="PRI-002",
                location=Location(latitude=11.61, longitude=75.58),
                address_raw="Priority 3",
                customer_ref="CUST-PRI2",
                weight_kg=14.2,
                quantity=1,
                priority=3,  # Low priority
            ),
        ]

        # VROOM response matching 2 orders (not the 3-order fixture)
        # Step-level values are cumulative from route start.
        vroom_response_2_orders = {
            "code": 0,
            "routes": [
                {
                    "vehicle": 0,
                    "distance": 4000,
                    "duration": 400,
                    "steps": [
                        {"type": "start", "location": [75.5796, 11.6244], "arrival": 0, "distance": 0, "duration": 0},
                        {"type": "job", "id": 0, "location": [75.57, 11.63], "arrival": 150, "duration": 150, "distance": 1500, "service": 300},
                        {"type": "job", "id": 1, "location": [75.58, 11.61], "arrival": 300, "duration": 300, "distance": 3000, "service": 300},
                        {"type": "end", "location": [75.5796, 11.6244], "arrival": 400, "distance": 4000, "duration": 400},
                    ],
                },
            ],
            "unassigned": [],
        }

        with patch("core.optimizer.vroom_adapter.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: vroom_response_2_orders,
                raise_for_status=lambda: None,
            )
            optimizer.optimize(orders, fleet)

        request_body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        jobs = request_body["jobs"]

        # Priority 1 order should have higher VROOM priority than priority 3
        assert jobs[0]["priority"] > jobs[1]["priority"]
        # Exact expected values: max(0, 100 - priority * 30)
        # Priority 1 → 100 - 30 = 70, Priority 3 → 100 - 90 = 10
        assert jobs[0]["priority"] == 70
        assert jobs[1]["priority"] == 10

    def test_vroom_http_error_propagates(
        self, optimizer, geocoded_orders, fleet,
    ):
        """VROOM HTTP errors (500, timeout, etc.) should propagate as exceptions.

        The API layer catches these and returns appropriate error responses.
        The adapter should not silently swallow server errors.
        """
        with patch("core.optimizer.vroom_adapter.httpx.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
            )
            mock_post.return_value = mock_response

            with pytest.raises(httpx.HTTPStatusError):
                optimizer.optimize(geocoded_orders, fleet)

    def test_service_time_converted_to_seconds(
        self, optimizer, geocoded_orders, fleet, vroom_success_response
    ):
        """Order service_time_minutes should be sent to VROOM as seconds.

        Default is 5 minutes → 300 seconds. VROOM uses seconds internally.
        """
        with patch("core.optimizer.vroom_adapter.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: vroom_success_response,
                raise_for_status=lambda: None,
            )
            optimizer.optimize(geocoded_orders, fleet)

        request_body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        # All test orders have default service_time_minutes=5
        for job in request_body["jobs"]:
            assert job["service"] == 5 * 60  # 300 seconds

    def test_weight_and_capacity_in_request(
        self, optimizer, geocoded_orders, fleet, vroom_success_response
    ):
        """Vehicle capacity and order delivery amounts must appear in request.

        Vehicle has max_weight_kg=446, max_items=30.
        Each test order: weight_kg=14.2, quantity=1.
        VROOM capacity uses int(), so 446.0 → 446.
        """
        with patch("core.optimizer.vroom_adapter.httpx.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: vroom_success_response,
                raise_for_status=lambda: None,
            )
            optimizer.optimize(geocoded_orders, fleet)

        request_body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")

        # Vehicles should have capacity=[446, 30]
        for v in request_body["vehicles"]:
            assert v["capacity"] == [446, 30]

        # Jobs should have delivery=[14, 1] (int(14.2)=14, quantity=1)
        for j in request_body["jobs"]:
            assert j["delivery"] == [14, 1]
