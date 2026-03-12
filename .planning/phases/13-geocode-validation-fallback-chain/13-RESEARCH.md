# Phase 13: Geocode Validation and Fallback Chain - Research

**Researched:** 2026-03-11
**Domain:** Geocode validation, haversine zone checking, fallback chain, circuit breaker pattern, Alembic migrations
**Confidence:** HIGH

## Summary

Phase 13 adds a geocode validation and fallback chain to the upload pipeline. Every geocoded address is checked against a 30km radius from the Vatakara depot using haversine distance. Out-of-zone results trigger an automatic retry with the CDCMS area name, then fall back to dictionary centroid coordinates, then to depot coordinates as the ultimate fallback. A per-batch circuit breaker halts Google API retries after 3 consecutive REQUEST_DENIED responses.

The codebase already has all the fundamental building blocks: `haversine_meters()` in `duplicate_detector.py`, `DEPOT_LOCATION` in `config.py`, the place name dictionary at `data/place_names_vatakara.json` with 381 entries (lat/lon centroids), the `CachedGeocoder` decorator pattern, Google confidence mapping in `google_adapter.py`, and the upload pipeline's geocoding loop at `main.py:1062-1141`. The core work is composing these into a validator class, integrating it into the CachedGeocoder, adding two new columns to the orders table via Alembic migration, and propagating confidence/method through GeocodingResult.

**Primary recommendation:** Build a standalone `GeocodeValidator` class in `core/geocoding/validator.py` that encapsulates the fallback chain logic (zone check, area retry, centroid lookup, depot fallback, circuit breaker). Inject it as an optional parameter into `CachedGeocoder.__init__()`. This keeps the validator testable in isolation and maintains backward compatibility when no validator is provided.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Circuit breaker: 3 consecutive Google API REQUEST_DENIED responses trip it; stateless per upload (resets each CSV upload)
- After tripping: all remaining ungeocoded addresses get centroid fallback (confidence 0.3) or depot fallback (confidence 0.1) -- no silent drops
- Upload succeeds with a yellow batch-level warning: "Google Maps API key issue -- X stops have approximate locations. Ask IT to check the API key."
- Warning does NOT block the workflow -- routes still generated with approximate locations
- Area-name retry: when address geocodes >30km from Vatakara depot, retry with "{area}, Vatakara, Kozhikode, Kerala"
- CDCMS area field is the primary source for area-name retry (direct, always available from CSV data)
- Fallback chain order: direct (1.0) -> area_retry (0.7) -> centroid (0.3) -> depot (0.1)
- Every stop appears on the map at some location -- matches core value "no silent drops, no missing stops"
- New `geocode_confidence` column on orders table (float, nullable)
- New `geocode_method` column on orders table (string/enum, nullable)
- Existing orders (pre-Phase 13) have NULL for both columns
- geocode_cache retains its own raw confidence column separately
- Always re-validate cached results on every upload -- no stale validation state
- Cache saves API calls; validation always runs fresh

### Claude's Discretion
- Whether to cache out-of-zone Google results (to avoid re-calling API) or not cache them
- Validation inside CachedGeocoder (optional validator parameter) vs in the upload pipeline
- Whether to cache fallback results (centroid/depot) as separate geocode_cache entries
- Centroid lookup strategy for circuit-breaker fallback (CDCMS area field vs AddressSplitter vs both)
- Centroid fallback chain when area not in dictionary (try AddressSplitter to find any known place name, or go straight to depot)
- Direct in-zone hit confidence: use Google's location_type granularity (ROOFTOP=0.95, APPROXIMATE=0.40) or always 1.0
- haversine function reuse/location (existing in duplicate_detector.py)
- Exact zone validation radius (30km from success criteria)
- Alembic migration approach for new columns
- GeocodingResult model updates for confidence/method fields

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| GVAL-01 | Geocoded coordinates validated against 30km radius from Vatakara depot via haversine distance check | `haversine_meters()` already exists in `duplicate_detector.py`; `DEPOT_LOCATION` in `config.py`; 30km = 30000m threshold |
| GVAL-02 | Out-of-zone geocode results trigger automatic retry with CDCMS area name only | Area name available in preprocessed DataFrame `area_name` column; retry query format: `"{area}, Vatakara, Kozhikode, Kerala"` using `CDCMS_AREA_SUFFIX` |
| GVAL-03 | Failed area-name retry falls back to area centroid coordinates from place name dictionary | Dictionary at `data/place_names_vatakara.json` has 381 entries with lat/lon; `AddressSplitter` can fuzzy-match area names |
| GVAL-04 | Confidence score adjusted based on validation outcome (1.0 direct hit, 0.7 area retry, 0.3 centroid fallback) | GeocodingResult model needs `method` field; Order model/DB need `geocode_confidence` + `geocode_method` columns |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.11+ | Runtime | Already in use; StrEnum, modern typing |
| SQLAlchemy | 2.0 | ORM + async | Already in use; `mapped_column()` style |
| Alembic | latest | Schema migration | Already configured in `infra/alembic/` with async support |
| Pydantic | v2 | Data models | Already in use for Order, Location, GeocodingResult |
| pytest | latest | Testing | Already configured with `asyncio_mode = auto` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| math (stdlib) | - | Haversine calculation | `haversine_meters()` already uses it |
| json (stdlib) | - | Dictionary loading | For place name centroid lookup |
| logging (stdlib) | - | Structured logging | Consistent with existing patterns |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom haversine | geopy.distance | Extra dependency for a 5-line function already written |
| JSON dictionary | SQLite/PostGIS lookup | Overkill for 381 static entries; JSON already loaded by AddressSplitter |

**Installation:**
No new dependencies needed. All required libraries are already in the project.

## Architecture Patterns

### Recommended Project Structure
```
core/geocoding/
    validator.py          # NEW: GeocodeValidator class (zone check + fallback chain)
    cache.py              # MODIFIED: Accept optional validator parameter
    interfaces.py         # MODIFIED: Add method field to GeocodingResult
    duplicate_detector.py # UNCHANGED: haversine_meters() reused via import
core/database/
    models.py             # MODIFIED: Add geocode_method column to OrderDB
core/models/
    order.py              # UNCHANGED (geocode_confidence already on Location)
infra/alembic/versions/
    xxxx_add_geocode_method_column.py  # NEW: Alembic migration
apps/kerala_delivery/
    config.py             # MODIFIED: Add GEOCODE_ZONE_RADIUS_KM constant
    api/main.py           # MODIFIED: Wire validator into upload pipeline
tests/core/geocoding/
    test_validator.py     # NEW: Comprehensive validator tests
```

### Pattern 1: GeocodeValidator as Injectable Dependency
**What:** A standalone `GeocodeValidator` class that encapsulates zone checking, area-name retry, centroid lookup, depot fallback, and circuit breaker logic. Injected into `CachedGeocoder` as an optional parameter.
**When to use:** When validation needs to run after every geocode result (cache hit or API call) but the validator itself should be testable independently.
**Example:**
```python
# core/geocoding/validator.py
from dataclasses import dataclass, field
from core.geocoding.duplicate_detector import haversine_meters

@dataclass
class ValidationResult:
    """Result of geocode validation against the delivery zone."""
    latitude: float
    longitude: float
    confidence: float        # 0.1 to 1.0
    method: str              # 'direct', 'area_retry', 'centroid', 'depot'
    original_lat: float | None = None   # Pre-validation coords (for logging)
    original_lon: float | None = None

class GeocodeValidator:
    def __init__(
        self,
        depot_lat: float,
        depot_lon: float,
        zone_radius_m: float = 30_000,
        dictionary_path: str | None = None,
        area_suffix: str = ", Vatakara, Kozhikode, Kerala",
    ):
        self._depot_lat = depot_lat
        self._depot_lon = depot_lon
        self._zone_radius_m = zone_radius_m
        self._area_suffix = area_suffix
        self._centroids: dict[str, tuple[float, float]] = {}
        self._circuit_breaker_count = 0
        self._circuit_breaker_tripped = False
        if dictionary_path:
            self._load_centroids(dictionary_path)

    def is_in_zone(self, lat: float, lon: float) -> bool:
        distance = haversine_meters(self._depot_lat, self._depot_lon, lat, lon)
        return distance <= self._zone_radius_m

    def get_centroid(self, area_name: str) -> tuple[float, float] | None:
        # Exact match first (case-insensitive), then fuzzy
        normalized = area_name.strip().upper()
        return self._centroids.get(normalized)
```

### Pattern 2: Circuit Breaker (Stateless Per-Batch)
**What:** A simple counter that tracks consecutive REQUEST_DENIED responses. After 3 consecutive denials, all remaining ungeocoded addresses skip the API and go straight to centroid/depot fallback.
**When to use:** When the Google API key is invalid or billing is broken (a known current state per STATE.md).
**Example:**
```python
def record_api_response(self, raw_response: dict) -> None:
    """Track consecutive REQUEST_DENIED for circuit breaker."""
    status = raw_response.get("status", "")
    if status == "REQUEST_DENIED":
        self._circuit_breaker_count += 1
        if self._circuit_breaker_count >= 3:
            self._circuit_breaker_tripped = True
    else:
        # Any non-REQUEST_DENIED resets the counter
        self._circuit_breaker_count = 0

@property
def is_tripped(self) -> bool:
    return self._circuit_breaker_tripped
```

### Pattern 3: Validation After Cache, Before Return
**What:** Validation runs on every geocode result regardless of source (cache hit or API call). This ensures cached results from before Phase 13 are also validated.
**When to use:** User decision: "Always re-validate cached results on every upload."
**Example:**
```python
# In CachedGeocoder.geocode() -- after getting result from cache or upstream:
if self._validator and result.success and result.location:
    validation = self._validator.validate(
        lat=result.location.latitude,
        lon=result.location.longitude,
        area_name=area_name,  # Passed from upload pipeline
        geocoder=self._upstream,  # For area-name retry API call
    )
    # Update result with validated coordinates/confidence/method
    result = self._apply_validation(result, validation)
```

### Anti-Patterns to Avoid
- **Validating inside GoogleGeocoder:** The adapter should remain a pure API caller. Validation is a separate concern.
- **Caching fallback coordinates in geocode_cache:** Centroid and depot coordinates are not Google results. Caching them would pollute the geocode_cache with synthetic entries and confuse cache hit/miss statistics.
- **Modifying cached entries based on validation:** The cache stores raw API results. Validation is ephemeral -- the same cached result might be valid for one depot but not another.
- **Blocking upload on circuit breaker:** The circuit breaker should switch to fallback mode, not fail the upload. Every stop must appear on the map.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Haversine distance | Custom math from scratch | `haversine_meters()` from `duplicate_detector.py` | Already tested, handles Earth radius correctly |
| Place name centroid lookup | Custom dictionary parser | Load from `data/place_names_vatakara.json` entries | 381 entries with lat/lon already available |
| Fuzzy area name matching | Character-level matching | `AddressSplitter._find_match()` or `rapidfuzz.fuzz.ratio()` | Length-dependent thresholds already tuned for Kerala names |
| Schema migration | Manual SQL ALTER TABLE | Alembic autogenerate | Async migration setup already configured in `infra/alembic/env.py` |
| Confidence mapping | Ad-hoc if/else | Enum or constant dict mapping method -> confidence | Clean, documented, easy to adjust |

**Key insight:** Every major component needed for this phase already exists in the codebase. The work is composition and integration, not building from scratch.

## Common Pitfalls

### Pitfall 1: Area Name Not Available in Geocoding Loop
**What goes wrong:** The CDCMS area name is in the preprocessed DataFrame (`area_name` column) but is NOT passed through CsvImporter to the Order model. CsvImporter creates Order objects without area_name. The geocoding loop in main.py only has access to Order objects.
**Why it happens:** CsvImporter was designed to be generic and doesn't map the `area_name` column. The Order model has no `area_name` field.
**How to avoid:** Before geocoding, build an `order_id -> area_name` mapping from the preprocessed DataFrame. Pass this mapping to the validator/geocoding loop. Do NOT add area_name to the Order model (it's CDCMS-specific metadata, not a core order property). The preprocessed DataFrame is available at `main.py:918` before CsvImporter is called.
**Warning signs:** Area-name retry always uses empty string; all out-of-zone addresses skip to centroid.

### Pitfall 2: Cached Results Bypass Validation
**What goes wrong:** Cache hits return immediately with the cached confidence (e.g., 0.95 from Google ROOFTOP), but the cached location might be out-of-zone. The address never gets validated.
**Why it happens:** `CachedGeocoder.geocode()` returns early on cache hit at line 153-158 without any zone check.
**How to avoid:** Validation must run AFTER the geocode result is obtained, regardless of whether it came from cache or API. This is the user's locked decision: "Always re-validate cached results on every upload."
**Warning signs:** Known out-of-zone addresses with high confidence appearing on the map far from the delivery zone.

### Pitfall 3: Circuit Breaker Counting Non-Consecutive Errors
**What goes wrong:** If the counter counts total REQUEST_DENIED (not consecutive), a batch with scattered denials among successes could trip the breaker even though the API is partially working.
**Why it happens:** Confusion between "3 consecutive" vs "3 total" REQUEST_DENIED responses.
**How to avoid:** Reset the counter to zero on any non-REQUEST_DENIED API response. Only increment on REQUEST_DENIED.
**Warning signs:** Circuit breaker triggers on batches where some addresses geocode successfully.

### Pitfall 4: GeocodingResult Confidence vs Order Confidence
**What goes wrong:** The project has multiple confidence values: Google's raw confidence (ROOFTOP=0.95, etc.) stored in geocode_cache, the validation-adjusted confidence (1.0/0.7/0.3/0.1) stored on orders, and Location.geocode_confidence. Mixing them causes inconsistent behavior.
**Why it happens:** Three different places store "confidence": `Location.geocode_confidence`, `GeocodeCacheDB.confidence`, and the new `OrderDB.geocode_confidence`.
**How to avoid:** Be explicit: geocode_cache.confidence = raw Google confidence (unchanged). OrderDB.geocode_confidence = validation-adjusted confidence (new Phase 13 value). Location.geocode_confidence = raw Google confidence (set by GoogleGeocoder). The validation result's confidence (1.0/0.7/0.3/0.1) goes on the Order, NOT on the Location or cache.
**Warning signs:** Duplicate detector using validation-adjusted confidence instead of raw Google confidence.

### Pitfall 5: Standard CSV Uploads Missing Area Name
**What goes wrong:** Non-CDCMS standard CSV uploads have no `area_name` column. The area-name retry has no data source.
**Why it happens:** Only CDCMS exports have the AreaName column.
**How to avoid:** For standard CSV uploads, skip the area-name retry step entirely. Fall through directly from failed zone check to centroid lookup (using AddressSplitter to extract a place name from the address text) or depot fallback. The validator must handle area_name=None gracefully.
**Warning signs:** KeyError or empty area-name retry for non-CDCMS uploads.

### Pitfall 6: Alembic Migration for geocode_method Column
**What goes wrong:** OrderDB already has `geocode_confidence` (Float, nullable) but does NOT have `geocode_method`. The migration must add only `geocode_method`, not try to re-add `geocode_confidence`.
**Why it happens:** Checking `models.py` shows `geocode_confidence` is already on `OrderDB` (line 201), but `geocode_method` is not.
**How to avoid:** Add `geocode_method: Mapped[str | None] = mapped_column(String(20))` to OrderDB, then run `alembic revision --autogenerate`. Verify the generated migration only adds the new column.
**Warning signs:** Migration tries to add geocode_confidence again (column already exists error).

## Code Examples

### Haversine Zone Check (Reuse Existing Function)
```python
# Source: core/geocoding/duplicate_detector.py (lines 50-64)
from core.geocoding.duplicate_detector import haversine_meters
from apps.kerala_delivery.config import DEPOT_LOCATION

ZONE_RADIUS_M = 30_000  # 30km

def is_in_delivery_zone(lat: float, lon: float) -> bool:
    distance_m = haversine_meters(
        DEPOT_LOCATION.latitude, DEPOT_LOCATION.longitude,
        lat, lon,
    )
    return distance_m <= ZONE_RADIUS_M
```

### Loading Centroids from Dictionary
```python
# Source: data/place_names_vatakara.json structure
import json

def load_centroids(dictionary_path: str) -> dict[str, tuple[float, float]]:
    """Load area name -> (lat, lon) mapping from place name dictionary."""
    with open(dictionary_path, "r") as f:
        data = json.load(f)

    centroids: dict[str, tuple[float, float]] = {}
    for entry in data.get("entries", []):
        name = entry.get("name", "").strip().upper()
        lat = entry.get("lat")
        lon = entry.get("lon")
        if name and lat is not None and lon is not None:
            centroids[name] = (lat, lon)
            # Also index aliases
            for alias in entry.get("aliases", []):
                alias_upper = alias.strip().upper()
                if alias_upper:
                    centroids[alias_upper] = (lat, lon)
    return centroids
```

### Area-Name Retry Query Format
```python
# Source: CONTEXT.md decision + config.py CDCMS_AREA_SUFFIX
# For area_name "Vallikkadu":
retry_query = f"{area_name}, Vatakara, Kozhikode, Kerala"
# Becomes: "Vallikkadu, Vatakara, Kozhikode, Kerala"
result = geocoder.geocode(retry_query)
```

### GeocodingResult with Method Field
```python
# Source: core/geocoding/interfaces.py (extended)
class GeocodingResult(BaseModel):
    location: Location | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    formatted_address: str = ""
    raw_response: dict[str, Any] = Field(default_factory=dict)
    method: str = Field(default="direct")  # NEW: 'direct', 'area_retry', 'centroid', 'depot'
```

### OrderDB Migration Column
```python
# In core/database/models.py, add to OrderDB class:
geocode_method: Mapped[str | None] = mapped_column(String(20))
```

### Extracting Area Name Mapping Before Geocoding
```python
# In main.py upload pipeline, AFTER preprocess_cdcms() but BEFORE CsvImporter:
if is_cdcms and not preprocessed_df.empty:
    # Build order_id -> area_name mapping for geocode validation
    area_name_map: dict[str, str] = dict(
        zip(
            preprocessed_df["order_id"].astype(str).str.strip(),
            preprocessed_df["area_name"].str.strip(),
        )
    )
else:
    area_name_map = {}  # Standard CSV -- no area names available
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No validation | Haversine zone check + fallback chain | Phase 13 (now) | Prevents wrong-location pins on driver map |
| Silent geocoding failures | Every address gets coordinates (fallback to centroid/depot) | Phase 13 (now) | Core value: no silent drops |
| Flat confidence scores | Method-aware confidence (1.0/0.7/0.3/0.1) | Phase 13 (now) | Phase 14 uses confidence for "Approx. location" badge |

**Deprecated/outdated:**
- Pre-Phase 13 orders will have NULL for geocode_confidence and geocode_method on OrderDB. Phase 14 treats NULL as "pre-validation data" with no badge shown.

## Open Questions

1. **Direct in-zone confidence: 1.0 or Google granularity?**
   - What we know: User marked as Claude's discretion. Google gives ROOFTOP=0.95, APPROXIMATE=0.40, etc.
   - What's unclear: Whether to override Google's granularity with flat 1.0 for all in-zone results
   - Recommendation: Use flat 1.0 for all direct in-zone hits. Rationale: the 4-tier confidence system (1.0/0.7/0.3/0.1) maps to the fallback method, not Google's sub-tier precision. Keeping Google's granularity would create a 7-level confidence system that complicates Phase 14's "approximate location" badge logic. The raw Google confidence is preserved separately in geocode_cache.confidence for any future use.

2. **Cache out-of-zone Google results?**
   - What we know: User marked as Claude's discretion. Caching saves API calls on repeated uploads.
   - Recommendation: YES, cache them. The geocode_cache stores raw API results. An out-of-zone result is still a valid Google result -- the zone check is a business rule, not a data quality issue. If the address is uploaded again, we want the cache hit to avoid paying for the API call. Validation runs fresh every time regardless.

3. **Cache centroid/depot fallback results?**
   - What we know: User marked as Claude's discretion.
   - Recommendation: NO. Centroid and depot coordinates are synthetic, not API results. Caching them would: (a) pollute cache statistics, (b) make it impossible to distinguish "Google says this address is at X" from "we guessed X because we had no data", (c) prevent re-geocoding if the API key is later fixed.

4. **Centroid lookup when area not in dictionary?**
   - What we know: Dictionary has 381 entries, >80% coverage of CDCMS area names verified in Phase 12 tests.
   - Recommendation: Try AddressSplitter fuzzy matching on the address text to find any known place name, then look up its centroid. If no match, fall back to depot. This maximizes the chance of a reasonable coordinate before resorting to depot.

5. **Where to place validation: CachedGeocoder or upload pipeline?**
   - What we know: User marked as Claude's discretion. Success criteria says "CachedGeocoder accepts the validator as an optional parameter."
   - Recommendation: Inject validator into CachedGeocoder but keep the full fallback chain (area retry, centroid lookup, depot) in the upload pipeline. CachedGeocoder handles: cache lookup, upstream call, zone validation check. The upload pipeline handles: passing area_name, deciding fallback strategy when CachedGeocoder returns an out-of-zone result. This respects the success criterion while keeping the pipeline logic in main.py where it has access to the area_name_map and dictionary.
   - Refined approach: The validator is passed to CachedGeocoder. CachedGeocoder delegates to the validator for the full chain (zone check + area retry + centroid + depot), passing through the area_name and the upstream geocoder reference. This way CachedGeocoder stays as the single entry point and the geocode result returned already has the correct confidence/method.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest with pytest-asyncio |
| Config file | `pytest.ini` |
| Quick run command | `pytest tests/core/geocoding/test_validator.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GVAL-01 | Zone validation via haversine (30km radius) | unit | `pytest tests/core/geocoding/test_validator.py::TestZoneCheck -x` | Wave 0 |
| GVAL-02 | Area-name retry on out-of-zone result | unit | `pytest tests/core/geocoding/test_validator.py::TestAreaRetry -x` | Wave 0 |
| GVAL-03 | Dictionary centroid fallback | unit | `pytest tests/core/geocoding/test_validator.py::TestCentroidFallback -x` | Wave 0 |
| GVAL-04 | Confidence scoring by method | unit | `pytest tests/core/geocoding/test_validator.py::TestConfidenceScoring -x` | Wave 0 |
| CB | Circuit breaker after 3 REQUEST_DENIED | unit | `pytest tests/core/geocoding/test_validator.py::TestCircuitBreaker -x` | Wave 0 |
| COMPAT | CachedGeocoder backward compatibility (no validator) | unit | `pytest tests/core/geocoding/test_cache.py -x` | Existing (must pass unchanged) |
| MIGRATION | geocode_method column added | integration | Manual: `alembic upgrade head` + verify column | Manual |
| PIPELINE | Full upload with validation | integration | `pytest tests/core/geocoding/test_validator.py::TestPipelineIntegration -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/core/geocoding/test_validator.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/core/geocoding/test_validator.py` -- covers GVAL-01 through GVAL-04, circuit breaker, depot fallback
- [ ] Alembic migration for geocode_method column
- [ ] Existing `test_cache.py` tests must pass unchanged (backward compatibility)

## Sources

### Primary (HIGH confidence)
- Codebase: `core/geocoding/duplicate_detector.py` -- `haversine_meters()` function (lines 50-64)
- Codebase: `core/geocoding/cache.py` -- `CachedGeocoder` class with decorator pattern
- Codebase: `core/geocoding/google_adapter.py` -- Google API response handling and confidence mapping
- Codebase: `core/geocoding/interfaces.py` -- `GeocodingResult` model
- Codebase: `core/database/models.py` -- `OrderDB` with existing `geocode_confidence` column (line 201), no `geocode_method` yet
- Codebase: `core/data_import/cdcms_preprocessor.py` -- `area_name` column in preprocessed DataFrame (line 294)
- Codebase: `apps/kerala_delivery/config.py` -- `DEPOT_LOCATION`, `CDCMS_AREA_SUFFIX`
- Codebase: `data/place_names_vatakara.json` -- 381 entries with lat/lon centroids
- Codebase: `infra/alembic/env.py` -- Async migration setup with PostGIS filtering
- Codebase: `apps/kerala_delivery/api/main.py` -- Upload pipeline geocoding loop (lines 1062-1141)

### Secondary (MEDIUM confidence)
- CONTEXT.md -- User decisions from `/gsd:discuss-phase` session
- STATE.md -- "Google Maps API key is currently invalid (REQUEST_DENIED)" blocker

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, no new dependencies
- Architecture: HIGH -- all building blocks exist, composition pattern clear from codebase review
- Pitfalls: HIGH -- identified from direct codebase analysis (area_name gap, cache bypass, confidence confusion)

**Key architectural insight:** The `area_name` column exists in the preprocessed DataFrame but is NOT on the Order model and NOT passed through CsvImporter. The upload pipeline must extract the area_name mapping from the preprocessed DataFrame before CsvImporter consumes it, then pass this mapping to the validator during the geocoding loop. This is the single most critical integration detail for this phase.

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (stable -- no external dependencies changing)
