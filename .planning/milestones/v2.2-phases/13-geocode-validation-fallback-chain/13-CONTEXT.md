# Phase 13: Geocode Validation and Fallback Chain - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Validate every geocoded delivery address against a 30km radius from the Vatakara depot. Out-of-zone results trigger an automatic area-name retry using the CDCMS area field, then fall back to dictionary centroid coordinates, then depot coordinates as the ultimate fallback. A circuit breaker stops Google API retries after 3 consecutive REQUEST_DENIED responses. Each order receives a validated confidence score and geocode method stored on the orders table for downstream API consumption (Phase 14). Requirements: GVAL-01, GVAL-02, GVAL-03, GVAL-04.

</domain>

<decisions>
## Implementation Decisions

### Circuit breaker behavior
- 3 consecutive Google API REQUEST_DENIED responses trip the circuit breaker
- After tripping: all remaining ungeocoded addresses in the batch get centroid fallback (confidence 0.3) or depot fallback (confidence 0.1) -- no silent drops
- Upload succeeds with a yellow batch-level warning: "Google Maps API key issue -- X stops have approximate locations. Ask IT to check the API key."
- Warning does NOT block the workflow -- routes are still generated with approximate locations
- Circuit breaker resets per upload (stateless) -- each CSV upload starts fresh, so a fixed API key works immediately on next upload

### Area-name retry strategy
- When a geocoded address lands >30km from Vatakara depot, retry with CDCMS area field: "{area}, Vatakara, Kozhikode, Kerala"
- CDCMS area field is the primary source (direct, always available from the CSV data)
- If area-name retry also geocodes outside 30km, fall back to dictionary centroid for that area name

### Fallback chain (ordered)
1. **Direct geocode** (confidence 1.0, method 'direct') -- Google result within 30km zone
2. **Area-name retry** (confidence 0.7, method 'area_retry') -- CDCMS area field sent to Google, result within 30km
3. **Dictionary centroid** (confidence 0.3, method 'centroid') -- centroid coordinates from place_names_vatakara.json
4. **Depot fallback** (confidence 0.1, method 'depot') -- Vatakara depot (11.6244, 75.5796) as last resort
- Every stop appears on the map at some location -- matches core value "no silent drops, no missing stops"

### Confidence storage
- New `geocode_confidence` column on orders table (float, nullable) -- set at upload time
- New `geocode_method` column on orders table (string/enum, nullable) -- tracks which fallback level was used: 'direct', 'area_retry', 'centroid', 'depot'
- Existing orders (pre-Phase 13) have NULL for both columns -- Phase 14 treats NULL as "pre-validation data" with no badge/warning shown
- geocode_cache retains its own raw confidence column separately (used for duplicate detection thresholds)

### Cache behavior
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

</decisions>

<specifics>
## Specific Ideas

- STATE.md flags "Google Maps API key is currently invalid (REQUEST_DENIED)" -- circuit breaker design must handle this from the very first upload
- The "Problem -- fix action" error pattern from v1.3 should be used for the batch-level warning message
- install.sh color helpers (info/success/warn/error) pattern for console output consistency

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `haversine_meters(lat1, lon1, lat2, lon2)` in `core/geocoding/duplicate_detector.py`: Returns distance in meters, reusable for zone validation (multiply threshold by 1000 for km)
- `CachedGeocoder` in `core/geocoding/cache.py`: Decorator pattern around GoogleGeocoder, supports optional parameters -- success criteria says "accepts validator as optional parameter"
- Place name dictionary at `data/place_names_vatakara.json`: 381 entries with lat/lon centroids, indexed by name -- ready for centroid lookups
- `AddressSplitter` in `core/data_import/address_splitter.py`: Fuzzy matching against dictionary names -- could be used for centroid lookup when CDCMS area field fails
- `DEPOT_LOCATION` in `apps/kerala_delivery/config.py`: (11.6244, 75.5796) -- depot coordinates for ultimate fallback
- `CDCMS_AREA_SUFFIX` in config.py: ", Vatakara, Kozhikode, Kerala" -- suffix for area-name retry queries
- Google confidence mapping in `google_adapter.py`: ROOFTOP->0.95, RANGE_INTERPOLATED->0.80, GEOMETRIC_CENTER->0.60, APPROXIMATE->0.40

### Established Patterns
- `set -euo pipefail` in shell scripts
- Alembic migrations for schema changes (`alembic/versions/`)
- CachedGeocoder stats tracking (hits/misses/errors) -- extend for validation stats
- `_confidence_tier()` in duplicate_detector.py maps float confidence to tier names
- ErrorResponse model with ErrorCodes for structured API errors (v2.0)
- Existing geocode_cache table has confidence column (raw Google confidence)

### Integration Points
- Upload pipeline in `main.py` lines 1015-1070: geocoding loop where validation would hook in
- `CachedGeocoder.geocode()` return value: `GeocodingResult` -- needs to carry confidence/method
- `repository.save_geocode_cache()`: called after successful geocoding
- `Order` model in `core/models/order.py`: needs new geocode_confidence and geocode_method fields
- `OrderDB` model in `core/database/models.py`: needs new columns for Alembic migration
- CDCMS preprocessor provides area field via `preprocess_cdcms()` -- available in the order data

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 13-geocode-validation-fallback-chain*
*Context gathered: 2026-03-11*
