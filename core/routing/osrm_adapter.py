"""OSRM (Open Source Routing Machine) adapter.

OSRM is a high-performance routing engine built on OpenStreetMap data.
We run it locally via Docker with Kerala map data (~130 MB PBF file).
It returns travel times and distances in milliseconds — fast enough
for real-time re-optimization.

API docs: https://project-osrm.org/docs/v5.24.0/api/
Docker: https://hub.docker.com/r/osrm/osrm-backend

Why OSRM over Google Maps for routing?
- Free (zero per-query cost) vs $5-15/day for Google Directions API
- Faster (local queries vs network round-trips)
- Full control over speed profiles (we can cap three-wheeler speeds)
- No vendor lock-in
Trade-off: we must self-host and update map data manually.
"""

import httpx

from core.models.location import Location
from core.routing.interfaces import DistanceMatrix, TravelTime


class OsrmAdapter:
    """Routing engine adapter for a self-hosted OSRM instance.

    Requires OSRM running locally (typically via Docker on port 5000).
    Uses the Table API for distance matrices and Route API for single pairs.

    Usage:
        osrm = OsrmAdapter(base_url="http://localhost:5000")
        matrix = osrm.get_distance_matrix(locations)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:5000",
        safety_multiplier: float = 1.3,
        profile: str = "driving",
    ):
        """Initialize OSRM adapter.

        Args:
            base_url: URL of the OSRM instance.
            safety_multiplier: Factor applied to all travel times to account
                for real-world conditions (Kerala roads, three-wheeler speeds,
                traffic). 1.3 means 30% safety buffer on top of OSRM estimates.
                See design doc Section 3 for rationale.
            profile: OSRM routing profile. "driving" for cars/three-wheelers.
        """
        self.base_url = base_url.rstrip("/")
        self.safety_multiplier = safety_multiplier
        self.profile = profile

    def get_travel_time(
        self, origin: Location, destination: Location
    ) -> TravelTime:
        """Get travel time and distance between two points via OSRM Route API.

        Uses OSRM's /route/v1/ endpoint for a single origin→destination query.
        Applies the safety multiplier to the duration.
        """
        # OSRM uses lon,lat format (not lat,lon)
        coords = (
            f"{origin.longitude},{origin.latitude};"
            f"{destination.longitude},{destination.latitude}"
        )
        url = f"{self.base_url}/route/v1/{self.profile}/{coords}"

        response = httpx.get(url, params={"overview": "false"}, timeout=10.0)
        response.raise_for_status()
        data = response.json()

        if data["code"] != "Ok" or not data.get("routes"):
            raise RuntimeError(f"OSRM route failed: {data.get('code', 'unknown')}")

        route = data["routes"][0]
        return TravelTime(
            # Apply safety multiplier: OSRM times are optimistic for Kerala
            duration_seconds=route["duration"] * self.safety_multiplier,
            distance_meters=route["distance"],
        )

    def get_distance_matrix(
        self, locations: list[Location]
    ) -> DistanceMatrix:
        """Compute NxN travel time/distance matrix via OSRM Table API.

        This is the critical call for route optimization. OSRM computes
        the full matrix in a single request, much faster than N² individual
        route queries.

        OSRM Table API: /table/v1/{profile}/{coordinates}
        Returns durations (always) and distances (with annotations=distance).
        """
        if len(locations) < 2:
            raise ValueError("Need at least 2 locations for a distance matrix")

        # Build coordinate string: lon1,lat1;lon2,lat2;...
        coords = ";".join(
            f"{loc.longitude},{loc.latitude}" for loc in locations
        )
        url = f"{self.base_url}/table/v1/{self.profile}/{coords}"

        response = httpx.get(
            url,
            params={"annotations": "duration,distance"},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

        if data["code"] != "Ok":
            raise RuntimeError(f"OSRM table failed: {data.get('code', 'unknown')}")

        # Apply safety multiplier to all durations
        # Why? OSRM assumes ideal driving conditions. Kerala three-wheeler
        # reality = narrow roads + traffic + slower speeds. 1.3× is our buffer.
        raw_durations = data["durations"]
        adjusted_durations = [
            [d * self.safety_multiplier if d is not None else None for d in row]
            for row in raw_durations
        ]

        return DistanceMatrix(
            durations=adjusted_durations,
            distances=data["distances"],
            locations=locations,
        )
