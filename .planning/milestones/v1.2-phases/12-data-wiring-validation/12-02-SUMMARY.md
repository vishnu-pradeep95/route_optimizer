---
phase: 12-place-name-dictionary
plan: 02
subsystem: data-import
tags: [rapidfuzz, fuzzy-matching, address-splitting, dictionary, tdd]

# Dependency graph
requires:
  - phase: 12-01
    provides: "place_names_vatakara.json dictionary with 381 entries"
provides:
  - "AddressSplitter class with split() and fuzzy matching"
  - "17 unit tests covering splitting, fuzzy matching, compound names, edge cases"
affects: [12-03, cdcms-preprocessor-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: [per-token-scanning, longest-match-first, length-dependent-fuzzy-thresholds]

key-files:
  created:
    - core/data_import/address_splitter.py
    - tests/core/data_import/test_address_splitter.py
  modified: []

key-decisions:
  - "Per-token processing instead of character-level scanning to prevent false positives on already-spaced text"
  - "Aliases indexed alongside primary names for fuzzy matching (VATAKARA indexed as alias of VADAKARA entry)"
  - "Compound names output with spaces restored; simple names preserve original input case"

patterns-established:
  - "Per-token splitting: split input on whitespace first, then dictionary-match each token individually to avoid cross-token false positives"
  - "Compound name matching: entry names with spaces have compact form (spaces stripped) for matching concatenated text"

requirements-completed: [ADDR-05, ADDR-06]

# Metrics
duration: 5min
completed: 2026-03-12
---

# Phase 12 Plan 02: AddressSplitter Summary

**Dictionary-powered word splitter using RapidFuzz with longest-match-first scanning and length-dependent fuzzy thresholds (95/90/85)**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-12T00:30:16Z
- **Completed:** 2026-03-12T00:35:17Z
- **Tasks:** 2 (TDD RED + GREEN; REFACTOR skipped -- no cleanup needed)
- **Files created:** 2

## Accomplishments
- AddressSplitter class loads 381-entry dictionary and splits concatenated CDCMS text at place name boundaries
- Fuzzy matching with RapidFuzz fuzz.ratio accepts transliteration variants (VATAKARA/VADAKARA at 87.5%, MUTUNGAL/MUTTUNGAL at 94.1%)
- Length-dependent thresholds prevent false positives: 95% for <=4 chars, 90% for 5-6 chars, 85% for 7+ chars
- Compound name support: "CHORODEEAST" matches "CHORODE EAST" entry over shorter "CHORODE" entry
- PO/NR abbreviation gap detection between consecutive place names
- 17 comprehensive tests covering all specified behaviors pass

## Task Commits

Each task was committed atomically:

1. **Task 1: RED -- Failing tests** - `fe42c6c` (test)
2. **Task 2: GREEN -- Implementation** - `d655736` (feat)

_Note: REFACTOR phase skipped -- code style already consistent with cdcms_preprocessor.py, no cleanup needed._

## Files Created/Modified
- `core/data_import/address_splitter.py` - AddressSplitter class (238 lines) with split(), _split_token(), _find_match(), _get_threshold()
- `tests/core/data_import/test_address_splitter.py` - 17 unit tests (159 lines) covering splitting, fuzzy matching, longest-match-first, edge cases

## Decisions Made
- **Per-token processing over character-level scanning:** Splitting input on whitespace before dictionary matching prevents false positives where spaces in already-spaced text get included in fuzzy match candidates (e.g., " PALLIVATAKAR" falsely matching "PALLIVATAKARA" at 92.3%)
- **Aliases indexed alongside primary names:** Dictionary aliases (e.g., VATAKARA as alias of VADAKARA) are added to the entry list so both exact and fuzzy matching work against them
- **Compound name output preserves entry spacing:** When a compound entry like "CHORODE EAST" matches concatenated text "CHORODEEAST", the output uses the entry name (with space) rather than the input text

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed false positive fuzzy matching on already-spaced text**
- **Found during:** Task 2 (GREEN -- implementation)
- **Issue:** Character-level scanning included spaces in candidate substrings, causing fuzzy match false positives (e.g., " PALLIVATAKAR" matching "PALLIVATAKARA" at 92.3% when scanning "VALLIKKADU SARAMBI PALLIVATAKARA")
- **Fix:** Redesigned split() to process tokens individually -- split input on whitespace first, then apply dictionary matching per-token
- **Files modified:** core/data_import/address_splitter.py
- **Verification:** test_already_spaced passes; all 17 tests pass; full 88-test suite green
- **Committed in:** d655736 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Algorithm redesign necessary for correctness. The per-token approach is simpler and more robust than character-level scanning. No scope creep.

## Issues Encountered
None beyond the deviation documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- AddressSplitter class ready for integration into clean_cdcms_address() pipeline (Plan 12-03)
- Integration point: between Step 6 (trailing letter split) and Step 7 (second-pass abbreviation expansion)
- Lazy initialization pattern documented in 12-RESEARCH.md for module-level _splitter singleton

## Self-Check: PASSED

- [x] core/data_import/address_splitter.py exists (238 lines, min 80)
- [x] tests/core/data_import/test_address_splitter.py exists (159 lines, min 60)
- [x] Commit fe42c6c (RED) exists
- [x] Commit d655736 (GREEN) exists
- [x] json.load pattern found in address_splitter.py
- [x] fuzz.ratio pattern found in address_splitter.py
- [x] All 17 tests pass
- [x] Full 88-test data_import suite passes (no regressions)

---
*Phase: 12-place-name-dictionary*
*Completed: 2026-03-12*
