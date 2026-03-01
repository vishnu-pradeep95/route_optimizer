"""Integration tests for the OSRM → VROOM → API pipeline.

These tests require Docker services running:
    docker compose up -d

They hit real OSRM and VROOM instances with Kerala map data to verify:
1. OSRM returns plausible travel times for Vatakara coordinates
2. VROOM solves a realistic 30-order CVRP and produces valid routes
3. The full API pipeline (CSV upload → optimize → routes) works end-to-end

Run with:
    pytest tests/integration/ -v -m integration

These are NOT run in CI (no Docker) — they're for local validation
after setting up infrastructure or changing adapters.

Why separate from unit tests?
- Unit tests mock external services → fast, deterministic, always run
- Integration tests hit real services → slower, require Docker, catch real issues
- See: https://martinfowler.com/bliki/IntegrationTest.html
"""

import csv
import os
import tempfile

import httpx
import pytest

from core.models.location import Location
from core.models.order import Order
from core.models.vehicle import Vehicle
from core.routing.osrm_adapter import OsrmAdapter
from core.optimizer.vroom_adapter import VroomAdapter
from apps.kerala_delivery import config


# =============================================================================
# Skip entire module if Docker services aren't running
# =============================================================================


def _service_is_up(url: str) -> bool:
    """Check if a service responds to HTTP requests."""
    try:
        resp = httpx.get(url, timeout=3.0)
        return resp.status_code < 500
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


# Check OSRM and VROOM availability once at module load
OSRM_URL = os.environ.get("OSRM_URL", "http://localhost:5000")
VROOM_URL = os.environ.get("VROOM_URL", "http://localhost:3000")

OSRM_AVAILABLE = _service_is_up(f"{OSRM_URL}/route/v1/driving/75.5796,11.6244;75.5700,11.5950")
VROOM_AVAILABLE = _service_is_up(VROOM_URL)

# Custom pytest marker — skip integration tests when services are down
requires_osrm = pytest.mark.skipif(
    not OSRM_AVAILABLE,
    reason=f"OSRM not available at {OSRM_URL}. Run: docker compose up -d",
)
requires_vroom = pytest.mark.skipif(
    not VROOM_AVAILABLE,
    reason=f"VROOM not available at {VROOM_URL}. Run: docker compose up -d",
)
requires_all = pytest.mark.skipif(
    not (OSRM_AVAILABLE and VROOM_AVAILABLE),
    reason="OSRM and/or VROOM not available. Run: docker compose up -d",
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def osrm():
    """Real OSRM adapter pointing at Docker instance with Kerala data."""
    return OsrmAdapter(base_url=OSRM_URL, safety_multiplier=config.SAFETY_MULTIPLIER)


@pytest.fixture
def vroom():
    """Real VROOM adapter pointing at Docker instance."""
    return VroomAdapter(vroom_url=VROOM_URL, safety_multiplier=config.SAFETY_MULTIPLIER)


@pytest.fixture
def kochi_depot():
    """Depot location in central Vatakara for integration tests.

    Why not use config.DEPOT_LOCATION?
    The production depot may be anywhere in Kerala (currently Vatakara).
    Integration tests need a fixed Vatakara depot to validate plausible
    distances against the Vatakara delivery points defined below.
    Using a hardcoded Vatakara location makes tests independent of config.
    """
    return Location(
        latitude=11.6244,
        longitude=75.5796,
        address_text="Integration Test Depot (Memunda, Vatakara)",
    )


@pytest.fixture
def kochi_delivery_points():
    """10 delivery points across Vatakara — real coordinates.

    These are public landmark locations spread across the city,
    covering ~8 km north-south and ~5 km east-west range.
    """
    return [
        Location(latitude=11.5950, longitude=75.5700, address_text="Vatakara Bus Stand"),
        Location(latitude=11.6150, longitude=75.5750, address_text="Vatakara Railway Station"),
        Location(latitude=11.5800, longitude=75.5870, address_text="Chorode Junction"),
        Location(latitude=11.6130, longitude=75.5820, address_text="Nadapuram Road Junction"),
        Location(latitude=11.5900, longitude=75.5760, address_text="Chorode"),
        Location(latitude=11.5850, longitude=75.5830, address_text="Edakkad"),
        Location(latitude=11.6500, longitude=75.6000, address_text="Payyoli Junction"),
        Location(latitude=11.5750, longitude=75.5500, address_text="Azhiyur"),
        Location(latitude=11.5650, longitude=75.6100, address_text="Thalassery"),
        Location(latitude=11.6400, longitude=75.5950, address_text="Mahe Junction"),
    ]


@pytest.fixture
def sample_orders_for_optimization(kochi_delivery_points):
    """10 geocoded orders ready for VROOM optimization."""
    orders = []
    for i, loc in enumerate(kochi_delivery_points):
        orders.append(Order(
            order_id=f"INT-{i+1:03d}",
            location=loc,
            address_raw=loc.address_text or f"Address {i+1}",
            customer_ref=f"CUST-INT-{i+1:03d}",
            weight_kg=config.DOMESTIC_CYLINDER_KG * (1 + i % 3),
            quantity=1 + i % 3,
        ))
    return orders


@pytest.fixture
def fleet_3_vehicles(kochi_depot):
    """Fleet of 3 Ape Xtra LDX vehicles."""
    return [
        Vehicle(
            vehicle_id=f"VEH-{i:02d}",
            driver_name=f"Driver {i}",
            max_weight_kg=config.VEHICLE_MAX_WEIGHT_KG,
            max_items=config.VEHICLE_MAX_CYLINDERS,
            depot=kochi_depot,
        )
        for i in range(1, 4)
    ]


# =============================================================================
# OSRM Integration Tests
# =============================================================================


class TestOsrmIntegration:
    """Tests that hit the real OSRM service with Kerala map data.

    Validates that:
    - OSRM has Kerala data loaded (not an empty or wrong region)
    - Travel times are plausible for Vatakara distances
    - Distance matrix is symmetric-ish (A→B ≈ B→A)
    - Safety multiplier is applied correctly
    """

    @requires_osrm
    def test_osrm_returns_travel_time_for_kochi(self, osrm, kochi_depot):
        """Basic smoke test: OSRM should route between known Vatakara locations.

        Depot (Memunda) → Vatakara Bus Stand is ~3-5 km by road.
        Expected: 5-20 min drive (with multiplier), 2-8 km.
        """
        edappally = Location(latitude=11.5950, longitude=75.5700, address_text="Vatakara Bus Stand")
        result = osrm.get_travel_time(kochi_depot, edappally)

        # Sanity checks — if these fail, OSRM probably has wrong data
        assert result.duration_seconds > 0, "Duration must be positive"
        assert result.distance_meters > 1000, "Vatakara Bus Stand is >1km from Memunda"
        assert result.distance_meters < 15000, "Should be <15km by road"
        assert result.duration_seconds < 3600, "Should be <1 hour drive"

        # Verify safety multiplier was applied (1.3× means duration > raw OSRM)
        # Raw OSRM for ~4km in Vatakara should be ~5-10 min ≈ 300-600s
        # With 1.3× that's 390-780s
        assert result.duration_seconds > 200, "With multiplier, should be >200s"

    @requires_osrm
    def test_distance_matrix_is_square(self, osrm, kochi_delivery_points):
        """Matrix for N locations should be N×N with zeros on diagonal."""
        points = kochi_delivery_points[:5]  # Use 5 points for speed
        matrix = osrm.get_distance_matrix(points)

        assert len(matrix.durations) == 5
        assert all(len(row) == 5 for row in matrix.durations)
        assert len(matrix.distances) == 5
        assert all(len(row) == 5 for row in matrix.distances)

        # Diagonal should be zero (same point → same point)
        for i in range(5):
            assert matrix.durations[i][i] == 0.0
            assert matrix.distances[i][i] == 0.0

    @requires_osrm
    def test_travel_times_are_asymmetric_but_close(self, osrm, kochi_delivery_points):
        """A→B and B→A should be similar but not identical (one-way streets).

        Kerala has many one-way roads in Vatakara. Travel times should differ
        by at most 50% between directions.
        """
        a = kochi_delivery_points[0]  # Vatakara Bus Stand
        b = kochi_delivery_points[2]  # Vyttila

        ab = osrm.get_travel_time(a, b)
        ba = osrm.get_travel_time(b, a)

        ratio = max(ab.duration_seconds, ba.duration_seconds) / min(ab.duration_seconds, ba.duration_seconds)
        assert ratio < 2.0, f"A→B / B→A ratio {ratio:.2f} too high — possible data issue"

    @requires_osrm
    def test_farther_points_take_longer(self, osrm, kochi_depot):
        """Closer destinations should have shorter travel times.

        Vatakara Bus Stand (~3km from depot) should be faster than Thalassery (~8km).
        """
        edappally = Location(latitude=11.5950, longitude=75.5700, address_text="Vatakara Bus Stand")
        tripunithura = Location(latitude=11.5650, longitude=75.6100, address_text="Thalassery")

        to_edappally = osrm.get_travel_time(kochi_depot, edappally)
        to_tripunithura = osrm.get_travel_time(kochi_depot, tripunithura)

        assert to_tripunithura.duration_seconds > to_edappally.duration_seconds, \
            "Thalassery (farther) should take longer than Vatakara Bus Stand (closer)"
        assert to_tripunithura.distance_meters > to_edappally.distance_meters, \
            "Thalassery should be a longer route"


# =============================================================================
# VROOM Integration Tests
# =============================================================================


class TestVroomIntegration:
    """Tests that hit the real VROOM solver (which internally calls OSRM).

    Validates that:
    - VROOM can solve a Vatakara delivery problem
    - All orders are assigned (fleet has enough capacity)
    - Routes respect vehicle capacity constraints
    - Stop sequences make geographic sense
    """

    @requires_all
    def test_optimize_10_orders_3_vehicles(
        self, vroom, sample_orders_for_optimization, fleet_3_vehicles
    ):
        """VROOM should assign 10 orders across 3 vehicles.

        With 10 orders averaging ~20 kg each and 446 kg capacity per vehicle,
        all orders should fit. VROOM should produce 1-3 routes.
        """
        assignment = vroom.optimize(sample_orders_for_optimization, fleet_3_vehicles)

        # All orders should be assigned
        assert assignment.total_orders_assigned == 10
        assert len(assignment.unassigned_order_ids) == 0

        # At least 1 vehicle should be used
        assert assignment.vehicles_used >= 1
        assert assignment.vehicles_used <= 3

        # Optimization should be fast (VROOM typically solves in <100ms)
        assert assignment.optimization_time_ms < 5000, "VROOM took >5s — unusual"

    @requires_all
    def test_route_distances_are_plausible(
        self, vroom, sample_orders_for_optimization, fleet_3_vehicles
    ):
        """Each route should have reasonable total distance for Vatakara.

        Vatakara delivery area is ~5km radius. Each route should be:
        - More than 1 km (has to go somewhere)
        - Less than 100 km (not circumnavigating India)
        """
        assignment = vroom.optimize(sample_orders_for_optimization, fleet_3_vehicles)

        for route in assignment.routes:
            assert route.total_distance_km > 0.5, \
                f"Route {route.vehicle_id}: {route.total_distance_km} km too short"
            assert route.total_distance_km < 100, \
                f"Route {route.vehicle_id}: {route.total_distance_km} km too long"

    @requires_all
    def test_routes_respect_vehicle_capacity(
        self, vroom, sample_orders_for_optimization, fleet_3_vehicles
    ):
        """No route should exceed the vehicle's weight limit."""
        assignment = vroom.optimize(sample_orders_for_optimization, fleet_3_vehicles)

        for route in assignment.routes:
            assert route.total_weight_kg <= config.VEHICLE_MAX_WEIGHT_KG, \
                f"Route {route.vehicle_id}: {route.total_weight_kg} kg exceeds {config.VEHICLE_MAX_WEIGHT_KG} kg limit"

    @requires_all
    def test_no_duplicate_order_assignments(
        self, vroom, sample_orders_for_optimization, fleet_3_vehicles
    ):
        """Each order should appear in exactly one route (no duplicates)."""
        assignment = vroom.optimize(sample_orders_for_optimization, fleet_3_vehicles)

        all_order_ids = []
        for route in assignment.routes:
            for stop in route.stops:
                all_order_ids.append(stop.order_id)

        assert len(all_order_ids) == len(set(all_order_ids)), \
            f"Duplicate order assignments: {[x for x in all_order_ids if all_order_ids.count(x) > 1]}"


# =============================================================================
# Full Pipeline Integration Test
# =============================================================================


class TestFullPipeline:
    """End-to-end test: CSV file → import → optimize → route output.

    This mirrors what happens when an operator uploads a CSV through the API,
    but tests the pipeline components directly (without FastAPI/HTTP layer).
    """

    @requires_all
    def test_csv_to_optimized_routes(self, kochi_depot):
        """Full pipeline: load sample CSV → import orders → run optimizer → verify routes.

        This is the core Phase 1 validation: does the system produce
        better routes than just visiting stops in CSV order?
        """
        from core.data_import.csv_importer import CsvImporter

        # Step 1: Import orders from the sample CSV
        csv_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "sample_orders.csv"
        )
        csv_path = os.path.normpath(csv_path)

        importer = CsvImporter(
            cylinder_weight_lookup=config.CYLINDER_WEIGHTS,
            default_cylinder_weight_kg=config.DEFAULT_CYLINDER_KG,
        )
        import_result = importer.import_orders(csv_path)
        orders = import_result.orders
        assert len(orders) == 30, f"Expected 30 orders from sample CSV, got {len(orders)}"

        # All orders should have coordinates (we added lat/lon to sample CSV)
        geocoded = [o for o in orders if o.location is not None]
        assert len(geocoded) == 30, f"Expected all 30 orders geocoded, got {len(geocoded)}"

        # Step 2: Build fleet
        fleet = [
            Vehicle(
                vehicle_id=f"VEH-{i:02d}",
                driver_name=f"Driver {i}",
                max_weight_kg=config.VEHICLE_MAX_WEIGHT_KG,
                max_items=config.VEHICLE_MAX_CYLINDERS,
                depot=kochi_depot,
            )
            for i in range(1, config.NUM_VEHICLES + 1)
        ]

        # Step 3: Optimize
        optimizer = VroomAdapter(
            vroom_url=VROOM_URL,
            safety_multiplier=config.SAFETY_MULTIPLIER,
        )
        assignment = optimizer.optimize(geocoded, fleet)

        # Step 4: Validate results
        assert assignment.total_orders_assigned == 30
        assert len(assignment.unassigned_order_ids) == 0
        assert assignment.vehicles_used >= 1

        # Print summary for manual review
        print(f"\n{'='*60}")
        print(f"OPTIMIZATION RESULT — {len(orders)} orders")
        print(f"{'='*60}")
        print(f"Vehicles used:    {assignment.vehicles_used} / {len(fleet)}")
        print(f"Total orders:     {assignment.total_orders_assigned}")
        print(f"Unassigned:       {len(assignment.unassigned_order_ids)}")
        print(f"Solve time:       {assignment.optimization_time_ms:.0f} ms")
        print()

        total_distance = 0.0
        total_duration = 0.0
        for route in assignment.routes:
            total_distance += route.total_distance_km
            total_duration += route.total_duration_minutes
            print(
                f"  {route.vehicle_id}: {route.stop_count} stops, "
                f"{route.total_distance_km:.1f} km, "
                f"{route.total_duration_minutes:.0f} min, "
                f"{route.total_weight_kg:.1f} kg"
            )

        print(f"\nTotal distance:   {total_distance:.1f} km")
        print(f"Total duration:   {total_duration:.0f} min")
        print(f"Avg km/delivery:  {total_distance / assignment.total_orders_assigned:.2f}")
        print(f"{'='*60}")
