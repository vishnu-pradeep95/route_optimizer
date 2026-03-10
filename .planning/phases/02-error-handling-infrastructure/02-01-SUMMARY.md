---
phase: 02-error-handling-infrastructure
plan: 01
subsystem: api
tags: [fastapi, pydantic, middleware, error-handling, contextvar, request-tracing]

# Dependency graph
requires: []
provides:
  - ErrorResponse Pydantic model with 7 fields (success, error_code, user_message, technical_message, request_id, timestamp, help_url)
  - ErrorCode StrEnum with 22 namespaced codes
  - error_response() helper with auto help_url population
  - RequestIDMiddleware generating 8-char hex IDs via ContextVar
  - RequestIDFilter for log record injection
  - Global HTTPException handler wrapping all errors in ErrorResponse format
  - OptimizationSummary partial success contract (success, imported, total, warnings)
affects: [02-error-handling-infrastructure, dashboard-error-ui]

# Tech tracking
tech-stack:
  added: []
  patterns: [ErrorResponse model, error_response() helper, RequestIDMiddleware, ContextVar request tracing, global exception handler]

key-files:
  created:
    - apps/kerala_delivery/api/errors.py
    - apps/kerala_delivery/api/middleware.py
    - tests/apps/kerala_delivery/api/test_errors.py
    - tests/apps/kerala_delivery/api/test_middleware.py
  modified:
    - apps/kerala_delivery/api/main.py
    - tests/apps/kerala_delivery/api/test_api.py

key-decisions:
  - "Auth dependency (_check_api_key) keeps raise HTTPException -- caught by global handler"
  - "sw.js 404 keeps raise HTTPException -- internal, not user-facing"
  - "ERROR_HELP_URLS maps 15 error codes to docs/ paths for frontend help links"
  - "RequestIDMiddleware registered LAST for outermost execution"

patterns-established:
  - "error_response() pattern: return error_response(status, ErrorCode.X, 'Problem -- fix action', technical_message, request_id_var.get(''))"
  - "All API errors return {success, error_code, user_message, technical_message, request_id, timestamp, help_url}"
  - "Log format: [request_id] LEVEL module: message for grep-based correlation"

requirements-completed: [ERR-01, ERR-02, ERR-03]

# Metrics
duration: 7min
completed: 2026-03-10
---

# Phase 02 Plan 01: Error Response Model & HTTPException Migration Summary

**ErrorResponse Pydantic model with 22 namespaced ErrorCodes, RequestID middleware via ContextVar, and migration of all 30 HTTPException calls to structured error_response() format**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-10T01:19:22Z
- **Completed:** 2026-03-10T01:26:30Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Created ErrorResponse model and ErrorCode enum with 22 namespaced codes covering all API subsystems
- Built RequestIDMiddleware generating 8-char hex IDs, RequestIDFilter for log injection, LOG_FORMAT constant
- Migrated all 30 HTTPException calls in main.py to error_response() with proper ErrorCodes
- Added global HTTPException handler as safety net for unmigrated exceptions
- Added success/imported/total fields to OptimizationSummary for partial success contract
- Configured logging with [request_id] prefix across all log lines
- 169 tests passing (32 new + 137 existing updated)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create ErrorResponse model, ErrorCode enum, and Request ID middleware with tests** - `9354cdb` (feat, TDD)
2. **Task 2: Wire middleware into main.py, add global exception handler, migrate all HTTPExceptions** - `04871e5` (feat)

## Files Created/Modified
- `apps/kerala_delivery/api/errors.py` - ErrorResponse model, ErrorCode enum (22 codes), error_response() helper, ERROR_HELP_URLS mapping
- `apps/kerala_delivery/api/middleware.py` - RequestIDMiddleware, RequestIDFilter, request_id_var ContextVar, LOG_FORMAT
- `apps/kerala_delivery/api/main.py` - Migrated 30 HTTPExceptions, registered middleware, added exception handler, added partial success fields
- `tests/apps/kerala_delivery/api/test_errors.py` - 23 unit tests for ErrorResponse, ErrorCode, error_response(), ERROR_HELP_URLS
- `tests/apps/kerala_delivery/api/test_middleware.py` - 9 integration tests for RequestIDMiddleware, RequestIDFilter
- `tests/apps/kerala_delivery/api/test_api.py` - Updated assertions from detail to user_message format

## Decisions Made
- Auth dependency (_check_api_key) keeps `raise HTTPException` because FastAPI dependency injection requires raising, not returning. The global handler wraps it in ErrorResponse format.
- sw.js 404 HTTPException left as-is per plan -- internal endpoint, not user-facing.
- ERROR_HELP_URLS maps 15 commonly-hit error codes to docs/ paths. Unmapped codes get empty help_url.
- RequestIDMiddleware registered LAST in middleware chain so it runs FIRST (outermost layer), ensuring even auth errors include request_id.
- X-Request-ID added to CORS expose_headers so frontend can read it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test assertions for new error response format**
- **Found during:** Task 2
- **Issue:** 13 test assertions checked `resp.json()["detail"]` which no longer exists in the new ErrorResponse format
- **Fix:** Updated all assertions to use `resp.json().get("user_message", resp.json().get("detail", ""))` for compatibility
- **Files modified:** tests/apps/kerala_delivery/api/test_api.py
- **Verification:** All 169 tests pass
- **Committed in:** 04871e5 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential fix for test compatibility with new error format. No scope creep.

## Issues Encountered
- Docker container does not volume-mount source code; tests must run via `docker run --rm -v` with host mount. This is a known infrastructure pattern for this project.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- ErrorResponse model and error_response() helper ready for use by Plans 02-04
- RequestIDMiddleware active on all requests
- Global exception handler catches any future HTTPExceptions during migration period
- OptimizationSummary partial success contract ready for frontend consumption

---
*Phase: 02-error-handling-infrastructure*
*Completed: 2026-03-10*
