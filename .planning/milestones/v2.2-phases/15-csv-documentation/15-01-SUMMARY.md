---
phase: 15-csv-documentation
plan: 01
subsystem: testing
tags: [pytest, integration-test, geocoding, cdcms, address-pipeline, mock-geocoder]

# Dependency graph
requires:
  - phase: 11-address-cleaning
    provides: "13-step clean_cdcms_address pipeline"
  - phase: 12-place-name-dictionary
    provides: "381-entry place_names_vatakara.json with centroids"
  - phase: 13-geocode-validation
    provides: "GeocodeValidator with zone check, fallback chain, circuit breaker"
  - phase: 14-api-confidence
    provides: "location_approximate flag (confidence < 0.5)"
provides:
  - "Integration tests proving full v2.2 address pipeline works end-to-end (9 tests)"
  - "HDFC ERGO regression test proving out-of-zone geocode triggers fallback"
  - "Mock geocoder patterns for area-aware and out-of-zone testing"
affects: [15-02-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Area-aware mock geocoder: returns dictionary centroids for known place names"
    - "Out-of-zone mock geocoder: returns Kozhikode coords (~40km) to simulate HDFC ERGO bug"
    - "Module-scoped fixture for read-only CDCMS DataFrame"

key-files:
  created:
    - tests/integration/test_address_pipeline.py
  modified: []

key-decisions:
  - "27 rows (not 28): sample CSV has 27 data rows, all Allocated-Printed status"
  - "Both test classes written in single file creation since plan specifies same file for both tasks"
  - "Mock geocoder uses dictionary centroids (not arbitrary in-zone coords) for realistic simulation"

patterns-established:
  - "_make_area_geocoder: mock geocoder pattern for dictionary-based area matching"
  - "_make_out_of_zone_geocoder: mock pattern for simulating wrong-location geocode results"

requirements-completed: [TEST-01, TEST-02]

# Metrics
duration: 3min
completed: 2026-03-12
---

# Phase 15 Plan 01: Integration Tests Summary

**9 pytest integration tests verifying full CDCMS address pipeline (cleaning + validation + fallback) with real sample data and mock geocoding**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-12T03:54:57Z
- **Completed:** 2026-03-12T03:58:07Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- All 27 CDCMS addresses process through cleaning + validation pipeline without errors
- Every address either geocodes within 30km of depot or is flagged with location_approximate: true (confidence < 0.5)
- HDFC ERGO bug scenario verified: out-of-zone geocode result (Kozhikode, ~40km) triggers fallback chain, never silently accepted as 'direct'
- Dictionary covers all 9 CDCMS area names with centroids (100% coverage)
- Validator stats confirm direct hits exist (proving in-zone addresses are correctly identified)

## Task Commits

Each task was committed atomically:

1. **Task 1: Full pipeline integration test (TEST-01)** - `fd8e521` (test)
   - TestFullPipeline: 5 tests covering all 27 CDCMS addresses
   - TestHdfcErgoBug: 4 tests for HDFC ERGO regression (same file, same commit)

_Note: Task 2 (HDFC ERGO regression) was written in the same file as Task 1 per plan specification. Both test classes committed together since they share the file._

## Files Created/Modified
- `tests/integration/test_address_pipeline.py` - 381-line integration test file with TestFullPipeline (5 tests) and TestHdfcErgoBug (4 tests), plus _make_area_geocoder and _make_out_of_zone_geocoder helpers

## Decisions Made
- **27 rows, not 28:** The sample CSV has 27 data rows (plan mentioned 28, research noted possible discrepancy). All 27 have "Allocated-Printed" status.
- **Single commit for both tasks:** Both test classes are in the same file as specified by the plan ("Add class TestHdfcErgoBug to the same test file created in Task 1").
- **Mock geocoder uses dictionary centroids:** More realistic than arbitrary in-zone coordinates -- tests exercise the actual dictionary content.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing API test failure (`test_get_driver_route_returns_stops`) unrelated to this plan. All 226 tests in integration/geocoding/data_import pass cleanly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Integration tests complete and passing for TEST-01 and TEST-02
- Ready for Plan 15-02 (METRICS.md with accuracy measurements and NER upgrade documentation for TEST-03 and TEST-04)

## Self-Check: PASSED

- FOUND: tests/integration/test_address_pipeline.py
- FOUND: .planning/milestones/v2.2-phases/15-csv-documentation/15-01-SUMMARY.md
- FOUND: fd8e521 (Task 1 commit)

---
*Phase: 15-csv-documentation*
*Completed: 2026-03-12*
