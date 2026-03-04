---
phase: 11-dashboard-cleanup
plan: 01
subsystem: ui
tags: [css, design-tokens, typescript, react, dashboard]

# Dependency graph
requires:
  - phase: 06-dashboard-ui-overhaul
    provides: Dashboard CSS design tokens and StatusBadge component
provides:
  - Clean CSS design tokens with no dead aliases
  - Token-driven muted color (.text-muted-30 via --color-text-faint)
  - Complete RouteDetail TypeScript interface (total_weight_kg, total_items)
  - Exhaustive switch-based StatusBadge (DASH-04 decision)
  - Type-safe StatusBadge usage in RunHistory (no unsafe casts)
  - Token-driven danger color in RunHistory (var(--color-danger))
affects: [dashboard, types]

# Tech tracking
tech-stack:
  added: []
  patterns: [exhaustive-switch-with-never, css-design-tokens]

key-files:
  created: []
  modified:
    - apps/kerala_delivery/dashboard/src/index.css
    - apps/kerala_delivery/dashboard/src/types.ts
    - apps/kerala_delivery/dashboard/src/pages/RunHistory.tsx
    - apps/kerala_delivery/dashboard/src/components/StatusBadge.tsx

key-decisions:
  - "StatusBadge uses exhaustive switch with never-typed default (per DASH-04 user decision)"
  - "New --color-text-faint token (Stone 400) for subtle text, preserving existing visual appearance"

patterns-established:
  - "Exhaustive switch: use never type assertion in default case for compile-time safety on union types"
  - "Design tokens: all colors in .text-muted-* classes must reference CSS variables, not hardcoded hex"

requirements-completed: [DASH-01, DASH-02, DASH-03, DASH-04]

# Metrics
duration: 2min
completed: 2026-03-04
---

# Phase 11 Plan 01: Dashboard CSS/TS Cleanup Summary

**Dead CSS aliases removed, .text-muted-30 tokenized via --color-text-faint, StatusBadge refactored to exhaustive switch, RouteDetail type completed, RunHistory type-cast and hardcoded color eliminated**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-04T03:01:50Z
- **Completed:** 2026-03-04T03:03:53Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Removed 3 dead legacy CSS alias variables (--color-bg, --color-text, --color-primary) from :root without touching the DaisyUI theme --color-primary (oklch)
- Added --color-text-faint design token and updated .text-muted-30 to reference it instead of hardcoded hex
- Refactored StatusBadge from Record lookups to exhaustive switch with never-typed default (DASH-04)
- Added total_weight_kg and total_items to RouteDetail interface, matching RouteSummary
- Removed unsafe `as` type cast in RunHistory.tsx StatusBadge usage
- Replaced hardcoded #dc2626 with var(--color-danger) token in RunHistory.tsx

## Task Commits

Each task was committed atomically:

1. **Task 1: Dead CSS token removal and .text-muted-30 tokenization** - `11a68b2` (refactor)
2. **Task 2: StatusBadge exhaustive switch, RouteDetail type fix, RunHistory cast removal and color fix** - `4c687c3` (feat)

## Files Created/Modified
- `apps/kerala_delivery/dashboard/src/index.css` - Removed dead aliases, added --color-text-faint token, tokenized .text-muted-30
- `apps/kerala_delivery/dashboard/src/types.ts` - Added total_weight_kg and total_items to RouteDetail
- `apps/kerala_delivery/dashboard/src/components/StatusBadge.tsx` - Refactored to exhaustive switch (DASH-04)
- `apps/kerala_delivery/dashboard/src/pages/RunHistory.tsx` - Removed unsafe cast, replaced hardcoded color with design token

## Decisions Made
- StatusBadge uses exhaustive switch with `never` type assertion in default case (per DASH-04 user decision) -- ensures compile-time failure if a new status is added to BadgeStatus without handling it
- Created --color-text-faint token using Stone 400 (#A8A29E) to preserve existing visual appearance of .text-muted-30

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Dashboard CSS is now fully token-driven with no dead aliases
- TypeScript types are complete and StatusBadge is type-safe
- Ready for 11-02 plan execution

## Self-Check: PASSED

All 5 files found. Both task commits (11a68b2, 4c687c3) verified in git log.

---
*Phase: 11-dashboard-cleanup*
*Completed: 2026-03-04*
