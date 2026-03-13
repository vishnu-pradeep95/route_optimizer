---
phase: 17-csv-upload-and-xlsx-detection
verified: 2026-03-13T22:10:00Z
status: passed
score: 10/10 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 9/10
  gaps_closed:
    - "Fuzzy-matched drivers now receive status='matched' (amber badge) — line 1151 of main.py fixed from 'existing' to 'matched'; test assertion updated from existing_found to matched_found"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Upload a CDCMS .xlsx file with drivers that fuzzy-match existing DB drivers"
    expected: "Driver preview shows amber 'Matched' badge for fuzzy-matched drivers, green 'Existing' for exact matches"
    why_human: "Requires real DB state + fuzzy match scoring to confirm badge renders in browser"
  - test: "Upload a single-driver CDCMS .xlsx file via dashboard, verify preview shows, process it"
    expected: "Preview appears even for single-driver files; routes generate for that one driver"
    why_human: "End-to-end flow validation requires running Docker stack + dashboard dev server"
  - test: "Upload a CDCMS file, deselect one driver, click Process Selected"
    expected: "Only selected drivers appear in route cards; deselected driver's routes are absent"
    why_human: "Route output visibility requires live browser with full Docker stack"
---

# Phase 17: CSV Upload & XLSX Detection Verification Report

**Phase Goal:** Users can upload both .csv and .xlsx CDCMS files, see which drivers are in the file, and select which drivers to process before optimization runs
**Verified:** 2026-03-13T22:10:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (Plan 03 fixed matched driver status)

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | A .xlsx CDCMS file is correctly detected as CDCMS format and parsed (not rejected) | VERIFIED | `_is_cdcms_format()` uses `pd.read_excel(nrows=0)` for .xlsx; `TestXlsxCdcmsDetection` 4 tests all pass |
| 2  | After uploading, user sees a list of drivers with order counts and correct status badges before processing | VERIFIED | Parse endpoint emits `status='matched'` for fuzzy-matched drivers (line 1151 fixed); `test_parse_upload_driver_status_categories` passes asserting `matched_found` |
| 3  | User can select a subset of drivers and only selected drivers get routes generated | VERIFIED | `upload_and_optimize()` accepts `selected_drivers` Form param; `TestUploadTokenBasedProcessing::test_upload_with_selected_drivers_filters_optimization` passes |
| 4  | System filters to "Allocated-Printed" OrderStatus by default | VERIFIED | `preprocess_cdcms()` default filter applied; `TestAllocatedPrintedDefaultFilter` (2 tests) pass |
| 5  | Column order in CSV/XLSX does not affect parsing | VERIFIED | Column set membership check in `_validate_cdcms_columns()`; `TestColumnOrderIndependence` (2 tests) pass |

**Score:** 5/5 truths verified (10/10 must-haves verified including sub-artifacts)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/kerala_delivery/api/main.py` | `_is_cdcms_format()`, `DriverPreview`, `ParsePreviewResponse`, `_upload_tokens`, `parse_upload()`, correct `status='matched'` in matched_drivers loop | VERIFIED | All present; line 1151 confirmed as `"status": "matched"` |
| `apps/kerala_delivery/dashboard/src/types.ts` | `DriverPreview` and `ParsePreviewResponse` TypeScript interfaces | VERIFIED | Both present; all fields match Pydantic models |
| `apps/kerala_delivery/dashboard/src/lib/api.ts` | `parseUpload()` and `processSelected()` functions | VERIFIED | Both present; FormData upload, X-API-Key auth, `ApiUploadError` handling |
| `apps/kerala_delivery/dashboard/src/pages/UploadRoutes.tsx` | `WorkflowState`, checkbox table, stats bar, `STATUS_BADGE_CLASS` mapping | VERIFIED | `STATUS_BADGE_CLASS` maps `"matched"` to `"tw:badge-warning"` (amber) — now reachable |
| `apps/kerala_delivery/dashboard/src/pages/UploadRoutes.css` | `.driver-preview`, `.tw\:badge-reactivated`, responsive stats | VERIFIED | All present |
| `tests/apps/kerala_delivery/api/test_api.py` | `TestXlsxCdcmsDetection` (4), `TestParseUploadEndpoint` (7), `TestUploadTokenBasedProcessing` (6) | VERIFIED | 17 tests, all 17 pass in isolation |
| `tests/core/data_import/test_cdcms_preprocessor.py` | `TestColumnOrderIndependence` (2), `TestAllocatedPrintedDefaultFilter` (2) | VERIFIED | 4 tests, all 4 pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `apps/kerala_delivery/dashboard/src/lib/api.ts` | `/api/parse-upload` | `fetch POST` with FormData | WIRED | `parseUpload()` sends FormData to `/api/parse-upload` |
| `apps/kerala_delivery/dashboard/src/lib/api.ts` | `/api/upload-orders` | `upload_token` in FormData | WIRED | `processSelected()` appends `upload_token` and `selected_drivers` to FormData |
| `apps/kerala_delivery/api/main.py` | `core/data_import/cdcms_preprocessor.py` | `preprocess_cdcms()` call in parse endpoint | WIRED | Confirmed at line 1101 |
| `apps/kerala_delivery/api/main.py` | `auto_create_drivers_from_csv()` | driver summary generation in parse endpoint | WIRED | Confirmed at line 1120 |
| `apps/kerala_delivery/api/main.py parse_upload()` | `DriverPreview.status='matched'` | `matched_drivers` loop line 1151 | WIRED | Fixed: now emits `"matched"` for fuzzy-matched drivers |
| `apps/kerala_delivery/dashboard/src/pages/UploadRoutes.tsx` | `STATUS_BADGE_CLASS["matched"]` | `DriverPreview.status` field from API | WIRED | `"tw:badge-warning"` (amber) now reachable since backend emits `"matched"` |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CSV-01 | 17-01 | System correctly detects CDCMS format in .xlsx Excel files | SATISFIED | `_is_cdcms_format()` extension-first detection; 4 passing tests |
| CSV-02 | 17-01, 17-02, 17-03 | User can see which drivers are found in uploaded CSV with correct status badges before processing | SATISFIED | Preview renders with order counts; `status='matched'` now emitted for fuzzy-matched drivers (Plan 03 fix) |
| CSV-03 | 17-02 | User can select which drivers' routes to generate | SATISFIED | `selected_drivers` Form param filters optimization; frontend checkbox table + `processSelected()` |
| CSV-04 | 17-01 | System filters to "Allocated-Printed" OrderStatus by default | SATISFIED | `preprocess_cdcms()` default filter; 2 tests verify exclusion |
| CSV-05 | 17-01 | Column order in CSV/XLSX does not affect parsing | SATISFIED | Column set membership check; 2 tests with shuffled columns pass |

### Anti-Patterns Found

None. The one anti-pattern from the previous verification (line 1151 `"status": "existing"` for matched drivers) has been resolved.

### Test Suite Health (Re-verification Run)

- `TestParseUploadEndpoint` (7 tests): **7 pass**
- `TestXlsxCdcmsDetection` (4 tests): **4 pass**
- `TestUploadTokenBasedProcessing` (6 tests): **6 pass**
- `tests/core/data_import/test_cdcms_preprocessor.py` (60 tests): **60 pass**
- Key targeted test: `test_parse_upload_driver_status_categories` now asserts `matched_found` and passes
- Pre-existing rate-limiter flakiness: unchanged, documented in `deferred-items.md`

### Human Verification Required

#### 1. Fuzzy-Match "Matched" Badge Display in Browser

**Test:** Set up DB with a driver named "Gireeshan Kumar", upload a CDCMS file containing "GIREESHAN K" as DeliveryMan via the dashboard
**Expected:** Driver preview shows amber "Matched" badge with sub-row: `"GIREESHAN K" -> Gireeshan Kumar (XX%)`
**Why human:** Requires real DB state + fuzzy match scoring + running Docker stack to confirm badge renders in browser

#### 2. End-to-End Upload Flow with .xlsx

**Test:** Start Docker stack, upload `data/Refill.xlsx` via dashboard
**Expected:** File accepted (not rejected), driver preview appears, drivers shown with order counts and correct status badges
**Why human:** Requires Docker stack running + real XLSX CDCMS file

#### 3. Driver Deselection to Route Output

**Test:** Upload multi-driver file, deselect one driver, click "Process Selected (N)"
**Expected:** Route cards appear only for selected drivers; deselected driver absent from results
**Why human:** Route output visibility requires live browser + full optimization pipeline

### Re-verification Summary

**Gap closed:** The single gap from the initial verification (Plan 03) is resolved. The `matched_drivers` loop in `parse_upload()` now assigns `"status": "matched"` at line 1151 of `main.py`. The corresponding test was updated to assert `matched_found` instead of `existing_found`. The amber "Matched" badge (`tw:badge-warning`) in the frontend `STATUS_BADGE_CLASS` mapping is now reachable for fuzzy-matched drivers.

**No regressions:** All 17 phase-specific API tests and all 60 CDCMS preprocessor tests pass. No new failures introduced.

**All 5 requirements satisfied.** Phase goal is achieved.

---

_Verified: 2026-03-13T22:10:00Z_
_Verifier: Claude (gsd-verifier)_
