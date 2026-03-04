# Phase 10: Driver PWA Hardening - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix safety bugs (GPS leak, alert replacement), consume config endpoint for office phone number, add proper PWA installability icons, complete service worker cache coverage, and gate debug logging. No new features — strictly hardening and cleanup of the existing Driver PWA.

</domain>

<decisions>
## Implementation Decisions

### Debug logging (PWA-06)
- Gate all console.log calls behind a `?debug=1` URL parameter
- When `?debug=1` is present, logs fire normally; otherwise silent
- URL param approach chosen for ease of field debugging — office staff can tell drivers to add `?debug=1` without DevTools

### Claude's Discretion
- **PWA icon design (PWA-04)**: Approach (rendered emoji, custom graphic, etc.), text overlay, color scheme, and generation method. Must produce 192px and 512px PNGs. Static files committed to repo preferred (no-build-step PWA constraint).
- **Debug flag scope**: Whether SW logs (sw.js) are also gated, and whether console.warn calls (GPS errors, storage failures) always show or are gated too. Visual debug indicator (badge) is optional.
- **Offline dialog (PWA-03)**: Recovery flow (retry vs return to upload), styling (match existing fail dialog vs distinct warning style), dismiss behavior (user-action vs auto-dismiss), and whether to audit for other browser-native popups beyond the single alert() at line 1240.
- **Config fetch timing (PWA-01)**: When to fetch `/api/config` (app load vs route load), whether to cache in localStorage for offline, fallback behavior when config fetch fails (hide FAB vs show with error-on-tap), and whether to also consume depot coords from config.
- **GPS leak fix (PWA-02)**: Implementation approach for saving watchPosition ID and calling clearWatch on route reset/page unload — straightforward fix, no ambiguity.
- **SW cache gap (PWA-05)**: Adding `tailwind.css` to APP_SHELL list — straightforward fix, no ambiguity.

</decisions>

<specifics>
## Specific Ideas

No specific requirements — user gave broad discretion across all areas. Follow existing PWA patterns (dark theme, saffron accents, WCAG AAA contrast) and prioritize practical field debugging and driver usability.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- Fail confirmation `<dialog>` already exists in the PWA — reuse its styling/pattern for the offline error dialog
- `saveToStorage()`/`loadFromStorage()` helpers for localStorage operations — use for config caching if needed
- `showToast()` function for transient notifications — potential fallback for config errors

### Established Patterns
- All state stored in localStorage with `STORAGE_KEYS` constants (route data, vehicle ID, offline queue)
- Service worker uses `APP_SHELL` array for pre-caching, `CACHE_VERSION` for cache busting
- Telemetry module handles GPS via `startTelemetry()`/`stopTelemetry()` — GPS fix goes here
- Call Office FAB visibility toggled via `style.display` in multiple places (lines 1147, 1264, 1641)

### Integration Points
- `GET /api/config` endpoint (Phase 9) returns `{ depot_lat, depot_lng, safety_multiplier, office_phone_number }`
- `tel:+919876543210` hardcoded at line 843 — replace href dynamically from config response
- `navigator.geolocation.watchPosition()` at line 1531 — return value must be captured in a variable
- `stopTelemetry()` at line 1542 — must call `navigator.geolocation.clearWatch(watchId)` alongside `clearInterval()`
- `APP_SHELL` array in sw.js line 29 — add `'./tailwind.css'` entry
- `manifest.json` icons array — replace data-URI SVG with paths to committed PNG files

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-driver-pwa-hardening*
*Context gathered: 2026-03-04*
