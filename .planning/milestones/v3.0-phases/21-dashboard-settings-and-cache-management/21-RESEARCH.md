# Phase 21: Dashboard Settings and Cache Management - Research

**Researched:** 2026-03-14
**Domain:** React dashboard page + FastAPI endpoints + SQLAlchemy model for settings/cache management
**Confidence:** HIGH

## Summary

This phase adds a Settings page to the React dashboard that lets office staff manage the Google Maps API key, view geocode cache statistics, export/import cache data, and review upload history. The implementation spans all three layers: a new SQLAlchemy `SettingsDB` model with Alembic migration, new FastAPI endpoints for CRUD operations on settings and cache, and a new React page following the established patterns from `DriverManagement.tsx` and `RunHistory.tsx`.

The codebase is well-structured for this addition. The `GeocodeCacheDB` model already has all fields needed for stats aggregation and export. The `_get_geocoder()` function in `main.py` reads `GOOGLE_MAPS_API_KEY` from `os.environ` -- this needs modification to check the DB settings table first. The `OptimizationRunDB` model already has `vehicles_used`, `total_orders`, `source_filename`, and `created_at` fields needed for upload history display. The dashboard's state-based page switching (`activePage` in App.tsx) makes adding a new page straightforward.

**Primary recommendation:** Use a simple key-value settings table (one row per setting key) rather than typed columns, because there is currently only one setting (API key) and this pattern scales naturally if more settings are added later. Implement cache export as a JSON download via a dedicated API endpoint, and cache import as a file upload endpoint with skip-duplicates merge strategy.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Store the API key in a new `settings` database table (not .env rewrite) -- immediately available without server restart
- DB overrides .env: if a key exists in the DB settings table, use it; otherwise fall back to GOOGLE_MAPS_API_KEY from .env. Existing deployments keep working
- Validate the key before saving: make a single test geocoding request to Google Maps API with a known address (Vatakara depot). Show success/failure feedback to the user immediately
- Key displayed masked in the UI (SET-02)
- Single scrollable page with stacked card/sections: API Key, Geocode Cache, Upload History
- Sidebar position: bottom of nav list (after Drivers) -- Upload, Live Map, Run History, Drivers, Settings
- Geocode cache stats section shows estimated cost savings: "X cached addresses . Y API calls saved . ~$Z saved" using $5/1000 Google rate
- Relabel `vehicles_used` as "Drivers" in the UI -- no DB schema change needed
- Export: single "Export Cache" button triggers browser JSON file download
- Import: file picker -> immediate import -> show summary after ("Added 142 entries, skipped 38 duplicates")
- "Clear Cache" button available with confirmation dialog showing entry count before deletion

### Claude's Discretion
- Exact API key masking pattern (first 4 + last 4, or just last 4, etc.)
- Settings icon (gear vs wrench from lucide-react)
- Upload history approach (compact card in Settings vs enhancing RunHistory page)
- Cache import merge strategy (skip duplicates vs update duplicates)
- Settings table schema design (key-value pairs vs typed columns)
- New API endpoint design for geocode stats, cache export/import, and API key management

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SET-01 | User can enter/update Google Maps API key in dashboard settings page | Settings page API Key card with input, validation endpoint, DB storage |
| SET-02 | API key is stored server-side and displayed masked in the UI | Settings table + masking logic in API response (first 4 + last 4 pattern) |
| SET-03 | User can view upload history with date, filename, driver count, and order count | Query `optimization_runs` table, display in Settings card or enhanced RunHistory |
| SET-04 | User can view geocode cache statistics (total cached, API calls, estimated cost) | SQL aggregation on `geocode_cache` table + $5/1000 cost calculation |
| SET-05 | User can export geocode cache to JSON file | API endpoint streams all cache rows as JSON, browser downloads file |
| SET-06 | User can import geocode cache from JSON file | File upload endpoint, parse JSON, upsert with duplicate detection |
</phase_requirements>

## Standard Stack

### Core (Already Installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.2 | Settings page component | Already in use across dashboard |
| SQLAlchemy | 2.0 | SettingsDB model + cache queries | ORM layer for all DB access |
| Alembic | (current) | Migration for settings table | All schema changes go through Alembic |
| FastAPI | (current) | New API endpoints | All backend endpoints in main.py |
| DaisyUI | 5.x | Card, stat, btn, modal components | UI component library already in use |
| lucide-react | 0.575 | Settings icon in nav | Icon library already in use |

### Supporting (Already Installed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| framer-motion | 12.x | Animated transitions for sections | If visual polish needed (optional) |
| GeoAlchemy2 | (current) | PostGIS point extraction for cache export | Extracting lat/lng from geometry columns |
| httpx | (current) | Test geocode request for API key validation | Already used in GoogleGeocoder |

### No New Dependencies Required

This phase requires zero new npm or pip packages. Everything needed is already installed.

## Architecture Patterns

### Recommended File Structure
```
# Backend (Python)
core/database/models.py           # Add SettingsDB model
core/database/repository.py       # Add settings + cache stats methods
infra/alembic/versions/            # New migration for settings table
apps/kerala_delivery/api/main.py   # New endpoints (settings, cache, upload history)

# Frontend (React)
apps/kerala_delivery/dashboard/src/
  pages/Settings.tsx               # New settings page component
  pages/Settings.css               # Settings page styles
  lib/api.ts                       # Add settings/cache API functions
  types.ts                         # Add Settings/GeocodeStats interfaces
  App.tsx                          # Add settings to Page union + NAV_ITEMS
```

### Pattern 1: State-Based Page Switching (Existing)
**What:** The dashboard uses `activePage` state + conditional rendering instead of a router.
**When to use:** Adding the Settings page follows this exact pattern.
**Example:**
```typescript
// In App.tsx -- extend the Page union type
type Page = "upload" | "live-map" | "run-history" | "drivers" | "settings";

// Add to NAV_ITEMS array (last position, after Drivers)
{ page: "settings", icon: Settings, label: "Settings" }

// Add conditional render in main content
{activePage === "settings" && <Settings />}
```

### Pattern 2: Data-Fetching Page (Existing -- RunHistory.tsx)
**What:** useState for data + useCallback for fetch + useEffect for mount-load + loading/error states.
**When to use:** The Settings page follows this pattern for loading settings, stats, and history.
**Example:**
```typescript
// Follow the exact pattern from RunHistory.tsx / DriverManagement.tsx
const [settings, setSettings] = useState<SettingsData | null>(null);
const [loading, setLoading] = useState(true);
const [apiError, setApiError] = useState<ApiError | null>(null);

const loadSettings = useCallback(async () => {
  try {
    setLoading(true);
    const data = await fetchSettings();
    setSettings(data);
    setApiError(null);
  } catch (err) {
    // Error handling follows isApiError pattern from DriverManagement
  } finally {
    setLoading(false);
  }
}, []);

useEffect(() => { loadSettings(); }, [loadSettings]);
```

### Pattern 3: API Client Functions (Existing -- lib/api.ts)
**What:** `apiFetch<T>()` for reads, `apiWrite<T>()` for mutations, typed return values.
**When to use:** All new settings/cache endpoints.
**Example:**
```typescript
// GET endpoints use apiFetch
export async function fetchSettings(): Promise<SettingsResponse> {
  return apiFetch<SettingsResponse>("/api/settings");
}

// POST/PUT endpoints use apiWrite
export async function updateApiKey(key: string): Promise<ApiKeyUpdateResponse> {
  return apiWrite<ApiKeyUpdateResponse>("/api/settings/api-key", "PUT", { api_key: key });
}
```

### Pattern 4: Repository Layer (Existing -- repository.py)
**What:** All CRUD operations in `core/database/repository.py`, endpoints call repo functions.
**When to use:** Settings CRUD, cache stats aggregation, cache export/import.
**Example:**
```python
# Repository function for geocode cache stats
async def get_geocode_cache_stats(session: AsyncSession) -> dict:
    """Aggregate geocode cache statistics."""
    result = await session.execute(
        select(
            func.count(GeocodeCacheDB.id),
            func.sum(GeocodeCacheDB.hit_count),
        )
    )
    row = result.one()
    return {
        "total_entries": row[0],
        "total_hits": row[1] or 0,
    }
```

### Pattern 5: Key-Value Settings Table
**What:** Simple table with `key` (VARCHAR, primary key) and `value` (TEXT) columns, plus timestamps.
**Why key-value over typed columns:** Only one setting currently exists (API key). A key-value pattern avoids empty-column waste and scales naturally. Values are always strings; the application layer parses as needed.
**Schema:**
```python
class SettingsDB(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

### Anti-Patterns to Avoid
- **Do not store the API key in .env file from the API:** Writing to the .env file from runtime code is fragile (file permissions, Docker volume mounts, requires restart). Use DB storage per CONTEXT.md decision.
- **Do not create a separate settings microservice:** This is a simple CRUD operation -- keep it in main.py with the other endpoints.
- **Do not use React state for API key persistence:** The key must persist server-side. The UI only displays the masked version.
- **Do not send the full API key in GET responses:** Always mask it. Only the PUT/POST request carries the full key (HTTPS encrypted in transit).
- **Do not use browser localStorage for settings:** These are server-level configurations shared across all clients.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| File download from API | Custom WebSocket streaming | `Response` with `Content-Disposition` header + JSON body | Standard HTTP pattern, browser handles download natively |
| File upload for import | Custom binary protocol | FastAPI `UploadFile` with JSON parsing | Already used by upload-orders endpoint |
| API key validation | Custom regex or format check | Test geocode request to Google API | Only way to confirm the key actually works |
| Cache stats aggregation | Python-side iteration | SQL `COUNT()` + `SUM()` via SQLAlchemy | Database does aggregation orders of magnitude faster |
| Confirmation dialogs | Custom modal from scratch | DaisyUI `tw:modal` component | Already available, consistent with dashboard styling |
| Masked key display | Complex masking library | Simple string slice: `key.slice(0,4) + "..." + key.slice(-4)` | Trivial operation, no library needed |

## Common Pitfalls

### Pitfall 1: Geocoder Instance Caching with DB-Stored Key
**What goes wrong:** `_get_geocoder()` in main.py caches the `GoogleGeocoder` instance in a module-level variable (`_geocoder_instance`). If the API key changes in DB, the cached instance still uses the old key.
**Why it happens:** The instance is created once and reused for performance. But API key updates should take effect immediately.
**How to avoid:** When the API key is updated via the settings endpoint, invalidate the cached `_geocoder_instance` by setting it to `None`. The next call to `_get_geocoder()` will read the new key from DB.
**Warning signs:** API key updated in settings but geocoding still fails with "invalid key" or still uses the old key.

### Pitfall 2: GeoAlchemy2 Point Extraction for Cache Export
**What goes wrong:** The `location` column in `geocode_cache` is a PostGIS `geometry(Point, 4326)`. You cannot simply serialize it to JSON -- it's stored as WKB (binary).
**Why it happens:** GeoAlchemy2 uses binary geometry representation internally.
**How to avoid:** Use the existing `to_shape()` function from `geoalchemy2.shape` (already used throughout repository.py) to convert geometry to Shapely Point, then extract `.x` (longitude) and `.y` (latitude).
**Warning signs:** Serialization errors or hex strings in exported JSON instead of coordinates.

### Pitfall 3: Cache Import Normalization Mismatch
**What goes wrong:** Imported addresses must be normalized using the same `normalize_address()` function from `core/geocoding/normalize.py`. If import skips normalization, duplicates won't be detected and cache lookups will miss.
**Why it happens:** The export includes `address_raw` and `address_norm`, but the import must re-normalize (the normalize function may have been updated between export and import).
**How to avoid:** Always re-normalize imported addresses using `normalize_address()` during import, don't trust the exported `address_norm` value.
**Warning signs:** Cache misses for addresses that appear to be cached.

### Pitfall 4: Large Cache Export Blocking the Event Loop
**What goes wrong:** Exporting thousands of geocode cache entries in a single async handler can block the event loop if done naively.
**Why it happens:** Serializing many rows with geometry conversion is CPU-bound work.
**How to avoid:** At current scale (hundreds of entries, not millions), this is unlikely to be a problem. Use a simple `select all -> convert -> serialize` approach. If scale grows, consider streaming JSON response.
**Warning signs:** API timeout or dashboard freezing during export.

### Pitfall 5: API Key Validation Test Request Cost
**What goes wrong:** Each validation makes a real Google Maps API call ($0.005). If users type character-by-character, it could trigger many calls.
**Why it happens:** Validation fires on every save attempt.
**How to avoid:** Only validate on explicit "Save" button click, not on input change or blur. The UI should have a clear "Save" action that triggers validation. Show a loading state during validation.
**Warning signs:** Unexpected API charges from repeated key validation.

### Pitfall 6: Alembic Migration with Docker
**What goes wrong:** The db-init container runs migrations on `docker compose up`. If the migration file isn't included in the Docker image, the settings table won't be created.
**Why it happens:** Docker builds use cached layers. After adding a migration, you need to rebuild the API image.
**How to avoid:** After creating the Alembic migration, rebuild with `docker compose build api` before testing.
**Warning signs:** "Table 'settings' does not exist" errors at runtime.

## Code Examples

### Settings Table Model (models.py)
```python
# Add to core/database/models.py

class SettingsDB(Base):
    """Key-value settings table for dashboard-configurable options.

    Why key-value instead of typed columns:
    Only one setting exists today (Google Maps API key). A key-value design
    avoids empty columns and scales naturally. Values are always TEXT;
    the application layer interprets them.
    """
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

### API Key Masking (Python-side)
```python
def mask_api_key(key: str) -> str:
    """Mask an API key for display: show first 4 and last 4 characters.

    Google API keys are 39 chars starting with 'AIza'.
    Masking preserves enough to identify the key without exposing it.
    """
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"
```

### Geocode Cache Stats Query (repository.py)
```python
async def get_geocode_cache_stats(session: AsyncSession) -> dict:
    """Aggregate geocode cache statistics for the settings page."""
    result = await session.execute(
        select(
            func.count(GeocodeCacheDB.id).label("total_entries"),
            func.coalesce(func.sum(GeocodeCacheDB.hit_count), 0).label("total_hits"),
        )
    )
    row = result.one()
    total_entries = row[0]
    total_hits = row[1]
    return {
        "total_entries": total_entries,
        "total_hits": total_hits,
        # API calls saved = total_hits (each hit avoided an API call)
        "api_calls_saved": total_hits,
        # $5 per 1000 requests = $0.005 per request
        "estimated_savings_usd": round(total_hits * 0.005, 2),
    }
```

### Cache Export Serialization (repository.py)
```python
async def export_geocode_cache(session: AsyncSession) -> list[dict]:
    """Export all geocode cache entries for JSON download."""
    result = await session.execute(
        select(GeocodeCacheDB).order_by(GeocodeCacheDB.created_at)
    )
    entries = []
    for row in result.scalars().all():
        point = to_shape(row.location)
        entries.append({
            "address_raw": row.address_raw,
            "address_norm": row.address_norm,
            "latitude": point.y,
            "longitude": point.x,
            "source": row.source,
            "confidence": row.confidence,
            "hit_count": row.hit_count,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })
    return entries
```

### Modifying _get_geocoder() to Check DB Settings
```python
def _get_geocoder() -> GoogleGeocoder | None:
    """Get or create the shared GoogleGeocoder instance.

    Priority: DB settings table > GOOGLE_MAPS_API_KEY env var.
    Returns None if no valid key found in either source.
    """
    global _geocoder_instance
    if _geocoder_instance is not None:
        return _geocoder_instance

    # Try DB settings first (set via dashboard Settings page)
    api_key = _get_api_key_from_db()  # Sync helper reading from cached value
    if not api_key:
        # Fall back to env var
        api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()

    placeholder_values = {"your-key-here", "your-api-key", "change-me", ""}
    if api_key.lower() in placeholder_values:
        return None

    _geocoder_instance = GoogleGeocoder(api_key=api_key)
    return _geocoder_instance
```

### Settings Page Component Pattern (Settings.tsx)
```typescript
// Follows DriverManagement.tsx mutation pattern
export function Settings() {
  const [apiKey, setApiKey] = useState("");
  const [maskedKey, setMaskedKey] = useState<string | null>(null);
  const [cacheStats, setCacheStats] = useState<GeocodeStats | null>(null);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);

  // Card sections: API Key, Geocode Cache, Upload History
  // Each section is a DaisyUI tw:card

  return (
    <div className="settings-page">
      <h2>Settings</h2>

      {/* API Key Section */}
      <div className="tw:card tw:bg-base-100 tw:shadow-sm">
        <div className="tw:card-body">
          <h3 className="tw:card-title">Google Maps API Key</h3>
          {/* Input + Save button + validation feedback */}
        </div>
      </div>

      {/* Geocode Cache Section */}
      <div className="tw:card tw:bg-base-100 tw:shadow-sm">
        <div className="tw:card-body">
          <h3 className="tw:card-title">Geocode Cache</h3>
          {/* Stats display + Export/Import/Clear buttons */}
        </div>
      </div>

      {/* Upload History Section */}
      <div className="tw:card tw:bg-base-100 tw:shadow-sm">
        <div className="tw:card-body">
          <h3 className="tw:card-title">Upload History</h3>
          {/* Table of past uploads */}
        </div>
      </div>
    </div>
  );
}
```

## Discretion Recommendations

### API Key Masking Pattern
**Recommendation:** Show first 4 + last 4 characters: `AIza***...***1234`
**Rationale:** Google API keys always start with "AIza", so showing the first 4 confirms it's a valid Google key format. Last 4 helps identify which key is configured when the user has multiple keys. This pattern is standard across cloud provider dashboards (AWS, GCP, Stripe).

### Settings Icon
**Recommendation:** Use `Settings` (gear icon) from lucide-react.
**Rationale:** The gear icon is the universal convention for settings pages. The wrench icon suggests maintenance/repair rather than configuration. lucide-react exports `Settings` which renders as a gear cog.

### Upload History Approach
**Recommendation:** Compact summary card within the Settings page.
**Rationale:** The RunHistory page already shows detailed per-run data with route drill-down. Duplicating that data in Settings would violate DRY. Instead, show a compact card in Settings with the last 5-10 uploads in a simple table (date, filename, drivers, orders). Add a "View Full History" link that switches to the RunHistory page. This gives Settings a quick overview without duplicating the full RunHistory functionality.

### Cache Import Merge Strategy
**Recommendation:** Skip duplicates (don't update existing entries).
**Rationale:** Safest approach per CONTEXT.md guidance. If an address already exists in the cache (matched by `address_norm` + `source`), keep the existing entry -- it may have been refined by driver verification or manual correction. The import summary should report counts: "Added X new, skipped Y duplicates". This prevents accidental data loss from importing an older cache file over newer data.

### Settings Table Schema
**Recommendation:** Key-value pairs with `(key VARCHAR(100) PK, value TEXT, updated_at TIMESTAMPTZ)`.
**Rationale:** Only one setting exists today (Google Maps API key). A key-value design is simpler than typed columns, avoids ALTER TABLE if new settings are added, and maps naturally to a Python dict. The repository functions `get_setting(key)` and `set_setting(key, value)` are trivial to implement and test.

### API Endpoint Design
**Recommendation:**
| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/api/settings` | GET | Get all settings (masked API key) + cache stats | API key |
| `/api/settings/api-key` | PUT | Update Google Maps API key (validates first) | API key |
| `/api/settings/api-key/validate` | POST | Test if a key works (dry run, no save) | API key |
| `/api/geocode-cache/stats` | GET | Cache statistics (count, hits, savings) | API key |
| `/api/geocode-cache/export` | GET | Download cache as JSON file | API key |
| `/api/geocode-cache/import` | POST | Upload and import cache JSON file | API key |
| `/api/geocode-cache` | DELETE | Clear all cache entries | API key |

**Rationale:** RESTful naming, consistent with existing endpoint patterns. The validation endpoint is separate from the save endpoint to allow "test before save" UX. Cache endpoints are under `/api/geocode-cache/` since they operate on a different resource than settings.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| .env file for API key | DB settings table with .env fallback | Phase 21 (now) | No restart needed for key changes |
| No cache visibility | Stats + export/import in dashboard | Phase 21 (now) | Office staff can manage cache |
| No upload history in settings | Compact view with link to RunHistory | Phase 21 (now) | Quick operational overview |

**No deprecated APIs or approaches apply to this phase.**

## Open Questions

1. **Async vs sync key lookup for `_get_geocoder()`**
   - What we know: `_get_geocoder()` is currently synchronous. DB queries require async session. The function is called inside async endpoint handlers.
   - What's unclear: Whether to cache the DB key in a module-level variable (refreshed on update) or make `_get_geocoder()` async.
   - Recommendation: Cache the API key value in a module-level variable. Update it when the settings endpoint saves a new key. `_get_geocoder()` remains synchronous and reads the cached value. This avoids making the function async, which would require changes everywhere it's called.

2. **health.py `check_google_api()` update**
   - What we know: Currently checks `os.environ.get("GOOGLE_MAPS_API_KEY")`. With DB-stored keys, it should also check the settings table.
   - What's unclear: `check_google_api()` is synchronous. Accessing DB requires async.
   - Recommendation: Keep `check_google_api()` synchronous. It can check the same module-level cached key variable used by `_get_geocoder()`. No async change needed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (asyncio_mode = auto) |
| Config file | `pytest.ini` |
| Quick run command | `pytest tests/apps/kerala_delivery/api/ -v -x` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SET-01 | PUT /api/settings/api-key saves key, invalidates geocoder cache | unit | `pytest tests/apps/kerala_delivery/api/test_settings.py::test_update_api_key -x` | Wave 0 |
| SET-02 | GET /api/settings returns masked key | unit | `pytest tests/apps/kerala_delivery/api/test_settings.py::test_get_settings_masked_key -x` | Wave 0 |
| SET-03 | GET /api/runs returns upload history data (already tested) | unit | `pytest tests/apps/kerala_delivery/api/test_api.py -x -k runs` | Existing |
| SET-04 | GET /api/geocode-cache/stats returns correct aggregates | unit | `pytest tests/apps/kerala_delivery/api/test_settings.py::test_geocode_cache_stats -x` | Wave 0 |
| SET-05 | GET /api/geocode-cache/export returns all entries as JSON | unit | `pytest tests/apps/kerala_delivery/api/test_settings.py::test_cache_export -x` | Wave 0 |
| SET-06 | POST /api/geocode-cache/import adds entries, skips duplicates | unit | `pytest tests/apps/kerala_delivery/api/test_settings.py::test_cache_import -x` | Wave 0 |

### Additional Tests
| Behavior | Test Type | Automated Command | File Exists? |
|----------|-----------|-------------------|-------------|
| API key validation via test geocode | unit | `pytest tests/apps/kerala_delivery/api/test_settings.py::test_validate_api_key -x` | Wave 0 |
| DB key fallback (DB > env var) | unit | `pytest tests/apps/kerala_delivery/api/test_settings.py::test_api_key_db_overrides_env -x` | Wave 0 |
| Cache clear endpoint | unit | `pytest tests/apps/kerala_delivery/api/test_settings.py::test_clear_cache -x` | Wave 0 |
| Settings table migration | integration | Manual -- `alembic upgrade head` against test DB | Wave 0 |
| Alembic model import | unit | Verified by existing env.py import pattern | Implicit |

### Sampling Rate
- **Per task commit:** `pytest tests/apps/kerala_delivery/api/test_settings.py -x -v`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/apps/kerala_delivery/api/test_settings.py` -- covers SET-01 through SET-06
- [ ] Alembic migration file for `settings` table
- [ ] `SettingsDB` model added to `core/database/models.py` (imported by `env.py` for autogenerate)

## Sources

### Primary (HIGH confidence)
- **Codebase inspection:** `apps/kerala_delivery/api/main.py` -- existing endpoint patterns, `_get_geocoder()` implementation
- **Codebase inspection:** `core/database/models.py` -- GeocodeCacheDB model, Base class, existing model patterns
- **Codebase inspection:** `core/database/repository.py` -- existing CRUD patterns, geocode cache methods
- **Codebase inspection:** `apps/kerala_delivery/dashboard/src/` -- App.tsx (page switching), DriverManagement.tsx (mutation pattern), RunHistory.tsx (data fetch pattern), lib/api.ts (API client pattern), types.ts (interface pattern)
- **Codebase inspection:** `infra/alembic/env.py` -- migration configuration, model import pattern
- **Codebase inspection:** `core/geocoding/normalize.py` -- address normalization for cache key consistency
- **Codebase inspection:** `apps/kerala_delivery/config.py` -- GEOCODING_COST_PER_REQUEST = 0.005

### Secondary (MEDIUM confidence)
- **21-CONTEXT.md:** User decisions and locked constraints from discussion session

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed, no new dependencies
- Architecture: HIGH -- follows existing patterns exactly (page switching, data fetch, API client, repository)
- Pitfalls: HIGH -- identified from direct code inspection of _get_geocoder(), GeoAlchemy2 serialization, and normalize_address()

**Research date:** 2026-03-14
**Valid until:** 2026-04-14 (stable codebase, no external dependency changes expected)
