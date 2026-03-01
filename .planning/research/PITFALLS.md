# Pitfalls Research

**Domain:** Logistics delivery route optimizer -- v1.1 milestone (Dashboard UI overhaul, Driver PWA refresh, Geocoding cache normalization)
**Researched:** 2026-03-01
**Confidence:** HIGH (codebase-verified, official docs cross-referenced)

---

## Critical Pitfalls

### Pitfall 1: Dual Geocoding Cache Normalization Mismatch

**What goes wrong:**
The system has two independent geocoding caches that normalize addresses differently. The `GoogleGeocoder` file cache (`core/geocoding/google_adapter.py` line 195) normalizes as `" ".join(address.lower().split())` -- which collapses all whitespace (tabs, double spaces, newlines) into single spaces. The PostGIS database cache (`core/database/repository.py` line 741) normalizes as `address_raw.strip().lower()` -- which only strips leading/trailing whitespace but preserves internal whitespace patterns. For the address `"Near SBI,  MG Road"` (two spaces), the file cache produces hash of `"near sbi, mg road"` (one space) while the DB cache stores `"near sbi,  mg road"` (two spaces). The same address gets geocoded twice via Google API (wasting money) and stored with potentially different coordinates if Google returns slightly different results on different days. Worse: the CDCMS export may have trailing tabs or inconsistent spacing, causing the same customer to appear as two separate map pins.

**Why it happens:**
The file cache was built first as a development convenience (zero infrastructure). The PostGIS cache was added later with its own normalization logic. Nobody unified the normalization because both caches worked independently. The CachedGeocoder decorator checks PostGIS first, then falls through to GoogleGeocoder which checks its own file cache -- but the two caches use different keys for the same address.

**How to avoid:**
Extract a single `normalize_address()` function into `core/geocoding/interfaces.py` that both caches use. The correct normalization is: `" ".join(address.lower().split())` (the file cache version) because it handles all whitespace variants. Update `repository.py` lines 741 and 789 to use this shared function. Then run a one-time migration to re-normalize all existing `address_norm` values in the `geocode_cache` table. Consider deprecating the file cache entirely since the PostGIS cache is production-ready and shared across containers.

**Warning signs:**
- Same customer address appearing as two pins on the map
- Cache hit rate lower than expected (should be 70%+ after first month)
- `geocode_batch.py --dry-run` reports cache misses for addresses you know were geocoded before
- `SELECT COUNT(*) FROM geocode_cache` shows more rows than unique delivery addresses

**Phase to address:** Geocoding fixes phase -- must be the first task before duplicate detection or cost tracking, because both depend on consistent normalization.

---

### Pitfall 2: Tailwind v4 CSS Variable Collision With Existing Design Tokens

**What goes wrong:**
Tailwind CSS v4 auto-generates CSS custom properties on `:root` using the `--color-*` namespace (e.g., `--color-red-500`, `--color-base-100`). The dashboard's `index.css` already defines 20+ custom properties using the same namespace: `--color-surface`, `--color-accent`, `--color-success`, `--color-danger`, `--color-border`, etc. The project already uses `prefix(tw)` in the CSS import (`@import "tailwindcss" prefix(tw)`), which namespaces Tailwind's utility classes as `tw-*`. However, there is a known Tailwind v4 bug ([tailwindlabs/tailwindcss#16441](https://github.com/tailwindlabs/tailwindcss/issues/16441)) where CSS variable references inside prefixed contexts do not get the prefix applied. For example, a DaisyUI theme variable `--color-background: var(--color-black)` in a `prefix(tw)` context generates `--tw-color-background: var(--color-black)` instead of the correct `--tw-color-background: var(--tw-color-black)`. This causes DaisyUI theme colors to silently fall back to the project's existing `--color-*` values instead of DaisyUI's intended colors, producing a confusing visual mismatch.

**Why it happens:**
The `prefix()` function in Tailwind v4 adds the prefix to variable declarations but not to `var()` references within those declarations. This is a confirmed bug in the Tailwind v4 variable resolution pipeline. Developers see the prefix working on class names and assume variables are equally safe.

**How to avoid:**
The project's existing approach is correct: `@import "tailwindcss" prefix(tw)` prevents class-level collisions. For the variable reference bug, verify in DevTools that DaisyUI's oklch theme variables resolve correctly. If the custom logistics theme's `--color-primary: oklch(62% 0.17 65)` is being read instead of DaisyUI's computed value, explicitly re-declare the affected DaisyUI variables in the custom theme block. Also verify that the existing `--color-accent: #D97706` in `index.css` does not shadow the DaisyUI `--color-accent: oklch(62% 0.17 65)` from the custom theme -- both exist in the current codebase and the cascade order determines which wins.

**Warning signs:**
- DaisyUI components render with hex colors (#D97706) instead of oklch values
- DevTools shows two `--color-accent` declarations on `:root` from different sources
- Alert components (`tw-alert-success`) show the wrong green shade
- DaisyUI theme switcher has no effect because project CSS variables override theme values

**Phase to address:** Dashboard UI overhaul -- verify CSS variable isolation immediately after any DaisyUI theme changes, before building any new components.

---

### Pitfall 3: PWA Compiled CSS Ships DaisyUI Default Theme Instead of Custom Theme

**What goes wrong:**
The driver PWA's `pwa-input.css` imports Tailwind and DaisyUI (`@import "tailwindcss" prefix(tw); @plugin "daisyui";`) but does NOT include the custom logistics theme defined in the dashboard's `index.css`. The compiled `tailwind.css` output (verified in codebase) contains DaisyUI's default light theme with blue/pink/teal colors (oklch values like `--color-primary: oklch(45% .24 277.023)`) -- not the project's amber/stone logistics theme. Additionally, the PWA's `index.html` uses zero `tw-` prefixed classes -- it uses custom CSS classes like `.header`, `.stop-list`, `.upload-btn`. This means the compiled Tailwind/DaisyUI CSS is entirely dead code shipped to every driver's phone, adding ~50KB of unused CSS to the PWA bundle while providing no visual benefit.

**Why it happens:**
The PWA CSS build was set up during v1.0 as infrastructure preparation but never actually integrated into the HTML. The `build-pwa-css.sh` script compiles the CSS, but since the HTML only uses hand-written CSS classes and inline styles, none of the Tailwind/DaisyUI classes are tree-shaken in. Tailwind v4 normally tree-shakes unused classes, but DaisyUI component styles are included wholesale by the plugin.

**How to avoid:**
Two valid approaches: (1) If the PWA refresh will adopt DaisyUI classes, copy the custom logistics theme (or a dark-mode variant) from `dashboard/src/index.css` into `pwa-input.css` so both apps share the same design tokens. Migrate PWA HTML to use `tw-` prefixed DaisyUI classes alongside existing custom CSS. (2) If the PWA will remain hand-styled (likely better for the no-build-step constraint), remove the Tailwind/DaisyUI import from `pwa-input.css` entirely and delete the compiled `tailwind.css` to avoid shipping dead CSS. The PWA's existing custom CSS (saffron accent, dark background) works well for outdoor readability and does not need DaisyUI.

**Warning signs:**
- Driver PWA loads two CSS files (tailwind.css + inline styles) but only the inline styles affect appearance
- PWA file size grows without visual changes
- Theme colors in the PWA don't match the dashboard
- Lighthouse performance audit flags unused CSS

**Phase to address:** Driver PWA refresh -- decide the CSS strategy (adopt DaisyUI or remove it) before any visual work begins.

---

### Pitfall 4: Service Worker Caches Stale CSS After PWA Refresh

**What goes wrong:**
The driver PWA's service worker (`sw.js`) uses a `CACHE_VERSION = 'v3'` constant to manage the cache lifecycle. The app shell includes `'./index.html'` in the pre-cache list. When PWA visual refresh changes are made to the inline styles in `index.html` or to `tailwind.css`, the service worker must be updated (version bumped) for drivers to receive the new styles. If `CACHE_VERSION` is not bumped, the service worker byte-check sees no change, the old cache persists, and installed PWA users see the old UI indefinitely. The `skipWaiting()` and `clients.claim()` calls in the current SW mean updates ARE applied immediately when detected -- but detection requires the SW file itself to change.

Critically, this is a silent failure. Drivers do not see errors. They simply see the old UI. If the PWA refresh includes critical changes like improved outdoor readability or larger touch targets, drivers in the field continue using the old, harder-to-read interface. There is no "check for updates" button in the current PWA.

**Why it happens:**
PWA cache invalidation is counterintuitive. Developers test in Chrome DevTools with "Update on reload" enabled, which bypasses the service worker lifecycle entirely. The CSS update works in dev, gets deployed, but installed PWAs don't receive it. This is the most commonly reported PWA deployment pitfall.

**How to avoid:**
Create a deploy checklist: every CSS or HTML change to the driver PWA must be accompanied by a `CACHE_VERSION` bump in `sw.js`. Better yet: automate the version bump by including a build timestamp in the cache name (e.g., `const CACHE_NAME = 'lpg-driver-${BUILD_TIMESTAMP}'`). Since the PWA CSS is compiled via `scripts/build-pwa-css.sh`, add a step to that script that updates the cache version automatically. Add an in-app update indicator that checks the SW registration for waiting workers and prompts the driver to refresh.

**Warning signs:**
- Drivers report the PWA "looks the same" after a deploy
- Testing on a freshly installed PWA shows new styles, but existing installs show old ones
- `navigator.serviceWorker.controller` shows old cache version in production
- The `sw.js` file has not changed in a commit that modified `index.html`

**Phase to address:** Driver PWA refresh -- implement cache versioning automation before the first visual change ships to production.

---

### Pitfall 5: Leaflet Inline Styles Require CSP unsafe-inline Permanently

**What goes wrong:**
Leaflet.js uses inline `style` attributes for positioning popups, markers, and map overlays. The CSP in `main.py` line 256 already allows `'unsafe-inline'` for `style-src`. During the UI overhaul, there is a temptation to tighten CSP by removing `'unsafe-inline'` and switching to nonce-based style injection -- especially since Tailwind/DaisyUI classes avoid inline styles. However, Leaflet will break immediately: popups stop positioning correctly, custom div markers (used for numbered route stop markers in the driver PWA, line 1050) fail to render, and the map becomes unusable. This is a confirmed open issue in Leaflet ([Leaflet/Leaflet#9168](https://github.com/Leaflet/Leaflet/issues/9168)) with no fix or workaround available.

**Why it happens:**
Leaflet uses `element.style.transform`, `element.style.left/top`, and `innerHTML` with style attributes for positioning map overlays. These are core to how Leaflet works, not optional features. The Leaflet team has acknowledged this but has not implemented nonce-based style injection. The driver PWA's custom marker HTML (line 1050: `<div style="background:${color};...">`) also relies on inline styles.

**How to avoid:**
Keep `'unsafe-inline'` in `style-src` for as long as Leaflet is used. Document this as a known security trade-off with clear justification. Do NOT attempt to remove it during UI overhaul -- it is not a cleanup target. If strict CSP is required in the future, the alternative is to replace Leaflet with MapLibre GL JS (which uses WebGL canvas rendering instead of DOM manipulation), but that is a significant migration not in scope for v1.1.

**Warning signs:**
- Map popups stop appearing after a CSP change
- Console shows `Refused to apply inline style` errors
- Route stop markers render as plain text without colored circles
- Map panning feels broken (transforms not applied)

**Phase to address:** Dashboard UI overhaul -- explicitly document that `style-src 'unsafe-inline'` is required and must NOT be removed. Add a code comment at line 256 explaining why.

---

### Pitfall 6: Dashboard UI Overhaul Creates Two Competing Design Systems

**What goes wrong:**
The dashboard currently has a complete, hand-crafted design system in `index.css` (20+ CSS custom properties for surfaces, accents, text, borders, spacing, radii, shadows, typography) plus 9 component-specific CSS files (`App.css`, `UploadRoutes.css`, `LiveMap.css`, etc.). DaisyUI introduces a second, overlapping design system with its own semantic color tokens (`--color-base-100`, `--color-primary`, `--color-neutral`). During the overhaul, developers mix both: some components use `var(--color-accent)` (project) while new components use `tw-bg-primary` (DaisyUI). The result is a codebase with two incompatible color systems where changing the project's `--color-accent` does not update DaisyUI components, and changing the DaisyUI theme does not update legacy components. Visual consistency becomes impossible to maintain.

**Why it happens:**
Incremental migration is natural: you start using DaisyUI classes for new features while leaving existing components alone. The custom logistics theme in `index.css` maps DaisyUI's semantic colors to the project's palette (e.g., `--color-primary: oklch(62% 0.17 65)` maps to the project's amber), which creates an illusion that both systems are synchronized. But the mapping is one-directional: DaisyUI reads from its variables, the existing CSS reads from its variables, and the connection is maintained only by manual synchronization.

**How to avoid:**
Choose one authoritative color system and make the other an alias. The correct choice is DaisyUI's semantic tokens as the source of truth, because new components will use them. Refactor the existing CSS custom properties to reference DaisyUI's variables: `--color-accent: var(--color-primary)` instead of a hardcoded hex value. This way, changing the DaisyUI theme automatically updates legacy components. Migrate one component CSS file at a time (start with `App.css` since it's the layout shell) rather than attempting a full rewrite.

**Warning signs:**
- Two different amber shades appearing on the same page (hex vs oklch rounding)
- Changing the DaisyUI theme has no effect on the sidebar or stats bar
- New components look "off" compared to existing ones despite using the same color name
- `grep --count` shows both `var(--color-accent)` and `tw-bg-primary` in the same component

**Phase to address:** Dashboard UI overhaul -- first task should be unifying the color token system before building any new components.

---

## Moderate Pitfalls

### Pitfall 7: PWA No-Build-Step Constraint Limits Tailwind v4 Usage

**What goes wrong:**
The driver PWA must remain a standalone HTML/JS app with no build step (per project constraints). Tailwind v4's JIT compiler requires a build step to scan HTML for class names and generate only used utilities. The current workaround (`scripts/build-pwa-css.sh` using `tailwindcss-extra` binary) pre-compiles CSS from `pwa-input.css`. But this means every CSS class used in the PWA must exist at compile time -- dynamic class names constructed in JavaScript (e.g., `element.className = 'tw-bg-' + statusColor`) will not be included in the compiled output. Developers adding new DaisyUI components or utility classes to the PWA's JavaScript must remember to re-run the build script, which is not automated and is easy to forget.

**How to avoid:**
If adopting Tailwind classes in the PWA, add a CI step that runs `build-pwa-css.sh` and fails if the output differs from the committed `tailwind.css` (staleness check). Alternatively, if the PWA will use primarily hand-crafted CSS (which it currently does), document that `tailwind.css` is a pre-compiled asset and list all used utility classes in a comment block at the top of `pwa-input.css` for discoverability. Never use dynamic class name construction with Tailwind utilities in the PWA.

**Warning signs:**
- New DaisyUI components in the PWA appear unstyled
- `tailwind.css` has not been regenerated after HTML changes
- Developer adds a class in JS, it works in the dashboard (Vite JIT), but not in the PWA (pre-compiled)

**Phase to address:** Driver PWA refresh -- establish the CSS build workflow before starting visual changes.

---

### Pitfall 8: Geocoding Duplicate Detection False Positives From Low-Confidence Results

**What goes wrong:**
The v1.1 milestone includes "duplicate location detection -- flag orders resolving to same GPS coordinates." If duplicate detection uses exact coordinate matching, it will miss true duplicates (same address, slightly different geocode results on different days). If it uses proximity matching (e.g., within 50 meters), it will produce false positives in dense urban areas where different buildings share a nearby GPS point. Vatakara has narrow streets where houses 10 meters apart have legitimately different delivery stops -- flagging these as duplicates causes drivers to skip deliveries.

**Why it happens:**
Geocoding confidence varies by location type. Google returns `ROOFTOP` (0.95 confidence, ~5m accuracy) for well-mapped buildings, but `GEOMETRIC_CENTER` (0.60 confidence, ~200m accuracy) for area matches. Two orders at the same `GEOMETRIC_CENTER` point may be genuinely different addresses within a 200m radius. The current confidence mapping in `google_adapter.py` (lines 158-165) provides this data but it is not used in duplicate detection.

**How to avoid:**
Use confidence-weighted proximity thresholds for duplicate detection: `ROOFTOP` results should flag duplicates within 10m, `RANGE_INTERPOLATED` within 25m, `GEOMETRIC_CENTER` within 100m, and `APPROXIMATE` should never flag duplicates (too imprecise). Also check the `address_raw` text similarity alongside GPS proximity -- two orders at the same coordinates with different address text are likely genuine (e.g., ground floor vs. first floor of the same building). Present flagged duplicates as warnings, not automatic removals.

**Warning signs:**
- Duplicate detection flags 30%+ of orders as duplicates in a Vatakara batch (far too many)
- Drivers report missing deliveries because "duplicate" orders were auto-removed
- Orders at bus stops or landmarks (low-precision geocoding) are always flagged

**Phase to address:** Geocoding fixes phase -- implement after cache normalization, using confidence data from the cache.

---

### Pitfall 9: Tailwind Preflight CSS Resets Breaking Existing Dashboard Components

**What goes wrong:**
Tailwind's Preflight layer (included by `@import "tailwindcss"`) resets all elements: removes default margins, sets `border-style: solid` on everything, changes button appearance, and normalizes line-height. The dashboard's existing 9 CSS files rely on some of these browser defaults. After installing Tailwind, components that were not explicitly styled for these properties shift subtly: table rows lose their default spacing, buttons change appearance, headings collapse margins. These are not dramatic breaks -- they are subtle visual regressions that make the dashboard look "slightly wrong" without any obvious cause.

**Why it happens:**
The dashboard's `index.css` already includes explicit resets for `box-sizing`, `button`, `table`, and headings (lines 54-166). But it does not reset every property that Preflight touches. The gap between "what the project resets" and "what Preflight resets" creates the regressions.

**How to avoid:**
After Tailwind installation (which is already done), visually compare every dashboard page before writing any new utility classes. The comparison should be done with screenshots, not by eye -- take before/after screenshots of: (1) Upload page empty state, (2) Upload page with results, (3) LiveMap, (4) Fleet Management, (5) Run History. Any visual difference is a Preflight regression. Fix by adding explicit CSS declarations to override Preflight rather than disabling Preflight entirely.

**Warning signs:**
- Table rows appear tighter than before without any CSS changes
- Buttons look flatter or lose rounded corners
- Sidebar navigation items shift by 1-2px
- Form inputs lose their default browser styling

**Phase to address:** Dashboard UI overhaul -- visual diff as the first step before any component work.

---

### Pitfall 10: File Cache Not Cleared During Geocoding Normalization Migration

**What goes wrong:**
The geocoding fix phase will unify normalization logic between the file cache and DB cache. If only the DB cache normalization is updated (in `repository.py`) but the file cache (`data/geocode_cache/google_cache.json`) is not migrated or cleared, the GoogleGeocoder will continue serving results from the old file cache with the old normalization. Since CachedGeocoder checks the DB first and falls through to GoogleGeocoder on miss, this creates a scenario where: (1) DB cache miss (new normalization), (2) file cache hit (old normalization, possibly stale coordinates), (3) result used but NOT saved back to DB cache. The two caches drift further apart over time.

**Why it happens:**
The file cache is a JSON file on disk (`data/geocode_cache/google_cache.json`) that is easy to forget about. It is not managed by Alembic migrations. The GoogleGeocoder is initialized lazily (`_get_geocoder()` in `main.py` line 637) and reads the file cache on startup. Developers fixing the DB normalization in `repository.py` may not realize the file cache exists as a separate system.

**How to avoid:**
The cleanest solution: deprecate the file cache entirely. The PostGIS cache is production-ready, shared across containers, and has superior features (hit tracking, spatial queries, driver-verified entries). Change GoogleGeocoder to accept an optional `cache_dir=None` parameter, and when `None`, skip file cache entirely. Delete `data/geocode_cache/google_cache.json` after migrating any entries not already in the DB cache. If the file cache must be kept for offline development: run a one-time migration that imports all file cache entries into the DB cache using the unified normalization function.

**Warning signs:**
- After normalization fix, cache hit rate drops temporarily then recovers (file cache being consulted instead of DB)
- `data/geocode_cache/google_cache.json` continues growing after normalization fix
- Same address has different coordinates in file cache vs. DB cache

**Phase to address:** Geocoding fixes phase -- handle file cache migration/deprecation as part of normalization unification.

---

### Pitfall 11: Cost Tracking Counts Cache Hits From Wrong Cache Layer

**What goes wrong:**
The v1.1 milestone includes "geocoding cost tracking -- cache hit vs API call indicator per address." The CachedGeocoder already tracks stats (`self.stats = {"hits": 0, "misses": 0, "errors": 0}`). But a "miss" in the CachedGeocoder (DB cache miss) may still be a "hit" in the GoogleGeocoder (file cache hit) -- which costs $0 but is counted as an API call. If cost tracking reports based on CachedGeocoder misses, it will overstate API costs. Conversely, if it reports based on actual `httpx.get()` calls to Google, it will undercount because the file cache intercepts.

**Why it happens:**
The two-layer cache architecture (DB cache wrapping file cache wrapping API) means "cache hit" has three possible meanings: (1) DB cache hit -- free, (2) file cache hit -- free, (3) API call -- $0.005. Cost tracking must distinguish all three, but the current stats only track two layers.

**How to avoid:**
After unifying/deprecating the file cache (Pitfall 10), cost tracking simplifies to: DB cache hit = free, API call = $0.005. If the file cache is retained, add a `file_hits` counter to GoogleGeocoder alongside its existing cache check logic. The cost tracking indicator per address should show one of three states: "cached" (DB hit), "cached-local" (file hit), or "API" (actual Google call with cost).

**Warning signs:**
- Cost report shows 50 API calls but Google Cloud Console shows only 20 billable requests
- Cost tracking and `geocode_batch.py` statistics disagree on cache hit rates
- CachedGeocoder reports 0% hit rate on first run even though file cache has entries

**Phase to address:** Geocoding fixes phase -- implement after cache normalization and file cache decision.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Using Tailwind utility classes inline without component abstraction | Fast styling during overhaul | Hundreds of `tw-bg-base-200 tw-p-4 tw-rounded-box` strings scattered through TSX -- impossible to maintain visual consistency | Only for one-off layouts; create `.card`, `.data-row` abstractions for repeated patterns |
| Keeping both file cache and DB cache during normalization fix | Lower risk -- less code changes | Two caches drift over time; debugging geocode issues requires checking both; cost tracking inaccurate | Acceptable only temporarily during migration; deprecate file cache within the same phase |
| Adding DaisyUI theme at `<html>` level for quick dark/light toggle | Quick theming | DaisyUI styles leak into Leaflet map containers, affecting tile contrast and popup readability | Never for this project -- scope theme to `.app` container, not `<html>` |
| Hardcoding driver PWA colors instead of using CSS custom properties | Works immediately for dark theme | When outdoor readability testing reveals needed color tweaks, every color must be found and changed individually across 600+ lines of inline CSS | Never -- extract colors to CSS custom properties at the top of the `<style>` block |

---

## Integration Gotchas

Common mistakes when connecting to external services or internal subsystems.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| DaisyUI oklch theme + existing hex CSS variables | Assuming oklch and hex values for the "same" color are visually identical -- they are not due to different color spaces | Use oklch throughout; convert existing hex values (`#D97706`) to oklch equivalents; verify visually in browser, not by color math |
| Leaflet map in DaisyUI-themed container | DaisyUI's base styles (font, color, background) leak into `.leaflet-container` and `.leaflet-popup-content` | Scope DaisyUI theme to content area; add explicit CSS reset for `.leaflet-container` preserving Leaflet's own defaults |
| Google Geocoding API rate limits during batch import | Assuming 1 req/sec rate limit -- Google's actual QPS limit is 50, but the project uses 0.05s delay (20 QPS) | The existing 20 QPS rate in `geocode_batch.py` is appropriate; do not "optimize" by removing the delay -- Google will throttle with 429s |
| Service worker + compiled Tailwind CSS | Changing CSS classes in `index.html` without re-running `build-pwa-css.sh` AND bumping `CACHE_VERSION` | Add a pre-deploy checklist or CI step that validates both the CSS compilation and SW version are current |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| PWA shipping 50KB+ of unused DaisyUI CSS | Slow initial PWA load on 3G mobile networks in rural Kerala | Either use DaisyUI classes (making the CSS useful) or remove the import entirely | Immediately visible on first load over slow mobile data |
| Re-normalizing all geocode cache entries on every query | Calling `.strip().lower()` on every cache lookup is fine; but if normalization grows to include transliteration or abbreviation expansion, N queries * normalization overhead adds up | Cache the normalized form in `address_norm` column (already done); never re-normalize at query time | If normalization includes expensive operations like Malayalam transliteration |
| Geocoding duplicate detection scanning all pairs | O(n^2) comparison of all order coordinates for duplicate detection | Use PostGIS `ST_DWithin()` spatial query for proximity matching instead of Python loops; the spatial index on `geocode_cache.location` makes this O(n log n) | At 200+ orders per batch |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Removing `'unsafe-inline'` from CSP `style-src` to "improve security" | Leaflet maps break completely -- popups, markers, and overlays stop working | Document why `'unsafe-inline'` is required; add code comment at CSP config line; do NOT remove during UI hardening |
| DaisyUI theme `data-theme` attribute exposing dark/light preference | Not a direct security risk, but if theme includes high-contrast mode for accessibility, the theme attribute on `<html>` is visible to any JavaScript including third-party CDN scripts | Scope theme attribute to app container div, not document root |
| Geocoding API key visible in Docker Compose environment | `GOOGLE_MAPS_API_KEY` in `.env` is bind-mounted into containers and visible via `docker inspect` | Restrict API key in Google Cloud Console to Geocoding API only + IP restriction; set daily quota limit of 1000 requests |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Redesigning dashboard layout during overhaul | Dispatchers who use the system daily lose muscle memory; "where did the upload button go?" | Keep navigation structure identical; change colors, typography, spacing, and visual polish -- not information architecture |
| PWA outdoor readability optimized on laptop screen | Colors that pass WCAG contrast checks on an LCD monitor fail in direct Kerala sunlight on a phone | Test all PWA color changes on a physical Android device outdoors; the current saffron-on-dark palette was chosen specifically for sun readability |
| Showing geocoding cost as dollar amounts | Indian office staff think in rupees; $0.005 per request is abstract | Show costs in INR (multiply by ~83) and as percentage of the $200 monthly free tier used |
| Flagging duplicate locations without showing which orders are affected | Dispatcher sees "5 duplicates detected" but cannot tell which orders to check | Show duplicate pairs/groups with order IDs, addresses, and GPS distance between them; link each to the map view |
| DaisyUI modal for confirmation dialogs in driver PWA | Modals are hard to dismiss on small mobile screens with gloves; driver may accidentally confirm wrong action | Use inline expandable confirmation (current pattern) instead of overlay modals; keep 60px minimum touch targets |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Geocoding normalization:** Both file cache (`google_adapter.py`) AND DB cache (`repository.py`) use the same normalization function -- not just one of them
- [ ] **Geocoding normalization:** Existing `address_norm` values in the DB have been re-normalized with the unified function (migration script run)
- [ ] **Geocoding normalization:** File cache (`data/geocode_cache/google_cache.json`) has been migrated or deprecated -- not silently ignored
- [ ] **Dashboard CSS:** After overhaul, verify no page has two competing `--color-accent` values in DevTools `:root` inspector
- [ ] **Dashboard CSS:** DaisyUI alert/badge/table components use the custom logistics theme colors, not DaisyUI defaults
- [ ] **Driver PWA CSS:** The compiled `tailwind.css` either contains classes actually used by the HTML, or has been removed entirely
- [ ] **Driver PWA cache:** Every visual change to `index.html` or `tailwind.css` is accompanied by a `CACHE_VERSION` bump in `sw.js`
- [ ] **Driver PWA readability:** Color changes tested on physical mobile device in bright outdoor light, not just browser DevTools
- [ ] **Duplicate detection:** Uses confidence-weighted proximity thresholds, not flat distance matching
- [ ] **Cost tracking:** Distinguishes DB cache hits, file cache hits, and actual API calls -- not just "cached" vs "not cached"
- [ ] **CSP:** `style-src 'unsafe-inline'` remains in place after UI overhaul (required by Leaflet)
- [ ] **Leaflet map:** DaisyUI theme colors do not leak into `.leaflet-container`, `.leaflet-popup-content`, or marker popups

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Geocoding cache normalization mismatch discovered after weeks of operation | MEDIUM | Run migration script to re-normalize all `address_norm` values in DB; clear file cache; re-geocode addresses with no DB cache entry; ~2 hours of work + potential duplicate order investigation |
| DaisyUI theme colors wrong due to CSS variable collision | LOW | Inspect DevTools `:root`, identify shadowed variables, add explicit overrides in the custom theme block; no architectural changes needed |
| PWA CSS update not reaching drivers | LOW | Bump `CACHE_VERSION` in `sw.js` and redeploy; drivers receive update within 24h on next app open; for urgent fixes, add manual "check for updates" button that calls `registration.update()` |
| Duplicate detection removed valid orders | HIGH | Restore from database (orders are persisted before duplicate flagging); change duplicate detection from auto-removal to warning-only; audit all "duplicate" removals from the affected batch |
| Two design systems in dashboard (mixed hex/oklch) | MEDIUM | Consolidate in a single focused PR: make DaisyUI tokens authoritative, convert all `var(--color-*)` references in component CSS to use DaisyUI equivalents; ~3-4 hours for 9 CSS files |
| Leaflet broken after CSP tightening | LOW | Re-add `'unsafe-inline'` to `style-src` in CSP config; immediate fix, no data loss |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Dual cache normalization mismatch | Geocoding fixes (first task) | Single `normalize_address()` function used by both caches; `address_norm` migration completed; unit test verifies normalization consistency |
| CSS variable collision | Dashboard UI overhaul (first task) | DevTools `:root` shows no duplicate `--color-*` variables from competing sources |
| PWA dead CSS / wrong theme | Driver PWA refresh (first task) | PWA either uses DaisyUI classes with correct theme or has Tailwind import removed |
| Service worker cache staleness | Driver PWA refresh (automation) | CI step validates `CACHE_VERSION` changes when `index.html` or `tailwind.css` change |
| Leaflet CSP requirement | Dashboard UI overhaul (documentation) | Code comment at CSP config explains `'unsafe-inline'` requirement |
| Two competing design systems | Dashboard UI overhaul (first task) | All CSS files reference DaisyUI tokens as source of truth; legacy variables are aliases |
| PWA no-build-step + Tailwind | Driver PWA refresh (workflow) | CI step validates compiled CSS matches source |
| Duplicate detection false positives | Geocoding fixes (after normalization) | Confidence-weighted thresholds documented; manual review of flagged duplicates in test batch |
| Preflight CSS regressions | Dashboard UI overhaul (visual diff) | Before/after screenshots of all 5 pages show no unintended changes |
| File cache not cleared | Geocoding fixes (migration task) | File cache deprecated or migrated; no entries in file cache missing from DB cache |
| Cost tracking layer confusion | Geocoding fixes (after cache unification) | Cost report matches Google Cloud Console billable request count within 5% |

---

## Sources

- [Tailwind CSS v4 CSS variable collision -- tailwindlabs/tailwindcss#15754](https://github.com/tailwindlabs/tailwindcss/issues/15754)
- [Tailwind v4 prefixed CSS variable references bug -- tailwindlabs/tailwindcss#16441](https://github.com/tailwindlabs/tailwindcss/issues/16441)
- [DaisyUI 5 release notes and theme configuration](https://daisyui.com/docs/v5/)
- [DaisyUI prefix configuration](https://daisyui.com/docs/config/)
- [Leaflet CSP unsafe-inline requirement -- Leaflet/Leaflet#9168](https://github.com/Leaflet/Leaflet/issues/9168)
- [MDN: Content-Security-Policy style-src directive](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/style-src)
- [PWA service worker cache invalidation -- MDN](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Caching)
- [PWA cache staleness patterns](https://iinteractive.com/resources/blog/taming-pwa-cache-behavior)
- [Geocoding cache normalization strategies](https://address-hub.com/address-intelligence/caching/)
- Codebase inspection: `core/geocoding/google_adapter.py` (line 195 normalization), `core/database/repository.py` (line 741 normalization), `apps/kerala_delivery/driver_app/pwa-input.css`, `apps/kerala_delivery/driver_app/sw.js`, `apps/kerala_delivery/driver_app/tailwind.css` (compiled output), `apps/kerala_delivery/dashboard/src/index.css` (design tokens + DaisyUI theme), `apps/kerala_delivery/api/main.py` (line 256 CSP config)

---
*Pitfalls research for: Kerala LPG delivery route optimizer -- v1.1 Polish & Reliability*
*Researched: 2026-03-01*
