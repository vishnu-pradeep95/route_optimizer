"""Tests for the QR code and Google Maps URL helper module.

Tests the extracted helper functions that build Google Maps navigation
URLs and generate QR codes (SVG and PNG) for the driver QR sheet workflow.

These are pure functions with no database or network dependency — all tests
run without Docker or external services.

Module under test: apps/kerala_delivery/api/qr_helpers.py
"""

import base64

import pytest

from apps.kerala_delivery.api.qr_helpers import (
    GOOGLE_MAPS_MAX_WAYPOINTS,
    build_google_maps_url,
    generate_qr_base64_png,
    generate_qr_svg,
    split_route_into_segments,
)


# =============================================================================
# Fixtures — reusable stop data
# =============================================================================


@pytest.fixture
def two_stops():
    """Minimal route: origin + destination (no waypoints)."""
    return [
        {"latitude": 9.97, "longitude": 76.28},
        {"latitude": 9.98, "longitude": 76.29},
    ]


@pytest.fixture
def three_stops():
    """Route with origin + 1 waypoint + destination."""
    return [
        {"latitude": 9.97, "longitude": 76.28},
        {"latitude": 9.975, "longitude": 76.285},
        {"latitude": 9.98, "longitude": 76.29},
    ]


@pytest.fixture
def eleven_stops():
    """Exactly 11 stops — maximum that fits in one Google Maps URL.

    Google Maps supports 9 waypoints + origin + destination = 11 stops.
    """
    return [{"latitude": 9.97 + i * 0.001, "longitude": 76.28} for i in range(11)]


@pytest.fixture
def fifteen_stops():
    """15 stops — requires route splitting into multiple segments."""
    return [{"latitude": 9.97 + i * 0.001, "longitude": 76.28} for i in range(15)]


# =============================================================================
# build_google_maps_url tests
# =============================================================================


class TestBuildGoogleMapsUrl:
    """Test Google Maps Directions URL construction."""

    def test_empty_stops_returns_empty_string(self):
        """No stops → empty URL (guard clause)."""
        assert build_google_maps_url([]) == ""

    def test_single_stop_same_origin_destination(self):
        """Single stop → origin and destination are the same point."""
        stops = [{"latitude": 9.97, "longitude": 76.28}]
        url = build_google_maps_url(stops)
        assert "origin=9.97,76.28" in url
        assert "destination=9.97,76.28" in url
        assert "waypoints" not in url

    def test_two_stops_no_waypoints(self, two_stops):
        """Two stops → origin + destination, no waypoints."""
        url = build_google_maps_url(two_stops)
        assert "origin=9.97,76.28" in url
        assert "destination=9.98,76.29" in url
        assert "waypoints" not in url
        assert "travelmode=driving" in url

    def test_three_stops_has_waypoint(self, three_stops):
        """Three stops → origin + 1 waypoint + destination."""
        url = build_google_maps_url(three_stops)
        assert "origin=9.97,76.28" in url
        assert "destination=9.98,76.29" in url
        assert "waypoints=9.975,76.285" in url

    def test_many_waypoints_pipe_separated(self):
        """Multiple intermediate stops are pipe-separated in waypoints param."""
        stops = [{"latitude": 9.97 + i * 0.001, "longitude": 76.28} for i in range(5)]
        url = build_google_maps_url(stops)
        # 3 intermediate stops should be pipe-separated
        assert url.count("|") == 2  # 3 waypoints = 2 pipe separators

    def test_url_starts_with_google_maps_base(self, two_stops):
        """URL must start with the correct Google Maps Directions base."""
        url = build_google_maps_url(two_stops)
        assert url.startswith("https://www.google.com/maps/dir/?api=1")

    def test_url_uses_driving_mode(self, two_stops):
        """Travel mode must always be 'driving' (delivery vehicles)."""
        url = build_google_maps_url(two_stops)
        assert "travelmode=driving" in url


# =============================================================================
# generate_qr_svg tests
# =============================================================================


class TestGenerateQrSvg:
    """Test SVG QR code generation."""

    def test_returns_valid_svg(self):
        """QR SVG should contain proper SVG tags."""
        svg = generate_qr_svg("https://example.com")
        assert "<svg" in svg
        assert "</svg>" in svg

    def test_uses_path_element(self):
        """SvgPathImage should produce <path> elements (not <rect>)."""
        svg = generate_qr_svg("https://example.com")
        assert "<path" in svg

    def test_different_data_produces_different_svg(self):
        """Different input data should produce different QR codes."""
        svg1 = generate_qr_svg("https://example.com/route1")
        svg2 = generate_qr_svg("https://example.com/route2")
        assert svg1 != svg2

    def test_custom_box_size(self):
        """Custom box_size should change the SVG viewBox dimensions.

        The qrcode library uses box_size to scale the SVG coordinate system.
        A larger box_size means larger width/height attributes in the SVG tag.
        """
        small = generate_qr_svg("test", box_size=5)
        large = generate_qr_svg("test", box_size=20)
        # Both are valid SVG — check viewBox reflects different scale
        assert 'width="' in small
        assert 'width="' in large
        # Different box_size → different SVG output
        assert small != large


# =============================================================================
# generate_qr_base64_png tests
# =============================================================================


class TestGenerateQrBase64Png:
    """Test PNG QR code generation (base64-encoded)."""

    def test_returns_valid_base64(self):
        """Output should be valid base64 that decodes without error."""
        png_b64 = generate_qr_base64_png("https://example.com")
        decoded = base64.b64decode(png_b64)
        assert len(decoded) > 0

    def test_decoded_is_png(self):
        """Decoded data should start with PNG magic bytes."""
        png_b64 = generate_qr_base64_png("https://example.com")
        decoded = base64.b64decode(png_b64)
        assert decoded[:4] == b"\x89PNG"

    def test_no_data_prefix(self):
        """Output should NOT include 'data:image/png;base64,' prefix.

        The caller adds the prefix when embedding in HTML.
        """
        png_b64 = generate_qr_base64_png("https://example.com")
        assert not png_b64.startswith("data:")


# =============================================================================
# split_route_into_segments tests
# =============================================================================


class TestSplitRouteIntoSegments:
    """Test route splitting for Google Maps waypoint limit."""

    def test_max_waypoints_constant(self):
        """GOOGLE_MAPS_MAX_WAYPOINTS should be 9 (Google's limit)."""
        assert GOOGLE_MAPS_MAX_WAYPOINTS == 9

    def test_short_route_single_segment(self):
        """Route with 8 stops → 1 segment."""
        stops = [{"latitude": 9.97 + i * 0.001, "longitude": 76.28} for i in range(8)]
        segments = split_route_into_segments(stops)
        assert len(segments) == 1
        assert segments[0]["segment"] == 1
        assert segments[0]["stop_count"] == 8

    def test_exactly_11_stops_single_segment(self, eleven_stops):
        """Exactly 11 stops → 1 segment (fits in one URL)."""
        segments = split_route_into_segments(eleven_stops)
        assert len(segments) == 1
        assert segments[0]["stop_count"] == 11

    def test_12_stops_two_segments(self):
        """12 stops → 2 segments (exceeds 11-stop limit)."""
        stops = [{"latitude": 9.97 + i * 0.001, "longitude": 76.28} for i in range(12)]
        segments = split_route_into_segments(stops)
        assert len(segments) == 2

    def test_fifteen_stops_multi_segment(self, fifteen_stops):
        """15 stops → multiple segments with overlap."""
        segments = split_route_into_segments(fifteen_stops)
        assert len(segments) >= 2
        for seg in segments:
            assert seg["stop_count"] <= 11

    def test_segments_overlap(self, fifteen_stops):
        """Adjacent segments should overlap at boundary stops.

        The destination of segment N is the origin of segment N+1.
        This gives the driver continuous navigation across segments.
        """
        segments = split_route_into_segments(fifteen_stops)
        assert len(segments) >= 2
        # End of segment 1 should be >= start of segment 2
        assert segments[0]["end_stop"] >= segments[1]["start_stop"]

    def test_each_segment_has_url_and_qr(self, fifteen_stops):
        """Every segment must have a Google Maps URL and QR SVG."""
        segments = split_route_into_segments(fifteen_stops)
        for seg in segments:
            assert "url" in seg
            assert "qr_svg" in seg
            assert seg["url"].startswith("https://www.google.com/maps/")
            assert "<svg" in seg["qr_svg"]

    def test_segments_numbered_sequentially(self, fifteen_stops):
        """Segment numbers should be 1, 2, 3, ..."""
        segments = split_route_into_segments(fifteen_stops)
        for i, seg in enumerate(segments):
            assert seg["segment"] == i + 1

    def test_large_route_30_stops(self):
        """30 stops should produce 3+ segments covering all stops."""
        stops = [{"latitude": 9.97 + i * 0.001, "longitude": 76.28} for i in range(30)]
        segments = split_route_into_segments(stops)
        assert len(segments) >= 3
        # All stops should be covered
        assert segments[-1]["end_stop"] == 30

    def test_single_stop_single_segment(self):
        """Edge case: single stop → 1 segment."""
        stops = [{"latitude": 9.97, "longitude": 76.28}]
        segments = split_route_into_segments(stops)
        assert len(segments) == 1
        assert segments[0]["stop_count"] == 1
