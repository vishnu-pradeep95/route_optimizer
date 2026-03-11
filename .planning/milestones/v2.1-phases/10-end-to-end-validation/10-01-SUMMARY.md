---
phase: 10-end-to-end-validation
plan: 01
subsystem: testing
tags: [playwright, docker, e2e, security-pipeline, license, integrity, revalidation, renewal, fingerprint]

# Dependency graph
requires:
  - phase: 05-machine-fingerprinting
    provides: fingerprint formula (machine-id + CPU model)
  - phase: 07-integrity-enforcement
    provides: _INTEGRITY_MANIFEST, verify_integrity(), enforcement middleware
  - phase: 08-periodic-revalidation
    provides: maybe_revalidate() counter mechanism, set_license_state() one-way guard
  - phase: 09-license-management
    provides: renewal.key file drop, X-License-Expires-In header, /health license section
provides:
  - E2E security pipeline test suite (e2e/security-pipeline.spec.ts) with 4 scenarios
  - Configurable REVALIDATION_INTERVAL env var (default 500, override for tests)
  - Docker Compose services for security testing (api-security-test on 8002, api-fingerprint-test on 8003)
  - CI job e2e-security gated to push-to-main
affects: [ci, docker-compose, licensing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "REVALIDATION_INTERVAL env var override for test-time fast cycling"
    - "Docker Compose service per test scenario with env var-based license key injection"
    - "test.describe.serial() for container lifecycle test stories"
    - "test.skip() for production-build-only tests (integrity tamper)"

key-files:
  created:
    - e2e/security-pipeline.spec.ts
  modified:
    - core/licensing/license_manager.py
    - docker-compose.license-test.yml
    - playwright.config.ts
    - .github/workflows/ci.yml

key-decisions:
  - "REVALIDATION_INTERVAL as module-level constant read at import time (works in both .py and .so)"
  - "Integrity tamper test gracefully skips in dev mode via test.skip() (empty _INTEGRITY_MANIFEST)"
  - "Separate CI job e2e-security instead of extending existing e2e job (different Docker lifecycle needs)"
  - "License keys generated dynamically in beforeAll via generate_license.py (works on any machine)"

patterns-established:
  - "Docker Compose override per test scenario with env var license key injection"
  - "Graceful test.skip() for production-build-only scenarios with clear message"
  - "waitForContainer polling helper reused across all security test scenarios"

requirements-completed: [DOC-01]

# Metrics
duration: 3min
completed: 2026-03-11
---

# Phase 10 Plan 01: Security Pipeline E2E Tests Summary

**Playwright E2E tests for 4 security scenarios (fingerprint mismatch, re-validation, integrity tamper, renewal lifecycle) with Docker Compose isolation and CI gating**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-11T11:15:44Z
- **Completed:** 2026-03-11T11:19:05Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Configurable REVALIDATION_INTERVAL env var replaces hardcoded 500 in maybe_revalidate()
- 415-line E2E test suite covering all 4 DOC-01 security scenarios with isolated Docker containers
- CI job e2e-security runs security tests separately on push to main, after test+docker jobs pass
- Docker Compose extended with api-security-test (port 8002) and api-fingerprint-test (port 8003) services

## Task Commits

Each task was committed atomically:

1. **Task 1: Add REVALIDATION_INTERVAL env var + Docker Compose security test services + Playwright config** - `68b0d97` (feat)
2. **Task 2: Create security-pipeline.spec.ts with 4 E2E scenarios + CI job** - `2114381` (feat)

## Files Created/Modified
- `core/licensing/license_manager.py` - Added _REVALIDATION_INTERVAL env var (default 500), used in maybe_revalidate()
- `docker-compose.license-test.yml` - Added api-security-test (port 8002, REVALIDATION_INTERVAL=10) and api-fingerprint-test (port 8003) services
- `playwright.config.ts` - Added security-pipeline project entry
- `e2e/security-pipeline.spec.ts` - 4 E2E test scenarios: fingerprint mismatch, re-validation, integrity tamper, renewal lifecycle
- `.github/workflows/ci.yml` - Added e2e-security CI job gated to push-to-main

## Decisions Made
- **REVALIDATION_INTERVAL as module-level constant:** Read from env var at import time via `int(os.environ.get("REVALIDATION_INTERVAL", "500"))`. Works identically in .py and .so because Python evaluates module-level constants at import time regardless of format.
- **Integrity tamper test uses test.skip() in dev mode:** The _INTEGRITY_MANIFEST is empty in dev builds (no files to check). Test detects this by checking for .so files in the container and skips with a clear message. Full validation requires a production build via build-dist.sh.
- **Separate e2e-security CI job:** Security tests start/stop multiple Docker containers with different license configurations, making them incompatible with the existing e2e job's shared compose stack. Separate job also prevents security test failures from blocking regular E2E results.
- **Dynamic license key generation in beforeAll:** Keys generated via `python3 scripts/generate_license.py --this-machine` and Python inline scripts. This ensures tests work on any machine (CI or local) because keys are bound to the current machine's fingerprint.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- E2E security tests ready to run locally (`npx playwright test --project=security-pipeline --workers=1`)
- Requires Docker Compose db service running and healthy
- Integrity tamper test (Scenario 3) will only fully exercise on production builds
- Plan 02 (documentation) can proceed independently

## Self-Check: PASSED

All files exist, all commits verified.

---
*Phase: 10-end-to-end-validation*
*Completed: 2026-03-11*
