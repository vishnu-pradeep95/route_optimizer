---
phase: 02-error-handling-infrastructure
plan: 03
subsystem: ui
tags: [react, typescript, daisyui, tailwind-v4, error-handling, error-ui, health-status]

# Dependency graph
requires:
  - phase: 02-01
    provides: ErrorResponse Pydantic model, ErrorCode enum, error_response() helper, ERROR_HELP_URLS mapping
  - phase: 02-02
    provides: Enhanced /health endpoint with per-service status and overall healthy/degraded/unhealthy
provides:
  - errors.ts with ApiError interface, classifyError(), isApiError(), ERROR_HELP_URLS client-side mapping
  - ErrorBanner component with severity color-coding, retry button, help link, auto-dismiss via health polling
  - ErrorDetail collapsible panel showing error_code, request_id, timestamp
  - ErrorTable inline failure table with download report and re-upload actions
  - api.ts typed ApiError parsing in apiFetch/apiWrite/uploadAndOptimize
  - ApiUploadError class extending Error for upload-specific error handling
  - Expanded HealthResponse type with per-service ServiceStatus
  - Per-service health status bar in App.tsx sidebar
  - All pages using ErrorBanner for structured API error display
affects: [02-04, dashboard-e2e-tests, error-ui-playwright]

# Tech tracking
tech-stack:
  added: []
  patterns: [typed-api-error-parsing, error-banner-auto-recover, per-service-health-display]

key-files:
  created:
    - apps/kerala_delivery/dashboard/src/lib/errors.ts
    - apps/kerala_delivery/dashboard/src/components/ErrorBanner.tsx
    - apps/kerala_delivery/dashboard/src/components/ErrorDetail.tsx
    - apps/kerala_delivery/dashboard/src/components/ErrorTable.tsx
  modified:
    - apps/kerala_delivery/dashboard/src/lib/api.ts
    - apps/kerala_delivery/dashboard/src/types.ts
    - apps/kerala_delivery/dashboard/src/pages/UploadRoutes.tsx
    - apps/kerala_delivery/dashboard/src/pages/LiveMap.tsx
    - apps/kerala_delivery/dashboard/src/pages/FleetManagement.tsx
    - apps/kerala_delivery/dashboard/src/pages/RunHistory.tsx
    - apps/kerala_delivery/dashboard/src/App.tsx

key-decisions:
  - "DaisyUI collapse used for ErrorDetail toggle (keeps error context visible vs modal)"
  - "Auto-dismiss uses 5-second debounce on health check to prevent flicker"
  - "ErrorTable caps display at 50 rows with truncation message for large failure sets"
  - "ApiUploadError class extends Error for instanceof checking in upload-specific catch blocks"
  - "Synthetic ApiError objects created for client-side validation errors to maintain consistent error shape"

patterns-established:
  - "All API errors flow through isApiError() type guard before rendering"
  - "Pages use typed ApiError | null state instead of string error messages"
  - "ErrorBanner accepts autoRecover prop for network-error pages (LiveMap)"
  - "data-testid attributes on all error UI elements for Playwright E2E testing"

requirements-completed: [ERR-07, ERR-08, ERR-09]

# Metrics
duration: 9min
completed: 2026-03-10
---

# Phase 02 Plan 03: Frontend Error UI Summary

**ErrorBanner with severity color-coding and auto-dismiss, ErrorTable with download/re-upload actions, ErrorDetail collapse, typed ApiError parsing in api.ts, and per-service health status bar in sidebar**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-10T01:51:06Z
- **Completed:** 2026-03-10T02:00:46Z
- **Tasks:** 3 (2 auto + 1 checkpoint auto-approved)
- **Files modified:** 11

## Accomplishments
- Created errors.ts with ApiError interface, ErrorSeverity type, classifyError(), isApiError(), ERROR_HELP_URLS mapping
- Built ErrorBanner with DaisyUI alert components, severity color-coding (red/amber/blue), retry button, help link, auto-dismiss with 5-second health poll debounce
- Built ErrorDetail with DaisyUI collapse showing error_code, request_id, timestamp, technical_message
- Built ErrorTable with color-coded rows (validation=red, geocoding=amber), 50-row cap, download CSV and re-upload buttons
- Updated api.ts: apiFetch/apiWrite parse ErrorResponse JSON and throw typed ApiError; uploadAndOptimize throws ApiUploadError
- Expanded HealthResponse in types.ts with ServiceStatus and per-service breakdown
- Integrated ErrorBanner into all 4 dashboard pages replacing plain string error messages
- Added ErrorTable to UploadRoutes ImportSummary for CSV failure display
- Added per-service health indicators (PG, OSRM, VROOM, Google) to App.tsx sidebar
- All error UI components have data-testid attributes for Playwright E2E testing
- Dashboard builds with zero TypeScript errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Create error types, error UI components, and update api.ts** - `a81b9a3` (feat)
2. **Task 2: Integrate error components into all dashboard pages and App.tsx health bar** - `4146b80` (feat)
3. **Task 3: Verify error UI components** - auto-approved (checkpoint:human-verify in auto mode)

## Files Created/Modified
- `apps/kerala_delivery/dashboard/src/lib/errors.ts` - ApiError interface, ErrorSeverity, classifyError(), isApiError(), ERROR_HELP_URLS
- `apps/kerala_delivery/dashboard/src/components/ErrorBanner.tsx` - Contextual error banner with severity, retry, help link, auto-dismiss
- `apps/kerala_delivery/dashboard/src/components/ErrorDetail.tsx` - Collapsible technical details (error_code, request_id, timestamp)
- `apps/kerala_delivery/dashboard/src/components/ErrorTable.tsx` - Inline CSV failure table with download report and re-upload actions
- `apps/kerala_delivery/dashboard/src/lib/api.ts` - Typed ApiError parsing in apiFetch/apiWrite/uploadAndOptimize, ApiUploadError class
- `apps/kerala_delivery/dashboard/src/types.ts` - Expanded HealthResponse with ServiceStatus and per-service breakdown
- `apps/kerala_delivery/dashboard/src/pages/UploadRoutes.tsx` - ErrorBanner for upload errors, ErrorTable in ImportSummary
- `apps/kerala_delivery/dashboard/src/pages/LiveMap.tsx` - ErrorBanner with autoRecover for route data errors
- `apps/kerala_delivery/dashboard/src/pages/FleetManagement.tsx` - ErrorBanner for fleet CRUD errors
- `apps/kerala_delivery/dashboard/src/pages/RunHistory.tsx` - ErrorBanner for run history fetch errors
- `apps/kerala_delivery/dashboard/src/App.tsx` - Per-service health status indicators in sidebar

## Decisions Made
- Used DaisyUI collapse for ErrorDetail toggle (keeps error context visible, consistent with existing ImportSummary pattern)
- Auto-dismiss uses 5-second debounce on health polling to prevent flicker on intermittent connectivity
- ErrorTable caps display at 50 rows with "... and N more" message for performance with large failure sets
- Created ApiUploadError class extending Error so pages can use instanceof checks for upload-specific error handling
- Synthetic ApiError objects created for client-side validation errors (file type, file size) to maintain consistent error shape across all error sources
- Removed unused AlertTriangle import from UploadRoutes.tsx after replacing inline error banner

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused AlertTriangle import from UploadRoutes.tsx**
- **Found during:** Task 2 (build verification)
- **Issue:** After replacing the inline error banner with ErrorBanner, the AlertTriangle import was unused, causing TypeScript error TS6133
- **Fix:** Removed AlertTriangle from the lucide-react import
- **Files modified:** apps/kerala_delivery/dashboard/src/pages/UploadRoutes.tsx
- **Verification:** Dashboard builds successfully
- **Committed in:** 4146b80 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Trivial cleanup. No scope creep.

## Issues Encountered
- TypeScript compiler (tsc) not available via npx -- resolved by running npm install to install devDependencies locally

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All error UI components ready for Playwright E2E testing (Plan 04)
- data-testid attributes on all error elements for test selectors
- ErrorBanner auto-dismiss mechanism ready for integration testing
- Per-service health display ready for visual verification

## Self-Check: PASSED

- [x] errors.ts exists: FOUND
- [x] ErrorBanner.tsx exists: FOUND
- [x] ErrorDetail.tsx exists: FOUND
- [x] ErrorTable.tsx exists: FOUND
- [x] Task 1 commit a81b9a3: FOUND
- [x] Task 2 commit 4146b80: FOUND
- [x] Dashboard builds with zero errors: PASSED

---
*Phase: 02-error-handling-infrastructure*
*Completed: 2026-03-10*
