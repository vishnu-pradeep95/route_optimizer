---
phase: 17-error-message-humanization
plan: 01
subsystem: api
tags: [error-messages, ux, validation, geocoding, python, fastapi]

# Dependency graph
requires:
  - phase: 15-csv-format-documentation
    provides: CSV_FORMAT.md with user-friendly error descriptions
provides:
  - Humanized CDCMS column validation error with comma-separated sorted names
  - Humanized CSV missing address column error with fix action
  - _humanize_row_error() helper for row-level parsing errors
  - Updated GEOCODING_REASON_MAP with "problem -- fix action" pattern
  - Friendly geocoding fallback for unknown status codes
  - ValueError catch at API boundary returning HTTP 400
affects: [api, dashboard, driver-app]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "problem -- fix action error message pattern for all user-facing errors"
    - "logger.warning() for IT debugging, friendly message for users"

key-files:
  created: []
  modified:
    - core/data_import/cdcms_preprocessor.py
    - core/data_import/csv_importer.py
    - apps/kerala_delivery/api/main.py
    - tests/core/data_import/test_cdcms_preprocessor.py
    - tests/core/data_import/test_csv_importer.py
    - tests/apps/kerala_delivery/api/test_api.py

key-decisions:
  - "All user-facing error messages follow 'problem -- fix action' pattern with ' -- ' separator"
  - "Raw technical details (column lists, API status codes) logged at WARNING level for IT, not shown to users"
  - "ValueError from preprocess_cdcms() caught at API boundary and returned as HTTP 400, not HTTP 500"

patterns-established:
  - "Error message pattern: 'Problem description -- fix action for office staff'"
  - "Dual-channel error reporting: friendly message to user, raw details to logger"

requirements-completed: [ERR-01, ERR-02]

# Metrics
duration: 6min
completed: 2026-03-06
---

# Phase 17 Plan 01: Error Message Humanization Summary

**Replaced Python set/list notation and raw API codes with plain-English "problem -- fix action" error messages across upload validation and geocoding flows**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-06T01:35:09Z
- **Completed:** 2026-03-06T01:41:30Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- CDCMS missing column errors now show sorted comma-separated names instead of Python set notation
- CSV missing address errors show friendly fix action instead of Python list notation
- Row-level parsing errors (ValueError, KeyError, TypeError) produce office-friendly messages via _humanize_row_error()
- All 6 GEOCODING_REASON_MAP entries follow "problem -- fix action" pattern
- Unknown geocoding statuses produce friendly fallback instead of "Geocoding failed (STATUS)"
- ValueError from preprocess_cdcms() returns HTTP 400 with friendly message, not HTTP 500 with traceback

## Task Commits

Each task was committed atomically (TDD: test then feat):

1. **Task 1: Humanize upload validation errors (ERR-01)**
   - `56cdf7d` (test) - add failing tests for humanized upload errors
   - `c49ad8c` (feat) - humanize upload validation error messages

2. **Task 2: Humanize geocoding error messages (ERR-02)**
   - `361a8d7` (test) - add failing tests for humanized geocoding errors
   - `3d7ecf7` (feat) - humanize geocoding error messages

## Files Created/Modified
- `core/data_import/cdcms_preprocessor.py` - Humanized missing column ValueError with logger.warning for IT
- `core/data_import/csv_importer.py` - Humanized address column error, added _humanize_row_error() helper
- `apps/kerala_delivery/api/main.py` - Updated GEOCODING_REASON_MAP, friendly fallback, ValueError catch
- `tests/core/data_import/test_cdcms_preprocessor.py` - Updated assertion for new error message format
- `tests/core/data_import/test_csv_importer.py` - Tests for _humanize_row_error and address column error format
- `tests/apps/kerala_delivery/api/test_api.py` - Tests for GEOCODING_REASON_MAP format and specific messages

## Decisions Made
- All user-facing error messages follow "problem -- fix action" pattern with " -- " separator
- Raw technical details (column lists, API status codes) logged at WARNING level for IT debugging
- ValueError from preprocess_cdcms() caught at API boundary and returned as HTTP 400

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Pre-existing test failures discovered (9 tests) caused by mock setup returning empty vehicle lists (`get_active_vehicles = AsyncMock(return_value=[])`). These are not caused by Phase 17 changes and are documented in `deferred-items.md`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Error message humanization complete for all upload validation and geocoding flows
- Pattern established: "problem -- fix action" with dual-channel reporting (user + logger)
- Pre-existing test mock issues should be addressed in a separate fix

---
*Phase: 17-error-message-humanization*
*Completed: 2026-03-06*
