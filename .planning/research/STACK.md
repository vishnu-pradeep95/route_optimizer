# Stack Research: Address Preprocessing Pipeline

**Domain:** Dictionary-powered address splitting, geocode validation, confidence UI
**Researched:** 2026-03-10
**Confidence:** HIGH

## Recommended Stack Additions

This project already has a mature Python/FastAPI + React/TypeScript stack. The address preprocessing pipeline requires **one new runtime dependency** (RapidFuzz) and **zero new build-time dependencies**. Everything else uses stdlib, existing packages, or free external APIs called only at dictionary build time.

### New Runtime Dependency

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| RapidFuzz | 3.14.3 | Fuzzy string matching for place name dictionary lookup | C++ core with Python bindings -- 10-100x faster than pure-Python alternatives (thefuzz/fuzzywuzzy). MIT license. Supports Python 3.10-3.14. Wheel size ~1-4MB depending on platform. Used for matching CDCMS transliteration variants (e.g., "RAYANRANGOTH" against dictionary entry "RAYARANGOTH") at 85% threshold. The `fuzz.ratio()` and `process.extractOne()` functions are the primary APIs needed. |

### Existing Dependencies (No Changes Needed)

| Technology | Current Version | Purpose in New Feature | Notes |
|------------|-----------------|------------------------|-------|
| Python stdlib `math` | 3.12 | Haversine distance calculation (30km zone check) | `math.radians`, `math.sin`, `math.cos`, `math.atan2` -- ~10 lines. Accuracy within 0.5% for distances under 100km. No external library needed. |
| Python stdlib `re` | 3.12 | Improved regex for lowercase-to-uppercase word splitting | Adding `re.sub(r"([a-z])([A-Z])", ...)` alongside existing digit-to-uppercase pattern at `cdcms_preprocessor.py:269`. |
| Python stdlib `json` | 3.12 | Loading static place name dictionary from `data/place_names_vatakara.json` | One-time load on first use, cached in memory. ~200-300 entries, <50KB file. |
| `requests` | 2.32.5 | HTTP calls in dictionary build script (OSM Overpass + PostalPinCode APIs) | Already in requirements.txt. Only used in `scripts/build_place_dictionary.py` (offline, not at runtime). |
| Pydantic | 2.12.5 | `Location` model already has `geocode_confidence` field | No model changes needed. Just expose existing field in API response JSON. |
| FastAPI | 0.129.1 | Adding `geocode_confidence` and `location_approximate` to route stop response | Two new fields in existing dict comprehension in `api/main.py`. |

### External APIs (Build-Time Only, Not Runtime)

These are called only by `scripts/build_place_dictionary.py` to generate the static JSON dictionary. The dictionary is committed to the repo. Runtime never calls these APIs.

| API | Endpoint | Purpose | Auth | Rate Limit | Cost |
|-----|----------|---------|------|------------|------|
| OSM Overpass | `https://overpass-api.de/api/interpreter` | Fetch hamlet/village/neighbourhood/town nodes within 30km of depot | None | 10,000 queries/day, 1GB/day | Free (ODbL license) |
| PostalPinCode | `https://api.postalpincode.in/pincode/{pincode}` | Fetch post office names for PIN codes 673101-673110 | None | 1,000 req/hour/IP | Free |

#### Overpass Query (for reference)

```
[out:json][timeout:30];
(
  node["place"~"hamlet|village|neighbourhood|town|suburb"](around:30000,11.6244,75.5796);
);
out body;
```

This returns place name nodes with lat/lon and optional `name:ml` (Malayalam) tags. Single query, returns ~200-300 results for the Vatakara delivery zone.

#### PostalPinCode Query (for reference)

```
GET https://api.postalpincode.in/pincode/673101
GET https://api.postalpincode.in/pincode/673102
... (10 PIN codes total, ~15 requests including retries)
```

Returns JSON array with `PostOffice` objects containing `Name`, `Pincode`, `District`, `State` fields. No coordinates provided -- geocode post office names via OSM results or the existing Google geocoding cache.

### Driver PWA (No New Dependencies)

| Technology | Purpose | Notes |
|------------|---------|-------|
| Existing DaisyUI `tw:badge` | "Approx. location" warning badge on hero card | `tw:badge-warning tw:badge-sm` -- already in the design system |
| Existing vanilla JS | Conditional rendering based on `location_approximate` boolean from API | Simple `style="display: ${stop.location_approximate ? 'inline-flex' : 'none'}"` |

No new CSS, no new JS libraries, no build step changes.

### Dashboard (No Changes in This Milestone)

The React dashboard does not need changes for this feature. Confidence data flows through the API to the Driver PWA only.

## Optional Future Dependency (Approach B -- NER Model)

Only install if Approach A (dictionary + regex) fails to meet accuracy targets (>10% geocode validation failures or >5% centroid fallbacks).

| Technology | Version | Purpose | Why Optional |
|------------|---------|---------|--------------|
| transformers | >=4.40 | Hugging Face model loading and tokenization | ~200MB installed. Only needed if dictionary approach proves insufficient. |
| torch (CPU-only) | >=2.0 | PyTorch inference runtime for IndicBERT NER model | ~200MB for CPU-only wheel. Adds significant Docker image size (~400MB+). |
| shiprocket-ai/open-indicbert-indian-address-ner | latest | Indian address NER: 32.9M params, 11 entity types (building_name, city, locality, landmarks, road, state, pincode, sub_locality, floor, house_details, country), Apache 2.0 | ~396MB model download on first use. 23 labels (BIO tagging scheme). CPU inference ~50ms/address. |

**Smaller alternative considered:** `shiprocket-ai/open-tinybert-indian-address-ner` -- 66.4M params, TinyBERT-based (6 layers vs 12). F1=0.94 micro. Same entity types. ~761MB on disk (F32 tensors -- larger despite fewer layers).

**Recommendation if NER is needed:** Use the IndicBERT variant (smaller disk footprint at 396MB vs 761MB, 32.9M vs 66.4M params). Install as optional dependency group:

```toml
# In pyproject.toml (not requirements.txt)
[project.optional-dependencies]
ner = ["transformers>=4.40", "torch>=2.0"]
```

Code must gracefully handle `ImportError` when these are not installed. The NER path should only be invoked when the dictionary-based splitter finds no known place names (slow path, ~50ms) while dictionary matching handles the common case (fast path, ~1ms).

## Installation

```bash
# Single new runtime dependency
pip install rapidfuzz==3.14.3

# Add to requirements.txt (one line):
# rapidfuzz==3.14.3
```

### Docker Impact

- **Image size increase:** ~1-4MB (RapidFuzz wheel). Negligible against current image size.
- **Build time increase:** ~2-3 seconds for pip install. Negligible.
- **No new system packages** needed in Dockerfile. RapidFuzz ships pre-built wheels for `python:3.12-slim` (linux/amd64). No gcc, no C headers needed at install time.
- **No Dockerfile changes needed.** The dictionary file at `data/place_names_vatakara.json` is accessible inside the container via the existing `./data:/app/data` bind mount in `docker-compose.yml`.

## Alternatives Considered

| Recommended | Alternative | Why Not Alternative |
|-------------|-------------|---------------------|
| RapidFuzz 3.14.3 | thefuzz (formerly fuzzywuzzy) | thefuzz is pure Python, 10-100x slower. Uses python-Levenshtein C extension for speed, but RapidFuzz does the same natively with a better API. thefuzz had GPL dependency concerns historically (python-Levenshtein was GPL). RapidFuzz is the modern replacement -- same algorithms, MIT license, C++ implementation. |
| RapidFuzz 3.14.3 | jellyfish | jellyfish provides phonetic algorithms (Soundex, Metaphone) suited for English names. Kerala place names are transliterated from Malayalam -- character-level edit distance (Levenshtein via RapidFuzz) is more appropriate than phonetic matching for transliteration variants. |
| Haversine via stdlib `math` | haversine package (v2.9.0, MIT) | Adding a dependency for 10 lines of well-known math is unnecessary. The project convention is "no unnecessary dependencies" (e.g., pure Python PNG generation instead of Pillow for icons). The stdlib `math` module suffices -- accuracy within 0.5% at 30km distances. |
| Haversine via stdlib `math` | shapely/geopandas `.distance()` | Already in requirements.txt but semantically wrong for this use case. Shapely uses Cartesian distance by default, not great-circle distance. Would need CRS projection first. More complexity for less accuracy at this scale. |
| Static JSON dictionary | SQLite table or PostgreSQL table | The dictionary is ~200-300 entries (<50KB). Loading into memory on first use is instant. A database table adds schema migration complexity and a runtime DB dependency for no benefit. The JSON file is human-readable, diffable in git, and trivially editable by hand. |
| Static JSON dictionary | Redis or in-memory cache layer | Same reasoning. 50KB of data does not warrant a caching layer. Python dict lookup is O(1). The dictionary is immutable during process lifetime. |
| OSM Overpass API | Nominatim API | Nominatim is for geocoding (address-to-coordinates), not for extracting place name inventories within a radius. Overpass is purpose-built for spatial queries on OSM data. Nominatim has strict rate limits (1 req/sec) and usage policy restrictions against bulk extraction. |
| PostalPinCode API | India Post official website scraping | The API is the official machine-readable interface. Scraping would be fragile and potentially violate ToS. The API is free, stable, and returns structured JSON. |
| PostalPinCode API | data.gov.in Pincode CSV dataset | The data.gov.in dataset is a bulk CSV download (~150MB) covering all of India. We need ~10 PIN codes. API calls for 10 specific pincodes are far more targeted and lighter. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| fuzzywuzzy | Deprecated -- renamed to thefuzz. Historical GPL licensing concerns. Slower than RapidFuzz. | RapidFuzz 3.14.3 |
| haversine PyPI package | Adds a dependency for trivial, well-known math. 10 lines of stdlib `math` is simpler, has zero dependency risk, and matches the project convention. | `math.radians`, `math.sin`, `math.cos`, `math.atan2` |
| geopy.distance | Geopy is a geocoding client library. Its distance module is accurate but pulls in the entire geopy package with its own dependencies. Overkill for one distance function. | Stdlib haversine implementation |
| spaCy for NER | 200MB+ model, English-centric NER pipeline. Indian address NER requires India-specific training data. spaCy's `en_core_web` models don't recognize Indian address components (P.O., locality patterns, Kerala place names). | If NER needed: shiprocket-ai/open-indicbert-indian-address-ner (trained on Indian address data) |
| transformers + torch in Approach A | Adds ~600MB+ to Docker image. CPU inference at 50ms/address is 50x slower than dictionary lookup at ~1ms. Only justified if dictionary approach fails measurable accuracy targets. | RapidFuzz dictionary matching (Approach A). Upgrade to NER (Approach B) only if >10% validation failures measured in Phase 5 integration testing. |
| Google Places Autocomplete for splitting | Costs $2.83 per session. Would require API calls during preprocessing (currently zero API calls in the splitting stage). Doesn't handle concatenated CDCMS text well. | Static dictionary + RapidFuzz fuzzy match |
| Nominatim for place name inventory | Rate-limited to 1 req/sec, requires email identification, intended for individual geocoding not bulk extraction. ToS prohibits bulk downloads. | OSM Overpass API (purpose-built for spatial data extraction, generous limits) |
| Any geocoding API at preprocessing time | Preprocessing must be zero-API-call (constraint from design spec). Dictionary is pre-built and committed. | Static JSON dictionary loaded from filesystem |

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| rapidfuzz==3.14.3 | Python 3.10-3.14 | Project uses Python 3.12. Pre-built wheels available for `python:3.12-slim` (linux/amd64). No compilation needed at install time. |
| rapidfuzz==3.14.3 | All existing requirements.txt packages | Zero Python dependencies. No shared C extensions or conflicting transitive dependencies. |
| requests==2.32.5 (existing) | Overpass API + PostalPinCode API | Used in build script only. Already tested and stable in the project. |
| Python 3.12 stdlib `math` | Haversine implementation | `math.radians()`, `math.sin()`, `math.cos()`, `math.atan2()` -- standard since Python 2. No compatibility concerns. |

## Integration Points Summary

### Where New Code Touches Existing Code

| Integration Point | Existing File | Change Type | Risk |
|--------------------|---------------|-------------|------|
| Word splitting | `core/data_import/cdcms_preprocessor.py` line 269 | Add `([a-z])([A-Z])` regex + call to `AddressSplitter.split()` between Stage 1 cleanup and Stage 3 title case | LOW -- additive, splitter is `None`-safe (graceful degradation if dictionary file missing) |
| address_display source | `core/optimizer/vroom_adapter.py` line 278 | One-line change: use `order.address_raw` instead of `order.location.address_text or order.address_raw` | LOW -- fixes existing bug, simpler expression |
| Geocode validation | `core/geocoding/cache.py` `CachedGeocoder.geocode()` | Add validation check + fallback chain after upstream call, before cache save | MEDIUM -- touches the critical geocoding path. Must preserve existing behavior for in-zone results. |
| API response fields | `apps/kerala_delivery/api/main.py` stops dict comprehension | Add `geocode_confidence` and `location_approximate` (2 new fields) | LOW -- additive, backward compatible |
| Driver PWA UI | `apps/kerala_delivery/driver_app/index.html` | Add conditional badge rendering for hero card + compact cards | LOW -- display-only, no logic changes |

### New Files

| File | Purpose | Dependencies |
|------|---------|--------------|
| `data/place_names_vatakara.json` | Static place name dictionary (~200-300 entries) | None (static data) |
| `scripts/build_place_dictionary.py` | One-time script to build dictionary from OSM + India Post | `requests` (existing) |
| `core/data_import/address_splitter.py` | Dictionary-aware word splitter using RapidFuzz | `rapidfuzz` (NEW), `json` (stdlib) |
| `core/geocoding/validator.py` | Geocode validation against 30km delivery zone | `math` (stdlib) |
| `tests/core/data_import/test_address_splitter.py` | Splitter unit tests | `pytest` (existing) |
| `tests/core/geocoding/test_validator.py` | Validator unit tests | `pytest` (existing) |
| `core/data_import/address_ner.py` | NER model wrapper (Approach B only, created later if needed) | `transformers`, `torch` (OPTIONAL) |

### What Does NOT Change

| Component | Why Unchanged |
|-----------|---------------|
| `core/geocoding/normalize.py` | Cache key normalization is orthogonal to address splitting |
| `core/geocoding/google_adapter.py` | Pure API caller -- no validation logic belongs here |
| `core/geocoding/interfaces.py` | `GeocodingResult` model already has `confidence` field |
| `core/models/location.py` | `geocode_confidence` field already exists on `Location` |
| `core/database/models.py` | No schema migration needed -- confidence stored on existing columns |
| `core/database/repository.py` | No new DB operations needed |
| Dashboard (React/TypeScript) | Confidence UI is Driver PWA only for this milestone |
| `docker-compose.yml` | `./data:/app/data` bind mount already exists |
| `infra/Dockerfile` | RapidFuzz ships pre-built wheels -- no new system packages |
| `requirements.txt` structure | Only one line added (`rapidfuzz==3.14.3`) |

## RapidFuzz API Usage Pattern

The two primary functions needed:

```python
from rapidfuzz import fuzz, process

# 1. Direct comparison for validating a candidate match
score = fuzz.ratio("RAYARANGOTH", "RAYANRANGOTH")  # Returns ~91.3
# Use score >= 85 as threshold

# 2. Find best match from dictionary list
match = process.extractOne(
    "RAYANRANGOTH",
    ["RAYARANGOTH", "MUTTUNGAL", "BALAVADI", ...],
    scorer=fuzz.ratio,
    score_cutoff=85,
)
# Returns: ("RAYARANGOTH", 91.3, 0) or None if no match >= 85
```

**Why `fuzz.ratio` over `fuzz.partial_ratio` or `fuzz.token_sort_ratio`?**
Place names are single tokens (e.g., "RAYARANGOTH") not multi-word phrases. `fuzz.ratio` computes the Levenshtein-based similarity between two full strings, which is exactly what we need for detecting character-level transliteration differences. `partial_ratio` would allow false positives where short names match inside longer ones. `token_sort_ratio` is for reordered multi-word strings.

## Haversine Implementation Reference

No library needed. Stdlib implementation for the 30km zone check:

```python
import math

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in kilometers."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
```

Accuracy: within 0.5% for distances under 100km. For our 30km zone check, the error is ~150m at worst -- irrelevant for a 30,000m threshold.

## Sources

- [RapidFuzz PyPI](https://pypi.org/project/RapidFuzz/) -- version 3.14.3 (Nov 2025), MIT license, Python 3.10+ (HIGH confidence)
- [RapidFuzz GitHub](https://github.com/rapidfuzz/RapidFuzz) -- API overview, comparison with fuzzywuzzy (HIGH confidence)
- [RapidFuzz fuzz module docs](https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html) -- `fuzz.ratio()` usage and semantics (HIGH confidence)
- [RapidFuzz process module docs](https://rapidfuzz.github.io/RapidFuzz/Usage/process.html) -- `extractOne()` with `score_cutoff` parameter (HIGH confidence)
- [Overpass API wiki](https://wiki.openstreetmap.org/wiki/Overpass_API) -- endpoint `overpass-api.de`, 10K queries/day limit, free public service (HIGH confidence)
- [Overpass API by Example](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_API_by_Example) -- `around` filter for radius-based queries (HIGH confidence)
- [OSM radius search tutorial](https://osm-queries.ldodds.com/tutorial/12-radius-search.osm.html) -- `around:30000,lat,lon` syntax (HIGH confidence)
- [PostalPinCode API docs](https://publicapi.dev/postal-pin-code-api) -- `/pincode/{code}` endpoint, 1000 req/hr limit, JSON response (MEDIUM confidence -- official site at postalpincode.in was unresponsive, verified via third-party documentation)
- [haversine package source](https://github.com/mapado/haversine/blob/main/haversine/haversine.py) -- reference implementation confirming stdlib `math` sufficiency (HIGH confidence)
- [shiprocket-ai/open-indicbert-indian-address-ner](https://huggingface.co/shiprocket-ai/open-indicbert-indian-address-ner) -- 32.9M params, 11 entity types, Apache 2.0 (HIGH confidence)
- [shiprocket-ai/open-tinybert-indian-address-ner](https://huggingface.co/shiprocket-ai/open-tinybert-indian-address-ner) -- 66.4M params, F1=0.94, Apache 2.0 (HIGH confidence)
- Project `requirements.txt` -- verified `requests==2.32.5` exists, confirmed no conflicting packages (HIGH confidence)
- Project `infra/Dockerfile` -- verified `python:3.12-slim`, multi-stage build, no `COPY data/` (HIGH confidence)
- Project `docker-compose.yml` -- verified `./data:/app/data` bind mount on API service (HIGH confidence)
- Project `core/models/location.py` -- confirmed `geocode_confidence: float | None` field exists (HIGH confidence)
- Project `core/geocoding/interfaces.py` -- confirmed `GeocodingResult.confidence` field exists (HIGH confidence)
- Project `core/geocoding/cache.py` -- verified integration point in `CachedGeocoder.geocode()` (HIGH confidence)
- Project design spec `docs/superpowers/specs/2026-03-10-address-preprocessing-design.md` -- feature requirements and architecture (HIGH confidence)

---
*Stack research for: Kerala LPG Delivery Route Optimizer v2.2 -- Address Preprocessing Pipeline*
*Researched: 2026-03-10*
