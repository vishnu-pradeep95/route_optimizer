---
phase: 17-csv-upload-and-xlsx-detection
plan: 01
subsystem: api
tags: [fastapi, pandas, xlsx, cdcms, upload, pydantic, typescript]

# Dependency graph
requires:
  - phase: 16-driver-database-foundation
    provides: "auto_create_drivers_from_csv(), driver CRUD, fuzzy matching"
provides:
  - "Fixed _is_cdcms_format() for .xlsx binary files"
  - "POST /api/parse-upload endpoint with ParsePreviewResponse"
  - "DriverPreview and ParsePreviewResponse Pydantic models"
  - "Upload token store with 30-min TTL"
  - "TypeScript DriverPreview and ParsePreviewResponse interfaces"
  - "parseUpload() API client function"
affects: [17-02-driver-preview-ui, upload-orders-endpoint, dashboard-upload-page]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-step upload flow: parse -> preview -> process"
    - "Upload token pattern: UUID references temp file on disk"
    - "Extension-first file format detection for binary vs text files"

key-files:
  created: []
  modified:
    - apps/kerala_delivery/api/main.py
    - apps/kerala_delivery/dashboard/src/types.ts
    - apps/kerala_delivery/dashboard/src/lib/api.ts
    - tests/apps/kerala_delivery/api/test_api.py
    - tests/core/data_import/test_cdcms_preprocessor.py

key-decisions:
  - "pandas import moved to module level in main.py (was local in auto_create_drivers_from_csv)"
  - "Upload token TTL set to 30 minutes (matches research recommendation)"
  - "Parse endpoint runs driver auto-creation to provide accurate status categories in preview"

patterns-established:
  - "Two-step upload: POST /api/parse-upload returns token, POST /api/upload-orders accepts token"
  - "Upload token cleanup on every parse request (lazy expiration)"

requirements-completed: [CSV-01, CSV-02, CSV-04, CSV-05]

# Metrics
duration: 7min
completed: 2026-03-13
---

# Phase 17 Plan 01: XLSX Detection Fix and Parse-Upload Endpoint Summary

**Fixed .xlsx CDCMS format detection via pandas read_excel, added POST /api/parse-upload endpoint returning driver preview with per-driver order counts and status categories, plus TypeScript types and API client**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-13T15:10:29Z
- **Completed:** 2026-03-13T15:17:38Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Fixed _is_cdcms_format() to handle .xlsx binary files by checking extension first and using pd.read_excel for Excel files (CSV-01)
- Created POST /api/parse-upload endpoint returning ParsePreviewResponse with driver preview data, order counts, and status categories (CSV-02 backend)
- Verified Allocated-Printed default filter (CSV-04) and column order independence (CSV-05) with comprehensive tests
- Added TypeScript interfaces and parseUpload() API client for frontend consumption
- 15 new tests across both test suites, all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix _is_cdcms_format() and add parse-upload endpoint (TDD)**
   - `b4324ee` (test): add failing tests for XLSX detection and parse-upload endpoint
   - `e7c0ccd` (feat): fix XLSX detection and add parse-upload endpoint
2. **Task 2: Add TypeScript types and parseUpload API client** - `a50cbbd` (feat)

## Files Created/Modified

- `apps/kerala_delivery/api/main.py` - Fixed _is_cdcms_format() for .xlsx, added DriverPreview/ParsePreviewResponse models, upload token store, POST /api/parse-upload endpoint
- `apps/kerala_delivery/dashboard/src/types.ts` - Added DriverPreview and ParsePreviewResponse TypeScript interfaces
- `apps/kerala_delivery/dashboard/src/lib/api.ts` - Added parseUpload() function with FormData upload and error handling
- `tests/apps/kerala_delivery/api/test_api.py` - 11 new tests: TestXlsxCdcmsDetection (4), TestParseUploadEndpoint (7)
- `tests/core/data_import/test_cdcms_preprocessor.py` - 4 new tests: TestColumnOrderIndependence (2), TestAllocatedPrintedDefaultFilter (2)

## Decisions Made

- Moved `import pandas as pd` from local import in auto_create_drivers_from_csv to module-level import (needed by _is_cdcms_format and parse endpoint)
- Parse endpoint runs auto_create_drivers_from_csv() to provide accurate driver status categories (new/matched/reactivated/existing) in the preview response
- Upload token cleanup uses lazy expiration (runs on every new parse request) rather than background task, matching the simple single-user office tool architecture

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Pre-existing test interaction issue: TestUploadAutoCreatesDrivers::test_upload_driver_names_title_cased_in_summary fails with 429 rate limit when run as part of full test suite (passes in isolation). This is a pre-existing issue not caused by Phase 17 changes. Documented in deferred-items.md.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Parse endpoint ready for frontend consumption in Plan 02 (driver preview UI)
- TypeScript types and API client ready for UploadRoutes.tsx state machine extension
- Upload token pattern established for the process endpoint extension in Plan 02

## Self-Check: PASSED

- All 5 modified files exist on disk
- All 3 task commits verified (b4324ee, e7c0ccd, a50cbbd)
- All key artifacts confirmed: _is_cdcms_format, DriverPreview, ParsePreviewResponse, parse_upload endpoint, TS interfaces, parseUpload client

---
*Phase: 17-csv-upload-and-xlsx-detection*
*Completed: 2026-03-13*
