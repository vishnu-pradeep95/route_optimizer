"""Shared test fixtures using real Kerala coordinates.

Why real coordinates?
- Tests with (0,0) miss real-world issues like road gaps in OSM data
- Kerala coordinates validate our models handle actual Indian locations
- These are public landmarks, not customer addresses (privacy safe)
"""

import pytest

from core.models.location import Location
from core.models.order import Order
from core.models.vehicle import Vehicle


@pytest.fixture
def kochi_depot():
    """Central Kochi depot location (near MG Road area)."""
    return Location(
        latitude=9.9716,
        longitude=76.2846,
        address_text="LPG Godown - Main Depot",
    )


@pytest.fixture
def sample_locations():
    """5 delivery locations within ~5km of Kochi depot.
    These are real public landmarks in Kochi.
    """
    return [
        Location(latitude=9.9816, longitude=76.2996, address_text="Edappally Junction"),
        Location(latitude=9.9567, longitude=76.2998, address_text="Palarivattom"),
        Location(latitude=9.9312, longitude=76.2673, address_text="Marine Drive"),
        Location(latitude=9.9674, longitude=76.2855, address_text="MG Road"),
        Location(latitude=9.9478, longitude=76.2870, address_text="Panampilly Nagar"),
    ]


@pytest.fixture
def sample_orders(sample_locations):
    """5 sample LPG delivery orders with geocoded locations."""
    orders = []
    for i, loc in enumerate(sample_locations):
        orders.append(
            Order(
                order_id=f"TEST-{i+1:03d}",
                location=loc,
                address_raw=loc.address_text or f"Test Address {i+1}",
                customer_ref=f"CUST-{i+1:03d}",
                weight_kg=14.2 * (1 + i % 2),  # alternating 14.2 and 28.4 kg
                quantity=1 + i % 2,
            )
        )
    return orders


@pytest.fixture
def sample_vehicle(kochi_depot):
    """A single Piaggio Ape Xtra LDX delivery vehicle."""
    return Vehicle(
        vehicle_id="VEH-01",
        driver_name="Test Driver",
        max_weight_kg=446.0,
        max_items=30,
        depot=kochi_depot,
    )


@pytest.fixture
def sample_fleet(kochi_depot):
    """Fleet of 3 delivery vehicles (for multi-vehicle tests)."""
    return [
        Vehicle(
            vehicle_id=f"VEH-{i:02d}",
            driver_name=f"Driver {i}",
            max_weight_kg=446.0,
            max_items=30,
            depot=kochi_depot,
        )
        for i in range(1, 4)
    ]
