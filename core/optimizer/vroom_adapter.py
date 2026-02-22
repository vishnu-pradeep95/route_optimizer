"""VROOM adapter — route optimization via the VROOM solver.

VROOM (Vehicle Routing Open-source Optimization Machine) is a high-performance
solver for vehicle routing problems. It solves CVRP/VRPTW instances with
hundreds of stops in milliseconds using custom meta-heuristics.

We run VROOM as a Docker container that connects to our OSRM instance
for travel time data. This means we don't need to precompute distance
matrices ourselves — VROOM handles it internally.

API docs: https://github.com/VROOM-Project/vroom/blob/master/docs/API.md
Docker: https://hub.docker.com/r/vroomvrp/vroom-docker

Why VROOM over OR-Tools?
- Millisecond solve times (OR-Tools takes seconds)
- Built-in OSRM integration (no separate matrix computation)
- Docker deployment (no Python dependency management)
- Supports CVRP, VRPTW, PDPTW out of the box
Trade-off: less control over custom constraints than OR-Tools.
"""

import uuid
from datetime import datetime

import httpx

from core.models.location import Location
from core.models.order import Order
from core.models.route import Route, RouteAssignment, RouteStop
from core.models.vehicle import Vehicle


class VroomAdapter:
    """Route optimizer using a self-hosted VROOM instance.

    Requires VROOM running (typically Docker on port 3000) configured
    to use our OSRM instance for routing data.

    Usage:
        optimizer = VroomAdapter(vroom_url="http://localhost:3000")
        assignment = optimizer.optimize(orders, vehicles)
        for route in assignment.routes:
            print(f"Vehicle {route.vehicle_id}: {route.stop_count} stops")
    """

    def __init__(
        self,
        vroom_url: str = "http://localhost:3000",
        safety_multiplier: float = 1.3,
    ):
        """Initialize VROOM adapter.

        Args:
            vroom_url: URL of the VROOM HTTP server.
            safety_multiplier: Applied to VROOM's duration estimates for display.
                VROOM gets raw OSRM times; we multiply for realistic estimates
                in the output routes.
        """
        self.vroom_url = vroom_url.rstrip("/")
        self.safety_multiplier = safety_multiplier

    def optimize(
        self,
        orders: list[Order],
        vehicles: list[Vehicle],
    ) -> RouteAssignment:
        """Run VROOM optimization and return assigned routes.

        Builds a VROOM-compatible JSON request from our Order/Vehicle models,
        sends it to the VROOM server, and converts the solution back to our
        Route/RouteStop models.

        VROOM request format:
        {
          "vehicles": [{"id": 0, "start": [lon, lat], "end": [lon, lat], "capacity": [kg]}],
          "jobs": [{"id": 0, "location": [lon, lat], "delivery": [kg], "service": seconds}]
        }
        """
        # Validate all orders are geocoded
        ungeocoded = [o.order_id for o in orders if not o.is_geocoded]
        if ungeocoded:
            raise ValueError(
                f"Cannot optimize: {len(ungeocoded)} orders not geocoded: "
                f"{ungeocoded[:5]}{'...' if len(ungeocoded) > 5 else ''}"
            )

        # Build VROOM request
        request_body = self._build_request(orders, vehicles)

        # Call VROOM API
        start_time = datetime.now()
        response = httpx.post(
            self.vroom_url,
            json=request_body,
            timeout=60.0,
        )
        response.raise_for_status()
        solve_ms = (datetime.now() - start_time).total_seconds() * 1000

        vroom_result = response.json()

        # Convert VROOM response to our RouteAssignment model
        return self._parse_response(vroom_result, orders, vehicles, solve_ms)

    def _build_request(
        self, orders: list[Order], vehicles: list[Vehicle]
    ) -> dict:
        """Convert our models to VROOM's JSON request format.

        VROOM uses integer IDs internally. We map:
        - jobs: indexed 0..N-1 matching orders list
        - vehicles: indexed 0..M-1 matching vehicles list

        VROOM coordinates are [longitude, latitude] — GeoJSON order.
        """
        # Build vehicles array
        vroom_vehicles = []
        for idx, vehicle in enumerate(vehicles):
            depot_coords = [vehicle.depot.longitude, vehicle.depot.latitude]
            vroom_vehicles.append(
                {
                    "id": idx,
                    "start": depot_coords,
                    "end": depot_coords,  # Return to depot after deliveries
                    # VROOM capacity is an array — we use [weight_kg, item_count]
                    # This lets us enforce both weight AND item count limits.
                    # int() truncates fractional kg (e.g. 446.5 → 446). This is
                    # intentional: VROOM requires integer capacities, and
                    # rounding down is safer than rounding up for weight limits.
                    "capacity": [
                        int(vehicle.max_weight_kg),
                        vehicle.max_items,
                    ],
                    "description": vehicle.vehicle_id,
                }
            )

        # Build jobs array (one per order)
        vroom_jobs = []
        for idx, order in enumerate(orders):
            loc = order.location  # Already validated as not None
            vroom_jobs.append(
                {
                    "id": idx,
                    "location": [loc.longitude, loc.latitude],
                    # delivery = amount consumed from vehicle capacity at this stop
                    "delivery": [int(order.weight_kg), order.quantity],
                    # service time in seconds (time spent at the stop)
                    "service": order.service_time_minutes * 60,
                    "description": order.order_id,
                    # Priority: VROOM uses higher = more important (0-100)
                    # Our model: 1=high, 2=normal, 3=low → invert
                    "priority": max(0, 100 - (order.priority * 30)),
                }
            )

        # Why options.g = true?
        # VROOM only returns distance fields (route-level and step-level) when
        # geometry is requested. Without this, distance is omitted from the
        # response entirely, and we can't compute route distances.
        # The "g" flag also makes VROOM include a polyline geometry string in
        # the response, which we don't use yet but costs negligible overhead.
        # See: https://github.com/VROOM-Project/vroom/blob/master/docs/API.md#output
        return {
            "vehicles": vroom_vehicles,
            "jobs": vroom_jobs,
            "options": {"g": True},
        }

    def _parse_response(
        self,
        vroom_result: dict,
        orders: list[Order],
        vehicles: list[Vehicle],
        solve_ms: float,
    ) -> RouteAssignment:
        """Convert VROOM's response into our RouteAssignment model.

        VROOM response structure:
        {
          "routes": [
            {
              "vehicle": 0,
              "steps": [
                {"type": "start", ...},
                {"type": "job", "id": 3, "arrival": 1234, "distance": 5678, ...},
                {"type": "end", ...}
              ],
              "distance": total_meters,
              "duration": total_seconds
            }
          ],
          "unassigned": [{"id": 2, "type": "job"}]
        }
        """
        assignment_id = str(uuid.uuid4())[:8]
        routes: list[Route] = []

        for vroom_route in vroom_result.get("routes", []):
            vehicle_idx = vroom_route["vehicle"]
            vehicle = vehicles[vehicle_idx]

            stops: list[RouteStop] = []
            sequence = 0

            # VROOM step-level `distance` and `duration` are CUMULATIVE from route
            # start, not incremental between stops. We need to track the previous
            # step's values and subtract to get per-leg distances/durations.
            # See: https://github.com/VROOM-Project/vroom/blob/master/docs/API.md
            prev_cumulative_distance = 0  # meters from route start
            prev_cumulative_duration = 0  # seconds from route start

            for step in vroom_route.get("steps", []):
                if step["type"] != "job":
                    # Still track cumulative values from "start" step so the
                    # first job's leg includes depot→first-stop distance.
                    prev_cumulative_distance = step.get("distance", 0)
                    prev_cumulative_duration = step.get("duration", 0)
                    continue

                sequence += 1
                order_idx = step["id"]
                order = orders[order_idx]

                # Compute incremental (per-leg) values by subtracting previous
                cumulative_distance = step.get("distance", 0)
                cumulative_duration = step.get("duration", 0)
                leg_distance_m = cumulative_distance - prev_cumulative_distance
                leg_duration_s = cumulative_duration - prev_cumulative_duration

                stops.append(
                    RouteStop(
                        order_id=order.order_id,
                        location=order.location,
                        address_display=order.location.address_text or order.address_raw,
                        sequence=sequence,
                        distance_from_prev_km=leg_distance_m / 1000.0,
                        duration_from_prev_minutes=(
                            leg_duration_s * self.safety_multiplier / 60.0
                        ),
                        weight_kg=order.weight_kg,
                        quantity=order.quantity,
                        notes=order.notes,
                    )
                )

                prev_cumulative_distance = cumulative_distance
                prev_cumulative_duration = cumulative_duration

            if stops:
                route = Route(
                    route_id=f"R-{assignment_id}-{vehicle.vehicle_id}",
                    vehicle_id=vehicle.vehicle_id,
                    driver_name=vehicle.driver_name,
                    stops=stops,
                    total_distance_km=vroom_route.get("distance", 0) / 1000.0,
                    total_duration_minutes=(
                        vroom_route.get("duration", 0) * self.safety_multiplier / 60.0
                    ),
                    total_weight_kg=sum(s.weight_kg for s in stops),
                    total_items=sum(s.quantity for s in stops),
                )
                routes.append(route)

        # Collect unassigned orders
        unassigned_ids = [
            orders[u["id"]].order_id
            for u in vroom_result.get("unassigned", [])
        ]

        return RouteAssignment(
            assignment_id=assignment_id,
            routes=routes,
            unassigned_order_ids=unassigned_ids,
            optimization_time_ms=solve_ms,
        )
