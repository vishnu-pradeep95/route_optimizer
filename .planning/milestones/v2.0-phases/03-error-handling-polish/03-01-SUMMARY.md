---
phase: 03-error-handling-polish
plan: 01
subsystem: api, ui
tags: [fetch, health-check, error-urls, documentation-links]

# Dependency graph
requires:
  - phase: 02-error-handling-infrastructure
    provides: ErrorResponse model, ERROR_HELP_URLS mapping, fetchHealth function
provides:
  - fetchHealth that preserves 503 per-service JSON body
  - All 15 ERROR_HELP_URLS anchors corrected to match actual doc headings
  - Python/TypeScript ERROR_HELP_URLS in verified sync
affects: [dashboard-health-bar, error-detail-help-links]

# Tech tracking
tech-stack:
  added: []
  patterns: [direct-fetch-for-non-error-status-codes]

key-files:
  created: []
  modified:
    - apps/kerala_delivery/dashboard/src/lib/api.ts
    - apps/kerala_delivery/api/errors.py
    - apps/kerala_delivery/dashboard/src/lib/errors.ts

key-decisions:
  - "Use direct fetch() instead of apiFetch() for /health endpoint to preserve 503 JSON body with per-service data"
  - "FLEET_NO_VEHICLES mapped to #step-11-cdcms-data-workflow as closest available heading (SETUP.md has no Fleet Setup section)"

patterns-established:
  - "Direct fetch for endpoints that return valid JSON on non-2xx: bypass apiFetch which throws on non-ok"

requirements-completed: [ERR-01, ERR-05, ERR-09]

# Metrics
duration: 2min
completed: 2026-03-10
---

# Phase 03 Plan 01: Error Handling Polish Summary

**Fixed fetchHealth 503 body discard and repaired all 15 ERROR_HELP_URLS broken anchor fragments in both Python and TypeScript**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-10T03:00:44Z
- **Completed:** 2026-03-10T03:02:33Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- fetchHealth now uses direct fetch() so App.tsx receives per-service health breakdown on degraded/unhealthy (503) states
- All 15 ERROR_HELP_URLS entries in errors.py updated with correct doc heading anchors
- All 15 ERROR_HELP_URLS entries in errors.ts updated identically, verified in sync with Python
- Closes 2 integration gaps (14/16 -> 16/16) and 1 degraded E2E flow (4/5 -> 5/5) from milestone audit

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix fetchHealth to preserve 503 per-service data** - `980ec45` (fix)
2. **Task 2: Repair all 15 ERROR_HELP_URLS anchor fragments** - `3839458` (fix)

## Files Created/Modified
- `apps/kerala_delivery/dashboard/src/lib/api.ts` - fetchHealth now uses direct fetch() with cache: "no-store" instead of apiFetch
- `apps/kerala_delivery/api/errors.py` - All 15 ERROR_HELP_URLS anchors corrected to match actual markdown headings
- `apps/kerala_delivery/dashboard/src/lib/errors.ts` - All 15 ERROR_HELP_URLS anchors mirrored from Python, verified in sync

## Decisions Made
- Used direct fetch() for /health only; all other endpoints correctly use apiFetch which throws on non-2xx
- FLEET_NO_VEHICLES pointed to #step-11-cdcms-data-workflow as the closest relevant heading in SETUP.md
- SERVICE_UNAVAILABLE uses #troubleshooting-1 (second Troubleshooting heading in SETUP.md, auto-suffixed by markdown renderers)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 16 integration gaps from the v1.0 milestone audit are now closed
- All 5 E2E flows pass without degraded paths
- Ready for any additional polish tasks in phase 03

## Self-Check: PASSED

- All 3 modified files exist on disk
- Commit 980ec45 (Task 1) verified in git log
- Commit 3839458 (Task 2) verified in git log
- TypeScript compiles with no errors
- All 35 pytest tests pass (test_errors.py + test_health.py)
- Python/TypeScript ERROR_HELP_URLS verified in sync (15/15 entries match)

---
*Phase: 03-error-handling-polish*
*Completed: 2026-03-10*
