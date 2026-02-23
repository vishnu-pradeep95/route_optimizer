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

import logging
import os
import pathlib
import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from core.database.models import VehicleDB

from apps.kerala_delivery import config
from core.data_import.csv_importer import CsvImporter, ColumnMapping
from core.database.connection import engine, get_session
from core.database import repository as repo
from core.geocoding.google_adapter import GoogleGeocoder
from core.models.location import Location
from core.models.order import Order
from core.models.route import Route, RouteAssignment
from core.models.vehicle import Vehicle
from core.optimizer.vroom_adapter import VroomAdapter
from geoalchemy2.shape import to_shape

logger = logging.getLogger(__name__)

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

# CORS: restrict origins to known frontends.
# SECURITY: never use allow_origins=["*"] in production — it lets any website
# make authenticated requests to this API. Use a whitelist from environment.
# See: https://owasp.org/www-community/attacks/csrf
_allowed_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:8000,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins],
    # PUT and DELETE needed for fleet management CRUD endpoints.
    # Phase 2 added vehicle CRUD — browser preflight checks these.
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Serve the driver PWA as static files at /driver/
# Drivers open http://<server>:8000/driver/ on their phone
_driver_app_dir = pathlib.Path(__file__).parent.parent / "driver_app"
if _driver_app_dir.exists():
    app.mount("/driver", StaticFiles(directory=str(_driver_app_dir), html=True), name="driver_app")

# =============================================================================
# Authentication — API key on mutating endpoints
# =============================================================================
# Why API key (not JWT)?
# This is an internal operations tool with a small user base (dispatchers +
# driver app). API key auth is simpler to implement and debug. JWT is better
# for multi-tenant SaaS — we'll migrate if/when needed in Phase 3+.
# See: plan/session-journal.md (OPEN: C1 auth discussion)
# SECURITY: auto_error=False so we get None (not 403) when the header is
# missing — our verify_api_key function handles the error with a clear message.
_api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

# Maximum upload file size (bytes). 10 MB is generous for CSV/Excel files
# containing 40-50 delivery orders per day. Prevents accidental or malicious
# large uploads from consuming server memory.
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


def _check_api_key(api_key: str | None) -> None:
    """Shared API key verification logic.

    Why a helper instead of duplicating in each dependency?
    Both verify_api_key and verify_read_key use the same key and logic.
    Extracting the check means a future security fix (e.g., switching to
    hmac.compare_digest for timing-safe comparison) only needs one change.

    Raises HTTPException(401) if API_KEY is set and the provided key
    doesn't match. No-ops in dev mode (API_KEY unset).
    """
    expected_key = os.environ.get("API_KEY", "")
    if not expected_key:
        return  # Dev mode — no auth required
    if not api_key or api_key != expected_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include X-API-Key header.",
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
# Why singleton? GoogleGeocoder loads a file-based cache from disk on init.
# Re-creating it per request wastes I/O reading the same cache file every time.
# A module-level singleton loads the cache once and reuses it.
_geocoder_instance: GoogleGeocoder | None = None


def _get_geocoder() -> GoogleGeocoder | None:
    """Get or create the shared GoogleGeocoder instance.

    Returns None if GOOGLE_MAPS_API_KEY is not set (geocoding disabled).
    Thread-safe for the single-worker uvicorn setup we use.
    Note: the instance is cached on first successful creation. If the API key
    changes at runtime, restart the server to pick up the new key.
    """
    global _geocoder_instance
    if _geocoder_instance is not None:
        return _geocoder_instance
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if api_key:
        _geocoder_instance = GoogleGeocoder(api_key=api_key)
    return _geocoder_instance


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
class OptimizationSummary(BaseModel):
    """Summary of the latest optimization run."""
    run_id: str = Field(..., description="UUID of this optimization run (use for subsequent queries)")
    assignment_id: str
    total_orders: int
    orders_assigned: int
    orders_unassigned: int
    vehicles_used: int
    optimization_time_ms: float
    created_at: datetime


# =============================================================================
# Helper: build fleet from Kerala config
# =============================================================================
def _build_fleet() -> list[Vehicle]:
    """Create the vehicle fleet from Kerala-specific configuration.

    All 13 vehicles are identical Piaggio Ape Xtra LDX three-wheelers
    starting from the same depot. In Phase 2, this could read from a
    database with per-vehicle specifics.
    """
    vehicles = []
    for i in range(1, config.NUM_VEHICLES + 1):
        vehicles.append(
            Vehicle(
                vehicle_id=f"VEH-{i:02d}",
                driver_name=f"Driver {i}",  # TODO: read real names from config/DB
                max_weight_kg=config.VEHICLE_MAX_WEIGHT_KG,
                max_items=config.VEHICLE_MAX_CYLINDERS,
                depot=config.DEPOT_LOCATION,
                speed_limit_kmh=config.SPEED_LIMIT_KMH,
            )
        )
    return vehicles


# =============================================================================
# API Endpoints
# =============================================================================


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Use app.version so we don't have to update this string separately.
    # The version is set once in the FastAPI() constructor above.
    return {"status": "ok", "service": "kerala-lpg-optimizer", "version": app.version}


@app.post("/api/upload-orders", response_model=OptimizationSummary, dependencies=[Depends(verify_api_key)])
@limiter.limit("10/minute")
async def upload_and_optimize(
    request: Request,
    file: UploadFile = File(...),
    session: AsyncSession = SessionDep,
):
    """Upload a CSV/Excel from CDCMS and get optimized routes.

    This is the main workflow endpoint:
    1. Parse the uploaded file into Orders
    2. Geocode any addresses without coordinates (cache results in DB)
    3. Run VROOM optimizer to assign orders to vehicles
    4. Persist everything to PostgreSQL (orders, routes, stops)

    Returns a summary with a run_id. Drivers then call
    GET /api/routes/{vehicle_id} to get their specific route.
    Requires X-API-Key header when API_KEY env var is set.
    """
    # Save uploaded file to temp location
    # SECURITY: file.filename can be None if the client omits the name header.
    # Always guard against None before calling string methods.
    filename = file.filename or ""
    # SECURITY: validate file extension before processing.
    # Prevents uploading executables, scripts, or other dangerous file types.
    if not filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Use .csv, .xlsx, or .xls",
        )

    suffix = ".csv" if filename.lower().endswith(".csv") else ".xlsx"
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            # SECURITY: enforce max upload size to prevent memory exhaustion.
            # 10 MB is generous for CSV/Excel with 40-50 orders per day.
            if len(content) > MAX_UPLOAD_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB.",
                )
            tmp.write(content)
            tmp_path = tmp.name
        # Step 1: Import orders from CSV/Excel
        # Pass Kerala-specific cylinder weight lookup from config.
        # Another business would pass their own weight table (or none).
        importer = CsvImporter(
            default_cylinder_weight_kg=config.DEFAULT_CYLINDER_KG,
            cylinder_weight_lookup=config.CYLINDER_WEIGHTS,
            coordinate_bounds=config.INDIA_COORDINATE_BOUNDS,
        )
        orders = importer.import_orders(tmp_path)

        if not orders:
            raise HTTPException(status_code=400, detail="No valid orders found in file")

        # Step 1b: Enforce minimum delivery window (Kerala MVD compliance)
        # Non-negotiable: no delivery window shorter than 30 minutes.
        # This prevents "10-minute delivery" promises that pressure drivers.
        # Rather than rejecting orders, we WIDEN narrow windows to the minimum.
        # The original window_end is extended; window_start stays as-is.
        # See: plan/kerala_delivery_route_system_design.md (Safety Constraints)
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
                    from datetime import time as dt_time
                    order.delivery_window_end = dt_time(new_end_hour, new_end_minute)
                    widened_count += 1

        if widened_count > 0:
            logger.info(
                "Widened %d delivery window(s) to minimum %d minutes (MVD compliance)",
                widened_count,
                min_window,
            )

        # Step 2: Geocode orders that don't have coordinates
        # First check the database geocode cache (free!), then fall back to Google API.
        # Uses module-level singleton to avoid re-reading cache file per request.
        geocoder = _get_geocoder()

        for order in orders:
            if not order.is_geocoded:
                # Try cache first — saves Google API calls ($5/1000 requests)
                cached = await repo.get_cached_geocode(session, order.address_raw)
                if cached:
                    order.location = cached
                    logger.info("Cache hit for address: %s", order.address_raw[:50])
                elif geocoder:
                    result = geocoder.geocode(order.address_raw)
                    # Guard: check result.location is not None before accessing
                    # its attributes. GeocodingResult can have success=True with
                    # location=None in edge cases.
                    if result.success and result.location:
                        order.location = result.location
                        # Cache for future use
                        await repo.save_geocode_cache(
                            session,
                            order.address_raw,
                            result.location,
                            source="google",
                            confidence=result.location.geocode_confidence or 0.5,
                        )
                    else:
                        logger.warning(
                            "Could not geocode order %s: %s",
                            order.order_id,
                            order.address_raw,
                        )

        # Check how many orders are geocoded
        geocoded = [o for o in orders if o.is_geocoded]
        if not geocoded:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No orders could be geocoded. Ensure addresses are valid "
                    "or provide latitude/longitude columns in the CSV. "
                    "Set GOOGLE_MAPS_API_KEY env variable for geocoding."
                ),
            )

        # Step 3: Build fleet and optimize
        # Try loading fleet from database first; fall back to config if DB is empty
        db_vehicles = await repo.get_active_vehicles(session)
        if db_vehicles:
            fleet = [repo.vehicle_db_to_pydantic(v) for v in db_vehicles]
        else:
            fleet = _build_fleet()

        # Apply monsoon multiplier (June–September) on top of base safety multiplier.
        # Kerala monsoon significantly increases travel times: flooded roads, reduced
        # visibility, slower speeds. See design doc Section 3.
        effective_multiplier = config.SAFETY_MULTIPLIER
        if datetime.now().month in config.MONSOON_MONTHS:
            effective_multiplier *= config.MONSOON_MULTIPLIER
            logger.info(
                "Monsoon season active — using %.1f× travel time multiplier",
                effective_multiplier,
            )

        optimizer = VroomAdapter(
            vroom_url=config.VROOM_URL,
            safety_multiplier=effective_multiplier,
        )
        assignment = optimizer.optimize(geocoded, fleet)

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
            run_id=str(run_id),
            assignment_id=assignment.assignment_id,
            total_orders=len(orders),
            orders_assigned=assignment.total_orders_assigned,
            orders_unassigned=len(assignment.unassigned_order_ids),
            vehicles_used=assignment.vehicles_used,
            optimization_time_ms=assignment.optimization_time_ms,
            created_at=assignment.created_at,
        )

    finally:
        # Clean up temp file — only if it was created successfully
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.get("/api/routes")
async def list_routes(session: AsyncSession = SessionDep):
    """Get all routes from the latest optimization.

    Returns a summary list — one entry per vehicle/driver.
    Used by the office dashboard to see the full picture.
    Reads from PostgreSQL instead of in-memory (Phase 2+).
    """
    run = await repo.get_latest_run(session)
    if not run:
        raise HTTPException(status_code=404, detail="No routes generated yet. Upload orders first.")

    route_dbs = await repo.get_routes_for_run(session, run.id)

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
        raise HTTPException(status_code=404, detail="No routes generated yet.")

    route_db = await repo.get_route_for_vehicle(session, run.id, vehicle_id)
    if not route_db:
        raise HTTPException(
            status_code=404,
            detail=f"No route found for vehicle {vehicle_id}",
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
                "latitude": stop.location.latitude,
                "longitude": stop.location.longitude,
                "weight_kg": stop.weight_kg,
                "quantity": stop.quantity,
                "notes": stop.notes,
                "distance_from_prev_km": round(stop.distance_from_prev_km, 2),
                "duration_from_prev_minutes": round(stop.duration_from_prev_minutes, 1),
                "status": stop.status,
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
        raise HTTPException(status_code=404, detail="No routes generated yet.")

    # Find the route for this vehicle
    route_db = await repo.get_route_for_vehicle(session, run.id, vehicle_id)
    if not route_db:
        raise HTTPException(status_code=404, detail="Stop not found")

    # Find the stop by order_id (string) — look up in the stops
    target_stop = None
    for stop in route_db.stops:
        if stop.order and stop.order.order_id == order_id:
            target_stop = stop
            break

    if not target_stop:
        raise HTTPException(status_code=404, detail="Stop not found")

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
        raise HTTPException(status_code=404, detail="Stop not found")

    return {
        "message": f"Order {order_id} marked as {body.status}",
        "order_id": order_id,
        "status": body.status,
    }


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
                "latitude": to_shape(p.location).y if p.location else None,  # type: ignore[union-attr]
                "longitude": to_shape(p.location).x if p.location else None,  # type: ignore[union-attr]
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
                # Cast to Point for type checker — telemetry stores Point geometry
                "latitude": to_shape(p.location).y if p.location else None,  # type: ignore[union-attr]
                "longitude": to_shape(p.location).x if p.location else None,  # type: ignore[union-attr]
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
    depot = to_shape(v.depot_location) if v.depot_location else None
    return {
        "vehicle_id": v.vehicle_id,
        "registration_no": v.registration_no,
        "vehicle_type": v.vehicle_type,
        "max_weight_kg": v.max_weight_kg,
        "max_items": v.max_items,
        "depot_latitude": depot.y if depot else None,
        "depot_longitude": depot.x if depot else None,
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
        raise HTTPException(status_code=404, detail=f"Vehicle {vehicle_id} not found")
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
        raise HTTPException(
            status_code=409,
            detail=f"Vehicle {body.vehicle_id} already exists",
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
        raise HTTPException(status_code=400, detail="No fields to update")

    updated = await repo.update_vehicle(session, vehicle_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Vehicle {vehicle_id} not found")

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
        raise HTTPException(status_code=404, detail=f"Vehicle {vehicle_id} not found")

    await session.commit()
    return {"message": f"Vehicle {vehicle_id} deactivated"}


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
        raise HTTPException(status_code=400, detail="Invalid run_id format")

    run = await repo.get_run_by_id(session, run_uuid)
    if not run:
        raise HTTPException(status_code=404, detail="Optimization run not found")

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
