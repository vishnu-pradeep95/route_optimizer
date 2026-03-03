# Phase 7: Driver PWA Refresh - Context

**Gathered:** 2026-03-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Upgrade the driver PWA so the next delivery is always front-and-center as a hero card, progress is visually tracked via a segmented bar, and the app works reliably in outdoor/field conditions with WCAG AAA contrast. All primary actions must be 60px+ touch targets. Offline reliability is hardened. No new data flows or API endpoints — this is a UI/UX overhaul of the existing single-file PWA.

</domain>

<decisions>
## Implementation Decisions

### Hero card design
- Full-width elevated card taking ~40% of viewport — large saffron-accent border/glow, oversized text, huge Navigate button
- Shows ALL stop info: address (large), distance from current location, customer name (if available), cylinder count, weight, notes, Navigate + Done + Fail buttons
- Label at top: "NEXT DELIVERY · Stop X of Y" — combines intent with position context
- Remaining stops render as a compact list below the hero
- On delivery/fail: brief success/fail toast (~1.5 seconds), then auto-advance — next pending stop smoothly slides into the hero position
- When all stops are complete, hero area shows completion state (existing all-done banner concept)

### Progress & status display
- Segmented progress bar directly below the sticky header — each stop gets its own segment
- Segment colors: green (#00C853) for delivered, red (#FF3B30) for failed, saffron (#FF9410) for next/current, dim for pending
- Header text changes to "X of Y delivered" format
- Below the progress bar: a subtle row with "Last updated: 10:32 AM" on the left, "Refresh" button on the right
- **Bottom summary bar is REMOVED** — hero card + segmented bar + header stats provide all the info the driver needs
- Refresh button reloads route data from server; timestamp updates on successful fetch

### Touch targets & actions
- Navigate button is the largest — 60px+ height (64-68px), full-width saffron, bold text
- Done and Fail buttons at 60px height
- "Call Office" button as a floating action button (FAB) in bottom-right corner — round, phone icon, always visible regardless of scroll position. Uses `tel:` link to dial office number directly
- Fail button triggers a custom dark-themed modal (NOT browser confirm()) matching the app design
- Fail modal includes: big "Yes, Failed" and "Cancel" buttons + optional reason dropdown (not home, refused, wrong address)
- All interactive elements maintain 60px+ touch targets for glove/motion usability

### Outdoor readability (WCAG AAA)
- Dark theme only — no light mode, no theme toggle. AAA-harden the existing dark theme
- Eliminate the "muted" text tier (#4E4D65, ~2.8:1 contrast). Only TWO text hierarchy levels: primary (#F0EFFB) and secondary (bumped to pass 7:1)
- 14px minimum font size everywhere — no 10px labels, no 12px meta text. Hero card text even larger (20-24px address)
- Saffron accent (#FF9410) kept for large elements (buttons, progress bar segments, hero border/glow) where 4.5:1 large-text ratio suffices
- White (#F0EFFB) used for any body-size text that would otherwise be saffron — ensures 7:1 for small text
- All color pairs audited and fixed to meet WCAG AAA: 7:1 for body text, 4.5:1 for large text (18px+ bold or 24px+ regular)

### Claude's Discretion
- Exact animation/transition approach for hero card auto-advance
- Toast notification styling and positioning
- Specific secondary text color value (must pass 7:1 against #0B0B0F)
- FAB size, shadow, and position offsets
- Fail reason dropdown options beyond the three specified
- Loading skeleton design during route fetch
- Exact spacing, padding, and gap values throughout

</decisions>

<specifics>
## Specific Ideas

- Hero card should feel like "mission briefing" — everything the driver needs for the next stop, no scrolling
- Segmented progress bar is inspired by multi-step progress indicators (each stop = one segment, colored by status)
- FAB for Call Office is the panic button — always reachable, one tap to dial
- The app runs on mid-range Android phones in direct Kerala sunlight from a bouncing LPG delivery truck — every design decision prioritizes clarity over aesthetics

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `escapeHtml()` function for XSS prevention — reuse for all innerHTML insertions
- `STORAGE_KEYS` constants and `saveToStorage()`/`loadFromStorage()` helpers — mature offline storage layer
- `queueOfflineUpdate()` / `replayOfflineQueue()` — offline queue already works for status updates
- CSS custom properties (`:root` variables) — color system is centralized, easy to audit/update
- Service worker (`sw.js`) with cache-first strategy — already handles offline app shell

### Established Patterns
- Single-file architecture: all CSS + JS inline in `index.html` (no build step, no framework)
- Optimistic UI: status updates applied locally first, synced to server async
- State management: `currentRoute` global + localStorage persistence
- Template rendering: `innerHTML` with `.map().join('')` (no virtual DOM)
- Dark-first design with CSS custom properties for the color system

### Integration Points
- `renderStopList()` is the main render function — needs to be split into hero card + compact list
- `updateSummary()` manages the bottom summary bar — will be replaced by the segmented progress bar logic
- Header section (`.header`) needs progress bar + refresh row added below it
- `loadRoute()` needs to record "last updated" timestamp on successful fetch
- `markFailed()` currently uses `confirm()` — replace with custom modal
- Office phone number needs to be sourced (likely from `apps/kerala_delivery/config.py` or hardcoded)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-driver-pwa-refresh*
*Context gathered: 2026-03-02*
