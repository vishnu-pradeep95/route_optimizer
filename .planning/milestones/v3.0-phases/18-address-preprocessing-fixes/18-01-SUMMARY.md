---
phase: 18-address-preprocessing-fixes
plan: 01
subsystem: data-import
tags: [regex, address-cleaning, cdcms, preprocessing, tdd]

# Dependency graph
requires:
  - phase: 15-address-preprocessing
    provides: "CDCMS preprocessor with 13-step cleaning pipeline"
provides:
  - "(HO) -> House expansion with space padding (172 Refill.xlsx occurrences)"
  - "(PO) -> P.O. expansion with space padding (368 Refill.xlsx occurrences)"
  - "(H) -> House space padding fix (104 Refill.xlsx occurrences)"
  - "16 new unit tests covering parenthesized abbreviation patterns"
affects: [geocoding-accuracy, address-quality]

# Tech tracking
tech-stack:
  added: []
  patterns: ["regex ordering: specific patterns (HO) before general (H)", "space padding for concatenated abbreviation expansion"]

key-files:
  created: []
  modified:
    - core/data_import/cdcms_preprocessor.py
    - tests/core/data_import/test_cdcms_preprocessor.py

key-decisions:
  - "(HO) regex placed before (H) to prevent partial matching"
  - "Space padding ' House ' instead of 'House' to prevent word concatenation in all patterns"
  - "Added PERATTEYATH, POOLAKANDY, KOLAKKOTT to protected words to prevent trailing-letter garbling"

patterns-established:
  - "Parenthesized abbreviation ordering: more specific patterns first ((HO) before (H))"

requirements-completed: [ADDR-01, ADDR-02, ADDR-03]

# Metrics
duration: 2min
completed: 2026-03-13
---

# Phase 18 Plan 01: Address Preprocessing Fixes Summary

**Fixed (HO), (PO), (H) regex patterns with space padding -- covers 644 of 1,885 Refill.xlsx orders**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-13T23:59:34Z
- **Completed:** 2026-03-14T00:01:34Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- Fixed (HO) expansion (172 Refill.xlsx occurrences) -- was completely unmatched, now expands to "House" with proper spacing
- Fixed (PO) expansion (368 Refill.xlsx occurrences) -- was completely unmatched, now expands to "P.O." with proper spacing
- Fixed (H) space padding (104 Refill.xlsx occurrences) -- was concatenating "House" with adjacent words
- Added 16 new tests (80 total, zero regressions) covering real Refill.xlsx address patterns
- MUTTUNGAL preserved as single word in all compound patterns

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for (HO), (PO), (H) patterns** - `bf28f9b` (test)
2. **Task 1 GREEN: Fix regex patterns in cdcms_preprocessor** - `4cde7ff` (feat)

_TDD task: test commit (RED) followed by implementation commit (GREEN)_

## Files Created/Modified
- `core/data_import/cdcms_preprocessor.py` - Added (HO), (PO) regex patterns, fixed (H) space padding, added 3 protected words
- `tests/core/data_import/test_cdcms_preprocessor.py` - Added TestParenthesizedAbbreviations (11 tests) and TestRefillXlsxRegressions (5 tests)

## Decisions Made
- **(HO) before (H) ordering:** Placed (HO) regex before (H) in Step 4 to prevent partial matching. While `\(H\)` technically wouldn't match `(HO)`, the ordering makes intent explicit and prevents future bugs.
- **Space padding for all patterns:** Used `" House "` and `" P.O. "` instead of `"House"` and `"P.O."` -- Step 8 collapses extra spaces, but without padding, concatenated inputs like `CHALIL(H)7/214A` become `CHALILHouse7/214A`.
- **Protected words:** Added PERATTEYATH, POOLAKANDY, KOLAKKOTT to `_PROTECTED_WORDS` to prevent Step 6 trailing-letter splitter from garbling these Kerala place names.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added missing protected words for trailing-letter splitter**
- **Found during:** Task 1 GREEN (implementation)
- **Issue:** PERATTEYATH, POOLAKANDY, KOLAKKOTT were being garbled by Step 6's trailing-letter splitter (e.g., "Peratteyat H", "Poolakand Y")
- **Fix:** Added these 3 words to `_PROTECTED_WORDS` frozenset
- **Files modified:** core/data_import/cdcms_preprocessor.py
- **Verification:** All 80 tests pass
- **Committed in:** 4cde7ff (part of GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential for correctness -- without protected words, the regex fixes would still produce garbled output for some addresses. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Address cleaning pipeline now handles all three parenthesized abbreviation patterns
- Ready for 18-02 (next plan in phase)

---
*Phase: 18-address-preprocessing-fixes*
*Completed: 2026-03-13*
