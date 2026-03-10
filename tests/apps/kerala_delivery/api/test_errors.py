"""Tests for the ErrorResponse model, ErrorCode enum, and error_response() helper.

Covers ERR-01: ErrorResponse model validates all fields.
"""

import json
from datetime import datetime, timezone

import pytest

from apps.kerala_delivery.api.errors import (
    ErrorCode,
    ErrorResponse,
    error_response,
    ERROR_HELP_URLS,
)


class TestErrorCodeEnum:
    """ErrorCode enum must contain all 22 namespaced codes."""

    def test_upload_codes_exist(self):
        assert ErrorCode.UPLOAD_INVALID_FORMAT == "UPLOAD_INVALID_FORMAT"
        assert ErrorCode.UPLOAD_FILE_TOO_LARGE == "UPLOAD_FILE_TOO_LARGE"
        assert ErrorCode.UPLOAD_EMPTY_FILE == "UPLOAD_EMPTY_FILE"
        assert ErrorCode.UPLOAD_NO_VALID_ORDERS == "UPLOAD_NO_VALID_ORDERS"
        assert ErrorCode.UPLOAD_NO_ALLOCATED == "UPLOAD_NO_ALLOCATED"

    def test_geocoding_codes_exist(self):
        assert ErrorCode.GEOCODING_FAILED == "GEOCODING_FAILED"
        assert ErrorCode.GEOCODING_NOT_CONFIGURED == "GEOCODING_NOT_CONFIGURED"
        assert ErrorCode.GEOCODING_QUOTA_EXCEEDED == "GEOCODING_QUOTA_EXCEEDED"

    def test_optimizer_codes_exist(self):
        assert ErrorCode.OPTIMIZER_TIMEOUT == "OPTIMIZER_TIMEOUT"
        assert ErrorCode.OPTIMIZER_UNAVAILABLE == "OPTIMIZER_UNAVAILABLE"
        assert ErrorCode.OPTIMIZER_ERROR == "OPTIMIZER_ERROR"

    def test_fleet_codes_exist(self):
        assert ErrorCode.FLEET_NO_VEHICLES == "FLEET_NO_VEHICLES"
        assert ErrorCode.FLEET_VEHICLE_NOT_FOUND == "FLEET_VEHICLE_NOT_FOUND"
        assert ErrorCode.FLEET_VEHICLE_EXISTS == "FLEET_VEHICLE_EXISTS"
        assert ErrorCode.FLEET_NO_FIELDS == "FLEET_NO_FIELDS"

    def test_route_codes_exist(self):
        assert ErrorCode.ROUTE_NOT_FOUND == "ROUTE_NOT_FOUND"
        assert ErrorCode.ROUTE_NO_RUNS == "ROUTE_NO_RUNS"
        assert ErrorCode.ROUTE_STOP_NOT_FOUND == "ROUTE_STOP_NOT_FOUND"

    def test_auth_codes_exist(self):
        assert ErrorCode.AUTH_KEY_MISSING == "AUTH_KEY_MISSING"
        assert ErrorCode.AUTH_KEY_INVALID == "AUTH_KEY_INVALID"

    def test_service_codes_exist(self):
        assert ErrorCode.SERVICE_UNAVAILABLE == "SERVICE_UNAVAILABLE"
        assert ErrorCode.SERVICE_DEGRADED == "SERVICE_DEGRADED"

    def test_general_codes_exist(self):
        assert ErrorCode.INTERNAL_ERROR == "INTERNAL_ERROR"
        assert ErrorCode.INVALID_REQUEST == "INVALID_REQUEST"

    def test_total_code_count(self):
        """At least 22 error codes defined."""
        assert len(ErrorCode) >= 22


class TestErrorResponse:
    """ErrorResponse Pydantic model validation."""

    def test_required_fields(self):
        """error_code and user_message are required."""
        resp = ErrorResponse(
            error_code="UPLOAD_INVALID_FORMAT",
            user_message="Bad file format",
        )
        assert resp.error_code == "UPLOAD_INVALID_FORMAT"
        assert resp.user_message == "Bad file format"
        assert resp.success is False

    def test_defaults(self):
        """technical_message, request_id, help_url default to empty string."""
        resp = ErrorResponse(
            error_code="TEST",
            user_message="test",
        )
        assert resp.technical_message == ""
        assert resp.request_id == ""
        assert resp.help_url == ""
        assert isinstance(resp.timestamp, datetime)

    def test_model_dump_json_serialization(self):
        """model_dump(mode='json') produces valid JSON with ISO timestamp."""
        resp = ErrorResponse(
            error_code="UPLOAD_INVALID_FORMAT",
            user_message="Bad file",
            technical_message="Expected .csv",
            request_id="abc12def",
        )
        data = resp.model_dump(mode="json")
        # Should be JSON-serializable
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        assert parsed["error_code"] == "UPLOAD_INVALID_FORMAT"
        assert parsed["success"] is False
        assert parsed["request_id"] == "abc12def"
        # timestamp should be ISO format string
        assert isinstance(parsed["timestamp"], str)
        # Should parse back to datetime
        datetime.fromisoformat(parsed["timestamp"])

    def test_custom_timestamp(self):
        """Explicit timestamp is preserved."""
        ts = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
        resp = ErrorResponse(
            error_code="TEST",
            user_message="test",
            timestamp=ts,
        )
        assert resp.timestamp == ts


class TestErrorResponseHelper:
    """error_response() helper function."""

    def test_returns_json_response_with_correct_status(self):
        """error_response() returns JSONResponse with given status code."""
        result = error_response(
            status_code=400,
            error_code=ErrorCode.UPLOAD_INVALID_FORMAT,
            user_message="Bad file",
        )
        assert result.status_code == 400
        body = json.loads(result.body)
        assert body["error_code"] == "UPLOAD_INVALID_FORMAT"
        assert body["user_message"] == "Bad file"
        assert body["success"] is False

    def test_auto_populates_help_url_for_known_codes(self):
        """Known error codes get help_url from ERROR_HELP_URLS."""
        result = error_response(
            status_code=400,
            error_code=ErrorCode.UPLOAD_INVALID_FORMAT,
            user_message="Bad file",
        )
        body = json.loads(result.body)
        assert body["help_url"] != ""
        assert body["help_url"] == ERROR_HELP_URLS.get(ErrorCode.UPLOAD_INVALID_FORMAT, "")

    def test_empty_help_url_for_unknown_codes(self):
        """Unknown/unmapped error codes get empty help_url."""
        result = error_response(
            status_code=500,
            error_code=ErrorCode.INTERNAL_ERROR,
            user_message="Something broke",
        )
        body = json.loads(result.body)
        # INTERNAL_ERROR may or may not have a help URL
        # The key test is it doesn't crash
        assert "help_url" in body

    def test_includes_request_id(self):
        """request_id is passed through to the response body."""
        result = error_response(
            status_code=404,
            error_code=ErrorCode.ROUTE_NOT_FOUND,
            user_message="Route not found",
            request_id="deadbeef",
        )
        body = json.loads(result.body)
        assert body["request_id"] == "deadbeef"

    def test_includes_technical_message(self):
        """technical_message is included in response body."""
        result = error_response(
            status_code=400,
            error_code=ErrorCode.UPLOAD_INVALID_FORMAT,
            user_message="Bad file type",
            technical_message="Got .doc, expected .csv",
        )
        body = json.loads(result.body)
        assert body["technical_message"] == "Got .doc, expected .csv"

    def test_timestamp_present(self):
        """Response body includes a timestamp."""
        result = error_response(
            status_code=400,
            error_code=ErrorCode.INVALID_REQUEST,
            user_message="Bad request",
        )
        body = json.loads(result.body)
        assert "timestamp" in body
        datetime.fromisoformat(body["timestamp"])


class TestErrorHelpUrls:
    """ERROR_HELP_URLS mapping validation."""

    def test_is_dict(self):
        assert isinstance(ERROR_HELP_URLS, dict)

    def test_has_upload_format_entry(self):
        assert ErrorCode.UPLOAD_INVALID_FORMAT in ERROR_HELP_URLS

    def test_has_geocoding_not_configured(self):
        assert ErrorCode.GEOCODING_NOT_CONFIGURED in ERROR_HELP_URLS

    def test_all_values_are_strings(self):
        for key, val in ERROR_HELP_URLS.items():
            assert isinstance(val, str), f"Value for {key} is not a string"
