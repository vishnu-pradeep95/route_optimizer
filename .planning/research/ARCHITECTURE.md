# Architecture Research: v2.2 Address Preprocessing Pipeline Integration

**Domain:** Dictionary-powered address splitting and geocode validation for Kerala LPG delivery route optimizer
**Researched:** 2026-03-10
**Confidence:** HIGH (existing codebase thoroughly analyzed, design spec reviewed, all integration points traced through source code)

## Existing System Data Flow (Before Changes)

```
CURRENT ADDRESS PROCESSING PIPELINE
=====================================

User uploads CDCMS CSV
  |
  v
apps/kerala_delivery/api/main.py :: upload_and_optimize()
  |-- _is_cdcms_format() detects tab-separated CDCMS columns
  |
  v
core/data_import/cdcms_preprocessor.py :: preprocess_cdcms()
  |-- Reads raw CDCMS export (tab-separated, 19 columns)
  |-- Filters by OrderStatus = "Allocated-Printed"
  |-- Calls clean_cdcms_address() per row:
  |     Step 1: Remove phone numbers (10-digit regex)
  |     Step 2: Remove CDCMS artifacts (PH: annotations, backticks)
  |     Step 3: Expand abbreviations (NR->Near, PO->P.O., (H)->House)
  |     Step 4: Split digit->uppercase only: re.sub(r"(\d)([A-Z])", ...)
  |     Step 5: Collapse whitespace
  |     Step 6: Title case
  |     Step 7: Append area suffix ", Vatakara, Kozhikode, Kerala"
  |-- Returns DataFrame with columns: order_id, address, quantity, area_name, delivery_man
  |
  v
core/data_import/csv_importer.py :: CsvImporter.import_orders()
  |-- Reads preprocessed CSV
  |-- Creates Order objects with address_raw = cleaned address
  |-- Returns ImportResult (orders + errors + warnings + row_numbers)
  |
  v
apps/kerala_delivery/api/main.py :: geocoding loop (lines 1074-1131)
  |-- For each order without coordinates:
  |     CachedGeocoder.geocode(order.address_raw)
  |       |-- Check PostGIS cache (by normalized key)
  |       |-- Cache HIT -> return Location
  |       |-- Cache MISS -> GoogleGeocoder._call_api(address)
  |       |     |-- Google returns formatted_address, location_type, lat/lon
  |       |     |-- Confidence mapped: ROOFTOP=0.95, INTERPOLATED=0.80, CENTER=0.60, APPROX=0.40
  |       |     |-- Location.address_text = Google's formatted_address     <-- BUG: wrong display text
  |       |-- Save to PostGIS cache
  |       |-- order.location = result.location
  |
  v
core/optimizer/vroom_adapter.py :: VroomAdapter.optimize()
  |-- _build_request(): converts Orders to VROOM JSON jobs
  |-- _parse_response(): converts VROOM solution to RouteAssignment
  |     Line 278: address_display = order.location.address_text or order.address_raw
  |                                 ^^^^^^^^^^^^^^^^^^^^^^^^^
  |                                 On cache MISS: Google's formatted_address (possibly wrong)
  |                                 On cache HIT: original address from cache
  |
  v
core/database/repository.py :: save_optimization_run()
  |-- Saves OptimizationRunDB, OrderDB (with geocode_confidence), RouteDB, RouteStopDB
  |-- OrderDB.address_display = order.location.address_text (Google's text)
  |-- RouteStopDB.address_display = stop.address_display (from vroom_adapter)
  |
  v
API Response: GET /api/routes/{vehicle_id}
  |-- route_db_to_pydantic() converts DB to Pydantic
  |-- Returns stops with address, lat, lon, etc.
  |-- NO geocode_confidence in response currently
  |
  v
Driver PWA: index.html
  |-- Renders stop address from API response
  |-- Navigate button opens Google Maps with lat/lon
  |-- NO "approximate location" indicator currently
```

### Two Interacting Bugs Identified

**Bug 1 -- Insufficient word splitting:**
`clean_cdcms_address()` only splits `digit->uppercase` transitions (`8/542SREESHYLAM` -> `8/542 SREESHYLAM`). CDCMS also concatenates `letter->letter` with no separator: `ANANDAMANDIRAMK.T.BAZAR`, `MUTTUNGAL-POBALAVADI`. These garbled strings produce wrong geocoding results.

**Bug 2 -- `formatted_address` overwrites display text:**
On cache MISS, `Location.address_text` = Google's `formatted_address` (could be "HDFC ERGO Insurance Agent, Palayam, Kozhikode" -- 40km away). This wrong text flows through `vroom_adapter.py:278` into `address_display`, then to the API response, then to the driver's navigation link.

---

## Target Architecture (After Changes)

```
TARGET ADDRESS PROCESSING PIPELINE
=====================================

User uploads CDCMS CSV
  |
  v
api/main.py :: upload_and_optimize()
  |
  v
cdcms_preprocessor.py :: preprocess_cdcms()
  |-- clean_cdcms_address() MODIFIED:
  |     Stage 1: Remove phone numbers, artifacts, backticks (existing)
  |     Stage 2: Word splitting IMPROVED:
  |       (a) Digit->uppercase (existing)
  |       (b) Lowercase->uppercase (NEW regex)                         <-- FIX #1
  |     Stage 3: Dictionary-powered splitting (NEW)                    <-- CORE ADDITION
  |       |-- AddressSplitter.split(text) called between cleanup and title case
  |       |-- Loads place_names_vatakara.json (static, ~285 entries)
  |       |-- Scans for known place names (longest match first)
  |       |-- Splits at place name boundaries
  |       |-- Detects PO/NR between place names
  |       |-- Falls back gracefully if dictionary missing (None check)
  |     Stage 4: Expand abbreviations (existing, reordered to AFTER splitting)
  |     Stage 5: Title case + suffix (existing)
  |
  v
csv_importer.py :: CsvImporter.import_orders()  -- UNCHANGED
  |
  v
api/main.py :: geocoding loop MODIFIED:
  |-- CachedGeocoder.geocode(address, area_name=area_name)            <-- area_name passed
  |     |-- Check PostGIS cache (unchanged)
  |     |-- Cache MISS -> GoogleGeocoder._call_api(address)
  |     |     |-- result.location.address_text still = Google's formatted_address
  |     |
  |     |-- NEW: GeocodeValidator.validate(location, area_name)       <-- FIX #3
  |     |     |-- Haversine distance from depot (11.6244, 75.5796)
  |     |     |-- Within 30km? -> accept as-is
  |     |     |-- Outside 30km? -> Fallback chain:
  |     |     |     1. Retry: geocode("{area_name}, Vatakara, Kozhikode, Kerala")
  |     |     |        -> validate again -> if within 30km, use (confidence * 0.7)
  |     |     |     2. Dictionary centroid: get_area_centroid(area_name)
  |     |     |        -> use centroid coordinates (confidence = 0.3)
  |     |     |     3. Last resort: use original result, flag as unvalidated
  |     |
  |     |-- Save to PostGIS cache (unchanged)
  |
  v
vroom_adapter.py :: VroomAdapter.optimize()
  |-- _parse_response():
  |     Line 278: address_display = order.address_raw                  <-- FIX #2
  |                                 ^^^^^^^^^^^^^^^^
  |                                 ALWAYS use cleaned original, never Google's text
  |
  v
repository.py :: save_optimization_run()  -- UNCHANGED
  |-- OrderDB.geocode_confidence already saved (existing field)
  |
  v
API Response: GET /api/routes/{vehicle_id}  MODIFIED:
  |-- NEW fields in stop JSON:
  |     "geocode_confidence": stop.location.geocode_confidence,
  |     "location_approximate": (confidence is not None and confidence < 0.5)
  |
  v
Driver PWA: index.html  MODIFIED:
  |-- Hero card: "Approx. location" badge (DaisyUI warning badge)
  |-- Compact cards: orange dot indicator for approximate stops
  |-- Informational only -- Navigate button still works
  |-- Driver-verified GPS on delivery corrects the cache for next time
```

---

## New Components

### 1. `core/data_import/address_splitter.py` (NEW)

**Responsibility:** Split concatenated CDCMS address text using a static place name dictionary. Pure function, no I/O beyond initial dictionary load.

**Why a separate module (not inline in cdcms_preprocessor.py):**
- Separation of concerns: preprocessor handles CDCMS format quirks, splitter handles word boundary detection
- Testability: dictionary splitting logic is independently testable with unit tests
- Reusability: if another data source has concatenated text, the splitter works with any text
- The dictionary dependency is injected via the constructor, keeping the splitter loosely coupled

**Component Boundary:**

| Aspect | Detail |
|--------|--------|
| Input | Raw uppercase text from CDCMS address field (after phone/artifact removal, before title case) |
| Output | Same text with spaces inserted at detected place name boundaries |
| Dependencies | `rapidfuzz` (fuzzy matching, MIT, ~200KB), `json` (stdlib) |
| Data source | `data/place_names_vatakara.json` (static, committed to repo) |
| Initialization | Lazy -- loaded on first call to `split()`. If dictionary file missing, returns `None` and preprocessor falls back to regex-only |
| Thread safety | Read-only after init. Dictionary is loaded once, immutable after construction |

**Interface:**

```python
class AddressSplitter:
    def __init__(self, dictionary_path: str | Path):
        """Load place name dictionary from JSON file.
        Sorts entries by name length descending (longest match first).
        """

    def split(self, text: str) -> str:
        """Split concatenated words at known place name boundaries.
        Unknown text passes through unchanged.
        """

    def find_place(self, text: str) -> PlaceMatch | None:
        """Find the best matching place name in the given text.
        Uses rapidfuzz.fuzz.ratio() with threshold 85%.
        Returns PlaceMatch(name, position, confidence) or None.
        """
```

**Integration point in cdcms_preprocessor.py:**

```python
# Module-level lazy initialization
_splitter: AddressSplitter | None = None
_splitter_loaded: bool = False

def _get_splitter() -> AddressSplitter | None:
    global _splitter, _splitter_loaded
    if not _splitter_loaded:
        dict_path = Path(__file__).parent.parent.parent / "data" / "place_names_vatakara.json"
        if dict_path.exists():
            _splitter = AddressSplitter(dict_path)
        _splitter_loaded = True
    return _splitter

# Inside clean_cdcms_address(), between Step 2 (word splitting) and Step 4 (abbreviation expansion):
splitter = _get_splitter()
if splitter is not None:
    addr = splitter.split(addr)
```

### 2. `core/geocoding/validator.py` (NEW)

**Responsibility:** Validate geocoding results against the delivery zone boundary. Implements the fallback chain (area retry -> centroid fallback) for out-of-zone results.

**Why a separate module (not inline in cache.py):**
- Separation of concerns: CachedGeocoder handles cache-then-API flow, validator handles spatial validation
- Testability: zone checking and fallback logic are independently testable with known coordinates
- Reusability: any geocoding source (not just Google) benefits from zone validation
- The haversine function is useful elsewhere (duplicate_detector.py already has one -- this could share it)

**Component Boundary:**

| Aspect | Detail |
|--------|--------|
| Input | A `Location` (lat/lon from geocoding result) + optional `area_name` from CDCMS |
| Output | `ValidationResult` with is_valid flag, distance_from_depot_km, confidence_adjustment, reason |
| Dependencies | `math` (stdlib for haversine), `json` (stdlib for dictionary load) |
| Data source | `data/place_names_vatakara.json` (same dictionary as AddressSplitter) |
| Configuration | `depot: Location`, `max_radius_km: float = 30.0` (injected via constructor) |

**Interface:**

```python
@dataclass
class ValidationResult:
    is_valid: bool
    distance_from_depot_km: float
    confidence_adjustment: float  # 1.0 = no change, 0.7 = area retry, 0.3 = centroid
    reason: str  # "within_zone", "outside_zone", "area_fallback", "centroid_fallback"

class GeocodeValidator:
    def __init__(self, depot: Location, max_radius_km: float = 30.0,
                 dictionary_path: str | Path | None = None):
        """Initialize with depot location and delivery zone radius."""

    def validate(self, location: Location, area_name: str = "") -> ValidationResult:
        """Check if a geocoded location falls within the delivery zone."""

    def get_area_centroid(self, area_name: str) -> Location | None:
        """Look up centroid coordinates for a CDCMS area name.
        Uses fuzzy matching against dictionary.
        """
```

**Integration point in cache.py -- CachedGeocoder:**

The validator integrates into `CachedGeocoder.geocode()` after the upstream provider returns a result but before saving to cache. This requires adding `area_name` as a parameter:

```python
class CachedGeocoder:
    def __init__(self, upstream, session, default_source="google",
                 validator=None, area_suffix=""):           # NEW params
        self._validator = validator
        self._area_suffix = area_suffix

    async def geocode(self, address: str, area_name: str = "") -> GeocodingResult:
        # ... existing cache check ...

        result = self._upstream.geocode(address)

        # NEW: Validate result if validator configured
        if result.success and result.location and self._validator:
            validation = self._validator.validate(result.location, area_name)
            if not validation.is_valid:
                # Execute fallback chain
                result = await self._try_fallbacks(result, area_name, validation)

        # ... existing cache save ...
```

**Fallback chain detail:**

```
geocode(address) -> location outside 30km?
  |
  |-- Retry #1: geocode("{area_name}, Vatakara, Kozhikode, Kerala")
  |     |-- Within 30km? -> use this result (confidence * 0.7)
  |     |-- Still outside? -> continue to #2
  |
  |-- Retry #2: get_area_centroid(area_name) from dictionary
  |     |-- Found in dictionary? -> use centroid (confidence = 0.3)
  |     |-- Not found? -> continue to #3
  |
  |-- Fallback #3: use original result, unmodified
  |     |-- Log warning "geocode outside delivery zone"
  |     |-- Original confidence preserved (driver still gets a location)
```

### 3. `data/place_names_vatakara.json` (NEW)

**Responsibility:** Static dictionary of ~285 place names within 30km of the Vatakara depot. Contains names, aliases, types, coordinates, and sources.

**Built by:** `scripts/build_place_dictionary.py` (one-time script)
**Data sources:** OSM Overpass API (hamlets, villages, neighbourhoods) + PostalPinCode API (post office names)
**Committed to repo:** Yes -- no runtime API calls needed

**Schema (from design spec):**

```json
{
  "metadata": {
    "generated_at": "2026-03-10T12:00:00Z",
    "depot": {"latitude": 11.6244, "longitude": 75.5796},
    "radius_km": 30,
    "sources": ["osm_overpass", "india_post_pincode"],
    "total_entries": 285
  },
  "places": [
    {
      "name": "VALLIKKADU",
      "name_ml": "...",
      "aliases": ["VALLIKADU", "VALLIKKAD"],
      "type": "hamlet",
      "latitude": 11.6312,
      "longitude": 75.5845,
      "source": "osm"
    }
  ],
  "post_offices": [
    {
      "name": "MUTTUNGAL",
      "pincode": "673104",
      "latitude": 11.6201,
      "longitude": 75.5867,
      "source": "india_post"
    }
  ]
}
```

**Consumed by:**
- `AddressSplitter` -- for word boundary detection (place name matching)
- `GeocodeValidator` -- for area centroid fallback coordinates

### 4. `scripts/build_place_dictionary.py` (NEW)

**Responsibility:** One-time (or periodic) script that fetches place names from public APIs and merges them into the static JSON dictionary.

**Not imported at runtime.** Only used by developers to refresh the dictionary.

---

## Modified Components

### 1. `core/data_import/cdcms_preprocessor.py` (MODIFIED)

**Changes:**
1. Add `lowercase->uppercase` word split regex alongside existing `digit->uppercase` split
2. Reorder cleaning steps: word splitting BEFORE abbreviation expansion (so `NR`, `PO` patterns are detected after words are separated)
3. Integrate `AddressSplitter` with lazy initialization and graceful fallback

**Line-level changes:**

| Location | Current | New |
|----------|---------|-----|
| Line 269 | `re.sub(r"(\d)([A-Z])", r"\1 \2", addr)` | Add: `re.sub(r"([a-z])([A-Z])", r"\1 \2", addr)` |
| After line 269 | (nothing) | Call `_get_splitter().split(addr)` if splitter available |
| Step ordering | Steps: phone -> artifacts -> abbreviations -> digit-split -> whitespace -> title case | Steps: phone -> artifacts -> digit-split -> letter-split -> dictionary-split -> abbreviations -> whitespace -> title case |

**Impact on existing tests:** `tests/core/data_import/test_cdcms_preprocessor.py` may need updates for step reordering. Some expected outputs may change because abbreviation expansion now happens after splitting. All changes improve output quality.

### 2. `core/optimizer/vroom_adapter.py` (MODIFIED)

**Change:** One line fix at line 278.

```python
# BEFORE:
address_display=order.location.address_text or order.address_raw,

# AFTER:
address_display=order.address_raw,
```

**Rationale:** `order.address_raw` is the cleaned CDCMS address that the driver recognizes. `order.location.address_text` is Google's `formatted_address` which may reference a completely different place (e.g., "HDFC ERGO Insurance Agent, Palayam, Kozhikode"). The driver should always see the address from the CSV.

**Impact:** `address_display` in all `RouteStop` objects will now use the original cleaned address instead of Google's interpretation. This is the correct behavior for all cases (cache hit and cache miss alike).

### 3. `core/geocoding/cache.py` (MODIFIED)

**Changes:**
1. Accept optional `validator: GeocodeValidator` and `area_suffix: str` in constructor
2. Accept optional `area_name: str` parameter in `geocode()` method
3. Add fallback chain logic after upstream returns a result
4. Add `_try_fallbacks()` private method for area retry and centroid fallback

**Backward compatibility:** All new parameters are optional with defaults. Existing callers (tests, scripts) that construct `CachedGeocoder` without a validator will work unchanged -- validation is simply skipped.

**The critical integration question -- where does `area_name` come from?**

In the API's `upload_and_optimize()` geocoding loop, the CDCMS preprocessor preserves `area_name` in the DataFrame and it flows into the import result. However, `Order` does not have an `area_name` field -- the field is on the DataFrame, not on the Order object.

**Solution:** Pass `area_name` through a side channel. The `preprocess_cdcms()` output DataFrame has an `area_name` column. The API code already has access to `preprocessed_df`. Build a mapping `order_id -> area_name` before the geocoding loop:

```python
# In upload_and_optimize(), after orders are imported:
area_name_map: dict[str, str] = {}
if is_cdcms and not preprocessed_df.empty:
    for _, row in preprocessed_df.iterrows():
        area_name_map[str(row["order_id"])] = str(row.get("area_name", ""))

# In geocoding loop:
for order in orders:
    if not order.is_geocoded:
        area_name = area_name_map.get(order.order_id, "")
        result = await cached_geocoder.geocode(order.address_raw, area_name=area_name)
```

### 4. `apps/kerala_delivery/api/main.py` (MODIFIED)

**Changes:**
1. Add `geocode_confidence` and `location_approximate` fields to stop JSON in `GET /api/routes/{vehicle_id}` (line ~1470) and batch mode in `GET /api/routes?include_stops=true` (line ~1388)
2. Construct `GeocodeValidator` and pass it to `CachedGeocoder` in the geocoding section
3. Build `area_name_map` from preprocessed DataFrame
4. Pass `area_name` to `cached_geocoder.geocode()` calls

**Stop JSON additions (two endpoints):**

```python
{
    "sequence": stop.sequence,
    "order_id": stop.order_id,
    "address": stop.address_display,
    "latitude": stop.location.latitude,
    "longitude": stop.location.longitude,
    "geocode_confidence": stop.location.geocode_confidence,      # NEW
    "location_approximate": (                                     # NEW
        stop.location.geocode_confidence is not None
        and stop.location.geocode_confidence < 0.5
    ),
    # ... existing fields ...
}
```

**Geocoder construction change:**

```python
# BEFORE:
cached_geocoder = CachedGeocoder(upstream=geocoder, session=session) if geocoder else None

# AFTER:
from core.geocoding.validator import GeocodeValidator
validator = GeocodeValidator(
    depot=config.DEPOT_LOCATION,
    max_radius_km=30.0,
    dictionary_path=Path(__file__).parent.parent.parent.parent / "data" / "place_names_vatakara.json",
)
cached_geocoder = CachedGeocoder(
    upstream=geocoder,
    session=session,
    validator=validator,
    area_suffix=config.CDCMS_AREA_SUFFIX,
) if geocoder else None
```

### 5. `apps/kerala_delivery/driver_app/index.html` (MODIFIED)

**Changes:** Add visual indicators for approximate locations.

**Hero card (next pending stop):**
```html
<!-- After address display, inside hero card -->
<div class="tw:badge tw:badge-warning tw:badge-sm tw:gap-1"
     style="display: ${stop.location_approximate ? 'inline-flex' : 'none'}">
  <span>~</span> Approx. location
</div>
```

**Compact card (remaining stops):**
```html
<!-- Orange dot next to address text -->
<span class="tw:text-warning" title="Approximate location"
      style="display: ${stop.location_approximate ? 'inline' : 'none'}">
  &#9679;
</span>
```

**Driver behavior:** Informational only. Navigate button still works with the approximate coordinates. Google Maps opens at the area center, and the driver calls the customer for exact directions. When driver marks "Done" and confirms GPS, `save_driver_verified()` caches the correct location for next time.

---

## Unchanged Components

| Component | Why No Change |
|-----------|--------------|
| `core/geocoding/normalize.py` | Cache key normalization is orthogonal. Dictionary splitting happens before cache lookup. |
| `core/geocoding/google_adapter.py` | Pure API caller. No changes needed -- it still sends addresses and returns results. |
| `core/geocoding/interfaces.py` | Geocoder/AsyncGeocoder protocols unchanged. Validation is external to the protocol. |
| `core/geocoding/duplicate_detector.py` | Already has `haversine_meters()`. The validator could share it, but circular imports are a concern. Better to have a standalone haversine in validator.py (10 lines, no dependency). |
| `core/models/location.py` | Already has `geocode_confidence` field. No schema change needed. |
| `core/models/order.py` | `address_raw` already preserved. No field additions needed. |
| `core/models/route.py` | `RouteStop.location` already carries confidence via `Location.geocode_confidence`. |
| `core/database/models.py` | `OrderDB.geocode_confidence` already exists. `RouteStopDB.location` already stores PostGIS point. No migration needed. |
| `core/database/repository.py` | `save_optimization_run()` already persists `geocode_confidence`. `route_db_to_pydantic()` already passes confidence through. |
| `core/data_import/csv_importer.py` | Generic importer. CDCMS-specific changes stay in preprocessor. |
| `apps/kerala_delivery/config.py` | `DEPOT_LOCATION`, `CDCMS_AREA_SUFFIX` already exist. No new config constants needed. |

---

## Data Flow Changes (Detailed)

### Change 1: Address Cleaning Pipeline Reorder

```
BEFORE:                               AFTER:
Step 1: Phone removal                 Step 1: Phone removal
Step 2: Artifact removal              Step 2: Artifact removal
Step 3: Abbreviation expansion        Step 3: Digit->uppercase split (existing)
Step 4: Digit->uppercase split        Step 4: Lowercase->uppercase split (NEW)
Step 5: Whitespace collapse           Step 5: Dictionary-powered split (NEW)
Step 6: Title case                    Step 6: Abbreviation expansion (MOVED)
Step 7: Title case artifacts fix      Step 7: Whitespace collapse
Step 8: Area suffix                   Step 8: Title case
                                      Step 9: Title case artifacts fix
                                      Step 10: Area suffix
```

**Why reorder?** Abbreviation expansion converts `NR.` to `Near`, `PO.` to `P.O.`. If this happens before splitting, the split patterns can not detect `NR` or `PO` in concatenated text. Example: `KUNIYILNR.EK GOPALAN` -- expanding `NR.` first gives `KUNIYILNear EK GOPALAN` (wrong). Splitting first detects `KUNIYIL` as a place name, then the remainder `NR.EK GOPALAN` gets expanded to `Near EK GOPALAN` (correct).

### Change 2: Geocoding Flow Adds Validation Layer

```
BEFORE:
  address -> cache check -> miss -> Google API -> save to cache -> return

AFTER:
  address -> cache check -> miss -> Google API
    -> VALIDATE (within 30km?)
    -> YES: save to cache -> return
    -> NO: retry with area name -> validate again
        -> YES: save to cache (confidence * 0.7) -> return
        -> NO: centroid fallback (confidence = 0.3) -> save to cache -> return
```

**Cache interaction:** The validation result (including adjusted confidence) is what gets saved to the PostGIS cache. Future cache hits for the same address will return the validated (possibly fallback) location, not the original wrong one. This means the fallback chain runs at most once per address.

### Change 3: API Response Adds Confidence Fields

```
BEFORE (GET /api/routes/{vehicle_id}):
{
  "stops": [
    {"sequence": 1, "address": "...", "latitude": ..., "longitude": ..., ...}
  ]
}

AFTER:
{
  "stops": [
    {
      "sequence": 1,
      "address": "...",
      "latitude": ...,
      "longitude": ...,
      "geocode_confidence": 0.95,          // NEW
      "location_approximate": false,        // NEW
      ...
    }
  ]
}
```

**Backward compatibility:** New fields are additive. Existing consumers that don't read `geocode_confidence` or `location_approximate` are unaffected. The driver PWA will be updated to display badges, but older cached versions of the PWA will simply ignore the new fields.

### Change 4: Display Text Source Change

```
BEFORE:
  RouteStop.address_display = order.location.address_text    (Google's formatted_address)
                                 OR order.address_raw         (fallback)

AFTER:
  RouteStop.address_display = order.address_raw               (ALWAYS cleaned original)
```

**This affects all routes, not just new ones.** Existing cached geocode results still have `address_text = formatted_address`, but the vroom adapter now ignores that field. The display always comes from the CSV source.

---

## Dependency Graph (Build Order)

```
Phase 1: Foundation Fixes (no dependencies)
  |-- 1.1: Fix address_display source (vroom_adapter.py:278) -- ONE LINE
  |-- 1.2: Add lowercase->uppercase regex (cdcms_preprocessor.py)
  |-- 1.3: Reorder cleaning steps (cdcms_preprocessor.py)
  |-- 1.4-1.5: Update/add tests
  |
Phase 2: Place Name Dictionary (no runtime dependencies on Phase 1)
  |-- 2.1: Write build_place_dictionary.py
  |-- 2.2: Run script, generate place_names_vatakara.json
  |-- 2.3: Build AddressSplitter class
  |-- 2.4: Add fuzzy matching with RapidFuzz
  |-- 2.5: Integrate splitter into clean_cdcms_address() -- depends on 1.3 (step reorder)
  |-- 2.6: Tests
  |
Phase 3: Geocode Validation (depends on 2.2 for dictionary)
  |-- 3.1: Implement haversine utility
  |-- 3.2: Build GeocodeValidator
  |-- 3.3: Add area centroid lookup
  |-- 3.4: Integrate into CachedGeocoder -- depends on 3.2
  |-- 3.5: Add retry-with-area-name fallback -- depends on 3.4
  |-- 3.6: Tests
  |
Phase 4: API + Driver UI (depends on 3.4 for confidence data)
  |-- 4.1: Add confidence fields to API response
  |-- 4.2: Add "Approx. location" badge to hero card
  |-- 4.3: Add orange dot to compact cards
  |-- 4.4: E2E tests
  |
Phase 5: Integration Testing (depends on all above)
  |-- 5.1: Full pipeline test with sample_cdcms_export.csv
  |-- 5.2: Verify "HDFC ERGO" bug is fixed
  |-- 5.3: Measure accuracy metrics
  |-- 5.4: Document upgrade trigger criteria for Approach B (NER)
```

### Build Order Rationale

- **Phase 1 first** because the `address_display` fix and regex improvements are safe, independent, and immediately beneficial. They can ship before the dictionary exists.
- **Phase 2 before Phase 3** because the validator uses the same dictionary for area centroid lookups. Building the dictionary infrastructure once and sharing it across both components avoids duplication.
- **Phase 3 before Phase 4** because the API confidence fields are only meaningful after the validator assigns adjusted confidence scores. Without validation, all Google results have the same confidence regardless of whether they are in-zone.
- **Phase 4 last (before integration testing)** because UI changes should reflect the complete pipeline behavior, not an intermediate state.
- **Phase 5 is verification, not implementation** -- it tests the assembled pipeline end-to-end.

---

## Haversine Function Sharing Decision

The codebase already has `haversine_meters()` in `core/geocoding/duplicate_detector.py` (lines 50-64). The new `GeocodeValidator` also needs haversine distance.

**Decision: Duplicate the haversine function in `validator.py`.**

**Rationale:**
- The function is 10 lines of pure math with no dependencies
- Extracting to a shared `core/geocoding/utils.py` would require modifying `duplicate_detector.py` imports, which adds a code change and test update to a module that is NOT part of this milestone
- The haversine formula is universally known and unlikely to have bugs or need changes
- If a shared utility becomes warranted later (3+ call sites), refactor then

---

## Scalability Considerations

| Concern | At 50 orders/day (current) | At 500 orders/day | At 5000 orders/day |
|---------|---------------------------|--------------------|--------------------|
| Dictionary loading | ~5ms one-time (285 entries) | Same -- loaded once | Same |
| Fuzzy matching per address | ~0.1ms (scan 285 entries) | Acceptable | Consider building a Trie or prefix index |
| Validation (haversine) | <0.01ms per check | Negligible | Negligible |
| Fallback retries (area geocode) | 1 extra Google API call per out-of-zone | Same cost per failure | Consider batch validation |
| Dictionary maintenance | Manual refresh via script | Same | Need automated refresh + versioning |

At the current scale of 40-50 deliveries/day, all performance concerns are negligible. The dictionary scan is O(n) where n=285, taking ~0.1ms per address. Even at 500 orders, this adds only 50ms total.

---

## Integration Risk Assessment

| Integration Point | Risk Level | What Could Go Wrong | Mitigation |
|-------------------|-----------|---------------------|------------|
| Step reordering in clean_cdcms_address() | Medium | Existing test expectations change | Run full test suite after reorder. Most changes are improvements. |
| AddressSplitter lazy init | Low | Dictionary file missing at runtime | Graceful None fallback. Preprocessor works without splitter (regex-only). |
| Validator in CachedGeocoder | Medium | area_name not available (non-CDCMS uploads) | Default area_name="" skips area retry. Still does zone check. |
| API response additions | Low | Breaking change for consumers | Additive fields only. No existing fields removed. |
| Driver PWA badge | Low | Older cached PWA versions | New fields ignored by old JS. Badge simply won't appear. |
| vroom_adapter address_display fix | Low | Some consumers expected Google's formatted_address | address_raw is always present and more recognizable to drivers. |

---

## Sources

- Design spec: `docs/superpowers/specs/2026-03-10-address-preprocessing-design.md` -- comprehensive design document with algorithm details, interface definitions, and implementation plan
- Existing codebase architecture: `.planning/codebase/ARCHITECTURE.md` -- system layer analysis
- Source code analysis: `core/data_import/cdcms_preprocessor.py`, `core/geocoding/cache.py`, `core/geocoding/google_adapter.py`, `core/geocoding/validator.py` (planned), `core/optimizer/vroom_adapter.py`, `core/database/repository.py`, `core/database/models.py`, `apps/kerala_delivery/api/main.py`
- Project context: `.planning/PROJECT.md` -- constraints, key decisions, scope

---
*Architecture research for: v2.2 Address Preprocessing Pipeline*
*Researched: 2026-03-10*
