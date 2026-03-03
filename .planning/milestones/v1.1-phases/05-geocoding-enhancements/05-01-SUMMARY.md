---
phase: 05-geocoding-enhancements
plan: 01
subsystem: api
tags: [haversine, union-find, geocoding, duplicate-detection, pydantic, cost-transparency]

# Dependency graph
requires:
  - phase: 04-geocoding-cache
    provides: CachedGeocoder with stats dict, normalize_address(), geocode_confidence on Location
provides:
  - "core/geocoding/duplicate_detector.py: haversine_meters(), detect_duplicate_locations(), DuplicateCluster"
  - "Config constants: DUPLICATE_THRESHOLDS, GEOCODING_COST_PER_REQUEST, GEOCODING_FREE_TIER_USD"
  - "Extended OptimizationSummary with cache_hits, api_calls, estimated_cost_usd, free_tier_note, per_order_geocode_source, duplicate_warnings"
  - "DuplicateLocationWarning Pydantic model"
affects: [05-02 (frontend rendering of cost stats and duplicate warnings)]

# Tech tracking
tech-stack:
  added: []
  patterns: [post-geocoding-detection, confidence-weighted-thresholds, union-find-clustering]

key-files:
  created:
    - core/geocoding/duplicate_detector.py
    - tests/core/geocoding/test_duplicate_detector.py
  modified:
    - apps/kerala_delivery/config.py
    - apps/kerala_delivery/api/main.py

key-decisions:
  - "Default confidence 0.4 (approximate tier) when geocode_confidence is None"
  - "Mixed-confidence pairs use max(threshold_a, threshold_b) -- wider threshold dominates"
  - "Per-order geocode source tracked via CachedGeocoder.stats snapshot before/after each geocode call"

patterns-established:
  - "Post-geocoding detection: duplicate check runs after geocoding loop, before optimization, on geocoded_orders"
  - "Confidence-weighted thresholds: tier selection via _confidence_tier() maps 0.0-1.0 to rooftop/interpolated/geometric_center/approximate"
  - "Union-Find clustering: inline parent array with path compression for transitive grouping"

requirements-completed: [GEO-03, GEO-04]

# Metrics
duration: 4min
completed: 2026-03-02
---

# Phase 5 Plan 1: Cost Transparency + Duplicate Detection Summary

**Haversine + Union-Find duplicate detector with confidence-weighted thresholds, geocoding cost stats in upload response, 21 new tests**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-02T01:08:21Z
- **Completed:** 2026-03-02T01:13:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Created `core/geocoding/duplicate_detector.py` with Haversine distance, confidence-weighted threshold selection, and Union-Find transitive clustering
- Extended `OptimizationSummary` with 6 new backward-compatible fields for cost transparency (GEO-04) and duplicate warnings (GEO-03)
- Wired per-order geocode source tracking into the geocoding loop (works in both CachedGeocoder and cache-only paths)
- Added 21 passing tests covering haversine accuracy, same-address exclusion, confidence tiers, mixed-confidence thresholds, transitive clustering, and edge cases

## Task Commits

Each task was committed atomically:

1. **Task 1 (TDD RED): Failing tests for duplicate detector** - `c7bf48c` (test)
2. **Task 1 (TDD GREEN): Duplicate detector + config constants** - `583d5db` (feat)
3. **Task 2: Wire cost stats + duplicate detection into upload** - `de4eb39` (feat)

_Note: Task 1 followed TDD: RED tests first, then GREEN implementation._

## Files Created/Modified
- `core/geocoding/duplicate_detector.py` - Haversine distance, DuplicateCluster dataclass, detect_duplicate_locations() with Union-Find clustering
- `tests/core/geocoding/test_duplicate_detector.py` - 21 test cases covering all behaviors
- `apps/kerala_delivery/config.py` - DUPLICATE_THRESHOLDS dict, GEOCODING_COST_PER_REQUEST, GEOCODING_FREE_TIER_USD constants
- `apps/kerala_delivery/api/main.py` - DuplicateLocationWarning model, extended OptimizationSummary, per-order source tracking in geocoding loop, cost stats + duplicate detection wiring

## Decisions Made
- Default confidence of 0.4 (approximate tier) when geocode_confidence is None -- conservative approach avoids false positives for GPS-provided coordinates
- Mixed-confidence pairs use max(threshold_a, threshold_b) -- the less-accurate result dominates uncertainty
- Per-order geocode source tracked via CachedGeocoder.stats["hits"] snapshot before/after each geocode call -- zero behavior change to the geocoding loop
- Cache-only fallback path also tracks per-order source as "cached" for complete reporting

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Backend API now returns cost stats and duplicate warnings in the upload response
- Plan 05-02 (frontend) can render CostSummary and DuplicateWarnings components using the new fields
- All response fields have defaults, so existing dashboard works unchanged until frontend is updated

## Self-Check: PASSED

- [x] core/geocoding/duplicate_detector.py exists
- [x] tests/core/geocoding/test_duplicate_detector.py exists
- [x] 05-01-SUMMARY.md exists
- [x] Commit c7bf48c (RED tests) found
- [x] Commit 583d5db (GREEN impl) found
- [x] Commit de4eb39 (Task 2) found
- [x] 415 tests pass, zero regressions

---
*Phase: 05-geocoding-enhancements*
*Completed: 2026-03-02*
