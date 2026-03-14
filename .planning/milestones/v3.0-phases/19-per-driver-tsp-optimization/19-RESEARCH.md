# Phase 19: Per-Driver TSP Optimization - Research

**Researched:** 2026-03-14
**Domain:** Route optimization (VROOM TSP), geometric analysis (Shapely), FastAPI pipeline refactoring
**Confidence:** HIGH

## Summary

Phase 19 replaces the current multi-vehicle CVRP optimization with per-driver TSP. The existing `VroomAdapter` already supports the needed VROOM API contract -- calling it with a single vehicle per driver group produces TSP-optimal stop ordering. The main work is restructuring `upload_and_optimize()` to group orders by driver from the preprocessed DataFrame, loop VROOM calls per driver, validate zero overlap, detect geographic anomalies with convex hulls, update the Driver PWA URL scheme, and update the QR sheet to show driver names as card titles.

Shapely 2.1.2 is already installed in the project (used by GeoAlchemy2's `to_shape()`), making convex hull overlap detection straightforward without adding new dependencies. The existing `RouteAssignment` model supports multiple routes under one assignment ID, and `save_optimization_run()` persists them all under a single `optimization_run` row -- so OPT-03 is architecturally pre-supported.

**Primary recommendation:** Reuse `VroomAdapter.optimize()` as-is, calling it N times with 1 vehicle + that driver's orders. Merge the N `RouteAssignment` results into a single combined `RouteAssignment` before passing to `save_optimization_run()`. Add a new `core/optimizer/tsp_orchestrator.py` module to encapsulate the per-driver grouping, VROOM calling, overlap validation, and anomaly detection logic -- keeping `main.py` clean.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Uncapped capacity for per-driver VROOM vehicles (high values like 99999 kg / 999 items) -- trust that CDCMS assignments are correct
- Still calculate and display total weight/items per driver route informationally in optimization results and route cards
- All drivers start/end at the Vatakara depot from config.DEPOT_LOCATION -- single depot, no per-driver depot
- Error with clear message at the parse-upload step (POST /api/parse-upload) if CSV has no DeliveryMan column -- fail fast before any processing
- Vehicle fleet table remains in DB untouched but is no longer read during optimization
- No CVRP fallback -- per-driver TSP is the only optimization path
- QR code per driver is the primary access method -- drivers scan QR to access their route
- QR URL uses driver name parameter: /driver/?driver=Suresh+Kumar
- No backward compatibility for old ?vehicle= parameter -- clean break
- Remove vehicle selector screen entirely -- QR-only access
- When PWA opened without ?driver= parameter, show upload screen as today (existing behavior)
- QR cards on print sheet show driver name as card title (replacing vehicle registration number)
- Group geocoded orders by delivery_man column from preprocessed DataFrame
- For each driver group, create 1 VROOM vehicle with uncapped capacity and Vatakara depot
- Run VROOM TSP per driver -- each call produces optimal stop ordering for that driver
- All per-driver routes stored under a single optimization_run
- Post-optimization validation: verify zero order overlap between driver routes (OPT-04)
- Convex hull overlap method -- compute convex hull around each driver's stops
- 30% overlap threshold -- flag when >30% of either driver's hull area is shared
- Warning message names both drivers with overlap percentage
- Warnings included in OptimizationSummary API response only (no dedicated UI card)
- Skip drivers with fewer than 3 stops (convex hull needs at least 3 points)
- route_id format: R-{assignment_id}-{driver_name} (e.g., R-abc12345-Suresh Kumar)
- Driver name stored in the vehicle_id column on RouteDB -- reuses existing column with new semantics
- driver_name column also populated (both vehicle_id and driver_name contain driver name)
- driver_id FK populated with the driver's UUID from the drivers table
- Dashboard route list and live map show driver names instead of vehicle IDs in this phase

### Claude's Discretion
- Partial failure handling: whether to return partial results when one driver's VROOM call fails or fail the entire batch
- Convex hull computation approach: pure Python (shapely) vs PostGIS spatial functions
- Exact error message wording for missing DeliveryMan column

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| OPT-01 | System optimizes stop order within each driver's assigned orders using per-driver TSP (VROOM with 1 vehicle per driver) | VroomAdapter already supports single-vehicle optimization; call it with 1 vehicle per driver group |
| OPT-02 | System groups orders by DeliveryMan column from CSV before optimization | preprocessed_df already contains delivery_man column; group by it before VROOM calls |
| OPT-03 | System stores all per-driver routes under a single optimization_run | RouteAssignment model + save_optimization_run() already support multiple routes under one assignment |
| OPT-04 | System validates post-optimization that no orders overlap between driver routes | Simple set intersection check on order IDs across routes |
| OPT-05 | System reports validation warnings if cross-driver geographic anomalies are detected | Shapely 2.1.2 convex_hull + intersection + area calculation available in project |
</phase_requirements>

## Standard Stack

### Core (Already in Project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| VROOM (Docker) | latest | TSP/CVRP optimization via HTTP API | Already deployed, millisecond solve times |
| Shapely | 2.1.2 | Convex hull computation + polygon intersection for OPT-05 | Already installed (GeoAlchemy2 dependency), proven geometric library |
| FastAPI | existing | HTTP API framework | Already the application framework |
| SQLAlchemy 2.0 | existing | ORM for RouteDB, OptimizationRunDB persistence | Already the DB layer |
| httpx | existing | VROOM HTTP client | Already used by VroomAdapter |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Alembic | existing | DB migration for RouteDB.vehicle_id column width | Widen VARCHAR(20) to VARCHAR(100) for driver names |
| pandas | existing | DataFrame groupby for order-to-driver grouping | Already used in upload pipeline |

### No New Dependencies Needed
The entire phase can be implemented with existing project dependencies. Shapely's `MultiPoint.convex_hull`, `Polygon.intersection()`, and `Polygon.area` cover all geometric computation needs for OPT-05.

## Architecture Patterns

### Recommended New Module
```
core/
  optimizer/
    vroom_adapter.py      # (existing) Single VROOM call
    tsp_orchestrator.py   # (NEW) Per-driver TSP coordination
    interfaces.py         # (existing) RouteOptimizer protocol
```

The `tsp_orchestrator.py` module encapsulates:
1. Order grouping by driver
2. Per-driver Vehicle creation (uncapped capacity, depot)
3. Sequential or parallel VROOM calls
4. Route merging into single RouteAssignment
5. Overlap validation (OPT-04)
6. Geographic anomaly detection (OPT-05)

### Pattern 1: Per-Driver TSP Orchestration
**What:** Group orders by driver name, call VROOM once per driver with 1 vehicle, merge results.
**When to use:** Every optimization run in the new per-driver model.
**Example:**
```python
# Source: Existing VroomAdapter + new orchestration layer
from core.optimizer.vroom_adapter import VroomAdapter
from core.models.vehicle import Vehicle
from core.models.route import RouteAssignment, Route
from apps.kerala_delivery import config

def optimize_per_driver(
    orders_by_driver: dict[str, list[Order]],
    driver_uuids: dict[str, uuid.UUID],
    optimizer: VroomAdapter,
) -> RouteAssignment:
    """Run TSP for each driver group, merge into single RouteAssignment."""
    assignment_id = str(uuid.uuid4())[:8]
    all_routes: list[Route] = []
    all_unassigned: list[str] = []
    total_time_ms = 0.0

    for driver_name, driver_orders in orders_by_driver.items():
        # Create single uncapped vehicle for this driver
        vehicle = Vehicle(
            vehicle_id=driver_name,   # Store driver name as vehicle_id
            driver_name=driver_name,
            max_weight_kg=99999.0,    # Uncapped -- trust CDCMS assignments
            max_items=999,
            depot=config.DEPOT_LOCATION,
        )

        result = optimizer.optimize(driver_orders, [vehicle])
        total_time_ms += result.optimization_time_ms

        for route in result.routes:
            # Override route_id with driver-name format
            route.route_id = f"R-{assignment_id}-{driver_name}"
            all_routes.append(route)

        all_unassigned.extend(result.unassigned_order_ids)

    return RouteAssignment(
        assignment_id=assignment_id,
        routes=all_routes,
        unassigned_order_ids=all_unassigned,
        optimization_time_ms=total_time_ms,
    )
```

### Pattern 2: Order Grouping from DataFrame
**What:** Build driver -> order list mapping using the preprocessed DataFrame's delivery_man column.
**When to use:** After geocoding, before optimization.
**Example:**
```python
# Source: Existing order_driver_map pattern in main.py:1589-1595
def group_orders_by_driver(
    orders: list[Order],
    preprocessed_df: pd.DataFrame,
) -> dict[str, list[Order]]:
    """Group geocoded orders by their assigned driver."""
    # Build order_id -> driver_name map from preprocessed DataFrame
    order_driver_map: dict[str, str] = {}
    for _, row in preprocessed_df.iterrows():
        oid = str(row.get("order_id", "")).strip()
        dm = str(row.get("delivery_man", "")).strip()
        if oid and dm:
            order_driver_map[oid] = dm

    # Group orders
    groups: dict[str, list[Order]] = {}
    for order in orders:
        driver = order_driver_map.get(order.order_id, "")
        if driver:
            groups.setdefault(driver, []).append(order)

    return groups
```

### Pattern 3: Overlap Validation (OPT-04)
**What:** Post-optimization check that no order_id appears in more than one driver's route.
**When to use:** After all per-driver VROOM calls complete.
**Example:**
```python
def validate_no_overlap(assignment: RouteAssignment) -> list[str]:
    """Check that no order appears in multiple routes. Returns error messages."""
    seen: dict[str, str] = {}  # order_id -> driver_name
    errors: list[str] = []
    for route in assignment.routes:
        for stop in route.stops:
            if stop.order_id in seen:
                errors.append(
                    f"Order {stop.order_id} assigned to both "
                    f"{seen[stop.order_id]} and {route.vehicle_id}"
                )
            seen[stop.order_id] = route.vehicle_id
    return errors
```

### Pattern 4: Geographic Anomaly Detection (OPT-05)
**What:** Compute convex hulls around each driver's delivery area, check for >30% overlap.
**When to use:** Post-optimization, after overlap validation passes.
**Example:**
```python
# Source: Shapely 2.1.2 docs (https://shapely.readthedocs.io/en/stable/)
from shapely.geometry import MultiPoint

def detect_geographic_anomalies(
    assignment: RouteAssignment,
    overlap_threshold: float = 0.30,
) -> list[str]:
    """Detect cross-driver geographic overlap using convex hulls."""
    driver_hulls: dict[str, Polygon] = {}

    for route in assignment.routes:
        if len(route.stops) < 3:
            continue  # Need 3+ points for a polygon hull
        points = [(s.location.longitude, s.location.latitude) for s in route.stops]
        hull = MultiPoint(points).convex_hull
        if hull.geom_type == "Polygon":
            driver_hulls[route.vehicle_id] = hull

    warnings: list[str] = []
    drivers = list(driver_hulls.keys())
    for i in range(len(drivers)):
        for j in range(i + 1, len(drivers)):
            hull_a = driver_hulls[drivers[i]]
            hull_b = driver_hulls[drivers[j]]
            if not hull_a.intersects(hull_b):
                continue
            intersection = hull_a.intersection(hull_b)
            overlap_a = intersection.area / hull_a.area if hull_a.area > 0 else 0
            overlap_b = intersection.area / hull_b.area if hull_b.area > 0 else 0
            max_overlap = max(overlap_a, overlap_b)
            if max_overlap > overlap_threshold:
                pct = int(max_overlap * 100)
                warnings.append(
                    f"Geographic overlap: {drivers[i]} and {drivers[j]} "
                    f"have {pct}% delivery area overlap -- "
                    f"consider reassigning orders in CDCMS"
                )

    return warnings
```

### Pattern 5: Driver PWA QR-Only Access
**What:** PWA reads `?driver=` URL param, fetches route by driver name, removes vehicle selector.
**When to use:** When driver scans QR code printed on their sheet.
**Example:**
```javascript
// Source: Existing Driver PWA index.html URL param pattern
const params = new URLSearchParams(window.location.search);
const driverName = params.get('driver');

if (driverName) {
    // QR-based access: load route directly for this driver
    loadRouteByDriver(driverName);
} else {
    // Manual access: show upload screen (existing behavior)
    showUploadScreen();
}
```

### Anti-Patterns to Avoid
- **Parallel VROOM calls:** VROOM Docker container is single-threaded. Parallel HTTP calls could cause timeouts or contention. Use sequential calls -- each TSP solve takes <100ms for typical driver loads (20-40 stops).
- **Modifying VroomAdapter internals:** The adapter works correctly for single-vehicle TSP as-is. Don't add special TSP mode -- just pass 1 vehicle.
- **Storing driver name in separate column only:** Both `vehicle_id` AND `driver_name` must contain the driver name (CONTEXT.md decision). The `vehicle_id` column is what the Driver PWA uses for route lookup via `GET /api/routes/{vehicle_id}`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Convex hull computation | Custom geometry math | `shapely.MultiPoint.convex_hull` | Handles degenerate cases (collinear points, <3 points), numerically stable |
| Polygon intersection area | Manual polygon clipping | `shapely.Polygon.intersection()` + `.area` | Handles all polygon intersection cases correctly |
| TSP optimization | Custom nearest-neighbor heuristic | VROOM with 1 vehicle | VROOM uses meta-heuristics that beat simple greedy approaches; 0ms overhead |
| URL encoding for driver names | Manual string replacement | `encodeURIComponent()` (JS) / `urllib.parse.quote_plus()` (Python) | Handles Unicode, spaces, special chars correctly |

**Key insight:** Every component of this phase has an existing, battle-tested implementation already in the project or its dependencies. The work is orchestration, not invention.

## Common Pitfalls

### Pitfall 1: RouteDB.vehicle_id Column Too Short
**What goes wrong:** Driver names like "Suresh Kumar Nair P" could exceed VARCHAR(20). Insert fails with PostgreSQL truncation or constraint error.
**Why it happens:** Column was designed for vehicle IDs like "VEH-01" (7 chars), not human names.
**How to avoid:** Create an Alembic migration to widen `routes.vehicle_id` from VARCHAR(20) to VARCHAR(100). Also widen `telemetry.vehicle_id` for consistency. The `vehicles.vehicle_id` column keeps its size since the vehicles table is no longer used for optimization.
**Warning signs:** Database insertion error after optimization completes.

### Pitfall 2: VROOM Returns Empty Route for Single-Stop Driver
**What goes wrong:** A driver with only 1 order gets an empty route from VROOM because VROOM may treat a single-job problem differently.
**Why it happens:** VROOM TSP with 1 job is trivial (depot -> stop -> depot) but the response format may vary.
**How to avoid:** Verify VROOM handles 1-job input correctly in tests. The existing VroomAdapter parser handles this case since it iterates `steps` with `type="job"`.
**Warning signs:** Missing routes for single-stop drivers in results.

### Pitfall 3: Driver Name Encoding in QR URLs
**What goes wrong:** Driver names with spaces or special characters break QR code URLs if not properly encoded.
**Why it happens:** Names like "Suresh Kumar" need to be "Suresh+Kumar" or "Suresh%20Kumar" in URLs.
**How to avoid:** Use `urllib.parse.quote_plus(driver_name)` when generating QR URLs server-side. Use `decodeURIComponent()` when reading the param in the PWA.
**Warning signs:** QR codes scan but driver route not found (name mismatch).

### Pitfall 4: Order-Driver Map Missing After Geocoding Filter
**What goes wrong:** The `order_driver_map` built from `preprocessed_df` may not align with the filtered `geocoded_orders` list if driver selection filtering happened.
**Why it happens:** Orders get filtered by selected_drivers, then some fail geocoding, but the order_driver_map still has all entries.
**How to avoid:** Build the order-driver grouping from the final `geocoded_orders` list (which already has driver selection and geocoding applied), not from the full preprocessed_df.
**Warning signs:** Orders from deselected drivers appearing in VROOM input.

### Pitfall 5: Convex Hull Area in Lat/Lon Coordinates
**What goes wrong:** Shapely computes area in the coordinate system's units. For lat/lon (EPSG:4326), area values are in square degrees, not square meters. This doesn't affect the overlap RATIO calculation (both numerator and denominator are in the same units), but logs showing "area = 0.0001" could be confusing.
**Why it happens:** We're using unprojected coordinates for hull computation.
**How to avoid:** The overlap threshold check uses ratios (intersection.area / hull.area), so the units cancel out. This is correct for overlap percentage detection. Document that absolute area values are in square degrees and not meaningful on their own.
**Warning signs:** None -- ratios work correctly with unprojected coordinates.

### Pitfall 6: parse-upload DeliveryMan Column Check Timing
**What goes wrong:** If the DeliveryMan column check is only in `upload_and_optimize()`, users discover the missing column too late (after waiting for upload + parsing).
**Why it happens:** CONTEXT.md requires the check in parse-upload (step 1), not in optimize (step 2).
**How to avoid:** Add DeliveryMan column validation in `parse_upload()` endpoint, right after `preprocess_cdcms()` succeeds. If `delivery_man` column is missing or empty, return 400 immediately.
**Warning signs:** User uploads CSV, sees driver preview, then gets error on "Process" step.

### Pitfall 7: Driver UUID Lookup for RouteDB.driver_id
**What goes wrong:** The `driver_id` FK on RouteDB must be populated with the driver's UUID from the drivers table, but matching driver names to UUIDs requires fuzzy matching (same logic as auto_create_drivers_from_csv).
**Why it happens:** CSV uses raw names like "SURESH K" but DB stores "Suresh Kumar" from previous auto-creation.
**How to avoid:** auto_create_drivers_from_csv() already runs before optimization (in the pipeline). After it runs, build a name -> UUID map from the DB. Use the same fuzzy matching to resolve each driver's orders to their DB UUID.
**Warning signs:** RouteDB rows with NULL driver_id.

## Code Examples

### VROOM Single-Vehicle (TSP) Request
```json
// Source: Verified against existing VroomAdapter._build_request()
{
  "vehicles": [
    {
      "id": 0,
      "start": [75.5796, 11.6244],
      "end": [75.5796, 11.6244],
      "capacity": [99999, 999],
      "description": "Suresh Kumar"
    }
  ],
  "jobs": [
    {"id": 0, "location": [75.57, 11.595], "delivery": [14, 1], "service": 300, "description": "ORD-001"},
    {"id": 1, "location": [75.565, 11.61], "delivery": [14, 1], "service": 300, "description": "ORD-002"}
  ],
  "options": {"g": true}
}
```

### Convex Hull Overlap Detection
```python
# Source: Shapely 2.1.2 (https://shapely.readthedocs.io/en/stable/)
from shapely.geometry import MultiPoint, Polygon

# Driver A's stops
points_a = [(75.57, 11.59), (75.56, 11.61), (75.59, 11.63), (75.58, 11.60)]
hull_a = MultiPoint(points_a).convex_hull

# Driver B's stops
points_b = [(75.58, 11.60), (75.57, 11.62), (75.60, 11.64), (75.59, 11.61)]
hull_b = MultiPoint(points_b).convex_hull

# Check overlap
if hull_a.intersects(hull_b):
    intersection = hull_a.intersection(hull_b)
    overlap_pct = max(
        intersection.area / hull_a.area,
        intersection.area / hull_b.area,
    )
    if overlap_pct > 0.30:
        print(f"Warning: {overlap_pct:.0%} overlap")
```

### QR URL Generation with Driver Name
```python
# Source: Existing qr_helpers.py pattern + urllib for name encoding
from urllib.parse import quote_plus

driver_name = "Suresh Kumar"
base_url = "https://example.com/driver/"
qr_url = f"{base_url}?driver={quote_plus(driver_name)}"
# Result: https://example.com/driver/?driver=Suresh+Kumar
```

### Route Lookup by Driver Name (API Endpoint)
```python
# Source: Existing get_route_for_vehicle pattern in repository.py
# The vehicle_id column now stores driver names
route_db = await repo.get_route_for_vehicle(session, run.id, driver_name)
# Works because vehicle_id column contains driver name
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fleet of vehicles from DB | Per-driver from CSV | Phase 19 | No vehicle DB lookup needed for optimization |
| Single CVRP VROOM call | N sequential TSP VROOM calls | Phase 19 | Each driver gets independently optimal routing |
| vehicle_id in routes | driver_name in vehicle_id column | Phase 19 | PWA lookup, QR URLs, and API all use driver name |
| Vehicle selector in PWA | QR-only access | Phase 19 | Remove vehicle selector screen |
| ?vehicle= URL param | ?driver= URL param | Phase 19 | Clean break, no backward compatibility |

## Discretion Recommendations

### Partial Failure Handling
**Recommendation: Return partial results** when one driver's VROOM call fails.
**Rationale:** If 5 drivers are being optimized and one fails (e.g., all orders geocoded to depot fallback), the other 4 should still get routes. Log the failure and include a warning in the response. The failing driver's orders become "unassigned" in the assignment.
**Implementation:** Wrap each VROOM call in try/except. On failure, add the driver's orders to `unassigned_order_ids` and add a warning message to the response.

### Convex Hull Computation
**Recommendation: Use Shapely (pure Python)** rather than PostGIS spatial functions.
**Rationale:**
1. Shapely 2.1.2 is already installed and imported in the codebase (repository.py uses `from shapely import Point`)
2. Convex hull computation happens on in-memory coordinates (already available from the Route model), not on DB-stored geometries
3. No additional DB round-trip needed
4. Easier to test (no DB dependency in unit tests)
5. Performance is not a concern: computing 13 convex hulls with 20-40 points each takes microseconds

### Error Message for Missing DeliveryMan Column
**Recommendation:** `"CSV is missing the DeliveryMan column -- this file must be a CDCMS export with driver assignments. Upload a file exported from CDCMS after allocating orders to drivers."`
**Rationale:** Actionable, tells the user what's wrong AND what to do about it. Matches the project's existing error message style (plain English, no jargon, includes corrective action).

## Database Migration Required

### RouteDB.vehicle_id Column Width
The `routes.vehicle_id` column is currently `VARCHAR(20)` in both the ORM model (`String(20)`) and init.sql. Since this column will now store driver names (e.g., "Muhammed Shafeek K" = 19 chars, but some names could be longer), it must be widened.

**Migration needed:**
```sql
ALTER TABLE routes ALTER COLUMN vehicle_id TYPE VARCHAR(100);
```

Also update `core/database/models.py`:
```python
vehicle_id: Mapped[str] = mapped_column(String(100), nullable=False)
```

The `telemetry.vehicle_id` column (also VARCHAR(20)) should be widened for consistency since telemetry pings will use driver names too.

## Open Questions

1. **VROOM with 0 orders for a driver**
   - What we know: If a driver is selected but has 0 geocoded orders (all failed geocoding), VROOM would receive an empty jobs list.
   - What's unclear: Does VroomAdapter handle empty order lists gracefully?
   - Recommendation: Add a guard -- skip VROOM call for drivers with 0 geocoded orders. This is an edge case that should be handled in the orchestrator.

2. **Dashboard route card display changes**
   - What we know: CONTEXT.md says "Dashboard route list and live map show driver names instead of vehicle IDs"
   - What's unclear: Exact UI changes needed -- but this is Phase 20 (UI-01, UI-02, UI-03) territory
   - Recommendation: Phase 19 ensures the data is correct (vehicle_id contains driver name, driver_name populated). The VehicleList component already shows `route.vehicle_id` and `route.driver_name` -- once vehicle_id contains the driver name, it will display correctly even before Phase 20 UI polish.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (async, asyncio_mode=auto) |
| Config file | `pytest.ini` |
| Quick run command | `pytest tests/core/optimizer/ -v -x` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OPT-01 | Per-driver TSP produces optimal stop ordering via VROOM | unit | `pytest tests/core/optimizer/test_tsp_orchestrator.py::test_single_driver_tsp -x` | Wave 0 |
| OPT-02 | Orders grouped by DeliveryMan column before optimization | unit | `pytest tests/core/optimizer/test_tsp_orchestrator.py::test_order_grouping_by_driver -x` | Wave 0 |
| OPT-03 | All per-driver routes stored under single optimization_run | unit | `pytest tests/core/optimizer/test_tsp_orchestrator.py::test_merged_assignment_single_run -x` | Wave 0 |
| OPT-04 | Zero order overlap validation between driver routes | unit | `pytest tests/core/optimizer/test_tsp_orchestrator.py::test_no_overlap_validation -x` | Wave 0 |
| OPT-05 | Geographic anomaly detection via convex hull overlap | unit | `pytest tests/core/optimizer/test_tsp_orchestrator.py::test_geographic_anomaly_detection -x` | Wave 0 |
| - | DeliveryMan column missing error in parse-upload | unit | `pytest tests/apps/kerala_delivery/test_parse_upload.py::test_missing_deliveryman_column -x` | Wave 0 |
| - | Driver PWA reads ?driver= param and loads route | e2e | `npx playwright test --project=driver-pwa -g "driver param"` | Wave 0 |
| - | QR sheet shows driver name as card title | e2e | `npx playwright test --project=api -g "qr sheet"` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/core/optimizer/test_tsp_orchestrator.py -v -x`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/core/optimizer/test_tsp_orchestrator.py` -- covers OPT-01 through OPT-05
- [ ] DB migration for routes.vehicle_id VARCHAR(20) -> VARCHAR(100) -- prerequisite for storing driver names
- [ ] Alembic migration file in `infra/alembic/versions/`

## Sources

### Primary (HIGH confidence)
- **Codebase analysis:** `core/optimizer/vroom_adapter.py` -- verified VroomAdapter works for single-vehicle (TSP) calls with no code changes
- **Codebase analysis:** `core/models/route.py` -- confirmed RouteAssignment supports multiple routes, Route has driver_name field
- **Codebase analysis:** `core/database/repository.py` -- confirmed save_optimization_run() handles any number of routes under one run
- **Codebase analysis:** `core/database/models.py` -- identified RouteDB.vehicle_id VARCHAR(20) constraint that needs widening
- **Codebase analysis:** `apps/kerala_delivery/api/main.py` lines 1589-1601 -- existing order_driver_map pattern reusable
- **Codebase analysis:** `apps/kerala_delivery/api/main.py` lines 1841-1880 -- current VROOM call site that needs replacement
- **Shapely 2.1.2 docs** (https://shapely.readthedocs.io/en/stable/) -- MultiPoint.convex_hull, Polygon.intersection, Polygon.area APIs confirmed

### Secondary (MEDIUM confidence)
- **VROOM GitHub** (https://github.com/VROOM-Project/vroom) -- TSP is a degenerate case of CVRP with 1 vehicle, fully supported
- **Shapely API verification** -- tested `MultiPoint.convex_hull` in project venv, returns Polygon with correct area

### Tertiary (LOW confidence)
- None -- all findings verified against codebase and installed libraries

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already installed, APIs verified in codebase
- Architecture: HIGH - existing patterns (VroomAdapter, RouteAssignment, save_optimization_run) directly support per-driver TSP with minimal refactoring
- Pitfalls: HIGH - identified through direct codebase analysis (VARCHAR(20) constraint, URL encoding, column timing)
- Discretion items: HIGH - recommendations based on project patterns and practical considerations

**Research date:** 2026-03-14
**Valid until:** 2026-04-14 (stable -- no external dependency changes expected)
