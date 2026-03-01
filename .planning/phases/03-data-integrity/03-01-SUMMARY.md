---
phase: 03-data-integrity
plan: 01
subsystem: data-import
tags: [pydantic, csv-import, validation, row-errors, coordinates]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: CsvImporter with ColumnMapping, DEPOT_LOCATION config, Vatakara coordinate migration
provides:
  - ImportResult model with orders, errors, warnings, row_numbers fields
  - RowError model for structured row-level validation errors
  - Duplicate order_id detection within CSV
  - Invalid weight warning (lenient) vs empty address error (strict)
  - All depot coordinate references verified as Vatakara (11.62N)
affects: [03-02 geocoding-failures, 03-03 dashboard-summary, api-response-enrichment]

# Tech tracking
tech-stack:
  added: []
  patterns: [ImportResult return type for import_orders(), RowError for row-level validation, warnings vs errors separation]

key-files:
  created: []
  modified:
    - core/data_import/csv_importer.py
    - core/data_import/interfaces.py
    - apps/kerala_delivery/api/main.py
    - apps/kerala_delivery/dashboard/src/components/RouteMap.tsx
    - tests/core/data_import/test_csv_importer.py
    - scripts/import_orders.py
    - scripts/compare_routes.py

key-decisions:
  - "Separate warnings (lenient defaults) from errors (row rejected) in ImportResult"
  - "RowError uses original CSV column names from ColumnMapping for staff-friendly messages"
  - "Row numbers are 1-based spreadsheet convention (pandas idx + 2)"
  - "row_numbers dict maps order_id to spreadsheet row for downstream geocoding error tracking"
  - "DataImporter protocol updated to return ImportResult (backward-compatible runtime check)"

patterns-established:
  - "ImportResult pattern: import_orders() returns structured result, callers extract .orders"
  - "Pre-validation before _row_to_order: empty address and duplicate ID checked in import_orders loop"
  - "Weight resolution returns tuple (value, optional warning) for non-fatal issues"

requirements-completed: [DATA-04, DATA-05]

# Metrics
duration: 7min
completed: 2026-03-01
---

# Phase 3 Plan 1: CSV Row-Level Validation and Depot Coordinate Audit Summary

**ImportResult return type for CsvImporter with row-level validation errors, duplicate detection, weight warnings, and Vatakara coordinate audit across 14 files**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-01T18:35:09Z
- **Completed:** 2026-03-01T18:42:53Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments
- CsvImporter.import_orders() now returns ImportResult with structured errors, warnings, and row_numbers
- Empty addresses produce RowError with original CSV column name and 1-based spreadsheet row number
- Duplicate order_ids within same CSV detected and flagged as validation errors
- Invalid weight values produce warnings (not errors) and default to 14.2kg
- Fixed RouteMap.tsx map center from Kochi (9.97N) to Vatakara (11.62N) -- was showing wrong map area
- Renamed all "kochi" test fixtures/variables to "vatakara" across 6 test files
- All 380 tests pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Add failing tests for ImportResult** - `b41f2a5` (test)
2. **Task 1 (GREEN): Implement ImportResult and row-level validation** - `08875c0` (feat)
3. **Task 2: Audit depot coordinates and rename Kochi references** - `40f8147` (fix)

_Note: Task 1 followed TDD — RED commit (failing tests) then GREEN commit (implementation)_

## Files Created/Modified
- `core/data_import/csv_importer.py` - Added RowError, ImportResult models; changed import_orders() return type
- `core/data_import/interfaces.py` - Updated DataImporter protocol to return ImportResult
- `apps/kerala_delivery/api/main.py` - Updated import_orders() callers to extract .orders
- `apps/kerala_delivery/dashboard/src/components/RouteMap.tsx` - Fixed map center from Kochi to Vatakara
- `tests/core/data_import/test_csv_importer.py` - Updated 10 existing tests, added 7 new tests (17 total)
- `scripts/import_orders.py` - Updated to use ImportResult.orders
- `scripts/compare_routes.py` - Updated to use ImportResult.orders
- `tests/test_e2e_pipeline.py` - KOCHI_DEPOT renamed to VATAKARA_DEPOT
- `tests/core/routing/test_osrm_adapter.py` - KOCHI_DEPOT renamed to VATAKARA_DEPOT
- `tests/core/geocoding/test_cache.py` - kochi_location renamed to vatakara_location
- `tests/core/models/test_models.py` - kochi_depot references updated to vatakara_depot
- `tests/integration/test_osrm_vroom_pipeline.py` - kochi_depot renamed to vatakara_depot
- `tests/core/database/test_database.py` - Updated to use ImportResult.orders
- `tests/apps/kerala_delivery/api/test_api.py` - Updated mock return values for ImportResult

## Decisions Made
- Separated warnings (lenient defaults applied) from errors (row rejected) in ImportResult -- staff sees both but errors are actionable
- RowError uses original CSV column names from ColumnMapping (e.g., "ConsumerAddress" not "address_raw") so non-technical staff can identify which spreadsheet column to fix
- Row numbers follow 1-based spreadsheet convention: header = row 1, first data = row 2 (pandas idx + 2)
- Added row_numbers dict (order_id -> row number) for downstream geocoding error tracking in Plan 03-02
- Updated DataImporter protocol return type; runtime_checkable isinstance still works because Protocol checks method existence not signatures

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated all callers of import_orders() across codebase**
- **Found during:** Task 1 (ImportResult implementation)
- **Issue:** Changing import_orders() return type from list[Order] to ImportResult broke 8 additional caller files not listed in plan's files_modified
- **Fix:** Updated scripts/import_orders.py, scripts/compare_routes.py, test_api.py (3 mock locations), test_e2e_pipeline.py (2 call sites), test_osrm_vroom_pipeline.py, test_database.py to extract .orders from ImportResult
- **Files modified:** 6 additional files beyond plan scope
- **Verification:** Full test suite (380 tests) passes
- **Committed in:** 08875c0 (Task 1 GREEN commit)

**2. [Rule 1 - Bug] Fixed RouteMap.tsx map center pointing to Kochi instead of Vatakara**
- **Found during:** Task 2 (coordinate audit)
- **Issue:** RouteMap.tsx had KOCHI_CENTER at 9.97N, 76.28E (Kochi city) -- map would center on wrong city 200km south of actual delivery area
- **Fix:** Changed to VATAKARA_CENTER at 11.6244N, 75.5796E matching config.py DEPOT_LOCATION
- **Files modified:** apps/kerala_delivery/dashboard/src/components/RouteMap.tsx
- **Verification:** Coordinates match config.py values
- **Committed in:** 40f8147 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both auto-fixes necessary for correctness. The RouteMap fix was a real bug -- dashboard map was centering on the wrong city. No scope creep.

## Issues Encountered
- pytest --timeout=60 flag not available (pytest-timeout not installed) -- ran without timeout, full suite completed in 3.09s regardless

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ImportResult model ready for Plan 03-02 (geocoding failure tracking) to add geocoding-stage errors
- row_numbers dict enables precise "Row 12: Address not found" messages in geocoding phase
- warnings vs errors separation ready for Plan 03-03 dashboard summary display
- All 380 tests passing, no regressions

## Self-Check: PASSED

All files exist, all commits verified, all 380 tests pass.

---
*Phase: 03-data-integrity*
*Completed: 2026-03-01*
