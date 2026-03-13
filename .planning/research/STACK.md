# Technology Stack: v3.0 Driver-Centric Model

**Project:** Kerala LPG Delivery Route Optimizer
**Researched:** 2026-03-12
**Milestone:** v3.0 Driver-Centric Model
**Overall Confidence:** HIGH

## Guiding Principle: Minimal Additions

This milestone adds significant features (driver model, per-driver TSP, Google Maps route validation, geocode cache management, dashboard settings) but requires **zero new Python dependencies** and **zero new npm packages**. Every capability can be built with what already exists in the stack. The v3.0 changes are architectural and data-model level, not technology-level.

---

## Recommended Stack (What to Use for Each Feature)

### 1. Driver-Centric Model (Vehicle-to-Driver Rename)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| SQLAlchemy 2.0 | 2.0.46 (existing) | New `DriverDB` model + schema evolution | Already has a `DriverDB` model in `core/database/models.py` with `name`, `phone`, `vehicle_id` FK, `is_active`. Extend it rather than replace. |
| Alembic | 1.18.4 (existing) | Migration: add columns to `drivers` table, add `driver_id` FK to `routes`, update `optimization_runs` | Async migration infrastructure already proven across 6 migrations. |
| Pydantic | 2.12.5 (existing) | New `Driver` Pydantic model in `core/models/` | Follow existing pattern: DB model (`DriverDB`) + Pydantic model (`Driver`) + repository functions. |

**What to change, not add:**
- The existing `DriverDB` ORM model already exists with the right fields (`name`, `phone`, `vehicle_id`, `is_active`). No new table -- just add columns and make it a first-class entity.
- The `RouteDB` model already has `driver_name: str`. Evolve it to `driver_id: UUID` FK referencing `drivers.id`, keeping `driver_name` as a denormalized display field.
- The `VehicleDB` model stays. Vehicles are still physical assets. The conceptual shift is: routes belong to **drivers**, not vehicles. Drivers may or may not have an assigned vehicle.
- CDCMS `DeliveryMan` column is already parsed by `cdcms_preprocessor.py` (line 58: `CDCMS_COL_DELIVERY_MAN = "DeliveryMan"`). Currently stored as `delivery_man` in preprocessed DataFrame. Wire this to auto-create/lookup `DriverDB` records.

**Confidence:** HIGH -- all components exist in the codebase. This is a wiring change, not a technology change.

### 2. Per-Driver TSP Optimization

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| VROOM | Docker `vroomvrp/vroom-docker` (existing) | TSP optimization per driver | VROOM handles single-vehicle optimization natively. Submit 1 vehicle + N jobs = TSP solve. Already proven with the multi-vehicle CVRP flow. |
| OSRM | v5.27.1 Docker (existing) | Distance matrix computation for VROOM | No changes needed. VROOM talks to OSRM internally. |

**Architecture decision: VROOM TSP, not a custom TSP solver.**

VROOM already solves TSP as a special case of VRP. When you submit a VROOM request with exactly 1 vehicle and N jobs, VROOM solves the Travelling Salesman Problem for that vehicle. The existing `VroomAdapter._build_request()` builds the vehicles/jobs arrays -- calling it N times (once per driver) with a single vehicle each time produces N independent TSP solutions.

**Why NOT add OR-Tools or a custom nearest-neighbor solver:**
- VROOM already handles this exact case in milliseconds
- The existing `VroomAdapter` code, error handling, safety multiplier, and response parsing all work unchanged
- Adding OR-Tools would introduce a 200+ MB dependency (google-ortools) for no benefit
- A custom nearest-neighbor heuristic would give worse route quality than VROOM's meta-heuristics

**Implementation approach:**
1. Group orders by driver (from CDCMS `DeliveryMan` column)
2. For each driver's order set, create a single `Vehicle` with the driver's depot
3. Call `VroomAdapter.optimize(driver_orders, [driver_vehicle])` per driver
4. Merge results into a combined `RouteAssignment`

This is a ~50-line wrapper around the existing optimizer, not a new optimization engine.

**Confidence:** HIGH -- tested the concept by reading VROOM API docs. Single-vehicle requests are explicitly supported. The existing adapter handles this without modification.

### 3. Google Maps Route Validation

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| httpx | 0.28.1 (existing) | HTTP POST to Google Routes API `computeRoutes` endpoint | Already used for OSRM and VROOM API calls throughout the codebase. No new HTTP library needed. |
| Google Routes API | v2 (Compute Routes) | Compare OSRM route distance/duration with Google's estimate | Replaces the deprecated Directions API. POST-based with field masking for efficient responses. |

**Why Google Routes API, not Directions API:**
- Directions API and Distance Matrix API were deprecated (moved to Legacy status) on March 1, 2025
- Routes API supports 25 intermediate waypoints (vs 10 for legacy Directions)
- Routes API uses POST with JSON body (cleaner than GET with URL params)
- Same pricing tier for basic use: $5 per 1,000 requests (Essentials SKU)
- $200/month free credit covers 40,000 geocoding requests OR separate Compute Routes budget

**API integration details:**

```
Endpoint: POST https://routes.googleapis.com/directions/v2:computeRoutes
Headers:
  X-Goog-Api-Key: {GOOGLE_MAPS_API_KEY}  # Same key as geocoding
  X-Goog-FieldMask: routes.distanceMeters,routes.duration
  Content-Type: application/json
Body:
  {
    "origin": {"location": {"latLng": {"latitude": N, "longitude": N}}},
    "destination": {"location": {"latLng": {"latitude": N, "longitude": N}}},
    "intermediates": [  # waypoints
      {"location": {"latLng": {"latitude": N, "longitude": N}}}
    ],
    "travelMode": "DRIVE",
    "units": "METRIC"
  }
```

**Pricing impact:**
- Essentials (basic routing, up to 10 waypoints): $5 per 1,000 requests
- Pro (11-25 waypoints or traffic-aware): $10 per 1,000 requests
- Most driver routes have <10 stops, so Essentials tier applies
- At 13 drivers/day = 13 validation requests/day = ~390/month = well within free tier
- Do NOT request `TRAFFIC_AWARE` routing preference -- it bumps to Pro tier ($10/1000) and is unnecessary for validation

**Implementation approach:**
- New module: `core/routing/google_routes_adapter.py` implementing the `RoutingEngine` protocol
- Call after VROOM optimization completes, for each route
- Compare OSRM distance/duration with Google distance/duration
- Flag routes where Google's estimate diverges by >20% as "needs review"
- This is a confidence metric, not a blocker -- OSRM routes are used regardless
- Store comparison results in the route response for dashboard display

**What NOT to do:**
- Do NOT install `googlemaps` Python package. It wraps the legacy Directions API. Use raw httpx POST to the Routes API endpoint directly. This matches the existing pattern (GoogleGeocoder uses httpx, VroomAdapter uses httpx, OsrmAdapter uses httpx).
- Do NOT use `TRAFFIC_AWARE` or `TRAFFIC_AWARE_OPTIMAL` routing preferences. They double the cost ($10/1000) and add latency. For validation purposes, basic routing is sufficient.
- Do NOT request polyline geometry. We only need `distanceMeters` and `duration` for comparison. Polylines would waste bandwidth and processing.

**Confidence:** HIGH -- verified endpoint URL, request format, pricing tiers, and field mask headers via official Google documentation.

### 4. Geocode Cache Export/Import

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python stdlib `json` | 3.12 (existing) | JSON export/import format for geocode cache | Human-readable, inspectable, and the cache is small (~400 entries currently). |
| Python stdlib `csv` | 3.12 (existing) | CSV export format (alternative to JSON) | For users who want to open the cache in Excel for inspection. |
| SQLAlchemy 2.0 | 2.0.46 (existing) | Bulk read/write of `geocode_cache` table | Repository already has `get_cached_geocode()` and `save_geocode_cache()`. Add `export_all_geocodes()` and `import_geocodes_batch()`. |
| GeoAlchemy2 | 0.18.1 (existing) | Point geometry serialization for export | `to_shape()` already used throughout the codebase. |

**Export format (JSON):**
```json
{
  "version": 1,
  "exported_at": "2026-03-12T10:30:00Z",
  "count": 387,
  "entries": [
    {
      "address_raw": "...",
      "address_norm": "...",
      "latitude": 11.624,
      "longitude": 75.579,
      "source": "google",
      "confidence": 0.95,
      "hit_count": 12,
      "created_at": "2026-01-15T...",
      "last_used_at": "2026-03-10T..."
    }
  ]
}
```

**Why JSON, not pg_dump:**
- pg_dump requires PostgreSQL client tools and knowledge of connection strings
- JSON is portable -- can be loaded into a fresh system, a different PostgreSQL instance, or even a different database entirely
- The office user can email the file or copy it on a USB drive
- Human-inspectable for debugging

**API endpoints:**
- `GET /api/geocode-cache/export` -- returns JSON file download
- `POST /api/geocode-cache/import` -- accepts JSON file upload, merges with existing cache
- `GET /api/geocode-cache/stats` -- returns cache statistics (total entries, source breakdown, oldest/newest, total hit count)

**Confidence:** HIGH -- no new technology. Standard repository pattern with JSON serialization.

### 5. Dashboard Settings Management

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| React 19 | 19.2.0 (existing) | Settings page component | New page in the dashboard sidebar. |
| DaisyUI 5 | 5.5.19 (existing) | Form inputs (text, toggle), cards, tabs | Existing component library already used throughout the dashboard. |
| FastAPI | 0.129.1 (existing) | Settings API endpoints | `GET /api/settings`, `PUT /api/settings` |
| PostgreSQL | 15 (existing) | `settings` table for key-value pairs | Simple table: `key VARCHAR PRIMARY KEY, value TEXT, updated_at TIMESTAMPTZ`. |

**API key management approach: Server-side storage with masked display.**

The Google Maps API key is currently read from `GOOGLE_MAPS_API_KEY` environment variable at API startup. For the dashboard settings feature:

1. Add a `settings` table to PostgreSQL (key-value store)
2. The dashboard sends the API key to `PUT /api/settings` with key `google_maps_api_key`
3. The API stores it in the database (NOT encrypted -- it's a server-side secret that the API itself needs in cleartext to call Google)
4. The API reads the key from database on each request, falling back to the environment variable
5. `GET /api/settings` returns the key masked (e.g., `AIza...****1234`) -- never the full key
6. The dashboard shows a text input with the masked value and a "Save" button

**Why NOT encrypt the API key in the database:**
- The API server needs the key in cleartext to make Google API calls
- Encryption with Fernet/AES would require a separate encryption key, stored... where? On the same server. This is security theater.
- The threat model here is an office employee accidentally exposing the key in the dashboard UI, which masking handles
- The PostgreSQL database is on the same Docker network as the API, behind the same auth layer

**Why NOT use localStorage/sessionStorage for the API key:**
- The key is a server-side secret used by the FastAPI backend, not the browser
- Storing it in the browser would require sending it with every upload request, exposing it to XSS
- The backend-for-frontend pattern is correct: browser sends to our API, our API uses the key

**What NOT to add:**
- Do NOT add the `cryptography` package (Fernet) for API key encryption. Overhead without security benefit in this deployment model.
- Do NOT add a separate auth system for settings. The existing `X-API-Key` header auth protects write endpoints.
- Do NOT add react-hook-form or formik. The settings page has ~3-4 fields. Native React state is sufficient.

**Confidence:** HIGH -- follows established patterns in the codebase. The dashboard already has a similar pattern with `VITE_API_KEY` for dashboard-to-API auth.

### 6. Upload History

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| SQLAlchemy 2.0 | 2.0.46 (existing) | Query `optimization_runs` table with filters | Table already exists with `source_filename`, `created_at`, `total_orders`, `status`. |
| React 19 | 19.2.0 (existing) | Enhanced Run History page | The `RunHistory.tsx` page already exists. Extend it with filters and detail view. |

**The upload history feature requires zero new storage.** The `optimization_runs` table already captures everything needed:
- `source_filename`: Original CSV filename
- `created_at`: When the upload happened
- `total_orders`, `orders_assigned`, `orders_unassigned`: Import stats
- `vehicles_used`: Fleet utilization
- `optimization_time_ms`: Performance metric
- `status`: completed/failed/running

The existing `GET /api/runs` endpoint already returns this data. Enhance it with:
- Pagination (`?page=1&per_page=10`)
- Date range filter (`?from=2026-03-01&to=2026-03-12`)
- Status filter (`?status=completed`)

**Confidence:** HIGH -- purely UI enhancement on existing data.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| TSP Solver | VROOM (existing) | Google OR-Tools | 200+ MB dependency, slower solve times, no benefit for single-vehicle TSP. VROOM already does this. |
| TSP Solver | VROOM (existing) | Custom nearest-neighbor | Worse route quality than VROOM's meta-heuristics. Reinventing the wheel. |
| Route Validation API | Google Routes API v2 | Google Directions API (Legacy) | Deprecated March 2025. Still functional but no longer recommended. Routes API has better pricing and more waypoints. |
| Route Validation API | Google Routes API v2 | `googlemaps` Python package | Wraps the legacy Directions API. Not updated for Routes API v2. Use raw httpx instead. |
| Settings Storage | PostgreSQL key-value table | .env file editing | Not accessible from dashboard UI. Requires server restart. |
| Settings Storage | PostgreSQL key-value table | Redis | Adds a new service to Docker Compose for ~5 key-value pairs. Massive overkill. |
| Settings Storage | PostgreSQL key-value table | SQLite | Adds a second database to the stack. PostgreSQL is already running and has ample capacity. |
| Cache Export Format | JSON | pg_dump | Requires PostgreSQL CLI knowledge. Not portable. Not human-readable. |
| Cache Export Format | JSON | GeoJSON | Adds unnecessary GeoJSON wrapper structure. Plain JSON with lat/lon fields is simpler and sufficient. |
| API Key Encryption | None (masked display) | Fernet symmetric encryption | Security theater -- the decryption key would be on the same server. Masking in UI responses is sufficient. |
| Form Library | Native React state | react-hook-form | Adds a dependency for 3-4 form fields. Overkill. |
| HTTP Client | httpx (existing) | `googlemaps` pip package | Legacy API wrapper. Does not support Routes API v2. Adds dependency for no benefit. |
| Driver Management | Extend existing DriverDB | New Driver microservice | This is a monolith with 4 Docker services. Adding a microservice for driver CRUD would be absurd at this scale. |

---

## Stack Summary: What Changes

### Python Backend (zero new packages)

| Existing Package | Current Use | New Use in v3.0 |
|-----------------|-------------|------------------|
| SQLAlchemy 2.0 | ORM for all tables | New `settings` table, extended `drivers` queries, driver-grouped optimization |
| Alembic | Schema migrations | Add `settings` table, add `driver_id` to `routes`, add columns to `drivers` |
| httpx | Google Geocoding, OSRM, VROOM API calls | Google Routes API validation calls (same pattern) |
| Pydantic | API request/response models | New `Driver`, `Settings`, `CacheExport` models |
| FastAPI | All API endpoints | New endpoints: settings CRUD, cache export/import, driver CRUD |

### Dashboard (zero new packages)

| Existing Package | Current Use | New Use in v3.0 |
|-----------------|-------------|------------------|
| React 19 | All pages | New Settings page, enhanced Upload/Run History pages |
| DaisyUI 5 | UI components | Form inputs for settings, driver badges in route cards |
| lucide-react | Navigation icons | Settings icon (wrench/gear) in sidebar |
| Tailwind v4 | Styling | Same patterns, no changes |

### Infrastructure (zero new services)

| Existing Service | Current Use | New Use in v3.0 |
|-----------------|-------------|------------------|
| PostgreSQL + PostGIS | All persistence | New `settings` table, extended driver queries |
| OSRM | Distance matrices | Same (VROOM uses internally for TSP) |
| VROOM | Multi-vehicle CVRP | Per-driver TSP (single-vehicle requests) |
| Docker Compose | Orchestration | Same services, no additions |

---

## Installation

No installation needed. Zero new dependencies.

```bash
# Existing setup works for v3.0
docker compose up -d

# Database migration (auto-runs on docker compose up via db-init)
# Manual if needed:
alembic upgrade head
```

---

## Version Compatibility Notes

| Technology | Pinned Version | Latest Available | Action |
|------------|---------------|------------------|--------|
| VROOM Docker | vroomvrp/vroom-docker (latest) | Tracked upstream | No pin needed -- VROOM API is stable |
| OSRM Docker | v5.27.1 (pinned) | v5.27.1 | Already pinned per v1.3 decision |
| Google Routes API | v2 | v2 | Current version, no migration needed |
| Python | 3.12 | 3.13 | Stay on 3.12 (stable, all deps compatible) |
| Node.js | v24 | v24 | Current LTS-adjacent, no change needed |

---

## Pricing Impact Assessment

### Google Maps API Cost for Route Validation

| Metric | Value |
|--------|-------|
| Validation requests per day | ~13 (one per driver route) |
| Requests per month | ~390 |
| SKU | Compute Routes Essentials ($5/1000) |
| Monthly cost | ~$1.95 |
| Free tier coverage | 10,000 free events/month (Essentials) |
| Net cost | $0 (well within free tier) |

### Existing Google Maps Costs (unchanged)

| API | Usage | Monthly Cost |
|-----|-------|-------------|
| Geocoding | ~40-50 orders/day, ~80% cache hit rate | ~$1.50 (within $200 free credit) |
| Route Validation (new) | ~13 routes/day | $0 (within free tier) |

**Total incremental cost: $0/month.** Route validation fits entirely within Google's free tier.

---

## Sources

- [Google Maps Routes API Usage and Billing](https://developers.google.com/maps/documentation/routes/usage-and-billing) -- pricing tiers, free tier limits
- [Google Maps Routes API Compute Routes](https://developers.google.com/maps/documentation/routes/compute_route_directions) -- POST endpoint, request/response format
- [Google Maps Directions API Migration Guide](https://developers.google.com/maps/documentation/routes/migrate-routes) -- legacy API deprecation, parameter renaming
- [Google Maps Platform Pricing](https://developers.google.com/maps/billing-and-pricing/pricing) -- $5/1000 Essentials, $10/1000 Pro, $15/1000 Enterprise
- [VROOM Project GitHub](https://github.com/VROOM-Project/vroom) -- single-vehicle TSP as VRP special case
- [VROOM API Documentation](https://github.com/VROOM-Project/vroom/blob/master/docs/API.md) -- request format, vehicles/jobs arrays
