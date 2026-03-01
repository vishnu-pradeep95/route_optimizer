# Architecture Research

**Domain:** Logistics SaaS UI overhaul + geocoding data integrity fixes for Kerala LPG delivery
**Researched:** 2026-03-01
**Confidence:** HIGH

## System Overview -- Current State

```
Dashboard (React/TS)                  Driver PWA (Vanilla JS)
    Vite + TW4/DaisyUI                  Static HTML, inline CSS/JS
    Port 5173 (dev)                      Served by FastAPI
         |                                     |
         |  /api/*                             |  /api/routes/{id}
         v                                     v
    +-------------------------------------------------+
    |              FastAPI Backend (8000)               |
    |  upload-orders | routes | telemetry | vehicles   |
    |  geocoding pipeline | QR generation              |
    +---------+----------+----------+------------------+
              |          |          |
    +---------+   +------+   +-----+--------+
    |PostGIS  |   |OSRM  |   |Google        |
    |DB (5432)|   |(5000) |   |Geocoding API |
    +---------+   +------+   +-----+--------+
                      |                |
                  +---+---+    +-------+-------+
                  | VROOM |    | File Cache    |
                  | (3000)|    | (JSON on disk)|
                  +-------+    +---------------+
```

## v1.1 Integration Architecture -- What Changes

The three workstreams (dashboard UI, driver PWA, geocoding fixes) touch different layers but share common integration points. This section maps exactly what is new vs modified.

### Workstream A: Dashboard UI Overhaul

**Goal:** Transform prototype-feeling React pages into clean, professional logistics SaaS.

**What gets modified (no new structural components needed):**

| File | Change Type | What Changes |
|------|-------------|--------------|
| `src/index.css` | Heavy rewrite | DaisyUI theme tokens already defined. Remaining work: migrate custom CSS properties to use DaisyUI utility classes across pages. |
| `src/App.css` | Moderate rewrite | Sidebar layout already uses CSS custom properties. Refine spacing, transitions, and polish with DaisyUI `tw:menu` and `tw:drawer` patterns. |
| `src/App.tsx` | Minor | NAV_ITEMS icons: replace emoji with proper icon components (Lucide or Heroicons via SVG). No structural changes -- sidebar+content layout is sound. |
| `src/pages/UploadRoutes.tsx` | Heavy rewrite (CSS) | Replace custom CSS classes with DaisyUI: `tw:card`, `tw:btn`, `tw:file-input`, `tw:alert`, `tw:progress`, `tw:table`. The logic (upload, parse response, show summary) stays. |
| `src/pages/UploadRoutes.css` | Heavy rewrite or delete | Move styles to DaisyUI utility classes inline. |
| `src/pages/LiveMap.tsx` + `.css` | Moderate rewrite | Map container stays. Sidebar panel for vehicle list becomes `tw:card` with `tw:badge` for status. |
| `src/pages/RunHistory.tsx` + `.css` | Moderate rewrite | Table becomes `tw:table` with `tw:badge` for status columns. |
| `src/pages/FleetManagement.tsx` + `.css` | Moderate rewrite | Form becomes `tw:form-control` + `tw:input`. Table becomes `tw:table`. Modal becomes `tw:modal`. |
| `src/components/StatsBar.tsx` + `.css` | Moderate rewrite | Stat cards become `tw:stats` components. |
| `src/components/VehicleList.tsx` + `.css` | Moderate rewrite | List items become DaisyUI cards or list components. |
| `src/components/RouteMap.tsx` + `.css` | Light touch | Map rendering logic unchanged. Container styling updated. |

**New dashboard components needed:**

| Component | Purpose | Why New |
|-----------|---------|--------|
| `src/components/GeocodingStats.tsx` | Show cache hit vs API call counts per upload | Surfaces geocoding cost data from new API fields |
| `src/components/DuplicateLocationAlert.tsx` | Warn about orders with same GPS coordinates | New feature: duplicate detection results display |

**Architecture pattern:** The dashboard already uses page-level CSS files alongside TSX. The v1.1 approach: migrate each page from custom CSS to DaisyUI utility classes in the TSX (using `tw:` prefix), then delete the corresponding CSS file once the page is fully migrated. This avoids maintaining two styling systems.

**No new API endpoints needed for dashboard UI overhaul.** The existing data shapes (`RoutesResponse`, `RouteDetail`, `UploadResponse`) are sufficient. The `UploadResponse` already includes `geocoded`, `failed_geocoding`, and `failures[]` which provide the data for geocoding stats display. New fields for cost tracking and duplicate detection are added in Workstream C.

### Workstream B: Driver PWA Refresh

**Goal:** Improve outdoor readability, simplify next-stop flow, strengthen offline.

**What gets modified:**

| File | Change Type | What Changes |
|------|-------------|--------------|
| `driver_app/index.html` | Heavy rewrite (CSS + JS) | Single monolithic file (~51KB). All CSS is inline `<style>`, all JS is inline `<script>`. |
| `driver_app/sw.js` | Moderate | Enhanced offline: cache route data in Cache API (not just localStorage), add background sync for status updates. |
| `driver_app/manifest.json` | Light | Update theme_color if design changes. Add proper icon files. |
| `driver_app/tailwind.css` | Regenerate | Re-run `scripts/build-pwa-css.sh` after any Tailwind class changes in index.html. |

**Critical constraint:** The driver PWA MUST remain a standalone HTML/JS app with no build step. Drivers install it as a PWA on their phones. The service worker caches `index.html` as a single resource. Any architectural change that introduces a build step or splits into multiple files would break the existing install flow.

**New PWA features requiring no API changes:**

| Feature | Implementation | Where |
|---------|---------------|-------|
| Simplified next-stop flow | Show only current + next stop prominently; collapse completed stops. JS state machine: `LOADING -> NAVIGATING -> AT_STOP -> NAVIGATING -> COMPLETE` | `index.html` script section |
| High-contrast outdoor mode | Already dark-first (WCAG AAA). Increase font sizes for saffron accent text. Add `prefers-contrast: more` media query. | `index.html` style section |
| Offline route persistence | Move route data from `localStorage` to Cache API via service worker. Cache API has larger storage quota and better eviction behavior. | `sw.js` + `index.html` |
| Background sync | Register `sync` event for delivery status updates queued while offline. Replay when connection returns. | `sw.js` |

**No PWA API changes needed for v1.1.** The current `GET /api/routes/{vehicle_id}` response has all data the PWA needs.

### Workstream C: Geocoding Cache Normalization + Duplicate Detection + Cost Tracking

**Goal:** Fix data integrity issues where the same address gets different cache keys in different systems, add duplicate GPS coordinate detection, and track geocoding costs.

#### The Normalization Bug

There are two independent caching layers with **different normalization algorithms:**

```
GoogleGeocoder (file cache)              Repository (PostGIS cache)
-----------------------------------      --------------------------
_address_hash(address):                  get_cached_geocode(session, addr):
  normalized = " ".join(                   normalized = addr.strip().lower()
    address.lower().split()                # Only strips outer whitespace
  )                                        # Inner whitespace preserved
  # Collapses ALL whitespace
  # "MG  Road,  Kochi"                    # "MG  Road,  Kochi"
  #  -> "mg road, kochi"                  #  -> "mg  road,  kochi"
  #  -> SHA-256[:16]                      # (no hashing, raw string match)
  return hash
```

**Consequence:** The same address can be cached in the file cache but miss in the PostGIS cache (or vice versa), causing:
1. Duplicate API calls (cost waste)
2. Two different geocoded coordinates for the same address stored in different caches (data integrity)
3. The upload endpoint (line 855 in main.py) checks PostGIS first, then falls back to GoogleGeocoder which has its own file cache -- these can return different results for the same address

#### Fix Architecture

**New shared module:**

```
core/geocoding/normalize.py        # NEW -- single source of truth
  normalize_address(address: str) -> str
```

This function becomes the ONE normalization used everywhere:

| Caller | Current Normalization | After Fix |
|--------|----------------------|-----------|
| `GoogleGeocoder._address_hash()` | `" ".join(address.lower().split())` + SHA-256 | `normalize_address(address)` + SHA-256 |
| `repository.get_cached_geocode()` | `address_raw.strip().lower()` | `normalize_address(address)` |
| `repository.save_geocode_cache()` | `address_raw.strip().lower()` | `normalize_address(address)` |
| `CachedGeocoder.geocode()` | Delegates to repo (uses repo normalization) | Uses `normalize_address()` through repo |

**Migration concern:** Existing `geocode_cache` rows have `address_norm` values using the old `strip().lower()` normalization. A data migration must re-normalize all existing rows:

```python
# Alembic migration: re-normalize address_norm column
from core.geocoding.normalize import normalize_address

def upgrade():
    # Read all rows, re-normalize, update in batch
    connection.execute(
        text("UPDATE geocode_cache SET address_norm = :norm WHERE id = :id"),
        [{"id": row.id, "norm": normalize_address(row.address_raw)}
         for row in rows]
    )
```

**Files modified for normalization fix:**

| File | Change |
|------|--------|
| `core/geocoding/normalize.py` | **NEW** -- `normalize_address()` function |
| `core/geocoding/google_adapter.py` | Use `normalize_address()` in `_address_hash()` |
| `core/database/repository.py` | Use `normalize_address()` in `get_cached_geocode()` and `save_geocode_cache()` |
| `infra/alembic/versions/xxx_normalize_cache.py` | **NEW** -- migration to re-normalize existing data |

#### Duplicate Location Detection

**What:** Flag orders that geocode to the same GPS coordinates (within 50m threshold). This often indicates address normalization issues or genuinely shared locations (e.g., apartment buildings).

**Architecture decision:** Use PostGIS `ST_DWithin()` -- not application-level distance math. PostGIS uses the existing GiST spatial index on `geocode_cache.location` for O(n log n) lookups vs O(n^2) in application code. At 50 orders this does not matter performance-wise, but it is the correct pattern for spatial queries and avoids reinventing distance calculations.

**Implementation approach:**

| Component | Change |
|-----------|--------|
| `core/database/repository.py` | **NEW function:** `find_duplicate_locations(session, orders, threshold_m=50) -> list[DuplicateGroup]` using ST_DWithin |
| `apps/kerala_delivery/api/main.py` | Call `find_duplicate_locations()` after geocoding, include results in `OptimizationSummary` response |
| `core/models/` (new file or extend route.py) | **NEW model:** `DuplicateGroup(BaseModel)` -- group of order_ids sharing a location |
| Dashboard `UploadRoutes.tsx` | Show duplicate warnings in upload results (new `DuplicateLocationAlert` component) |

#### Geocoding Cost Tracking

**What:** Track which addresses hit the cache vs called the Google API, so operators can see geocoding costs per upload.

**Current state:** The upload endpoint already tracks `geocoded` count and `failed_geocoding` count in `OptimizationSummary`. But it does not distinguish cache hits from API calls.

**Implementation approach:**

| Component | Change |
|-----------|--------|
| `apps/kerala_delivery/api/main.py` | Track `cache_hits` and `api_calls` counters in the geocoding loop (lines 852-898). Add to `OptimizationSummary` response model. |
| `OptimizationSummary` Pydantic model | Add fields: `geocode_cache_hits: int`, `geocode_api_calls: int` |
| Dashboard `UploadRoutes.tsx` | Display cache hit rate badge in the import summary UI |
| Dashboard `types.ts` | Add `geocode_cache_hits` and `geocode_api_calls` to `UploadResponse` |

**No new database tables.** Cost tracking is per-upload metadata, not persistent historical data. The `CachedGeocoder.stats` dict already tracks hits/misses -- the upload endpoint just needs to surface it in the response.

## Component Responsibilities

| Component | Responsibility | v1.1 Changes |
|-----------|----------------|-------------|
| `core/geocoding/normalize.py` | **NEW** Single normalization algorithm for all address matching | Foundation for cache fix |
| `core/geocoding/google_adapter.py` | Google Maps API calls + file cache | Use shared normalizer |
| `core/geocoding/cache.py` | PostGIS cache decorator around upstream geocoder | No changes (delegates to repo) |
| `core/database/repository.py` | PostGIS cache CRUD + new duplicate detection | Use shared normalizer + new `find_duplicate_locations()` |
| `apps/kerala_delivery/api/main.py` | Upload endpoint orchestration | Add cost tracking counters, duplicate detection call, new response fields |
| `apps/kerala_delivery/dashboard/` | React dashboard UI | CSS overhaul with DaisyUI, new geocoding stats + duplicate alert components |
| `apps/kerala_delivery/driver_app/` | Driver PWA | CSS refresh, simplified next-stop flow, enhanced offline |

## Data Flow Changes

### Current Geocoding Flow (Buggy)

```
Upload CSV
  -> Parse orders
  -> For each ungeooded order:
       1. repo.get_cached_geocode(session, address)  [normalize: strip().lower()]
          -> PostGIS cache lookup
       2. If miss: geocoder.geocode(address)          [normalize: " ".join(lower().split()) -> SHA-256]
          -> Check file cache (JSON)
          -> If file miss: Google API call
          -> Save to file cache
       3. repo.save_geocode_cache(session, ...)       [normalize: strip().lower()]
          -> Save to PostGIS cache

PROBLEM: Step 1 and Step 2 use different normalization.
"Near SBI,  MG Road" normalizes to:
  PostGIS: "near sbi,  mg road"  (double space preserved)
  File:    "near sbi, mg road"   (double space collapsed -> different key)
```

### Fixed Geocoding Flow

```
Upload CSV
  -> Parse orders
  -> For each ungeooded order:
       1. normalize_address(address)               [SHARED: collapse ws, lowercase, strip]
       2. repo.get_cached_geocode(session, norm)
          -> PostGIS cache lookup
       3. If miss: geocoder.geocode(address)
          -> Check file cache (uses SAME normalize_address -> SHA-256)
          -> If file miss: Google API call
          -> Save to file cache
       4. repo.save_geocode_cache(session, ...)    [uses SAME normalize_address]
  -> Count cache_hits vs api_calls                 [NEW: cost tracking]
  -> find_duplicate_locations(session, orders)      [NEW: duplicate detection]
  -> Return OptimizationSummary with new fields
```

### Dashboard UI Data Flow (Unchanged)

```
User navigates to page
  -> React component mounts
  -> Calls api.ts fetch function
  -> GET /api/{endpoint}
  -> Renders data with DaisyUI components

No state management library. Each page fetches its own data.
This is correct for 4 pages with no shared state.
```

### Driver PWA Data Flow (Enhanced Offline)

```
Current:
  Driver opens URL -> fetch /api/routes/{id} -> localStorage -> render
  Offline: read localStorage, queue status updates

Enhanced:
  Driver opens URL -> fetch /api/routes/{id} -> Cache API + localStorage -> render
  Offline: read Cache API (larger quota), queue status via BackgroundSync
  Online again: BackgroundSync replays queued status updates
```

## Recommended Project Structure for New Code

```
core/
  geocoding/
    normalize.py              # NEW -- shared normalization function
    google_adapter.py         # MODIFIED -- use normalize_address()
    cache.py                  # NO CHANGE
    interfaces.py             # NO CHANGE

core/database/
    repository.py             # MODIFIED -- use normalize_address(), add find_duplicate_locations()
    models.py                 # NO CHANGE (schema unchanged, data migrated)

apps/kerala_delivery/
  api/
    main.py                   # MODIFIED -- cost tracking, duplicate detection, new response fields
  dashboard/src/
    index.css                 # MODIFIED -- DaisyUI theme refinements
    App.tsx                   # LIGHT TOUCH -- icon swap
    App.css                   # MODIFIED -- DaisyUI sidebar patterns
    pages/
      UploadRoutes.tsx        # HEAVY REWRITE (CSS only, logic stays)
      UploadRoutes.css        # DELETE after migration to DaisyUI utilities
      LiveMap.tsx + .css      # MODERATE REWRITE
      RunHistory.tsx + .css   # MODERATE REWRITE
      FleetManagement.tsx + .css  # MODERATE REWRITE
    components/
      GeocodingStats.tsx      # NEW -- cache hit/API call breakdown display
      DuplicateLocationAlert.tsx  # NEW -- duplicate GPS coordinate warning
      StatsBar.tsx + .css     # MODERATE REWRITE
      VehicleList.tsx + .css  # MODERATE REWRITE
      RouteMap.tsx + .css     # LIGHT TOUCH
  driver_app/
    index.html                # HEAVY REWRITE (CSS + JS for UX improvements)
    sw.js                     # MODERATE REWRITE (Cache API, BackgroundSync)
    manifest.json             # LIGHT TOUCH
    tailwind.css              # REGENERATE

infra/alembic/versions/
    xxx_normalize_geocode_cache.py  # NEW -- migration to re-normalize existing data

tests/
  core/geocoding/
    test_normalize.py         # NEW -- test shared normalization
  core/database/
    test_duplicate_detection.py  # NEW -- test ST_DWithin duplicate logic
```

## Architectural Patterns

### Pattern 1: DaisyUI with Tailwind Prefix for Collision Safety

**What:** Tailwind 4 is configured with `prefix(tw)` in `index.css`, meaning all Tailwind utilities use `tw:` prefix (e.g., `tw:flex`, `tw:p-4`). DaisyUI component classes also use the prefix (`tw:btn`, `tw:card`). This prevents collisions with existing CSS custom properties that use `--color-*` names.

**When to use:** Always when adding new styles in the dashboard. Never write raw CSS classes when a DaisyUI component exists.

**Trade-off:** Slightly more verbose class names (`tw:btn tw:btn-primary` vs `btn btn-primary`), but eliminates CSS specificity wars.

### Pattern 2: Single Normalization Module

**What:** Extract address normalization into `core/geocoding/normalize.py` as the single source of truth. Every component that needs to match addresses imports from here.

**When to use:** Any time address comparison or cache lookup occurs. Never inline normalization logic.

**Trade-off:** One more import, but eliminates an entire class of cache inconsistency bugs.

```python
# core/geocoding/normalize.py
def normalize_address(address: str) -> str:
    """Normalize an address for cache lookup.

    Rules:
    1. Lowercase
    2. Collapse all whitespace to single space
    3. Strip leading/trailing whitespace
    4. Strip trailing commas/periods

    This is the ONLY normalization used for geocode cache keys.
    If you change this, you MUST run the migration to re-normalize
    all existing geocode_cache rows.
    """
    return " ".join(address.lower().split()).rstrip(",.")
```

### Pattern 3: PostGIS for Spatial Queries (Not Application Code)

**What:** Use ST_DWithin for duplicate detection instead of computing haversine distances in Python.

**When to use:** Any spatial comparison (proximity, containment, distance).

**Trade-off:** Requires database roundtrip, but PostGIS uses spatial indexes (GiST) for efficient lookups vs O(n^2) pairwise distance calculations in application code.

```python
# core/database/repository.py -- new function
async def find_duplicate_locations(
    session: AsyncSession,
    orders: list[Order],
    threshold_m: float = 50.0,
) -> list[DuplicateGroup]:
    """Find orders that resolved to the same GPS coordinates (within threshold).

    Uses PostGIS ST_DWithin with the GiST spatial index on orders.location.
    Returns groups of order_ids where all orders in a group are within
    threshold_m meters of each other.
    """
    # Implementation uses ST_DWithin(a.location, b.location, threshold_m)
    # with a self-join on geocoded orders
    ...
```

### Pattern 4: Service Worker Cache Versioning for Static CSS

**What:** When the pre-compiled `tailwind.css` for the driver PWA changes, the service worker `CACHE_VERSION` constant must be bumped so browsers fetch the new file.

**When to use:** Every time PWA HTML or styling changes.

**Current implementation already follows this pattern:**
```javascript
const CACHE_VERSION = 'v3';  // bump this when tailwind.css changes
const CACHE_NAME = `lpg-driver-${CACHE_VERSION}`;
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Splitting the Driver PWA into Multiple Files

**What people do:** Separate CSS/JS into external files for maintainability.
**Why it is wrong:** The service worker caches `./index.html` as the single app shell resource. Splitting files requires updating `APP_SHELL` in `sw.js`, and any cache miss on a JS/CSS file means a broken offline experience. The monolithic file IS the architecture -- it ensures atomic offline availability.
**Do this instead:** Keep all CSS and JS inline in `index.html`. Use clear section comments for navigation. The compiled `tailwind.css` is already a separate cached file in `APP_SHELL` -- this is the ONE exception because it changes independently.

### Anti-Pattern 2: Introducing a State Management Library for the Dashboard

**What people do:** Add Redux/Zustand/Jotai for "proper" state management.
**Why it is wrong:** The dashboard has 4 pages with no shared state between them. Each page fetches its own data on mount. Adding state management adds bundle size and complexity for zero benefit at this scale.
**Do this instead:** Keep page-level data fetching. If two pages need the same data (unlikely), lift the fetch to `App.tsx` and pass as props. The only shared state is `activePage` and `apiHealthy` -- both already in `App.tsx`.

### Anti-Pattern 3: Dual Cache Writes with Different Keys

**What people do:** Save to both file cache and PostGIS cache using each system's own normalization.
**Why it is wrong:** This is the current bug. Two caches with different normalization = inconsistent data, duplicate API calls, conflicting coordinates.
**Do this instead:** Use a single normalization function everywhere. Long-term, deprecate the file cache entirely -- PostGIS is the authoritative cache in production. Keep file cache only as a development fallback when no database is available.

### Anti-Pattern 4: Building a Separate "Geocoding Service"

**What people do:** Extract geocoding into a separate microservice for "scalability."
**Why it is wrong:** At 40-50 deliveries/day, geocoding takes under 30 seconds per batch. A separate service adds deployment complexity, network latency, and a new failure mode -- all for no scalability benefit.
**Do this instead:** Keep geocoding as a module within FastAPI. If batch sizes grow to 500+, add async task processing (background worker within the same codebase), not a separate service.

### Anti-Pattern 5: Big-Bang CSS Migration

**What people do:** Delete all `.css` files in one commit, rewrite everything in Tailwind utilities.
**Why it is wrong:** The existing 380+ tests do not cover visual output -- regression is invisible. A component-by-component migration allows visual verification at each step.
**Do this instead:** One page per phase. Remove the page's `.css` file only after confirming the DaisyUI classes produce the correct visual. Commit each page migration separately.

## Integration Points

### Internal Boundaries

| Boundary | Communication | v1.1 Impact |
|----------|---------------|-------------|
| Dashboard <-> API | HTTP REST (fetch) | New response fields added to `OptimizationSummary` for cost tracking + duplicates |
| Driver PWA <-> API | HTTP REST (fetch) | No API changes needed |
| API <-> PostGIS Cache | SQLAlchemy async | Normalization function changes; new `find_duplicate_locations()` spatial query |
| API <-> File Cache | Direct file I/O via GoogleGeocoder | Normalization function changes to match PostGIS |
| API <-> Google Geocoding | httpx HTTP | No changes to integration; normalization fix reduces unnecessary API calls |
| Dashboard <-> DaisyUI | CSS classes | Prefix `tw:` already configured in `index.css` |
| PWA <-> Service Worker | Cache API, localStorage | Enhanced offline strategy (Cache API + BackgroundSync) |

### External Services

| Service | Integration Pattern | v1.1 Changes |
|---------|---------------------|-------------|
| Google Geocoding API | httpx GET, per-address | No API integration changes; normalization fix reduces duplicate calls |
| OSRM | httpx, internal to VROOM | No changes |
| VROOM | httpx POST | No changes |
| PostGIS | SQLAlchemy async | New spatial query for duplicate detection via ST_DWithin |

## Suggested Build Order

Dependencies determine ordering:

```
Phase 1: Geocoding Normalization Fix (foundation -- MUST be first)
  1a. Create core/geocoding/normalize.py
  1b. Update repository.py to use normalize_address()
  1c. Update google_adapter.py to use normalize_address()
  1d. Write Alembic migration for existing data
  1e. Add tests for normalize_address()
  WHY FIRST: Other geocoding features depend on consistent normalization.
  Building UI on inconsistent data wastes effort.

Phase 2: Geocoding Enhancements (builds on normalization fix)
  2a. Add cost tracking counters to upload endpoint
  2b. Add geocode_cache_hits/geocode_api_calls to OptimizationSummary model
  2c. Add find_duplicate_locations() to repository.py
  2d. Add DuplicateGroup model
  2e. Wire duplicate detection into upload endpoint
  2f. Update dashboard types.ts with new response fields
  DEPENDS ON: Phase 1 (consistent cache behavior)

Phase 3: Dashboard UI Overhaul (needs Phase 2 response fields)
  3a. Migrate UploadRoutes page to DaisyUI (needs 2b/2f for new fields)
  3b. Add GeocodingStats component
  3c. Add DuplicateLocationAlert component
  3d. Migrate LiveMap page (independent of geocoding)
  3e. Migrate RunHistory page (independent)
  3f. Migrate FleetManagement page (independent)
  3g. Polish App sidebar with DaisyUI drawer/menu
  3h. Clean up: delete fully-migrated per-page CSS files
  DEPENDS ON: Phase 2 for 3a-3c; 3d-3h independent

Phase 4: Driver PWA Refresh (fully independent -- can parallel Phase 3)
  4a. Redesign next-stop UX flow (JS state machine)
  4b. Improve outdoor readability CSS
  4c. Enhance sw.js with Cache API + BackgroundSync
  4d. Update manifest.json
  4e. Regenerate tailwind.css
  NO DEPENDENCIES: Different tech stack, no shared code, no shared API changes
```

**Phase ordering rationale:**
- Normalization fix FIRST because it is a data integrity issue. Building UI on top of inconsistent geocode data wastes effort.
- Geocoding enhancements SECOND because they produce the new API fields the dashboard needs to display.
- Dashboard UI THIRD because it consumes the new response fields from Phase 2 for geocoding stats and duplicate warnings.
- Driver PWA FOURTH or parallel with Phase 3 because it is completely independent: different tech stack (vanilla JS), different frontend (mobile), different styling (dark theme), no shared API changes.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Current (13 vehicles, 50 orders/day) | Current architecture is correct. No scaling changes needed. |
| 50 vehicles, 200 orders/day | Add batch endpoint for LiveMap (already in CONCERNS.md). Consider in-memory cache for routes (30s TTL). |
| 100+ vehicles | Geocoding batch should be async (background worker). Consider WebSocket for live map instead of polling. |

### First bottleneck: geocoding latency on large uploads

At 500+ orders with 50% cache miss, geocoding takes 4+ minutes (1 req/sec Google API rate). The frontend HTTP request will timeout. Fix: make geocoding async with a progress polling endpoint. NOT a concern for v1.1 (50 orders/day scale).

### Second bottleneck: LiveMap N+1 queries

Already identified in CONCERNS.md -- at 50+ vehicles, serial route detail fetches cause visible lag. Fix: batch endpoint returning all vehicle positions in one response. NOT a concern for v1.1 (13 vehicles).

## Sources

- Direct codebase analysis of all files listed in this document (HIGH confidence)
- `.planning/codebase/ARCHITECTURE.md` -- existing architecture patterns (analyzed 2026-03-01)
- `.planning/codebase/STRUCTURE.md` -- file organization (analyzed 2026-03-01)
- `.planning/codebase/INTEGRATIONS.md` -- external service contracts (analyzed 2026-03-01)
- `.planning/codebase/CONCERNS.md` -- known issues and tech debt (analyzed 2026-03-01)
- `core/geocoding/google_adapter.py` lines 189-196 -- file cache normalization (whitespace collapse + SHA-256)
- `core/database/repository.py` lines 741, 789 -- PostGIS cache normalization (strip + lower only)
- `infra/postgres/init.sql` lines 209-225 -- geocode_cache DDL with UNIQUE(address_norm, source)
- `apps/kerala_delivery/dashboard/src/index.css` lines 1-38 -- Tailwind 4 + DaisyUI prefix(tw) config
- `apps/kerala_delivery/driver_app/sw.js` -- current service worker caching strategy (CACHE_VERSION v3)
- `apps/kerala_delivery/driver_app/index.html` -- PWA inline CSS/JS architecture (~51KB monolithic)

---
*Architecture research for: Kerala LPG Delivery v1.1 -- Dashboard UI overhaul + Driver PWA refresh + Geocoding fixes*
*Researched: 2026-03-01*
