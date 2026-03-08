---
phase: 22-ci-cd-pipeline-integration
plan: 01
subsystem: testing
tags: [pytest, async-mocking, ci, fastapi, sqlalchemy]

# Dependency graph
requires:
  - phase: 21-playwright-e2e-test-suite
    provides: "38 E2E tests and 362 passing pytest tests (64 pre-existing failures)"
provides:
  - "All 426 pytest tests passing with zero failures"
  - "Proper AsyncMock vehicle mocking pattern for upload endpoint tests"
  - "API_KEY env leak prevention in cross-module test execution"
affects: [22-02-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mock get_active_vehicles with non-empty list + vehicle_db_to_pydantic returning Vehicle objects"
    - "Clear API_KEY in client fixture to prevent load_dotenv leakage from script modules"

key-files:
  created: []
  modified:
    - tests/apps/kerala_delivery/api/test_api.py
    - tests/test_e2e_pipeline.py
    - .github/workflows/ci.yml

key-decisions:
  - "Fixed vehicle mock pattern: return [MagicMock()] from get_active_vehicles + configure vehicle_db_to_pydantic to return proper Vehicle objects"
  - "Cleared API_KEY in e2e pipeline client fixture to prevent env leakage from scripts/import_orders.py load_dotenv()"

patterns-established:
  - "Vehicle mock pattern: upload tests must provide mock vehicles since API enforces non-empty fleet"
  - "Env isolation pattern: test client fixtures must clear API_KEY to prevent cross-module dotenv leakage"

requirements-completed: [CICD-01]

# Metrics
duration: 10min
completed: 2026-03-08
---

# Phase 22 Plan 01: Fix Pytest Failures Summary

**Fixed all 12 remaining pytest failures via proper vehicle mocking and API_KEY env isolation -- 426 tests now pass green**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-08T21:33:25Z
- **Completed:** 2026-03-08T21:43:31Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- All 426 pytest tests pass with 0 failures, 0 errors
- No xfail or skip markers used -- all tests genuinely pass
- CI YAML comments updated from "211+ tests" to "420+ tests"
- Fixed cross-module API_KEY environment leakage from load_dotenv in script modules

## Task Commits

Each task was committed atomically:

1. **Task 1: Diagnose and fix all pytest failures** - `f599eb0` (fix)
2. **Task 2: Update CI YAML comments** - `b59ab60` (chore)

## Files Created/Modified
- `tests/apps/kerala_delivery/api/test_api.py` - Fixed 7 upload tests: proper vehicle mocking (get_active_vehicles returns non-empty list, vehicle_db_to_pydantic returns Vehicle objects), imported Vehicle model
- `tests/test_e2e_pipeline.py` - Fixed 5 tests: proper 2-vehicle fleet mocking, API_KEY env isolation in client fixture
- `.github/workflows/ci.yml` - Updated header comment from "211+ tests" to "420+ tests"

## Decisions Made
- **Vehicle mock pattern:** The upload endpoint now requires active vehicles (raises 400 if fleet is empty). Tests previously mocked `get_active_vehicles` with `[]`. Fixed by returning `[MagicMock()]` and configuring `vehicle_db_to_pydantic` to return proper `Vehicle` Pydantic objects with valid attributes.
- **API_KEY env isolation:** `scripts/import_orders.py` calls `load_dotenv()` at module level, which sets `API_KEY` from `.env` into `os.environ`. When `test_import_orders.py` runs before `test_e2e_pipeline.py`, the API_KEY persists and causes 401 errors in e2e tests. Fixed by adding `"API_KEY": ""` to the e2e pipeline client fixture's `patch.dict`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Actual failure count was 12, not 64**
- **Found during:** Task 1 (diagnosis)
- **Issue:** The plan referenced 64 failures (from Phase 21 context), but the actual count at execution time was 12. Previous phases likely fixed some failures as side effects.
- **Fix:** Diagnosed and fixed all 12 actual failures instead of 64
- **Verification:** `python -m pytest tests/ -q --tb=short` exits with 0, 426 passed

**2. [Rule 1 - Bug] Cross-module environment leakage from load_dotenv**
- **Found during:** Task 1 (diagnosing full-suite-only failures)
- **Issue:** 3 tests passed in isolation but failed in full suite due to `API_KEY` being set by `scripts/import_orders.py`'s `load_dotenv()` call, which persists in `os.environ` across test modules
- **Fix:** Added `"API_KEY": ""` to e2e pipeline client fixture's `patch.dict`
- **Files modified:** `tests/test_e2e_pipeline.py`
- **Committed in:** f599eb0

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
- The plan estimated 64 pre-existing failures, but only 12 remained at execution time. The root causes were: (1) empty vehicle list mock causing 400 errors (9 tests), and (2) load_dotenv environment leakage causing 401 errors (3 tests in full suite only).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 426 pytest tests pass green, CI Python Tests job is ready
- Plan 22-02 can proceed to add the Playwright E2E job, failure artifacts, and CI badge

---
## Self-Check: PASSED

- All files exist (test_api.py, test_e2e_pipeline.py, ci.yml, SUMMARY.md)
- All commits verified (f599eb0, b59ab60)
- 426/426 tests pass

*Phase: 22-ci-cd-pipeline-integration*
*Completed: 2026-03-08*
