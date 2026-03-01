"""QR code and Google Maps URL helpers for the Kerala LPG delivery system.

Extracted from main.py to keep the API module focused on HTTP concerns.
This module handles:
1. Building Google Maps Directions URLs from ordered stop lists
2. Splitting long routes into Google Maps-compatible segments (max 9 waypoints)
3. Generating QR codes (SVG for inline display, PNG for print)

Why Google Maps URLs instead of our own navigation?
Drivers are familiar with Google Maps. It handles traffic, voice guidance,
lane guidance, and offline maps. Building all that ourselves would take months.
Our value is in route OPTIMIZATION — Google Maps handles NAVIGATION.

Google Maps URL reference:
https://developers.google.com/maps/documentation/urls/get-started
"""

import base64
import io

import qrcode
import qrcode.image.svg

# Google Maps Directions URLs support a maximum of 9 waypoints between
# the origin and destination (11 total stops). Routes with more stops
# are automatically split into segments, each with its own URL and QR code.
# See: https://developers.google.com/maps/documentation/urls/get-started
GOOGLE_MAPS_MAX_WAYPOINTS = 9


def build_google_maps_url(stops: list[dict]) -> str:
    """Build a Google Maps Directions URL from an ordered list of stops.

    Args:
        stops: List of dicts with 'latitude' and 'longitude' keys,
               ordered by delivery sequence.

    Returns:
        Google Maps URL that opens navigation with all stops as waypoints.
        Empty string if stops is empty.

    Why Google Maps URL instead of our own map?
    Drivers are familiar with Google Maps navigation. It handles traffic,
    voice guidance, lane guidance, and offline maps. Building all that
    ourselves would take months. Our value is in route OPTIMIZATION —
    Google Maps handles NAVIGATION.
    """
    if not stops:
        return ""

    origin = stops[0]
    destination = stops[-1]

    url = (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={origin['latitude']},{origin['longitude']}"
        f"&destination={destination['latitude']},{destination['longitude']}"
        "&travelmode=driving"
    )

    # Add intermediate stops as waypoints (everything except first and last)
    if len(stops) > 2:
        waypoints = "|".join(
            f"{s['latitude']},{s['longitude']}" for s in stops[1:-1]
        )
        url += f"&waypoints={waypoints}"

    return url


def generate_qr_svg(data: str, box_size: int = 10) -> str:
    """Generate a QR code as an SVG string.

    Why SVG instead of PNG?
    - Scales perfectly for print (no pixelation at any size)
    - Smaller file size for embedding in HTML
    - No need for image hosting or base64 encoding of binary data
    - Can be styled with CSS if needed

    Args:
        data: The string to encode (typically a URL).
        box_size: Size of each QR module in SVG units.

    Returns:
        Complete SVG markup as a string.
    """
    # SvgPathImage produces a single <path> element — cleaner than
    # individual <rect> elements (SvgImage). Fewer DOM nodes = faster
    # rendering when embedding multiple QR codes on a print sheet.
    factory = qrcode.image.svg.SvgPathImage
    qr = qrcode.QRCode(
        version=None,  # Auto-detect smallest version that fits the data
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=2,  # Minimum quiet zone for reliable scanning
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(image_factory=factory)
    # Convert to string — SvgPathImage.to_string() returns bytes
    return img.to_string(encoding="unicode")


def generate_qr_base64_png(data: str, box_size: int = 10) -> str:
    """Generate a QR code as a base64-encoded PNG for embedding in HTML.

    Used for the printable QR sheet where inline images are more reliable
    across printers than inline SVG.

    Args:
        data: The string to encode (typically a URL).
        box_size: Size of each QR module in pixels.

    Returns:
        Base64-encoded PNG string (without data: prefix).
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def split_route_into_segments(stops: list[dict]) -> list[dict]:
    """Split a route with many stops into Google Maps-compatible segments.

    Google Maps URLs support max 9 waypoints (+ origin + destination = 11 stops).
    Routes with more than 11 stops are split into overlapping segments so the
    driver can navigate each part sequentially.

    Why overlap? The destination of segment N is the origin of segment N+1.
    This gives the driver a continuous path — Google Maps doesn't know about
    our other segments, so overlapping prevents a gap.

    Args:
        stops: All stops in delivery order, each with latitude/longitude.

    Returns:
        List of segment dicts, each with: segment, start_stop, end_stop,
        stop_count, url, qr_svg.
    """
    # 11 stops fit in one URL (1 origin + 9 waypoints + 1 destination)
    max_stops_per_segment = GOOGLE_MAPS_MAX_WAYPOINTS + 2  # = 11

    if len(stops) <= max_stops_per_segment:
        url = build_google_maps_url(stops)
        return [{
            "segment": 1,
            "start_stop": 1,
            "end_stop": len(stops),
            "stop_count": len(stops),
            "url": url,
            "qr_svg": generate_qr_svg(url),
        }]

    segments = []
    segment_num = 1
    i = 0

    while i < len(stops):
        segment_stops = stops[i : i + max_stops_per_segment]
        url = build_google_maps_url(segment_stops)

        segments.append({
            "segment": segment_num,
            "start_stop": i + 1,
            "end_stop": i + len(segment_stops),
            "stop_count": len(segment_stops),
            "url": url,
            "qr_svg": generate_qr_svg(url),
        })

        # Advance by (max - 1) so the last stop of this segment becomes
        # the first stop of the next segment (overlap for continuity)
        i += max_stops_per_segment - 1
        segment_num += 1

    return segments
