---
phase: 14-api-confidence-fields-and-driver-pwa-badge
plan: 02
subsystem: ui
tags: [driver-pwa, daisyui, badge, leaflet, tailwindcss, approximate-location]

# Dependency graph
requires:
  - phase: 14-api-confidence-fields-and-driver-pwa-badge
    plan: 01
    provides: "API stop objects with geocode_confidence, geocode_method, and location_approximate fields"
provides:
  - "Hero card DaisyUI badge-warning for approximate-location stops"
  - "Compact card orange notification dot on stop number for approximate stops"
  - "Map pins with dashed orange border for approximate delivered/failed stops"
  - "CSS rules: .approx-dot, .approx-badge, position:relative on .stop-number"
affects: [driver-ux, outdoor-testing]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Conditional rendering of location quality indicators based on API boolean field"]

key-files:
  created: []
  modified:
    - apps/kerala_delivery/driver_app/index.html
    - apps/kerala_delivery/driver_app/tailwind.css

key-decisions:
  - "Badge text is exactly 'warning-symbol Approx. location' using DaisyUI badge-warning badge-sm"
  - "Compact card dot is 8px orange circle at top-right of stop number, no text"
  - "Map pins: dashed orange border only for approximate delivered/failed stops (pending already orange)"

patterns-established:
  - "Location quality indicators: boolean-driven conditional rendering in card templates"
  - "Map pin differentiation: border style variation (dashed vs solid) for metadata signaling"

requirements-completed: [APUI-03, APUI-04]

# Metrics
duration: 3min
completed: 2026-03-12
---

# Phase 14 Plan 02: Driver PWA Approximate Location Badge Summary

**DaisyUI warning badge on hero card, orange dot on compact cards, and dashed border on map pins for approximate-location stops**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-12T03:11:25Z
- **Completed:** 2026-03-12T03:14:27Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Hero card renders "Approx. location" DaisyUI badge-warning when stop.location_approximate is true
- Compact cards show 8px orange notification dot at top-right of stop number circle for approximate stops
- Map pins for approximate delivered/failed stops display dashed orange border to signal imprecise pin location
- Tailwind CSS rebuilt to include DaisyUI badge-warning styles (tree-shaken in by new tw:badge classes)
- All indicators are absent when location_approximate is false or missing (null confidence safe)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add hero card badge, compact card dot, CSS, and map pin coloring** - `b9e5698` (feat)
2. **Task 2: Rebuild Tailwind CSS and verify Docker API serves new fields** - `a69e4b8` (chore)

## Files Created/Modified
- `apps/kerala_delivery/driver_app/index.html` - Added approx-badge in renderHeroCard, approx-dot in renderCompactCard, CSS for both indicators, dashed border for approximate map pins in showRouteOnMap
- `apps/kerala_delivery/driver_app/tailwind.css` - Rebuilt with DaisyUI badge-warning styles included

## Decisions Made
- Badge text is exactly "warning-symbol Approx. location" using DaisyUI badge-warning badge-sm -- per user decision in CONTEXT.md
- Compact card dot is 8px orange circle at top-right of stop number with no text -- minimal visual clutter
- Map pins use dashed orange border only for approximate delivered/failed stops; pending stops are already orange so no differentiation needed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Downloaded missing tailwindcss-extra binary**
- **Found during:** Task 2 (CSS rebuild)
- **Issue:** tools/tailwindcss-extra binary not present (tools/ directory did not exist)
- **Fix:** Created tools/ directory and downloaded tailwindcss-extra-linux-x64 binary from GitHub
- **Files modified:** tools/tailwindcss-extra (binary, gitignored)
- **Verification:** CSS build completed successfully, badge styles present in output
- **Committed in:** N/A (binary is gitignored)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Binary download was anticipated in plan instructions as a fallback. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 14 complete: API serves geocode quality fields, Driver PWA displays approximate location indicators
- Physical Android device testing recommended for outdoor contrast validation of badge visibility
- Ready for Phase 15 (if applicable) or next milestone work

## Self-Check: PASSED

All files exist, all commits verified.

---
*Phase: 14-api-confidence-fields-and-driver-pwa-badge*
*Completed: 2026-03-12*
