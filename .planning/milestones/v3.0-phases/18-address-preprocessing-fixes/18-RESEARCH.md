# Phase 18: Address Preprocessing Fixes - Research

**Researched:** 2026-03-13
**Domain:** CDCMS address text cleaning, geocode zone validation, MapLibre map overlays
**Confidence:** HIGH

## Summary

Phase 18 verifies and fixes address cleaning patterns implemented in v2.2, reduces the geocode validation zone from 30km to 20km, and adds a visual zone boundary on the dashboard map. Real data analysis of `data/Refill.xlsx` (2,398 orders, 1,885 Allocated-Printed, 68 areas, 35 drivers) reveals **critical bugs** in the current cleaning pipeline that garble a significant fraction of addresses.

The three main bug categories are: (1) `(HO)` notation (172 occurrences) is NOT handled by the existing `(H)` regex -- `\(H\)` does not match `\(HO\)`; (2) `(PO)` notation (368 occurrences) is not handled -- only `PO.` (inline) and standalone `PO` are caught; (3) trailing-letter-split still garbles words when `(H)` or `(HO)` appear without spaces before them (e.g., `CHALIL(H)` becomes "Chalilhouse" then gets trailing letter split). These are not edge cases -- they affect 540+ of 1,885 orders.

The zone radius change (30km to 20km) is straightforward: update `config.py`, add env var overrides for DEPOT_LAT/DEPOT_LON/GEOCODE_ZONE_RADIUS_KM, rebuild the place name dictionary at 20km, update `/api/config` response, and draw a dashed circle on the dashboard map using `@turf/circle` to generate a GeoJSON polygon.

**Primary recommendation:** Fix the `(HO)` and `(PO)` regex patterns first (they affect the most addresses), then fix spacing around parenthesized abbreviations, reduce the zone radius, rebuild the dictionary, add the map circle, and write comprehensive tests at all levels.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- v2.2 already implemented MUTTUNGAL protection, (H) expansion, and PO two-pass splitting
- This phase runs real CDCMS data (data/Refill.xlsx) through the pipeline to verify correctness
- If bugs are found, fix in existing v2.2 code (extend protected words, regex, dictionary -- not new layers)
- Comprehensive tests at all levels -- unit tests, API-level tests, and Playwright E2E -- no shortcuts
- Use real data/Refill.xlsx for both API-level and Playwright E2E testing
- API-level tests: POST to upload endpoints, verify cleaned address text and valid coordinates
- Playwright E2E: upload Refill.xlsx through dashboard, verify addresses display correctly in route view
- Add targeted unit tests for specific MUTTUNGAL/(H)/PO patterns found in Refill.xlsx
- Comprehensive coverage -- don't cheap out on test count
- Change GEOCODE_ZONE_RADIUS_KM from 30 to 20 (hard boundary, no buffer zone)
- Make depot lat/lon env-configurable (DEPOT_LAT, DEPOT_LON env vars override config.py defaults)
- Make zone radius env-configurable (GEOCODE_ZONE_RADIUS_KM env var, default 20)
- Rebuild place_names_vatakara.json dictionary at 20km radius (rerun OSM Overpass, same approach as v2.2)
- No audit log of removed entries -- trust the radius
- Expose zone_radius_km in /api/config response alongside depot coordinates
- Draw a dashed 20km zone circle on the dashboard live map showing the delivery boundary
- Out-of-zone addresses (>20km) are hard-rejected -- flagged as out-of-zone with UI warning
- Don't pre-guess edge cases -- let the real data reveal them
- Process Refill.xlsx through the pipeline, examine output for garbling
- Fix any found issues in existing v2.2 code (extend patterns, not new heuristics)
- If no issues found, phase focuses on radius change + env config + map circle + tests

### Claude's Discretion
- OSM Overpass query parameters for 20km dictionary rebuild
- Exact Playwright test structure and assertion patterns
- How to integrate zone circle with existing MapLibre live map component
- Whether to use MapLibre Circle or GeoJSON polygon for the zone boundary

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ADDR-01 | System correctly preserves "MUTTUNGAL" as a single word | Already in `_PROTECTED_WORDS`. Verified working for standalone MUTTUNGAL. BUT trailing-letter split still garbles adjacent words in compound patterns like `CHALIL(H)7/214A` |
| ADDR-02 | System correctly handles (H) expansion without splitting adjacent words | **BUG FOUND**: `(HO)` (172 occurrences) is NOT matched by `\(H\)` regex. Also `(H)` without preceding space (`CHALIL(H)`) garbles output. Need to add `(HO)` pattern and ensure spacing around parenthesized abbreviations |
| ADDR-03 | System correctly splits PO abbreviations from concatenated text | **BUG FOUND**: `(PO)` (368 occurrences) is NOT handled. Only `PO.` inline and standalone `PO` are caught. Need `(PO)` regex pattern. Also `(PO)` without space before/after garbles output |
| ADDR-04 | Geocode validation uses 20km radius | Change `GEOCODE_ZONE_RADIUS_KM = 20` in config.py, add env var override, rebuild dictionary at 20km |
| ADDR-05 | Geocode validation centroid is always the Vatakara depot location from config | Already implemented. Adding env var overrides for DEPOT_LAT/DEPOT_LON ensures configurability |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `re` | stdlib | Regex-based address cleaning | Already used in cdcms_preprocessor.py |
| RapidFuzz | existing | Fuzzy matching in dictionary splitter | Already a dependency |
| `@turf/circle` | 7.x | Generate GeoJSON circle polygon for zone boundary | Minimal Turf.js module, 64-vertex polygon from center+radius |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| react-map-gl | ^8.1.0 | Source/Layer components for zone circle | Already installed, used by RouteMap |
| maplibre-gl | ^5.18.0 | Map rendering engine | Already installed |
| requests | existing | OSM Overpass API call for dictionary rebuild | Already used by build_place_dictionary.py |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| @turf/circle | Hand-rolled math (cos/sin in TS) | @turf/circle is 2KB, battle-tested, handles lat/lon distortion correctly; hand-rolled risks inaccuracy near poles |
| @turf/circle | Full @turf/turf | Full package is 200KB+; we only need circle generation |

**Installation:**
```bash
cd apps/kerala_delivery/dashboard
npm install @turf/circle @turf/helpers
```

## Architecture Patterns

### Recommended Changes Structure
```
core/data_import/
  cdcms_preprocessor.py    # FIX: Add (HO), (PO) regex; fix spacing
apps/kerala_delivery/
  config.py                # MODIFY: env vars, radius 30->20
  api/main.py              # MODIFY: AppConfig + zone_radius_km
dashboard/src/
  components/RouteMap.tsx   # ADD: Zone circle GeoJSON layer
  lib/api.ts               # ADD: fetchAppConfig function
scripts/
  build_place_dictionary.py # MODIFY: RADIUS_M 30000->20000
data/
  place_names_vatakara.json # REGENERATE: at 20km radius
tests/
  core/data_import/test_cdcms_preprocessor.py    # ADD: new test cases
  core/geocoding/test_validator.py               # UPDATE: 30_000->20_000
  core/geocoding/test_interfaces_method.py       # UPDATE: ==30 -> ==20
  integration/test_address_pipeline.py           # UPDATE: 30km refs->20km
```

### Pattern 1: Parenthesized Abbreviation Handling
**What:** Add regex patterns for `(HO)` and `(PO)` before the existing `(H)` pattern
**When to use:** Step 4 of clean_cdcms_address, before word splitting
**Example:**
```python
# In cdcms_preprocessor.py, Step 4 (abbreviation expansion, first pass)

# (HO) -> House (must come BEFORE (H) pattern)
# Handles: "CHEMERI (HO) MUTTUNGAL", "PERATTEYATH(HO)CHORODE"
addr = re.sub(r"\(HO\)", " House ", addr, flags=re.IGNORECASE)

# (H) -> House (existing pattern, unchanged)
addr = re.sub(r"\(H\)", " House ", addr, flags=re.IGNORECASE)

# (PO) -> P.O. (new pattern)
# Handles: "CHORODE (PO)", "CHORODE(PO)POOLAKANDY"
addr = re.sub(r"\(PO\)", " P.O. ", addr, flags=re.IGNORECASE)
```

### Pattern 2: Env Var Config Override
**What:** Follow existing pattern in config.py for env var overrides
**When to use:** For DEPOT_LAT, DEPOT_LON, GEOCODE_ZONE_RADIUS_KM
**Example:**
```python
# In config.py -- follow existing VROOM_URL pattern
DEPOT_LOCATION = Location(
    latitude=float(os.environ.get("DEPOT_LAT", "11.624443730714066")),
    longitude=float(os.environ.get("DEPOT_LON", "75.57964507762223")),
    address_text="LPG Godown (Main Depot)",
)

GEOCODE_ZONE_RADIUS_KM = int(os.environ.get("GEOCODE_ZONE_RADIUS_KM", "20"))
```

### Pattern 3: Zone Circle GeoJSON Layer
**What:** Generate a dashed circle polygon using @turf/circle, render as MapLibre layer
**When to use:** RouteMap component, always visible overlay
**Example:**
```typescript
// In RouteMap.tsx
import circle from '@turf/circle';

// Generate 20km radius circle centered on depot
const zoneCircle = useMemo(() => {
  return circle(
    [VATAKARA_CENTER.longitude, VATAKARA_CENTER.latitude],
    20, // radius in km
    { steps: 64, units: 'kilometers' }
  );
}, []);

// Render as dashed line layer
<Source id="zone-boundary" type="geojson" data={zoneCircle}>
  <Layer
    id="zone-boundary-line"
    type="line"
    paint={{
      "line-color": "#888",
      "line-width": 1.5,
      "line-dasharray": [4, 4],
      "line-opacity": 0.6,
    }}
  />
</Source>
```

### Anti-Patterns to Avoid
- **Adding new cleaning layers instead of fixing existing patterns:** Fix the regex in Step 4 of clean_cdcms_address, don't add a new Step 4.5
- **Hardcoding zone_radius_km in the dashboard:** Fetch from /api/config, don't duplicate the value
- **Using MapLibre's native circle layer type:** That's for point-radius visualization (fixed pixel size), not geographic circles. Use GeoJSON polygon from @turf/circle
- **Processing the full Refill.xlsx through geocoding in tests:** Use only address cleaning (preprocess_cdcms) for unit/API tests. Real geocoding costs API calls

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Geographic circle polygon | Custom cos/sin math | `@turf/circle` | Handles lat/lon distortion, battle-tested, 2KB |
| Haversine distance | Custom implementation | Existing `haversine_meters()` | Already in `core/geocoding/duplicate_detector.py` |
| Dictionary rebuild | Custom OSM query | Existing `scripts/build_place_dictionary.py` | Just change RADIUS_M constant |

**Key insight:** Most of the infrastructure already exists. The bugs are in regex patterns (missing `(HO)` and `(PO)`), not in architecture.

## Common Pitfalls

### Pitfall 1: (HO) vs (H) Regex Order
**What goes wrong:** If `(H)` regex runs before `(HO)`, it matches the `(H` part of `(HO)` incorrectly, leaving a dangling `O)`.
**Why it happens:** `\(H\)` with IGNORECASE matches `(H)` but not `(HO)`. The issue is that `(HO)` is never matched at all.
**How to avoid:** Add `\(HO\)` pattern BEFORE `\(H\)` pattern in Step 4. Test both patterns independently.
**Warning signs:** Addresses containing `(Ho)` or `(Ho )` in cleaned output.

### Pitfall 2: Spacing Around Parenthesized Abbreviations
**What goes wrong:** `CHALIL(H)7/214A` -> `CHALILHOUSE7/214A` (no spaces inserted) -> trailing letter split garbles
**Why it happens:** The regex `\(H\)` -> `House` replaces but doesn't add surrounding spaces. When `(H)` is concatenated with adjacent text, the replacement merges words.
**How to avoid:** Use ` House ` (with spaces) in the replacement string. The Step 8 collapse-spaces cleanup removes any doubles.
**Warning signs:** Words concatenated with "House" in output (e.g., "Chalilhouse", "Housekuniyil").

### Pitfall 3: (PO) vs Inline PO.
**What goes wrong:** `(PO)` is a different pattern from `PO.` -- the parentheses make it distinct. Current code only handles `([a-zA-Z])PO\.` (inline with dot) and `\bPO\b` (standalone).
**Why it happens:** `(PO)` has parentheses that prevent both patterns from matching.
**How to avoid:** Add explicit `\(PO\)` -> ` P.O. ` pattern in Step 4, before word splitting. 368 of 1,885 orders use this notation.
**Warning signs:** Addresses containing `(P.O. )` or `(Po)` in cleaned output.

### Pitfall 4: Test Hardcoded Zone Radius Values
**What goes wrong:** Tests assert `== 30` for zone radius but config changes to 20.
**Why it happens:** Multiple test files hardcode `30_000` or `== 30`.
**How to avoid:** Grep for `30_000`, `== 30`, and `30km` across all test files and update.
**Warning signs:** Tests failing after config change.
**Known locations:**
- `tests/core/geocoding/test_interfaces_method.py:70` -- `assert GEOCODE_ZONE_RADIUS_KM == 30`
- `tests/core/geocoding/test_validator.py:83` -- `zone_radius_m=30_000`
- `tests/integration/test_address_pipeline.py` -- comments referencing 30km

### Pitfall 5: Dictionary Rebuild Removes Valid Entries
**What goes wrong:** Reducing radius from 30km to 20km may remove places that are within the delivery zone but whose OSM nodes are at the edge.
**Why it happens:** OSM place nodes may be positioned at the geographic center of a village, which could be >20km from the depot even if parts of the village are within range.
**How to avoid:** After rebuilding, run the coverage validation (`validate_coverage()` in build_place_dictionary.py) against Refill.xlsx area names. Check that coverage remains >= 80%.
**Warning signs:** Coverage dropping below 80%, CDCMS area names missing from rebuilt dictionary.

### Pitfall 6: AppConfig Model Must Be Updated
**What goes wrong:** Adding `zone_radius_km` to the API response but not to the Pydantic `AppConfig` model causes a validation error.
**Why it happens:** FastAPI enforces `response_model=AppConfig` on the endpoint.
**How to avoid:** Add the field to the `AppConfig` class before returning it.

## Code Examples

### Fix 1: Add (HO) and (PO) Patterns to Step 4
```python
# In cdcms_preprocessor.py, clean_cdcms_address(), Step 4
# Source: Analysis of data/Refill.xlsx -- 172 (HO), 368 (PO), 104 (H) occurrences

# (HO) -> House  (MUST come before (H) to avoid partial match)
# Space padding ensures words don't concatenate with "House"
addr = re.sub(r"\(HO\)", " House ", addr, flags=re.IGNORECASE)

# (H) -> House  (existing, add space padding)
addr = re.sub(r"\(H\)", " House ", addr, flags=re.IGNORECASE)

# (PO) -> P.O.  (new -- 368 occurrences in Refill.xlsx)
addr = re.sub(r"\(PO\)", " P.O. ", addr, flags=re.IGNORECASE)
```

### Fix 2: Config.py Env Var Overrides
```python
# In apps/kerala_delivery/config.py

import os
from core.models.location import Location

# Depot location with env var overrides
DEPOT_LOCATION = Location(
    latitude=float(os.environ.get("DEPOT_LAT", "11.624443730714066")),
    longitude=float(os.environ.get("DEPOT_LON", "75.57964507762223")),
    address_text="LPG Godown (Main Depot)",
)

# Zone radius: 20km default, overridable via env var
GEOCODE_ZONE_RADIUS_KM = int(os.environ.get("GEOCODE_ZONE_RADIUS_KM", "20"))
```

### Fix 3: AppConfig Model + Endpoint
```python
# In api/main.py

class AppConfig(BaseModel):
    """Public application configuration served to frontend clients."""
    depot_lat: float = Field(description="Depot latitude")
    depot_lng: float = Field(description="Depot longitude")
    safety_multiplier: float = Field(description="Route time safety multiplier")
    office_phone_number: str = Field(description="Office phone in E.164 format")
    zone_radius_km: float = Field(description="Geocode validation zone radius in km")

@app.get("/api/config", response_model=AppConfig)
async def get_app_config():
    return AppConfig(
        depot_lat=config.DEPOT_LOCATION.latitude,
        depot_lng=config.DEPOT_LOCATION.longitude,
        safety_multiplier=config.SAFETY_MULTIPLIER,
        office_phone_number=config.OFFICE_PHONE_NUMBER,
        zone_radius_km=config.GEOCODE_ZONE_RADIUS_KM,
    )
```

### Fix 4: Zone Circle on Dashboard Map
```typescript
// In RouteMap.tsx -- add zone boundary circle
import circle from '@turf/circle';

// Inside RouteMap component:
const zoneCircle = useMemo(() => {
  return circle(
    [VATAKARA_CENTER.longitude, VATAKARA_CENTER.latitude],
    20, // TODO: fetch from /api/config zone_radius_km
    { steps: 64, units: 'kilometers' }
  );
}, []);

// Inside <Map> component, BEFORE route layers (so it's behind):
<Source id="zone-boundary" type="geojson" data={zoneCircle}>
  <Layer
    id="zone-boundary-line"
    type="line"
    paint={{
      "line-color": "#888888",
      "line-width": 1.5,
      "line-dasharray": [4, 4],
      "line-opacity": 0.5,
    }}
  />
</Source>
```

### Fix 5: Dictionary Rebuild at 20km
```python
# In scripts/build_place_dictionary.py -- change radius
RADIUS_M = 20000      # was 30000
RADIUS_KM = RADIUS_M // 1000  # now 20
```

## Real Data Analysis Results

**Source:** `data/Refill.xlsx` (2,398 total orders, 1,885 Allocated-Printed)

### Pattern Frequency in Refill.xlsx
| Pattern | Count | Current Status | Fix Needed |
|---------|-------|----------------|------------|
| `(HO)` notation | 172 | NOT HANDLED -- regex `\(H\)` doesn't match `(HO)` | Add `\(HO\)` pattern |
| `(H)` notation | 104 | Handled when space-separated, garbled when concatenated | Add space padding to replacement |
| `(PO)` notation | 368 | NOT HANDLED -- parentheses prevent match | Add `\(PO\)` pattern |
| `PO.` inline | 101 | Handled by existing inline pattern | No change needed |
| MUTTUNGAL | 108 | Protected word works, but compound patterns garble | Verify after (HO)/(PO) fixes |
| Trailing letter split garbling | ~200+ | Active on many addresses | Reduced after fixing (HO)/(PO) spacing |

### Verified Garbling Examples (Current Code)
```
IN:  CHEMERI (HO)/ 9387908552RAMYA  MUTTUNGAL (PO)CHORODE
OUT: Chemeri (Ho)/ Ramya Muttungal (P.O. )Chorod E
     ^^^^^^^^ (HO) not expanded     ^^^^^^^^^ (PO) mangled   ^^^^^^^ trailing split

IN:  KOLAKKOTT MEETHAL (H) 13/301PO.CHORODEBEHIND RANI SCHOOL
OUT: Kolakkot T Meethal House 13/301 P.O. .Chorod Ebehind Rani School
     ^^^^^^^^^ trailing split garble         ^^^^^^^^^^^^^^^^ concatenation

IN:  AVARANGATH CHALIL(H)7/214ABEACH ROAD POAZHITHALA
OUT: Avarangat H Chalilhouse7/214 Abeach Road Poazhithal A
     ^^^^^^^^^ garbled  ^^^^^^^^^^^^^^^^ concatenated    ^^^^^^^^^^^ garbled
```

### Data Metadata
- 68 distinct area names (up from 9 in sample_cdcms_export.csv)
- 35 distinct drivers (including "Allocation Pending" placeholder)
- Order statuses: 1,885 Allocated-Printed, 465 Open, 48 Allocated-Generated

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No address cleaning | 13-step pipeline with protected words | v2.2 (Phase 11-15) | Handles most common patterns |
| No zone validation | 30km radius with fallback chain | v2.2 (Phase 13) | Prevents out-of-zone geocoding |
| No dictionary splitting | RapidFuzz-based splitter with 381 entries | v2.2 (Phase 15) | Handles concatenated place names |

**What needs updating:**
- `(HO)` and `(PO)` regex patterns -- not present in v2.2 implementation
- Zone radius 30km -> 20km per business decision
- Dictionary needs rebuild at 20km radius
- Env var configurability for depot and zone radius

## Open Questions

1. **Dictionary coverage at 20km**
   - What we know: Current 30km dictionary has 381 entries. OSM Overpass fetched ~367 nodes.
   - What's unclear: How many entries will be lost at 20km? Will coverage remain >= 80%?
   - Recommendation: Run the build script with 20km, check coverage, add manual seeds if needed for any newly uncovered CDCMS area names from Refill.xlsx

2. **Refill.xlsx has 68 area names vs sample's 9**
   - What we know: The real Refill.xlsx has 68 distinct area names, many not in the sample export
   - What's unclear: Does the dictionary cover all 68?
   - Recommendation: After dictionary rebuild, run coverage validation against Refill.xlsx area names (not just sample_cdcms_export.csv)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (Python) + Playwright (E2E) |
| Config file | pytest: `pyproject.toml` or inline; Playwright: `playwright.config.ts` |
| Quick run command | `pytest tests/core/data_import/test_cdcms_preprocessor.py -x` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ADDR-01 | MUTTUNGAL preserved as single word | unit | `pytest tests/core/data_import/test_cdcms_preprocessor.py::TestDictionarySplitting -x` | Partial -- existing tests pass but new Refill.xlsx patterns need coverage |
| ADDR-02 | (H)/(HO) expansion without garbling | unit | `pytest tests/core/data_import/test_cdcms_preprocessor.py -k "house" -x` | No -- needs new test class for (HO) pattern |
| ADDR-03 | PO splitting from concatenated text | unit | `pytest tests/core/data_import/test_cdcms_preprocessor.py -k "po" -x` | Partial -- needs (PO) pattern tests |
| ADDR-04 | 20km zone radius | unit | `pytest tests/core/geocoding/test_interfaces_method.py::TestGeocodZoneRadiusConfig -x` | Exists but asserts ==30, needs update to ==20 |
| ADDR-05 | Depot centroid from config | unit | `pytest tests/core/geocoding/test_validator.py -x` | Exists, may need env var override test |

### Sampling Rate
- **Per task commit:** `pytest tests/core/data_import/test_cdcms_preprocessor.py tests/core/geocoding/ -x`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/core/data_import/test_cdcms_preprocessor.py` -- Add (HO) expansion tests, (PO) expansion tests, Refill.xlsx pattern regression tests
- [ ] `tests/core/geocoding/test_interfaces_method.py:70` -- Update `== 30` to `== 20`
- [ ] `tests/core/geocoding/test_validator.py:83` -- Update `30_000` to `20_000`
- [ ] `tests/integration/test_address_pipeline.py` -- Update 30km references to 20km
- [ ] New E2E test file for address preprocessing with Refill.xlsx upload

## Sources

### Primary (HIGH confidence)
- `core/data_import/cdcms_preprocessor.py` -- Full source code analysis of all 13 cleaning steps
- `core/geocoding/validator.py` -- Zone validation with fallback chain
- `apps/kerala_delivery/config.py` -- Current config values
- `data/Refill.xlsx` -- Real CDCMS data analysis (2,398 orders, pattern counts)
- `scripts/build_place_dictionary.py` -- Dictionary build script with OSM Overpass
- `apps/kerala_delivery/dashboard/src/components/RouteMap.tsx` -- Existing MapLibre setup

### Secondary (MEDIUM confidence)
- [MapLibre GL JS Draw a Circle](https://maplibre.org/maplibre-gl-js/docs/examples/draw-a-circle/) -- Official example using @turf/circle
- [@turf/circle npm](https://www.npmjs.com/package/@turf/circle) -- Generates GeoJSON circle polygon

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all components already in use, only adding @turf/circle
- Architecture: HIGH -- extending existing patterns, not building new systems
- Pitfalls: HIGH -- verified all bugs by running real data through current code
- Address patterns: HIGH -- quantified from actual Refill.xlsx data analysis

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (stable domain, no external API changes expected)
