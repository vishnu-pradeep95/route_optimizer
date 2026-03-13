# Domain Pitfalls

**Domain:** Adding driver-centric model, per-driver TSP, Google Maps route validation, geocode cache management, and dashboard settings to an existing LPG delivery route optimization system
**Researched:** 2026-03-12
**Confidence:** HIGH for DB migration pitfalls (verified against init.sql, models.py, repository.py, 6 Alembic migrations); HIGH for CVRP-to-TSP pitfalls (verified against vroom_adapter.py and RouteOptimizer protocol); HIGH for API/frontend coupling (traced 371 vehicle references across 16 dashboard files, 67 in driver PWA, 129 in tests, 80 in E2E specs); MEDIUM for Google Maps Directions API costs (verified pricing structure against official docs, specific SKU rates may shift); HIGH for xlsx detection (verified _is_cdcms_format reads text, fails on binary .xlsx)

---

## Critical Pitfalls

Mistakes that cause rewrites, data corruption, or extended downtime.

### Pitfall 1: Vehicle-to-Driver Rename Creates a Semantic Minefield

**What goes wrong:**
The codebase has "vehicle" embedded at every layer: 7 database tables reference `vehicle_id` as a VARCHAR(20) string (routes, telemetry, vehicles table itself), 371 occurrences across 16 dashboard TypeScript files, 67 occurrences in the driver PWA, 129 occurrences across 7 Python test files, and 80 occurrences across 4 Playwright E2E spec files. A naive find-and-replace corrupts the system because `vehicle_id` serves two distinct roles:

1. **Physical vehicle identifier** (VEH-01): Used in the `vehicles` table, telemetry, fleet management, speed limits, depot locations, capacity constraints. These are properties of the VEHICLE.
2. **Route assignment key**: Used in `routes.vehicle_id`, API endpoints (`/api/routes/{vehicle_id}`), driver PWA route fetching, QR sheet generation. In the new model, this should become a DRIVER identifier.

Renaming the `routes.vehicle_id` column to `driver_id` while the `vehicles` table still exists creates foreign key ambiguity. The `telemetry.vehicle_id` column genuinely tracks which VEHICLE is moving (for speed alerts, GPS traces), not which driver is logged in. Renaming it to `driver_id` would be semantically wrong.

**Why it happens:**
The original CVRP model treats "vehicle" as the atomic routing unit. In the new driver-centric model, the driver is the routing unit, but vehicles still exist as physical assets. The rename is not a simple substitution -- it is a conceptual split of one entity into two related entities.

**Consequences:**
- Breaking all 38 Playwright E2E tests (they hardcode `VEH-01`, `/api/routes/VEH-01`)
- Breaking 435+ pytest unit tests (102 references to `vehicle_id` in test_api.py alone)
- API contract breakage: `/api/routes/{vehicle_id}` is consumed by the driver PWA. Changing the URL path breaks all existing QR codes already printed and distributed
- Telemetry data becomes unqueryable if `vehicle_id` column is renamed mid-stream (existing rows say "VEH-01", new rows say "DRIVER-01")

**Prevention:**
1. Do NOT rename the `vehicle_id` column in `routes` table. Add a new `driver_name` column (already exists) or `driver_id` FK alongside it. Keep `vehicle_id` for backward compatibility.
2. Keep `/api/routes/{vehicle_id}` endpoint path unchanged. Internally, look up by driver identifier OR vehicle identifier.
3. Add a `drivers` table (already exists in schema) and link it to routes via a new nullable `driver_id` FK column added by migration. Existing routes retain their `vehicle_id` and `driver_name` values.
4. In the dashboard, change LABELS (UI text) from "Vehicle" to "Driver" without changing the API field names. The TypeScript interfaces keep `vehicle_id` as the wire format but UI renders "Driver: RAJESH" instead of "Vehicle: VEH-01".
5. Phase the migration: Phase 1 adds driver entities, Phase 2 updates UI labels, Phase 3 (optional future) deprecates direct vehicle routing.

**Detection:**
Any plan that includes `ALTER TABLE routes RENAME COLUMN vehicle_id TO driver_id` or `s/vehicle_id/driver_id/g` is heading toward this pitfall.

---

### Pitfall 2: CVRP-to-TSP Transition Breaks the Optimizer Interface

**What goes wrong:**
The current `RouteOptimizer.optimize()` protocol signature is:
```python
def optimize(self, orders: list[Order], vehicles: list[Vehicle]) -> RouteAssignment
```
This takes ALL orders and ALL vehicles, letting VROOM decide the optimal assignment. Per-driver TSP means orders are pre-assigned to drivers before optimization. If you pass a single vehicle to VROOM with all orders, it still works -- but if you pass a single vehicle with only that driver's orders, VROOM solves TSP (which is correct). The pitfall is in the transition logic:

1. **Who assigns orders to drivers?** CDCMS's `DeliveryMan` column contains the pre-assignment. But if the office employee wants to reassign orders between drivers in the dashboard before optimizing, the assignment happens in the frontend/API layer, not the optimizer.
2. **VROOM still needs vehicle capacity constraints.** Even in TSP mode (1 vehicle, N orders), the vehicle's `max_weight_kg` and `max_items` must be respected. If you strip vehicle info from the TSP call, you lose capacity validation. VROOM will happily produce a route with 50 cylinders on a vehicle that holds 30.
3. **The `RouteAssignment` model assumes multi-vehicle output.** It has `vehicles_used`, `unassigned_order_ids`, multiple `routes`. For per-driver TSP, there is exactly 1 route and 0 unassigned orders (or the driver is overloaded). The UI code that iterates `assignment.routes` and shows "X vehicles used" becomes misleading.

**Why it happens:**
VROOM is a CVRP solver. Using it for TSP is not wrong -- TSP is a special case of CVRP with 1 vehicle. But the calling code, response parsing, and data model all assume multi-vehicle context.

**Consequences:**
- Overloaded drivers: no capacity check if vehicle info is stripped from per-driver calls
- Dashboard shows "1 vehicle used" instead of meaningful driver stats
- `optimization_runs.vehicles_used` is always 1 per run, losing fleet-wide visibility
- If you create N separate optimization runs (one per driver), the `get_latest_run()` query returns only the last driver's run, hiding all others

**Prevention:**
1. Keep VROOM as the optimizer but call it N times (once per driver) with 1 vehicle + that driver's orders. This preserves capacity constraints.
2. Wrap the N calls in a new `PerDriverOptimizer` that implements the same `RouteOptimizer` protocol but internally iterates over drivers.
3. Store all N driver routes under a SINGLE `optimization_run` so `get_latest_run()` returns the complete picture. The `vehicles_used` field becomes "drivers_optimized" semantically.
4. Alternatively, pass ALL orders to VROOM with N vehicles (one per driver) but use VROOM's `steps` feature to pre-assign specific jobs to specific vehicles. This lets VROOM optimize the SEQUENCE while respecting the ASSIGNMENT. (Requires VROOM job `skills` or vehicle `steps` matching.)

**Detection:**
Any approach that creates separate `optimization_runs` per driver, or removes `Vehicle` objects from optimize calls, is heading into this pitfall.

---

### Pitfall 3: .xlsx Binary Format Breaks CDCMS Auto-Detection

**What goes wrong:**
The `_is_cdcms_format()` function in `main.py` opens the uploaded file as TEXT (`open(file_path, "r", encoding="utf-8")`) and checks for tab characters and CDCMS column names in the first line. An `.xlsx` file is a ZIP archive of XML files -- opening it as text produces binary garbage, not column headers. The function returns `False`, so the upload falls through to the standard CSV import path, which also fails because `CsvImporter` cannot parse a binary Excel file as CSV.

The temp file is saved with suffix `.xlsx` (line 884: `suffix = ".csv" if ext == ".csv" else ".xlsx"`), so the file extension is correct. But `_is_cdcms_format()` ignores the extension entirely and relies on text content inspection.

Currently this is masked because CDCMS exports are tab-separated `.csv` files. But the v3.0 milestone explicitly targets `.xlsx` support for when employees save CDCMS exports via Excel (which converts to `.xlsx`).

**Why it happens:**
`_is_cdcms_format()` was written for tab-separated text files. When CDCMS data arrives as `.xlsx`, the function's text-reading approach fails silently (returns `False`) rather than raising an error. The `preprocess_cdcms()` function DOES handle `.xlsx` (via `pd.read_excel()`), but it never gets called because the auto-detection gate rejects the file first.

**Consequences:**
- Office employees who save CDCMS exports as `.xlsx` from Excel get cryptic "Required columns missing" errors
- The error message says "make sure you're uploading the raw CDCMS export" -- confusing because they ARE uploading from CDCMS, just in a different format
- Potential data loss if the employee gives up and manually reformats the file, losing CDCMS metadata

**Prevention:**
1. In `_is_cdcms_format()`, check file extension FIRST. If `.xlsx` or `.xls`, use `pd.read_excel()` to read the header row, then check for CDCMS column names.
2. Alternatively, always try `preprocess_cdcms()` first for any uploaded file, catch `ValueError` if columns are missing, then fall back to standard `CsvImporter`. This is the "try CDCMS first, fall back to generic" pattern.
3. Add a test case: upload a valid CDCMS `.xlsx` file and verify it reaches the preprocessor.

**Detection:**
Test the upload endpoint with a `.xlsx` file containing CDCMS columns. If it fails with "Required columns missing" instead of processing successfully, this pitfall is active.

---

### Pitfall 4: Google Maps Directions API Cost Explosion

**What goes wrong:**
Using Google Maps Directions API to "validate" VROOM routes means calling the Directions API for every optimized route after every upload. With 13 drivers and daily uploads, that is 13 Directions API calls per day. Each call with >10 waypoints uses the "Directions Advanced" SKU. Routes with 20-30 stops require splitting into segments of 25 waypoints max (the API limit), potentially doubling the call count.

The Directions API costs approximately $10 per 1,000 requests for Advanced SKU (routes with >10 waypoints). At 13 routes/day with possible segment splitting, that is ~20-26 API calls/day = ~600-780/month. Combined with the existing Geocoding API costs (~$5/1,000), the monthly API bill could jump from ~$5-10/month to ~$15-20/month. This is manageable, but the pitfall is in the IMPLEMENTATION:

If route validation is triggered on every page load (dashboard polling), or on every driver route refresh, or if a bug causes retry loops, the API call count could spike to thousands per month. Google's new 2025 billing structure provides free usage thresholds per SKU on the Essentials tier, but exceeding them triggers full-price billing.

**Why it happens:**
The Geocoding API is already integrated with careful caching (hit rates of 60-80%). The temptation is to add Directions API calls "just for validation" without the same caching discipline. Directions results are harder to cache because they depend on real-time traffic data and the exact waypoint order.

**Consequences:**
- Unexpected Google Cloud bills (could reach $50-100/month if validation runs on every API call)
- Hitting rate limits (3,000 requests/minute for Directions API, but the daily quota matters more for billing)
- If the API key has billing alerts disabled, costs accumulate silently

**Prevention:**
1. Call Directions API ONLY on explicit user action ("Validate with Google Maps" button), never on automatic route generation or page load.
2. Cache Directions results per route hash (ordered waypoint coordinates). Same route = same validation result. Only invalidate if stops change.
3. Display the estimated cost before calling: "This will use ~2 Google Maps API calls ($0.02). Validate?"
4. Set a daily/monthly budget cap in Google Cloud Console. Configure billing alerts at 50% and 80% of budget.
5. Consider using OSRM route distance as the "good enough" validation and reserve Google Maps for routes where OSRM and user expectations diverge significantly (>20% difference).

**Detection:**
If Directions API calls appear in Google Cloud billing without corresponding user actions in the dashboard audit log, the validation is being called too frequently.

---

## Moderate Pitfalls

### Pitfall 5: Alembic Migration for Schema Changes Drops Existing Data

**What goes wrong:**
Adding a `driver_id` FK column to the `routes` table, or adding new columns to `optimization_runs` (like `drivers_optimized`), requires an Alembic migration. Alembic's autogenerate feature CANNOT detect column renames -- it sees the old column disappearing and a new column appearing, generating a `DROP COLUMN` followed by `ADD COLUMN`. If the migration is auto-generated and applied without review, existing route data loses its `vehicle_id` or `driver_name` values.

The project already has 6 migrations. A new migration that alters the `routes` table interacts with existing data: hundreds of route rows reference `vehicle_id` values like "VEH-01" through "VEH-13". These must be preserved.

**Why it happens:**
Auto-generated migrations are a convenience but are explicitly documented as requiring manual review. The Alembic docs state: "autogenerate is not intended to be perfect, and it is always necessary to manually review and correct the candidate migrations."

**Consequences:**
- Existing optimization history disappears (routes table has ON DELETE CASCADE from optimization_runs, but column drops don't cascade -- they just lose data)
- The `GET /api/runs/{run_id}/routes` endpoint returns routes with NULL vehicle_id for historical runs
- Driver PWA cannot load historical routes (vehicle_id is the lookup key)

**Prevention:**
1. NEVER use `alembic revision --autogenerate` without manual review for this milestone. Hand-write the migration.
2. For adding `driver_id` to routes: use `ADD COLUMN driver_id UUID REFERENCES drivers(id) NULL`. Make it nullable for backward compatibility. Existing rows have NULL driver_id (they were vehicle-assigned, not driver-assigned).
3. For renaming concepts (vehicles_used -> drivers_used in optimization_runs): ADD the new column alongside the old one. Populate it with a data migration: `UPDATE optimization_runs SET drivers_used = vehicles_used`. Keep the old column for backward compatibility.
4. Test the migration on a copy of production data before applying: `pg_dump | psql test_db && alembic upgrade head`.

**Detection:**
Run `alembic revision --autogenerate --sql` (dry-run) and inspect the SQL. Any `DROP COLUMN` on `routes`, `orders`, or `optimization_runs` is a red flag.

---

### Pitfall 6: Per-Driver Optimization Loses Fleet-Wide Metrics

**What goes wrong:**
The dashboard's RunHistory page shows optimization summaries: total orders assigned, vehicles used, optimization time. The UploadRoutes page shows "X vehicles used" in the result summary. These metrics come from `optimization_runs` table columns and the `OptimizationSummary` response model (defined in main.py).

When optimization switches to per-driver TSP, several metrics break:
- `vehicles_used`: Always matches driver count, not fleet utilization
- `optimization_time_ms`: Is it the sum of all per-driver optimizations, the max (parallel), or the last one?
- `orders_unassigned`: In CVRP, VROOM reports orders it could not fit into any vehicle. In per-driver TSP, all orders are pre-assigned, so "unassigned" means "the driver's vehicle is overloaded". The semantic meaning shifts.
- `total_orders` vs `orders_assigned`: If different drivers are optimized at different times (upload per driver vs batch upload), the run-level totals are misleading.

**Why it happens:**
The `OptimizationSummary` Pydantic model and the `optimization_runs` table were designed for a single CVRP invocation that processes all orders at once. Per-driver optimization is N smaller invocations, and the aggregation semantics change.

**Consequences:**
- Dashboard shows confusing metrics ("1 vehicle used, 12 orders" when there are 13 drivers)
- RunHistory comparisons become meaningless (yesterday: "13 vehicles, 50 orders" vs today: "1 driver, 4 orders" for each of 13 runs)
- TypeScript types (`OptimizationRun.vehicles_used`) become misleading without UI label changes

**Prevention:**
1. If per-driver optimization, still store all driver routes under ONE `optimization_run`. Set `vehicles_used` = number of drivers optimized. This preserves the semantic meaning for the dashboard.
2. Add a `mode` field to `optimization_runs`: "fleet_cvrp" or "per_driver_tsp". The dashboard can adapt its labels based on the mode.
3. Aggregate metrics at the run level: `optimization_time_ms` = wall-clock time for the entire batch (not individual driver times). `orders_assigned` = sum across all drivers.
4. Update the TypeScript `OptimizationRun` interface to include `mode` and conditionally render "drivers" vs "vehicles" in RunHistory.

**Detection:**
Upload a file with per-driver optimization and check the RunHistory page. If it shows "1 vehicle used" or multiple confusing run entries, this pitfall is active.

---

### Pitfall 7: Dashboard Settings Page Exposes API Keys in Browser

**What goes wrong:**
The v3.0 milestone includes "Dashboard settings (API key input)". If the Google Maps API key is entered in a dashboard settings form and stored/transmitted via the browser, it becomes visible in:
1. Browser DevTools Network tab (the POST request body)
2. Browser history/autofill
3. React state (inspectable via React DevTools)
4. Any XSS vulnerability exposes the key

The current architecture keeps `GOOGLE_MAPS_API_KEY` as a server-side environment variable, never sent to the frontend. The dashboard has NO access to it. Moving key management to the browser breaks this security boundary.

**Why it happens:**
The desire to let office staff configure the API key without editing `.env` files or restarting Docker containers is legitimate. But the implementation must keep the key server-side.

**Consequences:**
- Compromised API key leads to unauthorized Google Maps usage (billing to the customer's account)
- Google's security best practices explicitly warn against client-side key exposure
- If the key is stored in localStorage, any XSS attack can exfiltrate it

**Prevention:**
1. The settings page should POST the API key to a backend endpoint (e.g., `POST /api/settings`). The backend stores it in the database (encrypted at rest) or writes it to a Docker secret/env file.
2. The settings page should NEVER display the full API key. Show only the last 4 characters: `****...Xk9M`.
3. The backend validates the key by making a test geocoding request and returns the result (valid/invalid/quota status) without sending the key back.
4. Use the existing `verify_api_key` dependency to protect the settings endpoint.
5. Consider whether this feature is even needed. If the API key rarely changes, `.env` file editing with Docker restart may be acceptable. Over-engineering settings UI for a rarely-changed value adds attack surface.

**Detection:**
Open browser DevTools, navigate to the settings page, and check if the full API key appears in any network request response, localStorage, or React component state.

---

### Pitfall 8: Address Preprocessing Changes Invalidate Geocode Cache

**What goes wrong:**
v3.0 includes "Address preprocessing improvements." The geocode cache is keyed by `normalize_address(cleaned_address)`. Any change to `clean_cdcms_address()` -- adding new word splits, changing abbreviation expansion, fixing garbling -- produces a DIFFERENT cleaned address for the same raw CDCMS input. The normalized key changes, causing cache misses for all previously-cached addresses.

This was already identified in the v2.2 research (previous PITFALLS.md, Pitfall 1), but it is MORE dangerous now because:
1. The cache has grown larger since v2.2 (more addresses cached)
2. The system may now have driver-verified coordinates in the cache (source='driver_verified'), which are more valuable than Google results
3. A cache miss means re-geocoding at $0.005/request. 200 cached addresses becoming misses = $1.00 per upload until re-cached

**Why it happens:**
The cache normalization function (`normalize_address`) operates on the CLEANED address, not the raw CDCMS text. Cleaning changes propagate through to cache keys.

**Consequences:**
- Spike in Google Maps API costs on first upload after preprocessing changes
- Loss of driver-verified geocode matches (high-confidence entries become orphaned in the cache)
- Potential duplicate cache entries: old key pointing to old coordinates, new key pointing to new coordinates for the same physical address

**Prevention:**
1. Before deploying preprocessing changes, run a cache migration script: for each existing cache entry, re-clean the raw address with the NEW preprocessing logic, re-normalize, and INSERT a duplicate entry with the new key pointing to the same coordinates.
2. Build a cache export/import feature BEFORE changing preprocessing. Export all cached geocodes, deploy the preprocessing change, import the cache with re-normalized keys.
3. Add a `address_raw_original` column to `geocode_cache` that stores the completely unprocessed CDCMS text. Normalization can then operate on the original text, making cache keys stable across preprocessing changes.
4. Log cache miss rates after deployment. If cache hits drop below 50%, the preprocessing change may have invalidated too many entries.

**Detection:**
Compare cache hit rates before and after preprocessing changes. A sudden drop from 70%+ to <30% indicates mass cache invalidation.

---

### Pitfall 9: Driver Auto-Creation from CSV Creates Ghost Drivers

**What goes wrong:**
v3.0 includes "Zero-start driver management (auto-create from CSV DeliveryMan column)". The `DeliveryMan` column in CDCMS exports contains driver names like "RAJESH", "SURESH K", "MUJEEB". Auto-creating driver records from these names seems straightforward, but:

1. **Name variations**: The same driver may appear as "RAJESH", "RAJESH K", "RAJESH KUMAR" across different CDCMS exports. Each creates a separate driver record. The system ends up with 3 "Rajesh" drivers who are actually the same person.
2. **Temporary drivers**: Substitute drivers appear in one export and never again. They become permanent records in the `drivers` table.
3. **Name encoding issues**: CDCMS names are ALL-CAPS ASCII. When Title-cased for display ("Rajesh K"), they look different from the original CDCMS value. Subsequent uploads comparing "RAJESH K" (from CSV) to "Rajesh K" (from DB) may or may not match depending on comparison logic.
4. **No unique identifier**: CDCMS does not provide a driver ID, only a name string. Name is a terrible unique key.

**Why it happens:**
CDCMS is a customer management system, not a driver management system. The DeliveryMan field is a free-text entry, not a foreign key to a driver database. Different office employees may type the same driver's name differently.

**Consequences:**
- Driver list grows with duplicates over time
- Route history fragments across duplicate driver records
- Office staff must manually merge/deactivate ghost drivers
- Per-driver analytics (routes/day, average stops) are skewed by fragmented data

**Prevention:**
1. Auto-create drivers with a REVIEW step: "Found new driver names: RAJESH K, MUJEEB. Create as new drivers?" with an option to map to existing drivers.
2. Use fuzzy matching (case-insensitive, whitespace-normalized) when checking if a driver already exists. "RAJESH K" matches "Rajesh K" matches "RAJESH  K".
3. Add a `cdcms_names` array field to the `drivers` table that stores all name variations seen for this driver. Matching checks all aliases.
4. Provide a "Merge Drivers" UI in the dashboard for post-hoc cleanup.
5. Consider a "driver code" field that office staff assigns once (e.g., "D01" for Rajesh) and map CDCMS names to codes via a settings table.

**Detection:**
After 2-3 weeks of uploads, query `SELECT name, COUNT(*) FROM drivers GROUP BY LOWER(TRIM(name)) HAVING COUNT(*) > 1`. If duplicates exist, the auto-creation logic needs fuzzy matching.

---

### Pitfall 10: Changing Routes Table `vehicle_id` Type Breaks Driver PWA Route Fetching

**What goes wrong:**
The driver PWA fetches routes via `GET /api/routes/{vehicle_id}` using the human-readable string like "VEH-01". The `routes.vehicle_id` column is `VARCHAR(20)`. If the new model changes this to a UUID FK to the `drivers` table, or changes the stored value from "VEH-01" to "RAJESH", every existing QR code, bookmarked URL, and offline-cached route in the driver PWA breaks.

The driver PWA (`apps/kerala_delivery/driver_app/index.html`) has 67 references to "vehicle" concepts. It stores the current vehicle_id in memory and uses it for API calls. Changing the identifier format requires updating both the API route parameter AND the PWA's state management.

**Why it happens:**
The temptation to make the API "clean" by using driver IDs everywhere conflicts with the reality that drivers access routes via printed QR codes and saved bookmarks that encode the old URL format.

**Consequences:**
- Printed QR code sheets from previous days stop working
- Drivers' PWA offline cache has routes keyed by "VEH-01" that don't match new "DRIVER-UUID" keys
- The service worker's cached responses become invalid

**Prevention:**
1. Keep the endpoint path as `/api/routes/{vehicle_id}`. Accept BOTH vehicle IDs ("VEH-01") and driver identifiers in the same parameter.
2. In the API handler, try lookup by driver name/code first, then fall back to vehicle_id. This makes the transition transparent.
3. When generating new QR codes, use the driver identifier. Old QR codes with vehicle IDs continue to work via the fallback.
4. Add a redirect: if someone accesses `/api/routes/VEH-01` and VEH-01 is now assigned to driver "RAJESH", the response includes both vehicle_id and driver_name so the PWA can update its display.

**Detection:**
Scan an old QR code after the transition. If it returns 404, the backward compatibility is broken.

---

## Minor Pitfalls

### Pitfall 11: VROOM Single-Vehicle TSP Returns Different Distance Format

**What goes wrong:**
When VROOM receives 1 vehicle and N jobs (TSP mode), its response structure is identical to CVRP, but there is only one route in `routes[]`. The `_parse_response()` method in `vroom_adapter.py` already handles this correctly (it iterates `vroom_result["routes"]`). However, VROOM's step-level `distance` and `duration` fields behave slightly differently with a single vehicle: the route always starts and ends at the depot, so the first and last legs include depot travel. With CVRP, multiple vehicles share the depot, and VROOM may optimize depot assignments differently.

The practical impact is small but can cause test failures if tests assert exact distance values for a CVRP setup and then run the same data through TSP.

**Prevention:**
Update test assertions to be approximate (within 5%) rather than exact when switching between CVRP and TSP modes.

---

### Pitfall 12: Google Maps Directions API 25-Waypoint Limit vs Route Size

**What goes wrong:**
The Google Maps Directions API allows a maximum of 25 intermediate waypoints per request. Kerala delivery routes can have 20-44 stops per driver. Routes with >25 stops must be split into segments, validated separately, and then reassembled. The existing `split_route_into_segments()` function in `qr_helpers.py` (used for Google Maps URL generation) already handles this for QR codes -- but the validation logic needs the same splitting, and the sum of segment distances may not equal the total route distance due to segment overlap (each segment's start/end adds extra depot<->split-point travel).

**Prevention:**
1. Reuse the existing `split_route_into_segments()` logic from `qr_helpers.py` for Directions API validation.
2. When comparing VROOM distance to Google distance for a multi-segment route, compare per-segment, not total. Or accept a 10-15% tolerance for segment boundary effects.
3. Document that routes with >25 stops require multiple API calls (cost implications from Pitfall 4).

---

### Pitfall 13: Settings Persistence Without Database Migration

**What goes wrong:**
Dashboard settings (API key, cache preferences, upload history) need server-side persistence. If settings are stored in a new database table, that requires an Alembic migration. If stored in a config file on the Docker volume, they survive container restarts but not volume recreations. If stored in environment variables, they require Docker restart to take effect.

The project currently uses `.env` for API keys and `config.py` for business constants. Adding a `settings` table is the right approach but adds migration complexity to an already migration-heavy milestone.

**Prevention:**
1. Create a simple `settings` key-value table: `(key VARCHAR PRIMARY KEY, value TEXT, updated_at TIMESTAMPTZ)`. This is flexible enough for API keys, cache preferences, and feature flags.
2. Add this table in the FIRST migration of the milestone, before any other schema changes. This minimizes migration ordering conflicts.
3. The API reads settings from DB on startup and caches in memory. Changes require an API restart OR an explicit cache-invalidation endpoint.

---

### Pitfall 14: Cache Export/Import Loses PostGIS Geometry Data

**What goes wrong:**
Building a geocode cache export feature (for backup or migration) requires serializing PostGIS `geometry(Point, 4326)` columns. A naive `SELECT * FROM geocode_cache` exports WKB (Well-Known Binary) blobs that are unreadable in CSV/JSON. The import side needs to parse these blobs back into PostGIS geometries, requiring `ST_GeomFromWKB()` or coordinate extraction.

**Prevention:**
1. Export as JSON with explicit `latitude`, `longitude` fields extracted via `ST_Y(location)` and `ST_X(location)`.
2. Import using `ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)` -- the same pattern used throughout `repository.py`.
3. Include `address_raw`, `address_norm`, `source`, `confidence`, and `hit_count` in the export. Skip `id` (regenerate UUIDs on import).
4. Handle the `UNIQUE(address_norm, source)` constraint on import: use `ON CONFLICT DO UPDATE` to merge rather than fail.

---

### Pitfall 15: Driver PWA Vehicle Selector Must Become Driver Selector

**What goes wrong:**
The driver PWA currently shows a vehicle selector after upload ("Select your vehicle: VEH-01, VEH-02..."). In the driver-centric model, this should show driver names. But the selector is populated from the API response, which returns `vehicle_id` values. Changing the selector to show driver names requires:
1. The upload response to include driver name mappings
2. The PWA to use driver name (or driver ID) as the route fetch key
3. The route fetch endpoint to accept driver identifiers

If the API changes the response format but the PWA is cached by the service worker, drivers see the OLD selector UI with the NEW data format, causing JavaScript errors.

**Prevention:**
1. Update the service worker cache version when changing API response formats. This forces a re-download of the PWA.
2. Add defensive parsing in the PWA: if `vehicle_id` exists, use it; if `driver_name` exists, prefer it for display.
3. Include both `vehicle_id` and `driver_name` in the API response during the transition period.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation | Severity |
|-------------|---------------|------------|----------|
| Vehicle-to-Driver DB migration | Pitfall 1 (semantic minefield), Pitfall 5 (Alembic drops data) | Add columns, do not rename. Hand-write migrations. | CRITICAL |
| Per-driver TSP optimization | Pitfall 2 (optimizer interface), Pitfall 6 (fleet metrics) | Wrap in PerDriverOptimizer, single run per batch | CRITICAL |
| CDCMS .xlsx support | Pitfall 3 (binary detection) | Fix `_is_cdcms_format()` to handle binary files | CRITICAL |
| Google Maps Directions validation | Pitfall 4 (cost explosion), Pitfall 12 (25-waypoint limit) | User-triggered only, budget caps, reuse segment logic | MODERATE |
| Dashboard settings page | Pitfall 7 (API key exposure), Pitfall 13 (persistence) | Server-side storage, never send full key to browser | MODERATE |
| Address preprocessing | Pitfall 8 (cache invalidation) | Cache migration script, export/import before changes | MODERATE |
| Driver auto-creation | Pitfall 9 (ghost drivers) | Fuzzy matching, review step, alias tracking | MODERATE |
| API URL changes | Pitfall 10 (PWA breakage) | Keep old endpoints working, accept both ID formats | MODERATE |
| Driver PWA updates | Pitfall 15 (cached old version) | Bump SW cache version, include both identifiers | MINOR |
| Cache export/import | Pitfall 14 (PostGIS serialization) | Export as lat/lng JSON, import with ST_MakePoint | MINOR |
| Test updates | Pitfall 11 (distance assertions) | Approximate assertions for TSP vs CVRP | MINOR |

---

## Sources

- Codebase analysis: `core/database/models.py` (8 ORM models), `core/optimizer/vroom_adapter.py` (CVRP implementation), `core/database/repository.py` (all CRUD), `apps/kerala_delivery/api/main.py` (upload + route endpoints), `core/data_import/cdcms_preprocessor.py` (address cleaning pipeline)
- Database schema: `infra/postgres/init.sql` (7 tables, 10 indexes), 6 existing Alembic migrations
- Frontend coupling: 371 "vehicle" references in dashboard, 67 in driver PWA, 129 in Python tests, 80 in E2E specs
- [Alembic autogenerate documentation](https://alembic.sqlalchemy.org/en/latest/autogenerate.html) -- column rename limitations (HIGH confidence)
- [VROOM API documentation](https://github.com/VROOM-Project/vroom/blob/master/docs/API.md) -- TSP as special case of CVRP (HIGH confidence)
- [Google Maps Directions API usage and billing](https://developers.google.com/maps/documentation/directions/usage-and-billing) -- 25 waypoint limit, Advanced SKU pricing (MEDIUM confidence, pricing may shift)
- [Google Maps API pricing restructure March 2025](https://masterconcept.ai/news/google-maps-api-changes-2025-migration-guide-for-directions-api-distance-matrix-api/) -- new billing tiers (MEDIUM confidence)
- [API key security best practices 2025](https://dev.to/hamd_writer_8c77d9c88c188/api-keys-the-complete-2025-guide-to-security-management-and-best-practices-3980) -- never expose keys client-side (HIGH confidence)
- [Google Maps Platform security guidance](https://developers.google.com/maps/api-security-best-practices) -- server-side key storage (HIGH confidence)
