"""Per-driver TSP orchestrator -- groups orders by driver and runs VROOM TSP per driver.

Phase 19 replaces the single multi-vehicle CVRP optimization with N sequential
per-driver TSP calls. Each driver gets independently optimal stop ordering via
VROOM with 1 vehicle (uncapped capacity). Results are merged into a single
RouteAssignment for persistence under one optimization run.

Post-optimization validation ensures no order appears in multiple routes (OPT-04)
and geographic anomaly detection flags significant convex hull overlap between
driver delivery areas (OPT-05).

Usage:
    from core.optimizer.tsp_orchestrator import (
        group_orders_by_driver,
        optimize_per_driver,
        validate_no_overlap,
        detect_geographic_anomalies,
    )

    orders_by_driver = group_orders_by_driver(orders, order_driver_map)
    assignment, warnings = optimize_per_driver(orders_by_driver, driver_uuids, depot, optimizer)
    overlap_errors = validate_no_overlap(assignment)
    geo_warnings = detect_geographic_anomalies(assignment)
"""

import logging
import uuid

from shapely.geometry import MultiPoint

from core.models.location import Location
from core.models.order import Order
from core.models.route import RouteAssignment
from core.models.vehicle import Vehicle
from core.optimizer.vroom_adapter import VroomAdapter

logger = logging.getLogger(__name__)


def group_orders_by_driver(
    orders: list[Order],
    order_driver_map: dict[str, str],
) -> dict[str, list[Order]]:
    """Group orders by their assigned driver name.

    Takes the final geocoded orders list and a pre-built order_id -> driver_name
    map. Orders not in the map are excluded (logged as warning).

    Args:
        orders: List of geocoded Order objects to be grouped.
        order_driver_map: Mapping of order_id to driver_name, typically built
            from the preprocessed DataFrame's delivery_man column.

    Returns:
        Dictionary mapping driver_name to list of Order objects assigned to
        that driver. Drivers with no orders are not included.
    """
    groups: dict[str, list[Order]] = {}

    for order in orders:
        driver = order_driver_map.get(order.order_id)
        if not driver:
            logger.warning(
                "Order %s has no driver mapping -- excluded from optimization",
                order.order_id,
            )
            continue
        groups.setdefault(driver, []).append(order)

    return groups


def optimize_per_driver(
    orders_by_driver: dict[str, list[Order]],
    driver_uuids: dict[str, uuid.UUID],
    depot: Location,
    optimizer: VroomAdapter,
) -> tuple[RouteAssignment, list[str]]:
    """Run TSP optimization for each driver group, merge into single RouteAssignment.

    For each driver, creates a single Vehicle with uncapped capacity (99999 kg,
    999 items) at the given depot, then calls the optimizer. Results from all
    drivers are merged into one RouteAssignment with a single assignment_id.

    Partial failure handling: if one driver's VROOM call fails, that driver's
    orders become unassigned and a warning is logged. Other drivers still get
    their optimized routes.

    Args:
        orders_by_driver: Dictionary mapping driver_name to list of Order objects.
        driver_uuids: Dictionary mapping driver_name to their UUID in the
            drivers table (used for RouteDB.driver_id population during persistence).
        depot: Starting and ending location for all drivers (Vatakara depot).
        optimizer: VroomAdapter instance for running VROOM TSP calls.

    Returns:
        Tuple of (RouteAssignment, warnings). The RouteAssignment contains all
        merged routes with route_ids in R-{assignment_id}-{driver_name} format.
        Warnings is a list of warning messages for partial failures.
    """
    assignment_id = str(uuid.uuid4())[:8]
    all_routes = []
    all_unassigned: list[str] = []
    total_time_ms = 0.0
    warnings: list[str] = []

    for driver_name, driver_orders in orders_by_driver.items():
        if not driver_orders:
            logger.info("Skipping driver %s with 0 orders", driver_name)
            continue

        vehicle = Vehicle(
            vehicle_id=driver_name,
            driver_name=driver_name,
            max_weight_kg=99999.0,
            max_items=999,
            depot=depot,
        )

        try:
            result = optimizer.optimize(driver_orders, [vehicle])
            total_time_ms += result.optimization_time_ms

            for route in result.routes:
                route.route_id = f"R-{assignment_id}-{driver_name}"
                route.vehicle_id = driver_name
                route.driver_name = driver_name
                all_routes.append(route)

            all_unassigned.extend(result.unassigned_order_ids)

        except Exception:
            logger.exception(
                "VROOM optimization failed for driver %s (%d orders)",
                driver_name,
                len(driver_orders),
            )
            failed_order_ids = [o.order_id for o in driver_orders]
            all_unassigned.extend(failed_order_ids)
            warnings.append(
                f"Optimization failed for driver {driver_name}: "
                f"{len(driver_orders)} orders moved to unassigned"
            )

    return (
        RouteAssignment(
            assignment_id=assignment_id,
            routes=all_routes,
            unassigned_order_ids=all_unassigned,
            optimization_time_ms=total_time_ms,
        ),
        warnings,
    )


def validate_no_overlap(assignment: RouteAssignment) -> list[str]:
    """Check that no order appears in multiple routes.

    Post-optimization validation for OPT-04: verifies zero order overlap
    between driver routes. Uses route.vehicle_id as the driver identifier
    (contains driver name per Phase 19 convention).

    Args:
        assignment: The merged RouteAssignment from optimize_per_driver.

    Returns:
        List of error messages. Empty list means no overlaps found.
        Each error message names both drivers and the overlapping order.
    """
    seen: dict[str, str] = {}  # order_id -> driver_name (vehicle_id)
    errors: list[str] = []

    for route in assignment.routes:
        for stop in route.stops:
            if stop.order_id in seen:
                errors.append(
                    f"Order {stop.order_id} assigned to both "
                    f"{seen[stop.order_id]} and {route.vehicle_id}"
                )
            seen[stop.order_id] = route.vehicle_id

    return errors


def detect_geographic_anomalies(
    assignment: RouteAssignment,
    overlap_threshold: float = 0.30,
) -> list[str]:
    """Detect cross-driver geographic overlap using convex hulls.

    For each driver with 3+ stops, computes the convex hull of their delivery
    locations. Then checks all pairs for >threshold overlap. Uses
    max(intersection/hull_a, intersection/hull_b) as the overlap metric.

    Note: computations use unprojected lat/lon coordinates (EPSG:4326). Area
    values are in square degrees, but the overlap RATIO is valid because both
    numerator and denominator use the same units.

    Shapely uses (x, y) = (longitude, latitude) ordering for coordinates.

    Args:
        assignment: The merged RouteAssignment from optimize_per_driver.
        overlap_threshold: Fraction (0.0-1.0) above which overlap is flagged.
            Default 0.30 (30%) per CONTEXT.md decision.

    Returns:
        List of warning messages naming both drivers and the overlap percentage.
        Empty list means no significant overlaps detected.
    """
    # Build convex hulls for drivers with 3+ stops
    driver_hulls: dict[str, object] = {}

    for route in assignment.routes:
        if len(route.stops) < 3:
            continue

        points = [
            (stop.location.longitude, stop.location.latitude)
            for stop in route.stops
        ]
        hull = MultiPoint(points).convex_hull

        # Only use Polygon hulls -- LineString (collinear) or Point (coincident)
        # cannot have meaningful area overlap
        if hull.geom_type == "Polygon":
            driver_hulls[route.vehicle_id] = hull

    # Check all pairs for overlap
    warnings: list[str] = []
    drivers = list(driver_hulls.keys())

    for i in range(len(drivers)):
        for j in range(i + 1, len(drivers)):
            hull_a = driver_hulls[drivers[i]]
            hull_b = driver_hulls[drivers[j]]

            if not hull_a.intersects(hull_b):
                continue

            intersection = hull_a.intersection(hull_b)
            area_a = hull_a.area
            area_b = hull_b.area

            overlap_a = intersection.area / area_a if area_a > 0 else 0
            overlap_b = intersection.area / area_b if area_b > 0 else 0
            max_overlap = max(overlap_a, overlap_b)

            if max_overlap > overlap_threshold:
                pct = int(max_overlap * 100)
                warnings.append(
                    f"Geographic overlap: {drivers[i]} and {drivers[j]} "
                    f"have {pct}% delivery area overlap -- "
                    f"consider reassigning orders in CDCMS"
                )

    return warnings
