---
phase: 11-foundation-fixes
plan: 01
subsystem: data-import
tags: [regex, text-processing, cdcms, address-cleaning, tdd]

# Dependency graph
requires:
  - phase: none
    provides: "existing clean_cdcms_address() 10-step pipeline"
provides:
  - "Trailing letter split heuristic for concatenated ALL-CAPS CDCMS words"
  - "Two-pass abbreviation expansion strategy (inline then standalone)"
  - "Protected word set pattern for false-positive prevention"
  - "BSNL and KSRTC title-case preservation"
affects: [11-02, 11-03, 12-dictionary]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Protected word set for heuristic false-positive prevention"
    - "Multi-priority word splitting (meaningful suffix > known prefix > single initial)"
    - "Two-pass abbreviation expansion (inline before split, standalone after split)"

key-files:
  created: []
  modified:
    - core/data_import/cdcms_preprocessor.py
    - tests/core/data_import/test_cdcms_preprocessor.py

key-decisions:
  - "Used protected word set instead of pure regex for trailing letter split -- ALL-CAPS text has no casing cues to distinguish real words from concatenations"
  - "Three-priority split heuristic: meaningful suffix (PO/NR/KB) > protected prefix match > single trailing initial"
  - "Module-level frozenset for protected words enables easy extension as new false positives are discovered in real data"
  - "Pipeline renumbered from 10 to 12 steps to accommodate new Step 6 (trailing split) and Step 7 (second-pass abbreviation)"

patterns-established:
  - "Protected word set pattern: add false-positive words to _PROTECTED_WORDS frozenset"
  - "Meaningful suffix pattern: add known abbreviations to _MEANINGFUL_SUFFIXES frozenset"

requirements-completed: [ADDR-02, ADDR-03]

# Metrics
duration: 11min
completed: 2026-03-11
---

# Phase 11 Plan 01: CDCMS Word Splitting and Abbreviation Reorder Summary

**Trailing letter split heuristic with protected word set for concatenated ALL-CAPS CDCMS addresses, plus two-pass abbreviation expansion strategy**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-11T10:48:02Z
- **Completed:** 2026-03-11T10:58:40Z
- **Tasks:** 3 (TDD: RED, GREEN, REFACTOR)
- **Files modified:** 2

## Accomplishments
- Trailing letter split correctly handles "ANANDAMANDIRAMK" -> "Anandamandiram K" and similar concatenations
- Two-pass abbreviation expansion: inline patterns (Step 4) handle "KUNIYILPO." before word splitting, standalone patterns (Step 7) handle "CHORODEEASTPO" after word splitting
- Zero regressions: all 33 existing tests pass unchanged alongside 16 new tests (49 total)
- Known abbreviations (KSEB, BSNL, KSRTC) are never split and always preserved as uppercase after title case

## Task Commits

Each task was committed atomically (TDD cycle):

1. **RED: Failing tests for ADDR-02 and ADDR-03** - `173b915` (test)
2. **GREEN: Implement trailing letter split and abbreviation reorder** - `c2bf39d` (feat)
3. **REFACTOR: Clean up pipeline structure and documentation** - `8daa47b` (refactor)

## Files Created/Modified
- `core/data_import/cdcms_preprocessor.py` - Enhanced clean_cdcms_address() with 12-step pipeline, new _split_word_if_concatenated() function, _PROTECTED_WORDS and _MEANINGFUL_SUFFIXES module-level frozensets
- `tests/core/data_import/test_cdcms_preprocessor.py` - Added TestWordSplitting (9 tests), TestKnownAbbreviationsPreserved (3 tests), TestStepOrdering (4 tests)

## Decisions Made
- **Protected word set over pure regex:** ALL-CAPS text provides no casing cues to distinguish "PARAMBATH" (real word) from "KUNIYILK" (concatenation). A protected word set is the only reliable false-positive prevention mechanism. The set will grow as more CDCMS data is processed.
- **Three-priority split heuristic:** (1) Meaningful suffix (PO, NR, KB, NKB) at word end, (2) known protected word as prefix after removing 2-3 chars, (3) default single trailing letter. This prioritizes semantically meaningful splits.
- **Module-level constants:** Moved _PROTECTED_WORDS and _MEANINGFUL_SUFFIXES to module-level frozensets for clarity and to avoid re-creating them on every function call.
- **Pipeline expanded to 12 steps:** New Step 6 (trailing letter split) and Step 7 (second-pass abbreviation) inserted between the existing digit-uppercase split and whitespace collapse.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Protected word set needed for false-positive prevention**
- **Found during:** GREEN phase (implementation)
- **Issue:** The plan's suggested regex approach `([A-Z]{4,})([A-Z]{1,3})` split every ALL-CAPS word of 5+ chars, incorrectly splitting real words like "PARAMBATH" -> "PARAMBAT H" and "KALAMASSERY" -> "KALAMASSER Y"
- **Fix:** Replaced pure regex with word-by-word processing using a protected word set (_PROTECTED_WORDS) containing known Kerala place/house names and abbreviations that should never be split
- **Files modified:** core/data_import/cdcms_preprocessor.py
- **Verification:** All 49 tests pass including `test_already_spaced_text_unchanged` which specifically tests that "VALIYA PARAMBATH NEAR SCHOOL" is not modified
- **Committed in:** c2bf39d (GREEN phase commit)

**2. [Rule 2 - Missing Critical] Added BSNL and KSRTC to title-case preservation**
- **Found during:** GREEN phase
- **Issue:** Step 9 (now Step 11) only preserved KSEB after title case. BSNL and KSRTC were converted to "Bsnl" and "Ksrtc" by title case
- **Fix:** Added `re.sub(r"\bBsnl\b", "BSNL", addr)` and `re.sub(r"\bKsrtc\b", "KSRTC", addr)` to Step 11
- **Files modified:** core/data_import/cdcms_preprocessor.py
- **Verification:** TestKnownAbbreviationsPreserved tests pass for all three abbreviations
- **Committed in:** c2bf39d (GREEN phase commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both fixes necessary for correctness. The protected word set approach is architecturally sound -- it follows the same pattern the plan suggested for abbreviation protection, extended to common place names. No scope creep.

## Issues Encountered
- The plan's regex approach for trailing letter splitting (`([A-Z]{4,})([A-Z]{1,3})`) is fundamentally incompatible with ALL-CAPS input because there are no case transitions to distinguish word boundaries. Multiple minimum-length thresholds were tested (5+, 8+, 12+, 15+) but none avoided false positives on normal Kerala words while catching the target concatenations. The protected word set approach was the pragmatic solution.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- clean_cdcms_address() pipeline is enhanced and ready for Phase 12 dictionary-based splitting
- _PROTECTED_WORDS set provides a pattern that Phase 12 can extend with dictionary-derived words
- The _split_word_if_concatenated() function's priority system is designed to be extended with dictionary lookups in Priority 2

---
*Phase: 11-foundation-fixes*
*Completed: 2026-03-11*
