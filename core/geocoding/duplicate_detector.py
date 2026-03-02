"""Duplicate location detection for geocoded orders.

Detects orders with different addresses that resolve to suspiciously close
GPS coordinates. Uses Haversine distance with confidence-weighted thresholds
and Union-Find clustering for transitive grouping.

Why this module?
When office staff upload CDCMS delivery orders, data entry errors sometimes
cause different addresses to geocode to nearly identical GPS coordinates.
This module flags those clusters so staff can investigate before dispatch.

Algorithm:
1. Filter to geocoded orders only
2. Compute normalized addresses for same-address exclusion
3. Pairwise O(n^2) Haversine distance comparison
4. Confidence-weighted threshold selection (wider for lower confidence)
5. Union-Find for transitive clustering
6. Extract and return clusters of size >= 2

Performance: O(n^2) pairwise is fine for typical uploads of 40-50 orders
(~1,225 comparisons). No spatial index needed at this scale.
"""

import math
from dataclasses import dataclass

from core.geocoding.normalize import normalize_address
from core.models.order import Order


@dataclass
class DuplicateCluster:
    """A group of orders with suspiciously close GPS coordinates.

    Attributes:
        order_ids: Order IDs in this cluster.
        addresses: Original address text for each order.
        max_distance_m: Largest pairwise distance within the cluster (meters).
        center_lat: Centroid latitude of the cluster.
        center_lon: Centroid longitude of the cluster.
    """

    order_ids: list[str]
    addresses: list[str]
    max_distance_m: float
    center_lat: float
    center_lon: float


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two GPS coordinates.

    Uses the standard Haversine formula with Earth radius 6,371,000 m.
    Accurate to <0.5% for distances under 1 km at Kerala latitudes.
    """
    R = 6_371_000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _confidence_tier(confidence: float) -> str:
    """Map a 0.0-1.0 confidence score to a threshold tier name.

    Tiers map to Google's location_type values:
    - >= 0.90 -> "rooftop" (ROOFTOP: building-level)
    - >= 0.70 -> "interpolated" (RANGE_INTERPOLATED: street-level)
    - >= 0.50 -> "geometric_center" (GEOMETRIC_CENTER: area center)
    - < 0.50 -> "approximate" (APPROXIMATE: neighborhood-level)
    """
    if confidence >= 0.90:
        return "rooftop"
    elif confidence >= 0.70:
        return "interpolated"
    elif confidence >= 0.50:
        return "geometric_center"
    else:
        return "approximate"


def detect_duplicate_locations(
    orders: list[Order],
    thresholds: dict[str, float],
) -> list[DuplicateCluster]:
    """Detect orders with different addresses that resolve to nearby coordinates.

    Args:
        orders: List of orders (non-geocoded ones are silently skipped).
        thresholds: Dict mapping tier name to distance threshold in meters.
            Example: {"rooftop": 10, "interpolated": 20,
                      "geometric_center": 50, "approximate": 100}

    Returns:
        List of DuplicateCluster objects, each containing 2+ orders whose
        different addresses resolve to suspiciously close GPS coordinates.

    Notes:
        - Orders with the same normalized address are excluded (legitimate
          multi-cylinder deliveries to the same household).
        - For mixed-confidence pairs, the wider (max) threshold is used
          because the less-accurate result dominates the uncertainty.
        - Orders without coordinates (location=None) are silently skipped.
    """
    # Filter to geocoded orders only
    geocoded = [o for o in orders if o.is_geocoded and o.location]
    if len(geocoded) < 2:
        return []

    # Build normalized address map for same-address exclusion
    norm_addrs = [normalize_address(o.address_raw) for o in geocoded]

    # Union-Find for transitive clustering
    n = len(geocoded)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # Path compression (halving)
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    # Pairwise comparison
    for i in range(n):
        for j in range(i + 1, n):
            # Skip same normalized address (legitimate multi-cylinder delivery)
            if norm_addrs[i] == norm_addrs[j]:
                continue

            oi, oj = geocoded[i], geocoded[j]
            dist = haversine_meters(
                oi.location.latitude,
                oi.location.longitude,
                oj.location.latitude,
                oj.location.longitude,
            )

            # Use the wider threshold (dominated by less-accurate result)
            conf_i = oi.location.geocode_confidence if oi.location.geocode_confidence is not None else 0.4
            conf_j = oj.location.geocode_confidence if oj.location.geocode_confidence is not None else 0.4
            tier_i = _confidence_tier(conf_i)
            tier_j = _confidence_tier(conf_j)
            threshold = max(thresholds.get(tier_i, 50.0), thresholds.get(tier_j, 50.0))

            if dist <= threshold:
                union(i, j)

    # Extract clusters of size >= 2
    clusters_map: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        clusters_map.setdefault(root, []).append(i)

    result = []
    for indices in clusters_map.values():
        if len(indices) < 2:
            continue
        cluster_orders = [geocoded[i] for i in indices]

        # Calculate max pairwise distance within cluster
        max_dist = 0.0
        for a in range(len(indices)):
            for b in range(a + 1, len(indices)):
                oa, ob = geocoded[indices[a]], geocoded[indices[b]]
                d = haversine_meters(
                    oa.location.latitude,
                    oa.location.longitude,
                    ob.location.latitude,
                    ob.location.longitude,
                )
                max_dist = max(max_dist, d)

        # Centroid of the cluster
        center_lat = sum(o.location.latitude for o in cluster_orders) / len(cluster_orders)
        center_lon = sum(o.location.longitude for o in cluster_orders) / len(cluster_orders)

        result.append(
            DuplicateCluster(
                order_ids=[o.order_id for o in cluster_orders],
                addresses=[o.address_raw for o in cluster_orders],
                max_distance_m=round(max_dist, 1),
                center_lat=center_lat,
                center_lon=center_lon,
            )
        )

    return result
