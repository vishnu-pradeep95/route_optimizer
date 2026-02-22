"""Abstract interface for route optimizers.

The optimizer takes a list of orders + vehicles and produces the best
assignment of orders to vehicles and the optimal visit sequence for each.

This is the core intelligence of the system — the module that answers:
"Which driver should deliver which orders, and in what order?"
"""

from typing import Protocol, runtime_checkable

from core.models.order import Order
from core.models.route import RouteAssignment
from core.models.vehicle import Vehicle


@runtime_checkable
class RouteOptimizer(Protocol):
    """Protocol for any route optimization engine.

    Implementations:
    - VroomAdapter: VROOM solver (millisecond solves, Docker-hosted)
    - (Future) OrToolsAdapter: Google OR-Tools (more custom constraints)
    """

    def optimize(
        self,
        orders: list[Order],
        vehicles: list[Vehicle],
    ) -> RouteAssignment:
        """Assign orders to vehicles and compute optimal routes.

        Args:
            orders: Delivery orders to be routed. Must be geocoded (have locations).
            vehicles: Available vehicles with capacity and depot info.

        Returns:
            RouteAssignment with optimized routes per vehicle,
            plus any unassigned orders.

        Raises:
            ValueError: If orders are not geocoded or inputs are invalid.
        """
        ...
