---
phase: 18-address-preprocessing-fixes
plan: 04
subsystem: testing
tags: [pytest, playwright, address-cleaning, cdcms, refill-xlsx, e2e]

requires:
  - phase: 18-01
    provides: clean_cdcms_address with (HO)/(PO)/(H) expansion and protected words
  - phase: 18-02
    provides: 20km zone radius and env-configurable depot/zone settings
  - phase: 18-03
    provides: zone circle overlay on dashboard live map

provides:
  - pytest API-level tests verifying address cleaning on real Refill.xlsx data (8 tests)
  - Playwright E2E spec verifying cleaned addresses display correctly in dashboard
  - Fix for AddressSplitter fuzzy match false positives (first+last char guard)
  - MUTTUNGALPARA added to protected words

affects: []

tech-stack:
  added: []
  patterns:
    - "Focused integration testing: real data through production code without HTTP/DB overhead"
    - "First+last character guard on fuzzy dictionary matching"

key-files:
  created:
    - tests/apps/kerala_delivery/api/test_address_cleaning.py
    - e2e/dashboard-address-cleaning.spec.ts
  modified:
    - core/data_import/address_splitter.py
    - core/data_import/cdcms_preprocessor.py
    - e2e/helpers/setup.ts

key-decisions:
  - "Focused integration approach chosen over full HTTP pipeline mocking for pytest tests"
  - "First+last char guard on fuzzy matching to eliminate off-by-one false positives"
  - "MUTTUNGALPARA added to _PROTECTED_WORDS to prevent trailing-letter garbling"
  - "E2E spec named dashboard-address-cleaning.spec.ts to match existing dashboard project testMatch"

patterns-established:
  - "Real CDCMS data (Refill.xlsx) as ground truth for address cleaning verification"

requirements-completed: [ADDR-01, ADDR-02, ADDR-03, ADDR-04, ADDR-05]

duration: 7min
completed: 2026-03-14
---

# Phase 18 Plan 04: Address Cleaning Test Coverage Summary

**Pytest + Playwright tests verifying (HO)/(PO)/(H)/MUTTUNGAL cleaning on 1885 real Refill.xlsx orders, with fuzzy match false positive fix**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-14T01:02:16Z
- **Completed:** 2026-03-14T01:09:30Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- 8 pytest test cases verifying all address patterns (HO, PO, H, MUTTUNGAL) on 1885 real orders
- 3 Playwright E2E tests verifying cleaned addresses display correctly in dashboard route view
- Fixed AddressSplitter fuzzy match false positives that garbled 44/65 MUTTUNGAL addresses
- Added MUTTUNGALPARA to protected words to prevent trailing-letter split garbling

## Task Commits

Each task was committed atomically:

1. **Task 1: Create pytest API-level tests for address cleaning with Refill.xlsx** - `5641db1` (test)
2. **Task 2: Create Playwright E2E spec for address cleaning verification** - `333f144` (feat)

_Note: Task 1 was TDD but tests passed immediately (cleaning code works from v2.2). Bug fixes for fuzzy matching discovered during test execution were committed with the test._

## Files Created/Modified
- `tests/apps/kerala_delivery/api/test_address_cleaning.py` - 8 pytest tests loading real Refill.xlsx through clean_cdcms_address pipeline
- `e2e/dashboard-address-cleaning.spec.ts` - 3 Playwright E2E tests for dashboard address display
- `e2e/helpers/setup.ts` - Added REFILL_XLSX_PATH constant
- `core/data_import/address_splitter.py` - First+last char guard on fuzzy matching
- `core/data_import/cdcms_preprocessor.py` - Added MUTTUNGALPARA to protected words

## Decisions Made
- Used focused integration approach (real data + direct function call) instead of full HTTP mock pipeline, keeping tests fast (2.3s) and avoiding 100+ lines of mock setup
- First+last character matching guard on fuzzy dictionary matching eliminates off-by-one alignment false positives (e.g., "LMUTTUNGA" no longer fuzzy-matches "MUTTUNGAL")
- E2E test file named `dashboard-address-cleaning.spec.ts` to match existing `dashboard*.spec.ts` glob in playwright.config.ts

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed AddressSplitter fuzzy match false positives**
- **Found during:** Task 1 (pytest test_muttungal_preserved)
- **Issue:** Fuzzy matching accepted off-by-one candidates like "LMUTTUNGA" matching "MUTTUNGAL" (ratio 88.9% > 85% threshold). Garbled 44/65 MUTTUNGAL addresses in Refill.xlsx.
- **Fix:** Added first AND last character match guard before fuzzy comparison in AddressSplitter._find_match()
- **Files modified:** core/data_import/address_splitter.py
- **Verification:** All 65 MUTTUNGAL addresses now clean correctly; 119 existing data_import tests still pass
- **Committed in:** 5641db1 (Task 1 commit)

**2. [Rule 1 - Bug] Added MUTTUNGALPARA to protected words**
- **Found during:** Task 1 (pytest test_muttungal_preserved)
- **Issue:** MUTTUNGALPARA (a real Kerala place name in dictionary) was being split to "MUTTUNGALPAR A" by trailing-letter heuristic
- **Fix:** Added MUTTUNGALPARA to _PROTECTED_WORDS frozenset
- **Files modified:** core/data_import/cdcms_preprocessor.py
- **Verification:** Address "POMUTTUNGALPARA" now correctly produces "P.O. Muttungalpara"
- **Committed in:** 5641db1 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes directly improve address cleaning accuracy on real data. No scope creep -- fixes are within the same files and patterns the plan covers.

## Issues Encountered
None -- real data revealed the fuzzy matching bug, which was fixed inline during task execution.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 18 (Address Preprocessing Fixes) is complete: all 4 plans executed
- Ready to proceed to Phase 19 in v3.0 milestone

## Self-Check: PASSED

- [x] tests/apps/kerala_delivery/api/test_address_cleaning.py exists (209 lines, 8 tests)
- [x] e2e/dashboard-address-cleaning.spec.ts exists (102 lines, 3 tests)
- [x] e2e/helpers/setup.ts modified with REFILL_XLSX_PATH
- [x] Commit 5641db1 found (Task 1)
- [x] Commit 333f144 found (Task 2)
- [x] All 520 existing tests still pass

---
*Phase: 18-address-preprocessing-fixes*
*Completed: 2026-03-14*
