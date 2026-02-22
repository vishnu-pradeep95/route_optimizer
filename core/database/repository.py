"""Repository layer — CRUD operations for the routing optimization database.

Provides high-level data access methods that convert between:
- Pydantic models (used by API and optimizer) ← core/models/
- SQLAlchemy ORM models (used by the database) ← core/database/models.py

Why a repository pattern instead of raw SQL in endpoints?
1. Separation of concerns: endpoints handle HTTP, repo handles persistence
2. Testability: mock the repo in endpoint tests, test SQL in repo tests
3. Single place to optimize queries (add joins, indexes, caching)
4. Easier to swap databases (e.g., PostgreSQL → SQLite for tests)
See: https://martinfowler.com/eaaCatalog/repository.html

All methods accept an AsyncSession — the caller (FastAPI dependency)
controls transaction boundaries.
"""

import uuid
from datetime import datetime, timezone

from geoalchemy2.functions import ST_MakePoint, ST_SetSRID
from geoalchemy2.shape import to_shape
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database.models import (
    GeocodeCacheDB,
    OptimizationRunDB,
    OrderDB,
    RouteDB,
    RouteStopDB,
    TelemetryDB,
    VehicleDB,
)
from core.models.location import Location
from core.models.order import Order, OrderStatus
from core.models.route import Route, RouteAssignment, RouteStop
from core.models.vehicle import Vehicle


# =============================================================================
# Helper: PostGIS geometry ↔ Pydantic Location conversion
# =============================================================================

def _make_point(location: Location):
    """Convert a Pydantic Location to a PostGIS point expression.

    PostGIS stores coordinates as (longitude, latitude) — the GeoJSON convention.
    Our Location model stores (latitude, longitude) — the human-friendly convention.
    This function handles the flip.

    SRID 4326 = WGS84, the GPS coordinate system. All our spatial data uses this.
    """
    return ST_SetSRID(ST_MakePoint(location.longitude, location.latitude), 4326)


def _point_to_location(
    geom, address_text: str | None = None, confidence: float | None = None
) -> Location | None:
    """Convert a PostGIS geometry to a Pydantic Location.

    Returns None if the geometry is NULL (e.g., order not yet geocoded).
    Uses Shapely's to_shape() to parse the WKB (Well-Known Binary) that
    PostgreSQL returns for geometry columns.
    """
    if geom is None:
        return None
    shape = to_shape(geom)
    return Location(
        latitude=shape.y,    # Shapely point: x=longitude, y=latitude
        longitude=shape.x,
        address_text=address_text,
        geocode_confidence=confidence,
    )


# =============================================================================
# Optimization Runs
# =============================================================================

async def save_optimization_run(
    session: AsyncSession,
    assignment: RouteAssignment,
    orders: list[Order],
    source_filename: str | None = None,
    safety_multiplier: float = 1.3,
) -> uuid.UUID:
    """Persist a complete optimization run: run metadata + orders + routes + stops.

    This is the main "save everything" method called after a successful
    optimization. It creates rows in 4 tables in a single transaction:
    1. optimization_runs (the run itself)
    2. orders (all input orders)
    3. routes (one per vehicle)
    4. route_stops (ordered stops within each route)

    Args:
        session: Async DB session (caller commits/rolls back).
        assignment: The RouteAssignment from the optimizer.
        orders: The full list of input orders (including unassigned).
        source_filename: Name of the uploaded CSV file (for audit trail).
        safety_multiplier: The travel time multiplier used for this run.

    Returns:
        UUID of the created optimization_run row.
    """
    run_id = uuid.uuid4()

    # --- 1. Create the optimization run record ---
    run_db = OptimizationRunDB(
        id=run_id,
        total_orders=len(orders),
        orders_assigned=assignment.total_orders_assigned,
        orders_unassigned=len(assignment.unassigned_order_ids),
        vehicles_used=assignment.vehicles_used,
        optimization_time_ms=assignment.optimization_time_ms,
        safety_multiplier=safety_multiplier,
        source_filename=source_filename,
        status="completed",
    )
    session.add(run_db)

    # --- 2. Save all orders ---
    # Build a mapping from order_id (string) to the DB UUID for linking stops later
    order_id_to_uuid: dict[str, uuid.UUID] = {}
    for order in orders:
        db_order_id = uuid.uuid4()
        order_id_to_uuid[order.order_id] = db_order_id

        order_db = OrderDB(
            id=db_order_id,
            run_id=run_id,
            order_id=order.order_id,
            customer_ref=order.customer_ref,
            address_raw=order.address_raw,
            address_display=(
                order.location.address_text if order.location else None
            ),
            weight_kg=order.weight_kg,
            quantity=order.quantity,
            priority=order.priority,
            service_time_min=order.service_time_minutes,
            notes=order.notes,
            # Phase 2: persist time windows for VRPTW audit trail.
            # These are imported from CSV and used by VROOM — if we don't save them,
            # historical analysis of "was this order delivered within its window?"
            # becomes impossible.
            delivery_window_start=order.delivery_window_start,
            delivery_window_end=order.delivery_window_end,
            status=(
                "assigned"
                if order.order_id not in assignment.unassigned_order_ids
                else "pending"
            ),
            geocode_confidence=(
                order.location.geocode_confidence if order.location else None
            ),
        )
        # Set PostGIS geometry if geocoded
        if order.location:
            order_db.location = _make_point(order.location)

        session.add(order_db)

    # --- 3. Save routes and their stops ---
    for route in assignment.routes:
        route_db_id = uuid.uuid4()
        route_db = RouteDB(
            id=route_db_id,
            run_id=run_id,
            vehicle_id=route.vehicle_id,
            driver_name=route.driver_name,
            total_distance_km=route.total_distance_km,
            total_duration_minutes=route.total_duration_minutes,
            total_weight_kg=route.total_weight_kg,
            total_items=route.total_items,
        )
        session.add(route_db)

        for stop in route.stops:
            # Look up the DB UUID for this order
            db_order_id = order_id_to_uuid.get(stop.order_id)
            if db_order_id is None:
                # Skip stops whose orders we don't have — shouldn't happen
                continue

            stop_db = RouteStopDB(
                route_id=route_db_id,
                order_id=db_order_id,
                sequence=stop.sequence,
                address_display=stop.address_display,
                distance_from_prev_km=stop.distance_from_prev_km,
                duration_from_prev_minutes=stop.duration_from_prev_minutes,
                weight_kg=stop.weight_kg,
                quantity=stop.quantity,
                notes=stop.notes,
                status="pending",
            )
            if stop.location:
                stop_db.location = _make_point(stop.location)

            session.add(stop_db)

    # Flush to database (but don't commit — caller decides)
    await session.flush()
    return run_id


# =============================================================================
# Query: Latest optimization run
# =============================================================================

async def get_latest_run(session: AsyncSession) -> OptimizationRunDB | None:
    """Get the most recent successful optimization run.

    Returns None if no runs exist yet (system just set up).
    """
    result = await session.execute(
        select(OptimizationRunDB)
        .where(OptimizationRunDB.status == "completed")
        .order_by(OptimizationRunDB.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_run_by_id(
    session: AsyncSession, run_id: uuid.UUID
) -> OptimizationRunDB | None:
    """Get a specific optimization run by UUID."""
    result = await session.execute(
        select(OptimizationRunDB).where(OptimizationRunDB.id == run_id)
    )
    return result.scalar_one_or_none()


async def get_recent_runs(
    session: AsyncSession, limit: int = 10
) -> list[OptimizationRunDB]:
    """Get the most recent optimization runs, newest first.

    Used by the dashboard to show optimization history and compare
    run-over-run metrics (e.g., "today used fewer vehicles than yesterday").

    Why keep this in the repository instead of inline in the endpoint?
    - Separation of concerns: endpoints handle HTTP, repo handles SQL
    - Testability: one place to mock for endpoint tests
    - Reusability: the dashboard and any future analytics can call this too
    """
    result = await session.execute(
        select(OptimizationRunDB)
        .order_by(OptimizationRunDB.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# =============================================================================
# Query: Routes
# =============================================================================

async def get_routes_for_run(
    session: AsyncSession, run_id: uuid.UUID
) -> list[RouteDB]:
    """Get all routes for a specific optimization run, with stops eagerly loaded.

    Why selectinload?
    - Avoids N+1 query problem (one query per route to load stops)
    - Loads all stops in a single additional query
    - Better than joinedload for one-to-many (avoids row multiplication)
    See: https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html
    """
    # Why chain selectinload(RouteDB.stops).selectinload(RouteStopDB.order)?
    # In async SQLAlchemy 2.0, accessing a relationship that wasn't eagerly loaded
    # triggers a synchronous lazy-load, which raises MissingGreenlet in an async context.
    # route_db_to_pydantic() accesses stop.order.order_id, so we MUST load the order
    # relationship here. Without this, the code works in tests (mocks don't enforce
    # async loading) but crashes with real PostgreSQL sessions.
    # See: https://docs.sqlalchemy.org/en/20/errors.html#error-xd2s
    result = await session.execute(
        select(RouteDB)
        .where(RouteDB.run_id == run_id)
        .options(selectinload(RouteDB.stops).selectinload(RouteStopDB.order))
    )
    return list(result.scalars().all())


async def get_route_for_vehicle(
    session: AsyncSession, run_id: uuid.UUID, vehicle_id: str
) -> RouteDB | None:
    """Get the route for a specific vehicle in a specific run."""
    # Same eager-load chain as get_routes_for_run — see comment there.
    # update_stop_status() iterates route.stops and accesses stop.order.order_id,
    # so both the stops AND their linked orders must be loaded upfront.
    result = await session.execute(
        select(RouteDB)
        .where(RouteDB.run_id == run_id, RouteDB.vehicle_id == vehicle_id)
        .options(selectinload(RouteDB.stops).selectinload(RouteStopDB.order))
    )
    return result.scalar_one_or_none()


# =============================================================================
# Query: Orders
# =============================================================================

async def get_orders_for_run(
    session: AsyncSession, run_id: uuid.UUID
) -> list[OrderDB]:
    """Get all orders for a specific optimization run."""
    result = await session.execute(
        select(OrderDB).where(OrderDB.run_id == run_id)
    )
    return list(result.scalars().all())


# =============================================================================
# Update: Stop status
# =============================================================================

async def update_stop_status(
    session: AsyncSession,
    route_id: uuid.UUID,
    order_db_id: uuid.UUID,
    new_status: str,
    delivery_location: Location | None = None,
) -> bool:
    """Update the delivery status of a specific stop.

    Called when a driver marks a delivery as 'delivered' or 'failed'.
    If delivered and a GPS location is provided, we record it as
    proof-of-delivery (and later use it for driver-verified geocoding).

    Args:
        session: Async DB session.
        route_id: UUID of the route.
        order_db_id: UUID of the order (DB ID, not the string order_id).
        new_status: New status ('delivered', 'failed', 'pending').
        delivery_location: Driver's GPS at delivery time (for verification).

    Returns:
        True if a row was updated, False if stop not found.
    """
    values: dict = {"status": new_status}

    if new_status == "delivered":
        values["delivered_at"] = datetime.now(timezone.utc)
        if delivery_location:
            values["delivery_location"] = _make_point(delivery_location)

    result = await session.execute(
        update(RouteStopDB)
        .where(
            RouteStopDB.route_id == route_id,
            RouteStopDB.order_id == order_db_id,
        )
        .values(**values)
    )
    # Also update the corresponding order status — but ONLY if the stop was found.
    # Without this guard, a mismatched order_db_id would leave RouteStopDB unchanged
    # (0 rows updated) while still mutating the OrderDB status, corrupting state.
    if result.rowcount > 0:
        await session.execute(
            update(OrderDB)
            .where(OrderDB.id == order_db_id)
            .values(status=new_status)
        )

    await session.flush()
    return result.rowcount > 0


# =============================================================================
# Telemetry: GPS pings
# =============================================================================

async def save_telemetry(
    session: AsyncSession,
    vehicle_id: str,
    location: Location,
    speed_kmh: float | None = None,
    accuracy_m: float | None = None,
    heading: float | None = None,
    recorded_at: datetime | None = None,
    driver_name: str | None = None,
    speed_limit_kmh: float = 40.0,
    accuracy_threshold_m: float = 50.0,
) -> tuple[uuid.UUID | None, bool]:
    """Save a GPS telemetry ping from a driver's device.

    Applies safety checks:
    - Discards pings with GPS accuracy > threshold (too inaccurate)
    - Flags speed_alert if speed > speed_limit_kmh (default 40 km/h urban)

    Args:
        session: Async DB session.
        vehicle_id: Which vehicle sent this ping.
        location: GPS coordinates.
        speed_kmh: Speed at time of ping (from GPS or computed).
        accuracy_m: GPS accuracy in meters. Pings > 50m are discarded.
        heading: Compass heading in degrees (0-360).
        recorded_at: When the GPS reading was taken (device time).
        driver_name: Driver associated with this vehicle.
        speed_limit_kmh: Speed threshold for safety alerts (default: 40 km/h).

    Returns:
        Tuple of (telemetry_id, speed_alert_triggered).
        Returns (None, False) if the ping was discarded (low accuracy).
    """
    # Discard low-accuracy pings — GPS drift in dense Kerala neighborhoods
    # can put drivers on the wrong street. The threshold is configurable per
    # deployment: 50m is a conservative default; tune down to 30m once we
    # have real-world accuracy data from Kerala drivers.
    # See: plan/kerala_delivery_route_system_design.md, Section 10 (GPS drift risk)
    if accuracy_m is not None and accuracy_m > accuracy_threshold_m:
        return None, False

    # Safety check: flag speeds above the urban limit
    # This is a non-negotiable Kerala MVD constraint
    speed_alert = False
    if speed_kmh is not None and speed_kmh > speed_limit_kmh:
        speed_alert = True

    ping_id = uuid.uuid4()
    ping = TelemetryDB(
        id=ping_id,
        vehicle_id=vehicle_id,
        driver_name=driver_name,
        location=_make_point(location),
        speed_kmh=speed_kmh,
        accuracy_m=accuracy_m,
        heading=heading,
        recorded_at=recorded_at or datetime.now(timezone.utc),
        speed_alert=speed_alert,
    )
    session.add(ping)
    await session.flush()

    return ping_id, speed_alert


async def get_vehicle_telemetry(
    session: AsyncSession,
    vehicle_id: str,
    since: datetime | None = None,
    limit: int = 100,
) -> list[TelemetryDB]:
    """Get recent telemetry for a vehicle.

    Used by the dashboard to show a driver's GPS trace on the map.

    Args:
        vehicle_id: Vehicle to query.
        since: Only return pings after this timestamp. If None, returns latest.
        limit: Max rows to return (default 100, enough for ~50 min at 30s intervals).
    """
    query = (
        select(TelemetryDB)
        .where(TelemetryDB.vehicle_id == vehicle_id)
        .order_by(TelemetryDB.recorded_at.desc())
        .limit(limit)
    )
    if since:
        query = query.where(TelemetryDB.recorded_at >= since)

    result = await session.execute(query)
    return list(result.scalars().all())


# =============================================================================
# Vehicles
# =============================================================================

async def get_active_vehicles(session: AsyncSession) -> list[VehicleDB]:
    """Get all active vehicles in the fleet."""
    result = await session.execute(
        select(VehicleDB).where(VehicleDB.is_active == True)  # noqa: E712
    )
    return list(result.scalars().all())


def vehicle_db_to_pydantic(vdb: VehicleDB) -> Vehicle:
    """Convert a VehicleDB ORM object to a Pydantic Vehicle model.

    This is the bridge between the persistence layer and the optimizer.
    The optimizer works with Pydantic models (no DB dependency), so we
    need this conversion at the boundary.
    """
    depot = _point_to_location(vdb.depot_location)
    return Vehicle(
        vehicle_id=vdb.vehicle_id,
        max_weight_kg=vdb.max_weight_kg,
        max_items=vdb.max_items,
        depot=depot if depot else Location(latitude=0, longitude=0),
        speed_limit_kmh=vdb.speed_limit_kmh or 40.0,
    )


# =============================================================================
# Geocode Cache
# =============================================================================

async def get_cached_geocode(
    session: AsyncSession, address_raw: str
) -> Location | None:
    """Look up a cached geocoding result for an address.

    Normalizes the address (lowercase, strip whitespace) before lookup.
    Returns the highest-confidence result if multiple sources have
    geocoded this address.

    Why cache? Google Maps Geocoding API costs $5/1000 requests.
    Repeat customers = free geocoding from cache. Over 6 months,
    this can save 70-80% of geocoding costs.
    """
    normalized = address_raw.strip().lower()
    result = await session.execute(
        select(GeocodeCacheDB)
        .where(GeocodeCacheDB.address_norm == normalized)
        .order_by(GeocodeCacheDB.confidence.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None

    # Increment hit count (tracks cache value over time)
    await session.execute(
        update(GeocodeCacheDB)
        .where(GeocodeCacheDB.id == row.id)
        .values(
            hit_count=GeocodeCacheDB.hit_count + 1,
            last_used_at=datetime.now(timezone.utc),
        )
    )

    return _point_to_location(row.location, confidence=row.confidence)


async def save_geocode_cache(
    session: AsyncSession,
    address_raw: str,
    location: Location,
    source: str = "google",
    confidence: float = 0.5,
) -> None:
    """Cache a geocoding result for future reuse.

    If this address+source combo already exists, updates the location
    and confidence (in case the provider improved their result).

    Args:
        session: Async DB session.
        address_raw: Original address text.
        location: Geocoded coordinates.
        source: Who provided this result ('google', 'driver_verified', 'manual').
        confidence: 0.0-1.0 confidence score.
    """
    normalized = address_raw.strip().lower()

    # Check if already cached from this source
    result = await session.execute(
        select(GeocodeCacheDB).where(
            GeocodeCacheDB.address_norm == normalized,
            GeocodeCacheDB.source == source,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        # Update existing entry
        await session.execute(
            update(GeocodeCacheDB)
            .where(GeocodeCacheDB.id == existing.id)
            .values(
                location=_make_point(location),
                confidence=confidence,
                last_used_at=datetime.now(timezone.utc),
            )
        )
    else:
        # Create new cache entry
        cache_entry = GeocodeCacheDB(
            address_raw=address_raw,
            address_norm=normalized,
            location=_make_point(location),
            source=source,
            confidence=confidence,
        )
        session.add(cache_entry)

    await session.flush()


# =============================================================================
# Conversion helpers: DB → Pydantic (for API responses)
# =============================================================================

def route_db_to_pydantic(route_db: RouteDB) -> Route:
    """Convert a RouteDB ORM object to a Pydantic Route model.

    Used when returning route data from API endpoints.
    The Pydantic model is what gets serialized to JSON.
    """
    stops = []
    for stop_db in route_db.stops:
        loc = _point_to_location(stop_db.location)
        stops.append(
            RouteStop(
                order_id=stop_db.order.order_id if stop_db.order else str(stop_db.order_id),
                location=loc if loc else Location(latitude=0, longitude=0),
                address_display=stop_db.address_display or "",
                sequence=stop_db.sequence,
                distance_from_prev_km=stop_db.distance_from_prev_km or 0.0,
                duration_from_prev_minutes=stop_db.duration_from_prev_minutes or 0.0,
                weight_kg=stop_db.weight_kg or 0.0,
                quantity=stop_db.quantity or 1,
                notes=stop_db.notes or "",
                status=stop_db.status or "pending",
            )
        )

    return Route(
        route_id=str(route_db.id),
        vehicle_id=route_db.vehicle_id,
        driver_name=route_db.driver_name or "",
        stops=stops,
        total_distance_km=route_db.total_distance_km or 0.0,
        total_duration_minutes=route_db.total_duration_minutes or 0.0,
        total_weight_kg=route_db.total_weight_kg or 0.0,
        total_items=route_db.total_items or 0,
        created_at=route_db.created_at or datetime.now(timezone.utc),
    )
