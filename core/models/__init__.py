# core/models — Shared Pydantic data models for the route optimization platform.
# These define the "language" all modules use to communicate.

from core.models.location import Location
from core.models.order import Order, OrderStatus
from core.models.vehicle import Vehicle
from core.models.route import Route, RouteStop, RouteAssignment

__all__ = [
    "Location",
    "Order",
    "OrderStatus",
    "Vehicle",
    "Route",
    "RouteStop",
    "RouteAssignment",
]
