"""Order model — a single delivery to be fulfilled.

Designed around LPG cylinder delivery data from HPCL's CDCMS system,
but generic enough for any delivery business. CDCMS exports typically
include: customer ID, address, cylinder type (14.2 kg domestic or 19 kg
commercial), quantity, and booking reference.
"""

from datetime import datetime, time
from enum import StrEnum

from pydantic import BaseModel, Field

from core.models.location import Location


class OrderStatus(StrEnum):
    """Lifecycle of a delivery order.

    Why StrEnum? So status values serialize as readable strings in JSON/CSV,
    not opaque integers. StrEnum requires Python 3.11+.
    """

    PENDING = "pending"  # Imported, not yet assigned to a route
    ASSIGNED = "assigned"  # Assigned to a driver/route
    IN_TRANSIT = "in_transit"  # Driver has started the route
    DELIVERED = "delivered"  # Successfully delivered
    FAILED = "failed"  # Delivery attempt failed (customer absent, etc.)


class Order(BaseModel):
    """A single delivery order to be routed and fulfilled.

    Attributes:
        order_id: Unique identifier (from CDCMS booking reference or generated).
        location: GPS coordinates of the delivery point. May be None initially
            if the address hasn't been geocoded yet.
        address_raw: The original address text from CDCMS, before geocoding.
            Kept separate from location.address_text so we preserve the source.
        customer_ref: Pseudonymized customer reference. NOT the real name.
            PII stays in the source spreadsheet — see privacy rules in design doc.
        weight_kg: Total weight of this delivery in kg.
            Domestic LPG cylinder = ~14.2 kg, commercial = ~19 kg.
            Used by the optimizer for vehicle capacity constraints.
        quantity: Number of cylinders (or items) in this order.
        priority: 1=high (urgent/VIP), 2=normal, 3=low. Default normal.
        service_time_minutes: Estimated time at the stop (unloading, paperwork).
            Default 5 min for a standard LPG cylinder swap.
        notes: Delivery instructions ("Ring bell twice", "Leave at gate").
        status: Current lifecycle status of this order.
        created_at: When this order was imported into our system.
    """

    order_id: str = Field(..., description="Unique order/booking reference")
    location: Location | None = Field(
        default=None, description="Geocoded delivery coordinates (None if not yet geocoded)"
    )
    address_raw: str = Field(
        ..., description="Original address text from source system (CDCMS etc.)"
    )
    customer_ref: str = Field(
        ..., description="Pseudonymized customer reference (NOT real name)"
    )
    weight_kg: float = Field(
        ..., gt=0, description="Total weight of delivery in kg"
    )
    quantity: int = Field(default=1, ge=1, description="Number of items/cylinders")
    priority: int = Field(default=2, ge=1, le=3, description="1=high, 2=normal, 3=low")
    service_time_minutes: int = Field(
        default=5,
        ge=0,
        description="Minutes needed at stop for unloading/paperwork",
    )
    notes: str = Field(default="", description="Delivery instructions for driver")
    status: OrderStatus = Field(default=OrderStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.now)
    # Phase 2: delivery time windows — "deliver between 09:00 and 12:00"
    # Used by VROOM's VRPTW solver to respect customer time preferences.
    # If both are None, the order has no time constraint (pure CVRP).
    delivery_window_start: time | None = Field(
        default=None, description="Earliest acceptable delivery time (HH:MM)"
    )
    delivery_window_end: time | None = Field(
        default=None, description="Latest acceptable delivery time (HH:MM)"
    )

    @property
    def is_geocoded(self) -> bool:
        """Check if this order has been geocoded (has GPS coordinates)."""
        return self.location is not None
