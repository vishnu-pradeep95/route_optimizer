---
phase: 04-geocoding-cache-normalization
plan: 01
subsystem: geocoding
tags: [normalization, cache, tdd, pure-function, unicode]

# Dependency graph
requires: []
provides:
  - "normalize_address() pure function -- single source of truth for cache key normalization"
  - "15 unit tests covering whitespace, casing, punctuation, Unicode NFC, idempotency, real CDCMS addresses"
  - "Repository layer integration -- get_cached_geocode() and save_geocode_cache() use normalize_address()"
affects: [04-02, geocoding-cache, duplicate-detection]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure function module pattern for shared normalization logic"
    - "TDD RED-GREEN-REFACTOR with separate commits per phase"

key-files:
  created:
    - core/geocoding/normalize.py
    - tests/core/geocoding/test_normalize.py
  modified:
    - core/database/repository.py

key-decisions:
  - "normalize_address() uses stdlib only (unicodedata, re) -- no new dependencies"
  - "Strip periods and commas as decorative; preserve slashes, hyphens, parentheses as meaningful"
  - "Four-step normalization: Unicode NFC, lowercase, strip decorative punct, collapse whitespace"

patterns-established:
  - "Pure function normalization: all cache key generation goes through normalize_address()"
  - "Import from core.geocoding.normalize in any module that needs address normalization"

requirements-completed: [GEO-01]

# Metrics
duration: 2min
completed: 2026-03-01
---

# Phase 4 Plan 1: Address Normalization Summary

**Pure normalize_address() function with TDD (15 tests) replacing inconsistent inline strip().lower() in repository cache layer**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-01T22:33:32Z
- **Completed:** 2026-03-01T22:35:53Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created normalize_address() pure function that unifies all address normalization (Unicode NFC, lowercase, strip decorative punctuation, collapse whitespace)
- 15 comprehensive unit tests covering lowercase, whitespace, tabs/newlines, periods, commas, slashes, hyphens, parentheses, Unicode NFC, idempotency, empty strings, and real CDCMS Kerala addresses
- Replaced inline address_raw.strip().lower() in both get_cached_geocode() and save_geocode_cache() with normalize_address() -- eliminates root cause of duplicate map pins from inconsistent normalization

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for normalize_address()** - `4bc84c6` (test)
2. **Task 1 GREEN: Implement normalize_address()** - `939e8fc` (feat)
3. **Task 2: Integrate into repository.py** - `5c7a655` (feat)

_TDD Task 1 has RED and GREEN commits. REFACTOR skipped -- implementation is already minimal._

## Files Created/Modified
- `core/geocoding/normalize.py` - Pure function: normalize_address() with Unicode NFC, lowercase, decorative punct removal, whitespace collapse
- `tests/core/geocoding/test_normalize.py` - 15 test methods in TestNormalizeAddress class covering all edge cases
- `core/database/repository.py` - Added import and replaced 2 inline normalizations with normalize_address() calls

## Decisions Made
None - followed plan as specified. The implementation exactly matches the plan's four-step normalization approach using stdlib only.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- normalize_address() is ready for Phase 4 Plan 2 (file cache deprecation, Alembic migration)
- The Alembic migration in Plan 2 will use normalize_address() to re-normalize existing DB entries
- GoogleGeocoder's separate SHA-256 normalization path can now be removed (Plan 2 scope)
- Full test suite passes: 395 tests, zero regressions

## Self-Check: PASSED

All files exist. All commits verified.

---
*Phase: 04-geocoding-cache-normalization*
*Completed: 2026-03-01*
