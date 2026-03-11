---
phase: 11-foundation-fixes
plan: 03
subsystem: ui, driver-pwa
tags: [driver-pwa, dual-address, cdcms, navigation, google-maps, xss]

# Dependency graph
requires:
  - phase: 11-02
    provides: "API response includes address_raw field for unprocessed CDCMS text"
provides:
  - "Hero card dual-address display: cleaned address (22px primary) + raw CDCMS text (13px muted monospace secondary)"
  - "Compact card dual-address display: cleaned address (primary) + raw CDCMS text (11px muted secondary)"
  - "Coordinate-based navigation with address text fallback"
  - "Graceful null handling for pre-v2.2 routes (address_raw hidden when null)"
affects: [phase-12, phase-13]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "address_raw conditional rendering: ternary hides div when null/undefined"
    - "encodeURIComponent for safe inline JS string passing in onclick attributes"
    - "navigateTo(lat, lon, address) three-arg pattern: coords primary, address fallback"

key-files:
  created: []
  modified:
    - "apps/kerala_delivery/driver_app/index.html"

key-decisions:
  - "Used encodeURIComponent/decodeURIComponent for safe address passing in onclick attributes (avoids quote escaping issues)"
  - "Raw address uses monospace font (JetBrains Mono / Courier New) to visually distinguish from cleaned address"
  - "Coordinates are primary navigation destination; address text used only as fallback when coords are missing/zero"

patterns-established:
  - "Dual-address display: cleaned as primary, raw CDCMS as secondary muted monospace"
  - "navigateTo three-arg call: navigateTo(lat, lon, address)"

requirements-completed: [ADDR-01]

# Metrics
duration: 2min
completed: 2026-03-11
---

# Phase 11 Plan 03: Driver PWA Dual-Address Display Summary

**Dual-address hero/compact cards showing cleaned CDCMS address (primary) and raw ALL-CAPS CDCMS text (secondary monospace), with coordinate-based Google Maps navigation**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-11T11:15:39Z
- **Completed:** 2026-03-11T11:17:55Z
- **Tasks:** 2 (1 auto + 1 auto-approved checkpoint)
- **Files modified:** 1

## Accomplishments
- Hero card now shows cleaned address at 22px (primary) with raw CDCMS text at 13px muted monospace below it (secondary)
- Compact cards show the same dual-address pattern with raw text at 11px
- Raw address div gracefully hidden when address_raw is null (pre-v2.2 routes without address_original)
- All address_raw rendering protected by escapeHtml() to prevent XSS
- navigateTo() updated to accept address as fallback: coordinates are primary (precise routing), address text used only when coords are missing/zero
- CSS classes hero-address-raw and compact-address-raw use JetBrains Mono / Courier New to visually distinguish raw CDCMS text from cleaned addresses

## Task Commits

Each task was committed atomically:

1. **Task 1: Update PWA dual-address display and navigate button** - `b786f25` (feat) - CSS, hero card, compact card, and navigateTo updates
2. **Task 2: Visual verification (auto-approved)** - checkpoint auto-approved in auto mode

## Files Created/Modified
- `apps/kerala_delivery/driver_app/index.html` - Added hero-address-raw/compact-address-raw CSS classes, dual-address rendering in hero and compact card templates, updated navigateTo to three-arg pattern with address fallback

## Decisions Made
- Used encodeURIComponent/decodeURIComponent for safe address passing in onclick attributes -- avoids quote escaping fragility with special characters in Kerala addresses
- Raw CDCMS text uses monospace font (JetBrains Mono fallback to Courier New) at reduced opacity to visually distinguish from cleaned address
- Coordinates remain primary navigation destination per user decision; address text is fallback only

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Full Phase 11 deliverable is complete: CDCMS address cleaning pipeline (Plan 01), address_display bug fix + address_original storage (Plan 02), and dual-address Driver PWA display (Plan 03)
- Drivers can now see both cleaned readable addresses and original CDCMS text for cross-referencing with paper delivery lists
- Navigate button uses coordinates for precise routing instead of address text
- Ready for Phase 12 (dictionary coverage) and Phase 13 (geocoding improvements)

## Self-Check: PASSED

- FOUND: apps/kerala_delivery/driver_app/index.html
- FOUND: .planning/phases/11-foundation-fixes/11-03-SUMMARY.md
- FOUND: b786f25 (Task 1 commit)

---
*Phase: 11-foundation-fixes*
*Completed: 2026-03-11*
