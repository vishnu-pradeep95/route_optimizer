---
phase: 03-data-integrity
plan: 02
subsystem: api
tags: [pydantic, geocoding, error-handling, fastapi, import-diagnostics]

# Dependency graph
requires:
  - phase: 03-data-integrity
    provides: ImportResult model with orders, errors, warnings, row_numbers from Plan 01
provides:
  - ImportFailure model for per-row failure details (validation + geocoding stages)
  - GEOCODING_REASON_MAP mapping Google API statuses to staff-friendly messages
  - Enriched OptimizationSummary with total_rows, geocoded, failed_geocoding, failed_validation, failures, warnings
  - Zero-success structured 200 response instead of HTTPException 400
  - Geocoding failure collection with human-readable reasons
affects: [03-03 dashboard-summary, frontend-types, api-response-consumers]

# Tech tracking
tech-stack:
  added: []
  patterns: [ImportFailure for structured per-row failures, GEOCODING_REASON_MAP for API status translation, structured zero-success response]

key-files:
  created: []
  modified:
    - apps/kerala_delivery/api/main.py
    - tests/apps/kerala_delivery/api/test_api.py

key-decisions:
  - "Zero-success returns structured HTTP 200 with run_id='' and failures list, not HTTPException 400"
  - "GEOCODING_REASON_MAP translates raw Google API statuses to office-staff-friendly messages"
  - "ImportFailure stage field distinguishes validation vs geocoding failures for dashboard display"
  - "All new OptimizationSummary fields default to zero/empty for backward compatibility"
  - "Diagnostic geocoder test on zero-success logs to server (logger.error) instead of embedding in HTTP response"

patterns-established:
  - "ImportFailure pattern: row_number + address_snippet + reason + stage for all import failures"
  - "Structured error response: zero-success returns 200 with empty run_id and populated failures array"
  - "GEOCODING_REASON_MAP: centralized status-to-message mapping for Google API codes"

requirements-completed: [DATA-01, DATA-02, DATA-03]

# Metrics
duration: 4min
completed: 2026-03-01
---

# Phase 3 Plan 2: Geocoding Failure Collection and Structured Import Diagnostics Summary

**ImportFailure model, GEOCODING_REASON_MAP, enriched OptimizationSummary with per-row failure details, and zero-success structured 200 response**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-01T18:45:56Z
- **Completed:** 2026-03-01T18:49:43Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Added ImportFailure Pydantic model with row_number, address_snippet, reason, and stage fields for per-row failure reporting
- Added GEOCODING_REASON_MAP translating Google API statuses (ZERO_RESULTS, REQUEST_DENIED, etc.) to office-staff-friendly messages
- Enriched OptimizationSummary with total_rows, geocoded, failed_geocoding, failed_validation, failures, and warnings fields (all with defaults for backward compatibility)
- Modified upload_and_optimize() to collect geocoding failures with human-readable reasons during the geocoding loop
- Replaced zero-success HTTPException(400) with structured HTTP 200 response containing run_id="", orders_assigned=0, and all failure details
- Updated test to expect structured 200 response instead of 400 for zero-geocoding-success case
- All 380 tests pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add ImportFailure model, enrich OptimizationSummary, and collect geocoding errors** - `16682a4` (feat)

## Files Created/Modified
- `apps/kerala_delivery/api/main.py` - Added ImportFailure model, GEOCODING_REASON_MAP, enriched OptimizationSummary, modified upload_and_optimize() for geocoding failure collection and zero-success structured response
- `tests/apps/kerala_delivery/api/test_api.py` - Updated test_upload_all_geocoding_failures to expect structured 200 response with per-row failure details

## Decisions Made
- Zero-success returns structured HTTP 200 with run_id="" and failures list instead of HTTPException 400 -- staff sees per-row reasons and can fix addresses
- GEOCODING_REASON_MAP maps raw Google API statuses to office-friendly messages (e.g., ZERO_RESULTS becomes "Address not recognized by Google Maps")
- ImportFailure.stage distinguishes "validation" (bad CSV data) from "geocoding" (valid row but address not found) for dashboard display
- All new OptimizationSummary fields default to zero/empty for backward compatibility -- existing clients continue to work unchanged
- Diagnostic geocoder test on zero-success logs via logger.error instead of embedding in HTTP response detail -- keeps response structure clean

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test expecting 400 for zero-geocoding-success**
- **Found during:** Task 1 (verification)
- **Issue:** test_upload_all_geocoding_failures_returns_400 expected HTTPException(400) but the behavior change intentionally returns structured 200
- **Fix:** Renamed to test_upload_all_geocoding_failures_returns_structured_200, updated assertions to verify structured response fields (run_id="", orders_assigned=0, total_rows=2, geocoded=0)
- **Files modified:** tests/apps/kerala_delivery/api/test_api.py
- **Verification:** All 380 tests pass
- **Committed in:** 16682a4 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug - expected test update for intentional behavior change)
**Impact on plan:** Necessary update to match the intentional behavior change from 400 to structured 200. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ImportFailure and enriched OptimizationSummary ready for Plan 03-03 (dashboard summary display)
- TypeScript types in dashboard will need updating to match new response shape (failures, warnings arrays)
- total_rows, geocoded, failed_geocoding, failed_validation summary counts ready for dashboard summary bar
- All 380 tests passing, no regressions

## Self-Check: PASSED

All files exist, all commits verified, all 380 tests pass.

---
*Phase: 03-data-integrity*
*Completed: 2026-03-01*
