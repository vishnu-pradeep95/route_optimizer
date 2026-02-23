"""Abstract interface for geocoding providers.

Why an interface?
Geocoding is the biggest accuracy challenge for Indian addresses.
We'll likely use Google Maps API first, but may switch to or supplement
with Latlong.ai, OLA Maps, or a local cache. The interface lets us
swap providers without touching optimizer or API code.
"""

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from core.models.location import Location


class GeocodingResult(BaseModel):
    """Result of a geocoding attempt.

    Why Pydantic BaseModel?
    Consistency with all other data models in the project, plus automatic
    JSON serialization for API responses and cache storage.

    Attributes:
        location: The resolved GPS coordinates (None if geocoding failed).
        confidence: 0.0–1.0 confidence score.
        formatted_address: Provider's cleaned-up address text.
        raw_response: Full provider response for debugging.
    """

    location: Location | None = Field(
        default=None, description="Resolved GPS coordinates (None if failed)"
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    formatted_address: str = Field(default="")
    raw_response: dict[str, Any] = Field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.location is not None


@runtime_checkable
class Geocoder(Protocol):
    """Protocol for geocoding text addresses into GPS coordinates.

    Implementations:
    - GoogleGeocoder: Google Maps Geocoding API (best for Indian addresses)
    - CacheGeocoder: PostGIS-backed local cache of previously geocoded addresses
    - (Future) LatlongGeocoder: Latlong.ai (India-specific)
    """

    def geocode(self, address: str) -> GeocodingResult:
        """Convert a text address to GPS coordinates.

        Args:
            address: Free-text address string.

        Returns:
            GeocodingResult with location (if found) and confidence score.
        """
        ...

    def geocode_batch(self, addresses: list[str]) -> list[GeocodingResult]:
        """Geocode multiple addresses. Default: sequential calls to geocode().

        Implementations may override for batch efficiency.
        """
        ...


@runtime_checkable
class AsyncGeocoder(Protocol):
    """Async variant of the Geocoder protocol for DB-backed implementations.

    Why a separate async protocol?
    CachedGeocoder uses SQLAlchemy's async session for PostGIS lookups,
    which requires ``await``. Callers that work with CachedGeocoder must
    be async-aware (``await geocoder.geocode(...)``), while callers using
    GoogleGeocoder can stay synchronous.

    Structural subtyping: any class with matching async methods satisfies
    this protocol — no inheritance required.

    Implementations:
    - CachedGeocoder: PostGIS-backed cache + upstream delegation
    """

    async def geocode(self, address: str) -> GeocodingResult:
        """Async geocode an address.

        Args:
            address: Free-text address string.

        Returns:
            GeocodingResult with location (if found) and confidence score.
        """
        ...

    async def geocode_batch(self, addresses: list[str]) -> list[GeocodingResult]:
        """Async geocode multiple addresses."""
        ...
