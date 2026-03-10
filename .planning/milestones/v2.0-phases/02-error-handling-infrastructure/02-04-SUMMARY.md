---
phase: 02-error-handling-infrastructure
plan: 04
subsystem: testing
tags: [playwright, e2e, error-ui, error-banner, error-table, health-status, dashboard]

# Dependency graph
requires:
  - phase: 02-03
    provides: ErrorBanner, ErrorDetail, ErrorTable components with data-testid attributes; per-service health status bar in sidebar
provides:
  - Playwright E2E test suite (e2e/dashboard-errors.spec.ts) covering all error UI elements
  - Updated playwright.config.ts dashboard project to glob pattern for multiple spec files
affects: [dashboard-e2e-tests, regression-testing, ci-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns: [e2e-error-ui-testing, force-click-daisyui-collapse, upload-form-reset-before-test]

key-files:
  created:
    - e2e/dashboard-errors.spec.ts
  modified:
    - playwright.config.ts

key-decisions:
  - "Use setInputFiles with .txt file to trigger client-side validation errors (avoids needing API_KEY for error banner tests)"
  - "Force-click on DaisyUI collapse toggle buttons to bypass hidden checkbox overlay interception"
  - "Scope health bar selector to aside.app-sidebar to disambiguate desktop vs mobile drawer instances"
  - "Navigate to upload form first (click 'Upload New File') when existing routes are loaded on dashboard"

patterns-established:
  - "E2E tests for DaisyUI collapse components must use force:true on click to bypass checkbox overlay"
  - "Dashboard error tests use navigateToUploadForm() helper to handle pre-existing route state"
  - "Error UI tests are separated into dashboard-errors.spec.ts (no API_KEY needed) from main dashboard.spec.ts (needs API_KEY)"

requirements-completed: [ERR-07, ERR-08, ERR-09]

# Metrics
duration: 10min
completed: 2026-03-10
---

# Phase 02 Plan 04: Dashboard Error UI E2E Tests Summary

**Playwright E2E test suite covering ErrorBanner severity/details/retry, ErrorTable columns, health status bar, and console error checks -- 7 tests, all passing**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-10T02:03:57Z
- **Completed:** 2026-03-10T02:13:58Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Created e2e/dashboard-errors.spec.ts with 7 test cases covering every error UI element
- ErrorBanner severity color-coding verified (data-severity attribute + alert-error CSS class)
- "Show details" toggle interaction verified (click toggle, check error_code, request_id, timestamp in detail panel)
- Retry button existence, clickability, and form-reset behavior verified
- Dismiss button banner-removal behavior verified
- ErrorTable column structure verified (Row #, Address, Reason) after CSV upload with bad rows
- Health status bar per-service indicators verified in desktop sidebar
- No console errors during error UI interactions verified
- Updated playwright.config.ts testMatch from exact string to glob pattern
- CONTEXT.md HARD REQUIREMENT satisfied: every error UI element has Playwright E2E test coverage

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Playwright E2E test suite for dashboard error UI components** - `d72a81a` (test)

## Files Created/Modified
- `e2e/dashboard-errors.spec.ts` - 319-line Playwright test suite with 7 test cases for all error UI elements
- `playwright.config.ts` - Dashboard project testMatch updated from `dashboard.spec.ts` to `dashboard*.spec.ts`

## Decisions Made
- Used `setInputFiles` with a `.txt` file to trigger client-side validation errors, avoiding the need for API_KEY authentication in error banner tests
- Used `force: true` on DaisyUI collapse toggle button clicks because the hidden checkbox input intercepts pointer events
- Scoped health status bar selector to `aside.app-sidebar` to disambiguate the desktop sidebar instance from the mobile drawer instance (both render the health bar)
- Added `navigateToUploadForm()` helper that clicks "Upload New File" when existing routes are loaded, since the dashboard loads pre-existing routes on mount and hides the upload form

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Rebuilt dashboard Docker image to include Plan 03 error UI components**
- **Found during:** Task 1 (initial test run)
- **Issue:** The Docker-served dashboard bundle was stale (built before Plan 03 commits), so ErrorBanner with data-testid attributes was not rendered
- **Fix:** Rebuilt dashboard-build Docker image, recreated dashboard_assets volume, restarted API container
- **Files modified:** None (Docker volume refresh only)
- **Verification:** Tests pass against updated dashboard build
- **Committed in:** d72a81a (Task 1 commit)

**2. [Rule 1 - Bug] Added force:true to DaisyUI collapse toggle clicks**
- **Found during:** Task 1 (test run attempt 4)
- **Issue:** Playwright could not click the "Show details" toggle button because DaisyUI's collapse checkbox intercepted pointer events
- **Fix:** Added `{ force: true }` to all detailToggle.click() calls
- **Files modified:** e2e/dashboard-errors.spec.ts
- **Verification:** Toggle interaction test passes
- **Committed in:** d72a81a (Task 1 commit)

**3. [Rule 1 - Bug] Scoped health bar selector to desktop sidebar**
- **Found during:** Task 1 (test run attempt 5)
- **Issue:** `[data-testid="health-status-bar"]` resolved to 2 elements (desktop sidebar + mobile drawer), causing strict mode violation
- **Fix:** Changed selector to `aside.app-sidebar [data-testid="health-status-bar"]`
- **Files modified:** e2e/dashboard-errors.spec.ts
- **Verification:** Health bar test passes
- **Committed in:** d72a81a (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 blocking)
**Impact on plan:** All fixes were necessary for test execution. No scope creep.

## Issues Encountered
- Dashboard Docker volume contained stale bundle from before Plan 03 -- resolved by rebuilding dashboard-build and recreating the shared volume
- DaisyUI collapse component uses a hidden checkbox that intercepts click events on nested buttons -- resolved with Playwright's force:true option

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All Phase 02 error handling infrastructure is complete (Plans 01-04)
- Error UI has full E2E test coverage for regression detection
- Phase can be marked complete in ROADMAP.md

## Self-Check: PASSED

- [x] e2e/dashboard-errors.spec.ts exists: FOUND
- [x] playwright.config.ts modified: FOUND
- [x] Task 1 commit d72a81a: FOUND
- [x] Test count: 7 test cases (meets 6+ requirement)
- [x] Line count: 319 lines (meets 100+ minimum)
- [x] All 7 Playwright tests pass

---
*Phase: 02-error-handling-infrastructure*
*Completed: 2026-03-10*
