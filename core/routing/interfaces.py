"""Abstract interface for routing engines.

The routing engine provides travel times and distances between locations.
The optimizer uses this data (as a "distance matrix") to plan efficient routes.

Why an interface?
We start with OSRM (free, fast, self-hosted) but may switch to Valhalla
or fall back to Google Maps API. The interface isolates calling code from
the specific engine.
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from core.models.location import Location


class TravelTime(BaseModel):
    """Travel time and distance between two points.

    Attributes:
        duration_seconds: Travel time in seconds.
        distance_meters: Travel distance in meters.
    """

    duration_seconds: float = Field(..., ge=0)
    distance_meters: float = Field(..., ge=0)

    @property
    def duration_minutes(self) -> float:
        return self.duration_seconds / 60.0

    @property
    def distance_km(self) -> float:
        return self.distance_meters / 1000.0


class DistanceMatrix(BaseModel):
    """NxN matrix of travel times and distances between N locations.

    Used by the optimizer to evaluate route options without making
    individual routing calls for every pair. OSRM can compute this
    in a single API call — much faster than N² individual queries.

    Attributes:
        durations: NxN matrix of travel durations in seconds.
            durations[i][j] = time from location i to location j.
        distances: NxN matrix of travel distances in meters.
            distances[i][j] = distance from location i to location j.
        locations: The locations in the same order as the matrix indices.
    """

    durations: list[list[float]]
    distances: list[list[float]]
    locations: list[Location]

    @property
    def size(self) -> int:
        return len(self.locations)


@runtime_checkable
class RoutingEngine(Protocol):
    """Protocol for any routing engine that provides travel times.

    Implementations:
    - OsrmAdapter: Self-hosted OSRM (recommended for production)
    - (Future) ValhallAdapter: Self-hosted Valhalla
    - (Future) GoogleMapsAdapter: Google Directions API (fallback)
    """

    def get_travel_time(
        self, origin: Location, destination: Location
    ) -> TravelTime:
        """Get travel time/distance between two points."""
        ...

    def get_distance_matrix(
        self, locations: list[Location]
    ) -> DistanceMatrix:
        """Compute NxN distance/duration matrix for a set of locations.

        This is the key input to the route optimizer.
        """
        ...
