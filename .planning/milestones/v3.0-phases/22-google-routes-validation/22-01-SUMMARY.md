---
phase: 22-google-routes-validation
plan: 01
subsystem: api, database
tags: [google-routes-api, httpx, validation, osrm, cvrp, alembic, sqlalchemy]

# Dependency graph
requires:
  - phase: 21-dashboard-settings
    provides: SettingsDB key-value store, _cached_api_key, API key management
provides:
  - RouteValidationDB ORM model for persisting Google Routes comparison results
  - Alembic migration creating route_validations table
  - Repository CRUD for validations (save, get, stats, increment, recent, confidence_level)
  - POST /api/routes/{vehicle_id}/validate endpoint calling Google Routes API
  - GET /api/validation-stats and GET /api/validation-stats/recent endpoints
affects: [22-02 (frontend validation UI), dashboard Settings page]

# Tech tracking
tech-stack:
  added: []
  patterns: [Google Routes API computeRoutes with optimizeWaypointOrder, field mask headers, duration "Xs" parsing]

key-files:
  created:
    - infra/alembic/versions/f7b2d4e19a33_add_route_validations_table.py
    - tests/apps/kerala_delivery/api/test_validation.py
  modified:
    - core/database/models.py
    - core/database/repository.py
    - apps/kerala_delivery/api/main.py

key-decisions:
  - "Confidence thresholds: green <=10%, amber <=25%, red >25% distance delta"
  - "Google Routes API Pro tier ($0.01/request) with TRAFFIC_UNAWARE routing preference"
  - "Cumulative validation stats stored in SettingsDB key-value store (validation_count, validation_total_cost_usd)"
  - "Route-level comparison only (not per-stop) since Google re-optimizes stop order"

patterns-established:
  - "Google Routes API integration: httpx.AsyncClient with X-Goog-Api-Key and X-Goog-FieldMask headers"
  - "Duration parsing: int(duration.rstrip('s')) / 60.0 for Google's 'Xs' format"
  - "Validation caching: return cached result unless ?force=true query parameter"

requirements-completed: [VAL-01, VAL-02, VAL-03, VAL-04]

# Metrics
duration: 6min
completed: 2026-03-15
---

# Phase 22 Plan 01: Google Routes Validation Backend Summary

**Google Routes API validation endpoint with OSRM comparison, confidence indicators, caching, cost tracking, and 20 tests with mocked API responses**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-14T23:54:37Z
- **Completed:** 2026-03-15T00:01:03Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- RouteValidationDB model with Alembic migration for persisting OSRM vs Google comparison results
- POST /api/routes/{vehicle_id}/validate endpoint that calls Google Routes API computeRoutes with waypoint optimization
- GET /api/validation-stats and GET /api/validation-stats/recent for cumulative cost tracking
- Full error handling: no API key (400), route not found (404), too many stops (400), timeout/HTTP errors (502)
- Cached validation results with ?force=true bypass for re-validation
- 20 passing tests covering all endpoint behaviors with mocked Google API responses

## Task Commits

Each task was committed atomically:

1. **Task 1: RouteValidationDB model, Alembic migration, repository CRUD, and tests** - `c9c067a` (feat)
2. **Task 2: POST validate endpoint, GET stats endpoints, and endpoint tests** - `5602ab5` (feat)

_Both tasks followed TDD: failing tests first (RED), then implementation (GREEN)._

## Files Created/Modified
- `core/database/models.py` - Added RouteValidationDB model with all columns and route relationship
- `core/database/repository.py` - Added save/get/stats/increment/recent validation functions and confidence_level helper
- `infra/alembic/versions/f7b2d4e19a33_add_route_validations_table.py` - Alembic migration creating route_validations table
- `apps/kerala_delivery/api/main.py` - Added validate_route, get_validation_stats, get_recent_validations endpoints
- `tests/apps/kerala_delivery/api/test_validation.py` - 20 tests covering all behaviors with mocked Google API

## Decisions Made
- Confidence thresholds set to green <=10%, amber <=25%, red >25% based on practical routing accuracy expectations
- Used Google Routes API computeRoutes (not legacy Directions API) with TRAFFIC_UNAWARE preference for stable comparison
- Cumulative validation count and cost tracked via existing SettingsDB key-value store (no new table needed)
- Route-level comparison only (not per-stop) since Google re-optimizes waypoint order
- INR conversion at 92.5 rate (approximate, displayed as estimate)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. Google Maps API key is already managed via the Settings page (Phase 21).

## Next Phase Readiness
- Backend validation infrastructure complete and tested
- Ready for 22-02: Frontend dashboard integration (validate button, inline results, cost modal, Settings history card)
- All three endpoints available: POST validate, GET stats, GET recent

## Self-Check: PASSED

All files exist, all commits verified, all must-have artifacts confirmed.

---
*Phase: 22-google-routes-validation*
*Completed: 2026-03-15*
