---
phase: 07-driver-pwa-refresh
plan: 02
subsystem: ui
tags: [pwa, hero-card, toast, dialog, fab, offline, service-worker]

# Dependency graph
requires:
  - phase: 07-driver-pwa-refresh/07-01
    provides: WCAG AAA design tokens, progress bar, touch targets, escapeHtml, updateProgressBar, updateHeaderStats, checkAllDone
provides:
  - Hero card rendering for next pending delivery stop
  - Compact card list for remaining stops
  - Auto-advance with toast feedback on delivery actions
  - Dark-themed fail confirmation dialog (replaces browser confirm)
  - Call Office floating action button with tel: link
  - Service worker cache v4 for deployment
affects: [07-03-driver-pwa-refresh]

# Tech tracking
tech-stack:
  added: [native-dialog-element]
  patterns: [hero-card-compact-list-split, toast-then-auto-advance, dialog-showModal]

key-files:
  created: []
  modified:
    - apps/kerala_delivery/driver_app/index.html
    - apps/kerala_delivery/driver_app/sw.js

key-decisions:
  - "Hero card + compact list architecture: only the next pending stop gets action buttons, remaining stops are read-only compact cards"
  - "Toast-then-advance pattern: 1.5s toast display before re-render auto-advances next stop into hero position"
  - "Native <dialog> element with showModal() replaces browser confirm() for fail action -- dark-themed, accessible, supports backdrop click dismiss"
  - "FAB and dialog HTML placed before main <script> block to ensure DOM availability for event listeners"

patterns-established:
  - "Hero card pattern: prominent first-pending stop with full actions, compact read-only list for the rest"
  - "Toast feedback: showToast(message, type) creates centered animated overlay with 1.5s auto-dismiss"
  - "Dialog modal: native <dialog> with showModal() for confirmations, styled to match dark theme"

requirements-completed: [PWA-01, PWA-04, PWA-06]

# Metrics
duration: 5min
completed: 2026-03-03
---

# Phase 7 Plan 2: Hero Card + Fail Modal + Call Office FAB Summary

**Hero card/compact list stop rendering with toast auto-advance, dark-themed fail dialog replacing confirm(), and Call Office FAB**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-03T12:32:40Z
- **Completed:** 2026-03-03T12:37:48Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Restructured flat stop list into hero card (next pending) + compact card list (remaining stops) with auto-advance
- Added toast notification system with 1.5s centered feedback on delivery/fail actions before auto-advancing
- Replaced browser confirm() with dark-themed native `<dialog>` modal for fail confirmation (reason dropdown, Yes Failed + Cancel buttons)
- Added Call Office floating action button (60px round, fixed bottom-right, tel: link, visible when route loaded)
- Bumped service worker cache from v3 to v4 for deployment cache invalidation
- All new rendering works offline from cached currentRoute data (no new API dependencies)

## Task Commits

Each task was committed atomically:

1. **Task 1: Hero card + compact list rendering with auto-advance and toast** - `8f460a6` (feat)
2. **Task 2: Fail modal dialog + Call Office FAB + service worker cache bump** - `c2ec0aa` (feat)

## Files Created/Modified
- `apps/kerala_delivery/driver_app/index.html` - Hero card CSS + JS, compact card CSS + JS, toast system, fail dialog HTML + CSS + JS, Call Office FAB HTML + CSS, FAB lifecycle management
- `apps/kerala_delivery/driver_app/sw.js` - Bumped CACHE_VERSION from v3 to v4

## Decisions Made
- Hero card + compact list architecture: only the next pending stop gets Navigate/Done/Fail buttons. Remaining stops show only address, meta, and status chip. This keeps the list scannable and focuses driver interaction on one stop at a time.
- Toast-then-advance pattern: updateStatus() shows toast immediately, updates progress bar/header stats, then delays renderStopList() by 1.5s. This gives the driver visual confirmation before the hero card content changes.
- Native `<dialog>` with showModal() replaces browser confirm(). The dialog matches the dark theme, has optional reason dropdown (not_home, refused, wrong_address, access_blocked, other), and supports backdrop click/Esc dismiss via native dialog behavior.
- FAB and dialog HTML placed before the main `<script>` block (not after) to ensure DOM elements exist when event listeners are attached at script evaluation time.
- Placeholder phone number +919876543210 for Call Office FAB -- acceptable for v1.1 single-distributor deployment per RESEARCH.md.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Moved FAB and dialog HTML before script block**
- **Found during:** Task 2 (Fail modal dialog + Call Office FAB)
- **Issue:** Plan specified placing HTML "just before `</body>`" (after `</script>`), but event listeners in the script reference these DOM elements at evaluation time. getElementById() would return null.
- **Fix:** Placed FAB and dialog HTML between the route-view div and the main script block, so DOM elements exist when the script executes.
- **Files modified:** apps/kerala_delivery/driver_app/index.html
- **Verification:** Event listeners correctly attach to existing DOM elements.
- **Committed in:** c2ec0aa (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential fix for correct DOM element availability. No scope creep.

## Issues Encountered
- Verification check `grep -c "confirm(" index.html | grep -q "^0$"` produces false positive on comment text `// replaces browser confirm()`. The actual requirement (no confirm() function calls) is met -- only the comment string matches.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Hero card + compact list + toast + fail dialog + FAB all functional
- Ready for Plan 07-03 (final PWA refinements)
- Call Office FAB uses placeholder phone number (TODO comment in HTML)
- Physical Android device testing still needed for outdoor contrast validation

---
*Phase: 07-driver-pwa-refresh*
*Completed: 2026-03-03*
