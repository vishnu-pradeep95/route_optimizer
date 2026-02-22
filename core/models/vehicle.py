"""Vehicle model — a delivery vehicle with capacity constraints.

For the Kerala LPG business, this is a Piaggio Ape Xtra LDX three-wheeler.
Rated payload ~496 kg, but we use 90% (446 kg) as the working limit for safety.
Each domestic LPG cylinder weighs ~14.2 kg, so max ~31 cylinders per load.
"""

from pydantic import BaseModel, Field

from core.models.location import Location


class Vehicle(BaseModel):
    """A delivery vehicle with its constraints and starting position.

    Why model vehicles explicitly instead of just a capacity number?
    - Different vehicles may have different capacities (e.g., a mix of
      Ape Xtra LDX and smaller Ape City models)
    - Some vehicles may be electric with range constraints
    - We need to track which driver is assigned to which vehicle
    - The optimizer needs vehicle IDs to assign routes

    Attributes:
        vehicle_id: Unique identifier (e.g., registration number or internal code).
        driver_name: Driver assigned to this vehicle today.
        max_weight_kg: Maximum payload in kg (after safety margin applied).
        max_items: Maximum number of items (cylinders) the vehicle can carry.
            This is a separate constraint from weight — sometimes volume/count
            limits before weight does.
        depot: Starting and ending location for this vehicle.
        speed_limit_kmh: Max allowed speed for this vehicle type in urban zones.
            Used for safety alerts, not for routing (OSRM uses road-level speeds).
    """

    vehicle_id: str = Field(..., description="Unique vehicle identifier")
    driver_name: str = Field(default="", description="Driver assigned today")
    max_weight_kg: float = Field(
        ..., gt=0, description="Max payload in kg (with safety margin)"
    )
    max_items: int = Field(
        default=999,
        ge=1,
        description="Max item count (cylinders, packages, etc.)",
    )
    depot: Location = Field(..., description="Start/end location (godown)")
    speed_limit_kmh: float = Field(
        default=40.0, ge=0, description="Speed alert threshold in km/h"
    )
