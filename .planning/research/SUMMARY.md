# Project Research Summary

**Project:** Kerala LPG Delivery Route Optimizer v1.1 — Polish & Reliability
**Domain:** Logistics SaaS dashboard UI overhaul + driver delivery PWA refresh + geocoding data integrity
**Researched:** 2026-03-01
**Confidence:** HIGH

## Executive Summary

This is a v1.1 polish and reliability milestone on a working logistics system, not a greenfield build. The product is a logistics operations tool for a 13-vehicle LPG delivery fleet in Kerala: a React dashboard for dispatch staff and a vanilla-JS PWA for drivers on Android phones. The v1.1 scope covers three distinct workstreams: (1) migrating the dashboard from prototype-quality custom CSS to a consistent DaisyUI component system, (2) improving the driver PWA for outdoor usability with a simplified next-stop flow, and (3) fixing a critical geocoding cache data integrity bug that causes duplicate map locations. All three workstreams build on a validated, already-deployed stack. Only one new dependency is needed across the entire milestone: `lucide-react` for SVG icons.

The recommended approach is sequential by data dependency. Geocoding normalization must be fixed first because the dashboard UI consumes the geocoding response — building cost-tracking UI on top of inconsistent cache data would waste effort. The backend geocoding enhancements (cost tracking, duplicate detection) come second, providing the new API response fields the dashboard needs. Dashboard UI migration comes third, page-by-page using DaisyUI utility classes with the existing `tw:` prefix to avoid CSS collisions. The driver PWA refresh is fully independent and can proceed in parallel with the dashboard work — it shares no code, no API changes, and no styling system with the React dashboard.

The key risks are all well-understood and preventable. The geocoding bug has a known root cause (two caches using different normalization functions, confirmed at specific code lines) and a direct fix (single `normalize_address()` module). The CSS overhaul has two specific landmines: DaisyUI theme variable collision with the project's existing `--color-*` custom properties, and Tailwind Preflight regressions against existing CSS files. Both are caught by visual inspection before committing component changes. The driver PWA has a silent deployment failure mode (service worker caching stale CSS) that is solved by automating the `CACHE_VERSION` bump. No architectural rewrites are needed — this milestone is about making the existing architecture consistent and reliable.

---

## Key Findings

### Recommended Stack

The existing stack is validated and should not change. The only addition is `lucide-react` (a single `npm install` in the dashboard) for SVG icons to replace the current emoji nav items. All other v1.1 improvements use technologies already installed: DaisyUI 5 component classes (already configured with `tw:` prefix), framer-motion (already installed, currently used only in RunHistory), Python stdlib `unicodedata` for Malayalam Unicode normalization, PostGIS `ST_DWithin` via existing GeoAlchemy2 for spatial duplicate detection, and vanilla JS + CSS for the PWA.

The driver PWA's constraint of no build step is a deliberate architectural decision: it keeps the app as a single cacheable `index.html` for reliable offline operation. This means all CSS must be pre-compiled via the existing `scripts/build-pwa-css.sh` script, and no dynamic Tailwind class names in JavaScript.

**Core technologies:**
- `lucide-react ^0.575.0`: SVG nav icons — only new dependency; tree-shakeable ESM, 1KB/icon, logistics icon set verified (Truck, Route, MapPin, ClipboardList)
- DaisyUI 5.5.19 with `tw:` prefix: all new dashboard UI components — already installed and themed to logistics amber/stone palette
- `core/geocoding/normalize.py` (new module): single `normalize_address()` function — stdlib only (`unicodedata` NFKC + whitespace collapse), eliminates dual-cache key divergence
- PostGIS `ST_DWithin`: duplicate GPS coordinate detection — existing GiST spatial index, O(n log n) vs O(n²) Python loops
- framer-motion 12 (already installed): page transitions and list animations — React 19 compatible, no migration needed

**What NOT to add:** No chart library (no charts in v1.1 scope), no React Router (4 pages with `useState<Page>` is correct), no TanStack Query (4-5 API calls with no polling complexity), no shadcn/ui (conflicts with DaisyUI), no Zustand/Redux (no cross-page shared state), no Workbox (existing hand-written sw.js is sufficient), no IndexedDB (localStorage is nowhere near the 5MB limit at 13 vehicles x ~50 stops), no libpostal (2GB model for a stdlib problem), no Redis (PostGIS cache handles caching at 40-50 addresses/day).

### Expected Features

The research distinguishes sharply between features that fix real problems (P1) versus incremental improvements (P2) versus scope creep. The geocoding normalization bug and dashboard CSS inconsistency are operational problems, not cosmetic — they get P1 treatment.

**Must have (P1 — table stakes and milestone requirements):**
- Unified geocoding cache normalization — fix root cause of duplicate map locations
- Deprecate file-based geocode cache — single source of truth via PostGIS only
- Duplicate GPS coordinate detection — flag orders resolving to same location (warning, not auto-remove)
- Geocoding cost tracking (backend) — cache hit vs API call counters in upload response
- DaisyUI component consistency across all 4 dashboard pages — professional logistics SaaS appearance
- SVG icons replacing emoji nav items — 4 icons, lucide-react
- Loading and empty states for all pages — no blank content areas
- Next-stop hero card in driver PWA — prominent current stop without scrolling
- Visual delivery progress indicator in PWA — "7 of 23 delivered" progress bar
- Pull-to-refresh in driver PWA — visible route reload mechanism
- 60px+ touch target audit — verify all primary actions meet outdoor-use size requirements
- WCAG AAA (7:1) contrast audit — verify all text combinations pass on dark backgrounds

**Should have (P2 — add during v1.1 if time permits):**
- Color-coded status badges on route cards (data already exists, DaisyUI badge is trivial)
- Per-vehicle capacity utilization bar (DaisyUI progress, single formula from `total_weight_kg / 446`)
- Daily summary card on Upload page (aggregate from existing `/api/routes` response)
- Cache migration tool (one-time script, preserves months of historical geocoding)
- Theme switcher light/dark (trivial after DaisyUI consistency is established)
- Auto-advance to next stop after delivery confirmation
- Haptic feedback on delivery confirmation (`navigator.vibrate(50)`, single line)
- Geocoding cost indicator display in ImportSummary UI
- Responsive sidebar with DaisyUI drawer for mobile breakpoint

**Defer to v1.2+:**
- Focus mode (next-stop-only full-screen view) — validate hero card pattern first
- Offline sync queue indicator — after validating queue reliability
- Driver-verified coordinate promotion — wire GPS delivery data to cache
- Fuzzy address matching — HIGH safety risk; false positives could assign wrong coordinates; defer until cache miss rate is measured

**Hard anti-features (never build):**
- Drag-and-drop route reordering — undermines VROOM optimizer, creates sub-optimal routes
- Countdown timers for delivery windows — Kerala MVD compliance prohibition, driver safety risk
- Real-time auto-refresh on all pages — LiveMap polls at 15s (correct); other pages need only a manual refresh button
- Multiple geocoding provider fallback — mixing coordinates from different providers breaks cache consistency
- Photo proof-of-delivery — camera complexity, image upload on Kerala 3G, privacy concerns; GPS verification is sufficient

### Architecture Approach

The v1.1 architecture is three parallel workstreams that touch different layers with one cross-cutting dependency. The geocoding fix (backend Python) produces new API response fields that the dashboard UI (React) displays — this single dependency forces the sequencing. The driver PWA (vanilla JS, different HTML file) is fully isolated. No microservices, no new databases, no new infrastructure. All changes are at the code level within the existing monorepo structure.

**New files created in v1.1:**
1. `core/geocoding/normalize.py` — single `normalize_address()` function, the root-cause fix
2. `infra/alembic/versions/xxx_normalize_geocode_cache.py` — data migration to re-normalize existing rows
3. `src/components/GeocodingStats.tsx` — cache hit/API call breakdown display
4. `src/components/DuplicateLocationAlert.tsx` — duplicate GPS coordinate warning

**New functions in existing files:**
- `core/database/repository.py::find_duplicate_locations()` — PostGIS ST_DWithin spatial query

**Major modifications:**
- `core/geocoding/google_adapter.py` — use `normalize_address()` in `_address_hash()`
- `core/database/repository.py` — use `normalize_address()` in get/save cache methods
- `apps/kerala_delivery/api/main.py` — cost tracking counters, duplicate detection, new `OptimizationSummary` fields
- All 4 dashboard pages (TSX + CSS) — migrate from custom CSS to DaisyUI utility classes; delete CSS files after migration
- `driver_app/index.html` — next-stop UX flow, outdoor readability improvements
- `driver_app/sw.js` — Cache API for route data, BackgroundSync for status updates

**Key patterns to enforce:**
- DaisyUI with `tw:` prefix for all new dashboard UI (pattern already established and verified working)
- Single normalization module imported everywhere address comparison occurs — never inline
- PostGIS for spatial queries, never Python distance math
- Driver PWA stays monolithic HTML — no file splitting (would break offline cache)
- One page migration per commit — visual verification between each, no big-bang CSS rewrite

### Critical Pitfalls

1. **Dual geocoding cache normalization mismatch** — Fix by creating `core/geocoding/normalize.py` as the single normalization source; update both `google_adapter.py` (line 195) and `repository.py` (line 741) to import from it; run Alembic migration to re-normalize existing `address_norm` values; deprecate the file cache entirely to avoid the two-cache drift problem persisting.

2. **Service worker caching stale PWA CSS** — Every change to `driver_app/index.html` or `tailwind.css` must be accompanied by a `CACHE_VERSION` bump in `sw.js`. Silent failure: drivers see old UI indefinitely with no errors. Automate via a CI step that fails if `index.html` changed but SW version did not.

3. **Competing CSS design systems in the dashboard** — DaisyUI and the project's 20+ `--color-*` custom properties both define semantic colors. Fix before building any new components: make DaisyUI semantic tokens authoritative; refactor existing CSS to alias them (`--color-accent: var(--color-primary)`). Never allow both systems to independently define the same semantic color.

4. **Duplicate location detection false positives** — A flat 50m proximity threshold flags legitimate separate deliveries in dense Vatakara streets. Use confidence-weighted thresholds: ROOFTOP results flag within 10m, RANGE_INTERPOLATED within 25m, GEOMETRIC_CENTER within 100m, APPROXIMATE never. Present as warnings, not automatic removals.

5. **Leaflet requires CSP `style-src 'unsafe-inline'` permanently** — Do not remove this during the UI overhaul. Leaflet uses `element.style.transform` and inline style attributes for positioning map overlays (confirmed open issue Leaflet/Leaflet#9168, no fix available). Add a code comment at `main.py` line 256 explaining this so it is not "cleaned up" later.

---

## Implications for Roadmap

Based on the dependency analysis in the research, the workstreams must be sequenced to respect the API contract: geocoding backend changes produce the fields that the dashboard UI consumes. Four phases are recommended.

### Phase 1: Geocoding Cache Normalization Fix

**Rationale:** This is the only true foundation phase — its output (consistent `address_norm` keys) is a prerequisite for accurate cost tracking and meaningful duplicate warnings. Building UI features on top of inconsistent geocoding data wastes effort. This phase also has the highest correctness risk (data migration of existing rows) and should be validated before UI work begins.

**Delivers:** Unified `normalize_address()` function in `core/geocoding/normalize.py`, updated `google_adapter.py` and `repository.py`, Alembic migration for existing `address_norm` values, file cache deprecated or migrated, unit tests for normalization consistency.

**Addresses (P1 features):** Unified cache normalization, deprecate file-based cache.

**Avoids:** Pitfall 1 (dual-cache mismatch), Pitfall 10/PITFALLS (file cache not cleared), Pitfall 11/PITFALLS (cost tracking counts wrong cache layer).

**Research flag:** No deeper research needed. Root cause is fully diagnosed to specific code lines. `normalize_address()` is stdlib-only. Alembic migration pattern is established in the codebase.

---

### Phase 2: Geocoding Enhancements (Backend)

**Rationale:** Builds directly on Phase 1's consistent normalization. Cost tracking counters and duplicate detection both require the cache to behave consistently before their counts are meaningful. This phase closes out the entire backend geocoding workstream and produces the updated `OptimizationSummary` response shape that Phase 3 (dashboard) will consume.

**Delivers:** `geocode_cache_hits` and `geocode_api_calls` fields in upload response, `find_duplicate_locations()` in repository using PostGIS `ST_DWithin`, `DuplicateGroup` Pydantic model, updated `OptimizationSummary`, updated `dashboard/types.ts`.

**Addresses (P1 features):** Duplicate GPS coordinate detection, geocoding cost tracking (backend), file cache deprecation finalized.

**Avoids:** Pitfall 8/PITFALLS (duplicate detection false positives — implement confidence-weighted thresholds here, not flat distance matching).

**Research flag:** No deeper research needed. PostGIS ST_DWithin and Pydantic model extension are well-documented. The only judgment call is the confidence-weighted threshold values — use ROOFTOP=10m, RANGE_INTERPOLATED=25m, GEOMETRIC_CENTER=100m, APPROXIMATE=skip.

---

### Phase 3: Dashboard UI Overhaul

**Rationale:** Depends on Phase 2 for the `GeocodingStats` and `DuplicateLocationAlert` components, which consume new API response fields. The remaining page migrations (LiveMap, RunHistory, FleetManagement) are independent of the geocoding work and can be worked in parallel within the phase. The page-by-page migration strategy avoids visual regression — one page per commit, CSS file deleted after visual verification.

**Delivers:** All 4 pages migrated to DaisyUI utility classes with `tw:` prefix; emoji icons replaced with lucide-react SVGs; loading and empty states for all pages; GeocodingStats and DuplicateLocationAlert components wired to new API fields; all per-page CSS files deleted after migration.

**Addresses (P1 features):** DaisyUI consistency, SVG icons, loading/empty states, geocoding cost indicator (UI), duplicate location warning display.

**Addresses (P2 features if time permits):** Color-coded status badges, capacity utilization bars, daily summary card, theme switcher.

**Avoids:** Pitfall 2 (CSS variable collision — verify DevTools `:root` before first component), Pitfall 5 (CSP `'unsafe-inline'` — document, do not remove), Pitfall 6 (competing design systems — make DaisyUI tokens authoritative first), Pitfall 9 (Preflight regressions — visual diff before any component work).

**Recommended internal order:** (1) Unify color token system (DaisyUI as source of truth), (2) Replace emoji icons in App.tsx, (3) Migrate UploadRoutes + add GeocodingStats + DuplicateLocationAlert, (4) Migrate LiveMap, (5) Migrate RunHistory, (6) Migrate FleetManagement, (7) Clean up sidebar/drawer patterns.

**Research flag:** No deeper research needed. The `tw:` prefix is already configured and verified working in the project. DaisyUI component migration is mechanical.

---

### Phase 4: Driver PWA Refresh

**Rationale:** Fully independent of Phases 1-3 (different tech stack, different HTML file, no shared API changes). Can run in parallel with Phase 3 if two developers are available. Listed as Phase 4 for single-developer sequencing — completing the backend and dashboard first means the PWA refresh is the sole focus with no context-switching between React and vanilla JS.

**Delivers:** Next-stop hero card at top of stop list, delivery progress bar ("7 of 23"), pull-to-refresh button with last-updated timestamp, 60px+ touch target audit and fixes, WCAG AAA contrast audit and fixes, enhanced offline (route data in Cache API not just localStorage), BackgroundSync for status updates, service worker cache version automation.

**Addresses (P1 features):** Next-stop hero card, progress indicator, pull-to-refresh, touch target audit, contrast audit.

**Addresses (P2 features if time permits):** Auto-advance after delivery confirmation, haptic feedback (`navigator.vibrate(50)`, one line).

**Avoids:** Pitfall 3/PITFALLS (PWA dead CSS — decide on DaisyUI adoption vs removal before visual work starts), Pitfall 4 (stale SW cache — automate CACHE_VERSION bump), Pitfall 7 (no-build-step Tailwind — no dynamic class names in JS).

**Critical constraint:** PWA must remain a single monolithic `index.html` with no build step. No external JS files. No splitting CSS into multiple files. The monolithic structure is the offline architecture — splitting files requires updating `APP_SHELL` in sw.js and risks cache miss on a split file breaking offline mode entirely.

**Research flag:** Physical Android device testing required for outdoor contrast validation before declaring the contrast audit complete. Browser DevTools cannot replicate direct Kerala sunlight on a mobile screen.

---

### Phase Ordering Rationale

- **Geocoding first** because it is a data integrity fix, not a UI concern. Two cache layers with different normalization have been producing inconsistent data since v1.0. Every day this goes unfixed adds to the migration scope.
- **Backend enhancements before frontend** because the `OptimizationSummary` response model is the API contract. Dashboard types.ts must reflect the final response shape before building UI components that consume new fields.
- **Dashboard third** because it is the largest workstream by file count but has no blocking dependencies after Phase 2 completes. Page-by-page migration avoids coordinating with other changes.
- **PWA fourth (or parallel)** because it is fully isolated. Putting it last in single-developer sequencing avoids context-switching between two frontend paradigms.

### Research Flags

Phases needing deeper research during planning:
- **Phase 4 (PWA contrast audit):** Physical Android device required for outdoor testing. Plan for in-field testing or coordinate with an actual driver before declaring the audit done.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Normalization fix):** Root cause fully diagnosed. stdlib only. Write the code.
- **Phase 2 (Backend enhancements):** PostGIS ST_DWithin and Pydantic model extension are well-documented. Only judgment call is confidence thresholds — captured above.
- **Phase 3 (Dashboard UI):** DaisyUI 5 with `tw:` prefix is already working in the project. Migration is mechanical.
- **Phase 4 (PWA refresh JS/CSS):** Vanilla JS state machine and CSS variables are well-understood. No unknowns beyond physical device testing.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Codebase directly analyzed. Only new dependency (lucide-react) is npm-verified at v0.575.0. All others are existing working dependencies with confirmed version compatibility. |
| Features | HIGH | Geocoding bug root-caused to specific code lines in google_adapter.py:195 and repository.py:741. Industry patterns cross-referenced against DispatchTrack, Routific, and delivery app UX research. |
| Architecture | HIGH | All file paths, function names, and line numbers verified against actual codebase. No inferred architecture — direct inspection throughout. Build order derived from actual data flow. |
| Pitfalls | HIGH | CSS variable prefix bug is a confirmed open GitHub issue (tailwindlabs/tailwindcss#16441). Leaflet CSP requirement is a confirmed open GitHub issue (Leaflet/Leaflet#9168). Dual normalization bug is code-verified at specific lines. |

**Overall confidence: HIGH**

### Gaps to Address

- **Confidence-weighted duplicate detection thresholds:** The 10m/25m/100m thresholds for ROOFTOP/RANGE_INTERPOLATED/GEOMETRIC_CENTER are reasonable estimates. Validate against the actual `geocode_cache` table — check the distribution of `location_type` values for Kerala addresses. Adjust based on observed false-positive rate in the first test batch.
- **PWA outdoor contrast validation:** WCAG 7:1 contrast ratios are mathematically verifiable but do not account for sunlight conditions. The saffron-on-dark palette was designed for outdoor use but any color changes must be tested on a physical device. Plan for in-field sign-off.
- **File cache migration scope:** The size and entry count of `data/geocode_cache/google_cache.json` are not known from research. If it contains months of unique Kerala addresses not yet in the DB cache, migration is worth running. If it is small or stale, deleting it is faster. Check file size before Phase 1 begins.
- **DaisyUI oklch vs hex visual parity:** DaisyUI's oklch color values and the existing hex `#D97706` amber are not visually identical. Plan for one design review session after the first page migration to verify the custom logistics theme tokens produce the correct colors.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `core/geocoding/google_adapter.py` line 195 — file cache normalization (`" ".join(address.lower().split())`)
- Direct codebase inspection: `core/database/repository.py` line 741 — DB cache normalization (`address_raw.strip().lower()`) — normalization bug confirmed here
- Direct codebase inspection: `apps/kerala_delivery/driver_app/sw.js` — CACHE_VERSION v3, APP_SHELL pre-cache list
- Direct codebase inspection: `apps/kerala_delivery/driver_app/index.html` — monolithic ~51KB, inline CSS and JS architecture
- Direct codebase inspection: `apps/kerala_delivery/driver_app/pwa-input.css` and `tailwind.css` — dead CSS confirmed
- Direct codebase inspection: `apps/kerala_delivery/dashboard/src/index.css` — DaisyUI `@import "tailwindcss" prefix(tw)` configuration, 20+ `--color-*` custom properties
- Direct codebase inspection: `apps/kerala_delivery/api/main.py` line 256 — CSP config, lines 852-898 — geocoding loop structure
- [PostGIS ST_DWithin docs](https://postgis.net/docs/ST_DWithin.html) — spatial proximity query with GiST index
- [Python unicodedata docs](https://docs.python.org/3/library/unicodedata.html) — NFKC normalization for Malayalam script
- [DaisyUI 5 Components](https://daisyui.com/components/) — Stat, Table, Badge, Skeleton, Steps, Alert, Toast, Modal verified available
- [MDN Screen Wake Lock API](https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API) — 95%+ Android support confirmed
- [lucide-react npm](https://www.npmjs.com/package/lucide-react) — v0.575.0, 10.3k+ dependents, ESM tree-shaking

### Secondary (MEDIUM confidence)
- [Tailwind v4 CSS variable prefix bug — tailwindlabs/tailwindcss#16441](https://github.com/tailwindlabs/tailwindcss/issues/16441) — confirmed open issue, workaround documented
- [Leaflet CSP unsafe-inline — Leaflet/Leaflet#9168](https://github.com/Leaflet/Leaflet/issues/9168) — confirmed open issue, no fix available
- [AddressHub: Caching Geocoding Results](https://address-hub.com/address-intelligence/caching/) — cache normalization strategies, 10-20ms cache vs 100-300ms API
- [DispatchTrack Mobile App UX](https://www.dispatchtrack.com/blog/mobile-app-ui-ux/) — driver app redesign patterns, outdoor readability
- [Last-Mile Delivery Driver App UX (zigpoll)](https://www.zigpoll.com/content/how-can-our-ux-designers-optimize-the-mobile-app-interface-to-reduce-delivery-time-errors-and-improve-driver-efficiency-for-lastmile-logistics) — next-stop workflow, one-handed operation, bottom thumb zone
- [Radar: Complete Guide to Geocoding APIs](https://radar.com/blog/geocoding-apis) — normalize before provider calls, deduplication best practices
- [Deduplicate Location Records (Towards Data Science)](https://towardsdatascience.com/deduplicate-and-clean-up-millions-of-location-records-abcffb308ebf/) — geospatial duplicate detection patterns
- [PWA Offline-First Strategies (MagicBell)](https://www.magicbell.com/blog/offline-first-pwas-service-worker-caching-strategies) — Cache API vs localStorage, BackgroundSync patterns
- [MDN prefers-contrast media query](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-contrast) — browser support, implementation

### Tertiary (LOW confidence — needs validation)
- [Lucide bundle benchmark 2026](https://medium.com/codetodeploy/the-hidden-bundle-cost-of-react-icons-why-lucide-wins-in-2026-1ddb74c1a86c) — tree-shaking comparison (single article, verify independently)
- [PWA Best Practices 2026 (Wirefuture)](https://wirefuture.com/post/progressive-web-apps-pwa-best-practices-for-2026) — general offline-first patterns

---
*Research completed: 2026-03-01*
*Ready for roadmap: yes*
