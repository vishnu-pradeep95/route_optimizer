---
phase: 14-api-confidence-fields-and-driver-pwa-badge
plan: 01
subsystem: api
tags: [pydantic, geocoding, confidence, route-api, serialization]

# Dependency graph
requires:
  - phase: 13-geocode-validation-and-fallback-chain
    provides: "OrderDB.geocode_confidence and OrderDB.geocode_method fields populated during upload"
provides:
  - "RouteStop Pydantic model with geocode_confidence and geocode_method optional fields"
  - "GET /api/routes/{vehicle_id} response includes geocode_confidence, geocode_method, location_approximate per stop"
  - "Computed location_approximate boolean (true when confidence < 0.5, false for null or >= 0.5)"
affects: [14-02-driver-pwa-badge, dashboard-geocode-display]

# Tech tracking
tech-stack:
  added: []
  patterns: ["computed API field derived from model data (location_approximate not stored, computed at serialization)"]

key-files:
  created: []
  modified:
    - core/models/route.py
    - core/database/repository.py
    - apps/kerala_delivery/api/main.py

key-decisions:
  - "location_approximate computed inline in API serialization, not stored in Pydantic model"
  - "Null geocode_confidence (pre-Phase 13 orders) maps to location_approximate: false"

patterns-established:
  - "Computed API fields: derive boolean flags at serialization layer, not model layer"

requirements-completed: [APUI-01, APUI-02]

# Metrics
duration: 1min
completed: 2026-03-12
---

# Phase 14 Plan 01: API Confidence Fields Summary

**Route API now returns geocode_confidence, geocode_method, and computed location_approximate per stop for approximate-location badge support**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-12T03:08:01Z
- **Completed:** 2026-03-12T03:09:05Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- RouteStop Pydantic model extended with geocode_confidence (float|None, 0.0-1.0) and geocode_method (str|None)
- Repository layer propagates geocode fields from OrderDB through route_db_to_pydantic with null guard for broken FK
- API serialization includes all three new fields with correct null-safe computation of location_approximate

## Task Commits

Each task was committed atomically:

1. **Task 1: Add geocode fields to RouteStop Pydantic model** - `9db2807` (feat)
2. **Task 2: Propagate geocode fields through repository and API serialization** - `d3ffd04` (feat)

## Files Created/Modified
- `core/models/route.py` - Added geocode_confidence and geocode_method optional fields to RouteStop
- `core/database/repository.py` - route_db_to_pydantic propagates geocode fields from stop_db.order with None guard
- `apps/kerala_delivery/api/main.py` - Stop serialization dict includes geocode_confidence, geocode_method, and computed location_approximate

## Decisions Made
- location_approximate is computed inline at API serialization, not stored as a Pydantic model field -- keeps the model clean and avoids stale data
- Null geocode_confidence (pre-Phase 13 orders) maps to location_approximate: false -- follows user decision that missing data should not trigger the approximate badge

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- API now returns all three fields needed for the Driver PWA "Approx. location" badge (Plan 14-02)
- No blockers for Plan 14-02 implementation

## Self-Check: PASSED

All files exist, all commits verified.

---
*Phase: 14-api-confidence-fields-and-driver-pwa-badge*
*Completed: 2026-03-12*
