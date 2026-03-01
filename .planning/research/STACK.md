# Stack Research

**Domain:** Logistics SaaS dashboard UI overhaul + driver PWA refresh + geocoding data integrity
**Researched:** 2026-03-01
**Confidence:** HIGH
**Scope:** v1.1 milestone additions only. Dashboard UI overhaul, driver PWA refresh, geocoding cache normalization and duplicate detection.

---

## Context: What Already Exists (Do Not Change)

The base stack is validated and working. Listed here as context for additions only.

| Technology | Version | Layer |
|------------|---------|-------|
| React | 19.2.0 | Dashboard |
| TypeScript | 5.9.3 | Dashboard |
| Vite | 7.3.1 | Dashboard build |
| Tailwind CSS | 4.2.1 | Both (dashboard via Vite plugin, PWA via tailwindcss-extra CLI) |
| DaisyUI | 5.5.19 | Both (oklch logistics theme, `@plugin "daisyui"`) |
| @tailwindcss/vite | 4.2.1 | Dashboard build |
| MapLibre GL + react-map-gl | 5.18.0 / 8.1.0 | Dashboard maps |
| Leaflet | 1.9.4 | Driver PWA maps (CDN) |
| framer-motion | 12.34.3 | Dashboard animation (RunHistory only) |
| DM Sans + IBM Plex Mono | @fontsource | Dashboard typography |
| Outfit + JetBrains Mono | Google Fonts CDN | Driver PWA typography |
| Python/FastAPI | 0.129.1 | Backend API |
| SQLAlchemy + asyncpg | 2.0.46 / 0.31.0 | Async PostgreSQL ORM |
| GeoAlchemy2 | 0.18.1 | PostGIS geometry columns |
| Shapely | 2.1.2 | Geometric operations |
| PostGIS | 3.5 | Spatial database extension (ST_DWithin, ST_DistanceSphere available) |
| Secweb | 1.30.10 | HTTP security headers (already in requirements.txt) |

---

## Recommended Additions

### Dashboard UI Overhaul

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| lucide-react | ^0.575.0 | SVG icon library | Tree-shakeable ESM-native icons, ~1KB per icon. The dashboard currently uses emoji for nav icons (upload emoji, map emoji, clipboard emoji, truck emoji). Professional logistics SaaS requires proper SVG icons. lucide-react has 1500+ icons including logistics-relevant ones: Truck, Package, MapPin, Route, ClipboardList, Fuel, Navigation, BarChart3, Upload, Settings, Activity. Best bundle efficiency in 2026 React icon benchmarks. |

**Why lucide-react over alternatives:**

| Alternative | Why Not |
|-------------|---------|
| react-icons | Imports pull in entire icon family bundles. At 50k+ icons, tree-shaking is less efficient. lucide-react tree-shakes to only imported icons. |
| @heroicons/react | Only ~300 icons. Missing logistics-specific icons (no fuel, no route, limited navigation). |
| @phosphor-icons/react | Viable alternative with 6 weight variants per icon. Overkill for this dashboard -- lucide's single clean stroke style fits the industrial-utilitarian design language. |
| Copy-paste SVGs | Loses React component ergonomics (props for size, color, strokeWidth, className). |

### Driver PWA Refresh

**Zero new dependencies required.** The driver PWA must remain a standalone HTML/JS app with no build step. All improvements use existing technologies:

| Capability | Implementation | Notes |
|------------|----------------|-------|
| High-contrast outdoor mode | CSS `@media (prefers-contrast: more)` + manual toggle in localStorage | Native CSS feature. Add high-contrast color overrides for saffron-on-dark theme. Toggle via settings gear icon. |
| Simplified next-stop flow | Vanilla JS state machine: `currentStopIndex`, tap/swipe to advance | ~50 lines of JS. The current list view shows all stops. New flow: one stop at a time with large "Navigate" and "Mark Delivered" buttons. |
| Better offline: pre-cache route data | Service worker `fetch` event: intercept `GET /api/routes/{vehicle_id}` response, clone to cache | Extend existing SW from caching only app shell to also caching the last fetched route data. ~20 lines added to sw.js. |
| Screen wake lock | `navigator.wakeLock.request('screen')` in delivery mode | Prevents screen dimming during active delivery. 95%+ Android mobile support. Release lock when all stops delivered. |
| Haptic feedback | `navigator.vibrate([200])` on delivery confirmation | Single line. Gives tactile confirmation when marking stop as delivered. |
| Swipe navigation | `touchstart`/`touchmove`/`touchend` listeners | ~30 lines vanilla JS. Horizontal swipe to advance/go back between stops. |
| Font readability improvements | Already using Outfit (UI) + JetBrains Mono (data). Increase base font-size to 16px minimum, bump touch target data text to 18px. | CSS changes only. |

**Driver PWA CSS build:** Continue using `scripts/build-pwa-css.sh` with `tailwindcss-extra` CLI binary. This compiles `pwa-input.css` (Tailwind + DaisyUI plugin) to static `tailwind.css`. No Node.js runtime needed at deploy time.

### Geocoding Cache Normalization + Duplicate Detection

**Zero new Python dependencies required.** The existing stack covers all needs:

| Capability | Implementation | Why No New Library |
|------------|----------------|-------------------|
| Address normalization unification | Single `normalize_address()` function: `unicodedata.normalize('NFKC', " ".join(addr.strip().lower().split()))` | Python 3.12 stdlib `unicodedata` handles Malayalam Unicode canonical normalization. The bug is two different normalizations (see details below), not a missing library. |
| Duplicate GPS detection | PostGIS `ST_DWithin(location, target_point, 50)` query in repository | GeoAlchemy2 0.18.1 already exposes ST_DWithin. GiST spatial index on `geocode_cache.location` enables sub-ms queries. No Python haversine library needed. |
| Cache hit/miss cost tracking | Add `is_cache_hit: bool` and `api_calls_count: int` to response Pydantic model | Model change + counter in CachedGeocoder.stats dict. Zero new deps. |
| Malayalam Unicode normalization | `unicodedata.normalize('NFKC', text)` | Stdlib. Handles combining characters and canonical decomposition for Malayalam script. |

---

## The Geocoding Normalization Bug (Detailed)

This is the core data integrity issue. Two caching layers use different normalization:

**Layer 1 -- File cache** (`core/geocoding/google_adapter.py:189-196`):
```python
def _address_hash(self, address: str) -> str:
    normalized = " ".join(address.lower().split())  # collapses whitespace
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]
```

**Layer 2 -- DB cache** (`core/database/repository.py:741`):
```python
normalized = address_raw.strip().lower()  # preserves internal whitespace
```

**Example divergence:** Address `"Near SBI,  MG Road,  Kochi"` (double spaces):
- File cache normalizes to: `"near sbi, mg road, kochi"` (spaces collapsed) -> SHA-256 hash
- DB cache normalizes to: `"near sbi,  mg road,  kochi"` (double spaces preserved)
- Result: Same address gets different cache keys. DB misses, makes unnecessary API call, creates duplicate entry.

**Fix:** Create `core/geocoding/normalize.py` with a single canonical function:
```python
import re
import unicodedata

def normalize_address(raw: str) -> str:
    """Canonical address normalization for cache key generation.

    Used by both file-based and DB-based geocode caches.
    Steps: NFKC normalize -> lowercase -> collapse whitespace -> strip.
    """
    text = unicodedata.normalize('NFKC', raw)
    text = text.lower()
    text = re.sub(r'\s+', ' ', text).strip()
    return text
```

Then use this function in both `GoogleGeocoder._address_hash()` and `repository.get_cached_geocode()` / `repository.save_geocode_cache()`.

**Migration:** Run a one-time script to re-normalize existing `address_norm` values in the DB.

**Recommendation:** Deprecate the file cache entirely. The DB cache is the production path (shared across instances, supports spatial queries, tracks hit counts). The file cache was a bootstrap mechanism. After migration, GoogleGeocoder should delegate all caching to CachedGeocoder.

---

## DaisyUI 5 Components to Leverage (Already Installed)

These require zero installation -- just use the CSS classes with `tw-` prefix.

| Component | Use Case in v1.1 | Why |
|-----------|-------------------|-----|
| **Table** | Route list, fleet management, geocoding failure report | Responsive via `overflow-x-auto`, zebra striping, hover states. Replace current custom CSS tables. |
| **Stat** | KPI cards: orders uploaded, cache hit rate, routes generated, total distance, API calls saved | Clean numeric display with title, value, description. Replace current plain text stats. |
| **Badge** | Status tags: "Geocoded", "Cache Hit", "API Call", "Failed", vehicle status | Semantic colors mapped to DaisyUI theme (success, warning, error, info). |
| **Skeleton** | Loading states during optimization and route fetch | Content-shaped placeholders, better UX than spinner for route cards and stats. |
| **Steps** | Upload workflow progress indicator: Parse -> Geocode -> Optimize -> Done | Visual multi-step progress. Shows current phase during the 5-30 second optimization flow. |
| **Alert** | Import summary states (already partially used in ImportSummary) | Standardize success/warning/error patterns across the dashboard. |
| **Toast** | Non-blocking notifications: "Routes generated", "Upload failed" | Corner-positioned, auto-dismiss. Non-intrusive confirmation. |
| **Modal** | Confirmation dialogs: delete vehicle, re-optimize, clear cache | Accessible, ESC-dismissible, focus-trapped. |
| **Tooltip** | Explain cache indicators, abbreviations, status icons | Non-intrusive contextual help for operators. |
| **Indicator** | Badge overlay on nav icons (e.g., pending routes count) | Overlays a count number on sidebar icon. |
| **Collapse** | Expandable geocoding failure details (already used in ImportSummary) | Standardize on DaisyUI version for visual consistency. |
| **Loading** | Inline loading spinner for buttons during API calls | Small spinner inside button during submit. |
| **Validator** | Fleet management form field validation feedback | Color changes on input validity (green/red border + message). |

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| recharts / chart.js / echarts | No charts in v1.1 scope. Dashboard shows route lists, maps, and stat numbers. Adding a chart library is premature. | DaisyUI Stat component for numeric KPIs |
| react-router / @tanstack/router | Only 4 pages. Current `useState<Page>` works perfectly. Adding a router is overhead for zero benefit at this page count. | Keep existing `activePage` state pattern in App.tsx |
| @tanstack/react-query | Only 4-5 API calls total. Current `useEffect` + `fetch` is adequate. No polling, no optimistic updates, no cache invalidation complexity. | Keep existing `useCallback` + `fetch` pattern in lib/api.ts |
| shadcn/ui | Would conflict with DaisyUI -- both provide component primitives. DaisyUI is already installed, themed, and working. | DaisyUI 5 components |
| @headlessui/react | DaisyUI 5 already provides accessible modal, dropdown, tabs, accordion. Headless UI adds abstraction without new capability. | DaisyUI modal, dropdown, tabs |
| Zustand / Redux / Jotai | 4 pages with independent state. No cross-page state sharing needed. Prop depth is shallow (App -> Page -> Component). | React useState / useReducer |
| react-table / TanStack Table | Route list has 13 rows max. Fleet management has 13 vehicles. No need for virtualization, column resizing, or complex filtering. | DaisyUI Table with manual sort (~20 lines) |
| Workbox (Google SW toolkit) | Driver PWA already has a well-structured 146-line service worker. Workbox adds a build step and abstraction for something already working. | Extend existing hand-written sw.js |
| IndexedDB / idb library | Current localStorage holds route data for 13 vehicles x ~50 stops = ~650 items. localStorage 5MB limit is nowhere near reached. | Keep localStorage for route cache + offline queue |
| libpostal / pypostal | Requires 2GB+ trained model download. Massive overhead for normalizing Kerala landmark-based addresses. | Python stdlib `unicodedata.normalize('NFKC')` + whitespace collapsing |
| text-unidecode / Unidecode | Transliterates Malayalam to ASCII gibberish. We need Unicode canonical normalization (NFKC), not transliteration. | `unicodedata.normalize('NFKC', text)` |
| haversine (Python library) | All geocoded data lives in PostGIS. ST_DWithin does the same calculation on indexed spatial data, faster than loading into Python. | PostGIS `ST_DWithin` via GeoAlchemy2 |
| Redis | PostgreSQL geocode_cache with GiST index handles caching. Redis would add another Docker service for no measurable benefit at this scale (40-50 addresses/day). | PostgreSQL geocode_cache table |
| Leaflet.markercluster | Not needed for v1.1. Dashboard uses MapLibre GL (not Leaflet). Driver PWA shows one route at a time (max ~50 markers). Clustering is a future concern if dashboard switches to showing all routes simultaneously. | MapLibre native clustering (if ever needed) |

---

## framer-motion Status

The project has `framer-motion@^12.34.3` installed. This IS the same code as "Motion for React" -- the npm `motion` package v12.34.3 and `framer-motion` v12.34.3 are the same library by Matt Perry / Motion Division.

Currently only `RunHistory.tsx` imports from `framer-motion`. This works with React 19 at v12.

**No migration needed.** The import can optionally change from:
```typescript
import { motion, AnimatePresence } from "framer-motion";
```
to:
```typescript
import { motion, AnimatePresence } from "motion/react";
```
This is cosmetic (same underlying code). Do it during RunHistory refactor if convenient. Do not create a separate task.

**Use framer-motion for v1.1:** Page transitions in App.tsx, list item animations in route cards, stat counter animations. Already installed, zero additional cost.

---

## Installation

```bash
# Dashboard -- single new dependency
cd apps/kerala_delivery/dashboard
npm install lucide-react

# That's it. Everything else is already installed or uses stdlib.
```

**No Python additions needed.** `unicodedata` is Python stdlib. PostGIS `ST_DWithin` is available via existing GeoAlchemy2.

**No driver PWA additions needed.** All improvements are CSS + vanilla JS using existing Tailwind/DaisyUI compiled CSS.

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| lucide-react@0.575 | React 19.2.0 | Confirmed. Uses React.forwardRef (still supported in React 19). Tree-shakes cleanly with Vite 7. |
| lucide-react@0.575 | TypeScript 5.9.3 | Ships its own type definitions. |
| framer-motion@12.34.3 | React 19.2.0 | Full React 19 support since v12 alpha. Working in project today. |
| DaisyUI@5.5.19 | Tailwind CSS 4.2.1 | DaisyUI 5 built for Tailwind 4. Uses `@plugin` directive. Working in project today. |
| tailwindcss-extra CLI | Tailwind CSS 4.x + DaisyUI 5.x | Third-party CLI bundles DaisyUI plugin for standalone compilation. Used by driver PWA CSS build. |
| Python 3.12 unicodedata | All Python deps | stdlib, no version conflicts possible. |
| PostGIS 3.5 ST_DWithin | GeoAlchemy2 0.18.1 | ST_DWithin available since PostGIS 1.x. GiST index on location column already exists in schema. |

---

## Stack Patterns by Feature Area

**Dashboard UI overhaul:**
- Replace emoji nav icons with lucide-react SVG icons (Truck, Upload, Map, ClipboardList)
- Use DaisyUI 5 component classes with `tw-` prefix for all new UI elements
- Leverage DaisyUI Stat for KPI cards, Table for data lists, Badge for status tags
- Keep existing CSS custom properties (`:root` vars in index.css) for backward compat
- Use framer-motion for page transitions (AnimatePresence) and list animations
- Maintain current DM Sans + IBM Plex Mono typography

**Driver PWA refresh:**
- All styling via Tailwind utility classes compiled by `tailwindcss-extra` CLI
- No new JavaScript dependencies; all interactivity via vanilla JS
- Extend sw.js to cache route API responses (clone response in fetch handler)
- Add `prefers-contrast: more` CSS media query + localStorage toggle
- Use Screen Wake Lock API for active delivery mode
- Keep Outfit + JetBrains Mono fonts; increase base font sizes for outdoor readability

**Geocoding cache normalization:**
- Create single `core/geocoding/normalize.py` module with `normalize_address()` function
- Apply `unicodedata.normalize('NFKC')` + lowercase + whitespace collapse
- Use in both GoogleGeocoder._address_hash() and repository get/save_geocode_cache()
- Run Alembic migration to re-normalize existing `address_norm` column values
- Add `ST_DWithin(location, new_point, 50)` query for duplicate coordinate detection
- Add `is_cache_hit` and `api_calls_count` fields to geocoding response model
- Long-term: deprecate file cache, use DB cache as single source of truth

---

## Sources

- [lucide-react on npm](https://www.npmjs.com/package/lucide-react) -- v0.575.0, 10.3k+ dependents (HIGH confidence)
- [Lucide icon search](https://lucide.dev/icons/) -- verified logistics-relevant icons exist (HIGH confidence)
- [Lucide bundle benchmark 2026](https://medium.com/codetodeploy/the-hidden-bundle-cost-of-react-icons-why-lucide-wins-in-2026-1ddb74c1a86c) -- tree-shaking comparison (MEDIUM confidence, single article)
- [DaisyUI Components](https://daisyui.com/components/) -- verified Stat, Table, Badge, Skeleton, Steps availability (HIGH confidence)
- [DaisyUI 5 release notes](https://daisyui.com/docs/v5/) -- confirmed all modifiers responsive, 34KB compressed (HIGH confidence)
- [Motion for React](https://motion.dev/docs/react) -- confirmed framer-motion v12 = motion v12, React 19 compatible (HIGH confidence)
- [PostGIS ST_DWithin docs](https://postgis.net/docs/ST_DWithin.html) -- spatial proximity queries (HIGH confidence)
- [Python unicodedata docs](https://docs.python.org/3/library/unicodedata.html) -- NFKC normalization for Malayalam (HIGH confidence)
- [MDN Screen Wake Lock API](https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API) -- browser support table (HIGH confidence)
- [MDN prefers-contrast](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-contrast) -- CSS media query for outdoor readability (HIGH confidence)
- [PWA Best Practices 2026](https://wirefuture.com/post/progressive-web-apps-pwa-best-practices-for-2026) -- offline-first patterns (MEDIUM confidence)

---

*Stack research for: Kerala LPG Delivery Route Optimizer v1.1 Polish & Reliability*
*Researched: 2026-03-01*
