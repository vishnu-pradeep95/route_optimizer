---
phase: 06-build-pipeline
plan: 02
subsystem: auth
tags: [hmac, pbkdf2, license-key, security, migration]

# Dependency graph
requires:
  - phase: 05-fingerprinting-overhaul
    provides: "New fingerprint formula (machine-id + CPU model)"
provides:
  - "Rotated HMAC seed (32-byte cryptographic random)"
  - "Rotated PBKDF2 salt (16-byte cryptographic random)"
  - "Increased PBKDF2 iterations to 200,000"
  - "Clean __init__.py stub (no security-sensitive references)"
  - "Customer migration procedure (docs/MIGRATION.md)"
affects: [06-build-pipeline, 07-enforcement, 10-migration]

# Tech tracking
tech-stack:
  added: []
  patterns: ["bytes.fromhex() for non-greppable secrets", "named _PBKDF2_SALT constant"]

key-files:
  created: [docs/MIGRATION.md]
  modified: [core/licensing/license_manager.py, core/licensing/__init__.py, tests/core/licensing/test_license_manager.py]

key-decisions:
  - "HMAC seed as bytes.fromhex() -- not greppable, not human-readable"
  - "PBKDF2 iterations doubled to 200k for stronger key derivation"
  - "Migration docs written in Phase 6 while context is fresh (execution in Phase 10)"

patterns-established:
  - "Cryptographic secrets stored as bytes.fromhex() literals, not string constants"
  - "Regression tests for security credential rotation (old values must not validate)"

requirements-completed: [ENF-04]

# Metrics
duration: 5min
completed: 2026-03-10
---

# Phase 6 Plan 02: HMAC Credential Rotation Summary

**Rotated HMAC seed/salt/iterations, cleaned __init__.py stub, documented v2.1 customer migration procedure**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-10T22:31:23Z
- **Completed:** 2026-03-10T22:36:14Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Replaced human-readable HMAC seed with 32-byte cryptographic random (not greppable)
- Replaced inline salt with 16-byte cryptographic random, extracted to named constant
- Increased PBKDF2 iterations from 100,000 to 200,000
- Cleaned __init__.py of all HMAC/pyc/obscurity references (will be plaintext in distribution)
- Added regression test confirming old seed produces incompatible HMAC key
- Documented complete v2.1 migration procedure covering both breaking changes

## Task Commits

Each task was committed atomically:

1. **Task 1: Rotate HMAC seed, salt, and iterations** - `99fbe23` (feat)
2. **Task 2: Regenerate test fixtures and clean __init__.py** - `24d1fa6` (test)
3. **Task 3: Write customer migration procedure** - `66d7a58` (docs)

## Files Created/Modified
- `core/licensing/license_manager.py` - Rotated all three HMAC derivation parameters, stripped verbose comments
- `core/licensing/__init__.py` - Clean docstring stub with no security-sensitive references
- `tests/core/licensing/test_license_manager.py` - Added TestHMACSeedRotation regression test class
- `docs/MIGRATION.md` - Complete v2.1 customer migration procedure

## Decisions Made
- Used `bytes.fromhex()` for seed/salt storage instead of byte string literals -- hex values are not greppable as ASCII strings, raising the bar for casual extraction
- PBKDF2 iterations doubled to 200,000 (from 100,000) -- meaningful increase in brute-force cost with negligible startup-time impact
- Migration documentation written now in Phase 6 while both breaking changes are fresh context, actual migration execution deferred to Phase 10

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all 39 licensing tests passed immediately after HMAC rotation (fixtures are dynamic via encode_license_key()). Full test suite (493 tests) also passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- HMAC credentials rotated and ready for Cython compilation (Plan 03)
- __init__.py clean and ready to serve as plaintext stub in distribution
- generate_license.py untouched -- automatically uses new HMAC key via import
- Migration procedure documented for Phase 10 execution

## Self-Check: PASSED

All 4 created/modified files verified on disk. All 3 task commits verified in git log.

---
*Phase: 06-build-pipeline*
*Completed: 2026-03-10*
