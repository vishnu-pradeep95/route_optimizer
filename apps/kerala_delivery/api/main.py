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

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal

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
    logger.info("Starting up — DB engine pool initialized")
    yield
    # Shutdown: dispose DB connection pool
    await engine.dispose()
    logger.info("Shutdown — DB engine pool disposed")


app = FastAPI(
    title="Kerala LPG Delivery Route Optimizer",
    description=(
        "Upload today's delivery list from CDCMS → get optimized routes "
        "for each driver. Minimizes total distance while respecting vehicle "
        "capacity and delivery priorities."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

# CORS: restrict origins to known frontends.
# SECURITY: never use allow_origins=["*"] in production — it lets any website
# make authenticated requests to this API. Use a whitelist from environment.
# See: https://owasp.org/www-community/attacks/csrf
_allowed_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:8000,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Serve the driver PWA as static files at /driver/
# Drivers open http://<server>:8000/driver/ on their phone
_driver_app_dir = pathlib.Path(__file__).parent.parent / "driver_app"
if _driver_app_dir.exists():
    app.mount("/driver", StaticFiles(directory=str(_driver_app_dir), html=True), name="driver_app")

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


@app.post("/api/upload-orders", response_model=OptimizationSummary)
async def upload_and_optimize(
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
    """
    # Save uploaded file to temp location
    # SECURITY: file.filename can be None if the client omits the name header.
    # Always guard against None before calling string methods.
    filename = file.filename or ""
    suffix = ".csv" if filename.lower().endswith(".csv") else ".xlsx"
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
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

        # Step 2: Geocode orders that don't have coordinates
        # First check the database geocode cache (free!), then fall back to Google API
        api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
        geocoder = GoogleGeocoder(api_key=api_key) if api_key else None

        for order in orders:
            if not order.is_geocoded:
                # Try cache first — saves Google API calls ($5/1000 requests)
                cached = await repo.get_cached_geocode(session, order.address_raw)
                if cached:
                    order.location = cached
                    logger.info("Cache hit for address: %s", order.address_raw[:50])
                elif geocoder:
                    result = geocoder.geocode(order.address_raw)
                    if result.success:
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


@app.post("/api/routes/{vehicle_id}/stops/{order_id}/status")
async def update_stop_status(
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


@app.post("/api/telemetry", response_model=TelemetryResponse)
async def submit_telemetry(
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


@app.get("/api/telemetry/{vehicle_id}")
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
                "latitude": to_shape(p.location).y if p.location else None,
                "longitude": to_shape(p.location).x if p.location else None,
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
