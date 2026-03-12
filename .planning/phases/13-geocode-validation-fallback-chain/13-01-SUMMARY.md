---
phase: 13-geocode-validation-fallback-chain
plan: 01
subsystem: geocoding
tags: [haversine, zone-validation, fallback-chain, circuit-breaker, tdd]

# Dependency graph
requires:
  - phase: 12-place-name-dictionary
    provides: "place_names_vatakara.json with 381 entries (centroids for fallback lookup)"
provides:
  - "GeocodeValidator class with zone check, fallback chain, circuit breaker"
  - "ValidationResult dataclass with confidence/method tracking"
  - "Centroid lookup from dictionary (case-insensitive, alias-aware)"
affects: [13-02 CachedGeocoder integration, 13-03 pipeline wiring, 14 approx-location badge]

# Tech tracking
tech-stack:
  added: []
  patterns: [injectable-validator, four-level-fallback-chain, circuit-breaker-per-batch]

key-files:
  created:
    - core/geocoding/validator.py
    - tests/core/geocoding/test_validator.py
  modified: []

key-decisions:
  - "Flat 1.0 confidence for all direct in-zone hits (4-tier system, not 7-tier with Google granularity)"
  - "Circuit breaker does not un-trip on success (stateless per batch, resets on new upload)"
  - "Unused dataclass field import removed in refactor pass"

patterns-established:
  - "Fallback chain pattern: direct(1.0) -> area_retry(0.7) -> centroid(0.3) -> depot(0.1)"
  - "Circuit breaker: 3 consecutive REQUEST_DENIED trips, any success resets counter"
  - "Centroid lookup: UPPERCASE index of primary names + aliases from dictionary JSON"

requirements-completed: [GVAL-01, GVAL-02, GVAL-03, GVAL-04]

# Metrics
duration: 3min
completed: 2026-03-12
---

# Phase 13 Plan 01: GeocodeValidator Summary

**GeocodeValidator with 4-level fallback chain (direct/area_retry/centroid/depot), 30km haversine zone check, and 3-strike circuit breaker -- 32 TDD tests, all passing**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-12T02:12:07Z
- **Completed:** 2026-03-12T02:15:40Z
- **Tasks:** 3 (TDD: RED, GREEN, REFACTOR)
- **Files modified:** 2

## Accomplishments
- GeocodeValidator class with is_in_zone(), get_centroid(), validate() methods
- All 4 fallback paths tested and working: direct (1.0), area_retry (0.7), centroid (0.3), depot (0.1)
- Circuit breaker trips after 3 consecutive REQUEST_DENIED, resets counter on success
- Centroid loading from place_names_vatakara.json with case-insensitive and alias matching
- area_name=None handled gracefully (skips area retry, falls to depot)
- haversine_meters reused from duplicate_detector.py (not reimplemented)
- Pure sync business logic -- no database, async, or external dependencies
- 32 comprehensive tests covering all behavior specified in plan
- Zero regressions across 94 total geocoding tests

## Task Commits

Each task was committed atomically (TDD cycle):

1. **RED: Failing tests** - `33950c6` (test) - 32 tests for all validator behaviors
2. **GREEN: Implementation** - `d2adc23` (feat) - GeocodeValidator class with full fallback chain
3. **REFACTOR: Cleanup** - `e98474d` (refactor) - Remove unused dataclass field import

## Files Created/Modified
- `core/geocoding/validator.py` - GeocodeValidator class with zone check, fallback chain, circuit breaker (332 lines)
- `tests/core/geocoding/test_validator.py` - Comprehensive unit tests for all validator behaviors (459 lines)

## Decisions Made
- Used flat 1.0 confidence for all direct in-zone hits rather than Google's sub-tier granularity (ROOFTOP=0.95, APPROXIMATE=0.40). The 4-tier confidence system maps to the fallback method, keeping Phase 14's badge logic simple. Raw Google confidence preserved separately in geocode_cache.
- Circuit breaker does not un-trip on success -- it is stateless per batch and resets on new upload (new GeocodeValidator instance).
- Area-name retry records REQUEST_DENIED responses to increment the circuit breaker even when the retry call itself fails.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- GeocodeValidator ready for injection into CachedGeocoder (Plan 13-02)
- ValidationResult dataclass ready for pipeline integration (Plan 13-03)
- All test infrastructure in place for integration tests

## Self-Check: PASSED

- [x] core/geocoding/validator.py exists (332 lines, >= 100 min)
- [x] tests/core/geocoding/test_validator.py exists (459 lines, >= 150 min)
- [x] Commit 33950c6 exists (RED: failing tests)
- [x] Commit d2adc23 exists (GREEN: implementation)
- [x] Commit e98474d exists (REFACTOR: cleanup)
- [x] 32/32 validator tests pass
- [x] 94/94 total geocoding tests pass (zero regressions)

---
*Phase: 13-geocode-validation-fallback-chain*
*Completed: 2026-03-12*
