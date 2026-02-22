"""Location model — a GPS coordinate with optional address metadata.

Why a dedicated Location model instead of a plain (lat, lon) tuple?
- Type safety: prevents mixing up lat/lon order (a common bug)
- Validation: Pydantic enforces valid coordinate ranges
- Extensibility: we can add address_text, geocode_confidence, etc.
- Reuse: every module (geocoding, routing, optimizer) shares this type
"""

from pydantic import BaseModel, Field


class Location(BaseModel):
    """A geographic point with optional descriptive metadata.

    Attributes:
        latitude: WGS84 latitude (-90 to 90). Kerala range: ~8.2 to ~12.8.
        longitude: WGS84 longitude (-180 to 180). Kerala range: ~74.8 to ~77.4.
        address_text: Human-readable address for driver display.
        place_id: Google Maps place_id or similar, for cache lookups.
        geocode_confidence: 0.0–1.0 score from geocoding provider.
            None means the coordinate was manually provided (e.g., GPS pin).
    """

    latitude: float = Field(..., ge=-90, le=90, description="WGS84 latitude")
    longitude: float = Field(..., ge=-180, le=180, description="WGS84 longitude")
    address_text: str | None = Field(
        default=None, description="Human-readable address for display"
    )
    place_id: str | None = Field(
        default=None, description="Geocoding provider's place ID for caching"
    )
    geocode_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Geocoding confidence score (0=low, 1=high). None if GPS-provided.",
    )

    def to_lon_lat_tuple(self) -> tuple[float, float]:
        """Return (longitude, latitude) — the format OSRM and most GeoJSON use.

        Why lon,lat not lat,lon?
        GeoJSON spec (RFC 7946) and OSRM both use [longitude, latitude] order.
        Our model stores lat,lon (human-friendly), but this method converts
        for API calls.
        """
        return (self.longitude, self.latitude)
