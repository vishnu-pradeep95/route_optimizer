---
phase: 11-foundation-fixes
plan: 02
subsystem: database, api, data-import
tags: [address-display, cdcms, pydantic, sqlalchemy, alembic, bug-fix]

# Dependency graph
requires:
  - phase: 11-01
    provides: "Clean CDCMS address text pipeline (word splitting, abbreviation expansion)"
provides:
  - "Fixed address_display to use order.address_raw (cleaned CDCMS text) instead of Google formatted_address"
  - "New address_original field storing completely unprocessed CDCMS ConsumerAddress"
  - "API response includes address_raw field for unprocessed address text"
  - "Alembic migration adding address_original column and backfilling address_display"
affects: [phase-12, phase-13, driver-app]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "address_display always sourced from order.address_raw (never from geocoder)"
    - "address_original field for unprocessed source text preservation"
    - "Non-CDCMS uploads backfill address_original = address_raw in upload endpoint"

key-files:
  created:
    - "infra/alembic/versions/9c370459587f_add_address_original_column.py"
  modified:
    - "core/models/order.py"
    - "core/models/route.py"
    - "core/database/models.py"
    - "core/database/repository.py"
    - "core/optimizer/vroom_adapter.py"
    - "core/data_import/cdcms_preprocessor.py"
    - "core/data_import/csv_importer.py"
    - "apps/kerala_delivery/api/main.py"
    - "infra/postgres/init.sql"
    - "tests/core/database/test_database.py"
    - "tests/apps/kerala_delivery/api/test_api.py"
    - "tests/core/data_import/test_cdcms_preprocessor.py"

key-decisions:
  - "address_display sourced from order.address_raw at both bug sites (repository.py, vroom_adapter.py)"
  - "API field named 'address_raw' maps to Python model field 'address_original' (avoids confusion with Order.address_raw)"
  - "Non-CDCMS uploads backfill address_original = address_raw (no null for standard CSV)"
  - "Alembic migration backfills address_display from address_raw but does NOT backfill address_original (original text was never stored)"

patterns-established:
  - "address_display = order.address_raw: all future code creating OrderDB or RouteStop must use this pattern"
  - "address_original preservation: CDCMS preprocessor stores unprocessed text, CsvImporter reads it, repository persists it"

requirements-completed: [ADDR-01]

# Metrics
duration: 10min
completed: 2026-03-11
---

# Phase 11 Plan 02: Address Display Bug Fix Summary

**Fixed address_display to use cleaned CDCMS text (order.address_raw) instead of Google's formatted_address, added address_original column for unprocessed text preservation, and exposed address_raw field in API response**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-11T11:01:55Z
- **Completed:** 2026-03-11T11:12:22Z
- **Tasks:** 2 (TDD: RED then GREEN)
- **Files modified:** 14

## Accomplishments
- Fixed the core ADDR-01 bug: drivers now see cleaned CDCMS delivery addresses instead of Google's generic "Vatakara, Kerala, India"
- Added address_original field across the full stack (Pydantic models, ORM models, SQL schema, CsvImporter, preprocessor)
- API response now includes address_raw field at both serialization sites (GET /api/routes and GET /api/routes/{vehicle_id})
- Created Alembic migration that adds address_original columns and backfills address_display from address_raw for existing data
- Wired CsvImporter to read address_original from preprocessed CDCMS CSV and pass it to Order constructor

## Task Commits

Each task was committed atomically:

1. **Task 1: Write targeted tests for ADDR-01 bug fix and address_raw API field** - `5b01958` (test) - TDD RED phase, 7 failing tests
2. **Task 2: Add address_original field and fix address_display bug sites** - `7050765` (feat) - TDD GREEN phase, all 515 tests pass

## Files Created/Modified
- `core/models/order.py` - Added address_original field to Order Pydantic model
- `core/models/route.py` - Added address_original field to RouteStop Pydantic model
- `core/database/models.py` - Added address_original column to OrderDB and RouteStopDB ORM models
- `core/database/repository.py` - Fixed address_display source (address_raw not location.address_text), added address_original pass-through
- `core/optimizer/vroom_adapter.py` - Fixed address_display source (address_raw not location.address_text), added address_original
- `core/data_import/cdcms_preprocessor.py` - Added address_original column to preprocess_cdcms() output DataFrame
- `core/data_import/csv_importer.py` - CsvImporter reads address_original from CSV and passes to Order constructor
- `apps/kerala_delivery/api/main.py` - Added address_raw field to API response at both stop serialization sites, backfill loop for non-CDCMS uploads
- `infra/postgres/init.sql` - Added address_original column to orders and route_stops tables
- `infra/alembic/versions/9c370459587f_add_address_original_column.py` - Migration adding columns + backfilling address_display
- `tests/core/database/test_database.py` - TestAddressDisplaySource class (4 tests)
- `tests/apps/kerala_delivery/api/test_api.py` - TestAddressRawApiField class (3 tests), mock_stop updates
- `tests/core/data_import/test_cdcms_preprocessor.py` - Updated column assertions for address_original
- `pytest.ini` - Added addr01 and integration markers

## Decisions Made
- address_display sourced from order.address_raw at both bug sites -- this is the cleaned CDCMS text, not Google's formatted_address
- API field named "address_raw" maps to Python model field "address_original" to avoid confusion with Order.address_raw
- Non-CDCMS uploads backfill address_original = address_raw so every Order has non-None address_original
- Alembic migration backfills address_display from address_raw but does NOT backfill address_original (original unprocessed text was never stored before)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed existing test mocks missing address_original attribute**
- **Found during:** Task 2 (GREEN phase regression check)
- **Issue:** Existing mock_stop objects in test_api.py and test_database.py didn't have address_original attribute, causing MagicMock to auto-create one with a MagicMock value that Pydantic rejected
- **Fix:** Added `mock_stop.address_original = None` to all mock_stop instances used with route_db_to_pydantic
- **Files modified:** tests/apps/kerala_delivery/api/test_api.py (4 sites), tests/core/database/test_database.py (1 site)
- **Verification:** All 515 tests pass
- **Committed in:** 7050765 (Task 2 commit)

**2. [Rule 1 - Bug] Updated preprocessor column assertions**
- **Found during:** Task 2 (GREEN phase regression check)
- **Issue:** test_cdcms_preprocessor.py checked exact column list which didn't include address_original
- **Fix:** Added "address_original" to expected column lists in 2 assertions
- **Files modified:** tests/core/data_import/test_cdcms_preprocessor.py
- **Verification:** All 515 tests pass
- **Committed in:** 7050765 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs in existing test mocks)
**Impact on plan:** Both auto-fixes necessary for test compatibility with new field. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- address_display pipeline is fixed and tested -- drivers will see correct CDCMS addresses
- address_original column is ready for use by Phase 12 (dictionary coverage) and Phase 13 (geocoding improvements)
- Alembic migration must be run on production database: `alembic upgrade head`
- The address_display backfill in the migration will correct all existing orders in the database

---
*Phase: 11-foundation-fixes*
*Completed: 2026-03-11*
