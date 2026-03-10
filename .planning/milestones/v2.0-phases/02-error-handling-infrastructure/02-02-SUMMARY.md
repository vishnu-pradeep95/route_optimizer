---
phase: 02-error-handling-infrastructure
plan: 02
subsystem: api
tags: [health-check, retry, tenacity, startup-gates, service-health]

# Dependency graph
requires:
  - phase: 02-01
    provides: ErrorResponse model, ErrorCode enum, RequestIDMiddleware, error_response() helper
provides:
  - health.py with per-service health checks (PostgreSQL, OSRM, VROOM, Google API)
  - wait_for_services() startup gate with 60s timeout and sequential checking
  - retry.py with tenacity retry decorators for transient external service failures
  - Enhanced /health endpoint with per-service status and overall healthy/degraded/unhealthy
  - Retry wiring at geocoding and optimizer call sites in main.py
affects: [02-03, 02-04, dashboard-status-bar, start-daily-sh]

# Tech tracking
tech-stack:
  added: [tenacity==9.1.4]
  patterns: [startup-health-gates, per-service-health-endpoint, call-site-retry-decorators]

key-files:
  created:
    - apps/kerala_delivery/api/health.py
    - apps/kerala_delivery/api/retry.py
    - tests/apps/kerala_delivery/api/test_health.py
    - tests/apps/kerala_delivery/api/test_retry.py
  modified:
    - apps/kerala_delivery/api/main.py
    - requirements.txt
    - tests/apps/kerala_delivery/api/test_api.py

key-decisions:
  - "Call-site retry wrapping (geocoder._call_api = geocoding_retry(...)) avoids modifying core/ files"
  - "Per-service health uses tuple[bool, str] return type for consistent API across all checks"
  - "OSRM 400 treated as healthy (running but bad coords input) to avoid false negatives"
  - "wait_for_services checks sequentially (PG->OSRM->VROOM) with shared timeout deadline"

patterns-established:
  - "Startup health gates: wait_for_services() in lifespan with timeout, degrade gracefully"
  - "Call-site retry: decorator applied at usage point, not on core module methods"
  - "Health endpoint: per-service breakdown with overall status and HTTP 503 on degraded"

requirements-completed: [ERR-04, ERR-05, ERR-06]

# Metrics
duration: 11min
completed: 2026-03-10
---

# Phase 02 Plan 02: Health Checks, Startup Gates & Retry Summary

**Startup health gates blocking until PG/OSRM/VROOM ready (60s timeout), enhanced /health with per-service status, and tenacity retry decorators for geocoding and optimizer HTTP calls**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-10T01:36:22Z
- **Completed:** 2026-03-10T01:48:05Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- health.py: async health checks for PostgreSQL (SELECT 1), OSRM (nearest query), VROOM (/health), Google API (env key check)
- wait_for_services() blocks startup sequentially with 2s retry interval, 60s total timeout, starts in degraded mode on timeout
- retry.py: tenacity decorators -- geocoding_retry (3 attempts, 1-10s backoff) and optimizer_retry (2 attempts, 2-15s backoff)
- Enhanced /health returns per-service breakdown with overall healthy/degraded/unhealthy status and 503 on degraded
- Retry decorators applied at call sites: geocoder._call_api and optimizer.optimize wrapped in main.py
- 21 new unit tests (12 health + 9 retry), all 190 API tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Create health check module and retry decorators with tests** - `10800da` (test: RED phase), `0730436` (feat: GREEN phase)
2. **Task 2: Wire startup health gates, enhance /health, apply retry decorators** - `1bcb189` (feat)

_Note: Task 1 followed TDD with separate RED and GREEN commits._

## Files Created/Modified
- `apps/kerala_delivery/api/health.py` - Per-service health checks and startup wait_for_services()
- `apps/kerala_delivery/api/retry.py` - Tenacity retry decorators for geocoding and optimizer calls
- `apps/kerala_delivery/api/main.py` - Startup health gates in lifespan, enhanced /health endpoint, retry wiring at call sites
- `requirements.txt` - Added tenacity==9.1.4
- `tests/apps/kerala_delivery/api/test_health.py` - 12 tests for health module
- `tests/apps/kerala_delivery/api/test_retry.py` - 9 tests for retry module
- `tests/apps/kerala_delivery/api/test_api.py` - Updated health test and all fixtures to mock wait_for_services

## Decisions Made
- Used call-site retry wrapping (`geocoder._call_api = geocoding_retry(geocoder._call_api)`) to avoid modifying core/ modules that are shared infrastructure
- OSRM HTTP 400 treated as "available" because it means the service is running (just received invalid coordinates in the health check probe)
- wait_for_services uses a shared deadline across all services rather than per-service timeouts
- Test fixtures set `app.state.service_health` directly to avoid lifespan context manager issues with TestClient

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test fixtures to mock wait_for_services and set app.state**
- **Found during:** Task 2 (test execution)
- **Issue:** TestClient(app) triggers lifespan which calls wait_for_services trying to connect to real services. Also, app.state.service_health was not set when lifespan didn't run in TestClient without context manager.
- **Fix:** Added `patch("apps.kerala_delivery.api.main.wait_for_services", ...)` and direct `app.state.service_health = mock_health` to all 4 TestClient fixtures (client, auth_client, rate_limited_client, production client)
- **Files modified:** tests/apps/kerala_delivery/api/test_api.py
- **Verification:** All 190 tests pass
- **Committed in:** 1bcb189

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential fix for test infrastructure. No scope creep.

## Issues Encountered
- Local Python environment missing many project dependencies (asyncpg, tenacity, etc.) -- installed them with pip3 for local test execution since Docker container doesn't mount the tests/ directory
- TestClient without context manager does not reliably trigger lifespan in Starlette 0.52.1 -- resolved by setting app.state directly in fixtures

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Health module ready for Plan 03 (structured logging) to log service health state
- Enhanced /health endpoint ready for dashboard status bar integration
- Retry decorators in place, protecting against transient failures for geocoding and optimization
- Plan 04 (frontend error display) can use the per-service health data

---
*Phase: 02-error-handling-infrastructure*
*Completed: 2026-03-10*
