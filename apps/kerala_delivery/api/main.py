"""FastAPI application for the Kerala LPG delivery route optimizer.

This is the main API that:
1. Accepts a CSV/Excel upload of today's CDCMS delivery orders
2. Geocodes any addresses without GPS coordinates
3. Runs the VROOM optimizer to assign orders to drivers
4. Returns optimized routes for each driver
5. Persists everything to PostgreSQL + PostGIS (Phase 2)
6. Accepts GPS telemetry from driver devices (Phase 2)

The driver app (PWA) calls this API to get today's route.
"""

import hmac  # For timing-safe API key comparison (prevents timing attacks)
import json
import html as html_module  # For escaping user data in server-rendered HTML (XSS prevention)
from urllib.parse import quote_plus  # For URL-encoding driver names in QR codes
import logging
import os
import pathlib
import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, time as dt_time, timedelta, timezone

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
import pandas as pd
from pydantic import BaseModel, Field
import httpx
from Secweb import SecWeb
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from core.database.models import VehicleDB

from apps.kerala_delivery import config
from apps.kerala_delivery.api.qr_helpers import (
    build_google_maps_url,
    generate_qr_base64_png,
    generate_qr_svg,
    split_route_into_segments,
    GOOGLE_MAPS_MAX_WAYPOINTS,
)
from core.data_import.csv_importer import CsvImporter, ColumnMapping, ImportResult, RowError
from core.data_import.cdcms_preprocessor import preprocess_cdcms, get_cdcms_column_mapping, CDCMS_COL_ORDER_NO, CDCMS_COL_ADDRESS
from core.database.connection import engine, get_session
from core.database import repository as repo
from core.geocoding.cache import CachedGeocoder
from core.geocoding.duplicate_detector import detect_duplicate_locations
from core.geocoding.google_adapter import GoogleGeocoder
from core.licensing.license_manager import validate_license, LicenseStatus, LicenseInfo, GRACE_PERIOD_DAYS
from core.models.location import Location
from core.models.order import Order
from core.optimizer.tsp_orchestrator import (
    group_orders_by_driver,
    optimize_per_driver,
    validate_no_overlap,
    detect_geographic_anomalies,
)
from core.optimizer.vroom_adapter import VroomAdapter
from geoalchemy2.shape import to_shape

from apps.kerala_delivery.api.errors import ErrorCode, ErrorResponse, error_response, ERROR_HELP_URLS
from apps.kerala_delivery.api.health import wait_for_services, check_postgresql, check_osrm, check_vroom, check_google_api
from apps.kerala_delivery.api.middleware import RequestIDMiddleware, RequestIDFilter, request_id_var, LOG_FORMAT
from apps.kerala_delivery.api.retry import geocoding_retry, optimizer_retry

logger = logging.getLogger(__name__)

# Configure logging with request ID filter so every log line includes [request_id].
# This enables grep-based log correlation for support: "grep abc12def api.log"
logging.basicConfig(format=LOG_FORMAT, level=logging.INFO, force=True)
logging.getLogger().addFilter(RequestIDFilter())


def _point_lat(geom: object) -> float | None:
    """Extract latitude from a PostGIS Point geometry, or None."""
    if geom is None:
        return None
    return float(to_shape(geom).y)


def _point_lng(geom: object) -> float | None:
    """Extract longitude from a PostGIS Point geometry, or None."""
    if geom is None:
        return None
    return float(to_shape(geom).x)


# Google Geocoding API status codes → user-friendly failure reasons.
# Office staff see these messages, so they must be actionable and jargon-free.
# The raw status is still logged server-side for debugging.
GEOCODING_REASON_MAP: dict[str, str] = {
    "ZERO_RESULTS": "Address not found -- check spelling in CDCMS",
    "REQUEST_DENIED": "Geocoding service blocked -- contact IT",
    "OVER_QUERY_LIMIT": "Google Maps quota exceeded -- contact IT",
    "OVER_DAILY_LIMIT": "Google Maps quota exceeded -- contact IT",
    "INVALID_REQUEST": "Address could not be processed -- check for unusual characters",
    "UNKNOWN_ERROR": "Google Maps is temporarily unavailable -- try again in a few minutes",
}


# =============================================================================
# Custom Middleware: Permissions-Policy
# =============================================================================


class PermissionsPolicyMiddleware(BaseHTTPMiddleware):
    """Add Permissions-Policy header to all responses.

    Allows geolocation (driver PWA GPS) and denies all other features.
    SecWeb stable (1.30.x) does not include Permissions-Policy support,
    so we implement it as a lightweight custom middleware.
    """

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Permissions-Policy"] = (
            "geolocation=(self), "
            "camera=(), "
            "microphone=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "accelerometer=()"
        )
        return response


# =============================================================================
# App setup with lifespan (manages DB engine lifecycle)
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: start up and shut down the async DB engine.

    Why lifespan instead of on_event("startup")?
    FastAPI recommends lifespan context managers (added in 0.95):
    - Cleaner resource management (engine disposal on shutdown)
    - Works with the ASGI lifecycle protocol
    - on_event is deprecated in newer FastAPI versions.
    See: https://fastapi.tiangolo.com/advanced/events/#lifespan
    """
    # SECURITY: warn if API_KEY is unset outside dev mode.
    # Missing API_KEY in production means all POST endpoints are unprotected.
    env = os.environ.get("ENVIRONMENT", "development")
    api_key = os.environ.get("API_KEY", "")
    if not api_key and env != "development":
        logger.warning(
            "⚠️  API_KEY is not set and ENVIRONMENT=%s. "
            "All protected endpoints (POST + sensitive GET) are UNPROTECTED. "
            "Set API_KEY in production.",
            env,
        )
    elif api_key:
        logger.info("API key authentication enabled for POST and sensitive GET endpoints")

    # ── License validation ────────────────────────────────────────────
    # Check hardware-bound license on startup. In production, an invalid
    # license blocks all API endpoints with 503. In development, licensing
    # is optional (no key = no enforcement).
    # See: core/licensing/license_manager.py for the full validation logic.
    license_info = validate_license()
    app.state.license_info = license_info  # Store for middleware access

    if license_info.status == LicenseStatus.VALID:
        logger.info(
            "License valid — customer=%s, expires=%s, %d days remaining",
            license_info.customer_id,
            license_info.expires_at.strftime("%Y-%m-%d"),
            license_info.days_remaining,
        )
    elif license_info.status == LicenseStatus.GRACE:
        logger.warning(
            "⚠️  LICENSE IN GRACE PERIOD — %s. "
            "System will stop working in %d days. Renew immediately.",
            license_info.message,
            GRACE_PERIOD_DAYS - abs(license_info.days_remaining),
        )
    else:
        # INVALID — but only enforce in production. In dev, just warn.
        if env == "production":
            logger.error(
                "❌ LICENSE INVALID: %s. All endpoints will return 503.",
                license_info.message,
            )
        else:
            logger.info(
                "License not configured (dev mode) — running without license enforcement"
            )
            # In dev mode, override to VALID so the middleware doesn't block
            license_info = LicenseInfo(
                customer_id="dev-mode",
                fingerprint="",
                expires_at=license_info.expires_at,
                status=LicenseStatus.VALID,
                days_remaining=999,
                message="Development mode — no license required",
            )
            app.state.license_info = license_info

    # ── Startup health gates (NON-NEGOTIABLE) ────────────────────────
    # Block until PostgreSQL, OSRM, VROOM are healthy (60s timeout).
    # Sequence: PostgreSQL first, then OSRM, then VROOM.
    # If timeout, start anyway but store degraded status for /health endpoint.
    osrm_url = os.environ.get("OSRM_URL", "http://osrm:5000")
    vroom_url = os.environ.get("VROOM_URL", "http://vroom:3000")

    logger.info("Checking service health (60s timeout)...")
    service_health = await wait_for_services(engine, osrm_url, vroom_url, timeout=60.0)
    app.state.service_health = service_health
    app.state.started_at = datetime.now(timezone.utc)

    unhealthy = [name for name, (healthy, _) in service_health.items() if not healthy]
    if unhealthy:
        logger.warning(
            "Starting with unhealthy services: %s — API will return 503 for affected operations",
            unhealthy,
        )
    else:
        logger.info("All services healthy")

    logger.info("Starting up — DB engine pool initialized")
    yield
    # Shutdown: dispose DB connection pool
    await engine.dispose()
    logger.info("Shutdown — DB engine pool disposed")


# SECURITY: Disable Swagger UI and OpenAPI schema in production.
# FastAPI's /docs endpoint exposes every endpoint, parameter schema, and error
# format to unauthenticated users — giving attackers a complete API map.
# In development, /docs is invaluable for testing. In production, disable it.
# Access API docs in production by SSHing to the server and running:
#   curl http://localhost:8000/docs  (internal-only, not exposed through Caddy)
_env_name = os.environ.get("ENVIRONMENT", "development")
_docs_url = "/docs" if _env_name != "production" else None
_redoc_url = "/redoc" if _env_name != "production" else None
_openapi_url = "/openapi.json" if _env_name != "production" else None

app = FastAPI(
    title="Kerala LPG Delivery Route Optimizer",
    description=(
        "Upload today's delivery list from CDCMS → get optimized routes "
        "for each driver. Minimizes total distance while respecting vehicle "
        "capacity and delivery priorities."
    ),
    version="0.2.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

# =============================================================================
# Rate limiting — prevent abuse of expensive endpoints
# =============================================================================
# Why rate limiting?
# - Upload/optimize is CPU-intensive (VROOM solve) and triggers Google API calls
# - Telemetry POST is called frequently from all driver devices
# - Without limits, a misconfigured client or attacker can exhaust resources
#
# Why slowapi?
# - Built on top of the proven `limits` library
# - Integrates cleanly with FastAPI as a Starlette extension
# - In-memory storage is fine for single-instance Phase 2; switch to Redis
#   for multi-instance in Phase 3+
# See: https://github.com/laurentS/slowapi
#
# Rate limits are based on client IP. Override with X-Forwarded-For
# header if behind a reverse proxy (configure in production).
limiter = Limiter(
    key_func=get_remote_address,
    # Default limit: 60 requests/minute for all endpoints.
    # Individual endpoints override this with @limiter.limit() decorator.
    default_limits=["60/minute"],
    # RATE_LIMIT_ENABLED env var allows disabling in tests/CI
    enabled=os.environ.get("RATE_LIMIT_ENABLED", "true").lower() != "false",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# =============================================================================
# Security headers — SecWeb + Permissions-Policy
# =============================================================================
# Middleware ordering is CRITICAL. FastAPI/Starlette wraps in reverse
# registration order (last registered = outermost = processes first).
# Registration order in code:
#   1. SecWeb (outermost — every response gets security headers)
#   2. PermissionsPolicyMiddleware (adds Permissions-Policy header)
#   3. CORSMiddleware (handles cross-origin requests)
#   4. License enforcement (@app.middleware("http"), below)
#   5. Rate limiter (app.state.limiter, above)

_secweb_options = {
    "csp": {
        "default-src": ["'self'"],
        "script-src": ["'self'", "'unsafe-inline'", "https://unpkg.com"],
        "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com", "https://unpkg.com"],
        "img-src": [
            "'self'",
            "data:",
            "blob:",
            "https://*.tile.openstreetmap.org",
            "https://unpkg.com",
            "https://*.basemaps.cartocdn.com",
        ],
        "connect-src": [
            "'self'",
            "https://basemaps.cartocdn.com",
            "https://*.basemaps.cartocdn.com",
        ],
        "worker-src": ["'self'", "blob:"],
        "font-src": ["'self'", "https://fonts.gstatic.com"],
        "frame-ancestors": ["'none'"],
    },
    "xframe": "DENY",
    "referrer": ["strict-origin-when-cross-origin"],
    # xcto (X-Content-Type-Options: nosniff) is enabled by default in SecWeb
}

# HSTS: only in non-development environments to prevent localhost HTTPS lock-in.
# Caddy already handles HSTS at the proxy level in production, but defense-in-depth
# at the app layer ensures coverage even if the proxy is misconfigured.
if _env_name != "development":
    _secweb_options["hsts"] = {
        "max-age": 31536000,
        "includeSubDomains": True,
        "preload": True,
    }

SecWeb(app=app, Option=_secweb_options)
app.add_middleware(PermissionsPolicyMiddleware)

# CORS: restrict origins to known frontends.
# SECURITY: never use allow_origins=["*"] in production — it lets any website
# make authenticated requests to this API. Use a whitelist from environment.
# See: https://owasp.org/www-community/attacks/csrf
_cors_origins_raw = os.environ.get("CORS_ALLOWED_ORIGINS", "")
if _env_name == "development" and not _cors_origins_raw:
    # Dev default: allow common local origins
    _allowed_origins = [
        "http://localhost:8000",
        "http://localhost:3000",
        "http://localhost:5173",
    ]
else:
    # Production/staging: explicit whitelist only (empty = no cross-origin allowed)
    _allowed_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    # PUT and DELETE needed for fleet management CRUD endpoints.
    # Phase 2 added vehicle CRUD — browser preflight checks these.
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    # Tighten from ["*"] to explicit list matching actual API headers
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
    expose_headers=["X-License-Warning", "Retry-After", "X-Request-ID"],
)

# RequestIDMiddleware MUST be registered LAST because Starlette processes
# middleware in reverse registration order (last added = outermost = runs first).
# This ensures every request gets a request_id BEFORE any other middleware
# processes it, so even auth/license error responses include request_id.
app.add_middleware(RequestIDMiddleware)


# =============================================================================
# License enforcement middleware
# =============================================================================
# Checks app.state.license_info (set during lifespan) on every request.
# - VALID: pass through normally
# - GRACE: pass through but add X-License-Warning header
# - INVALID: return 503 on all endpoints except /health (for diagnostics)


@app.middleware("http")
async def license_enforcement_middleware(request: Request, call_next):
    """Block all requests if license is invalid (production only).

    Why middleware instead of a dependency?
    - Dependencies only run on endpoints that declare them. A middleware
      catches ALL requests, including static files and undeclared routes.
    - We want the /health endpoint to still work (for debugging), so we
      exclude it explicitly.

    Why 503 (Service Unavailable) instead of 403 (Forbidden)?
    - 503 signals "the server can't handle the request right now" which
      is semantically correct for a licensing issue.
    - It also tells monitoring tools that the service is down, triggering
      alerts that help the customer notice and renew.
    """
    license_info = getattr(request.app.state, "license_info", None)

    if license_info is None:
        # No license info = not yet initialized, pass through
        return await call_next(request)

    # Always allow health checks (for debugging license issues)
    if request.url.path == "/health":
        response = await call_next(request)
        # Add license status to health response header for diagnostics
        if license_info.status != LicenseStatus.VALID:
            response.headers["X-License-Status"] = license_info.status.value
        return response

    if license_info.status == LicenseStatus.INVALID:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "License expired or invalid. Contact support.",
                "license_status": "invalid",
            },
        )

    # Process the request normally
    response = await call_next(request)

    # Add warning header during grace period
    if license_info.status == LicenseStatus.GRACE:
        response.headers["X-License-Warning"] = license_info.message

    return response


# =============================================================================
# Global HTTPException handler — wraps old-style exceptions in ErrorResponse
# =============================================================================
# Catches any remaining `raise HTTPException(...)` that haven't been migrated
# to `return error_response(...)`. Ensures ALL error responses conform to
# the ErrorResponse JSON shape, even during migration period.


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Wrap all HTTPExceptions in ErrorResponse format for consistency."""
    req_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_code="INTERNAL_ERROR" if exc.status_code >= 500 else "INVALID_REQUEST",
            user_message=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            request_id=req_id,
        ).model_dump(mode="json"),
    )


# Serve the driver PWA as static files at /driver/
# Drivers open http://<server>:8000/driver/ on their phone
_driver_app_dir = pathlib.Path(__file__).parent.parent / "driver_app"

# Service worker MUST be served with Cache-Control: no-cache so the browser
# always fetches the latest sw.js and can detect CACHE_VERSION bumps.
# If sw.js is HTTP-cached, the browser won't notice the version change and
# will keep serving the old app shell indefinitely.
# This route intercepts /driver/sw.js before the StaticFiles mount handles it.

@app.get("/driver/sw.js", include_in_schema=False)
async def serve_sw_js():
    """Serve service worker with no-cache headers so version bumps take effect immediately."""
    sw_path = _driver_app_dir / "sw.js"
    if not sw_path.exists():
        raise HTTPException(status_code=404, detail="sw.js not found")
    return Response(
        content=sw_path.read_bytes(),
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        },
    )

if _driver_app_dir.exists():
    app.mount("/driver", StaticFiles(directory=str(_driver_app_dir), html=True), name="driver_app")

# Serve the ops dashboard as static files at /dashboard/
# In dev mode, the dashboard-build container populates /srv/dashboard via a shared volume.
# In production, Caddy serves the dashboard at / instead (see Caddyfile).
# html=True enables SPA fallback: any path under /dashboard/ that doesn't match a
# real file serves index.html, letting the React app handle client-side navigation.
_dashboard_dir = pathlib.Path("/srv/dashboard")
if _dashboard_dir.exists() and any(_dashboard_dir.iterdir()):
    app.mount("/dashboard", StaticFiles(directory=str(_dashboard_dir), html=True), name="dashboard")

# =============================================================================
# Authentication — API key on mutating endpoints
# =============================================================================
# Why API key (not JWT)?
# This is an internal operations tool with a small user base (dispatchers +
# driver app). API key auth is simpler to implement and debug. JWT is better
# for multi-tenant SaaS — we'll migrate if/when needed in Phase 3+.
# SECURITY: auto_error=False so we get None (not 403) when the header is
# missing — our verify_api_key function handles the error with a clear message.
_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

# Maximum upload file size (bytes). 10 MB is generous for CSV/Excel files
# containing 40-50 delivery orders per day. Prevents accidental or malicious
# large uploads from consuming server memory.
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

# Allowed file extensions for upload. Matches the two formats the importer
# supports: CsvImporter for .csv and openpyxl for .xlsx/.xls.
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

# Content-types that correspond to CSV and Excel files.
# application/octet-stream is included because some browsers send it for .csv.
ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/octet-stream",
}

# Maximum number of order rows in a single upload.
# Fleet is 13 vehicles with typical batches of 50-100 orders.
# 1000 is generous — prevents processing absurdly large batches.
MAX_ROW_COUNT = 1000


def _check_api_key(api_key: str | None) -> None:
    """Shared API key verification logic.

    Why a helper instead of duplicating in each dependency?
    Both verify_api_key and verify_read_key use the same key and logic.
    Extracting the check means a future security fix only needs one change.

    Why hmac.compare_digest instead of ==?
    String equality (==) short-circuits on the first mismatched character,
    leaking timing information about how much of the key matched. An attacker
    could measure response times to guess the key character-by-character.
    hmac.compare_digest runs in constant time regardless of where the mismatch
    occurs, preventing this class of timing side-channel attacks.
    See: https://docs.python.org/3/library/hmac.html#hmac.compare_digest

    Raises HTTPException(401) if API_KEY is set and the provided key
    doesn't match. No-ops in dev mode (API_KEY unset).
    """
    expected_key = os.environ.get("API_KEY", "")
    if not expected_key:
        return  # Dev mode — no auth required
    if not api_key or not hmac.compare_digest(api_key, expected_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key -- include X-API-Key header",
        )


async def verify_api_key(
    api_key: str | None = Depends(_api_key_scheme),
) -> None:
    """Verify the X-API-Key header on mutating (POST/PUT/DELETE) endpoints.

    Security model:
    - If API_KEY env var is empty/unset: all requests allowed (dev mode).
      This lets developers run locally without configuring a key.
    - If API_KEY is set: every mutating request must include a matching
      X-API-Key header or receive 401 Unauthorized.

    Usage: add ``dependencies=[Depends(verify_api_key)]`` to @app.post().
    """
    _check_api_key(api_key)


async def verify_read_key(
    api_key: str | None = Depends(_api_key_scheme),
) -> None:
    """Verify the X-API-Key header on sensitive GET endpoints.

    Why protect some GET endpoints?
    Fleet telemetry exposes real-time GPS locations of all drivers —
    this is personally sensitive data (driver tracking). Vehicle details
    include registration numbers and depot locations. Unlike route
    summaries or optimization run history, this data has privacy
    implications if exposed publicly.

    Uses the SAME API key as verify_api_key — no separate "read key".
    This keeps the auth model simple (one key to manage) while closing
    the gap where fleet-wide location data was publicly accessible.

    Protected endpoints:
    - GET /api/telemetry/fleet  (all driver locations)
    - GET /api/telemetry/{vehicle_id}  (driver GPS history)
    - GET /api/vehicles  (fleet details, registration numbers)
    - GET /api/vehicles/{vehicle_id}  (individual vehicle details)

    Usage: add ``dependencies=[Depends(verify_read_key)]`` to @app.get().
    """
    _check_api_key(api_key)


# =============================================================================
# Geocoder singleton — reuse across requests to avoid repeated init
# =============================================================================
# GoogleGeocoder is a pure API caller -- caching is handled by CachedGeocoder.
_geocoder_instance: GoogleGeocoder | None = None


def _get_geocoder() -> GoogleGeocoder | None:
    """Get or create the shared GoogleGeocoder instance.

    Returns None if GOOGLE_MAPS_API_KEY is not set (geocoding disabled).
    GoogleGeocoder is a pure API caller -- caching is handled by CachedGeocoder.
    """
    global _geocoder_instance
    if _geocoder_instance is not None:
        return _geocoder_instance
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    # Reject placeholder values that aren't real API keys.
    # Real Google API keys start with "AIza" and are 39 characters.
    placeholder_values = {"your-key-here", "your-api-key", "change-me", ""}
    if api_key.lower() in placeholder_values:
        if api_key:
            logger.warning(
                "GOOGLE_MAPS_API_KEY appears to be a placeholder ('%s') — geocoding disabled. "
                "Set a real API key in .env to enable geocoding.",
                api_key,
            )
        return None
    _geocoder_instance = GoogleGeocoder(api_key=api_key)
    return _geocoder_instance


def _is_cdcms_format(file_path: str) -> bool:
    """Detect whether a file is a raw CDCMS export (tab-separated CSV or Excel).

    For CSV files: checks the first line for CDCMS-specific column names
    (OrderNo, ConsumerAddress) separated by tabs.

    For Excel files (.xlsx/.xls): reads headers via pandas and checks
    for CDCMS marker columns. This fixes the previous bug where .xlsx
    files (ZIP-based binary) were opened as UTF-8 text and failed silently.

    This lets the upload endpoint auto-detect the format and run the
    preprocessor when needed, so employees can upload CDCMS exports
    directly without manual conversion.
    """
    ext = pathlib.Path(file_path).suffix.lower()

    # For Excel files: read headers via pandas and check column names
    if ext in (".xlsx", ".xls"):
        try:
            df = pd.read_excel(file_path, nrows=0, dtype=str)
            columns = set(df.columns)
            cdcms_markers = {CDCMS_COL_ORDER_NO, CDCMS_COL_ADDRESS}
            return cdcms_markers.issubset(columns)
        except Exception:
            return False

    # For CSV/text files: existing logic (check for tabs + column names)
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            header_line = f.readline().strip()
        # CDCMS exports are tab-separated with specific column names
        if "\t" not in header_line:
            return False
        columns = [col.strip() for col in header_line.split("\t")]
        # Check for at least two CDCMS-specific columns
        cdcms_markers = {CDCMS_COL_ORDER_NO, CDCMS_COL_ADDRESS}
        return cdcms_markers.issubset(set(columns))
    except (OSError, UnicodeDecodeError):
        return False


# =============================================================================
# Database session dependency
# =============================================================================
# Why a global dependency instead of importing get_session in each endpoint?
# FastAPI's Depends() provides automatic lifecycle management: the session
# is created per-request, yielded to the endpoint, and cleaned up after.
# This is the standard pattern for SQLAlchemy async sessions.
SessionDep = Depends(get_session)


# =============================================================================
# Request/Response models
# =============================================================================
class ImportFailure(BaseModel):
    """A single import failure (validation or geocoding stage).

    Surfaced to office staff so they can fix CSV issues. Row numbers
    match the original spreadsheet (1-based, header = row 1). Address
    snippets help identify which order failed without exposing full
    customer data.
    """

    row_number: int = Field(..., description="1-based row in original CSV")
    address_snippet: str = Field(default="", description="First 80 chars of address")
    reason: str = Field(..., description="Human-readable failure reason for office staff")
    stage: Literal["validation", "geocoding", "optimization"] = Field(..., description="When the failure occurred")


class DuplicateLocationWarning(BaseModel):
    """A cluster of orders with suspiciously close GPS coordinates.

    Non-blocking: optimization proceeds normally, these warnings are shown
    alongside results so office staff can investigate data entry errors.
    """

    order_ids: list[str] = Field(..., description="Order IDs in this cluster")
    addresses: list[str] = Field(..., description="Address text for each order")
    max_distance_m: float = Field(..., description="Largest distance between orders in cluster (meters)")


class OptimizationSummary(BaseModel):
    """Summary of the latest optimization run.

    Includes import diagnostics (failures, warnings, summary counts) so the
    dashboard can display per-row feedback without a separate API call.
    All new fields have defaults for backward compatibility — existing clients
    that don't read the new fields continue to work unchanged.

    Partial success contract (LOCKED DECISION from CONTEXT.md):
    - success: true for successful/partial-success uploads
    - imported: count of successfully imported orders
    - total: total rows in CSV
    - warnings[]: per-row warning details
    """

    # Partial success contract fields
    success: bool = Field(default=True, description="True for successful/partial-success uploads")
    imported: int = Field(default=0, description="Number of successfully imported orders (geocoded count)")
    total: int = Field(default=0, description="Total rows in uploaded CSV (alias for total_rows)")

    # Existing fields (unchanged)
    run_id: str = Field(..., description="UUID of this optimization run (use for subsequent queries)")
    assignment_id: str
    total_orders: int
    orders_assigned: int
    orders_unassigned: int
    vehicles_used: int
    optimization_time_ms: float
    created_at: datetime

    # Import diagnostics (all default to zero/empty for backward compatibility)
    total_rows: int = Field(default=0, description="Total rows in uploaded CSV")
    geocoded: int = Field(default=0, description="Orders successfully geocoded")
    failed_geocoding: int = Field(default=0, description="Orders that failed geocoding")
    failed_validation: int = Field(default=0, description="Rows rejected during pre-validation")
    failures: list[ImportFailure] = Field(default_factory=list, description="Per-row failure details")
    warnings: list[ImportFailure] = Field(default_factory=list, description="Per-row warnings (defaults applied)")

    # GEO-04: Cost transparency
    cache_hits: int = Field(default=0, description="Addresses resolved from cache (free)")
    api_calls: int = Field(default=0, description="Addresses that required Google API call")
    estimated_cost_usd: float = Field(default=0.0, description="Estimated API cost at $0.005/request")
    free_tier_note: str = Field(default="", description="Human-readable free tier context")
    per_order_geocode_source: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of order_id to 'cached' or 'api_call'",
    )

    # GEO-03: Duplicate location warnings
    duplicate_warnings: list[DuplicateLocationWarning] = Field(
        default_factory=list,
        description="Groups of orders with suspiciously close GPS coordinates",
    )

    # Phase 16: Driver auto-creation summary from CSV DeliveryMan column
    drivers: dict | None = Field(
        default=None,
        description="Driver auto-creation summary from CSV upload. "
        "Shape: {new_drivers: [str], matched_drivers: [{csv_name, matched_to, score}], "
        "reactivated_drivers: [str], existing_drivers: [str]}. "
        "None for non-CDCMS uploads.",
    )


# =============================================================================
# Phase 17: Parse-upload models and upload token store
# =============================================================================


class DriverPreview(BaseModel):
    """One driver found in a parsed CDCMS upload file.

    Returned as part of ParsePreviewResponse to show which drivers
    are in the file, how many orders each has, and whether they're
    new or already exist in the database.
    """

    csv_name: str = Field(description="Original name from the CSV/CDCMS DeliveryMan column")
    display_name: str = Field(description="Title-cased display name for UI")
    order_count: int = Field(description="Number of Allocated-Printed orders for this driver")
    status: Literal["existing", "new", "matched", "reactivated"] = Field(
        description="Driver status: existing (exact match), new (no match), "
        "matched (fuzzy match to active driver), reactivated (inactive driver reactivated)"
    )
    matched_to: str | None = Field(default=None, description="DB driver name if matched/reactivated")
    match_score: float | None = Field(default=None, description="Fuzzy match score (0-100)")


class ParsePreviewResponse(BaseModel):
    """Response from POST /api/parse-upload.

    Contains a driver preview list and an upload_token that references
    the parsed file on disk. The client sends this token to the process
    endpoint to avoid re-uploading the file.
    """

    upload_token: str = Field(description="UUID referencing the temp file on disk (30-min TTL)")
    filename: str = Field(description="Original uploaded filename")
    total_rows: int = Field(description="Total rows in the uploaded file (before filtering)")
    filtered_rows: int = Field(description="Rows after Allocated-Printed filter")
    drivers: list[DriverPreview] = Field(description="Per-driver preview data")


# In-memory upload token store. Tokens map to temp file paths and metadata.
# Tokens expire after 30 minutes. Cleanup runs on every new parse request.
_upload_tokens: dict[str, dict] = {}
_TOKEN_TTL = timedelta(minutes=30)


def _cleanup_expired_tokens() -> None:
    """Remove expired upload tokens and their associated temp files.

    Called on every parse request to prevent memory leaks from abandoned
    parse sessions (user closes browser, clicks Back, etc.).
    """
    now = datetime.now(timezone.utc)
    expired = [k for k, v in _upload_tokens.items() if now - v["created_at"] > _TOKEN_TTL]
    for k in expired:
        path = _upload_tokens[k].get("path")
        if path and os.path.exists(path):
            try:
                os.unlink(path)
            except OSError:
                logger.warning("Failed to clean up temp file: %s", path)
        del _upload_tokens[k]
    if expired:
        logger.info("Cleaned up %d expired upload token(s)", len(expired))


# =============================================================================
# API Endpoints
# =============================================================================


class AppConfig(BaseModel):
    """Public application configuration served to frontend clients."""

    depot_lat: float = Field(description="Depot latitude")
    depot_lng: float = Field(description="Depot longitude")
    safety_multiplier: float = Field(description="Route time safety multiplier")
    office_phone_number: str = Field(description="Office phone in E.164 format")
    zone_radius_km: float = Field(description="Geocode validation zone radius in km")


@app.get("/health")
async def health_check():
    """Enhanced health check with per-service status.

    Returns overall status (healthy/degraded/unhealthy) and per-service
    breakdown. Used by start-daily.sh health polling and dashboard status bar.

    - 200: all services healthy
    - 503: one or more services unhealthy (includes details in response body)
    """
    service_health = getattr(app.state, "service_health", {})
    google_status, google_msg = check_google_api()

    services = {
        "postgresql": {
            "status": "connected" if service_health.get("postgresql", (False,))[0] else "unavailable",
            "message": service_health.get("postgresql", (False, "unknown"))[1],
        },
        "osrm": {
            "status": "available" if service_health.get("osrm", (False,))[0] else "unavailable",
            "message": service_health.get("osrm", (False, "unknown"))[1],
        },
        "vroom": {
            "status": "available" if service_health.get("vroom", (False,))[0] else "unavailable",
            "message": service_health.get("vroom", (False, "unknown"))[1],
        },
        "google_api": {
            "status": google_status,
            "message": google_msg,
        },
    }

    all_healthy = all(
        s["status"] in ("connected", "available", "configured", "not_configured")
        for s in services.values()
    )
    any_unhealthy = any(
        s["status"] in ("unavailable", "timeout", "error")
        for s in services.values()
    )
    overall = "healthy" if all_healthy else ("unhealthy" if any_unhealthy else "degraded")

    started_at = getattr(app.state, "started_at", datetime.now(timezone.utc))
    uptime = (datetime.now(timezone.utc) - started_at).total_seconds()

    status_code = 200 if overall == "healthy" else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall,
            "service": "kerala-lpg-optimizer",
            "version": app.version,
            "uptime_seconds": round(uptime, 1),
            "services": services,
        },
    )


@app.get("/api/config", response_model=AppConfig)
async def get_app_config():
    """Return public application configuration.

    Frontend clients read depot coordinates, safety multiplier,
    and office phone number from this endpoint instead of
    hardcoding values.
    """
    return AppConfig(
        depot_lat=config.DEPOT_LOCATION.latitude,
        depot_lng=config.DEPOT_LOCATION.longitude,
        safety_multiplier=config.SAFETY_MULTIPLIER,
        office_phone_number=config.OFFICE_PHONE_NUMBER,
        zone_radius_km=config.GEOCODE_ZONE_RADIUS_KM,
    )


async def auto_create_drivers_from_csv(
    session: AsyncSession,
    preprocessed_df: "pd.DataFrame",
) -> dict:
    """Auto-create drivers from CSV DeliveryMan column.

    For each unique delivery_man in the DataFrame:
    1. Fuzzy-match against ALL existing drivers (including deactivated)
       using the snapshot taken BEFORE processing starts.
    2. If match found and active: record as "existing"
    3. If match found and inactive: reactivate, record as "reactivated"
    4. If no match: create new driver, record as "new"

    CRITICAL: Do NOT merge intra-CSV name variations. Process each unique
    name independently against the EXISTING driver database at the start.
    New drivers created from this CSV are NOT used as match targets for
    other names in the same CSV.

    Args:
        session: Async DB session.
        preprocessed_df: CDCMS preprocessed DataFrame with delivery_man column.

    Returns:
        Dict with new_drivers, matched_drivers, reactivated_drivers, existing_drivers.
    """
    if "delivery_man" not in preprocessed_df.columns:
        return None

    # Extract unique delivery_man values, dropping NaN/empty
    unique_names = (
        preprocessed_df["delivery_man"]
        .dropna()
        .str.strip()
        .loc[lambda s: s != ""]
        .unique()
        .tolist()
    )

    if not unique_names:
        return None

    # Take a snapshot of existing drivers BEFORE processing
    # so intra-CSV names don't match each other
    existing_drivers_snapshot = await repo.get_all_drivers(session)

    new_drivers: list[str] = []
    matched_drivers: list[dict] = []
    reactivated_drivers: list[str] = []
    existing_drivers: list[str] = []

    for csv_name in unique_names:
        # Find fuzzy matches against the pre-existing snapshot only
        matches = await repo.find_similar_drivers(session, csv_name)

        if matches:
            best_match, score = matches[0]
            if best_match.is_active:
                existing_drivers.append(best_match.name)
                matched_drivers.append({
                    "csv_name": csv_name.strip().title(),
                    "matched_to": best_match.name,
                    "score": score,
                })
            else:
                # Reactivate deactivated driver
                await repo.reactivate_driver(session, best_match.id)
                reactivated_drivers.append(best_match.name)
        else:
            # No match -- create new driver
            driver = await repo.create_driver(session, csv_name)
            new_drivers.append(driver.name)

    return {
        "new_drivers": new_drivers,
        "matched_drivers": matched_drivers,
        "reactivated_drivers": reactivated_drivers,
        "existing_drivers": existing_drivers,
    }


@app.post("/api/parse-upload", response_model=ParsePreviewResponse, dependencies=[Depends(verify_api_key)])
@limiter.limit("10/minute")
async def parse_upload(
    request: Request,
    file: UploadFile = File(...),
    session: AsyncSession = SessionDep,
):
    """Parse a CDCMS upload file and return driver preview data (Phase 17).

    This is step 1 of the two-step upload flow:
    1. parse_upload() -- fast parse, returns driver list for selection
    2. upload_and_optimize() -- runs geocoding + optimization for selected drivers

    The file is validated, saved to a temp location, and parsed with the
    CDCMS preprocessor. Driver auto-creation runs to categorize each driver
    as new/matched/reactivated/existing. An upload_token is returned to
    reference the parsed file for the subsequent process step.

    Returns 400 if the file is not a recognized CDCMS export or has no
    Allocated-Printed orders after filtering.
    """
    # --- File validation (same as upload-orders) ---
    filename = file.filename or ""
    ext = pathlib.Path(filename).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        return error_response(
            status_code=400,
            error_code=ErrorCode.UPLOAD_INVALID_FORMAT,
            user_message=f"Unsupported file type ({ext or 'none'}) -- use .csv, .xlsx, or .xls",
            technical_message=f"Expected one of {sorted(ALLOWED_EXTENSIONS)}, got '{ext}'",
            request_id=request_id_var.get(""),
        )

    content_type = file.content_type or ""
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        return error_response(
            status_code=400,
            error_code=ErrorCode.UPLOAD_INVALID_FORMAT,
            user_message=f"Unexpected content type ({content_type}) -- upload a CSV or Excel file",
            technical_message=f"Allowed types: {sorted(ALLOWED_CONTENT_TYPES)}",
            request_id=request_id_var.get(""),
        )

    suffix = ".csv" if ext == ".csv" else ".xlsx"
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            if len(content) > MAX_UPLOAD_SIZE_BYTES:
                size_mb = len(content) / (1024 * 1024)
                max_mb = MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
                return error_response(
                    status_code=413,
                    error_code=ErrorCode.UPLOAD_FILE_TOO_LARGE,
                    user_message=f"File too large ({size_mb:.1f} MB) -- maximum is {max_mb:.0f} MB",
                    technical_message=f"{len(content)} bytes exceeds {MAX_UPLOAD_SIZE_BYTES} byte limit",
                    request_id=request_id_var.get(""),
                )
            if len(content) == 0:
                return error_response(
                    status_code=400,
                    error_code=ErrorCode.UPLOAD_INVALID_FORMAT,
                    user_message="File is empty -- upload a CDCMS export with delivery orders",
                    technical_message="Uploaded file has 0 bytes",
                    request_id=request_id_var.get(""),
                )
            tmp.write(content)
            tmp_path = tmp.name

        # --- CDCMS detection ---
        is_cdcms = _is_cdcms_format(tmp_path)
        if not is_cdcms:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return error_response(
                status_code=400,
                error_code=ErrorCode.UPLOAD_INVALID_FORMAT,
                user_message="File is not a recognized CDCMS export -- ensure the file has OrderNo and ConsumerAddress columns",
                technical_message="CDCMS format detection failed: missing required marker columns",
                request_id=request_id_var.get(""),
            )

        # --- Preprocess CDCMS file ---
        # Count total rows before filtering (read raw file for count)
        try:
            if suffix == ".xlsx":
                raw_df = pd.read_excel(tmp_path, dtype=str)
            else:
                raw_df = pd.read_csv(tmp_path, sep="\t", dtype=str)
            total_rows = len(raw_df)
        except Exception:
            total_rows = 0

        preprocessed_df = preprocess_cdcms(
            tmp_path,
            area_suffix=config.CDCMS_AREA_SUFFIX,
        )

        if preprocessed_df.empty:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return error_response(
                status_code=400,
                error_code=ErrorCode.UPLOAD_NO_VALID_ORDERS,
                user_message="No Allocated-Printed orders found in this file -- check that the CDCMS export contains pending orders",
                technical_message=f"preprocess_cdcms returned empty DataFrame from {total_rows} total rows",
                request_id=request_id_var.get(""),
            )

        filtered_rows = len(preprocessed_df)

        # Phase 19: Fail fast if DeliveryMan column is missing -- per-driver TSP requires it.
        # Check both column existence AND that at least one non-empty value exists.
        # preprocess_cdcms fills missing DeliveryMan with empty strings (not NaN),
        # so dropna() alone won't catch the "column exists but all empty" case.
        _has_delivery_man = (
            "delivery_man" in preprocessed_df.columns
            and not preprocessed_df["delivery_man"].dropna().str.strip().replace("", pd.NA).dropna().empty
        )
        if not _has_delivery_man:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return error_response(
                status_code=400,
                error_code=ErrorCode.UPLOAD_INVALID_FORMAT,
                user_message="CSV is missing the DeliveryMan column -- this file must be a CDCMS export with driver assignments. Upload a file exported from CDCMS after allocating orders to drivers.",
                technical_message="delivery_man column missing or empty in preprocessed DataFrame",
                request_id=request_id_var.get(""),
            )

        # --- Driver auto-creation and categorization ---
        driver_summary = await auto_create_drivers_from_csv(session, preprocessed_df)

        # --- Build per-driver order counts ---
        driver_order_counts: dict[str, int] = {}
        if "delivery_man" in preprocessed_df.columns:
            for name, group in preprocessed_df.groupby("delivery_man"):
                if pd.notna(name) and str(name).strip():
                    driver_order_counts[str(name).strip()] = len(group)

        # --- Build DriverPreview list ---
        driver_previews: list[DriverPreview] = []

        if driver_summary:
            # Map csv_name -> status based on driver_summary categories
            csv_name_status: dict[str, dict] = {}

            for name in driver_summary.get("new_drivers", []):
                # Find the original csv_name from order counts
                for csv_name in driver_order_counts:
                    if csv_name.strip().title() == name:
                        csv_name_status[csv_name] = {"status": "new", "display_name": name}
                        break
                else:
                    # Fallback: use the name as-is
                    csv_name_status[name] = {"status": "new", "display_name": name}

            for match_info in driver_summary.get("matched_drivers", []):
                csv_title = match_info["csv_name"]
                for csv_name in driver_order_counts:
                    if csv_name.strip().title() == csv_title:
                        csv_name_status[csv_name] = {
                            "status": "matched",
                            "display_name": match_info["matched_to"],
                            "matched_to": match_info["matched_to"],
                            "match_score": match_info["score"],
                        }
                        break

            for name in driver_summary.get("reactivated_drivers", []):
                for csv_name in driver_order_counts:
                    if csv_name.strip().title() == name or csv_name.strip().upper() == name.upper():
                        csv_name_status[csv_name] = {
                            "status": "reactivated",
                            "display_name": name,
                            "matched_to": name,
                        }
                        break
                else:
                    csv_name_status[name] = {"status": "reactivated", "display_name": name, "matched_to": name}

            for name in driver_summary.get("existing_drivers", []):
                for csv_name in driver_order_counts:
                    if csv_name.strip().title() == name or csv_name.strip().upper() == name.upper():
                        if csv_name not in csv_name_status:
                            csv_name_status[csv_name] = {
                                "status": "existing",
                                "display_name": name,
                            }
                        break

            # Build preview list from all drivers in order counts
            for csv_name, count in driver_order_counts.items():
                info = csv_name_status.get(csv_name, {})
                driver_previews.append(DriverPreview(
                    csv_name=csv_name,
                    display_name=info.get("display_name", csv_name.strip().title()),
                    order_count=count,
                    status=info.get("status", "new"),
                    matched_to=info.get("matched_to"),
                    match_score=info.get("match_score"),
                ))
        else:
            # No driver_summary (no delivery_man column) -- single unnamed driver
            for csv_name, count in driver_order_counts.items():
                driver_previews.append(DriverPreview(
                    csv_name=csv_name,
                    display_name=csv_name.strip().title(),
                    order_count=count,
                    status="new",
                ))

        # --- Generate upload token ---
        _cleanup_expired_tokens()
        token = str(uuid.uuid4())
        _upload_tokens[token] = {
            "path": tmp_path,
            "filename": filename,
            "created_at": datetime.now(timezone.utc),
        }

        logger.info(
            "Parse-upload complete: %d total rows, %d filtered, %d drivers, token=%s",
            total_rows, filtered_rows, len(driver_previews), token[:8],
        )

        return ParsePreviewResponse(
            upload_token=token,
            filename=filename,
            total_rows=total_rows,
            filtered_rows=filtered_rows,
            drivers=driver_previews,
        )

    except Exception as exc:
        # Clean up temp file on unexpected errors
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        logger.exception("Parse-upload failed: %s", exc)
        return error_response(
            status_code=500,
            error_code=ErrorCode.INTERNAL_ERROR,
            user_message="Failed to parse file -- please try again or contact IT",
            technical_message=str(exc),
            request_id=request_id_var.get(""),
        )


@app.post("/api/upload-orders", response_model=OptimizationSummary, dependencies=[Depends(verify_api_key)])
@limiter.limit("10/minute")
async def upload_and_optimize(
    request: Request,
    file: UploadFile = File(None),
    upload_token: str = Form(None),
    selected_drivers: str = Form(None),
    session: AsyncSession = SessionDep,
):
    """Upload a CSV/Excel from CDCMS and get optimized routes.

    Supports two modes:
    A. Direct upload (backward compatible): Send file in multipart form.
    B. Two-step flow (Phase 17): Send upload_token from parse-upload plus
       optional selected_drivers JSON array. The token references a file
       already on the server, avoiding re-upload.

    The endpoint:
    1. Parse the uploaded/stored file into Orders
    2. Geocode any addresses without coordinates (cache results in DB)
    3. Run VROOM optimizer to assign orders to vehicles
    4. Persist everything to PostgreSQL (orders, routes, stops)

    Args:
        file: CSV/Excel file (required if upload_token not provided).
        upload_token: UUID from parse-upload (skips file upload/save).
        selected_drivers: JSON array of csv_name strings to generate routes for.
            When provided, only these drivers' orders are optimized.
            All orders are still geocoded regardless.

    Returns a summary with a run_id. Drivers then call
    GET /api/routes/{vehicle_id} to get their specific route.
    Requires X-API-Key header when API_KEY env var is set.
    """
    # --- Determine input mode: token-based or file-based ---
    tmp_path: str | None = None
    preprocessed_path: str | None = None
    filename: str = ""
    token_based = False

    # Parse selected_drivers JSON if provided
    selected_driver_list: list[str] | None = None
    if selected_drivers:
        try:
            selected_driver_list = json.loads(selected_drivers)
            if not isinstance(selected_driver_list, list):
                return error_response(
                    status_code=400,
                    error_code=ErrorCode.INVALID_REQUEST,
                    user_message="selected_drivers must be a JSON array of driver names",
                    technical_message=f"selected_drivers parsed to {type(selected_driver_list).__name__}, expected list",
                    request_id=request_id_var.get(""),
                )
        except json.JSONDecodeError as e:
            return error_response(
                status_code=400,
                error_code=ErrorCode.INVALID_REQUEST,
                user_message="Invalid selected_drivers format -- expected a JSON array",
                technical_message=f"json.JSONDecodeError: {e}",
                request_id=request_id_var.get(""),
            )

    if upload_token:
        # --- Token-based mode: load file from parse-upload step ---
        token_data = _upload_tokens.get(upload_token)
        if not token_data:
            return error_response(
                status_code=400,
                error_code=ErrorCode.INVALID_REQUEST,
                user_message="Upload session expired -- please re-upload the file",
                technical_message=f"Upload token '{upload_token[:8]}...' not found in token store",
                request_id=request_id_var.get(""),
            )

        # Check TTL
        now = datetime.now(timezone.utc)
        if now - token_data["created_at"] > _TOKEN_TTL:
            # Clean up expired token
            path = token_data.get("path")
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                except OSError:
                    pass
            del _upload_tokens[upload_token]
            return error_response(
                status_code=400,
                error_code=ErrorCode.INVALID_REQUEST,
                user_message="Upload session expired -- please re-upload the file",
                technical_message=f"Token created at {token_data['created_at']} exceeded {_TOKEN_TTL} TTL",
                request_id=request_id_var.get(""),
            )

        # Consume the token (one-time use)
        tmp_path = token_data["path"]
        filename = token_data["filename"]
        del _upload_tokens[upload_token]
        token_based = True

        # Verify the file still exists on disk
        if not tmp_path or not os.path.exists(tmp_path):
            return error_response(
                status_code=400,
                error_code=ErrorCode.INVALID_REQUEST,
                user_message="Upload session expired -- please re-upload the file",
                technical_message=f"Token file '{tmp_path}' no longer exists on disk",
                request_id=request_id_var.get(""),
            )

        logger.info("Token-based upload: loading stored file %s (token=%s)", filename, upload_token[:8])

    elif file and file.filename:
        # --- File-based mode (backward compatible) ---
        filename = file.filename or ""
        ext = pathlib.Path(filename).suffix.lower()

        # Extension check with descriptive error
        if ext not in ALLOWED_EXTENSIONS:
            return error_response(
                status_code=400,
                error_code=ErrorCode.UPLOAD_INVALID_FORMAT,
                user_message=f"Unsupported file type ({ext or 'none'}) -- use .csv, .xlsx, or .xls",
                technical_message=f"Expected one of {sorted(ALLOWED_EXTENSIONS)}, got '{ext}'",
                request_id=request_id_var.get(""),
            )

        # Content-type check
        content_type = file.content_type or ""
        if content_type and content_type not in ALLOWED_CONTENT_TYPES:
            return error_response(
                status_code=400,
                error_code=ErrorCode.UPLOAD_INVALID_FORMAT,
                user_message=f"Unexpected content type ({content_type}) -- upload a CSV or Excel file",
                technical_message=f"Allowed types: {sorted(ALLOWED_CONTENT_TYPES)}",
                request_id=request_id_var.get(""),
            )

        suffix = ".csv" if ext == ".csv" else ".xlsx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            if len(content) > MAX_UPLOAD_SIZE_BYTES:
                size_mb = len(content) / (1024 * 1024)
                max_mb = MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
                return error_response(
                    status_code=413,
                    error_code=ErrorCode.UPLOAD_FILE_TOO_LARGE,
                    user_message=f"File too large ({size_mb:.1f} MB) -- maximum is {max_mb:.0f} MB",
                    technical_message=f"{len(content)} bytes exceeds {MAX_UPLOAD_SIZE_BYTES} byte limit",
                    request_id=request_id_var.get(""),
                )
            tmp.write(content)
            tmp_path = tmp.name
    else:
        # Neither token nor file provided
        return error_response(
            status_code=400,
            error_code=ErrorCode.INVALID_REQUEST,
            user_message="No file or upload token provided -- upload a CDCMS export file or provide an upload_token from a previous parse",
            technical_message="Both file and upload_token are None/empty",
            request_id=request_id_var.get(""),
        )

    try:
        # Step 1: Import orders from CSV/Excel
        # Auto-detect CDCMS format: if the file is tab-separated with CDCMS
        # column names (OrderNo, ConsumerAddress), run the preprocessor first
        # to clean addresses and extract relevant columns. Otherwise, treat
        # as a standard CSV with our expected column names.
        #
        # Why auto-detect instead of a separate endpoint?
        # The employee workflow is: export from CDCMS -> upload here. Adding
        # a preprocessing step would confuse non-technical users. The system
        # should "just work" with whatever file they upload.
        is_cdcms = _is_cdcms_format(tmp_path)

        if is_cdcms:
            logger.info("Detected CDCMS tab-separated format — running preprocessor")
            preprocessed_df = preprocess_cdcms(
                tmp_path,
                area_suffix=config.CDCMS_AREA_SUFFIX,
            )
            if preprocessed_df.empty:
                return error_response(
                    status_code=400,
                    error_code=ErrorCode.UPLOAD_NO_ALLOCATED,
                    user_message="No 'Allocated-Printed' orders found in CDCMS export -- check that the file has orders with status 'Allocated-Printed'",
                    technical_message="preprocess_cdcms returned empty DataFrame",
                    request_id=request_id_var.get(""),
                )
            # Save preprocessed data to a temp CSV for CsvImporter
            preprocessed_path = tmp_path + ".preprocessed.csv"
            preprocessed_df.to_csv(preprocessed_path, index=False)
            importer = CsvImporter(
                column_mapping=get_cdcms_column_mapping(),
                default_cylinder_weight_kg=config.DEFAULT_CYLINDER_KG,
                cylinder_weight_lookup=config.CYLINDER_WEIGHTS,
                coordinate_bounds=config.INDIA_COORDINATE_BOUNDS,
            )
            import_result = importer.import_orders(preprocessed_path)
            orders = import_result.orders
            # Clean up the intermediate preprocessed file immediately.
            # Also cleaned in finally block in case import_orders() throws.
            os.unlink(preprocessed_path)
            preprocessed_path = None  # Mark as cleaned
        else:
            # Standard CSV format (order_id, address, etc.)
            importer = CsvImporter(
                default_cylinder_weight_kg=config.DEFAULT_CYLINDER_KG,
                cylinder_weight_lookup=config.CYLINDER_WEIGHTS,
                coordinate_bounds=config.INDIA_COORDINATE_BOUNDS,
            )
            import_result = importer.import_orders(tmp_path)
            orders = import_result.orders

        # Backfill address_original for orders where it wasn't set.
        # CDCMS uploads: address_original is set by CsvImporter from the preprocessed CSV's
        #   address_original column (populated by preprocess_cdcms from raw ConsumerAddress).
        # Standard CSV uploads: the CSV has no address_original column, so CsvImporter
        #   leaves it as None. For these, the raw and cleaned text are identical, so
        #   we set address_original = address_raw.
        for order in orders:
            if order.address_original is None:
                order.address_original = order.address_raw

        # Phase 13: Build order_id -> area_name mapping for geocode validation.
        # CDCMS exports have an area_name column; standard CSVs do not.
        # This mapping is passed to the validator during geocoding so out-of-zone
        # addresses can be retried with the area name.
        area_name_map: dict[str, str] = {}
        if is_cdcms and not preprocessed_df.empty:
            area_name_map = dict(
                zip(
                    preprocessed_df["order_id"].astype(str).str.strip(),
                    preprocessed_df["area_name"].str.strip(),
                )
            )

        # Phase 16: Auto-create drivers from CDCMS DeliveryMan column.
        # This runs early in the pipeline (before geocoding) so drivers are
        # created even if geocoding fails for some orders. For non-CDCMS uploads,
        # driver_summary stays None (backward compatible).
        driver_summary = None
        if is_cdcms and not preprocessed_df.empty:
            driver_summary = await auto_create_drivers_from_csv(session, preprocessed_df)

        # Step 1a: Convert ImportResult errors/warnings to ImportFailure lists.
        # These track validation-stage failures (bad CSV data caught before geocoding).
        # Geocoding failures are collected separately in step 2 below.
        validation_failures: list[ImportFailure] = [
            ImportFailure(
                row_number=err.row_number,
                address_snippet="",  # Address may be empty/missing for validation errors
                reason=err.message,
                stage="validation",
            )
            for err in import_result.errors
        ]
        validation_warnings: list[ImportFailure] = [
            ImportFailure(
                row_number=w.row_number,
                address_snippet="",
                reason=w.message,
                stage="validation",
            )
            for w in import_result.warnings
        ]
        # Map order_id → spreadsheet row number for geocoding error tracking.
        # When geocoding fails, we use this to report the original CSV row.
        order_row_map = import_result.row_numbers

        if not orders:
            if import_result.errors:
                # All rows failed validation — return structured response with failures
                # instead of a generic 400 error. Staff can see exactly which rows to fix.
                return OptimizationSummary(
                    success=True,
                    imported=0,
                    total=len(import_result.errors),
                    run_id="",
                    assignment_id="",
                    total_orders=0,
                    orders_assigned=0,
                    orders_unassigned=0,
                    vehicles_used=0,
                    optimization_time_ms=0,
                    created_at=datetime.now(timezone.utc),
                    total_rows=len(import_result.errors),
                    geocoded=0,
                    failed_geocoding=0,
                    failed_validation=len(import_result.errors),
                    failures=validation_failures,
                    warnings=validation_warnings,
                    cache_hits=0,
                    api_calls=0,
                    estimated_cost_usd=0.0,
                    free_tier_note="",
                    per_order_geocode_source={},
                    duplicate_warnings=[],
                    drivers=driver_summary,
                )
            # Genuinely empty file (no rows at all, no errors) — this is a user error
            return error_response(
                status_code=400,
                error_code=ErrorCode.UPLOAD_NO_VALID_ORDERS,
                user_message="No valid orders found in file -- check that the CSV has data rows",
                technical_message="CsvImporter returned 0 orders and 0 errors",
                request_id=request_id_var.get(""),
            )

        # Step 1b: Enforce minimum delivery window (Kerala MVD compliance)
        # Non-negotiable: no delivery window shorter than 30 minutes.
        # This prevents "10-minute delivery" promises that pressure drivers.
        # Rather than rejecting orders, we WIDEN narrow windows to the minimum.
        # The original window_end is extended; window_start stays as-is.
        min_window = config.MIN_DELIVERY_WINDOW_MINUTES
        widened_count = 0
        for order in orders:
            if order.delivery_window_start and order.delivery_window_end:
                # Calculate window duration in minutes
                start_mins = order.delivery_window_start.hour * 60 + order.delivery_window_start.minute
                end_mins = order.delivery_window_end.hour * 60 + order.delivery_window_end.minute
                # Handle midnight crossing (e.g., 23:00 → 01:00)
                if end_mins <= start_mins:
                    end_mins += 24 * 60
                window_mins = end_mins - start_mins

                if window_mins < min_window:
                    # Widen by extending end time to meet minimum
                    new_end_mins = start_mins + min_window
                    # Wrap around midnight if needed
                    new_end_mins = new_end_mins % (24 * 60)
                    new_end_hour = new_end_mins // 60
                    new_end_minute = new_end_mins % 60
                    order.delivery_window_end = dt_time(new_end_hour, new_end_minute)
                    widened_count += 1

        if widened_count > 0:
            logger.info(
                "Widened %d delivery window(s) to minimum %d minutes (MVD compliance)",
                widened_count,
                min_window,
            )

        # Phase 17 gap closure: Filter orders by selected drivers BEFORE geocoding.
        # Previously this filter was after geocoding (wasting API calls on deselected
        # drivers' orders). Now only selected drivers' orders are geocoded.
        if selected_driver_list is not None and is_cdcms and not preprocessed_df.empty:
            order_driver_map: dict[str, str] = {}
            if "delivery_man" in preprocessed_df.columns:
                for _, row in preprocessed_df.iterrows():
                    oid = str(row.get("order_id", "")).strip()
                    dm = str(row.get("delivery_man", "")).strip()
                    if oid and dm:
                        order_driver_map[oid] = dm

            selected_set = set(selected_driver_list)
            before_filter = len(orders)
            orders = [
                o for o in orders
                if order_driver_map.get(o.order_id, "") in selected_set
            ]
            # Also filter area_name_map to only selected orders
            area_name_map = {k: v for k, v in area_name_map.items() if k in {o.order_id for o in orders}}
            logger.info(
                "Driver selection: %d of %d orders selected for geocoding (%d drivers selected)",
                len(orders), before_filter, len(selected_set),
            )

        # Step 2: Geocode orders that don't have coordinates
        # CachedGeocoder handles DB cache lookup + API fallback in one call.
        geocoder = _get_geocoder()
        # Apply retry decorator to individual geocoding HTTP calls.
        # This wraps _call_api (synchronous httpx.get) so each Google API
        # request is retried on transient failures (ConnectError, TimeoutException).
        # Permanent errors (HTTP 400/401/403) are NOT retried.
        if geocoder is not None:
            geocoder._call_api = geocoding_retry(geocoder._call_api)
        geocoding_failures: list[ImportFailure] = []

        # GEO-04: Initialize cost tracking variables (available in all return paths)
        per_order_source: dict[str, str] = {}
        geo_cache_hits = 0
        geo_api_calls = 0
        estimated_cost = 0.0
        free_tier_note = ""
        duplicate_warnings_list: list[DuplicateLocationWarning] = []

        # Phase 13: Create zone validator for geocode validation + fallback chain.
        # Every geocoded address is validated against a radius from the depot.
        # Out-of-zone results trigger: area-name retry -> centroid -> depot fallback.
        from core.geocoding.validator import GeocodeValidator
        dictionary_path = str(
            pathlib.Path(__file__).resolve().parents[3] / "data" / "place_names_vatakara.json"
        )
        validator = GeocodeValidator(
            depot_lat=config.DEPOT_LOCATION.latitude,
            depot_lon=config.DEPOT_LOCATION.longitude,
            zone_radius_m=config.GEOCODE_ZONE_RADIUS_KM * 1000,
            dictionary_path=dictionary_path if os.path.exists(dictionary_path) else None,
            area_suffix=config.CDCMS_AREA_SUFFIX,
        )

        # Use CachedGeocoder for unified cache-then-API flow
        cached_geocoder = CachedGeocoder(
            upstream=geocoder, session=session, validator=validator
        ) if geocoder else None

        for order in orders:
            if not order.is_geocoded:
                if cached_geocoder:
                    # GEO-04: Snapshot stats before geocoding to detect cache hit vs API call
                    hits_before = cached_geocoder.stats["hits"]
                    area_name = area_name_map.get(order.order_id)
                    result = await cached_geocoder.geocode(order.address_raw, area_name=area_name)
                    if result.success and result.location:
                        order.location = result.location
                        # Phase 13: Store validation confidence and method on order
                        order.geocode_confidence = result.confidence
                        order.geocode_method = result.method
                        # Track per-order geocode source
                        if cached_geocoder.stats["hits"] > hits_before:
                            per_order_source[order.order_id] = "cached"
                        else:
                            per_order_source[order.order_id] = "api_call"
                    else:
                        # Log the raw Google API response for debugging.
                        # Common causes: API key not enabled, billing not set up,
                        # or address too ambiguous for Google to resolve.
                        raw = getattr(result, "raw_response", {})
                        error_msg = raw.get("error_message", "")
                        status = raw.get("status", "UNKNOWN")
                        logger.warning(
                            "Could not geocode order %s: %s (API status: %s%s)",
                            order.order_id,
                            order.address_raw,
                            status,
                            f" — {error_msg}" if error_msg else "",
                        )
                        # Collect structured failure for the response.
                        # Staff sees a human-friendly reason, not raw API codes.
                        reason = GEOCODING_REASON_MAP.get(
                            status, "Could not find this address -- try checking the spelling"
                        )
                        if status not in GEOCODING_REASON_MAP:
                            logger.warning(
                                "Unmapped geocoding status '%s' for order %s",
                                status,
                                order.order_id,
                            )
                        geocoding_failures.append(ImportFailure(
                            row_number=order_row_map.get(order.order_id, 0),
                            address_snippet=order.address_raw[:80],
                            reason=reason,
                            stage="geocoding",
                        ))
                else:
                    # No geocoder available -- still try cache for previously
                    # geocoded addresses, then fail if no cache hit
                    cached = await repo.get_cached_geocode(session, order.address_raw)
                    if cached:
                        order.location = cached
                        per_order_source[order.order_id] = "cached"
                    else:
                        geocoding_failures.append(ImportFailure(
                            row_number=order_row_map.get(order.order_id, 0),
                            address_snippet=order.address_raw[:80],
                            reason="Geocoding service not configured (missing API key)",
                            stage="geocoding",
                        ))

        # Phase 13: Validate pre-geocoded orders (had coordinates in CSV).
        # These orders skipped the geocoding loop above because is_geocoded was
        # already True. We still need to zone-validate their coordinates.
        if validator:
            for order in orders:
                if order.is_geocoded and order.geocode_method is None:
                    # Order had coordinates from CSV but hasn't been validated yet
                    vr = validator.validate(
                        order.location.latitude, order.location.longitude,
                        area_name=area_name_map.get(order.order_id),
                        geocoder=geocoder,
                    )
                    order.location = Location(
                        latitude=vr.latitude,
                        longitude=vr.longitude,
                        address_text=order.location.address_text,
                        geocode_confidence=vr.confidence,
                    )
                    order.geocode_confidence = vr.confidence
                    order.geocode_method = vr.method

        # Phase 13: Log validation stats for observability
        if validator:
            logger.info(
                "Geocode validation: %d direct, %d area-retry, %d centroid, %d depot fallback",
                validator.stats.get("direct_count", 0),
                validator.stats.get("area_retry_count", 0),
                validator.stats.get("centroid_count", 0),
                validator.stats.get("depot_count", 0),
            )

        # Combine all failures and determine how many orders geocoded successfully
        all_failures = validation_failures + geocoding_failures
        all_warnings = validation_warnings
        geocoded_orders = [o for o in orders if o.is_geocoded]

        # Phase 13: Circuit breaker warning -- surface API key issues to staff
        if validator and validator.is_tripped:
            circuit_breaker_count = sum(
                1 for o in orders
                if getattr(o, 'geocode_method', None) in ('centroid', 'depot')
            )
            all_warnings.append(
                ImportFailure(
                    row_number=0,
                    address_snippet="",
                    reason=f"Google Maps API key issue -- {circuit_breaker_count} stop(s) have approximate locations. Ask IT to check the API key.",
                    stage="geocoding",
                )
            )

        # --- GEO-04: Collect geocoding cost stats ---
        if cached_geocoder:
            geo_cache_hits = cached_geocoder.stats["hits"]
            geo_api_calls = cached_geocoder.stats["misses"]
        else:
            # Cache-only mode (no API key): all results are cache hits
            geo_cache_hits = len(geocoded_orders)
            geo_api_calls = 0

        estimated_cost = geo_api_calls * config.GEOCODING_COST_PER_REQUEST
        if geo_api_calls > 0:
            free_tier_note = (
                f"{geo_api_calls} API call{'s' if geo_api_calls != 1 else ''} "
                f"(~${estimated_cost:.2f}) — within ${config.GEOCODING_FREE_TIER_USD:.0f}/month free tier"
            )
        elif geo_cache_hits > 0:
            free_tier_note = "All addresses resolved from cache (no API cost)"
        else:
            free_tier_note = ""

        # --- GEO-03: Duplicate location detection ---
        duplicate_clusters = detect_duplicate_locations(
            geocoded_orders,
            thresholds=config.DUPLICATE_THRESHOLDS,
        )
        duplicate_warnings_list = [
            DuplicateLocationWarning(
                order_ids=c.order_ids,
                addresses=c.addresses,
                max_distance_m=c.max_distance_m,
            )
            for c in duplicate_clusters
        ]

        if not geocoded_orders:
            # Zero-success case: return structured 200 with all failure details
            # instead of HTTPException(400). Staff sees per-row reasons and can
            # fix addresses in the next upload.
            #
            # Diagnostic: test with a known-good address to surface API config issues.
            # This log message helps admins debug API key / billing problems.
            if geocoder:
                test_result = geocoder.geocode("Kerala, India")
                raw = getattr(test_result, "raw_response", {})
                api_status = raw.get("status", "")
                api_error = raw.get("error_message", "")
                if api_status == "REQUEST_DENIED" and api_error:
                    logger.error("Google Geocoding API error: %s", api_error)
                elif api_status == "OVER_QUERY_LIMIT":
                    logger.error("Google Geocoding API quota exceeded. Check billing.")

            return OptimizationSummary(
                success=True,
                imported=0,
                total=len(orders) + len(import_result.errors),
                run_id="",
                assignment_id="",
                total_orders=len(orders),
                orders_assigned=0,
                orders_unassigned=0,
                vehicles_used=0,
                optimization_time_ms=0,
                created_at=datetime.now(timezone.utc),
                total_rows=len(orders) + len(import_result.errors),
                geocoded=0,
                failed_geocoding=len(geocoding_failures),
                failed_validation=len(import_result.errors),
                failures=all_failures,
                warnings=all_warnings,
                cache_hits=geo_cache_hits,
                api_calls=geo_api_calls,
                estimated_cost_usd=estimated_cost,
                free_tier_note=free_tier_note,
                per_order_geocode_source=per_order_source,
                duplicate_warnings=[],  # No geocoded orders, so no duplicates
                drivers=driver_summary,
            )

        # Step 3: Per-driver TSP optimization (Phase 19)
        # No vehicle fleet needed -- each driver gets 1 virtual vehicle with uncapped capacity.
        # The DeliveryMan column from the CSV determines grouping.

        effective_multiplier = config.SAFETY_MULTIPLIER
        if datetime.now().month in config.MONSOON_MONTHS:
            effective_multiplier *= config.MONSOON_MULTIPLIER
            logger.info(
                "Monsoon season active -- using %.1fx travel time multiplier",
                effective_multiplier,
            )

        optimizer = VroomAdapter(
            vroom_url=config.VROOM_URL,
            safety_multiplier=effective_multiplier,
        )
        optimizer.optimize = optimizer_retry(optimizer.optimize)

        # Build order-driver map from preprocessed DataFrame (only for geocoded orders)
        order_driver_map: dict[str, str] = {}
        if is_cdcms and not preprocessed_df.empty and "delivery_man" in preprocessed_df.columns:
            for _, row in preprocessed_df.iterrows():
                oid = str(row.get("order_id", "")).strip()
                dm = str(row.get("delivery_man", "")).strip()
                if oid and dm:
                    order_driver_map[oid] = dm
        elif not is_cdcms:
            # Standard CSV (non-CDCMS): no driver column, group all orders under
            # a single default driver for backward compatibility with TSP pipeline
            for o in geocoded_orders:
                order_driver_map[o.order_id] = "Driver"

        # Group geocoded orders by driver
        orders_by_driver = group_orders_by_driver(geocoded_orders, order_driver_map)

        if not orders_by_driver:
            # No orders could be mapped to drivers
            return error_response(
                status_code=400,
                error_code=ErrorCode.INVALID_REQUEST,
                user_message="No orders could be matched to drivers -- check that the DeliveryMan column has valid names",
                technical_message="group_orders_by_driver returned empty dict",
                request_id=request_id_var.get(""),
            )

        # Build driver name -> UUID map from auto_create_drivers_from_csv result
        driver_uuids: dict[str, uuid.UUID] = {}
        if driver_summary:
            # Query all active drivers to build name->UUID mapping
            all_drivers = await repo.get_all_drivers(session)
            for drv in all_drivers:
                driver_uuids[drv.name] = drv.id
                # Also map normalized name for fuzzy match resilience
                if hasattr(drv, "name_normalized") and drv.name_normalized:
                    driver_uuids[drv.name_normalized] = drv.id

        # Run per-driver TSP
        assignment, opt_warnings = optimize_per_driver(
            orders_by_driver=orders_by_driver,
            driver_uuids=driver_uuids,
            depot=config.DEPOT_LOCATION,
            optimizer=optimizer,
        )

        # Post-optimization validations (OPT-04 + OPT-05)
        overlap_errors = validate_no_overlap(assignment)
        if overlap_errors:
            logger.error("Order overlap detected: %s", overlap_errors)
            opt_warnings.extend(overlap_errors)

        geo_anomalies = detect_geographic_anomalies(assignment)
        opt_warnings.extend(geo_anomalies)

        # Populate driver_id FK on routes for DB persistence
        for route in assignment.routes:
            driver_uuid = driver_uuids.get(route.driver_name) or driver_uuids.get(route.vehicle_id)
            if driver_uuid:
                route.driver_id = driver_uuid

        # Add optimization warnings (overlap, anomalies, partial failures)
        for w in opt_warnings:
            all_warnings.append(ImportFailure(
                row_number=0,
                address_snippet="",
                reason=w,
                stage="optimization",
            ))

        # Step 4: Persist to database
        run_id = await repo.save_optimization_run(
            session=session,
            assignment=assignment,
            orders=orders,
            source_filename=filename,
            safety_multiplier=effective_multiplier,
        )
        await session.commit()

        return OptimizationSummary(
            success=True,
            imported=len(geocoded_orders),
            total=len(orders) + len(import_result.errors),
            run_id=str(run_id),
            assignment_id=assignment.assignment_id,
            total_orders=len(orders),
            orders_assigned=assignment.total_orders_assigned,
            orders_unassigned=len(assignment.unassigned_order_ids),
            vehicles_used=assignment.vehicles_used,
            optimization_time_ms=assignment.optimization_time_ms,
            created_at=assignment.created_at,
            # Import diagnostics: total_rows is all CSV data rows (valid + rejected)
            total_rows=len(orders) + len(import_result.errors),
            geocoded=len(geocoded_orders),
            failed_geocoding=len(geocoding_failures),
            failed_validation=len(import_result.errors),
            failures=all_failures,
            warnings=all_warnings,
            # GEO-04: Cost transparency
            cache_hits=geo_cache_hits,
            api_calls=geo_api_calls,
            estimated_cost_usd=estimated_cost,
            free_tier_note=free_tier_note,
            per_order_geocode_source=per_order_source,
            # GEO-03: Duplicate location warnings
            duplicate_warnings=duplicate_warnings_list,
            # Phase 16: Driver auto-creation summary
            drivers=driver_summary,
        )

    except ValueError as e:
        # ValueError from preprocess_cdcms() or CsvImporter._validate_columns()
        # already has a humanized message — pass it through as HTTP 400.
        return error_response(
            status_code=400,
            error_code=ErrorCode.INVALID_REQUEST,
            user_message=str(e),
            technical_message=f"ValueError: {e}",
            request_id=request_id_var.get(""),
        )

    except httpx.ConnectError as e:
        logger.error("VROOM/OSRM connection failed during upload: %s", e)
        return error_response(
            status_code=503,
            error_code=ErrorCode.OPTIMIZER_UNAVAILABLE,
            user_message="Route optimizer is not ready yet -- OSRM may still be downloading map data (this takes ~15 minutes on first run). Please wait and try again",
            technical_message=f"httpx.ConnectError: {e}",
            request_id=request_id_var.get(""),
        )
    except httpx.TimeoutException as e:
        logger.error("VROOM/OSRM timed out during upload: %s", e)
        return error_response(
            status_code=503,
            error_code=ErrorCode.OPTIMIZER_TIMEOUT,
            user_message="Route optimizer timed out -- OSRM may still be processing map data. Please wait a few minutes and try again",
            technical_message=f"httpx.TimeoutException: {e}",
            request_id=request_id_var.get(""),
        )
    except httpx.HTTPStatusError as e:
        logger.error("VROOM returned error %d: %s", e.response.status_code, e.response.text[:300])
        return error_response(
            status_code=502,
            error_code=ErrorCode.OPTIMIZER_ERROR,
            user_message=f"Route optimizer returned an error (HTTP {e.response.status_code}) -- this may indicate OSRM is still starting up. Please try again in a few minutes",
            technical_message=f"VROOM HTTP {e.response.status_code}: {e.response.text[:200]}",
            request_id=request_id_var.get(""),
        )
    except Exception as e:
        logger.exception("Unexpected error during upload: %s", e)
        return error_response(
            status_code=500,
            error_code=ErrorCode.INTERNAL_ERROR,
            user_message="An unexpected error occurred while processing your upload -- please check that all services are running and try again",
            technical_message=f"{type(e).__name__}: {e}",
            request_id=request_id_var.get(""),
        )

    finally:
        # Clean up temp files — only if they were created and not yet removed.
        # preprocessed_path is set to None after successful cleanup above,
        # so this only fires if an exception prevented normal cleanup.
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if preprocessed_path and os.path.exists(preprocessed_path):
            os.unlink(preprocessed_path)


@app.get("/api/routes")
async def list_routes(include_stops: bool = False, session: AsyncSession = SessionDep):
    """Get all routes from the latest optimization.

    Returns a summary list — one entry per vehicle/driver.
    Used by the office dashboard to see the full picture.
    Reads from PostgreSQL instead of in-memory (Phase 2+).

    Query params:
        include_stops: When true, each route includes its full stops array,
            total_weight_kg, and total_items. Used by the dashboard LiveMap
            to load all route data in a single request instead of N+1 calls.
            Default false for backward compatibility.
    """
    run = await repo.get_latest_run(session)
    if not run:
        return error_response(
            status_code=404,
            error_code=ErrorCode.ROUTE_NO_RUNS,
            user_message="No routes generated yet -- upload orders first",
            request_id=request_id_var.get(""),
        )

    route_dbs = await repo.get_routes_for_run(session, run.id)

    if include_stops:
        # Batch mode: return full route details (with stops) for every vehicle.
        # Eliminates the N+1 pattern where the dashboard fetches summaries
        # then calls GET /api/routes/{vehicle_id} for each vehicle.
        return {
            "assignment_id": str(run.id),
            "routes": [
                {
                    "route_id": str(r.id),
                    "vehicle_id": r.vehicle_id,
                    "driver_name": r.driver_name,
                    "total_stops": len(r.stops),
                    "total_distance_km": round(r.total_distance_km, 2),
                    "total_duration_minutes": round(r.total_duration_minutes, 1),
                    "total_weight_kg": round(r.total_weight_kg, 1),
                    "total_items": r.total_items,
                    "stops": [
                        {
                            "sequence": stop.sequence,
                            "order_id": stop.order_id,
                            "address": stop.address_display,
                            "address_raw": stop.address_original,
                            "latitude": stop.location.latitude,
                            "longitude": stop.location.longitude,
                            "weight_kg": round(stop.weight_kg, 1),
                            "quantity": stop.quantity,
                            "notes": stop.notes,
                            "distance_from_prev_km": round(stop.distance_from_prev_km, 2),
                            "duration_from_prev_minutes": round(stop.duration_from_prev_minutes, 1),
                            "status": stop.status,
                        }
                        for stop in repo.route_db_to_pydantic(r).stops
                    ],
                }
                for r in route_dbs
            ],
            "unassigned_orders": run.orders_unassigned,
        }

    return {
        "assignment_id": str(run.id),
        "routes": [
            {
                "route_id": str(r.id),
                "vehicle_id": r.vehicle_id,
                "driver_name": r.driver_name,
                "total_stops": len(r.stops),
                "total_distance_km": round(r.total_distance_km, 2),
                "total_duration_minutes": round(r.total_duration_minutes, 1),
                "total_weight_kg": round(r.total_weight_kg, 1),
                "total_items": r.total_items,
            }
            for r in route_dbs
        ],
        "unassigned_orders": run.orders_unassigned,
    }


@app.get("/api/routes/{vehicle_id}")
async def get_driver_route(vehicle_id: str, session: AsyncSession = SessionDep):
    """Get the specific route for a driver/vehicle.

    This is what the driver app calls. Returns an ordered list of
    stops with addresses, map coordinates, and delivery details.

    Safety: No countdown timers. Shows estimated arrival as a range
    ("between HH:MM and HH:MM"), never a countdown.
    """
    run = await repo.get_latest_run(session)
    if not run:
        return error_response(
            status_code=404,
            error_code=ErrorCode.ROUTE_NO_RUNS,
            user_message="No routes generated yet -- upload orders first",
            request_id=request_id_var.get(""),
        )

    route_db = await repo.get_route_for_vehicle(session, run.id, vehicle_id)
    if not route_db:
        return error_response(
            status_code=404,
            error_code=ErrorCode.ROUTE_NOT_FOUND,
            user_message=f"No route found for vehicle {vehicle_id}",
            technical_message=f"run_id={run.id}, vehicle_id={vehicle_id}",
            request_id=request_id_var.get(""),
        )

    # Convert to Pydantic for clean serialization
    route = repo.route_db_to_pydantic(route_db)

    return {
        "route_id": route.route_id,
        "vehicle_id": route.vehicle_id,
        "driver_name": route.driver_name,
        "total_stops": route.stop_count,
        "total_distance_km": round(route.total_distance_km, 2),
        "total_duration_minutes": round(route.total_duration_minutes, 1),
        "stops": [
            {
                "sequence": stop.sequence,
                "order_id": stop.order_id,
                "address": stop.address_display,
                "address_raw": stop.address_original,
                "latitude": stop.location.latitude,
                "longitude": stop.location.longitude,
                "weight_kg": round(stop.weight_kg, 1),
                "quantity": stop.quantity,
                "notes": stop.notes,
                "distance_from_prev_km": round(stop.distance_from_prev_km, 2),
                "duration_from_prev_minutes": round(stop.duration_from_prev_minutes, 1),
                "status": stop.status,
                # Phase 14: Geocode confidence for "Approx. location" badge
                "geocode_confidence": stop.geocode_confidence,
                "geocode_method": stop.geocode_method,
                "location_approximate": (
                    stop.geocode_confidence is not None
                    and stop.geocode_confidence < 0.5
                ),
            }
            for stop in route.stops
        ],
    }


class StatusUpdate(BaseModel):
    """Request body for updating a delivery stop's status.

    Why a body param instead of query param?
    - REST convention: mutations use request bodies
    - Easier for the driver app to queue offline and replay later
    - Type-safe validation via Pydantic

    Using Literal instead of plain str gives us:
    - Automatic Pydantic validation (rejects unknown values)
    - Better OpenAPI schema (enum in docs)
    - No manual validation needed in the endpoint

    Phase 2 addition: optional GPS coordinates for proof-of-delivery.
    When a driver marks a stop as delivered, their current GPS location
    is recorded. This lets us:
    1. Verify the driver was at the right place
    2. Build a driver-verified geocode database (better than any API!)
    """

    status: Literal["delivered", "failed", "pending"] = Field(
        ..., description="New status for this delivery stop"
    )
    latitude: float | None = Field(
        default=None, ge=-90, le=90, description="Driver's GPS latitude at delivery"
    )
    longitude: float | None = Field(
        default=None, ge=-180, le=180, description="Driver's GPS longitude at delivery"
    )


@app.post("/api/routes/{vehicle_id}/stops/{order_id}/status", dependencies=[Depends(verify_api_key)])
@limiter.limit("60/minute")
async def update_stop_status(
    request: Request,
    vehicle_id: str,
    order_id: str,
    body: StatusUpdate,
    session: AsyncSession = SessionDep,
):
    """Update delivery status for a specific stop.

    Called by the driver app when they mark a delivery as:
    - "delivered" — successfully completed
    - "failed" — could not deliver (customer absent, wrong address, etc.)

    No time pressure language in responses — Kerala MVD compliance.

    If a GPS location is included, it's recorded as proof-of-delivery
    and used to build a driver-verified geocode database.
    """
    run = await repo.get_latest_run(session)
    if not run:
        return error_response(
            status_code=404,
            error_code=ErrorCode.ROUTE_NO_RUNS,
            user_message="No routes generated yet -- upload orders first",
            request_id=request_id_var.get(""),
        )

    # Find the route for this vehicle
    route_db = await repo.get_route_for_vehicle(session, run.id, vehicle_id)
    if not route_db:
        return error_response(
            status_code=404,
            error_code=ErrorCode.ROUTE_STOP_NOT_FOUND,
            user_message=f"Stop not found for vehicle {vehicle_id}",
            technical_message=f"No route for vehicle_id={vehicle_id}",
            request_id=request_id_var.get(""),
        )

    # Find the stop by order_id (string) — look up in the stops
    target_stop = None
    for stop in route_db.stops:
        if stop.order and stop.order.order_id == order_id:
            target_stop = stop
            break

    if not target_stop:
        return error_response(
            status_code=404,
            error_code=ErrorCode.ROUTE_STOP_NOT_FOUND,
            user_message=f"Stop {order_id} not found in route for vehicle {vehicle_id}",
            technical_message=f"order_id={order_id} not in route stops",
            request_id=request_id_var.get(""),
        )

    # Parse delivery location if provided
    delivery_loc = None
    if body.latitude is not None and body.longitude is not None:
        delivery_loc = Location(latitude=body.latitude, longitude=body.longitude)

    updated = await repo.update_stop_status(
        session=session,
        route_id=route_db.id,
        order_db_id=target_stop.order_id,
        new_status=body.status,
        delivery_location=delivery_loc,
    )
    await session.commit()

    if not updated:
        return error_response(
            status_code=404,
            error_code=ErrorCode.ROUTE_STOP_NOT_FOUND,
            user_message=f"Stop {order_id} not found",
            technical_message=f"repo.update_stop_status returned False for order_id={order_id}",
            request_id=request_id_var.get(""),
        )

    # --- API-07: Save driver-verified location to geocode cache ---
    # Only on successful delivery WITH GPS — builds verified Kerala address DB.
    # Do NOT fire on "failed" (driver may not be at exact address).
    # Do NOT fire without GPS (no location data to save).
    if body.status == "delivered" and delivery_loc is not None and target_stop.order.address_raw:
        try:
            await repo.save_geocode_cache(
                session=session,
                address_raw=target_stop.order.address_raw,
                location=delivery_loc,
                source="driver_verified",
                confidence=0.95,
            )
            await session.commit()
        except Exception:
            logger.warning(
                "Failed to save driver-verified location for order %s (non-fatal)",
                order_id,
                exc_info=True,
            )

    return {
        "message": f"Order {order_id} marked as {body.status}",
        "order_id": order_id,
        "status": body.status,
    }


# =============================================================================
# QR Code / Google Maps Route URLs
# =============================================================================
# Helper functions (build_google_maps_url, generate_qr_svg/png,
# split_route_into_segments) are in apps/kerala_delivery/api/qr_helpers.py.
# Extracted to keep this module focused on HTTP endpoint concerns.


@app.get("/api/routes/{vehicle_id}/google-maps", dependencies=[Depends(verify_read_key)])
async def get_google_maps_route(
    vehicle_id: str,
    session: AsyncSession = SessionDep,
):
    """Get Google Maps navigation URL(s) and QR code(s) for a vehicle's route.

    The employee scans or prints the QR code → driver scans with phone →
    Google Maps opens with turn-by-turn navigation for their delivery route.

    If the route has > 11 stops, it's automatically split into segments
    (Google Maps only supports 9 waypoints + origin + destination).

    Returns:
        JSON with segments, each containing a Google Maps URL and QR code SVG.
        For routes ≤ 11 stops, there's a single segment.
    """
    run = await repo.get_latest_run(session)
    if not run:
        return error_response(
            status_code=404,
            error_code=ErrorCode.ROUTE_NO_RUNS,
            user_message="No routes generated yet -- upload orders first",
            request_id=request_id_var.get(""),
        )

    route_db = await repo.get_route_for_vehicle(session, run.id, vehicle_id)
    if not route_db:
        return error_response(
            status_code=404,
            error_code=ErrorCode.ROUTE_NOT_FOUND,
            user_message=f"No route found for vehicle {vehicle_id}",
            technical_message=f"run_id={run.id}, vehicle_id={vehicle_id}",
            request_id=request_id_var.get(""),
        )

    route = repo.route_db_to_pydantic(route_db)

    # Build ordered stop list with coordinates
    # Include depot as the first stop (origin for navigation)
    stops = []
    depot = config.DEPOT_LOCATION
    stops.append({
        "latitude": depot.latitude,
        "longitude": depot.longitude,
        "label": "Depot (Start)",
    })
    for stop in route.stops:
        stops.append({
            "latitude": stop.location.latitude,
            "longitude": stop.location.longitude,
            "label": stop.address_display or f"Stop {stop.sequence}",
        })

    segments = split_route_into_segments(stops)

    return {
        "vehicle_id": vehicle_id,
        "driver_name": route.driver_name,
        "total_stops": route.stop_count,
        "total_segments": len(segments),
        "segments": segments,
    }


@app.get("/api/qr-sheet", response_class=HTMLResponse, dependencies=[Depends(verify_read_key)])
async def get_qr_sheet(request: Request, session: AsyncSession = SessionDep):
    """Generate a printable HTML page with QR codes for ALL vehicles.

    Workflow: dispatcher opens this URL in the browser → clicks Print →
    each driver gets a QR code card they scan with their phone to open
    their route in Google Maps for navigation.

    Layout: A4-optimized, 2 cards per row, each card has:
    - Vehicle ID and driver name
    - Number of stops and total distance
    - QR code(s) — one per segment if route > 11 stops
    - Human-readable stop summary

    Why a server-rendered HTML page instead of a React component?
    The print stylesheet needs precise A4 layout control. Server-rendered
    HTML with inline CSS is the most reliable way to ensure consistent
    printing across browsers. No JavaScript dependency — works even if
    the dashboard is down.
    """
    run = await repo.get_latest_run(session)
    if not run:
        return error_response(
            status_code=404,
            error_code=ErrorCode.ROUTE_NO_RUNS,
            user_message="No routes generated yet -- upload orders first",
            request_id=request_id_var.get(""),
        )

    route_dbs = await repo.get_routes_for_run(session, run.id)
    if not route_dbs:
        return error_response(
            status_code=404,
            error_code=ErrorCode.ROUTE_NO_RUNS,
            user_message="No routes found for the latest run",
            technical_message=f"run_id={run.id} has 0 routes",
            request_id=request_id_var.get(""),
        )

    depot = config.DEPOT_LOCATION

    # Build QR data for each vehicle
    vehicle_cards = []
    for route_db in route_dbs:
        route = repo.route_db_to_pydantic(route_db)

        stops = [{"latitude": depot.latitude, "longitude": depot.longitude, "label": "Depot"}]
        for stop in route.stops:
            stops.append({
                "latitude": stop.location.latitude,
                "longitude": stop.location.longitude,
                "label": stop.address_display or f"Stop {stop.sequence}",
            })

        segments = split_route_into_segments(stops)

        # Generate driver PWA access QR code (Phase 19)
        # This is the QR code drivers scan to open their route in the PWA.
        # Separate from Google Maps navigation QR codes (those are for turn-by-turn nav).
        driver_display = route.driver_name or route.vehicle_id
        base_url = str(request.base_url).rstrip("/")
        driver_pwa_url = f"{base_url}/driver/?driver={quote_plus(driver_display)}"
        driver_pwa_qr = generate_qr_base64_png(driver_pwa_url, box_size=8)

        vehicle_cards.append({
            "vehicle_id": route.vehicle_id,
            "driver_name": driver_display,
            "total_stops": route.stop_count,
            "total_distance_km": round(route.total_distance_km, 1),
            "total_duration_minutes": round(route.total_duration_minutes, 0),
            "total_weight_kg": round(route.total_weight_kg, 1),
            "segments": segments,
            # Generate PNG QR codes for print (more printer-compatible than SVG)
            "qr_pngs": [
                generate_qr_base64_png(seg["url"], box_size=8)
                for seg in segments
            ],
            "driver_pwa_qr": driver_pwa_qr,
            "driver_pwa_url": driver_pwa_url,
        })

    # Generate the printable HTML page
    created_at = run.created_at.strftime("%d %b %Y, %I:%M %p") if run.created_at else "Unknown"

    cards_html = ""
    for card in vehicle_cards:
        qr_images = ""
        for i, (seg, png_b64) in enumerate(zip(card["segments"], card["qr_pngs"])):
            segment_label = ""
            if len(card["segments"]) > 1:
                segment_label = f'<div class="segment-label">Part {seg["segment"]}: Stops {seg["start_stop"]}–{seg["end_stop"]}</div>'
            qr_images += f'''
                <div class="qr-block">
                    {segment_label}
                    <img src="data:image/png;base64,{png_b64}" alt="QR Code" class="qr-img" />
                </div>
            '''

        # XSS prevention: escape all user-controllable values before
        # inserting into HTML. Vehicle IDs and driver names come from the
        # database — while they're created via authenticated endpoints,
        # defence-in-depth requires escaping at the output layer.
        esc = html_module.escape
        
        cards_html += f'''
        <div class="card">
            <div class="card-header">
                <div class="driver-name" style="font-size: 1.3em; font-weight: bold;">{esc(str(card["driver_name"]))}</div>
            </div>
            <div class="card-stats">
                <div class="stat">
                    <span class="stat-value">{int(card["total_stops"])}</span>
                    <span class="stat-label">Stops</span>
                </div>
                <div class="stat">
                    <span class="stat-value">{card["total_distance_km"]} km</span>
                    <span class="stat-label">Distance</span>
                </div>
                <div class="stat">
                    <span class="stat-value">{int(card["total_duration_minutes"])}–{int(card["total_duration_minutes"] * config.QR_SHEET_DURATION_BUFFER)} min</span>
                    <span class="stat-label">Est. Route Time</span>
                </div>
                <div class="stat">
                    <span class="stat-value">{card["total_weight_kg"]} kg</span>
                    <span class="stat-label">Weight</span>
                </div>
            </div>
            <div class="qr-container">
                <div class="qr-block" style="margin-bottom: 12px; border-bottom: 1px solid #ddd; padding-bottom: 12px;">
                    <div class="segment-label" style="font-weight: bold;">Scan to open route</div>
                    <img src="data:image/png;base64,{card["driver_pwa_qr"]}" alt="Route QR" class="qr-img" />
                </div>
                {qr_images}
            </div>
            <div class="scan-instruction">Top QR → opens route in phone | Bottom QR(s) → Google Maps navigation</div>
        </div>
        '''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Route QR Codes — {created_at}</title>
    <style>
        /* Print-optimized layout for A4 paper */
        @page {{
            size: A4;
            margin: 10mm;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            color: #1a1a1a;
            background: #fff;
            padding: 16px;
        }}
        .page-header {{
            text-align: center;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 2px solid #333;
        }}
        .page-header h1 {{
            font-size: 20px;
            font-weight: 700;
        }}
        .page-header .date {{
            font-size: 13px;
            color: #555;
            margin-top: 4px;
        }}
        .cards-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        .card {{
            border: 2px solid #333;
            border-radius: 8px;
            padding: 16px;
            break-inside: avoid;
            page-break-inside: avoid;
        }}
        .card-header {{
            margin-bottom: 8px;
            padding-bottom: 6px;
            border-bottom: 1px solid #ddd;
        }}
        .driver-name {{
            font-size: 22px;
            font-weight: 800;
        }}
        .card-stats {{
            display: flex;
            gap: 16px;
            margin-bottom: 12px;
            font-variant-numeric: tabular-nums;
        }}
        .stat {{
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .stat-value {{
            font-size: 16px;
            font-weight: 700;
        }}
        .stat-label {{
            font-size: 11px;
            color: #555;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .qr-container {{
            display: flex;
            justify-content: center;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .qr-block {{
            text-align: center;
        }}
        .segment-label {{
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 6px;
            color: #222;
        }}
        .qr-img {{
            width: 210px;
            height: 210px;
        }}
        .scan-instruction {{
            text-align: center;
            font-size: 13px;
            color: #444;
            margin-top: 10px;
            font-style: italic;
        }}
        /* Screen-only styles */
        @media screen {{
            body {{ max-width: 900px; margin: 0 auto; background: #f5f5f5; }}
            .page-header {{ background: #1a1a1a; color: white; padding: 16px; border-radius: 8px; }}
            .page-header .date {{ color: #ccc; }}
            .print-btn {{
                display: block;
                margin: 0 auto 20px;
                padding: 12px 32px;
                font-size: 16px;
                font-weight: 600;
                background: #D97706;
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
            }}
            .print-btn:hover {{ background: #B45309; }}
            .card {{ background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        }}
        @media print {{
            .print-btn {{ display: none; }}
            .no-print {{ display: none; }}
        }}
    </style>
</head>
<body>
    <div class="page-header">
        <h1>LPG Delivery Route QR Codes</h1>
        <div class="date">Generated: {created_at} | {len(vehicle_cards)} drivers | {sum(c["total_stops"] for c in vehicle_cards)} total deliveries</div>
    </div>
    <button class="print-btn no-print" onclick="window.print()">🖨️ Print QR Sheet</button>
    <div class="cards-grid">
        {cards_html}
    </div>
</body>
</html>'''

    return HTMLResponse(content=html)


# =============================================================================
# GPS Telemetry (Phase 2)
# =============================================================================

class TelemetryPing(BaseModel):
    """GPS ping from a driver's device.

    Sent periodically (every 10-30 seconds) during delivery routes.
    The driver app collects GPS data and batches it when online.
    """

    vehicle_id: str = Field(..., description="Vehicle sending this ping")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    speed_kmh: float | None = Field(default=None, ge=0, description="GPS speed")
    accuracy_m: float | None = Field(default=None, ge=0, description="GPS accuracy in meters")
    heading: float | None = Field(default=None, ge=0, le=360, description="Compass heading")
    recorded_at: datetime | None = Field(
        default=None, description="Device timestamp (ISO 8601). Server uses now() if omitted."
    )
    driver_name: str | None = Field(default=None, description="Driver identifier")


class TelemetryResponse(BaseModel):
    """Response after saving a GPS ping."""

    telemetry_id: str | None
    speed_alert: bool
    message: str


@app.post("/api/telemetry", response_model=TelemetryResponse, dependencies=[Depends(verify_api_key)])
@limiter.limit("120/minute")
async def submit_telemetry(
    request: Request,
    ping: TelemetryPing,
    session: AsyncSession = SessionDep,
):
    """Submit a GPS telemetry ping from a driver's device.

    Called by the driver app every 10-30 seconds during active routes.
    Handles:
    - Storage in PostGIS (for live tracking and historical analysis)
    - Speed safety alerts (flags > 40 km/h in urban zones)
    - GPS accuracy filtering (discards pings > 50m accuracy)

    Safety: speed_alert=true in the response means the driver exceeded
    the urban speed limit. The driver app should show a gentle reminder
    (NOT a panic alarm — we don't want to distract them while driving).
    """
    location = Location(latitude=ping.latitude, longitude=ping.longitude)

    telemetry_id, speed_alert = await repo.save_telemetry(
        session=session,
        vehicle_id=ping.vehicle_id,
        location=location,
        speed_kmh=ping.speed_kmh,
        accuracy_m=ping.accuracy_m,
        heading=ping.heading,
        recorded_at=ping.recorded_at,
        driver_name=ping.driver_name,
        speed_limit_kmh=config.SPEED_LIMIT_KMH,
        accuracy_threshold_m=config.GPS_ACCURACY_THRESHOLD_M,
    )
    await session.commit()

    if telemetry_id is None:
        return TelemetryResponse(
            telemetry_id=None,
            speed_alert=False,
            message=f"Ping discarded — GPS accuracy too low (>{config.GPS_ACCURACY_THRESHOLD_M:.0f}m)",
        )

    msg = "Ping recorded"
    if speed_alert:
        msg = (
            f"Ping recorded — SPEED ALERT: {ping.speed_kmh:.0f} km/h "
            f"exceeds {config.SPEED_LIMIT_KMH:.0f} km/h limit"
        )

    return TelemetryResponse(
        telemetry_id=str(telemetry_id),
        speed_alert=speed_alert,
        message=msg,
    )


@app.get("/api/telemetry/fleet", dependencies=[Depends(verify_read_key)])
async def get_fleet_telemetry(
    session: AsyncSession = SessionDep,
):
    """Get the latest GPS ping for every vehicle in one request.

    Replaces the N+1 pattern where the dashboard calls
    GET /api/telemetry/{vehicle_id}?limit=1 once per vehicle.
    At 13 vehicles polling every 15 seconds, that's 13 HTTP requests
    and 13 DB queries per cycle. This endpoint does it in 1+1.

    Uses PostgreSQL's DISTINCT ON to pick the most recent ping per
    vehicle_id in a single query. The idx_telemetry_vehicle_time index
    makes this efficient even with millions of rows.

    IMPORTANT: This route is defined BEFORE /api/telemetry/{vehicle_id}
    because FastAPI matches routes top-to-bottom. If {vehicle_id} came
    first, the literal "fleet" would be captured as a vehicle_id.

    Requires API key authentication — fleet-wide location data is sensitive
    (real-time GPS positions of all drivers). See verify_read_key.

    Returns:
        Dict with vehicle_id → latest ping mapping and total count.
    """
    pings = await repo.get_fleet_latest_telemetry(session)

    return {
        "count": len(pings),
        "vehicles": {
            p.vehicle_id: {
                "latitude": _point_lat(p.location),
                "longitude": _point_lng(p.location),
                "speed_kmh": p.speed_kmh,
                "accuracy_m": p.accuracy_m,
                "heading": p.heading,
                "recorded_at": p.recorded_at.isoformat() if p.recorded_at else None,
                "speed_alert": p.speed_alert,
            }
            for p in pings
        },
    }


class TelemetryBatchRequest(BaseModel):
    """Batch of GPS pings from a driver's device.

    The driver app queues pings while offline (patchy Kerala mobile data)
    and sends them all at once when connectivity returns. This endpoint
    processes the entire batch in one transaction instead of N separate
    POST /api/telemetry calls.

    Max 100 pings per batch — roughly 50 minutes of 30-second interval data.
    """

    pings: list[TelemetryPing] = Field(
        ...,
        max_length=100,
        description="Array of GPS pings (max 100 per batch)",
    )


@app.post("/api/telemetry/batch", dependencies=[Depends(verify_api_key)])
@limiter.limit("20/minute")
async def submit_telemetry_batch(
    request: Request,
    body: TelemetryBatchRequest,
    session: AsyncSession = SessionDep,
):
    """Submit a batch of GPS telemetry pings.

    Used by the driver app to replay queued pings after coming back online.
    Each ping is validated and saved individually — low-accuracy pings are
    discarded, speed alerts are flagged, but the overall batch succeeds.

    Returns a summary: how many pings were saved, discarded, and alerted.
    """
    ping_dicts = [
        {
            "vehicle_id": p.vehicle_id,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "speed_kmh": p.speed_kmh,
            "accuracy_m": p.accuracy_m,
            "heading": p.heading,
            "recorded_at": p.recorded_at,
            "driver_name": p.driver_name,
        }
        for p in body.pings
    ]

    results = await repo.save_telemetry_batch(
        session=session,
        pings=ping_dicts,
        speed_limit_kmh=config.SPEED_LIMIT_KMH,
        accuracy_threshold_m=config.GPS_ACCURACY_THRESHOLD_M,
    )
    await session.commit()

    saved = sum(1 for tid, _ in results if tid is not None)
    discarded = sum(1 for tid, _ in results if tid is None)
    alerts = sum(1 for _, alert in results if alert)

    return {
        "total": len(body.pings),
        "saved": saved,
        "discarded": discarded,
        "speed_alerts": alerts,
        "message": f"{saved} pings saved, {discarded} discarded (low accuracy), {alerts} speed alerts",
    }


@app.get("/api/telemetry/{vehicle_id}", dependencies=[Depends(verify_read_key)])
async def get_vehicle_telemetry(
    vehicle_id: str,
    limit: int = Query(default=100, ge=1, le=1000, description="Max pings to return"),
    session: AsyncSession = SessionDep,
):
    """Get recent GPS telemetry for a vehicle.

    Used by the operations dashboard to show a driver's live location
    and route trace on the map.

    Args:
        vehicle_id: Which vehicle to query.
        limit: Max pings to return (default 100 ≈ 50 min at 30s intervals).
    """
    pings = await repo.get_vehicle_telemetry(session, vehicle_id, limit=limit)

    return {
        "vehicle_id": vehicle_id,
        "count": len(pings),
        "pings": [
            {
                "latitude": _point_lat(p.location),
                "longitude": _point_lng(p.location),
                "speed_kmh": p.speed_kmh,
                "accuracy_m": p.accuracy_m,
                "heading": p.heading,
                "recorded_at": p.recorded_at.isoformat() if p.recorded_at else None,
                "speed_alert": p.speed_alert,
            }
            for p in pings
        ],
    }


# =============================================================================
# Fleet Management (Phase 2)
# =============================================================================
# CRUD endpoints for managing the vehicle fleet.
# Previously, vehicles were hardcoded in config.py. Now dispatchers can
# add/edit/deactivate vehicles via API. The optimizer reads from the DB
# (falling back to config if the fleet table is empty).


class VehicleCreate(BaseModel):
    """Request body for creating a new vehicle."""

    vehicle_id: str = Field(
        ..., min_length=1, max_length=20,
        description="Unique vehicle identifier (e.g., 'VEH-14')",
    )
    depot_latitude: float = Field(..., ge=-90, le=90, description="Depot latitude")
    depot_longitude: float = Field(..., ge=-180, le=180, description="Depot longitude")
    max_weight_kg: float = Field(default=446.0, gt=0, description="Payload capacity (kg)")
    max_items: int = Field(default=30, gt=0, description="Max items per trip")
    registration_no: str | None = Field(default=None, max_length=20, description="Registration number")
    # Why Literal instead of free string: prevents garbage like vehicle_type="banana"
    # from being persisted. Design doc specifies diesel, electric, and CNG variants.
    vehicle_type: Literal["diesel", "electric", "cng"] = Field(
        default="diesel", description="Vehicle fuel type"
    )
    speed_limit_kmh: float = Field(default=40.0, gt=0, description="Speed limit for safety alerts (km/h)")


class VehicleUpdate(BaseModel):
    """Request body for updating an existing vehicle. Only provided fields are updated."""

    max_weight_kg: float | None = Field(default=None, gt=0)
    max_items: int | None = Field(default=None, gt=0)
    registration_no: str | None = Field(default=None, max_length=20)
    vehicle_type: Literal["diesel", "electric", "cng"] | None = Field(default=None)
    speed_limit_kmh: float | None = Field(default=None, gt=0)
    is_active: bool | None = Field(default=None)
    depot_latitude: float | None = Field(default=None, ge=-90, le=90)
    depot_longitude: float | None = Field(default=None, ge=-180, le=180)


def _vehicle_to_dict(v: "VehicleDB") -> dict:
    """Convert a VehicleDB to a JSON-serializable dict.

    Centralizes the DB→JSON conversion for vehicle responses.
    Extracts coordinates from PostGIS geometry and formats timestamps.
    """
    return {
        "vehicle_id": v.vehicle_id,
        "registration_no": v.registration_no,
        "vehicle_type": v.vehicle_type,
        "max_weight_kg": v.max_weight_kg,
        "max_items": v.max_items,
        "depot_latitude": _point_lat(v.depot_location),
        "depot_longitude": _point_lng(v.depot_location),
        "speed_limit_kmh": v.speed_limit_kmh,
        "is_active": v.is_active,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "updated_at": v.updated_at.isoformat() if v.updated_at else None,
    }


@app.get("/api/vehicles", dependencies=[Depends(verify_read_key)])
async def list_vehicles(
    active_only: bool = Query(default=False, description="If true, return only active vehicles"),
    session: AsyncSession = SessionDep,
):
    """List all vehicles in the fleet.

    Used by the dashboard fleet management page. Returns all vehicles
    by default; pass ?active_only=true for optimizer-relevant vehicles.
    """
    if active_only:
        vehicles = await repo.get_active_vehicles(session)
    else:
        vehicles = await repo.get_all_vehicles(session)

    return {
        "count": len(vehicles),
        "vehicles": [_vehicle_to_dict(v) for v in vehicles],
    }


@app.get("/api/vehicles/{vehicle_id}", dependencies=[Depends(verify_read_key)])
async def get_vehicle(
    vehicle_id: str,
    session: AsyncSession = SessionDep,
):
    """Get details for a specific vehicle."""
    vehicle = await repo.get_vehicle_by_vehicle_id(session, vehicle_id)
    if not vehicle:
        return error_response(
            status_code=404,
            error_code=ErrorCode.FLEET_VEHICLE_NOT_FOUND,
            user_message=f"Vehicle {vehicle_id} not found",
            request_id=request_id_var.get(""),
        )
    return _vehicle_to_dict(vehicle)


@app.post("/api/vehicles", dependencies=[Depends(verify_api_key)])
@limiter.limit("20/minute")
async def create_vehicle(
    request: Request,
    body: VehicleCreate,
    session: AsyncSession = SessionDep,
):
    """Add a new vehicle to the fleet.

    The vehicle will be immediately available for the next optimization run.
    Requires API key authentication.
    """
    # Check for duplicate vehicle_id
    existing = await repo.get_vehicle_by_vehicle_id(session, body.vehicle_id)
    if existing:
        return error_response(
            status_code=409,
            error_code=ErrorCode.FLEET_VEHICLE_EXISTS,
            user_message=f"Vehicle {body.vehicle_id} already exists -- use a different ID",
            request_id=request_id_var.get(""),
        )

    depot = Location(latitude=body.depot_latitude, longitude=body.depot_longitude)
    vehicle = await repo.create_vehicle(
        session=session,
        vehicle_id=body.vehicle_id,
        depot_location=depot,
        max_weight_kg=body.max_weight_kg,
        max_items=body.max_items,
        registration_no=body.registration_no,
        vehicle_type=body.vehicle_type,
        speed_limit_kmh=body.speed_limit_kmh,
    )
    await session.commit()

    return {"message": f"Vehicle {body.vehicle_id} created", "vehicle": _vehicle_to_dict(vehicle)}


@app.put("/api/vehicles/{vehicle_id}", dependencies=[Depends(verify_api_key)])
@limiter.limit("20/minute")
async def update_vehicle(
    request: Request,
    vehicle_id: str,
    body: VehicleUpdate,
    session: AsyncSession = SessionDep,
):
    """Update an existing vehicle's properties.

    Only provided (non-null) fields are updated. Use is_active=false
    to soft-delete a vehicle (it stays in history but is excluded from
    future optimization runs).
    """
    updates = body.model_dump(exclude_none=True)

    # Handle depot coordinates — convert to Location for PostGIS
    if body.depot_latitude is not None and body.depot_longitude is not None:
        updates["depot_location"] = {
            "latitude": body.depot_latitude,
            "longitude": body.depot_longitude,
        }
    # Remove the flat lat/lon keys — repo expects depot_location dict
    updates.pop("depot_latitude", None)
    updates.pop("depot_longitude", None)

    if not updates:
        return error_response(
            status_code=400,
            error_code=ErrorCode.FLEET_NO_FIELDS,
            user_message="No fields to update -- provide at least one field to change",
            request_id=request_id_var.get(""),
        )

    updated = await repo.update_vehicle(session, vehicle_id, updates)
    if not updated:
        return error_response(
            status_code=404,
            error_code=ErrorCode.FLEET_VEHICLE_NOT_FOUND,
            user_message=f"Vehicle {vehicle_id} not found",
            request_id=request_id_var.get(""),
        )

    await session.commit()
    return {"message": f"Vehicle {vehicle_id} updated"}


@app.delete("/api/vehicles/{vehicle_id}", dependencies=[Depends(verify_api_key)])
@limiter.limit("10/minute")
async def delete_vehicle(
    request: Request,
    vehicle_id: str,
    session: AsyncSession = SessionDep,
):
    """Soft-delete a vehicle (set is_active=false).

    Why soft-delete: historical routes reference this vehicle. Hard delete
    would break foreign key constraints and lose audit trail data.
    The vehicle can be reactivated with PUT is_active=true.
    """
    deactivated = await repo.deactivate_vehicle(session, vehicle_id)
    if not deactivated:
        return error_response(
            status_code=404,
            error_code=ErrorCode.FLEET_VEHICLE_NOT_FOUND,
            user_message=f"Vehicle {vehicle_id} not found",
            request_id=request_id_var.get(""),
        )

    await session.commit()
    return {"message": f"Vehicle {vehicle_id} deactivated"}


# =============================================================================
# Driver Management (Phase 16)
# =============================================================================


class DriverCreate(BaseModel):
    """Request body for creating a new driver."""

    name: str = Field(
        ..., min_length=1, max_length=100,
        description="Driver's full name",
    )


class DriverUpdate(BaseModel):
    """Request body for updating an existing driver.

    Only provided (non-null) fields are updated.
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = Field(default=None)


def _driver_to_dict(driver, route_count: int = 0) -> dict:
    """Convert a DriverDB to a JSON-serializable dict.

    Centralizes the DB-to-JSON conversion for driver responses.
    """
    return {
        "id": str(driver.id),
        "name": driver.name,
        "is_active": driver.is_active,
        "route_count": route_count,
        "created_at": driver.created_at.isoformat() if driver.created_at else None,
        "updated_at": driver.updated_at.isoformat() if driver.updated_at else None,
    }


def _similar_drivers_list(matches: list) -> list[dict]:
    """Convert fuzzy match tuples [(DriverDB, score), ...] to JSON-safe dicts."""
    return [
        {
            "id": str(driver.id),
            "name": driver.name,
            "score": round(score, 1),
            "is_active": driver.is_active,
        }
        for driver, score in matches
    ]


# IMPORTANT: check-name is placed BEFORE /{id} routes so FastAPI doesn't
# try to parse "check-name" as a UUID path parameter.
@app.get("/api/drivers/check-name", dependencies=[Depends(verify_read_key)])
async def check_driver_name(
    name: str = Query(..., min_length=1, description="Name to check for similar matches"),
    exclude_id: str | None = Query(default=None, description="UUID to exclude from results"),
    session: AsyncSession = SessionDep,
):
    """Check if a driver name has similar matches in the database.

    Used by the dashboard to warn operators before creating or renaming
    a driver. Returns a list of similar existing drivers with match scores.
    """
    exclude_uuid = uuid.UUID(exclude_id) if exclude_id else None
    matches = await repo.find_similar_drivers(session, name, exclude_uuid)
    return {"similar_drivers": _similar_drivers_list(matches)}


@app.get("/api/drivers", dependencies=[Depends(verify_read_key)])
async def list_drivers(
    active_only: bool = Query(default=False, description="If true, return only active drivers"),
    session: AsyncSession = SessionDep,
):
    """List all drivers with route counts.

    Used by the dashboard driver management page. Returns all drivers
    by default; pass ?active_only=true for active drivers only.
    """
    drivers = await repo.get_all_drivers(session, active_only)
    route_counts = await repo.get_driver_route_counts(session)

    return {
        "count": len(drivers),
        "drivers": [
            _driver_to_dict(d, route_counts.get(d.id, 0))
            for d in drivers
        ],
    }


@app.post("/api/drivers", dependencies=[Depends(verify_api_key)])
@limiter.limit("20/minute")
async def create_driver(
    request: Request,
    body: DriverCreate,
    session: AsyncSession = SessionDep,
):
    """Create a new driver.

    The name is stored title-cased (e.g., "suresh kumar" -> "Suresh Kumar").
    Returns the created driver along with any similar existing drivers
    as an informational warning for the operator.
    """
    # Check for similar names before creating
    similar = await repo.find_similar_drivers(session, body.name)
    driver = await repo.create_driver(session, body.name)
    await session.commit()

    return JSONResponse(
        status_code=201,
        content={
            "message": "Driver created",
            "driver": _driver_to_dict(driver),
            "similar_drivers": _similar_drivers_list(similar),
        },
    )


@app.put("/api/drivers/{driver_id}", dependencies=[Depends(verify_api_key)])
@limiter.limit("20/minute")
async def update_driver(
    request: Request,
    driver_id: str,
    body: DriverUpdate,
    session: AsyncSession = SessionDep,
):
    """Update an existing driver's name and/or active status.

    If name is provided, updates the driver's display name and normalized name.
    If is_active is provided, reactivates or deactivates the driver.
    Returns similar_drivers only when the name was changed.
    """
    driver_uuid = uuid.UUID(driver_id)
    similar_drivers = None

    if body.name is not None:
        updated = await repo.update_driver_name(session, driver_uuid, body.name)
        if not updated:
            return error_response(
                status_code=404,
                error_code=ErrorCode.DRIVER_NOT_FOUND,
                user_message=f"Driver {driver_id} not found",
                request_id=request_id_var.get(""),
            )
        similar = await repo.find_similar_drivers(session, body.name, exclude_id=driver_uuid)
        similar_drivers = _similar_drivers_list(similar)

    if body.is_active is not None:
        driver = await repo.get_driver_by_id(session, driver_uuid)
        if driver is None:
            return error_response(
                status_code=404,
                error_code=ErrorCode.DRIVER_NOT_FOUND,
                user_message=f"Driver {driver_id} not found",
                request_id=request_id_var.get(""),
            )
        if body.is_active:
            await repo.reactivate_driver(session, driver_uuid)
        else:
            await repo.deactivate_driver(session, driver_uuid)

    if body.name is None and body.is_active is None:
        return error_response(
            status_code=400,
            error_code=ErrorCode.DRIVER_NAME_EMPTY,
            user_message="No fields to update -- provide name or is_active",
            request_id=request_id_var.get(""),
        )

    await session.commit()
    result: dict = {"message": "Driver updated"}
    if similar_drivers is not None:
        result["similar_drivers"] = similar_drivers
    return result


@app.delete("/api/drivers/{driver_id}", dependencies=[Depends(verify_api_key)])
@limiter.limit("10/minute")
async def delete_driver(
    request: Request,
    driver_id: str,
    session: AsyncSession = SessionDep,
):
    """Soft-delete a driver (set is_active=false).

    Why soft-delete: routes reference driver_id FK. Hard delete would
    break foreign key constraints and lose audit trail data.
    The driver can be reactivated with PUT is_active=true.
    """
    driver_uuid = uuid.UUID(driver_id)
    deactivated = await repo.deactivate_driver(session, driver_uuid)
    if not deactivated:
        return error_response(
            status_code=404,
            error_code=ErrorCode.DRIVER_NOT_FOUND,
            user_message=f"Driver {driver_id} not found",
            request_id=request_id_var.get(""),
        )

    await session.commit()
    return {"message": f"Driver {driver_id} deactivated"}


# =============================================================================
# Optimization History (Phase 2)
# =============================================================================

@app.get("/api/runs")
async def list_optimization_runs(
    limit: int = Query(default=10, ge=1, le=100, description="Max runs to return"),
    session: AsyncSession = SessionDep,
):
    """List recent optimization runs.

    Used by the dashboard to show optimization history and compare
    run-over-run metrics (e.g., "today used fewer vehicles than yesterday").
    """
    # W4 fix: all DB access goes through the repository layer.
    # This keeps endpoints focused on HTTP concerns (validation, serialization)
    # and lets us mock repo functions cleanly in tests.
    runs = await repo.get_recent_runs(session, limit=limit)

    return {
        "runs": [
            {
                "run_id": str(r.id),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "total_orders": r.total_orders,
                "orders_assigned": r.orders_assigned,
                "orders_unassigned": r.orders_unassigned,
                "vehicles_used": r.vehicles_used,
                "optimization_time_ms": r.optimization_time_ms,
                "source_filename": r.source_filename,
                "status": r.status,
            }
            for r in runs
        ],
    }


@app.get("/api/runs/{run_id}/routes")
async def get_routes_for_run(
    run_id: str,
    session: AsyncSession = SessionDep,
):
    """Get all routes for a specific optimization run.

    Allows the dashboard to view historical routes, not just the latest.
    """
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        return error_response(
            status_code=400,
            error_code=ErrorCode.INVALID_REQUEST,
            user_message="Invalid run ID format -- expected a UUID",
            technical_message=f"Could not parse '{run_id}' as UUID",
            request_id=request_id_var.get(""),
        )

    run = await repo.get_run_by_id(session, run_uuid)
    if not run:
        return error_response(
            status_code=404,
            error_code=ErrorCode.ROUTE_NO_RUNS,
            user_message="Optimization run not found",
            technical_message=f"No run with id={run_id}",
            request_id=request_id_var.get(""),
        )

    route_dbs = await repo.get_routes_for_run(session, run_uuid)

    return {
        "run_id": str(run.id),
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "routes": [
            {
                "route_id": str(r.id),
                "vehicle_id": r.vehicle_id,
                "driver_name": r.driver_name,
                "total_stops": len(r.stops),
                "total_distance_km": round(r.total_distance_km, 2),
                "total_duration_minutes": round(r.total_duration_minutes, 1),
                "total_weight_kg": round(r.total_weight_kg, 1),
                "total_items": r.total_items,
            }
            for r in route_dbs
        ],
    }
