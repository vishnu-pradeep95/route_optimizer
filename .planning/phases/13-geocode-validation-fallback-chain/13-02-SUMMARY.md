---
phase: 13-geocode-validation-fallback-chain
plan: 02
subsystem: geocoding
tags: [geocoding-result, cached-geocoder, validator-integration, alembic, backward-compat]

# Dependency graph
requires:
  - phase: 13-geocode-validation-fallback-chain
    provides: "GeocodeValidator class with zone check, fallback chain, circuit breaker (Plan 01)"
  - phase: 12-place-name-dictionary
    provides: "place_names_vatakara.json with 381 entries (centroids for fallback lookup)"
provides:
  - "GeocodingResult.method field (default 'direct') for tracking geocode fallback level"
  - "OrderDB.geocode_method column (String(20), nullable) for database persistence"
  - "CachedGeocoder with optional validator parameter (backward compatible)"
  - "CachedGeocoder.geocode() area_name parameter for fallback chain"
  - "GEOCODE_ZONE_RADIUS_KM = 30 config constant"
  - "Alembic migration 54c27825e8df for geocode_method column"
affects: [13-03 pipeline wiring, 14 approx-location badge]

# Tech tracking
tech-stack:
  added: []
  patterns: [optional-validator-injection, validation-after-cache-and-api, circuit-breaker-tracking-in-cache]

key-files:
  created:
    - tests/core/geocoding/test_interfaces_method.py
    - infra/alembic/versions/54c27825e8df_add_geocode_method_column_to_orders.py
  modified:
    - core/geocoding/interfaces.py
    - core/geocoding/cache.py
    - core/database/models.py
    - apps/kerala_delivery/config.py
    - tests/core/geocoding/test_cache.py

key-decisions:
  - "GeocodingResult.method is a plain string, not an enum -- avoids import coupling between interfaces and validator modules"
  - "Validation runs on every geocode result (cache hit AND API call) -- user locked decision: always re-validate"
  - "REQUEST_DENIED tracking happens only for upstream API calls (not cache hits) -- cache hits have no API response to track"
  - "Validation stats added to existing CachedGeocoder.stats dict -- consistent with existing hits/misses/errors pattern"

patterns-established:
  - "Optional validator injection: CachedGeocoder(validator=None) is backward compatible, validator=instance enables validation"
  - "Post-geocode validation: _apply_validation() runs after both cache hits and API calls, returns new GeocodingResult"
  - "area_name as keyword-only parameter: geocode(address, *, area_name=None) prevents accidental positional usage"

requirements-completed: [GVAL-04]

# Metrics
duration: 4min
completed: 2026-03-12
---

# Phase 13 Plan 02: Model & Cache Integration Summary

**GeocodingResult.method field, OrderDB.geocode_method column, and CachedGeocoder validator injection with full backward compatibility -- 19 new TDD tests, 113 total passing**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-12T02:19:09Z
- **Completed:** 2026-03-12T02:23:46Z
- **Tasks:** 2 (TDD: RED + GREEN each)
- **Files modified:** 7

## Accomplishments
- GeocodingResult.method field defaults to "direct", accepts any string (not enum)
- OrderDB.geocode_method column (String(20), nullable) with Alembic migration
- CachedGeocoder accepts optional GeocodeValidator parameter -- backward compatible
- geocode() accepts keyword-only area_name for fallback chain activation
- Validation runs on every result (cache hit or API call) per user decision
- Circuit breaker REQUEST_DENIED/success tracking in cache layer
- Validation stats tracked (validation_direct/area_retry/centroid/depot)
- GEOCODE_ZONE_RADIUS_KM = 30 in config.py
- All 16 existing cache tests pass unchanged (backward compatibility proven)
- 113 total geocoding tests passing with zero regressions

## Task Commits

Each task was committed atomically (TDD cycles):

1. **Task 1 RED: Failing tests for model/config changes** - `8ad1c91` (test)
2. **Task 1 GREEN: GeocodingResult.method, OrderDB.geocode_method, config, migration** - `7dacf81` (feat)
3. **Task 2 RED: Failing tests for CachedGeocoder validator integration** - `471394e` (test)
4. **Task 2 GREEN: CachedGeocoder validator integration** - `ff86646` (feat)

## Files Created/Modified
- `core/geocoding/interfaces.py` - Added method field to GeocodingResult with docstring
- `core/geocoding/cache.py` - Added optional validator parameter, area_name parameter, validation after cache/API, REQUEST_DENIED tracking, validation stats
- `core/database/models.py` - Added geocode_method column to OrderDB (String(20), nullable)
- `apps/kerala_delivery/config.py` - Added GEOCODE_ZONE_RADIUS_KM = 30 constant
- `infra/alembic/versions/54c27825e8df_add_geocode_method_column_to_orders.py` - Alembic migration for geocode_method (does NOT re-add geocode_confidence)
- `tests/core/geocoding/test_interfaces_method.py` - 9 tests for method field, OrderDB column, config constant
- `tests/core/geocoding/test_cache.py` - 10 new tests in TestCachedGeocoderWithValidator class (existing 16 unchanged)

## Decisions Made
- GeocodingResult.method as plain string (not enum) to avoid import coupling between interfaces.py and validator.py. The validator sets the method value; keeping it as a string means interfaces.py stays dependency-free.
- Validation runs on both cache hits and API calls. User locked decision: "Always re-validate cached results on every upload." Cache saves API calls; validation always runs fresh.
- REQUEST_DENIED tracking only on upstream API calls (not cache hits). Cache hits have no raw_response to inspect for API status, so circuit breaker tracking is limited to actual API interactions.
- Validation stats added to CachedGeocoder.stats dict (validation_direct, validation_area_retry, validation_centroid, validation_depot) -- extends existing pattern of hits/misses/errors tracking.
- Alembic migration created manually (no Docker database available) following the pattern from 9c370459587f. Adds only geocode_method, explicitly does NOT re-add geocode_confidence.

## Deviations from Plan

None -- plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None -- no external service configuration required.

## Next Phase Readiness
- GeocodingResult carries method field for downstream badge logic (Phase 14)
- OrderDB has geocode_method column ready for persistence in upload pipeline
- CachedGeocoder validator injection ready for wiring in upload pipeline (Plan 13-03)
- All test infrastructure in place for pipeline integration tests

## Self-Check: PASSED

- [x] core/geocoding/interfaces.py has method field (verified: method in model_fields)
- [x] core/database/models.py has geocode_method column on OrderDB (verified: test passes)
- [x] apps/kerala_delivery/config.py has GEOCODE_ZONE_RADIUS_KM = 30 (verified: import + assert)
- [x] infra/alembic/versions/54c27825e8df_add_geocode_method_column_to_orders.py exists
- [x] core/geocoding/cache.py accepts validator parameter (verified: test passes)
- [x] Commit 8ad1c91 exists (Task 1 RED)
- [x] Commit 7dacf81 exists (Task 1 GREEN)
- [x] Commit 471394e exists (Task 2 RED)
- [x] Commit ff86646 exists (Task 2 GREEN)
- [x] 113/113 total geocoding tests pass (zero regressions)
- [x] 16/16 existing cache tests pass unchanged (backward compatibility)

---
*Phase: 13-geocode-validation-fallback-chain*
*Completed: 2026-03-12*
