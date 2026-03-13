# Architecture Research: v3.0 Driver-Centric Model Integration

**Domain:** Driver-centric route optimization for Kerala LPG delivery
**Researched:** 2026-03-12
**Confidence:** HIGH (all integration points traced through source code, VROOM TSP capability verified, Google Routes API pricing researched)

## Executive Summary

The v3.0 milestone replaces the vehicle-fleet mental model with a driver-centric model. Today, the system creates 13 predefined vehicles in `init.sql`, optimizes across all of them via VROOM CVRP, and routes are identified by `vehicle_id` (VEH-01 through VEH-13). The target state: drivers are first-class entities created from CDCMS CSV uploads, each driver gets their pre-assigned orders optimized as a single-vehicle TSP, and the dashboard becomes the primary management interface.

This is a conceptual rename with significant data flow changes, NOT a schema rewrite. The existing `vehicles` table, `routes` table structure, and `route_stops` ordering all remain valid. The changes center on: (1) promoting `DriverDB` to a working entity with auto-creation from CSV, (2) changing the optimization from fleet-wide CVRP to per-driver TSP, (3) adding dashboard settings/management pages, and (4) adding Google Maps route validation as a confidence comparison.

---

## Current System Data Flow (Before Changes)

```
CURRENT UPLOAD-TO-ROUTE PIPELINE
==================================

1. Employee uploads CDCMS CSV
   |
   v
2. api/main.py :: upload_and_optimize()
   |-- _is_cdcms_format() detects CDCMS tab-separated format
   |-- preprocess_cdcms() extracts: order_id, address, quantity, area_name, delivery_man
   |     NOTE: delivery_man column is PRESERVED in DataFrame but NEVER USED for routing
   |-- CsvImporter.import_orders() creates Order objects
   |
   v
3. Geocoding loop
   |-- CachedGeocoder.geocode() for each un-geocoded order
   |-- GeocodeValidator validates against 30km zone
   |
   v
4. Fleet assembly
   |-- repo.get_active_vehicles(session) -> 13 VehicleDB rows from DB
   |-- vehicle_db_to_pydantic() converts each to Pydantic Vehicle
   |-- All 13 vehicles participate in optimization regardless of CSV content
   |
   v
5. VROOM optimization (CVRP -- Capacitated Vehicle Routing Problem)
   |-- VroomAdapter._build_request(): ALL orders + ALL 13 vehicles
   |-- VROOM decides: which orders go to which vehicle, in what sequence
   |-- VROOM may leave some vehicles empty if not needed
   |-- Result: RouteAssignment with routes per vehicle
   |
   v
6. Persistence
   |-- save_optimization_run(): optimization_runs + orders + routes + route_stops
   |-- routes.vehicle_id = "VEH-01" through "VEH-13"
   |-- routes.driver_name = vehicle.driver_name (empty string from DB)
   |
   v
7. Driver access
   |-- GET /api/routes/VEH-01 -> driver's route
   |-- Driver PWA identifies by vehicle_id, not driver name
```

### Key Problem

The CDCMS CSV already has a `DeliveryMan` column that pre-assigns orders to specific drivers. The current system **ignores this assignment** and re-assigns all orders across all 13 vehicles via CVRP. This conflicts with the real-world workflow where the office has already decided which driver handles which orders.

---

## Target Architecture (After Changes)

```
TARGET UPLOAD-TO-ROUTE PIPELINE (v3.0)
========================================

1. Employee uploads CDCMS CSV
   |
   v
2. api/main.py :: upload_and_optimize()
   |-- preprocess_cdcms() extracts delivery_man column (ALREADY EXTRACTED)
   |-- Build driver_orders_map: {driver_name -> [order_ids]}
   |
   v
3. Driver resolution
   |-- For each unique delivery_man in CSV:
   |     a. Look up DriverDB by name (case-insensitive)
   |     b. If not found: auto-create DriverDB with name from CSV
   |     c. Associate driver -> vehicle (round-robin or manual assignment)
   |-- Result: driver_vehicle_map: {driver_name -> vehicle_id}
   |
   v
4. Geocoding loop (UNCHANGED)
   |
   v
5. Per-driver TSP optimization
   |-- For each driver:
   |     a. Filter orders assigned to this driver
   |     b. Create single VROOM vehicle for this driver's assigned vehicle
   |     c. VroomAdapter.optimize([driver_orders], [single_vehicle])
   |     d. VROOM solves TSP: optimal sequence for this driver's stops
   |-- Result: list of RouteAssignment (one per driver)
   |
   v
6. Persistence (MODIFIED)
   |-- save_optimization_run(): single run, multiple routes
   |-- routes.vehicle_id = driver's assigned vehicle_id
   |-- routes.driver_name = driver's name from CSV
   |
   v
7. Driver access (MODIFIED)
   |-- GET /api/routes/{driver_name_or_vehicle_id} -> driver's route
   |-- Dashboard shows driver names, not vehicle IDs
```

---

## New Components

### 1. Driver Management Service (in `core/database/repository.py`)

**Responsibility:** CRUD operations for drivers with auto-creation from CSV uploads.

**Why extend repository.py instead of a new module:**
- The repository already manages all other entities (vehicles, orders, routes, telemetry, geocode cache)
- Driver operations are simple CRUD with one unique pattern (find-or-create)
- A separate `driver_service.py` would add indirection without adding value at this scale

**New repository functions:**

```python
async def get_driver_by_name(session: AsyncSession, name: str) -> DriverDB | None:
    """Case-insensitive driver lookup by name."""

async def get_or_create_driver(session: AsyncSession, name: str) -> DriverDB:
    """Find existing driver or create new one. Idempotent.
    Used during CSV upload to auto-create drivers from DeliveryMan column."""

async def get_active_drivers(session: AsyncSession) -> list[DriverDB]:
    """Get all active drivers for dashboard display."""

async def update_driver(session: AsyncSession, driver_id: uuid.UUID, updates: dict) -> bool:
    """Update driver fields (name, phone, vehicle assignment, active status)."""

async def assign_driver_to_vehicle(
    session: AsyncSession, driver_id: uuid.UUID, vehicle_id: uuid.UUID
) -> bool:
    """Assign a driver to a specific vehicle."""
```

**Integration point:** Called from `upload_and_optimize()` after CSV parsing, before optimization.

### 2. Per-Driver TSP Optimizer Wrapper (in `apps/kerala_delivery/api/main.py`)

**Responsibility:** Split orders by driver, run VROOM TSP for each driver separately, combine results.

**Why in main.py instead of a new module:**
- This is orchestration logic specific to the Kerala delivery workflow
- The VroomAdapter itself stays generic (it already handles 1 vehicle = TSP)
- Moving orchestration to a separate module would mean passing many dependencies (session, geocoder, validator) through yet another layer

**Pseudocode:**

```python
async def optimize_per_driver(
    orders: list[Order],
    driver_orders_map: dict[str, list[str]],  # driver_name -> [order_ids]
    driver_vehicle_map: dict[str, Vehicle],     # driver_name -> Vehicle
    optimizer: VroomAdapter,
) -> RouteAssignment:
    """Run per-driver TSP optimization and combine into single RouteAssignment."""
    all_routes: list[Route] = []
    all_unassigned: list[str] = []

    for driver_name, order_ids in driver_orders_map.items():
        driver_orders = [o for o in orders if o.order_id in order_ids]
        vehicle = driver_vehicle_map[driver_name]

        if not driver_orders:
            continue

        # VROOM with 1 vehicle = TSP (optimal stop sequence)
        assignment = optimizer.optimize(driver_orders, [vehicle])

        for route in assignment.routes:
            route.driver_name = driver_name
            all_routes.append(route)

        all_unassigned.extend(assignment.unassigned_order_ids)

    return RouteAssignment(
        assignment_id=str(uuid.uuid4())[:8],
        routes=all_routes,
        unassigned_order_ids=all_unassigned,
        optimization_time_ms=total_time,
    )
```

**VROOM TSP behavior:** When VROOM receives 1 vehicle + N jobs, it solves a TSP -- finding the optimal visit order that minimizes total travel time. This is confirmed by VROOM documentation: "VROOM solves several well-known types of vehicle routing problems including the Travelling Salesman Problem." No special configuration needed; 1 vehicle = TSP automatically.

### 3. Google Maps Route Validation Service (NEW: `core/routing/gmaps_validator.py`)

**Responsibility:** Compare OSRM-based route distance/duration against Google Maps Directions API (now Routes API) for confidence scoring.

**Why in core/routing/ (not apps/):**
- Route validation is a generic routing concept, not Kerala-specific
- The RoutingEngine protocol in `core/routing/interfaces.py` already defines the routing abstraction boundary
- Could be reused by any deployment that wants Google validation

**Component Boundary:**

| Aspect | Detail |
|--------|--------|
| Input | Ordered list of waypoints (depot + stops as lat/lon) |
| Output | `RouteValidation` with Google distance_km, duration_min, comparison delta |
| Dependencies | `httpx` for Google Routes API HTTP calls |
| Configuration | Google Maps API key (already available via `GOOGLE_MAPS_API_KEY` env var) |
| Cost | ~$5 per 1000 Basic requests (< 11 waypoints), $10 per 1000 Advanced (11-25 waypoints) |
| Limit | 25 intermediate waypoints per request (matching existing QR segment splitting logic) |

**Interface:**

```python
@dataclass
class RouteValidation:
    google_distance_km: float
    google_duration_minutes: float
    osrm_distance_km: float
    osrm_duration_minutes: float
    distance_delta_pct: float    # (google - osrm) / osrm * 100
    duration_delta_pct: float
    confidence: str              # "high" if delta < 15%, "medium" < 30%, "low" >= 30%

class GoogleMapsRouteValidator:
    def __init__(self, api_key: str):
        """Initialize with Google Maps API key."""

    def validate_route(
        self, waypoints: list[Location], osrm_distance_km: float, osrm_duration_min: float
    ) -> RouteValidation:
        """Call Google Routes API computeRoutes and compare with OSRM estimates."""
```

**API choice:** Use Google Routes API (computeRoutes) NOT the legacy Directions API. The Directions API is deprecated. Routes API supports up to 25 intermediate waypoints per request at the Essentials tier ($5/1000 requests for Basic, no traffic awareness needed for validation).

**Integration point:** Called optionally after VROOM optimization, before persistence. Dashboard displays the comparison. NOT used for routing decisions -- purely informational for office staff confidence.

### 4. Dashboard Settings Page (NEW: `apps/kerala_delivery/dashboard/src/pages/Settings.tsx`)

**Responsibility:** Admin interface for API key configuration, geocode cache management, and upload history.

**Sub-sections:**

| Section | Data Source | Operations |
|---------|------------|------------|
| API Key Config | `/api/config` + new PUT endpoint | View masked key, test connectivity, update |
| Geocode Cache Stats | New `GET /api/geocode-cache/stats` | View hit rate, entry count, top addresses, estimated savings |
| Upload History | Existing `GET /api/runs` enhanced | View past uploads with filename, date, order count, driver breakdown |
| Driver Management | New `GET /api/drivers`, `POST /api/drivers` | List drivers, edit, assign to vehicles, deactivate |

---

## Modified Components

### 1. `core/database/models.py` -- DriverDB Enhancement

**Current state:** `DriverDB` exists but is minimal (name, phone, vehicle_id FK, is_active). It has never been used in the upload-optimize pipeline.

**Changes needed:**

```python
class DriverDB(Base):
    __tablename__ = "drivers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(100), nullable=False)  # NEW: lowercase for lookup
    phone: Mapped[str | None] = mapped_column(String(20))
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(30), default="csv")  # NEW: "csv", "manual"
    last_seen_at: Mapped[datetime | None] = mapped_column(  # NEW: last CSV upload with this driver
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_drivers_name_normalized", "name_normalized"),  # NEW: fast lookup
    )

    vehicle: Mapped[VehicleDB | None] = relationship(back_populates="drivers")
```

**New columns:**
- `name_normalized`: Lowercase, stripped name for case-insensitive matching. CDCMS names can be "SURESH KUMAR", "Suresh Kumar", or "SURESHKUMAR". Normalizing prevents duplicate driver creation.
- `source`: Track how the driver was created ("csv" for auto-creation, "manual" for dashboard-created).
- `last_seen_at`: Updated on each CSV upload. Helps identify inactive drivers who no longer appear in CDCMS exports.

**Migration:** Alembic migration adds `name_normalized`, `source`, `last_seen_at` columns with defaults. Backfills `name_normalized` from existing `name` values.

### 2. `infra/postgres/init.sql` -- Driver Seed Data

**Current state:** Seeds 13 vehicles. No driver seed data.

**Change:** Add index on `drivers.name_normalized`. No seed data for drivers -- they are auto-created from CSV.

```sql
CREATE INDEX IF NOT EXISTS idx_drivers_name_normalized ON drivers(name_normalized);
```

### 3. `core/data_import/cdcms_preprocessor.py` -- Expose Driver Assignment

**Current state:** `preprocess_cdcms()` already extracts `delivery_man` column into the DataFrame. It is preserved in the output but never consumed by the optimization pipeline.

**Change:** No code change needed in the preprocessor itself. The `delivery_man` column is already available. The change is in how `upload_and_optimize()` consumes it.

### 4. `apps/kerala_delivery/api/main.py` -- Major Pipeline Change

This is the largest modification. The `upload_and_optimize()` endpoint changes from fleet-wide CVRP to per-driver TSP.

**Changes in order:**

#### 4a. After CSV parsing, build driver-to-orders mapping

```python
# After import_result = importer.import_orders(...)
# and after orders list is populated:

# Build driver -> order mapping from preprocessed DataFrame
driver_orders_map: dict[str, list[str]] = {}
if is_cdcms and not preprocessed_df.empty:
    for _, row in preprocessed_df.iterrows():
        driver = str(row.get("delivery_man", "")).strip()
        order_id = str(row.get("order_id", "")).strip()
        if driver and order_id:
            driver_orders_map.setdefault(driver, []).append(order_id)
```

#### 4b. After geocoding, resolve drivers and run per-driver TSP

```python
# Resolve drivers (find-or-create in DB)
driver_vehicle_map: dict[str, Vehicle] = {}
for driver_name in driver_orders_map:
    driver_db = await repo.get_or_create_driver(session, driver_name)
    if driver_db.vehicle_id:
        vehicle_db = await session.get(VehicleDB, driver_db.vehicle_id)
        vehicle = repo.vehicle_db_to_pydantic(vehicle_db)
    else:
        # Auto-assign to next available vehicle (round-robin or first available)
        vehicle = fleet[len(driver_vehicle_map) % len(fleet)]
    driver_vehicle_map[driver_name] = vehicle

# Per-driver TSP optimization
if driver_orders_map:
    assignment = await optimize_per_driver(
        geocoded_orders, driver_orders_map, driver_vehicle_map, optimizer
    )
else:
    # Fallback: no driver column in CSV -> fleet-wide CVRP (backward compatible)
    assignment = optimizer.optimize(geocoded_orders, fleet)
```

#### 4c. New API endpoints

```python
# Driver management
GET  /api/drivers                    # List all drivers
POST /api/drivers                    # Create driver manually
PUT  /api/drivers/{driver_id}        # Update driver (name, phone, vehicle)
DELETE /api/drivers/{driver_id}      # Deactivate driver

# Geocode cache management
GET  /api/geocode-cache/stats        # Cache hit rate, entry count, cost savings
POST /api/geocode-cache/clear        # Clear cache (admin operation)

# Route validation
GET  /api/routes/{vehicle_id}/validate   # Compare OSRM vs Google for this route

# Settings
GET  /api/settings                   # Current settings (masked API key, cache stats)
PUT  /api/settings                   # Update settings (API key)
```

### 5. `apps/kerala_delivery/dashboard/src/types.ts` -- New TypeScript Types

```typescript
// Driver types
export interface Driver {
  id: string;
  name: string;
  phone: string | null;
  vehicle_id: string | null;
  is_active: boolean;
  source: "csv" | "manual";
  last_seen_at: string | null;
  created_at: string;
}

export interface DriversResponse {
  count: number;
  drivers: Driver[];
}

// Route validation types
export interface RouteValidation {
  google_distance_km: number;
  google_duration_minutes: number;
  osrm_distance_km: number;
  osrm_duration_minutes: number;
  distance_delta_pct: number;
  duration_delta_pct: number;
  confidence: "high" | "medium" | "low";
}

// Geocode cache stats
export interface GeocodeCacheStats {
  total_entries: number;
  google_entries: number;
  driver_verified_entries: number;
  total_hits: number;
  estimated_savings_usd: number;
  top_addresses: { address: string; hit_count: number }[];
}
```

### 6. `apps/kerala_delivery/dashboard/src/App.tsx` -- New Navigation Item

Add "Settings" page to the sidebar navigation:

```typescript
const NAV_ITEMS = [
  { page: "upload", icon: Upload, label: "Upload & Routes" },
  { page: "live-map", icon: Map, label: "Live Map" },
  { page: "run-history", icon: ClipboardList, label: "Run History" },
  { page: "fleet", icon: Truck, label: "Fleet" },
  { page: "settings", icon: Settings, label: "Settings" },  // NEW
];
```

### 7. `apps/kerala_delivery/dashboard/src/pages/UploadRoutes.tsx` -- Driver Selection UI

**Current state:** Employee uploads CSV, system optimizes across all vehicles, shows route cards per vehicle.

**Target state:** After CSV upload and before optimization, show a driver selection/confirmation step:

1. Parse CSV and extract unique driver names from `DeliveryMan` column
2. Display driver list with order counts: "SURESH (12 orders), RAJESH (8 orders), ..."
3. Allow selecting/deselecting drivers to include
4. "Optimize" button triggers per-driver TSP
5. Route cards show driver names instead of vehicle IDs

This is a UI flow change, not a separate component. The existing `UploadRoutes.tsx` gains a new intermediate state between "file uploaded" and "routes generated".

### 8. Route Response Format -- Vehicle ID vs Driver Name

**Current API responses** use `vehicle_id` as the primary identifier:
- `GET /api/routes/VEH-01` to fetch a specific route
- Response: `{"vehicle_id": "VEH-01", "driver_name": ""}`

**Target state:** Support both vehicle_id and driver name as route lookup keys. The existing `vehicle_id` field in `RouteDB` remains the DB storage format. A new lookup path resolves driver name to vehicle_id:

```python
@app.get("/api/routes/{identifier}")
async def get_driver_route(identifier: str, session: AsyncSession = SessionDep):
    """Get route by vehicle_id OR driver name."""
    # Try vehicle_id first (backward compatible)
    route_db = await repo.get_route_for_vehicle(session, run.id, identifier)
    if not route_db:
        # Try driver name lookup
        route_db = await repo.get_route_by_driver_name(session, run.id, identifier)
    if not route_db:
        raise HTTPException(404, ...)
```

---

## Unchanged Components

| Component | Why No Change |
|-----------|--------------|
| `core/optimizer/vroom_adapter.py` | Already handles 1 vehicle = TSP. No code change needed -- the orchestration layer decides how many vehicles to pass. |
| `core/optimizer/interfaces.py` | `RouteOptimizer.optimize(orders, vehicles)` protocol works for both CVRP (N vehicles) and TSP (1 vehicle). |
| `core/models/order.py` | Order model is driver-agnostic. Orders don't know which driver they belong to -- that's a routing decision. |
| `core/models/vehicle.py` | Vehicle model unchanged. The driver_name field already exists. |
| `core/models/route.py` | Route and RouteStop models already have `driver_name` field. |
| `core/geocoding/` (all) | Geocoding is independent of driver assignment. No changes. |
| `core/data_import/csv_importer.py` | Generic importer. CDCMS-specific driver extraction stays in preprocessor. |
| `core/routing/osrm_adapter.py` | OSRM provides travel times. Unrelated to driver assignment. |
| `apps/kerala_delivery/driver_app/` | Driver PWA fetches route by vehicle_id. It will continue to work -- the route lookup just adds driver name as an alternative key. |
| `core/database/connection.py` | Async engine and session factory unchanged. |
| `core/licensing/` | License management unrelated to driver features. |

---

## Database Schema Changes

### New Migration: Add Driver Management Columns

```sql
-- Alembic migration: add driver management columns
ALTER TABLE drivers ADD COLUMN IF NOT EXISTS name_normalized VARCHAR(100);
ALTER TABLE drivers ADD COLUMN IF NOT EXISTS source VARCHAR(30) DEFAULT 'manual';
ALTER TABLE drivers ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;

-- Backfill normalized names from existing data
UPDATE drivers SET name_normalized = LOWER(TRIM(name)) WHERE name_normalized IS NULL;

-- Make name_normalized NOT NULL after backfill
ALTER TABLE drivers ALTER COLUMN name_normalized SET NOT NULL;

-- Index for fast driver lookup during CSV upload
CREATE INDEX IF NOT EXISTS idx_drivers_name_normalized ON drivers(name_normalized);

-- Unique constraint to prevent duplicate drivers
ALTER TABLE drivers ADD CONSTRAINT uq_drivers_name_normalized UNIQUE (name_normalized);
```

### New Migration: Routes Table Driver Lookup

```sql
-- Index for looking up routes by driver_name (new lookup path)
CREATE INDEX IF NOT EXISTS idx_routes_driver_name ON routes(driver_name);
```

### No Changes to These Tables

| Table | Reason |
|-------|--------|
| `vehicles` | Still the physical fleet. Drivers are assigned to vehicles, not the reverse. |
| `orders` | Orders are driver-agnostic at the DB level. Driver assignment is via routes. |
| `route_stops` | Stops belong to routes. Driver info is on the route, not the stop. |
| `optimization_runs` | Already tracks vehicles_used. Could add drivers_used but not essential. |
| `telemetry` | Already has `vehicle_id` and `driver_name` fields. No schema change. |
| `geocode_cache` | Completely independent of driver management. |

---

## Data Flow Changes (Detailed)

### Change 1: CSV Upload Extracts Driver Assignment

```
BEFORE:
  CDCMS CSV -> preprocess_cdcms() -> DataFrame with delivery_man column -> IGNORED

AFTER:
  CDCMS CSV -> preprocess_cdcms() -> DataFrame with delivery_man column
    -> Build driver_orders_map: {"SURESH": ["ORD-001", "ORD-003", ...]}
    -> For each driver: get_or_create_driver(session, name)
    -> Assign drivers to vehicles (round-robin or manual mapping)
```

### Change 2: Optimization Strategy Changes

```
BEFORE (CVRP):
  All 40 orders + All 13 vehicles -> VROOM -> Assigns orders to vehicles

AFTER (Per-driver TSP):
  SURESH's 12 orders + 1 vehicle -> VROOM -> Optimal sequence for SURESH
  RAJESH's 8 orders + 1 vehicle -> VROOM -> Optimal sequence for RAJESH
  KUMAR's 10 orders + 1 vehicle -> VROOM -> Optimal sequence for KUMAR
  ... (one VROOM call per driver)
  -> Combine into single RouteAssignment
```

**Performance note:** Multiple VROOM calls (one per driver) is slightly more overhead than a single call, but VROOM solves TSP for 30 stops in < 10ms. With 13 drivers, total optimization time is still < 200ms. Negligible compared to geocoding (which takes seconds per address).

### Change 3: Route Lookup Supports Driver Name

```
BEFORE:
  GET /api/routes/VEH-01  -> route for vehicle VEH-01

AFTER:
  GET /api/routes/VEH-01  -> route for vehicle VEH-01 (backward compatible)
  GET /api/routes/SURESH   -> route for driver SURESH (new)
  GET /api/routes?driver_name=SURESH  -> alternative query param syntax
```

### Change 4: Dashboard Shows Drivers, Not Vehicles

```
BEFORE:
  Route cards: "VEH-01 | 8 stops | 23.4 km"

AFTER:
  Route cards: "Suresh Kumar | VEH-03 | 8 stops | 23.4 km"
  Driver selection step before optimization
  Settings page with cache stats and driver management
```

### Change 5: Google Maps Route Validation (New Data Flow)

```
After VROOM optimization (optional, triggered from dashboard):
  1. Take VROOM's optimized stop sequence for a driver
  2. Build waypoint list: depot -> stop1 -> stop2 -> ... -> depot
  3. Call Google Routes API computeRoutes with waypoints (no optimization)
  4. Compare:
     - OSRM distance (from VROOM) vs Google distance
     - OSRM duration * safety_multiplier vs Google duration
  5. Display delta on dashboard route card:
     "OSRM: 23.4 km / Google: 24.1 km (+3%)"
  6. High confidence (< 15% delta) = green badge
     Medium (15-30%) = amber badge
     Low (> 30%) = red badge -- investigate OSRM data quality
```

---

## Dependency Graph (Build Order)

```
Phase 1: Driver DB Foundation (no external dependencies)
  |-- 1.1: Alembic migration for DriverDB columns (name_normalized, source, last_seen_at)
  |-- 1.2: Repository functions (get_or_create_driver, get_active_drivers, etc.)
  |-- 1.3: API endpoints for driver CRUD (GET/POST/PUT/DELETE /api/drivers)
  |-- 1.4: Unit tests for driver repository and API
  |
Phase 2: Per-Driver TSP Optimization (depends on Phase 1)
  |-- 2.1: Build driver_orders_map from CDCMS delivery_man column
  |-- 2.2: Driver-to-vehicle assignment logic (round-robin default)
  |-- 2.3: Per-driver TSP wrapper calling VroomAdapter with 1 vehicle
  |-- 2.4: Fallback to fleet-wide CVRP for non-CDCMS uploads
  |-- 2.5: Update save_optimization_run to persist driver_name correctly
  |-- 2.6: Unit + integration tests
  |
Phase 3: CSV Upload Flow Improvements (parallel with Phase 2)
  |-- 3.1: CDCMS .xlsx detection fixes (already in scope)
  |-- 3.2: Address garbling fixes in preprocessor
  |-- 3.3: Multi-format support (tab-sep, comma-sep, Excel)
  |-- 3.4: Tests
  |
Phase 4: Dashboard Driver UI (depends on Phase 1 + 2)
  |-- 4.1: Driver selection step in UploadRoutes.tsx
  |-- 4.2: Route cards show driver names
  |-- 4.3: Driver management section (list, edit, assign vehicles)
  |-- 4.4: TypeScript types for new API responses
  |
Phase 5: Google Maps Route Validation (depends on Phase 2)
  |-- 5.1: GoogleMapsRouteValidator in core/routing/
  |-- 5.2: GET /api/routes/{id}/validate endpoint
  |-- 5.3: Dashboard validation badge on route cards
  |-- 5.4: Tests (mock Google API)
  |
Phase 6: Dashboard Settings & Cache Management (parallel with Phase 5)
  |-- 6.1: GET /api/geocode-cache/stats endpoint
  |-- 6.2: Settings page (API key, cache stats, upload history)
  |-- 6.3: Geocode zone radius tightening (30km -> 20km)
  |
Phase 7: Integration Testing (depends on all above)
  |-- 7.1: Full pipeline test with real CDCMS export
  |-- 7.2: Driver auto-creation and vehicle assignment verification
  |-- 7.3: Per-driver TSP vs fleet CVRP comparison
  |-- 7.4: E2E Playwright tests for new dashboard flows
```

### Build Order Rationale

- **Phase 1 first** because driver DB is the foundation everything else depends on. Auto-creation from CSV is the critical path for the entire milestone.
- **Phase 2 depends on Phase 1** because per-driver TSP requires resolved driver entities with vehicle assignments.
- **Phase 3 parallel with Phase 2** because CSV improvements (xlsx detection, address fixes) are independent of the optimization strategy change. They improve the input quality for both old and new flows.
- **Phase 4 depends on Phases 1+2** because the dashboard driver UI needs working API endpoints for drivers and per-driver routes.
- **Phase 5 depends on Phase 2** because route validation compares VROOM output against Google, so optimization must be working first.
- **Phase 6 parallel with Phase 5** because settings/cache management are independent of route validation.
- **Phase 7 last** because it tests the assembled system end-to-end.

---

## API Endpoint Summary

### New Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/drivers` | Read key | List all drivers |
| POST | `/api/drivers` | Write key | Create driver manually |
| PUT | `/api/drivers/{id}` | Write key | Update driver (name, phone, vehicle) |
| DELETE | `/api/drivers/{id}` | Write key | Deactivate driver |
| GET | `/api/geocode-cache/stats` | Read key | Cache performance metrics |
| POST | `/api/geocode-cache/clear` | Write key | Clear cache (admin) |
| GET | `/api/routes/{id}/validate` | Read key | Google Maps route validation |
| GET | `/api/settings` | Read key | Current settings |
| PUT | `/api/settings` | Write key | Update settings |

### Modified Endpoints

| Method | Path | Change |
|--------|------|--------|
| POST | `/api/upload-orders` | Add driver extraction, per-driver TSP, driver auto-creation |
| GET | `/api/routes` | Include driver_name in response, support driver lookup |
| GET | `/api/routes/{identifier}` | Accept both vehicle_id and driver name |

### Unchanged Endpoints

All other endpoints (telemetry, vehicles, health, config, QR sheet) remain unchanged. The vehicle CRUD endpoints stay for fleet management -- vehicles are physical assets, drivers are the people who use them.

---

## Scalability Considerations

| Concern | At 13 drivers (current) | At 50 drivers | At 200 drivers |
|---------|------------------------|---------------|----------------|
| VROOM calls per upload | 13 TSP calls, ~130ms total | 50 calls, ~500ms | 200 calls, ~2s (still acceptable) |
| Driver DB lookups | 13 get_or_create calls | 50 calls, ~50ms | Consider batch upsert |
| Google validation calls | 13 Routes API calls, ~$0.065 | 50 calls, ~$0.25 | $1/upload, may need caching |
| Dashboard rendering | 13 route cards | 50 cards, pagination needed | Virtual scroll + search filter |

At the current scale of 13 drivers and 40-50 orders/day, all concerns are negligible. The per-driver TSP approach is actually faster than fleet-wide CVRP because each individual TSP solve is simpler (fewer stops per vehicle).

---

## Integration Risk Assessment

| Integration Point | Risk | What Could Go Wrong | Mitigation |
|-------------------|------|---------------------|------------|
| Driver auto-creation from CSV | Medium | CDCMS name variations create duplicates ("SURESH K" vs "SURESH KUMAR") | Normalize names aggressively (lowercase, strip, collapse spaces). Add fuzzy matching if needed later. |
| Per-driver TSP replacing CVRP | Medium | Non-CDCMS uploads have no delivery_man column | Fallback to fleet-wide CVRP when no driver mapping available. Feature flag for gradual rollout. |
| Vehicle assignment for new drivers | Low | More drivers than vehicles (13) | Round-robin assignment with clear warning in dashboard. Long-term: decouple driver from vehicle. |
| Route lookup by driver name | Low | Name collisions (two drivers named "SURESH") | Use normalized name + run_id for disambiguation. Dashboard shows full name with vehicle. |
| Google Routes API cost | Low | Validation adds API cost per upload | Make validation opt-in (button click, not automatic). Cache validation results. |
| Dashboard driver selection UI | Medium | Complex state management for upload flow | Keep it simple: show checkboxes, not drag-and-drop. Use existing DaisyUI components. |
| Backward compatibility | Low | Driver PWA uses vehicle_id for route fetch | Vehicle_id lookup remains primary. Driver name is additive path. |

---

## Sources

- VROOM API documentation: [GitHub VROOM-Project/vroom docs/API.md](https://github.com/VROOM-Project/vroom/blob/master/docs/API.md) -- confirms TSP behavior with 1 vehicle
- Google Routes API: [Routes API Usage and Billing](https://developers.google.com/maps/documentation/routes/usage-and-billing) -- pricing tiers, 25 waypoint limit
- Google Routes API overview: [Compute Routes Overview](https://developers.google.com/maps/documentation/routes/overview/) -- computeRoutes endpoint specification
- Existing codebase analysis: `.planning/codebase/ARCHITECTURE.md` -- system layer analysis (2026-03-01)
- Source code traced: `core/database/models.py` (DriverDB schema), `core/database/repository.py` (all CRUD patterns), `core/optimizer/vroom_adapter.py` (request building), `core/data_import/cdcms_preprocessor.py` (delivery_man extraction), `apps/kerala_delivery/api/main.py` (upload pipeline, fleet assembly at line 1306), `apps/kerala_delivery/config.py` (fleet constants)
- Project context: `.planning/PROJECT.md` -- v3.0 milestone scope and constraints

---
*Architecture research for: v3.0 Driver-Centric Model*
*Researched: 2026-03-12*
