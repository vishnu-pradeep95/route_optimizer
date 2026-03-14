---
phase: 19-per-driver-tsp-optimization
plan: 01
subsystem: optimizer
tags: [vroom, tsp, shapely, convex-hull, alembic, postgresql]

# Dependency graph
requires:
  - phase: 16-driver-database-foundation
    provides: "DriverDB model, driver auto-creation, driver_id FK on RouteDB"
provides:
  - "Per-driver TSP orchestrator: group_orders_by_driver, optimize_per_driver, validate_no_overlap, detect_geographic_anomalies"
  - "Alembic migration widening routes.vehicle_id and telemetry.vehicle_id to VARCHAR(100)"
  - "Updated ORM models for RouteDB and TelemetryDB with String(100) vehicle_id"
affects: [19-02-PLAN, 19-03-PLAN, upload-and-optimize pipeline, driver-pwa, dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns: [per-driver TSP orchestration, convex hull overlap detection, partial failure with warnings]

key-files:
  created:
    - core/optimizer/tsp_orchestrator.py
    - tests/core/optimizer/test_tsp_orchestrator.py
    - infra/alembic/versions/b3e8f4a17c02_widen_vehicle_id_for_driver_names.py
  modified:
    - core/database/models.py
    - infra/postgres/init.sql

key-decisions:
  - "Partial failure returns partial results with warnings (not full batch failure)"
  - "Shapely for convex hull computation (already installed, no DB round-trip needed)"
  - "Collinear/degenerate hulls gracefully skipped (only Polygon hulls compared)"

patterns-established:
  - "Per-driver TSP: call VroomAdapter.optimize once per driver with 1 vehicle (uncapped capacity)"
  - "Geographic anomaly detection: convex hull overlap ratio threshold at 30%"
  - "Route identity: R-{assignment_id}-{driver_name} format with driver name in vehicle_id column"

requirements-completed: [OPT-01, OPT-02, OPT-03, OPT-04, OPT-05]

# Metrics
duration: 3min
completed: 2026-03-14
---

# Phase 19 Plan 01: Per-Driver TSP Orchestrator Summary

**Per-driver TSP orchestrator with Shapely convex hull overlap detection, 17 unit tests, and Alembic migration widening vehicle_id to VARCHAR(100)**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-14T04:45:40Z
- **Completed:** 2026-03-14T04:49:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created `core/optimizer/tsp_orchestrator.py` with 4 exported functions: grouping, optimization, overlap validation, anomaly detection
- 17 unit tests all passing covering all behaviors including partial failure, degenerate hulls, and edge cases
- Alembic migration and ORM updates widening vehicle_id from VARCHAR(20) to VARCHAR(100) on routes and telemetry tables
- Existing 15 vroom_adapter tests still passing (zero regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create tsp_orchestrator.py with full test suite** - `9d394e5` (test: failing tests - TDD RED) + `8ef310d` (feat: implementation - TDD GREEN)
2. **Task 2: Alembic migration and ORM update** - `7b20dff` (chore: column widening)

## Files Created/Modified
- `core/optimizer/tsp_orchestrator.py` - Per-driver TSP orchestration: grouping, VROOM calls, merge, validation, anomaly detection
- `tests/core/optimizer/test_tsp_orchestrator.py` - 17 unit tests for all orchestrator functions
- `infra/alembic/versions/b3e8f4a17c02_widen_vehicle_id_for_driver_names.py` - Alembic migration widening vehicle_id columns
- `core/database/models.py` - RouteDB and TelemetryDB vehicle_id widened to String(100)
- `infra/postgres/init.sql` - routes and telemetry vehicle_id widened to VARCHAR(100)

## Decisions Made
- Partial failure returns partial results with warnings -- if 5 drivers are optimized and 1 fails, the other 4 still get routes. Failed driver's orders become unassigned.
- Shapely (pure Python) for convex hull computation -- already installed via GeoAlchemy2, no DB round-trip, easier to test
- Collinear/degenerate hulls (LineString geometry) gracefully skipped -- only Polygon hulls are compared for overlap

## Deviations from Plan

None -- plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `tsp_orchestrator.py` ready for integration into `upload_and_optimize()` pipeline in Plan 02
- Vehicle_id column widened and ready for driver name storage
- All 4 functions exported and documented with docstrings

## Self-Check: PASSED

All files verified present. All commits verified in git log.

---
*Phase: 19-per-driver-tsp-optimization*
*Completed: 2026-03-14*
