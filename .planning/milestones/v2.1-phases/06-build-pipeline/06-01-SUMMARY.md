---
phase: 06-build-pipeline
plan: 01
subsystem: api
tags: [fastapi, security, environment, production-default]

# Dependency graph
requires:
  - phase: 05-fingerprint
    provides: "License validation infrastructure (validate_license, LicenseInfo)"
provides:
  - "Production-default ENVIRONMENT logic in main.py"
  - "Dev conveniences gated behind explicit ENVIRONMENT=development"
  - "Expanded test coverage for docs/redoc/openapi gating"
affects: [07-cython-compilation, 08-runtime-enforcement]

# Tech tracking
tech-stack:
  added: []
  patterns: [production-default-environment, explicit-dev-opt-in]

key-files:
  created: []
  modified:
    - apps/kerala_delivery/api/main.py
    - tests/apps/kerala_delivery/api/test_api.py

key-decisions:
  - "Set ENVIRONMENT=development at top of test file (os.environ.setdefault) rather than in pytest.ini or conftest -- keeps test environment requirements explicit and co-located with the test module"
  - "Used _is_dev_mode (module-level) and _lifespan_is_dev (lifespan-scoped) as separate variables to respect Python scoping -- module-level for FastAPI constructor args, lifespan-level for startup logic"

patterns-established:
  - "Production-default: ENVIRONMENT must be explicitly set to 'development' to enable dev conveniences"
  - "Test environment setup: os.environ.setdefault before importing modules with environment-dependent init"

requirements-completed: [ENF-01]

# Metrics
duration: 6min
completed: 2026-03-10
---

# Phase 6 Plan 1: ENVIRONMENT Production-Default Summary

**Inverted ENVIRONMENT logic so production is the default -- dev conveniences (Swagger /docs, /redoc, /openapi.json, permissive CORS, license bypass) only activate with explicit ENVIRONMENT=development**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-10T22:31:45Z
- **Completed:** 2026-03-10T22:37:51Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- All 4 ENVIRONMENT-dependent locations in main.py refactored to production-default logic
- /docs, /redoc, and /openapi.json all return 404 when ENVIRONMENT is not "development"
- HSTS enabled by default, permissive CORS disabled by default, license enforcement active by default
- Expanded test coverage: 2 new tests (docs gated when unset, docs enabled in dev mode)
- Full project test suite: 495 passed, 0 failed

## Task Commits

Each task was committed atomically:

1. **Task 1: Refactor main.py ENVIRONMENT checks to production-default** - `37fe58d` (feat)
2. **Task 2: Update test_docs_gated_in_production for inverted logic** - `02d2c5f` (test)

## Files Created/Modified
- `apps/kerala_delivery/api/main.py` - Replaced _env_name with _is_dev_mode (module-level) and _lifespan_is_dev (lifespan); inverted all 4 ENVIRONMENT checks; wired _redoc_url and _openapi_url into FastAPI constructor
- `tests/apps/kerala_delivery/api/test_api.py` - Set ENVIRONMENT=development before import; updated test_docs_gated_in_production; added test_docs_gated_when_environment_unset and test_docs_enabled_in_development

## Decisions Made
- Set ENVIRONMENT=development at top of test file via os.environ.setdefault rather than pytest.ini -- keeps the dependency explicit and co-located with the importing code
- Used separate _is_dev_mode (module-level) and _lifespan_is_dev (lifespan-scoped) variables because module-level code runs at import time while lifespan runs at startup -- both need independent checks

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added ENVIRONMENT=development to test file imports**
- **Found during:** Task 1 (ENVIRONMENT refactor)
- **Issue:** After inverting the default, the test file's top-level `from apps.kerala_delivery.api.main import app` triggered module-level code in production mode, causing test_cors_allows_listed_origin to fail (no dev CORS origins)
- **Fix:** Added `os.environ.setdefault("ENVIRONMENT", "development")` before the main import in the test file
- **Files modified:** tests/apps/kerala_delivery/api/test_api.py
- **Verification:** All 115 API tests pass
- **Committed in:** 37fe58d (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential fix for test infrastructure after inverting the production default. No scope creep.

## Issues Encountered
None -- plan executed as specified with one expected test infrastructure adjustment.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Security audit finding #1 (ENVIRONMENT=development bypass) is now closed
- main.py is ready for Cython compilation (Phase 6, Plan 2) -- the ENVIRONMENT logic is clean and self-contained
- All enforcement paths are production-default, reducing attack surface for distributed builds

## Self-Check: PASSED

All files exist, all commits verified.

---
*Phase: 06-build-pipeline*
*Completed: 2026-03-10*
