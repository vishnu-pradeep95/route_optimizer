---
phase: 08-api-dead-code-hygiene
plan: 01
subsystem: licensing
tags: [tdd, state-guard, revalidation, integrity, license-expiry, security]

# Dependency graph
requires:
  - phase: 07-enforcement-module
    provides: "set_license_state(), get_license_status(), verify_integrity(), _INTEGRITY_MANIFEST, _license_state"
provides:
  - "maybe_revalidate() function for periodic runtime re-validation (every 500 requests)"
  - "_STATUS_SEVERITY mapping and one-way state transition guard in set_license_state()"
  - "_request_counter module-level state for re-validation trigger"
  - "TestStateGuard (9 tests) and TestMaybeRevalidate (12 tests) test classes"
affects: [08-02, enforcement-middleware-integration, runtime-protection]

# Tech tracking
tech-stack:
  added: []
  patterns: ["one-way state machine with severity ordering", "counter-based periodic re-validation", "dataclasses.replace() for immutable state updates"]

key-files:
  created: []
  modified:
    - core/licensing/license_manager.py
    - tests/core/licensing/test_license_manager.py
    - core/licensing/__init__.py

key-decisions:
  - "Counter resets to 0 after re-validation (not to 1), so next cycle is exactly 500 requests"
  - "Dev mode skip uses empty _INTEGRITY_MANIFEST check (same pattern as verify_integrity and enforce)"
  - "License expiry boundary logic copies exactly from decode_license_key() for consistency"
  - "dataclasses.replace() preserves customer_id, fingerprint, expires_at when transitioning state"

patterns-established:
  - "One-way state guard: _STATUS_SEVERITY dict maps LicenseStatus to severity int, guard rejects upgrades"
  - "Counter-based re-validation: module-level _request_counter, modulo check, reset after fire"

requirements-completed: [RTP-02, RTP-03]

# Metrics
duration: 4min
completed: 2026-03-11
---

# Phase 8 Plan 01: Runtime Re-validation Summary

**Periodic re-validation with request counter (every 500 calls) checking integrity manifest + license expiry, plus one-way state transition guard preventing accidental state upgrades**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-11T01:47:18Z
- **Completed:** 2026-03-11T01:51:05Z
- **Tasks:** 2 (TDD, 4 commits total: 2 RED + 2 GREEN)
- **Files modified:** 3

## Accomplishments
- One-way state transition guard in set_license_state() with _STATUS_SEVERITY mapping -- prevents INVALID->VALID or GRACE->VALID upgrades without restart
- maybe_revalidate() function with _request_counter triggering every 500 calls -- integrity manifest verification + license expiry re-check
- 21 new tests (9 TestStateGuard + 12 TestMaybeRevalidate), 84 total licensing tests all green

## Task Commits

Each task was committed atomically (TDD RED + GREEN):

1. **Task 1 RED: TestStateGuard failing tests** - `bfadee3` (test)
2. **Task 1 GREEN: State transition guard** - `91fb5b3` (feat)
3. **Task 2 RED: TestMaybeRevalidate failing tests** - `7bec3c1` (test)
4. **Task 2 GREEN: maybe_revalidate() implementation** - `cc39910` (feat)

## Files Created/Modified
- `core/licensing/license_manager.py` - Added _STATUS_SEVERITY, state guard in set_license_state(), _request_counter, maybe_revalidate(), logging
- `tests/core/licensing/test_license_manager.py` - Added TestStateGuard (9 tests) and TestMaybeRevalidate (12 tests) classes
- `core/licensing/__init__.py` - Updated public API docs to include maybe_revalidate()

## Decisions Made
- Counter resets to 0 after re-validation fires (not to 1), ensuring exactly 500 requests between checks
- Dev mode skip uses the same `not _INTEGRITY_MANIFEST` pattern already established in verify_integrity() and enforce()
- License expiry boundary logic replicates decode_license_key() exactly (days_remaining >= 0 = VALID, abs <= GRACE_PERIOD_DAYS+1 = GRACE, else INVALID)
- dataclasses.replace() used for state transitions to preserve immutable fields (customer_id, fingerprint, expires_at)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- maybe_revalidate() is ready to be wired into enforcement middleware (Phase 8 Plan 2)
- State guard is already active -- set_license_state() calls from enforce() at startup still work (None check first)
- All 84 licensing tests pass with zero regression

## Self-Check: PASSED

All files verified present, all 4 commits found in git log.

---
*Phase: 08-api-dead-code-hygiene*
*Completed: 2026-03-11*
