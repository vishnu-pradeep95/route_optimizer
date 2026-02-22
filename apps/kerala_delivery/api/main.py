"""FastAPI application for the Kerala LPG delivery route optimizer.

This is the main API that:
1. Accepts a CSV/Excel upload of today's CDCMS delivery orders
2. Geocodes any addresses without GPS coordinates
3. Runs the VROOM optimizer to assign orders to drivers
4. Returns optimized routes for each driver

The driver app (PWA) calls this API to get today's route.
"""

import logging
import os
import pathlib
import tempfile
import uuid
from datetime import datetime

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal

from apps.kerala_delivery import config
from core.data_import.csv_importer import CsvImporter, ColumnMapping
from core.geocoding.google_adapter import GoogleGeocoder
from core.models.order import Order
from core.models.route import Route, RouteAssignment
from core.models.vehicle import Vehicle
from core.optimizer.vroom_adapter import VroomAdapter

logger = logging.getLogger(__name__)

# =============================================================================
# App setup
# =============================================================================
app = FastAPI(
    title="Kerala LPG Delivery Route Optimizer",
    description=(
        "Upload today's delivery list from CDCMS → get optimized routes "
        "for each driver. Minimizes total distance while respecting vehicle "
        "capacity and delivery priorities."
    ),
    version="0.1.0",
)

# Allow the driver PWA to call this API from any origin
# In production, restrict to your domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the driver PWA as static files at /driver/
# Drivers open http://<server>:8000/driver/ on their phone
_driver_app_dir = pathlib.Path(__file__).parent.parent / "driver_app"
if _driver_app_dir.exists():
    app.mount("/driver", StaticFiles(directory=str(_driver_app_dir), html=True), name="driver_app")

# =============================================================================
# In-memory storage (Phase 1 — replace with PostgreSQL in Phase 2)
# =============================================================================
# Why in-memory first? Get the end-to-end flow working before adding database
# complexity. With 12-13 drivers and <500 orders/day, memory is fine.
#
# NOTE (thread safety): These globals are not thread-safe. Concurrent requests
# (e.g., two drivers hitting /api/routes while an upload is in progress) could
# see inconsistent state. Acceptable for Phase 1 with uvicorn's single-worker
# async model. Phase 2 moves to PostgreSQL which handles concurrency properly.
_current_assignment: RouteAssignment | None = None
_current_orders: list[Order] = []


# =============================================================================
# Request/Response models
# =============================================================================
class OptimizeRequest(BaseModel):
    """Manual order entry (alternative to CSV upload)."""
    orders: list[dict] = Field(
        ..., description="List of order dicts with address, weight_kg, etc."
    )


class DriverRouteResponse(BaseModel):
    """Simplified route for the driver app."""
    driver_name: str
    vehicle_id: str
    total_stops: int
    total_distance_km: float
    total_duration_minutes: float
    stops: list[dict]


class OptimizationSummary(BaseModel):
    """Summary of the latest optimization run."""
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
    return {"status": "ok", "service": "kerala-lpg-optimizer", "version": "0.1.0"}


@app.post("/api/upload-orders", response_model=OptimizationSummary)
async def upload_and_optimize(file: UploadFile = File(...)):
    """Upload a CSV/Excel from CDCMS and get optimized routes.

    This is the main workflow endpoint:
    1. Parse the uploaded file into Orders
    2. Geocode any addresses without coordinates
    3. Run VROOM optimizer to assign orders to vehicles
    4. Store the result for driver app queries

    Returns a summary of the optimization. Drivers then call
    GET /api/routes/{vehicle_id} to get their specific route.
    """
    global _current_assignment, _current_orders

    # Save uploaded file to temp location
    suffix = ".csv" if file.filename.endswith(".csv") else ".xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Step 1: Import orders from CSV/Excel
        # Pass Kerala-specific cylinder weight lookup from config.
        # Another business would pass their own weight table (or none).
        importer = CsvImporter(
            default_cylinder_weight_kg=config.DEFAULT_CYLINDER_KG,
            cylinder_weight_lookup=config.CYLINDER_WEIGHTS,
        )
        orders = importer.import_orders(tmp_path)

        if not orders:
            raise HTTPException(status_code=400, detail="No valid orders found in file")

        # Step 2: Geocode orders that don't have coordinates
        api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
        if api_key:
            geocoder = GoogleGeocoder(api_key=api_key)
            for order in orders:
                if not order.is_geocoded:
                    result = geocoder.geocode(order.address_raw)
                    if result.success:
                        order.location = result.location
                    else:
                        logger.warning("Could not geocode order %s: %s", order.order_id, order.address_raw)

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

        # Store for driver queries
        _current_assignment = assignment
        _current_orders = orders

        return OptimizationSummary(
            assignment_id=assignment.assignment_id,
            total_orders=len(orders),
            orders_assigned=assignment.total_orders_assigned,
            orders_unassigned=len(assignment.unassigned_order_ids),
            vehicles_used=assignment.vehicles_used,
            optimization_time_ms=assignment.optimization_time_ms,
            created_at=assignment.created_at,
        )

    finally:
        # Clean up temp file
        os.unlink(tmp_path)


@app.get("/api/routes")
async def list_routes():
    """Get all routes from the latest optimization.

    Returns a summary list — one entry per vehicle/driver.
    Used by the office dashboard to see the full picture.
    """
    if not _current_assignment:
        raise HTTPException(status_code=404, detail="No routes generated yet. Upload orders first.")

    return {
        "assignment_id": _current_assignment.assignment_id,
        "routes": [
            {
                "route_id": r.route_id,
                "vehicle_id": r.vehicle_id,
                "driver_name": r.driver_name,
                "total_stops": r.stop_count,
                "total_distance_km": round(r.total_distance_km, 2),
                "total_duration_minutes": round(r.total_duration_minutes, 1),
                "total_weight_kg": round(r.total_weight_kg, 1),
                "total_items": r.total_items,
            }
            for r in _current_assignment.routes
        ],
        "unassigned_orders": _current_assignment.unassigned_order_ids,
    }


@app.get("/api/routes/{vehicle_id}")
async def get_driver_route(vehicle_id: str):
    """Get the specific route for a driver/vehicle.

    This is what the driver app calls. Returns an ordered list of
    stops with addresses, map coordinates, and delivery details.

    Safety: No countdown timers. Shows estimated arrival as a range
    ("between HH:MM and HH:MM"), never a countdown.
    """
    if not _current_assignment:
        raise HTTPException(status_code=404, detail="No routes generated yet.")

    # Find route for this vehicle
    route = next(
        (r for r in _current_assignment.routes if r.vehicle_id == vehicle_id),
        None,
    )
    if not route:
        raise HTTPException(
            status_code=404,
            detail=f"No route found for vehicle {vehicle_id}",
        )

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
    """

    status: Literal["delivered", "failed", "pending"] = Field(
        ..., description="New status for this delivery stop"
    )


@app.post("/api/routes/{vehicle_id}/stops/{order_id}/status")
async def update_stop_status(
    vehicle_id: str, order_id: str, body: StatusUpdate
):
    """Update delivery status for a specific stop.

    Called by the driver app when they mark a delivery as:
    - "delivered" — successfully completed
    - "failed" — could not deliver (customer absent, wrong address, etc.)

    No time pressure language in responses — Kerala MVD compliance.
    """
    if not _current_assignment:
        raise HTTPException(status_code=404, detail="No routes generated yet.")

    # Pydantic's Literal type handles validation automatically —
    # invalid status values are rejected with 422 before reaching here.

    # Find the stop and update
    for route in _current_assignment.routes:
        if route.vehicle_id == vehicle_id:
            for stop in route.stops:
                if stop.order_id == order_id:
                    stop.status = body.status
                    return {
                        "message": f"Order {order_id} marked as {body.status}",
                        "order_id": order_id,
                        "status": body.status,
                    }

    raise HTTPException(status_code=404, detail="Stop not found")
