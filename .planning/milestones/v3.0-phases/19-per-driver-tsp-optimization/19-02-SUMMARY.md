---
phase: 19-per-driver-tsp-optimization
plan: 02
subsystem: api
tags: [fastapi, tsp, vroom, per-driver, upload-pipeline, pydantic]

# Dependency graph
requires:
  - phase: 19-per-driver-tsp-optimization
    provides: "Per-driver TSP orchestrator (group, optimize, validate, detect) from Plan 01"
  - phase: 16-driver-database-foundation
    provides: "DriverDB model, driver auto-creation, driver_id FK on RouteDB"
provides:
  - "Per-driver TSP integrated into upload_and_optimize endpoint"
  - "DeliveryMan column validation in parse_upload (fail fast)"
  - "Route.driver_id Pydantic field for DB persistence"
  - "Optimization warnings (overlap, anomalies) in OptimizationSummary response"
affects: [19-03-PLAN, driver-pwa, dashboard, upload-and-optimize pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns: [per-driver TSP pipeline replacing fleet CVRP, non-CDCMS fallback to single default driver]

key-files:
  created:
    - tests/apps/kerala_delivery/test_parse_upload_deliveryman.py
  modified:
    - apps/kerala_delivery/api/main.py
    - core/models/route.py
    - core/database/repository.py
    - core/data_import/cdcms_preprocessor.py

key-decisions:
  - "Non-CDCMS uploads fall back to single 'Driver' group for backward compatibility with per-driver TSP pipeline"
  - "preprocess_cdcms handles missing DeliveryMan column gracefully (fills empty strings) so parse_upload check works cleanly"
  - "Optimization warnings converted to ImportFailure objects with stage='optimization' for consistent response format"

patterns-established:
  - "Per-driver TSP: upload_and_optimize builds order_driver_map from preprocessed_df, groups orders, runs TSP per driver"
  - "Non-CDCMS backward compatibility: all orders grouped under default 'Driver' name"

requirements-completed: [OPT-01, OPT-02, OPT-03]

# Metrics
duration: 6min
completed: 2026-03-14
---

# Phase 19 Plan 02: Per-Driver TSP Integration Summary

**Per-driver TSP pipeline integrated into upload_and_optimize, DeliveryMan column validation in parse_upload, Route.driver_id persisted to DB**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-14T04:52:33Z
- **Completed:** 2026-03-14T04:59:02Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- parse_upload fails fast with 400 when DeliveryMan column is missing or empty
- upload_and_optimize now uses per-driver TSP instead of fleet CVRP -- no vehicle fleet lookup needed
- Post-optimization overlap validation and geographic anomaly detection run automatically
- Route.driver_id populated with driver UUID and persisted via save_optimization_run
- 3 new tests for DeliveryMan column validation, all 265 existing app tests still passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Add DeliveryMan column check in parse_upload** - `e444971` (feat)
2. **Task 2: Replace fleet CVRP with per-driver TSP in upload_and_optimize** - `650d00d` (feat)

## Files Created/Modified
- `apps/kerala_delivery/api/main.py` - DeliveryMan validation in parse_upload, per-driver TSP pipeline replacing fleet CVRP in upload_and_optimize, tsp_orchestrator imports
- `core/models/route.py` - Added driver_id field (uuid.UUID | None) to Route Pydantic model
- `core/database/repository.py` - save_optimization_run now persists route.driver_id FK
- `core/data_import/cdcms_preprocessor.py` - Handles missing DeliveryMan column gracefully (fills empty strings instead of KeyError)
- `tests/apps/kerala_delivery/test_parse_upload_deliveryman.py` - 3 tests: missing column, empty column, valid column

## Decisions Made
- Non-CDCMS uploads fall back to single 'Driver' group for backward compatibility -- standard CSV uploads without DeliveryMan column still work through per-driver TSP with all orders grouped under one driver
- preprocess_cdcms handles missing DeliveryMan column gracefully by filling empty strings, so the validation check in parse_upload can cleanly evaluate the column content
- Optimization warnings (overlap errors, geographic anomalies, partial failures) are converted to ImportFailure objects with stage="optimization" for consistent response format alongside validation and geocoding failures

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] preprocess_cdcms crashes on missing DeliveryMan column**
- **Found during:** Task 1 (DeliveryMan column validation)
- **Issue:** preprocess_cdcms raises KeyError at `df[CDCMS_COL_DELIVERY_MAN]` when DeliveryMan column is absent from CSV, preventing parse_upload from reaching the validation check
- **Fix:** Added conditional handling in preprocess_cdcms: `df[CDCMS_COL_DELIVERY_MAN].str.strip() if CDCMS_COL_DELIVERY_MAN in df.columns else pd.Series("", index=df.index)`
- **Files modified:** core/data_import/cdcms_preprocessor.py
- **Verification:** Test for missing DeliveryMan column now returns 400 instead of 500
- **Committed in:** e444971 (Task 1 commit)

**2. [Rule 1 - Bug] Non-CDCMS standard CSV uploads break with per-driver TSP**
- **Found during:** Task 2 (replacing fleet CVRP)
- **Issue:** Standard CSV uploads (not CDCMS) have no DeliveryMan column, so order_driver_map is empty and group_orders_by_driver returns empty dict, causing all uploads to fail with 400
- **Fix:** Added fallback for non-CDCMS uploads: all orders grouped under default "Driver" name
- **Files modified:** apps/kerala_delivery/api/main.py
- **Verification:** test_upload_csv_triggers_optimization passes (standard CSV upload still works)
- **Committed in:** 650d00d (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes essential for correctness. preprocess_cdcms fix enables the validation check; non-CDCMS fallback preserves backward compatibility. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Per-driver TSP pipeline fully integrated into both parse_upload and upload_and_optimize
- Plan 03 (dashboard and driver PWA updates) can proceed -- routes now contain driver names in vehicle_id and driver_name fields
- All 297 tests passing (32 optimizer + 265 app) with zero regressions

## Self-Check: PASSED

All files verified present. All commits verified in git log.

---
*Phase: 19-per-driver-tsp-optimization*
*Completed: 2026-03-14*
