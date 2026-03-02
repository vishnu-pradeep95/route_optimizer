"""Tests for duplicate location detection in geocoded orders.

Verifies that detect_duplicate_locations() correctly:
- Computes Haversine distance (same point, known distance)
- Returns empty for fewer than 2 geocoded orders
- Excludes orders with the same normalized address (multi-cylinder)
- Detects clusters of different addresses at nearby coordinates
- Skips non-geocoded orders (location=None)
- Uses confidence-weighted thresholds (wider for lower confidence)
- Uses the max threshold for mixed-confidence pairs
- Groups transitive duplicates into a single cluster (Union-Find)
- Produces correct DuplicateCluster fields (order_ids, addresses, max_distance_m, center)

All tests use Order and Location constructors directly -- no DB or mocks needed.
"""

import math

import pytest

from core.geocoding.duplicate_detector import (
    DuplicateCluster,
    detect_duplicate_locations,
    haversine_meters,
    _confidence_tier,
)
from core.models.location import Location
from core.models.order import Order


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_order(
    order_id: str,
    address: str,
    lat: float | None = None,
    lon: float | None = None,
    confidence: float | None = None,
) -> Order:
    """Create an Order for testing. If lat/lon are None, order is not geocoded."""
    location = None
    if lat is not None and lon is not None:
        location = Location(
            latitude=lat,
            longitude=lon,
            geocode_confidence=confidence,
        )
    return Order(
        order_id=order_id,
        address_raw=address,
        customer_ref="CUST-TEST",
        weight_kg=14.2,
        location=location,
    )


# Default thresholds matching apps/kerala_delivery/config.py
DEFAULT_THRESHOLDS = {
    "rooftop": 10.0,
    "interpolated": 20.0,
    "geometric_center": 50.0,
    "approximate": 100.0,
}


# ===========================================================================
# Haversine Tests
# ===========================================================================

class TestHaversineMeters:
    """Tests for the haversine_meters distance function."""

    def test_same_point_returns_zero(self):
        """Same GPS coordinates should return exactly 0.0 meters."""
        dist = haversine_meters(11.6, 75.5, 11.6, 75.5)
        assert dist == 0.0

    def test_known_latitude_distance(self):
        """0.001 degrees of latitude at Kerala (~11.6 N) is approximately 111m.

        At the equator, 1 degree of latitude = ~111,195m, so 0.001 deg ~ 111.2m.
        At 11.6 N, latitude degrees are nearly the same length (~110.9m per 0.001 deg).
        We allow 1% tolerance.
        """
        dist = haversine_meters(11.600, 75.500, 11.601, 75.500)
        assert abs(dist - 111.0) < 2.0, f"Expected ~111m, got {dist:.1f}m"

    def test_known_longitude_distance(self):
        """0.001 degrees of longitude at 11.6 N should be ~108.9m.

        Longitude degrees shrink by cos(lat). At 11.6 N:
        111,195 * cos(11.6 deg) ~ 108,900m per degree, so 0.001 deg ~ 108.9m.
        """
        dist = haversine_meters(11.600, 75.500, 11.600, 75.501)
        expected = 111195 * math.cos(math.radians(11.6)) / 1000  # meters per 0.001 deg
        assert abs(dist - expected) < 2.0, f"Expected ~{expected:.1f}m, got {dist:.1f}m"

    def test_symmetry(self):
        """Distance A->B should equal distance B->A."""
        d1 = haversine_meters(11.6, 75.5, 11.7, 75.6)
        d2 = haversine_meters(11.7, 75.6, 11.6, 75.5)
        assert abs(d1 - d2) < 0.001


# ===========================================================================
# Confidence Tier Tests
# ===========================================================================

class TestConfidenceTier:
    """Tests for _confidence_tier mapping."""

    def test_rooftop(self):
        assert _confidence_tier(0.95) == "rooftop"
        assert _confidence_tier(0.90) == "rooftop"

    def test_interpolated(self):
        assert _confidence_tier(0.80) == "interpolated"
        assert _confidence_tier(0.70) == "interpolated"

    def test_geometric_center(self):
        assert _confidence_tier(0.60) == "geometric_center"
        assert _confidence_tier(0.50) == "geometric_center"

    def test_approximate(self):
        assert _confidence_tier(0.40) == "approximate"
        assert _confidence_tier(0.10) == "approximate"
        assert _confidence_tier(0.0) == "approximate"


# ===========================================================================
# Duplicate Detection Tests
# ===========================================================================

class TestDetectDuplicateLocations:
    """Tests for the main detect_duplicate_locations function."""

    def test_empty_list(self):
        """No orders should return empty clusters."""
        result = detect_duplicate_locations([], DEFAULT_THRESHOLDS)
        assert result == []

    def test_single_order(self):
        """Fewer than 2 geocoded orders should return empty."""
        orders = [_make_order("O1", "Address 1", 11.6, 75.5)]
        result = detect_duplicate_locations(orders, DEFAULT_THRESHOLDS)
        assert result == []

    def test_same_normalized_address_excluded(self):
        """Orders with the same normalized address should NOT be flagged as duplicates.

        Multi-cylinder deliveries to the same address are legitimate.
        """
        # Same address, same coordinates -- should be excluded
        orders = [
            _make_order("O1", "M.G. Road, Vatakara", 11.600, 75.500, 0.95),
            _make_order("O2", "M.G. Road, Vatakara", 11.600, 75.500, 0.95),
        ]
        result = detect_duplicate_locations(orders, DEFAULT_THRESHOLDS)
        assert result == [], "Same-address orders should be excluded (multi-cylinder)"

    def test_different_addresses_nearby_detected(self):
        """Two different addresses resolving to nearby coordinates should be flagged."""
        # ~5m apart (well within 10m ROOFTOP threshold)
        orders = [
            _make_order("O1", "House A, MG Road", 11.600000, 75.500000, 0.95),
            _make_order("O2", "House B, Near MG Road", 11.600045, 75.500000, 0.95),
        ]
        result = detect_duplicate_locations(orders, DEFAULT_THRESHOLDS)
        assert len(result) == 1
        cluster = result[0]
        assert set(cluster.order_ids) == {"O1", "O2"}
        assert len(cluster.addresses) == 2

    def test_non_geocoded_orders_skipped(self):
        """Orders without coordinates (location=None) should be silently skipped."""
        orders = [
            _make_order("O1", "Address A", lat=None, lon=None),  # Not geocoded
            _make_order("O2", "Address B", 11.600, 75.500, 0.95),
        ]
        result = detect_duplicate_locations(orders, DEFAULT_THRESHOLDS)
        assert result == [], "Should return empty -- only 1 geocoded order"

    def test_rooftop_pair_tight_threshold(self):
        """Two ROOFTOP results 12m apart should NOT be flagged (outside 10m threshold)."""
        # 12m apart at Kerala latitude is about 0.000108 degrees of latitude
        offset = 12.0 / 111000  # ~0.000108 degrees
        orders = [
            _make_order("O1", "Address A", 11.600000, 75.500, 0.95),
            _make_order("O2", "Address B", 11.600000 + offset, 75.500, 0.95),
        ]
        result = detect_duplicate_locations(orders, DEFAULT_THRESHOLDS)
        assert result == [], "12m apart with ROOFTOP threshold (10m) should not be flagged"

    def test_geometric_center_pair_wide_threshold(self):
        """Two GEOMETRIC_CENTER results 30m apart should be flagged (within 50m threshold)."""
        offset = 30.0 / 111000  # ~0.000270 degrees
        orders = [
            _make_order("O1", "Address A", 11.600000, 75.500, 0.60),
            _make_order("O2", "Address B", 11.600000 + offset, 75.500, 0.60),
        ]
        result = detect_duplicate_locations(orders, DEFAULT_THRESHOLDS)
        assert len(result) == 1, "30m apart with GEOMETRIC_CENTER threshold (50m) should be flagged"

    def test_mixed_confidence_uses_wider_threshold(self):
        """Mixed confidence pair should use the wider (max) threshold.

        One ROOFTOP (10m threshold) + one GEOMETRIC_CENTER (50m threshold)
        at 30m apart: should be flagged (30m < 50m max threshold).
        """
        offset = 30.0 / 111000
        orders = [
            _make_order("O1", "Address A", 11.600000, 75.500, 0.95),  # ROOFTOP
            _make_order("O2", "Address B", 11.600000 + offset, 75.500, 0.60),  # GEOMETRIC_CENTER
        ]
        result = detect_duplicate_locations(orders, DEFAULT_THRESHOLDS)
        assert len(result) == 1, "Mixed pair should use wider threshold (50m), 30m apart should be flagged"

    def test_transitive_clustering(self):
        """If A near B and B near C, all three should be in one cluster (not two)."""
        # Place A, B, C each ~5m apart along a line (within ROOFTOP 10m threshold)
        offset = 5.0 / 111000
        orders = [
            _make_order("O1", "Address A", 11.600000, 75.500, 0.95),
            _make_order("O2", "Address B", 11.600000 + offset, 75.500, 0.95),
            _make_order("O3", "Address C", 11.600000 + 2 * offset, 75.500, 0.95),
        ]
        result = detect_duplicate_locations(orders, DEFAULT_THRESHOLDS)
        assert len(result) == 1, "Should form one transitive cluster, not two"
        assert set(result[0].order_ids) == {"O1", "O2", "O3"}

    def test_cluster_fields_correct(self):
        """DuplicateCluster should have correct order_ids, addresses, max_distance_m, center."""
        orders = [
            _make_order("O1", "Address Alpha", 11.600000, 75.500000, 0.95),
            _make_order("O2", "Address Beta", 11.600045, 75.500000, 0.95),
        ]
        result = detect_duplicate_locations(orders, DEFAULT_THRESHOLDS)
        assert len(result) == 1
        cluster = result[0]
        assert cluster.order_ids == ["O1", "O2"]
        assert cluster.addresses == ["Address Alpha", "Address Beta"]
        assert cluster.max_distance_m > 0
        assert cluster.max_distance_m < 10.0  # ~5m apart
        # Center should be midpoint
        assert abs(cluster.center_lat - 11.6000225) < 0.0001
        assert abs(cluster.center_lon - 75.500) < 0.0001

    def test_no_confidence_defaults_to_approximate(self):
        """Orders with geocode_confidence=None should default to 'approximate' tier (100m threshold)."""
        offset = 80.0 / 111000  # ~80m apart
        orders = [
            _make_order("O1", "Address A", 11.600000, 75.500, None),  # No confidence
            _make_order("O2", "Address B", 11.600000 + offset, 75.500, None),
        ]
        result = detect_duplicate_locations(orders, DEFAULT_THRESHOLDS)
        assert len(result) == 1, "80m apart with approximate threshold (100m) should be flagged"

    def test_separate_clusters_not_merged(self):
        """Two distinct pairs far from each other should form two separate clusters."""
        orders = [
            # Cluster 1: two orders ~5m apart
            _make_order("O1", "Address A", 11.600000, 75.500000, 0.95),
            _make_order("O2", "Address B", 11.600045, 75.500000, 0.95),
            # Cluster 2: two orders ~5m apart, far from cluster 1
            _make_order("O3", "Address C", 11.700000, 75.600000, 0.95),
            _make_order("O4", "Address D", 11.700045, 75.600000, 0.95),
        ]
        result = detect_duplicate_locations(orders, DEFAULT_THRESHOLDS)
        assert len(result) == 2
        cluster_ids = [set(c.order_ids) for c in result]
        assert {"O1", "O2"} in cluster_ids
        assert {"O3", "O4"} in cluster_ids

    def test_far_apart_orders_no_cluster(self):
        """Orders far apart (> all thresholds) should not be clustered."""
        orders = [
            _make_order("O1", "Address A", 11.600, 75.500, 0.95),
            _make_order("O2", "Address B", 11.700, 75.600, 0.95),  # ~14km away
        ]
        result = detect_duplicate_locations(orders, DEFAULT_THRESHOLDS)
        assert result == []
