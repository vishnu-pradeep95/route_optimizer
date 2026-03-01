---
phase: 01-foundation
plan: 03
subsystem: infra, testing
tags: [tailwind, daisyui, pwa, pytest, asyncio, coordinate-migration]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: "Project structure, config.py with DEPOT_LOCATION"
provides:
  - "Tailwind CSS + DaisyUI standalone CLI build pipeline for PWA"
  - "Compiled tailwind.css for driver app PWA"
  - "build-pwa-css.sh repeatable build script"
  - "pytest.ini with asyncio_mode=auto"
  - "Vatakara-area test fixtures and coordinates across all 14 test files"
  - "Guard fixture verifying test depot matches production config"
affects: [phase-05-pwa-redesign, all-test-phases]

# Tech tracking
tech-stack:
  added: [tailwindcss-extra v4.2.1, daisyui 5.5.19]
  patterns: [prefix(tw) for CSS class isolation, autouse guard fixtures for config drift]

key-files:
  created:
    - tools/tailwindcss-extra (binary, gitignored)
    - apps/kerala_delivery/driver_app/pwa-input.css
    - apps/kerala_delivery/driver_app/tailwind.css
    - scripts/build-pwa-css.sh
    - pytest.ini
  modified:
    - .gitignore
    - apps/kerala_delivery/driver_app/index.html
    - tests/conftest.py
    - tests/apps/kerala_delivery/api/test_api.py
    - tests/apps/kerala_delivery/api/test_qr_helpers.py
    - tests/integration/test_osrm_vroom_pipeline.py
    - tests/test_e2e_pipeline.py
    - tests/scripts/test_geocode_batch.py
    - tests/scripts/test_import_orders.py
    - tests/core/geocoding/test_cache.py
    - tests/core/models/test_models.py
    - tests/core/data_import/test_csv_importer.py
    - tests/core/geocoding/test_google_adapter.py
    - tests/core/database/test_database.py
    - tests/core/optimizer/test_vroom_adapter.py
    - tests/core/routing/test_osrm_adapter.py

key-decisions:
  - "Used tailwind-cli-extra (not standard tailwindcss CLI) for bundled DaisyUI support"
  - "Added backward-compatible kochi_depot alias to prevent breakage during migration"
  - "Added autouse guard fixture to catch config/test depot drift"

patterns-established:
  - "PWA CSS build: scripts/build-pwa-css.sh compiles pwa-input.css to tailwind.css"
  - "Test coordinates: All tests use Vatakara-area landmarks (lat 11.5-11.7, lon 75.5-75.6)"
  - "Guard fixtures: autouse fixtures verify test data matches production config"

requirements-completed: [PWA-01, TEST-01, TEST-06]

# Metrics
duration: 6min
completed: 2026-03-01
---

# Phase 1 Plan 3: Tailwind PWA CSS Pipeline + Test Coordinate Migration Summary

**Tailwind standalone CLI with DaisyUI for PWA CSS, all 14 test files migrated from Kochi to Vatakara coordinates, pytest asyncio_mode=auto configured**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-01T14:43:20Z
- **Completed:** 2026-03-01T14:49:23Z
- **Tasks:** 2
- **Files modified:** 20

## Accomplishments
- Tailwind CSS + DaisyUI standalone build pipeline producing 10KB compiled CSS for driver PWA
- All 14 test files migrated from Kochi coordinates (lat 9.9x) to Vatakara (lat 11.5x-11.6x) matching production DEPOT_LOCATION
- pytest.ini with asyncio_mode=auto eliminates per-test @pytest.mark.asyncio boilerplate
- Autouse guard fixture prevents test/production coordinate drift
- Full 360-test suite passes with zero Kochi coordinates remaining

## Task Commits

Each task was committed atomically:

1. **Task 1: Set up Tailwind standalone CLI for PWA and create build pipeline** - `a91005f` (feat)
2. **Task 2: Migrate all test coordinates from Kochi to Vatakara and configure pytest asyncio** - `1bb96d1` (feat)

## Files Created/Modified
- `tools/tailwindcss-extra` - Standalone Tailwind CLI binary with DaisyUI (gitignored)
- `apps/kerala_delivery/driver_app/pwa-input.css` - Tailwind input CSS with prefix(tw) and DaisyUI plugin
- `apps/kerala_delivery/driver_app/tailwind.css` - Compiled 10KB static CSS for offline PWA
- `scripts/build-pwa-css.sh` - Repeatable build script for PWA CSS compilation
- `apps/kerala_delivery/driver_app/index.html` - Added tailwind.css link before inline styles
- `.gitignore` - Added tools/tailwindcss-extra exclusion
- `pytest.ini` - asyncio_mode=auto configuration
- `tests/conftest.py` - vatakara_depot fixture, guard fixture, Vatakara sample_locations
- `tests/apps/kerala_delivery/api/test_api.py` - All coordinates migrated to Vatakara
- `tests/apps/kerala_delivery/api/test_qr_helpers.py` - All coordinates migrated to Vatakara
- `tests/integration/test_osrm_vroom_pipeline.py` - All coordinates migrated to Vatakara
- `tests/test_e2e_pipeline.py` - All coordinates migrated to Vatakara
- `tests/scripts/test_geocode_batch.py` - All coordinates migrated to Vatakara
- `tests/scripts/test_import_orders.py` - All coordinates migrated to Vatakara
- `tests/core/geocoding/test_cache.py` - All coordinates migrated to Vatakara
- `tests/core/models/test_models.py` - All coordinates migrated to Vatakara
- `tests/core/data_import/test_csv_importer.py` - All coordinates migrated to Vatakara
- `tests/core/geocoding/test_google_adapter.py` - All coordinates migrated to Vatakara
- `tests/core/database/test_database.py` - All coordinates migrated to Vatakara
- `tests/core/optimizer/test_vroom_adapter.py` - All coordinates migrated to Vatakara
- `tests/core/routing/test_osrm_adapter.py` - All coordinates migrated to Vatakara

## Decisions Made
- Used tailwind-cli-extra (not standard tailwindcss CLI) because it bundles DaisyUI without needing npm/node
- Added backward-compatible `kochi_depot` fixture alias to prevent any test breakage during migration
- Added autouse `_verify_depot_matches_config` guard fixture to catch future config/test coordinate drift
- Fixed trailing-zero precision in OSRM and VROOM coordinate assertions (Python `75.5700` renders as `75.57` in URLs)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed floating-point trailing zero precision in coordinate assertions**
- **Found during:** Task 2 (test suite run after migration)
- **Issue:** Coordinates like 75.5700 and 11.5950 render as 75.57 and 11.595 in Python string formatting, causing assertion mismatches in test_osrm_adapter.py and test_vroom_adapter.py
- **Fix:** Updated assertions to use the Python-rendered form (75.57, 11.595) instead of padded form (75.5700, 11.5950)
- **Files modified:** tests/core/routing/test_osrm_adapter.py, tests/core/optimizer/test_vroom_adapter.py
- **Verification:** Full test suite passes (360/360)
- **Committed in:** 1bb96d1 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor precision fix necessary for test correctness. No scope creep.

## Issues Encountered
None - plan executed cleanly after the single precision fix.

## User Setup Required
None - no external service configuration required. The tailwindcss-extra binary is downloaded automatically.

## Next Phase Readiness
- PWA CSS pipeline ready for Phase 5 driver app redesign (Tailwind utility classes will be scanned from index.html)
- All tests validate correct Vatakara geography
- async tests no longer need per-function @pytest.mark.asyncio decorator

## Self-Check: PASSED

All 6 artifact files verified present. Both task commits (a91005f, 1bb96d1) verified in git log.

---
*Phase: 01-foundation*
*Completed: 2026-03-01*
