"""Route model — an ordered sequence of delivery stops assigned to one vehicle.

This is the OUTPUT of the optimizer: for each vehicle, a Route describes
which orders to deliver and in what sequence, along with estimated times
and distances.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from core.models.location import Location


def _utcnow() -> datetime:
    """Return timezone-aware UTC now.

    Why a helper instead of inline lambda?
    Pydantic's default_factory must be a callable. Using
    datetime.now(timezone.utc) directly would evaluate at import time
    (not per-instance). This wrapper defers evaluation to instance creation.
    """
    return datetime.now(timezone.utc)


class RouteStop(BaseModel):
    """A single stop on a delivery route.

    Attributes:
        order_id: Reference to the Order being delivered at this stop.
        location: GPS coordinates of this stop.
        address_display: Short address text for the driver's screen.
        sequence: Position in the route (1-based). Drivers follow this order.
        estimated_arrival: When the driver is expected to reach this stop.
        estimated_departure: When the driver is expected to leave this stop.
        distance_from_prev_km: Distance from the previous stop (or depot) in km.
        duration_from_prev_minutes: Travel time from the previous stop in minutes.
            Includes the safety multiplier — this is the "real-world" estimate.
        weight_kg: Weight of delivery at this stop (for display/verification).
        quantity: Number of items at this stop.
        notes: Delivery instructions.
        status: Current status (pending, delivered, failed).
    """

    order_id: str
    location: Location
    address_display: str = ""
    sequence: int = Field(..., ge=1)
    estimated_arrival: datetime | None = None
    estimated_departure: datetime | None = None
    distance_from_prev_km: float = Field(default=0.0, ge=0)
    duration_from_prev_minutes: float = Field(default=0.0, ge=0)
    weight_kg: float = Field(default=0.0, ge=0)
    quantity: int = Field(default=1, ge=1)
    notes: str = ""
    status: str = "pending"


class Route(BaseModel):
    """A complete delivery route for a single vehicle.

    Attributes:
        route_id: Unique identifier for this route.
        vehicle_id: Which vehicle runs this route.
        driver_name: Driver assigned (denormalized for convenience in driver app).
        stops: Ordered list of delivery stops.
        total_distance_km: Total route distance in km (depot → stops → depot).
        total_duration_minutes: Total estimated route time in minutes.
        total_weight_kg: Sum of all delivery weights on this route.
        total_items: Sum of all items on this route.
        created_at: When the optimizer generated this route.
    """

    route_id: str
    vehicle_id: str
    driver_name: str = ""
    stops: list[RouteStop] = Field(default_factory=list)
    total_distance_km: float = Field(default=0.0, ge=0)
    total_duration_minutes: float = Field(default=0.0, ge=0)
    total_weight_kg: float = Field(default=0.0, ge=0)
    total_items: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=_utcnow)

    @property
    def stop_count(self) -> int:
        """Number of delivery stops (excludes depot start/end)."""
        return len(self.stops)


class RouteAssignment(BaseModel):
    """The complete output of one optimization run: all routes for all vehicles.

    This is what the optimizer returns after processing a batch of orders.
    It includes the routes for each vehicle plus any orders that couldn't
    be assigned (e.g., over total fleet capacity).

    Attributes:
        assignment_id: Unique identifier for this optimization run.
        routes: List of routes, one per vehicle used.
        unassigned_order_ids: Orders that couldn't fit into any route.
        optimization_time_ms: How long the optimizer took in milliseconds.
        created_at: Timestamp of this optimization run.
    """

    assignment_id: str
    routes: list[Route] = Field(default_factory=list)
    unassigned_order_ids: list[str] = Field(default_factory=list)
    optimization_time_ms: float = Field(default=0.0, ge=0)
    created_at: datetime = Field(default_factory=_utcnow)

    @property
    def total_orders_assigned(self) -> int:
        """Total number of orders assigned across all routes."""
        return sum(r.stop_count for r in self.routes)

    @property
    def vehicles_used(self) -> int:
        """Number of vehicles with at least one stop."""
        return len([r for r in self.routes if r.stop_count > 0])
