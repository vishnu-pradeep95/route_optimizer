# Phase 19: Per-Driver TSP Optimization - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the current multi-vehicle CVRP optimization with per-driver TSP. Group orders by driver from the CSV DeliveryMan column, run VROOM with 1 vehicle per driver (TSP for optimal stop ordering), store all per-driver routes under a single optimization run, validate no order overlap, and detect cross-driver geographic anomalies. Update the Driver PWA to use driver-name-based QR codes and the dashboard to display driver names instead of vehicle IDs.

</domain>

<decisions>
## Implementation Decisions

### Vehicle Capacity
- Uncapped capacity for per-driver VROOM vehicles (high values like 99999 kg / 999 items) -- trust that CDCMS assignments are correct
- Still calculate and display total weight/items per driver route informationally in optimization results and route cards
- All drivers start/end at the Vatakara depot from config.DEPOT_LOCATION -- single depot, no per-driver depot

### No-DeliveryMan-Column Fallback
- Error with clear message at the parse-upload step (POST /api/parse-upload) if CSV has no DeliveryMan column
- Fail fast before any processing -- user sees error immediately after selecting file
- Vehicle fleet table remains in DB untouched but is no longer read during optimization
- No CVRP fallback -- per-driver TSP is the only optimization path

### Driver PWA Changes
- QR code per driver is the primary access method -- drivers scan QR to access their route
- QR URL uses driver name parameter: `/driver/?driver=Suresh+Kumar`
- No backward compatibility for old `?vehicle=` parameter -- clean break
- Remove vehicle selector screen entirely -- QR-only access
- When PWA opened without `?driver=` parameter, show upload screen as today (existing behavior)
- QR cards on print sheet show driver name as card title (replacing vehicle registration number)

### Per-Driver TSP Optimization Flow
- Group geocoded orders by delivery_man column from preprocessed DataFrame
- For each driver group, create 1 VROOM vehicle with uncapped capacity and Vatakara depot
- Run VROOM TSP per driver -- each call produces optimal stop ordering for that driver
- All per-driver routes stored under a single optimization_run
- Post-optimization validation: verify zero order overlap between driver routes (OPT-04)

### Geographic Anomaly Detection (OPT-05)
- Convex hull overlap method -- compute convex hull around each driver's stops
- 30% overlap threshold -- flag when >30% of either driver's hull area is shared
- Warning message names both drivers with overlap percentage: "Geographic overlap: Suresh Kumar and Anil P have 42% delivery area overlap -- consider reassigning orders in CDCMS"
- Warnings included in OptimizationSummary API response only (no dedicated UI card)
- Skip drivers with fewer than 3 stops (convex hull needs at least 3 points)

### Route Identity and Naming
- route_id format: `R-{assignment_id}-{driver_name}` (e.g., R-abc12345-Suresh Kumar)
- Driver name stored in the vehicle_id column on RouteDB -- reuses existing column with new semantics
- driver_name column also populated (both vehicle_id and driver_name contain driver name)
- driver_id FK populated with the driver's UUID from the drivers table
- Dashboard route list and live map show driver names instead of vehicle IDs in this phase

### Claude's Discretion
- Partial failure handling: whether to return partial results when one driver's VROOM call fails or fail the entire batch
- Convex hull computation approach: pure Python (shapely) vs PostGIS spatial functions
- Exact error message wording for missing DeliveryMan column

</decisions>

<specifics>
## Specific Ideas

- The system should feel like "upload CSV, get per-driver routes" -- no vehicle fleet configuration needed anymore
- QR sheet is the bridge between office and drivers -- driver name as title makes it immediately clear whose sheet it is
- Geographic overlap warnings help office staff catch CDCMS assignment issues before drivers hit the road
- Weight totals are informational only -- no blocking on overloads since CDCMS manages assignments

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `VroomAdapter` (core/optimizer/vroom_adapter.py): Full VROOM integration with request building and response parsing -- needs modification to accept per-driver calls
- `RouteAssignment`, `Route`, `RouteStop` models (core/models/route.py): Output models already support multiple routes under one assignment
- `save_optimization_run` (core/database/repository.py:88): Persists assignment with routes and stops -- works with any number of routes
- `order_driver_map` construction (main.py:1589-1595): Already maps order_id -> delivery_man from preprocessed_df
- `auto_create_drivers_from_csv()` (main.py:933): Returns driver summary with DB UUIDs for linking
- QR sheet HTML generation (main.py ~line 2349): Server-rendered HTML cards per route -- update card title and QR URL
- Driver PWA (apps/kerala_delivery/driver_app/index.html): Vanilla JS, reads ?vehicle= param -- change to ?driver=

### Established Patterns
- VROOM adapter takes list[Order] + list[Vehicle], returns RouteAssignment -- call once per driver
- Repository pattern for all DB operations including save_optimization_run
- Config values in config.py with env var overrides
- OptimizationSummary response model includes warnings array

### Integration Points
- `upload_and_optimize()` (main.py:1244): Main pipeline -- replace fleet lookup + single VROOM call with per-driver grouping + multiple VROOM calls
- `parse_upload()` (main.py ~line 1050): Add DeliveryMan column check, error early if missing
- `VroomAdapter._build_request()`: Needs to accept single-vehicle config for TSP mode
- `RouteDB.vehicle_id`: Store driver name instead of vehicle registration
- `RouteDB.driver_id`: Populate with driver UUID from drivers table
- Driver PWA `index.html`: Change URL param from ?vehicle= to ?driver=, remove vehicle selector
- Dashboard route components: Display driver_name instead of vehicle_id in route cards and map
- QR sheet generator: Update card title and QR URL to use driver name

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 19-per-driver-tsp-optimization*
*Context gathered: 2026-03-14*
