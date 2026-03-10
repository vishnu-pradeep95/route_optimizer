# Address Preprocessing Pipeline — Design Document

**Date:** 2026-03-10
**Status:** Draft
**Branch:** `fix/unexpected-route-locations`

## Problem Statement

When uploading CDCMS CSV files, some delivery stops get routed to completely wrong
locations (e.g., "HDFC ERGO Insurance Agent, Palayam, Kozhikode" — 40km from the
delivery zone). The wrong address appears in Google Maps navigation links but NOT in
the delivery stops list, confusing drivers.

### Root Cause (Two Interacting Issues)

**Issue 1 — Insufficient word splitting in `clean_cdcms_address()`:**
The regex at `cdcms_preprocessor.py:269` only splits `digit→uppercase` transitions
(`8/542SREESHYLAM` → `8/542 SREESHYLAM`). CDCMS also concatenates `letter→letter`
words with no separator:

| Raw CDCMS text | Current output | Expected output |
|----------------|---------------|-----------------|
| `ANANDAMANDIRAMK.T.BAZAR` | `Anandamandiramk.T.Bazar` | `Anandamandiram, K.T. Bazar` |
| `MUTTUNGAL-POBALAVADI` | `Muttungal-Pobalavadi` | `Muttungal P.O., Balavadi` |
| `KUNIYILNR.EK GOPALAN MASTER` | `Kuniyilnr.Ek Gopalan Master` | `Kuniyil, Near Ek Gopalan Master` |
| `CHEKKIPURATHPO.` | `Chekkipurathp.O.` | `Chekkipurath P.O.` |

These garbled strings produce wrong geocoding results from Google Maps API.

**Issue 2 — `formatted_address` overwrites display text on cache MISS:**
- Cache MISS: `address_text` = Google's `formatted_address` (could be "HDFC ERGO...")
- Cache HIT: `address_text` = original cleaned address (from `repository.py:766`)
- `vroom_adapter.py:278`: `address_display = order.location.address_text or order.address_raw`

On first upload (cache miss), wrong Google `formatted_address` shows in navigation.
On re-upload (cache hit), original address shows in stops list but coordinates still wrong.

### Constraints

- **Fixed depot:** Vatakara (11.6244, 75.5796)
- **Delivery zone:** 30km radius around depot (~100-200 unique place names)
- **Scale:** 40-50 deliveries/day
- **No new heavy dependencies** (no ML models, no PyTorch)
- **Runtime:** No mandatory API calls during address preprocessing
- **Self-improving:** Leverage existing `save_driver_verified()` geocode cache

---

## Solution Overview

Two-tier approach: **Approach A** (dictionary-powered regex) implemented first,
with **Approach B** (NER model fallback) designed as an upgrade path if A proves
insufficient during testing.

### Architecture Diagram

```
CDCMS CSV Upload
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Stage 1: CDCMS-Specific Cleaning (existing)        │
│  - Remove phone numbers, artifacts, backticks       │
│  - Expand abbreviations (NR→Near, PO→P.O., (H)→H.) │
│  - Remove dangling punctuation                      │
│                                                     │
│  Stage 2: Dictionary-Powered Word Splitting (NEW)   │
│  - Load place name dictionary (static JSON)         │
│  - Scan for known place names in concatenated text   │
│  - Split at place name boundaries                   │
│  - Fuzzy match for transliteration variants         │
│                                                     │
│  Stage 3: Title Case + Suffix (existing)            │
│  - Title case, fix artifacts, append area suffix    │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
              Google Geocoding API
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  Stage 4: Geocode Validation (NEW)                  │
│  - Is result within 30km of depot?                  │
│  - YES → accept, record confidence                  │
│  - NO  → retry with area name only                  │
│         → still NO → use area centroid fallback     │
│         → tag as "approximate"                      │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  Stage 5: Confidence in API + Driver UI (NEW)       │
│  - geocode_confidence piped through API response    │
│  - Driver app shows visual badge for approximate    │
│    locations (orange dot, "Approx. location" text)  │
└─────────────────────────────────────────────────────┘
```

---

## Approach A: Dictionary-Powered Regex (Primary)

### A1. Place Name Dictionary

**File:** `data/place_names_vatakara.json`

Static JSON file committed to the repo. Built once from two free sources:

#### Data Sources

| Source | What it gives | How to fetch | Count |
|--------|--------------|--------------|-------|
| [OSM Overpass API](https://overpass-api.de/) | Hamlets, villages, neighbourhoods, towns within 30km of depot, with lat/lon and Malayalam names | Single HTTP query, free, no auth | ~200-300 |
| [PostalPinCode API](https://api.postalpincode.in/) | Post office names in Vadakara postal division by PIN code (673101-673110) | ~15 HTTP requests, free, no auth | ~77 |

Both APIs are **free, read-only, no authentication required, no personal data sent**.
Data is government/community sourced (India Post / OpenStreetMap ODbL).

#### Dictionary Schema

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
      "name_ml": "വള്ളിക്കാട്",
      "aliases": ["VALLIKADU", "VALLIKKAD"],
      "type": "hamlet",
      "latitude": 11.6312,
      "longitude": 75.5845,
      "source": "osm"
    },
    {
      "name": "RAYARANGOTH",
      "name_ml": "രായരങ്ങോത്ത്",
      "aliases": ["RAYANRANGOTH", "RAYARANGOTHU"],
      "type": "village",
      "latitude": 11.6189,
      "longitude": 75.5923,
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

#### Build Script

**File:** `scripts/build_place_dictionary.py`

One-time script (also runnable periodically to refresh):

```
python scripts/build_place_dictionary.py \
  --depot-lat 11.6244 --depot-lon 75.5796 \
  --radius-km 30 \
  --output data/place_names_vatakara.json
```

1. Queries OSM Overpass API for place nodes within 30km of depot
2. Queries PostalPinCode API for PIN codes 673101-673110
3. Deduplicates by name (fuzzy match, threshold 85%)
4. Writes merged JSON to `data/`

The output JSON is **committed to the repo** — no API calls needed at runtime.

---

### A2. Dictionary-Aware Word Splitter

**File:** `core/data_import/address_splitter.py` (new module)

The core algorithm for splitting concatenated CDCMS text using known place names.

#### Algorithm

```
Input:  "MUTTUNGAL-POBALAVADI"
Dictionary: ["MUTTUNGAL", "BALAVADI", "VALLIKKADU", ...]

Step 1: Uppercase the input for matching
        → "MUTTUNGAL-POBALAVADI"

Step 2: Try to find known place names (longest match first)
        → Match "MUTTUNGAL" at position 0-8

Step 3: Examine the remainder after the match
        → "-POBALAVADI"
        → Detect "PO" prefix → separate as "P.O."
        → Remainder: "BALAVADI"
        → Match "BALAVADI" in dictionary

Step 4: Reconstruct
        → "MUTTUNGAL P.O. BALAVADI"

Output: "MUTTUNGAL P.O. BALAVADI"
```

#### Key Design Decisions

1. **Longest match first** — Prevents "MUTTUNGAL" from matching as "MUTTU" + "NGAL"
   (if both existed in the dictionary). Sort dictionary entries by length descending.

2. **Fuzzy matching with RapidFuzz** — `rapidfuzz.fuzz.ratio()` with threshold 85%.
   Handles transliteration variants: `RAYARANGOTH` matches `RAYANRANGOTH`.
   RapidFuzz is a lightweight C++ library (MIT license, ~200KB wheel), already
   common in Python data projects. No heavy ML dependency.

3. **PO/NR detection between place names** — After splitting at a place name
   boundary, check if the gap contains `PO`, `NR`, or similar abbreviation.
   Expand inline: `MUTTUNGAL-POBALAVADI` → `MUTTUNGAL P.O. BALAVADI`.

4. **Passthrough for unknown text** — If no dictionary match found, leave the
   text unchanged. The geocoder may still handle it. The validation layer
   (Stage 4) catches bad results.

#### Interface

```python
class AddressSplitter:
    """Split concatenated CDCMS address text using a place name dictionary."""

    def __init__(self, dictionary_path: str | Path):
        """Load place name dictionary from JSON file."""

    def split(self, text: str) -> str:
        """Split concatenated words at known place name boundaries.

        Returns the text with spaces inserted at detected boundaries.
        Unknown text passes through unchanged.
        """

    def find_place(self, text: str) -> PlaceMatch | None:
        """Find the best matching place name in the given text.

        Returns PlaceMatch with name, position, confidence, or None.
        """
```

#### Integration Point

Called from `clean_cdcms_address()` between Stage 1 (cleanup) and Stage 3 (title case):

```python
# In cdcms_preprocessor.py

# After existing cleanup steps (phone removal, artifact cleanup, abbreviations)...
# NEW: Dictionary-powered word splitting
if _splitter is not None:
    addr = _splitter.split(addr)
# Then continue with existing title case, suffix, etc.
```

The splitter is initialized lazily (on first use) from the static JSON dictionary.
If the dictionary file is missing, the splitter is `None` and we fall back to the
current regex-only behavior — graceful degradation.

---

### A3. Improved Regex (Regardless of Dictionary)

Even without the dictionary, the current regex can be improved. These changes are
safe, independent, and should be done first:

**File:** `core/data_import/cdcms_preprocessor.py` — `clean_cdcms_address()`

| Current (line 269) | Improved | What it fixes |
|---|---|---|
| `re.sub(r"(\d)([A-Z])", r"\1 \2", addr)` | Also add: `re.sub(r"([a-z])([A-Z])", r"\1 \2", addr)` | Splits `lowercase→uppercase`: `ANANDAMANDIRAMK` → (after .title()) `Anandamandiram K` |
| Only handles `PO.` at end of word | Also handle `PO` mid-word preceded by place name | `CHORODE EASTNR.` → `CHORODE EAST Near` |
| Abbreviation expansion after concat | Move abbreviation expansion after word splitting | Ensures `NR`, `PO` patterns are detected after words are separated |

**Why do this even with a dictionary?** The dictionary handles known places, but
new addresses may reference places not yet in the dictionary. The improved regex
provides a baseline level of splitting that works for any text.

---

### A4. Geocode Validation

**File:** `core/geocoding/validator.py` (new module)

Validates geocoding results against the delivery zone boundary.

#### Interface

```python
@dataclass
class ValidationResult:
    is_valid: bool
    distance_from_depot_km: float
    confidence_adjustment: float  # Multiplier: 1.0 = no change, 0.5 = halved
    reason: str  # "within_zone", "outside_zone", "area_fallback", "centroid_fallback"

class GeocodeValidator:
    """Validate geocoding results against delivery zone constraints."""

    def __init__(
        self,
        depot: Location,
        max_radius_km: float = 30.0,
        dictionary_path: str | Path | None = None,
    ):
        """Initialize with depot location and delivery zone radius."""

    def validate(self, location: Location, area_name: str = "") -> ValidationResult:
        """Check if a geocoded location falls within the delivery zone.

        Args:
            location: The geocoded coordinates to validate.
            area_name: CDCMS AreaName for fallback centroid lookup.

        Returns:
            ValidationResult with validity flag and confidence adjustment.
        """

    def get_area_centroid(self, area_name: str) -> Location | None:
        """Look up the centroid coordinates for a CDCMS area name.

        Uses the place name dictionary with fuzzy matching.
        Returns None if no match found.
        """
```

#### Haversine Distance

The 30km radius check uses the haversine formula (already well-known, ~10 lines of
Python). No external dependency needed. Accuracy is within ~0.5% for distances
under 100km — more than sufficient for a 30km zone check.

#### Integration Point

Called in `CachedGeocoder.geocode()` after getting a result from the upstream
provider, before returning:

```python
# In cache.py — CachedGeocoder.geocode()

result = self._upstream.geocode(address)

# NEW: Validate result is within delivery zone
if result.success and result.location and self._validator:
    validation = self._validator.validate(result.location, area_name=area_name)
    if not validation.is_valid:
        # Retry with area name only
        retry_result = self._upstream.geocode(f"{area_name}, {self._area_suffix}")
        if retry_result.success and retry_result.location:
            retry_validation = self._validator.validate(retry_result.location)
            if retry_validation.is_valid:
                result = retry_result
                result.confidence *= 0.7  # Lower confidence for area-only geocode
            else:
                # Fall back to area centroid from dictionary
                centroid = self._validator.get_area_centroid(area_name)
                if centroid:
                    result = GeocodingResult(
                        location=centroid,
                        confidence=0.3,  # Low confidence — approximate
                        formatted_address=f"{area_name} (approximate)",
                    )
```

#### Fallback Chain

```
Geocode result within 30km?
  ├── YES → use as-is (confidence from Google: 0.40-0.95)
  └── NO
      ├── Retry: geocode "{AreaName}, Vatakara, Kozhikode, Kerala"
      │   ├── Within 30km? → use it (confidence × 0.7)
      │   └── Still outside?
      │       ├── Dictionary has area centroid? → use centroid (confidence = 0.3)
      │       └── No centroid? → use original result, flag as unvalidated
      └── (original result preserved as raw_response for debugging)
```

---

### A5. Confidence in API Response + Driver UI

#### API Changes

**File:** `apps/kerala_delivery/api/main.py` — route retrieval endpoint

Add `geocode_confidence` and `location_approximate` to the stop JSON:

```python
# In the stops list comprehension (line 1468-1483)
{
    "sequence": stop.sequence,
    "order_id": stop.order_id,
    "address": stop.address_display,
    "latitude": stop.location.latitude,
    "longitude": stop.location.longitude,
    "geocode_confidence": stop.location.geocode_confidence,  # NEW
    "location_approximate": (                                 # NEW
        stop.location.geocode_confidence is not None
        and stop.location.geocode_confidence < 0.5
    ),
    # ... existing fields ...
}
```

#### Model Changes

No model changes needed — `Location.geocode_confidence` already exists and flows
through `RouteStop.location`. We just need to expose it in the API response.

#### Database Changes

`RouteStopDB` already has `location` (PostGIS POINT). The `geocode_confidence`
lives on `OrderDB` and is accessible through the `Location` Pydantic model.
No schema migration needed.

#### Driver App UI Changes

**File:** `apps/kerala_delivery/driver_app/index.html`

Add a visual indicator when `location_approximate` is true:

**Hero card (next stop):**
```html
<!-- After the address display -->
<div class="tw:badge tw:badge-warning tw:badge-sm tw:gap-1"
     style="display: ${stop.location_approximate ? 'inline-flex' : 'none'}">
  <span>~</span> Approx. location
</div>
```

**Compact card (remaining stops):**
```html
<!-- Small orange dot indicator next to address -->
<span class="tw:text-warning" title="Approximate location"
      style="display: ${stop.location_approximate ? 'inline' : 'none'}">
  &#9679;
</span>
```

**Behavior when tapped:**
- "Approx. location" badge is informational only — driver still gets Navigate button
- Navigate opens Google Maps at the approximate coordinates (area center)
- Driver knows to call customer for exact directions
- When driver marks "Done" and confirms GPS, `save_driver_verified()` caches the
  correct location for next time

---

### A6. `address_display` Source Fix

**File:** `core/optimizer/vroom_adapter.py` — line 278

Fix the root cause of display inconsistency between cache hits and misses:

```python
# BEFORE (uses Google's formatted_address, which can be wrong):
address_display=order.location.address_text or order.address_raw,

# AFTER (always prefer the cleaned original address):
address_display=order.address_raw,
```

**Why?** `order.address_raw` is the cleaned CDCMS address that the user recognizes.
`order.location.address_text` is Google's `formatted_address` which may be a
completely different place. The driver should always see the address from the CSV,
not Google's interpretation.

This is a one-line fix that eliminates the display inconsistency regardless of
cache state.

---

## Approach B: NER Model Fallback (Upgrade Path)

If Approach A's dictionary + regex proves insufficient during testing (e.g., too
many addresses still geocode incorrectly), Approach B adds an NER model layer.

### When to Upgrade to Approach B

Trigger criteria (measure during testing):
- More than 10% of addresses fail geocode validation (outside 30km)
- More than 5% of addresses need area centroid fallback (confidence 0.3)
- Drivers frequently report wrong locations despite improved preprocessing

### B1. Model Selection

**Recommended:** [shiprocket-ai/open-indicbert-indian-address-ner](https://huggingface.co/shiprocket-ai/open-indicbert-indian-address-ner)

| Aspect | Detail |
|--------|--------|
| Size | 32.9M params, ~396MB on disk |
| Base model | IndicBERT (Indic language aware) |
| Entity types | building_name, city, locality, landmarks, road, state, pincode, etc. |
| F1 score | 0.94 micro (on Shiprocket's test set) |
| License | Apache 2.0 |
| Runtime | CPU inference ~50ms/address (no GPU needed) |
| Dependencies | `transformers`, `torch` (CPU-only: ~200MB) |

### B2. Integration Architecture

```
                    ┌─────────────────────┐
                    │  clean_cdcms_address │
                    │  (Stage 1: cleanup)  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  AddressSplitter    │
                    │  (Stage 2: dict)    │
                    └──────────┬──────────┘
                               │
                   ┌───────────▼───────────┐
                   │ Confidence check:     │
                   │ Did splitter find     │
                   │ known place names?    │
                   └───┬───────────────┬───┘
                       │               │
                   YES │           NO  │
                       │               │
                       ▼               ▼
              ┌────────────┐  ┌────────────────┐
              │ Continue   │  │ NER Model      │
              │ (fast path)│  │ (slow path)    │
              │            │  │ Extract:       │
              │            │  │ - building     │
              │            │  │ - locality     │
              │            │  │ - city         │
              │            │  │ - landmarks    │
              └─────┬──────┘  └───────┬────────┘
                    │                 │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Stage 3: Title  │
                    │ case + suffix   │
                    └─────────────────┘
```

**Key principle:** NER is the **slow path** — only invoked when the dictionary-based
splitter doesn't find any known place names. This keeps the common case fast
(dictionary match = ~1ms) and reserves the expensive path (~50ms) for genuinely
unknown addresses.

### B3. NER Module

**File:** `core/data_import/address_ner.py` (new module, only created if upgrading)

```python
class AddressNER:
    """Indian address NER using Shiprocket's IndicBERT model.

    Lazy-loaded: model is only downloaded/loaded on first use.
    Falls back gracefully if transformers/torch not installed.
    """

    def __init__(self, model_name: str = "shiprocket-ai/open-indicbert-indian-address-ner"):
        """Initialize (does NOT load model yet — lazy loading on first call)."""

    def extract(self, address: str) -> dict[str, str]:
        """Extract structured components from an address string.

        Returns dict with keys: building_name, locality, city,
        landmarks, road, state, pincode (all optional).
        """

    def reconstruct(self, components: dict[str, str]) -> str:
        """Reconstruct a clean address string from extracted components.

        Joins components with commas in a geocoder-friendly order.
        """
```

### B4. Dependency Management

Approach B dependencies are **optional** — the system works without them:

```toml
# In pyproject.toml
[project.optional-dependencies]
ner = [
    "transformers>=4.40",
    "torch>=2.0",  # CPU-only
]
```

Install only when upgrading: `pip install -e ".[ner]"`

Code checks for availability:

```python
try:
    from core.data_import.address_ner import AddressNER
    _ner_available = True
except ImportError:
    _ner_available = False
```

---

## Implementation Plan

### Phase 1: Foundation (Approach A — Core Fixes)

| # | Task | File(s) | Depends on |
|---|------|---------|------------|
| 1.1 | Fix `address_display` source — always use `address_raw` | `vroom_adapter.py:278` | — |
| 1.2 | Add `lowercase→uppercase` word split regex | `cdcms_preprocessor.py:269` | — |
| 1.3 | Reorder cleaning steps: split words BEFORE expanding abbreviations | `cdcms_preprocessor.py` | 1.2 |
| 1.4 | Add tests for new regex patterns with real CDCMS samples | `test_cdcms_preprocessor.py` | 1.2, 1.3 |
| 1.5 | Update existing tests that may break from reordering | `test_cdcms_preprocessor.py` | 1.3 |

**Estimated complexity:** Small. ~20 lines changed, ~30 lines of new tests.

### Phase 2: Place Name Dictionary

| # | Task | File(s) | Depends on |
|---|------|---------|------------|
| 2.1 | Write dictionary build script (OSM + India Post) | `scripts/build_place_dictionary.py` | — |
| 2.2 | Run script, generate initial dictionary | `data/place_names_vatakara.json` | 2.1 |
| 2.3 | Build `AddressSplitter` class with dictionary loading | `core/data_import/address_splitter.py` | 2.2 |
| 2.4 | Add fuzzy matching with RapidFuzz | `address_splitter.py` | 2.3 |
| 2.5 | Integrate splitter into `clean_cdcms_address()` | `cdcms_preprocessor.py` | 2.3 |
| 2.6 | Tests for splitter (unit + integration with real addresses) | `tests/core/data_import/test_address_splitter.py` | 2.3, 2.5 |

**Estimated complexity:** Medium. ~150 lines new code, ~100 lines tests.
**New dependency:** `rapidfuzz` (lightweight, MIT, pure Python fallback available).

### Phase 3: Geocode Validation

| # | Task | File(s) | Depends on |
|---|------|---------|------------|
| 3.1 | Implement haversine distance utility | `core/geocoding/validator.py` | — |
| 3.2 | Build `GeocodeValidator` with zone check | `core/geocoding/validator.py` | 3.1, 2.2 |
| 3.3 | Add area centroid lookup from dictionary | `validator.py` | 3.2 |
| 3.4 | Integrate validator into `CachedGeocoder.geocode()` | `core/geocoding/cache.py` | 3.2 |
| 3.5 | Add retry-with-area-name fallback logic | `cache.py` | 3.4 |
| 3.6 | Tests for validator (in-zone, out-of-zone, fallback chain) | `tests/core/geocoding/test_validator.py` | 3.2, 3.3 |

**Estimated complexity:** Medium. ~120 lines new code, ~80 lines tests.

### Phase 4: API + Driver UI

| # | Task | File(s) | Depends on |
|---|------|---------|------------|
| 4.1 | Add `geocode_confidence` and `location_approximate` to API response | `api/main.py` | — |
| 4.2 | Add "Approx. location" badge to hero card | `driver_app/index.html` | 4.1 |
| 4.3 | Add orange dot indicator to compact cards | `driver_app/index.html` | 4.1 |
| 4.4 | E2E test: upload CSV → verify badge appears for low-confidence stops | Playwright MCP | 4.2, 4.3 |

**Estimated complexity:** Small. ~20 lines API, ~15 lines HTML/CSS.

### Phase 5: Integration Testing

| # | Task | Depends on |
|---|------|------------|
| 5.1 | Test full pipeline with `sample_cdcms_export.csv` | Phase 1-4 |
| 5.2 | Verify "HDFC ERGO" bug is fixed (original addresses geocode within zone) | 5.1 |
| 5.3 | Measure geocode accuracy: % of addresses within 30km, % needing fallback | 5.1 |
| 5.4 | Document accuracy metrics — triggers for Approach B upgrade | 5.3 |

### Phase 6: Approach B (If Needed)

| # | Task | File(s) | Trigger |
|---|------|---------|---------|
| 6.1 | Add `ner` optional dependency group | `pyproject.toml` | >10% validation failures |
| 6.2 | Build `AddressNER` class with lazy model loading | `core/data_import/address_ner.py` | 6.1 |
| 6.3 | Integrate NER into splitter as slow-path fallback | `address_splitter.py` | 6.2 |
| 6.4 | Test NER with real CDCMS addresses, measure improvement | Tests | 6.3 |

---

## File Inventory

### New Files

| File | Purpose | Phase |
|------|---------|-------|
| `data/place_names_vatakara.json` | Static place name dictionary (~200 entries) | 2 |
| `scripts/build_place_dictionary.py` | One-time script to build dictionary from OSM + India Post | 2 |
| `core/data_import/address_splitter.py` | Dictionary-aware word splitter | 2 |
| `core/geocoding/validator.py` | Geocode validation against delivery zone | 3 |
| `tests/core/data_import/test_address_splitter.py` | Splitter tests | 2 |
| `tests/core/geocoding/test_validator.py` | Validator tests | 3 |
| `core/data_import/address_ner.py` | NER model wrapper (Approach B only) | 6 |

### Modified Files

| File | Change | Phase |
|------|--------|-------|
| `core/data_import/cdcms_preprocessor.py` | Add lowercase→uppercase regex, integrate splitter | 1, 2 |
| `core/optimizer/vroom_adapter.py` | Fix `address_display` source (line 278) | 1 |
| `core/geocoding/cache.py` | Integrate validator, add fallback chain | 3 |
| `apps/kerala_delivery/api/main.py` | Add confidence fields to API response | 4 |
| `apps/kerala_delivery/driver_app/index.html` | Add approx. location badge | 4 |
| `tests/core/data_import/test_cdcms_preprocessor.py` | New tests for improved regex | 1 |

### Unchanged Files

| File | Why unchanged |
|------|---------------|
| `core/geocoding/normalize.py` | Cache key normalization — orthogonal to this fix |
| `core/geocoding/google_adapter.py` | Pure API caller — no changes needed |
| `core/geocoding/interfaces.py` | Protocol unchanged |
| `core/models/location.py` | Already has `geocode_confidence` |
| `core/models/route.py` | Already has `location` with confidence |
| `core/database/models.py` | No schema migration needed |
| `core/database/repository.py` | No changes needed |

---

## Testing Strategy

### Unit Tests

| Test | What it verifies |
|------|------------------|
| `test_splits_lowercase_uppercase_transition` | `ANANDAMANDIRAMK` → `ANANDAMANDIRAM K` |
| `test_splits_known_place_names` | `MUTTUNGALPOBALAVADI` → `MUTTUNGAL P.O. BALAVADI` |
| `test_fuzzy_matches_transliteration_variant` | `RAYANRANGOTH` matches `RAYARANGOTH` |
| `test_passthrough_unknown_text` | Unknown words left unchanged |
| `test_haversine_within_zone` | Point 10km from depot → valid |
| `test_haversine_outside_zone` | Point 50km from depot → invalid |
| `test_fallback_to_area_centroid` | Out-of-zone + area match → centroid coords |
| `test_address_display_uses_raw` | `address_display` = `address_raw`, not Google's `formatted_address` |

### Integration Tests

| Test | What it verifies |
|------|------------------|
| Full pipeline with `sample_cdcms_export.csv` | All 27 addresses clean correctly |
| Geocode validation with known-bad address | "HDFC ERGO" result rejected, fallback used |
| API response includes confidence fields | `geocode_confidence` and `location_approximate` present |
| Driver app shows badge for low confidence | Playwright MCP visual check |

### Accuracy Metrics (Phase 5)

After implementing, measure on the 27 sample addresses:
- **Geocode success rate:** % that geocode within 30km (target: >90%)
- **Fallback rate:** % that need area centroid (target: <10%)
- **Dictionary coverage:** % of area names in addresses found in dictionary (target: >95%)

---

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Dictionary misses a new area name | Medium | Graceful fallback to regex-only. Driver-verified cache self-heals over time. Periodic dictionary refresh. |
| Fuzzy matching produces false positive | Low | Threshold 85% is conservative. Place names are distinctive enough in a 30km zone. |
| OSM/India Post API down during dictionary build | Low | APIs are stable public services. Dictionary is built once and committed — runtime never calls them. |
| Google geocodes area-only retry to wrong place | Low | Second validation check catches this. Centroid fallback is the safety net. |
| `rapidfuzz` dependency conflict | Very low | Pure Python fallback (`thefuzz`) available. Can also vendor a simple Levenshtein. |

---

## Success Criteria

1. The "HDFC ERGO" bug is fixed — no addresses geocode outside the 30km zone without
   being flagged
2. Driver sees "Approx. location" badge when geocode confidence is low
3. All 27 sample addresses produce geocode results within the delivery zone
4. No new heavy dependencies (no PyTorch, no ML models) — only `rapidfuzz` (~200KB)
5. Existing tests continue to pass
6. Clear upgrade path to Approach B documented and triggered by measurable metrics
