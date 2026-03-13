"""Structured error response model and error codes for the Kerala LPG API.

Replaces ad-hoc {"detail": "..."} HTTPException responses with a consistent
ErrorResponse Pydantic model. Every API error returns a JSON body with:
- error_code: namespaced code for frontend programmatic handling
- user_message: plain-English "Problem -- fix action" for office staff
- technical_message: developer-level detail for debugging
- request_id: 8-char UUID for support correlation
- timestamp: UTC ISO-8601 for log correlation
- help_url: link to relevant docs section

See: .planning/phases/02-error-handling-infrastructure/02-CONTEXT.md
"""

from datetime import datetime, timezone
from enum import StrEnum

from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ErrorCode(StrEnum):
    """Namespaced error codes grouped by subsystem.

    Each code maps to a specific failure mode. The frontend uses these
    to determine error presentation (banner vs inline table vs toast).
    The docs/ files provide remediation steps for each code.
    """

    # Upload
    UPLOAD_INVALID_FORMAT = "UPLOAD_INVALID_FORMAT"
    UPLOAD_FILE_TOO_LARGE = "UPLOAD_FILE_TOO_LARGE"
    UPLOAD_EMPTY_FILE = "UPLOAD_EMPTY_FILE"
    UPLOAD_NO_VALID_ORDERS = "UPLOAD_NO_VALID_ORDERS"
    UPLOAD_NO_ALLOCATED = "UPLOAD_NO_ALLOCATED"

    # Geocoding
    GEOCODING_FAILED = "GEOCODING_FAILED"
    GEOCODING_NOT_CONFIGURED = "GEOCODING_NOT_CONFIGURED"
    GEOCODING_QUOTA_EXCEEDED = "GEOCODING_QUOTA_EXCEEDED"

    # Optimizer
    OPTIMIZER_TIMEOUT = "OPTIMIZER_TIMEOUT"
    OPTIMIZER_UNAVAILABLE = "OPTIMIZER_UNAVAILABLE"
    OPTIMIZER_ERROR = "OPTIMIZER_ERROR"

    # Fleet
    FLEET_NO_VEHICLES = "FLEET_NO_VEHICLES"
    FLEET_VEHICLE_NOT_FOUND = "FLEET_VEHICLE_NOT_FOUND"
    FLEET_VEHICLE_EXISTS = "FLEET_VEHICLE_EXISTS"
    FLEET_NO_FIELDS = "FLEET_NO_FIELDS"

    # Drivers
    DRIVER_NOT_FOUND = "DRIVER_NOT_FOUND"
    DRIVER_NAME_EMPTY = "DRIVER_NAME_EMPTY"
    DRIVER_NAME_DUPLICATE = "DRIVER_NAME_DUPLICATE"

    # Route
    ROUTE_NOT_FOUND = "ROUTE_NOT_FOUND"
    ROUTE_NO_RUNS = "ROUTE_NO_RUNS"
    ROUTE_STOP_NOT_FOUND = "ROUTE_STOP_NOT_FOUND"

    # Auth
    AUTH_KEY_MISSING = "AUTH_KEY_MISSING"
    AUTH_KEY_INVALID = "AUTH_KEY_INVALID"

    # Service
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    SERVICE_DEGRADED = "SERVICE_DEGRADED"

    # General
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"


# Error code -> docs/ URL path mapping.
# Dashboard renders these as clickable help links in error details.
ERROR_HELP_URLS: dict[str, str] = {
    ErrorCode.UPLOAD_INVALID_FORMAT: "/docs/CSV_FORMAT.md#before-processing-file-level-errors",
    ErrorCode.UPLOAD_FILE_TOO_LARGE: "/docs/CSV_FORMAT.md#before-processing-file-level-errors",
    ErrorCode.UPLOAD_EMPTY_FILE: "/docs/CSV_FORMAT.md#before-processing-file-level-errors",
    ErrorCode.UPLOAD_NO_VALID_ORDERS: "/docs/CSV_FORMAT.md#during-processing-row-level-errors",
    ErrorCode.UPLOAD_NO_ALLOCATED: "/docs/CSV_FORMAT.md#cdcms-export-format",
    ErrorCode.GEOCODING_NOT_CONFIGURED: "/docs/GOOGLE-MAPS.md#setting-up-a-google-maps-api-key",
    ErrorCode.GEOCODING_QUOTA_EXCEEDED: "/docs/GOOGLE-MAPS.md#over_query_limit",
    ErrorCode.GEOCODING_FAILED: "/docs/GOOGLE-MAPS.md#common-errors",
    ErrorCode.OPTIMIZER_UNAVAILABLE: "/docs/SETUP.md#osrm-not-ready",
    ErrorCode.OPTIMIZER_TIMEOUT: "/docs/SETUP.md#osrm-not-ready",
    ErrorCode.OPTIMIZER_ERROR: "/docs/SETUP.md#osrm-not-ready",
    ErrorCode.FLEET_NO_VEHICLES: "/docs/SETUP.md#step-11-cdcms-data-workflow",
    ErrorCode.AUTH_KEY_INVALID: "/docs/SETUP.md#step-6-environment-variables",
    ErrorCode.AUTH_KEY_MISSING: "/docs/SETUP.md#step-6-environment-variables",
    ErrorCode.SERVICE_UNAVAILABLE: "/docs/SETUP.md#troubleshooting-1",
}


class ErrorResponse(BaseModel):
    """Structured error response for all API errors.

    Tiered by role:
    - user_message: plain-English "Problem -- fix action" for office staff
    - technical_message: developer-level detail for debugging
    - error_code: namespaced code for frontend error handling
    - request_id: short UUID for support correlation
    """

    success: bool = Field(default=False)
    error_code: str = Field(..., description="Namespaced error code (e.g., UPLOAD_INVALID_FORMAT)")
    user_message: str = Field(..., description="Plain-English error for office staff")
    technical_message: str = Field(default="", description="Developer-level detail")
    request_id: str = Field(default="", description="8-char request ID for support")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    help_url: str = Field(default="", description="Link to relevant docs section")


def error_response(
    status_code: int,
    error_code: str,
    user_message: str,
    technical_message: str = "",
    request_id: str = "",
) -> JSONResponse:
    """Create a structured error JSONResponse.

    Auto-populates help_url from ERROR_HELP_URLS when the error_code
    has a known mapping. Returns a JSONResponse (not a raise) -- callers
    must use ``return error_response(...)`` not ``raise``.

    Args:
        status_code: HTTP status code (400, 404, 500, etc.)
        error_code: ErrorCode enum value or string
        user_message: Human-readable "Problem -- fix action" message
        technical_message: Developer detail (logged, shown in "Show details")
        request_id: 8-char request ID from middleware
    """
    body = ErrorResponse(
        error_code=error_code,
        user_message=user_message,
        technical_message=technical_message,
        request_id=request_id,
        help_url=ERROR_HELP_URLS.get(error_code, ""),
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
    )
