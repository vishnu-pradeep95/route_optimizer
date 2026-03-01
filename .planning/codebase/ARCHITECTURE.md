# Architecture

**Analysis Date:** 2026-03-01

## Pattern Overview

**Overall:** Layered hexagonal architecture (ports & adapters) with clear separation between business-agnostic core, database persistence, external service integrations, and application-specific implementations.

**Key Characteristics:**
- **Core-first design:** Business logic in `core/` is database-agnostic and framework-agnostic
- **Adapter pattern:** External services (VROOM, OSRM, Google Geocoding) are pluggable via interface implementations
- **Async/await throughout:** FastAPI + asyncpg for non-blocking operations
- **Repository pattern:** Clean data access layer between ORM models and domain models
- **Type safety:** Heavy use of Pydantic models for validation and FastAPI documentation

## Layers

**Domain/Business Logic (core/):**
- Purpose: Pure delivery route optimization logic, independent of any framework or database
- Location: `core/models/`, `core/optimizer/`, `core/routing/`, `core/geocoding/`, `core/data_import/`
- Contains: Pydantic models (Order, Route, Vehicle, Location), optimizer adapters, router adapters
- Depends on: httpx for external HTTP calls, pydantic for validation
- Used by: Application layer (FastAPI), tests, scripts

**Database Persistence (core/database/):**
- Purpose: SQLAlchemy ORM models, async engine/session management, and repository pattern for data access
- Location: `core/database/models.py`, `core/database/connection.py`, `core/database/repository.py`
- Contains: VehicleDB, DriverDB, OrderDB, RouteDB, RouteStopDB, TelemetryDB, GeocodeCacheDB ORM models; async engine/session factory; CRUD methods converting between Pydantic and ORM models
- Depends on: SQLAlchemy 2.0 with asyncio, GeoAlchemy2 for PostGIS geometry, asyncpg for PostgreSQL wire protocol
- Used by: Repository methods, FastAPI endpoints, optimization run persistence

**API Application Layer (apps/kerala_delivery/api/):**
- Purpose: FastAPI HTTP server exposing the optimization and telemetry workflows
- Location: `apps/kerala_delivery/api/main.py`, `apps/kerala_delivery/api/qr_helpers.py`
- Contains: FastAPI app definition, route handlers (/api/upload-orders, /api/routes, /api/telemetry, /api/vehicles), middleware (CORS, rate limiting, license enforcement), authentication (API key validation)
- Depends on: FastAPI, slowapi (rate limiting), core/ modules, core/database/
- Used by: Dashboard (React/TypeScript), driver app (PWA JavaScript), client scripts

**Business Configuration (apps/kerala_delivery/config.py):**
- Purpose: Single source of truth for Kerala LPG delivery-specific constants
- Contains: Depot location (Vatakara), fleet size (13 vehicles), cylinder weights, vehicle specs (446 kg max), safety multipliers, delivery zone radius
- Strategy: Not in core/ because another business (Mumbai food delivery) would have entirely different config
- Used by: API endpoints, optimization setup, data import

**Frontend Dashboard (apps/kerala_delivery/dashboard/):**
- Purpose: React/TypeScript web UI for operations staff
- Location: `apps/kerala_delivery/dashboard/src/`
- Contains: Pages (UploadRoutes, LiveMap, RunHistory, FleetManagement), components (VehicleList, RouteMap, StatsBar), API client, types
- Entry points: `src/App.tsx` (root component with sidebar navigation), `src/main.tsx` (React DOM mount)
- Depends on: React 18+, TypeScript, Leaflet (maps), CSS
- Does NOT depend on: Backend API at build time (only at runtime via fetch)

**Driver PWA (apps/kerala_delivery/driver_app/):**
- Purpose: Progressive Web App (PWA) for drivers in the field on mobile devices
- Location: `apps/kerala_delivery/driver_app/` (static HTML/CSS/JavaScript)
- Contains: `index.html` (single-page app with embedded styles and scripts), `manifest.json` (PWA metadata), `sw.js` (service worker for offline caching)
- Design: Dark-first UI optimized for Kerala sun readability, 48px minimum touch targets, no countdown timers (MVD compliance)
- Entry point: Opens at `/api/routes/{vehicle_id}` or standalone as installed app
- Depends on: Leaflet JS for maps, no build step (served directly)

## Data Flow

**Upload & Optimize Workflow:**

1. **User uploads CDCMS CSV** → FastAPI endpoint `POST /api/upload-orders`
2. **File parsing** → `CsvImporter` or `CdcmsPreprocessor` validates and parses rows into `Order` objects
3. **Geocoding** → For orders without GPS coords, `GoogleGeocoder` (via `GoogleGeocoder.batch()`) converts addresses to lat/lon; results cached in DB (`GeocodeCacheDB`)
4. **Fleet assembly** → `_build_fleet()` creates `Vehicle` objects from config + DB (Vatakara depot, 13 vehicles, 446 kg each)
5. **Optimization** → `VroomAdapter.optimize(orders, vehicles)` sends JSON request to VROOM Docker container on port 3000
6. **VROOM calls OSRM** → VROOM internally queries OSRM (port 5000) for travel times/distances between all stop pairs
7. **Route assignment** → VROOM returns optimized assignment: which orders assigned to which vehicle, in what sequence
8. **Persistence** → `repository.save_optimization_run()` stores in one transaction:
   - `optimization_runs` — run metadata (timestamp, source file, safety multiplier)
   - `orders` — imported orders with geocoded locations
   - `routes` — one per vehicle with total distance/duration
   - `route_stops` — ordered stops within each route (sequence 1..N, ETA, distance from previous)
9. **Response** → Returns `OptimizationSummary` with `run_id` + basic route metrics

**Telemetry Ingestion Workflow:**

1. **Driver submits GPS update** → `POST /api/telemetry` with current location, order_id, stop_status
2. **Validation** → License check (middleware), API key check, request validation
3. **Storage** → `repository.save_telemetry()` appends to `TelemetryDB` (timestamp, vehicle_id, order_id, lat/lon, status)
4. **Route status update** → Mark order as "in_transit" or "delivered" in `OrderDB`

**Driver App Data Flow:**

1. **Driver requests their route** → `GET /api/routes/{vehicle_id}` with API key
2. **Query & format** → Repository fetches all stops for that vehicle, ordered by sequence
3. **Response** → JSON with full route: depot location, stops (address, GPS, ETA, weight), total metrics
4. **Driver app renders** → List view (sequential stops) + map view (Leaflet showing all stops as markers)
5. **Driver navigates** → Clicking a stop opens Google Maps (via `GOOGLE_MAPS_MAX_WAYPOINTS` URL splitting for directions)

**Geocoding Cache:**

- **First request:** Order address not in `GeocodeCacheDB` → Query Google Geocoding API
- **Result stored:** Hash(address) → Location cached in DB with confidence score
- **Subsequent requests:** Same address hits cache instantly (no API cost)
- **Batch geocoding:** CsvImporter can pre-populate cache from historical data

## Key Abstractions

**Location:**
- Purpose: Represents a GPS point with optional address text and geocoding confidence
- File: `core/models/location.py`
- Pattern: Pydantic BaseModel with lat/lon (WGS84), address_text, geocode_confidence
- Used by: Order, Vehicle, Route, RouteStop

**Order:**
- Purpose: A single delivery task to be routed
- File: `core/models/order.py`
- Pattern: Pydantic with order_id, location (optional, filled by geocoding), address_raw, weight_kg, quantity, priority, service_time_minutes, status (Pending/Assigned/InTransit/Delivered/Failed)
- Lifecycle: Pending (imported) → Assigned (assigned to route) → InTransit (driver started) → Delivered or Failed

**Vehicle:**
- Purpose: A delivery vehicle (three-wheeler) with capacity and home location
- File: `core/models/vehicle.py`
- Pattern: Pydantic with vehicle_id, driver_name, max_weight_kg (446.0), max_items (30), depot (Location)
- Usage: Input to optimizer, represents fleet capacity constraints

**Route & RouteAssignment:**
- Purpose: Output of optimizer: ordered sequence of stops assigned to a vehicle
- File: `core/models/route.py`
- Pattern:
  - `RouteStop`: Single stop with order_id, location, sequence, ETA, distance_from_prev_km, duration_from_prev_minutes (with safety multiplier applied), weight_kg, quantity, notes, status
  - `Route`: Full route with route_id, vehicle_id, stops list, total_distance_km, total_duration_minutes, total_weight_kg
  - `RouteAssignment`: Container with list of routes (one per vehicle) + unassigned_orders (if any vehicle was over capacity)
- Unique aspect: `duration_from_prev_minutes` includes SAFETY_MULTIPLIER (1.3) applied to raw OSRM times — this is the "realistic" estimate drivers see

**Optimizer Interface:**
- Purpose: Abstract over route optimization solvers
- File: `core/optimizer/interfaces.py`
- Pattern: Protocol (structural typing) with `.optimize(orders, vehicles) -> RouteAssignment`
- Current implementation: `VroomAdapter` — HTTP client to VROOM Docker container
- Why protocols instead of ABC? Loose coupling; a new optimizer (OR-Tools, Concorde) just needs to match the signature

**Router Interface:**
- Purpose: Abstract over distance/routing services
- File: `core/routing/interfaces.py`
- Pattern: Protocol with `.get_distance_matrix(locations) -> DistanceMatrix` and `.get_travel_time(origin, dest) -> TravelTime`
- Current implementation: `OsrmAdapter` — HTTP client to OSRM Docker container with safety multiplier applied
- Distance matrix: 2D array of travel times between all location pairs

**Geocoder Interface:**
- Purpose: Abstract over geocoding providers
- File: `core/geocoding/interfaces.py`
- Pattern: Protocol with `.geocode(address) -> GeocodingResult` and `.batch(addresses) -> list[GeocodingResult]`
- Current implementation: `GoogleGeocoder` with local file-based cache
- Cache: `GeocodingCache` wraps the geocoder and stores results in `GeocodeCacheDB` to avoid API calls

**Repository Pattern:**
- Purpose: Isolate persistence logic from business logic
- File: `core/database/repository.py`
- Pattern: Module with async functions like `save_optimization_run()`, `get_route_by_vehicle_id()`, `save_telemetry()`, etc.
- Conversion logic: `_point_to_location()` (PostGIS geometry → Pydantic Location), `_make_point()` (Location → PostGIS)

## Entry Points

**FastAPI Application:**
- Location: `apps/kerala_delivery/api/main.py` (creates FastAPI app in lifespan context manager)
- Triggers: Command `uvicorn apps.kerala_delivery.api.main:app --reload` (dev) or Docker entry point (prod)
- Responsibilities:
  - Middleware: CORS, rate limiting (slowapi), license enforcement (checks license.dat existence)
  - Routes: POST /api/upload-orders, GET /api/routes/{vehicle_id}, POST /api/telemetry, GET /api/vehicles, PUT/DELETE vehicles, etc.
  - Dependency injection: Verify API key, get AsyncSession for DB access
  - Static files: Mounts `/api/routes/{vehicle_id}` to serve driver PWA (index.html)

**Dashboard React App:**
- Location: `apps/kerala_delivery/dashboard/src/main.tsx`
- Triggers: `npm run dev` (Vite dev server) or `npm run build` (static files to dist/)
- Entry component: `App.tsx` — manages page state (upload, live-map, run-history, fleet), polls API health every 30s
- Pages: UploadRoutes (file upload), LiveMap (Leaflet map showing all vehicles), RunHistory (list of optimization runs), FleetManagement (CRUD vehicles)

**Driver PWA:**
- Location: `apps/kerala_delivery/driver_app/index.html`
- Triggers: Driver opens mobile browser to URL `/api/routes/{vehicle_id}` or installs PWA from home screen
- Behavior: Single HTML file served with `Content-Type: text/html` by FastAPI, contains all CSS and JavaScript inline
- Key functions: List view (stops in sequence), map view (Leaflet), Google Maps navigation (splits route into segments due to GOOGLE_MAPS_MAX_WAYPOINTS=25)

**Data Import Scripts:**
- Location: `scripts/import_orders.py` (imports CSV), `scripts/geocode_batch.py` (pre-geocodes addresses), `scripts/compare_routes.py` (debugging)
- Usage: `python scripts/import_orders.py data/orders.csv` (standalone data prep before API upload)

## Error Handling

**Strategy:** Validation early, errors as structured responses, logging for debugging.

**Patterns:**
- **Validation:** Pydantic models validate on construction (type, range, required fields); raises `ValidationError` if invalid
- **HTTP Errors:** FastAPI endpoints raise `HTTPException(status_code, detail)` for user-facing errors (400 bad request, 401 unauthorized, 422 validation failed)
- **External service failures:** If VROOM/OSRM/Google Geocoding fails, catch `httpx.HTTPError` or JSON decode errors, log context, return 500 with generic "Service unavailable" message (no internal details to frontend)
- **Database errors:** AsyncSession transaction auto-rolls back on error; endpoint returns 500
- **License enforcement:** Middleware checks license.dat; if missing or expired, returns 403 Forbidden with custom error detail

**Example (from upload endpoint):**
```python
try:
    # parse CSV
    importer = CsvImporter(...)
    orders = importer.parse()  # Raises ValidationError if bad data
except Exception as e:
    logger.error(f"CSV parse failed: {e}")
    raise HTTPException(status_code=400, detail="Invalid CSV format")

try:
    # geocode
    geocoded = geocoder.batch(addresses)
except httpx.HTTPError as e:
    logger.error(f"Geocoding API failed: {e}")
    raise HTTPException(status_code=503, detail="Geocoding service unavailable")

try:
    # optimize
    assignment = optimizer.optimize(orders, vehicles)
except Exception as e:
    logger.error(f"Optimizer failed: {e}")
    raise HTTPException(status_code=500, detail="Optimization failed")
```

## Cross-Cutting Concerns

**Logging:**
- Framework: Python `logging` module with logger names matching module path (e.g., `logger = logging.getLogger(__name__)`)
- Level: DEBUG for detailed flow, INFO for milestones, WARNING for unusual (retry-able), ERROR for failures
- Destinations: Console (stderr in containers) — no local file logging in production (Docker logs via stdout)
- Example: `logger.info(f"Optimizing {len(orders)} orders for {len(vehicles)} vehicles")`

**Authentication:**
- Method: API key in `X-API-Key` header (timing-safe comparison via `hmac.compare_digest()`)
- Enforcement: `verify_api_key()` and `verify_read_key()` dependencies injected into endpoint signatures
- Environment: `API_KEY` env var (required for write operations, optional for read)
- Fallback: If `API_KEY` not set, no authentication enforced (useful for development)

**Rate Limiting:**
- Framework: slowapi with `Limiter.limit()` decorator
- Strategy: Per-IP rate limit (5 requests/minute for upload-orders, higher for status endpoints)
- Enforcement: Returns 429 Too Many Requests if exceeded
- Bypass: Requests from localhost (127.0.0.1) not rate-limited

**PostGIS Spatial Queries:**
- Coordinate system: SRID 4326 (WGS84), stored as (longitude, latitude) in database
- Client-side model: Pydantic Location stores (latitude, longitude) — human-friendly
- Conversion: `_make_point()` flips to (lon, lat), `_point_to_location()` flips back
- Why GeoAlchemy2? Handles WKB encoding/decoding; enables distance queries (ST_DistanceSphere) and bounding-box filters (ST_DWithin)

**Safety Multiplier:**
- Purpose: Account for real-world delays (Kerala narrow roads, three-wheeler speeds, traffic) on top of OSRM's optimistic estimates
- Value: 1.3 (30% buffer) — stored in config and applied in:
  - `OsrmAdapter.get_travel_time()`: Multiplies OSRM duration before returning
  - Route output: `route_stop.duration_from_prev_minutes` is the multiplied value (what drivers see and plan around)
- Rationale: OSRM assumes ideal highway speeds; three-wheelers max 40 km/h in urban areas; Kerala has narrow roads and traffic

---

*Architecture analysis: 2026-03-01*
