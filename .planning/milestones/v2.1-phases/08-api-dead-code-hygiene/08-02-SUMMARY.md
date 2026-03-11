---
phase: 08-api-dead-code-hygiene
plan: 02
subsystem: licensing
tags: [tdd, middleware, revalidation, enforcement, security, runtime-protection]

# Dependency graph
requires:
  - phase: 08-api-dead-code-hygiene
    plan: 01
    provides: "maybe_revalidate(), _request_counter, set_license_state() one-way guard, _STATUS_SEVERITY"
provides:
  - "Enforcement middleware calls maybe_revalidate() on every request when license state is set"
  - "Middleware re-reads get_license_status() after maybe_revalidate() to detect state transitions"
  - "SystemExit from maybe_revalidate() propagates through middleware for graceful shutdown"
  - "TestRuntimeRevalidation test class (8 tests) covering middleware integration"
affects: [runtime-protection-complete, distribution-builds]

# Tech tracking
tech-stack:
  added: []
  patterns: ["maybe_revalidate() called synchronously from async middleware", "status re-read after revalidation for same-request state reflection"]

key-files:
  created: []
  modified:
    - core/licensing/enforcement.py
    - tests/core/licensing/test_enforcement.py

key-decisions:
  - "maybe_revalidate() not wrapped in try/except -- SystemExit must propagate for graceful shutdown"
  - "maybe_revalidate() called for ALL requests including /health -- counter should increment consistently"
  - "Status re-read placed immediately after maybe_revalidate(), before any branching logic"
  - "SystemExit test uses BaseExceptionGroup catch for Starlette/anyio compatibility"

patterns-established:
  - "Sync-from-async middleware pattern: synchronous maybe_revalidate() called from async middleware (sub-ms execution)"
  - "Status re-read pattern: get_license_status() called twice -- before and after maybe_revalidate()"

requirements-completed: [RTP-02, RTP-03]

# Metrics
duration: 3min
completed: 2026-03-11
---

# Phase 8 Plan 02: Middleware Revalidation Wiring Summary

**Enforcement middleware now calls maybe_revalidate() on every request with active license, re-reads status to reflect runtime state transitions in the same request**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-11T01:53:39Z
- **Completed:** 2026-03-11T01:56:52Z
- **Tasks:** 1 (TDD, 2 commits: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- Wired maybe_revalidate() into enforcement middleware -- completes the runtime protection circuit started in Plan 01
- Middleware re-reads get_license_status() after revalidation so VALID->GRACE or GRACE->INVALID transitions take effect on the same request
- 8 new TestRuntimeRevalidation tests covering call/no-call, status re-read, degradation headers, 503 on INVALID, SystemExit propagation, and health bypass
- Full test suite: 92 licensing tests, 548 total tests, all green

## Task Commits

Each task was committed atomically (TDD RED + GREEN):

1. **Task 1 RED: TestRuntimeRevalidation failing tests** - `cf0b429` (test)
2. **Task 1 GREEN: Wire maybe_revalidate() into middleware** - `cecd29f` (feat)

## Files Created/Modified
- `core/licensing/enforcement.py` - Added maybe_revalidate import, added revalidation call and status re-read to middleware
- `tests/core/licensing/test_enforcement.py` - Added TestRuntimeRevalidation class (8 tests) with request counter reset fixture

## Decisions Made
- maybe_revalidate() is NOT wrapped in try/except -- SystemExit must propagate unhindered for graceful shutdown on integrity failure
- maybe_revalidate() is called for ALL requests including /health -- the counter should increment on every request for consistent revalidation cadence; the health endpoint bypass happens AFTER revalidation
- Status re-read is placed immediately after maybe_revalidate() and before the None check, so state degradation during revalidation is reflected in the same request's response
- SystemExit propagation test catches BaseExceptionGroup as Starlette/anyio wraps SystemExit in exception groups during async processing

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Runtime protection circuit is now complete: Plan 01 built maybe_revalidate(), Plan 02 wired it into the middleware
- Every 500th request triggers integrity manifest verification + license expiry re-check
- State guard prevents INVALID->VALID upgrades without restart
- Phase 8 is complete -- ready for next phase (distribution/packaging)

## Self-Check: PASSED

All files verified present, all 2 commits found in git log.

---
*Phase: 08-api-dead-code-hygiene*
*Completed: 2026-03-11*
