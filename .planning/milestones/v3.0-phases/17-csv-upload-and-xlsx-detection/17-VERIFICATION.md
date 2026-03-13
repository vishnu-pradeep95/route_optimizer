---
phase: 17-csv-upload-and-xlsx-detection
verified: 2026-03-13T23:14:43Z
status: passed
score: 8/8 must-haves verified
re_verification:
  previous_status: passed
  previous_score: 10/10
  gaps_closed:
    - "Geocoding now filters to selected drivers' orders BEFORE the geocoding loop — pre-geocoding filter added at main.py:1583-1606; old post-geocoding block replaced with simple assignment at line 1876"
    - "PLACEHOLDER_DRIVER_NAMES constant added to cdcms_preprocessor.py:88; Step 3b filter at lines 250-263 removes Allocation Pending and blank DeliveryMan values before any preview or geocoding occurs"
    - "Process Selected button replaced upload-btn class with tw:btn tw:btn-warning tw:flex-1 tw:gap-2 at UploadRoutes.tsx:795 — DaisyUI component handles sizing, flex alignment, and disabled state natively"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Upload a CDCMS XLSX file that contains rows where DeliveryMan = 'Allocation Pending'; inspect driver preview table"
    expected: "No row named 'Allocation Pending' appears in driver preview — only real driver names shown"
    why_human: "Requires real CDCMS XLSX file with placeholder rows and running Docker stack with dashboard"
  - test: "Upload multi-driver CDCMS file, deselect all but 2 drivers, click Process Selected — check server logs for geocoding call counts"
    expected: "Log shows 'Driver selection: N of M orders selected for geocoding (2 drivers selected)' where N matches only 2 selected drivers' orders; Google Maps API calls equal N not M"
    why_human: "Requires live Docker stack with real Google Maps API key and log inspection"
  - test: "Inspect Process Selected button in driver preview panel on mobile viewport (393x851)"
    expected: "Button fills available width alongside Back button with amber color; no overflow or misalignment"
    why_human: "Visual layout requires browser rendering to confirm DaisyUI flex behavior on small screens"
---

# Phase 17: CSV Upload & XLSX Detection Verification Report

**Phase Goal:** Users can upload both .csv and .xlsx CDCMS files, see which drivers are in the file, and select which drivers to process before optimization runs
**Verified:** 2026-03-13T23:14:43Z
**Status:** passed
**Re-verification:** Yes — after Plan 04 UAT gap closure (3 additional gaps fixed beyond Plan 03)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A .xlsx CDCMS file is correctly detected as CDCMS format and parsed (not rejected) | VERIFIED | `_is_cdcms_format()` at main.py:629 handles .xlsx; `TestXlsxCdcmsDetection` 4 tests pass |
| 2 | After uploading, user sees a list of drivers with order counts and correct status badges before processing | VERIFIED | parse_upload emits `status='matched'` at line 1151; `test_parse_upload_driver_status_categories` passes |
| 3 | User can select a subset of drivers and only those drivers get routes generated | VERIFIED | Pre-geocoding filter at main.py:1586-1606; `test_upload_with_selected_drivers_filters_optimization` passes |
| 4 | Selecting N drivers only geocodes those N drivers' orders, not all orders in the file | VERIFIED | Filter placed before geocoding loop at line 1608; `test_upload_selected_drivers_filters_before_geocoding` passes |
| 5 | Driver preview does not show CDCMS placeholders like "Allocation Pending" | VERIFIED | `PLACEHOLDER_DRIVER_NAMES` + Step 3b in `preprocess_cdcms()` at lines 250-263; `test_parse_upload_excludes_allocation_pending` and `TestPlaceholderDriverFiltering` (4 tests) pass |
| 6 | System filters to "Allocated-Printed" OrderStatus by default | VERIFIED | `preprocess_cdcms()` default filter; `TestAllocatedPrintedDefaultFilter` (2 tests) pass |
| 7 | Column order in CSV/XLSX does not affect parsing | VERIFIED | Column set membership check in `_validate_cdcms_columns()`; `TestColumnOrderIndependence` (2 tests) pass |
| 8 | Process Selected button is correctly sized and aligned in the driver preview panel | VERIFIED | Button uses `tw:btn tw:btn-warning tw:flex-1 tw:gap-2` at UploadRoutes.tsx:795; dashboard production build passes in 4.13s with no TypeScript errors |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/kerala_delivery/api/main.py` | `_is_cdcms_format()`, `DriverPreview`, `ParsePreviewResponse`, `_upload_tokens`, `parse_upload()`, pre-geocoding driver filter, `status='matched'` | VERIFIED | All present; pre-geocoding filter at lines 1583-1606; matched status at line 1151 |
| `core/data_import/cdcms_preprocessor.py` | `PLACEHOLDER_DRIVER_NAMES`, Step 3b placeholder filter | VERIFIED | `PLACEHOLDER_DRIVER_NAMES = {"ALLOCATION PENDING", ""}` at line 88; Step 3b filter at lines 250-263 |
| `apps/kerala_delivery/dashboard/src/types.ts` | `DriverPreview` and `ParsePreviewResponse` TypeScript interfaces | VERIFIED | Both present at lines 134 and 144 |
| `apps/kerala_delivery/dashboard/src/lib/api.ts` | `parseUpload()` and `processSelected()` functions | VERIFIED | Both present; `processSelected()` appends `upload_token` and `selected_drivers` to FormData at lines 471-472 |
| `apps/kerala_delivery/dashboard/src/pages/UploadRoutes.tsx` | `WorkflowState`, checkbox table, stats bar, `STATUS_BADGE_CLASS` mapping, Process Selected uses DaisyUI classes | VERIFIED | `STATUS_BADGE_CLASS` maps `"matched"` to `"tw:badge-warning"`; Process Selected uses `tw:btn tw:btn-warning tw:flex-1 tw:gap-2` at line 795 |
| `apps/kerala_delivery/dashboard/src/pages/UploadRoutes.css` | `.driver-preview`, `.tw\:badge-reactivated`, responsive stats | VERIFIED | All present |
| `tests/apps/kerala_delivery/api/test_api.py` | `TestXlsxCdcmsDetection` (4), `TestParseUploadEndpoint` (8), `TestUploadTokenBasedProcessing` (7) | VERIFIED | 19 tests, all 19 pass |
| `tests/core/data_import/test_cdcms_preprocessor.py` | `TestColumnOrderIndependence` (2), `TestAllocatedPrintedDefaultFilter` (2), `TestPlaceholderDriverFiltering` (4) | VERIFIED | 64 total tests, all 64 pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `dashboard/src/lib/api.ts` | `/api/parse-upload` | `fetch POST` with FormData | WIRED | `parseUpload()` sends FormData to `/api/parse-upload` |
| `dashboard/src/lib/api.ts` | `/api/upload-orders` | `upload_token` + `selected_drivers` in FormData | WIRED | `processSelected()` appends both fields at lines 471-472 |
| `main.py` | `preprocess_cdcms()` | Called in both `parse_upload()` (line 1101) and `upload_and_optimize()` (line 1417) | WIRED | Placeholder filter at Step 3b benefits both endpoints through this shared call |
| `main.py` | Pre-geocoding driver filter | `selected_driver_list` check at lines 1586-1606 before geocoding loop at line 1608 | WIRED | Filter order confirmed; old post-geocoding block removed, replaced with `orders_for_optimization = geocoded_orders` at line 1876 |
| `cdcms_preprocessor.py` | Placeholder filter | `PLACEHOLDER_DRIVER_NAMES` applied in Step 3b of `preprocess_cdcms()` | WIRED | Rows with Allocation Pending or blank DeliveryMan never reach driver preview or geocoding pipeline |
| `main.py parse_upload()` | `DriverPreview.status='matched'` | `matched_drivers` loop at line 1151 | WIRED | Emits `"matched"` for fuzzy-matched drivers; `STATUS_BADGE_CLASS["matched"]` = `"tw:badge-warning"` (amber) reachable |
| `UploadRoutes.tsx` | DaisyUI button component | `tw:btn tw:btn-warning tw:flex-1 tw:gap-2` at line 795 | WIRED | No `upload-btn` class on process button; DaisyUI handles disabled state via `disabled` prop |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CSV-01 | 17-01 | System correctly detects CDCMS format in .xlsx Excel files | SATISFIED | `_is_cdcms_format()` extension-first detection; 4 passing `TestXlsxCdcmsDetection` tests |
| CSV-02 | 17-01, 17-02, 17-03, 17-04 | User can see which drivers are found in uploaded CSV with correct status badges before processing | SATISFIED | Preview renders with order counts; `status='matched'` emitted for fuzzy-matched drivers; "Allocation Pending" excluded by Step 3b filter |
| CSV-03 | 17-02, 17-04 | User can select which drivers' routes to generate | SATISFIED | `selected_drivers` Form param filters optimization; pre-geocoding filter ensures only selected drivers' orders are geocoded; frontend checkbox table + `processSelected()` |
| CSV-04 | 17-01 | System filters to "Allocated-Printed" OrderStatus by default | SATISFIED | `preprocess_cdcms()` default filter; 2 tests verify exclusion of non-Allocated-Printed rows |
| CSV-05 | 17-01 | Column order in CSV/XLSX does not affect parsing | SATISFIED | Column set membership check; 2 tests with shuffled columns pass |

### Anti-Patterns Found

None. No TODO/FIXME/HACK markers found in the 5 files modified by Plan 04. No stub implementations detected.

### Test Suite Health (Re-verification Run)

- `TestXlsxCdcmsDetection` (4 tests): 4 pass
- `TestParseUploadEndpoint` (8 tests, includes new `test_parse_upload_excludes_allocation_pending`): 8 pass
- `TestUploadTokenBasedProcessing` (7 tests, includes new `test_upload_selected_drivers_filters_before_geocoding`): 7 pass
- `tests/core/data_import/test_cdcms_preprocessor.py` (64 tests, includes new `TestPlaceholderDriverFiltering` with 4 tests): 64 pass
- Dashboard production build: passes (built in 4.13s, no TypeScript or CSS errors)
- Pre-existing rate-limiter flakiness: unchanged, documented in `deferred-items.md`

### Human Verification Required

#### 1. Allocation Pending Excluded from Live Driver Preview

**Test:** Start Docker stack with dashboard. Upload a CDCMS XLSX file that contains rows where DeliveryMan = "Allocation Pending". Inspect the driver preview table.
**Expected:** No row named "Allocation Pending" appears in the driver preview. Only rows with real driver names are shown.
**Why human:** Requires real CDCMS file with placeholder rows and a running Docker stack.

#### 2. Pre-Geocoding Filter API Cost Verification

**Test:** Start Docker stack with a real Google Maps API key. Upload a multi-driver CDCMS file with 100+ orders. Deselect all drivers except 2. Click "Process Selected". Check server logs for geocoding call counts.
**Expected:** Log line shows "Driver selection: N of M orders selected for geocoding (2 drivers selected)" where N matches only the 2 selected drivers' order totals, and Google Maps API calls equal N (not M).
**Why human:** Requires live Docker stack with real Google Maps API key and log inspection.

#### 3. Process Selected Button Visual Alignment

**Test:** Upload a file and reach the driver preview screen. Inspect the button row containing "Back" and "Process Selected (N)" on a mobile viewport (393x851).
**Expected:** Both buttons sit side by side in a flex row; Process Selected fills remaining space with amber color; button is fully visible without overflow or clipping.
**Why human:** Visual layout requires browser rendering to confirm DaisyUI flex behavior on small screens.

### Re-verification Summary

**Plan 04 gaps closed:** All 3 UAT issues reported from `17-UAT.md` are resolved and verified in code.

1. **Geocoding filter (blocker):** Pre-geocoding driver filter added at `main.py:1583-1606`, before the geocoding loop at line 1608. The old post-geocoding filter block was removed and replaced with a simple `orders_for_optimization = geocoded_orders` assignment (line 1876). New test `test_upload_selected_drivers_filters_before_geocoding` verifies the order count entering geocoding equals only selected drivers' orders.

2. **Allocation Pending placeholder (major):** `PLACEHOLDER_DRIVER_NAMES = {"ALLOCATION PENDING", ""}` added to `cdcms_preprocessor.py:88`. Step 3b filter at lines 250-263 strips these rows before the DataFrame is returned from `preprocess_cdcms()`. Since both `parse_upload` and `upload_and_optimize` call `preprocess_cdcms()`, placeholder rows never reach the driver preview or geocoding pipeline. `TestPlaceholderDriverFiltering` (4 tests) and `test_parse_upload_excludes_allocation_pending` confirm the behavior.

3. **Button alignment (cosmetic):** `upload-btn` class removed from Process Selected button. Now uses `tw:btn tw:btn-warning tw:flex-1 tw:gap-2` at `UploadRoutes.tsx:795`. DaisyUI handles disabled state natively; no inline style override. Dashboard production build confirms no TypeScript or CSS errors.

**No regressions:** All previously verified items remain verified. 19 phase-specific API tests and 64 CDCMS preprocessor tests pass. Dashboard production build succeeds.

**All 5 requirements (CSV-01 through CSV-05) satisfied.** Phase goal is achieved.

---

_Verified: 2026-03-13T23:14:43Z_
_Verifier: Claude (gsd-verifier)_
