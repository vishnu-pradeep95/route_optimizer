"""Shared test fixtures using real Kerala coordinates.

Why real coordinates?
- Tests with (0,0) miss real-world issues like road gaps in OSM data
- Kerala coordinates validate our models handle actual Indian locations
- These are public landmarks, not customer addresses (privacy safe)

Coordinates: Vatakara, Kozhikode district (production depot area).
"""

import pytest

from apps.kerala_delivery.config import DEPOT_LOCATION
from core.models.location import Location
from core.models.order import Order
from core.models.vehicle import Vehicle


@pytest.fixture
def vatakara_depot():
    """Production depot location -- Vatakara, Kozhikode district."""
    return Location(
        latitude=11.624443730714066,
        longitude=75.57964507762223,
        address_text="LPG Godown (Main Depot)",
    )


@pytest.fixture
def kochi_depot(vatakara_depot):
    """DEPRECATED: Use vatakara_depot. Alias kept for backward compatibility."""
    return vatakara_depot


@pytest.fixture(autouse=True)
def _verify_depot_matches_config(vatakara_depot):
    """Guard: test depot must always match production config."""
    assert vatakara_depot.latitude == pytest.approx(DEPOT_LOCATION.latitude, abs=0.001)
    assert vatakara_depot.longitude == pytest.approx(DEPOT_LOCATION.longitude, abs=0.001)


@pytest.fixture
def sample_locations():
    """5 delivery locations within ~10km of Vatakara depot.
    Real public landmarks near Vatakara, Kozhikode district.
    """
    return [
        Location(latitude=11.5950, longitude=75.5700, address_text="Vatakara Bus Stand"),
        Location(latitude=11.6100, longitude=75.5650, address_text="Vatakara Railway Station"),
        Location(latitude=11.6350, longitude=75.5900, address_text="Chorode Junction"),
        Location(latitude=11.5800, longitude=75.5850, address_text="Memunda"),
        Location(latitude=11.6200, longitude=75.5500, address_text="Edakkad"),
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
def sample_vehicle(vatakara_depot):
    """A single Piaggio Ape Xtra LDX delivery vehicle."""
    return Vehicle(
        vehicle_id="VEH-01",
        driver_name="Test Driver",
        max_weight_kg=446.0,
        max_items=30,
        depot=vatakara_depot,
    )


@pytest.fixture
def sample_fleet(vatakara_depot):
    """Fleet of 3 delivery vehicles (for multi-vehicle tests)."""
    return [
        Vehicle(
            vehicle_id=f"VEH-{i:02d}",
            driver_name=f"Driver {i}",
            max_weight_kg=446.0,
            max_items=30,
            depot=vatakara_depot,
        )
        for i in range(1, 4)
    ]
