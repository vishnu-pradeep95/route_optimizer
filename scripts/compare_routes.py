#!/usr/bin/env python3
"""Compare optimized routes against sequential (naive) baseline.

Phase 1 success criteria: optimizer route is ≥15% shorter than naive
on ≥70% of test runs.

What this script does:
  1. Loads orders from a CSV file (with lat/lon coordinates)
  2. Computes "naive" route: visit stops in CSV order, one vehicle
  3. Runs VROOM optimizer: capacity-constrained multi-vehicle routing
  4. Compares total distance and time, prints improvement metrics

Usage:
  # Requires Docker services running: docker compose up -d
  python scripts/compare_routes.py data/sample_orders.csv

  # With custom config (overrides Kerala defaults):
  python scripts/compare_routes.py data/sample_orders.csv \\
      --osrm-url http://localhost:5000 \\
      --vroom-url http://localhost:3000 \\
      --num-vehicles 5

The naive baseline simulates what a dispatcher might do manually:
divide orders evenly across vehicles in CSV order. The optimizer
should produce significantly shorter routes by clustering nearby
stops and sequencing them efficiently.

NOTE: This script imports from apps.kerala_delivery.config for default
values. To use with a different business config, override via CLI args.
"""

import argparse
import os
import sys

# Add project root to path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data_import.csv_importer import CsvImporter
from core.models.vehicle import Vehicle
from core.routing.osrm_adapter import OsrmAdapter
from core.optimizer.vroom_adapter import VroomAdapter
from apps.kerala_delivery import config


def compute_naive_distance(orders: list, depot, osrm: OsrmAdapter, num_vehicles: int) -> dict:
    """Compute total distance visiting stops in CSV order.

    Naive strategy: split orders evenly across vehicles, visit each
    vehicle's orders in the order they appear in the CSV.
    Returns dict with total_distance_km and total_duration_minutes.

    Why this is the baseline:
    - Many small businesses do this: first order goes on first truck,
      second on second, etc. — no geographic optimization at all.
    - Comparing against this shows the value of route optimization.
    """
    geocoded = [o for o in orders if o.location is not None]
    if not geocoded:
        return {"total_distance_km": 0, "total_duration_minutes": 0, "routes": []}

    # Split orders evenly across vehicles (round-robin)
    n_vehicles = min(num_vehicles, len(geocoded))
    vehicle_orders: list[list] = [[] for _ in range(n_vehicles)]
    for i, order in enumerate(geocoded):
        vehicle_orders[i % n_vehicles].append(order)

    total_dist_m = 0.0
    total_dur_s = 0.0
    route_summaries = []

    for v_idx, v_orders in enumerate(vehicle_orders):
        if not v_orders:
            continue

        route_dist_m = 0.0
        route_dur_s = 0.0

        # Depot → first stop
        tt = osrm.get_travel_time(depot, v_orders[0].location)
        route_dist_m += tt.distance_meters
        route_dur_s += tt.duration_seconds

        # Stop-to-stop in CSV order
        for j in range(1, len(v_orders)):
            tt = osrm.get_travel_time(v_orders[j - 1].location, v_orders[j].location)
            route_dist_m += tt.distance_meters
            route_dur_s += tt.duration_seconds

        # Last stop → depot
        tt = osrm.get_travel_time(v_orders[-1].location, depot)
        route_dist_m += tt.distance_meters
        route_dur_s += tt.duration_seconds

        # Add service time at each stop (default 5 min from config)
        service_time_s = len(v_orders) * 5 * 60  # 5 min per stop

        route_summaries.append({
            "vehicle": f"VEH-{v_idx + 1:02d}",
            "stops": len(v_orders),
            "distance_km": route_dist_m / 1000,
            "duration_min": (route_dur_s + service_time_s) / 60,
        })

        total_dist_m += route_dist_m
        total_dur_s += route_dur_s + service_time_s

    return {
        "total_distance_km": total_dist_m / 1000,
        "total_duration_minutes": total_dur_s / 60,
        "routes": route_summaries,
    }


def run_optimizer(
    orders: list, depot, vroom_url: str, safety_multiplier: float,
    num_vehicles: int, max_weight: float,
) -> dict:
    """Run VROOM optimizer and return results as dict."""
    geocoded = [o for o in orders if o.location is not None]
    if not geocoded:
        return {"total_distance_km": 0, "total_duration_minutes": 0, "routes": []}

    fleet = [
        Vehicle(
            vehicle_id=f"VEH-{i:02d}",
            driver_name=f"Driver {i}",
            max_weight_kg=max_weight,
            max_items=config.VEHICLE_MAX_CYLINDERS,
            depot=depot,
        )
        for i in range(1, num_vehicles + 1)
    ]

    optimizer = VroomAdapter(
        vroom_url=vroom_url,
        safety_multiplier=safety_multiplier,
    )
    assignment = optimizer.optimize(geocoded, fleet)

    total_dist = sum(r.total_distance_km for r in assignment.routes)
    total_dur = sum(r.total_duration_minutes for r in assignment.routes)

    route_summaries = [
        {
            "vehicle": r.vehicle_id,
            "stops": r.stop_count,
            "distance_km": r.total_distance_km,
            "duration_min": r.total_duration_minutes,
        }
        for r in assignment.routes
    ]

    return {
        "total_distance_km": total_dist,
        "total_duration_minutes": total_dur,
        "vehicles_used": assignment.vehicles_used,
        "solve_time_ms": assignment.optimization_time_ms,
        "routes": route_summaries,
    }


def main():
    parser = argparse.ArgumentParser(description="Compare optimized vs naive routing")
    parser.add_argument("csv_file", help="Path to CSV with delivery orders")
    # CLI overrides for Kerala defaults — makes the script reusable for other configs
    parser.add_argument("--osrm-url", default=None, help="OSRM server URL (default: from config)")
    parser.add_argument("--vroom-url", default=None, help="VROOM server URL (default: from config)")
    parser.add_argument("--num-vehicles", type=int, default=None, help="Number of vehicles (default: from config)")
    parser.add_argument("--max-weight", type=float, default=None, help="Max weight per vehicle in kg (default: from config)")
    parser.add_argument("--safety-multiplier", type=float, default=None, help="Safety multiplier (default: from config)")
    args = parser.parse_args()

    # Resolve config values: CLI overrides > Kerala defaults
    osrm_url = args.osrm_url or config.OSRM_URL
    vroom_url = args.vroom_url or config.VROOM_URL
    num_vehicles = args.num_vehicles or config.NUM_VEHICLES
    max_weight = args.max_weight or config.VEHICLE_MAX_WEIGHT_KG
    safety_multiplier = args.safety_multiplier or config.SAFETY_MULTIPLIER

    if not os.path.exists(args.csv_file):
        print(f"Error: File not found: {args.csv_file}")
        sys.exit(1)

    # Load orders
    print(f"Loading orders from {args.csv_file}...")
    importer = CsvImporter(
        cylinder_weight_lookup=config.CYLINDER_WEIGHTS,
        default_cylinder_weight_kg=config.DEFAULT_CYLINDER_KG,
    )
    orders = importer.import_orders(args.csv_file)
    geocoded = [o for o in orders if o.location is not None]
    print(f"  {len(orders)} orders loaded, {len(geocoded)} with coordinates")

    if not geocoded:
        print("Error: No geocoded orders. Add latitude/longitude to the CSV.")
        sys.exit(1)

    depot = config.DEPOT_LOCATION
    osrm = OsrmAdapter(base_url=osrm_url, safety_multiplier=safety_multiplier)

    # Run baseline
    print(f"\nComputing naive baseline (CSV order, round-robin across {num_vehicles} vehicles)...")
    naive = compute_naive_distance(orders, depot, osrm, num_vehicles)

    # Run optimizer
    print("Running VROOM optimizer...")
    optimized = run_optimizer(orders, depot, vroom_url, safety_multiplier, num_vehicles, max_weight)

    # Print comparison
    print(f"\n{'='*65}")
    print(f"  ROUTE COMPARISON — {len(geocoded)} deliveries")
    print(f"{'='*65}")
    print()

    # Naive results
    print("  NAIVE (CSV order, round-robin):")
    for r in naive["routes"]:
        print(f"    {r['vehicle']}: {r['stops']} stops, {r['distance_km']:.1f} km, {r['duration_min']:.0f} min")
    print(f"    TOTAL: {naive['total_distance_km']:.1f} km, {naive['total_duration_minutes']:.0f} min")
    print()

    # Optimized results
    print(f"  OPTIMIZED ({optimized.get('vehicles_used', '?')} vehicles, solved in {optimized.get('solve_time_ms', '?'):.0f} ms):")
    for r in optimized["routes"]:
        print(f"    {r['vehicle']}: {r['stops']} stops, {r['distance_km']:.1f} km, {r['duration_min']:.0f} min")
    print(f"    TOTAL: {optimized['total_distance_km']:.1f} km, {optimized['total_duration_minutes']:.0f} min")
    print()

    # Improvement metrics
    dist_improvement = (1 - optimized["total_distance_km"] / naive["total_distance_km"]) * 100
    time_improvement = (1 - optimized["total_duration_minutes"] / naive["total_duration_minutes"]) * 100

    print(f"  IMPROVEMENT:")
    print(f"    Distance: {dist_improvement:+.1f}% ({naive['total_distance_km']:.1f} → {optimized['total_distance_km']:.1f} km)")
    print(f"    Time:     {time_improvement:+.1f}% ({naive['total_duration_minutes']:.0f} → {optimized['total_duration_minutes']:.0f} min)")
    print(f"    Avg km/delivery: {optimized['total_distance_km'] / len(geocoded):.2f}")
    print()

    # Phase 1 success check
    if dist_improvement >= 15:
        print(f"  ✓ PASS: {dist_improvement:.1f}% distance reduction (target: ≥15%)")
    else:
        print(f"  ✗ BELOW TARGET: {dist_improvement:.1f}% distance reduction (target: ≥15%)")
    print(f"{'='*65}")


if __name__ == "__main__":
    main()
