# Feature Research

**Domain:** Logistics dashboard UI redesign, driver delivery PWA refresh, geocoding cache management
**Researched:** 2026-03-01
**Confidence:** HIGH (codebase thoroughly analyzed; industry patterns well-established; geocoding cache issue root-caused from code)

---

## Context: What Already Exists (v1.0 Complete)

This is a v1.1 Polish & Reliability milestone on a working system. These features are ALREADY SHIPPED and should NOT be rebuilt:

- CSV upload with drag-and-drop, file validation, and row-level validation
- Import summary UI with success/partial/zero states and expandable failure tables
- Geocoding failure reporting with per-row reasons (validation + geocoding stages)
- Route optimization via VROOM/OSRM for 13-vehicle fleet
- QR code generation for route sharing + printable QR sheet
- Driver PWA with dark-first design, Leaflet maps, offline support, and 48px+ touch targets
- React dashboard with 4 pages: UploadRoutes, LiveMap, RunHistory, FleetManagement
- Collapsible sidebar with emoji icons, API health indicator
- Telemetry ingestion and fleet telemetry batch endpoint
- HTTP security headers (CSP, CORS hardening, Permissions-Policy)
- DaisyUI 5 with tw- collision-safe prefix installed
- API key auth with timing-safe comparison

**The gap for v1.1:** Dashboard looks prototype-quality (emoji icons, mixed CSS approaches, no loading/empty states). Driver PWA lacks next-stop prominence and progress visibility. Geocoding has dual-cache normalization bug causing duplicate map locations. No cost transparency for geocoding API usage.

---

## Feature Landscape

### Domain 1: Dashboard UI Overhaul

#### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Consistent DaisyUI styling across all 4 pages** | Current mix of raw CSS classes (`.upload-btn`, `.route-card`) alongside DaisyUI `tw-alert` components looks inconsistent. Every professional logistics SaaS has unified visual language. | MEDIUM | Migrate UploadRoutes, LiveMap, RunHistory, FleetManagement to DaisyUI component vocabulary. The tw- prefix approach is already installed. Largest effort is LiveMap (3-panel layout) and UploadRoutes (most complex page). |
| **SVG icons replacing emoji nav items** | Sidebar uses emoji (fire, truck, clipboard, map). Professional dashboards use clean SVG icon sets. Emoji render differently across OS/browser. | LOW | Replace with Heroicons or Lucide React. 4 icons total: upload, map, history, truck. Keep DaisyUI menu component for nav structure. |
| **Typography hierarchy with data fonts** | Dashboard renders distances, weights, durations in same font as labels. Numeric data needs monospace or tabular-number font for column alignment and scannability. | LOW | Use DaisyUI prose for text. Apply `font-variant-numeric: tabular-nums` or a monospace font (like JetBrains Mono, already used in driver PWA) for numeric values in route cards, stats, tables. |
| **Loading and empty states for all pages** | RunHistory with no runs and FleetManagement with no vehicles show blank content areas. Users think the page is broken. LiveMap has a spinner but other pages do not. | LOW | DaisyUI skeleton component for loading. Illustrated empty states with CTA: "No routes generated today -- upload a CDCMS file" with link to Upload page. 4 pages x 2 states = 8 small components. |
| **Color-coded status badges on route cards** | Route cards show text-only metadata ("12 stops, 8.3 km"). Logistics dashboards use colored chips/badges for status (green=all delivered, amber=in progress, red=issues). | LOW | DaisyUI badge component with semantic colors. Data already exists: `orders_assigned`, `orders_unassigned` determine status. |
| **Responsive sidebar behavior** | Current sidebar collapses on hover (64px to 220px). On screens below 1280px this causes content reflow. Standard pattern: sidebar collapses to icons permanently on small screens, uses DaisyUI drawer on mobile. | LOW | DaisyUI drawer component for mobile breakpoint. Keep hover-expand for desktop. Add a pin/unpin toggle for sidebar. |
| **Print-friendly QR sheet styling** | QR sheet endpoint exists (`/api/qr-sheet`) but relies on server-rendered HTML. Office staff print this daily. Needs clean layout with vehicle name, driver name, and large QR codes. | LOW | CSS `@media print` rules. Already functional but not polished. Ensure QR codes are large enough to scan from printed paper at arm's length. |

#### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **DaisyUI theme switcher (light/dark)** | Office staff work indoors (light preferred for readability). Late shift operations benefit from dark mode. Most logistics tools are light-only. | LOW | DaisyUI has built-in multi-theme support. Use "corporate" or "nord" for light, "business" for dark. Theme toggle in sidebar footer. Store preference in localStorage. |
| **Geocoding cost indicator on upload results** | After upload, show "42 cache hits (free) + 8 API calls ($0.04)". Office staff gain transparency into geocoding costs. No competitor in this niche exposes this. | LOW | Backend upload endpoint already has the cache-hit vs API-call code branch. Add two counters. Return as new fields in OptimizationSummary. Display as info badge in ImportSummary component. |
| **At-a-glance daily summary card** | First thing office staff see on Upload page when routes exist: "Today: 47 deliveries across 11 vehicles, 2 geocoding failures, estimated 127 km total". Quick situational awareness before printing QR sheet. | MEDIUM | Aggregate existing route data. Can compute from current `/api/routes` response. New component on UploadRoutes success state above route cards. |
| **Per-vehicle capacity utilization bar** | Show weight used vs 446 kg max as a horizontal bar on each route card. Operators see at a glance if loads are balanced or if one vehicle is overloaded. | LOW | Data already in `route.total_weight_kg`. Simple DaisyUI progress bar. Width = `(total_weight_kg / 446) * 100%`. Color: green <70%, amber 70-90%, red >90%. |

#### Anti-Features (Do NOT Build)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Drag-and-drop route reordering** | "Let me manually adjust stop order" | Undermines VROOM optimizer. Manual overrides create sub-optimal routes. Complex React DnD implementation. Operators are not routing experts. | Show optimizer output as read-only. If a stop needs moving, re-run optimization. Add "pin stop to position" as a constraint input in v2+ if ever needed. |
| **Real-time auto-refresh on all pages** | "I want to see live data everywhere" | Polling every 5s across 4 pages wastes bandwidth, creates flicker. LiveMap already polls telemetry at 15s which matches GPS ping frequency. | Poll only on LiveMap (already done). Other pages show point-in-time data with a visible "Refresh" button and "Last updated: 2 min ago" timestamp. |
| **Complex role-based dashboard views** | "Managers see different data than operators" | Single office with 2-3 users. Role-based access adds auth complexity (login, sessions, permissions) for zero value at this scale. | Single view for all users. If needed later, simple feature flags per config, not a full RBAC system. |
| **Multi-tab panel layout** | "Map + routes side-by-side" | Responsive layout complexity. 4-page app with 1366px typical screen doesn't need panel management. LiveMap already has sidebar + map two-panel layout which is sufficient. | Keep single-page-at-a-time. LiveMap's two-panel layout is the exception that proves the rule. |
| **Dark mode for dashboard (as P1)** | "Make it match the driver app" | Risks destabilizing CSS during the overhaul. Get consistent DaisyUI styling working first in one theme, then adding a second theme is trivial. | Ship light-mode-first dashboard. Theme switcher is a P2 differentiator once consistency is proven. |

---

### Domain 2: Driver PWA Refresh

#### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Prominent "next stop" card** | Drivers need instant answer to "where am I going?" without scrolling. DispatchTrack, Routific, and every delivery app puts next stop front-and-center. Current PWA shows a flat list where all stops have equal visual weight. | MEDIUM | New hero card at top of stop list: large address text, distance/weight, and prominent "Navigate" button. Separate from scrollable list below. Key UX pattern: the answer to the driver's most frequent question must be visible without ANY interaction. |
| **Visual delivery progress indicator** | "7 of 23 delivered" as a progress bar in header. Drivers are motivated by visible progress. Standard in every delivery app (Amazon Flex, DoorDash driver, DispatchTrack). | LOW | DaisyUI progress bar or simple filled bar. Count delivered+failed stops / total stops. Use success green fill. Display in header alongside existing stats. |
| **Pull-to-refresh or manual refresh** | Drivers need to reload if office re-runs optimization mid-day. Current PWA has no visible refresh mechanism beyond browser pull-to-refresh (which is not discoverable). | LOW | Add visible "Refresh Route" button in header area. Show "Last updated: 10:42 AM" timestamp so driver knows data freshness. Simple: re-fetch route data from API and update DOM. |
| **60px+ touch targets for primary actions (audit)** | Kerala conditions: rain, gloves, one-handed operation on three-wheeler. Current PWA specifies 48px minimum, 60px for primary actions. Need to verify all interactive elements meet this. | LOW | Audit existing buttons. "Delivered" / "Failed" buttons, "Navigate" button, "Call office" -- all must be 60px+ height. Fix any that are smaller. DaisyUI btn-lg is 48px by default; may need custom sizing. |
| **High-contrast text verification** | Current PWA has WCAG AAA design intent (7:1 contrast). Need to verify every text/background combination actually meets this. Some secondary text (#9897B0 on #0B0B0F) may be borderline. | LOW | Run contrast checker on all color pairs in the CSS custom properties. Fix any that fall below 7:1 for body text or 4.5:1 for large text. Particularly check: `--color-text-secondary` and `--color-text-muted` against `--color-bg`. |
| **Offline route persistence verification** | Kerala has patchy mobile data. Route MUST work offline once loaded. Current PWA stores route in localStorage and service worker caches app shell. Need to verify this works end-to-end after PWA refresh changes. | LOW | Test: (1) Load route with network, (2) go offline, (3) refresh page, (4) verify route data still visible, (5) mark a stop delivered, (6) verify status queued in localStorage, (7) go online, (8) verify queued updates sync. |

#### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **"Focus mode" -- next-stop-only view** | Instead of showing all 20+ stops, show ONLY the current stop as a full-screen card with navigate button. Toggle between "focus" and "full list" view. Reduces cognitive load in the field. | MEDIUM | New view mode. Full-screen card: address (large), quantity, weight, "Navigate in Google Maps" button (60px), "Delivered" / "Failed" buttons. Swipe or tap arrow to peek at next stop. |
| **Auto-advance after delivery confirmation** | When driver marks stop as delivered, automatically scroll list to next undelivered stop or update focus mode card. Removes one tap from the repetitive workflow (mark delivered -> find next -> tap -> navigate). | LOW | After status update (API call or localStorage queue), programmatically scroll to next stop with `pending` status. In focus mode, swap card content to next stop. |
| **Offline sync queue indicator** | Show "3 updates pending sync" badge when offline. Drivers need confidence that delivery confirmations aren't lost. Green checkmark when all synced. | MEDIUM | Already partially exists (localStorage queue for status updates). Add visible UI indicator: pending count badge on header, retry logic on `navigator.onLine` event. Show last sync timestamp. |
| **Haptic feedback on delivery confirmation** | Brief vibration when marking a stop delivered/failed. Confirms the action without looking at screen. Important for one-handed outdoor operation. | LOW | `navigator.vibrate(50)` on button tap. Single line of JS. Graceful degradation if vibration API not available. |

#### Anti-Features (Do NOT Build)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Turn-by-turn navigation in-app** | "Don't make me open Google Maps" | Building navigation requires a routing engine, voice guidance, lane guidance, and massive map tile caching. Google Maps is free and already installed on every phone. Leaflet cannot do turn-by-turn. | Deep-link to Google Maps with destination coordinates (already implemented). One-tap "Navigate" button per stop. Google handles the routing. |
| **Photo proof-of-delivery** | "Prove the cylinder was delivered" | Camera API complexity, image upload on spotty Kerala networks (each photo 1-3MB), storage costs, privacy concerns photographing customer homes. Overkill for LPG where delivery is confirmed by receipt signature. | GPS-verified delivery (driver GPS at stop location = proof). Already captures coordinates with status updates. Add distance-from-stop validation if needed. |
| **Countdown timers for delivery windows** | "Show time remaining to deadline" | Explicitly prohibited for Kerala MVD compliance. Creates pressure on drivers leading to unsafe driving on narrow Kerala roads. Already noted as a hard constraint in PROJECT.md. | Show delivery window as static text ("9:00 AM - 12:00 PM"). No countdown, no urgency coloring, no "late" indicators. |
| **Pre-cached map tiles for entire route** | "Map should work fully offline" | OSM tiles for even a small Kerala region require 50-100MB+ of storage. Browser cache quotas are unpredictable. Service worker may be evicted by OS on low-memory Android devices. | Cache tiles opportunistically as driver views map (already in sw.js). Primary offline interface is the LIST view (no tiles needed). Map is a bonus when online. |
| **Real-time chat with office** | "Driver needs to ask about an address" | Chat requires WebSocket infrastructure, message persistence, notification handling, and an always-on server component. Two people can call each other. | Display office phone number prominently in PWA header. One-tap "Call Office" button. |

---

### Domain 3: Geocoding Cache Fixes

#### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Unified cache normalization** | ROOT CAUSE of duplicate map locations. Two caches use different normalization: GoogleGeocoder file cache hashes `" ".join(address.lower().split())` (collapses all whitespace), while DB cache uses `address.strip().lower()` (preserves internal whitespace). Same address can exist in both with different coordinates. | MEDIUM | Create a single `normalize_address()` function in `core/geocoding/normalization.py`. Apply everywhere: `" ".join(address.strip().lower().split())` which handles leading/trailing whitespace AND internal whitespace normalization. Update GoogleGeocoder._address_hash() and repository.get_cached_geocode()/save_geocode_cache() to use it. |
| **Single source of truth for cache** | GoogleGeocoder has a file-based JSON cache (`data/geocode_cache/google_cache.json`) AND the DB has a `geocode_cache` table. The upload endpoint checks DB cache first, then calls GoogleGeocoder which checks its own file cache. Results can diverge. | MEDIUM | Deprecate file-based cache. All cache reads/writes go through DB (repository layer). GoogleGeocoder becomes a pure API caller with no internal caching. The upload endpoint already does `repo.get_cached_geocode()` before calling the geocoder. |
| **Duplicate location detection** | When two different addresses resolve to the same GPS coordinates (within a threshold), drivers get confused by overlapping map markers. Common in Kerala with informal addresses ("near SBI, MG Road" vs "opp. SBI, MG Road"). | MEDIUM | After geocoding all orders in a batch, compare each pair's coordinates. Flag pairs within ~15 meters (configurable). Use haversine or PostGIS `ST_DWithin`. Report as warning in ImportSummary: "Orders #5 and #12 may be at the same location (8m apart)". Use DaisyUI warning alert. |
| **Geocoding cost tracking per upload** | Office staff should know how much each upload costs in Google API calls vs free cache hits. Directly requested in v1.1 milestone requirements. | LOW | Add two counters in the upload endpoint's geocoding loop: `cache_hits += 1` on DB cache hit, `api_calls += 1` on Google API call. Add fields to OptimizationSummary: `cache_hits: int`, `api_calls: int`. Display in ImportSummary: "42 cached (free) + 8 API calls (~$0.04)". |

#### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Cache migration tool** | One-time script to import existing `google_cache.json` entries into DB cache with correct normalization. Preserves months of geocoding history. Without this, switching to DB-only cache loses all file-cached results, causing unnecessary API calls. | LOW | Python script: read JSON file, for each entry normalize address using new function, upsert into `geocode_cache` table via `repo.save_geocode_cache()`. Run once during v1.1 deployment. |
| **Cache statistics in upload response** | Beyond just hits/calls count, show: total addresses in cache, cache hit rate over last 30 days, estimated total savings. Office staff see the cache growing in value. | LOW | SQL aggregation on `geocode_cache` table: `COUNT(*)`, `SUM(hit_count)`, estimated savings at $0.005/request. New endpoint `GET /api/geocode-stats` or add to upload response. |
| **Driver-verified coordinate promotion** | When a driver confirms delivery at a GPS location, save those coordinates as a `driver_verified` cache entry (confidence=0.95). Over 6 months, this builds a Kerala-specific address database more accurate than Google. | LOW | Already partially implemented: `GeocodeCacheDB` supports `source="driver_verified"`, and the `PostGISGeocodingCache.save_driver_verified()` method exists. Need to wire: when telemetry status update includes coordinates AND status="delivered", call save with source="driver_verified". |

#### Anti-Features (Do NOT Build)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Automatic TTL-based cache invalidation** | "Addresses might change over time" | Physical addresses do not move. A 30-day TTL forces re-geocoding the same addresses monthly, wasting $5/1000 API calls for zero benefit. Only new construction warrants re-geocoding (and that's a new address, not a changed one). | No expiration. Manual invalidation only. Add admin "re-geocode this address" button in a future admin panel if ever needed. |
| **Fuzzy address matching (Levenshtein/trigram)** | "Near SBI MG Road and nr. SBI MG Rd should match" | False positives could assign WRONG coordinates to an order. "Near SBI, MG Road, Kochi" and "Near SBI, MG Road, Kozhikode" would fuzzy-match but are 300km apart. Kerala has many similar-sounding place names. Safety-critical system cannot tolerate false geocode matches. | Exact normalized match only. If an address is not in cache, call Google API (it handles fuzzy matching with geographic context). Keep humans in the loop for ambiguous addresses. |
| **Multiple geocoding provider fallback** | "If Google is down, use Nominatim as backup" | Different providers return slightly different coordinates for the same address. Mixing results in the cache creates route inconsistency. Nominatim's Kerala data is significantly less accurate (rural India coverage is poor). | Single provider (Google). If Google is down, queue orders for retry rather than falling back to an inferior provider. Surface the error clearly: "Geocoding service unavailable -- try again in a few minutes". |
| **Reverse geocoding for telemetry pings** | "Show human-readable address for every GPS point on the map" | 25,000 pings/day x $0.005/request = $125/day = $45K/year. Completely unnecessary for fleet monitoring. | Show raw coordinates on hover. Reverse geocode only on demand (admin clicks a point). Cache the reverse result for future lookups. |
| **Google Places autocomplete for manual address entry** | "Help users type correct addresses" | Google Places API costs $2.83/1000 sessions. Requires client-side API key (security risk). Users don't type addresses -- CDCMS CSV provides them. | Addresses come from CDCMS export. No manual entry needed in v1.1. If manual override is added later, use server-side geocoding with result preview, not client-side autocomplete. |

---

## Feature Dependencies

```
[Unified cache normalization]
    +-- requires --> [Single source of truth (deprecate file cache)]
    +-- enables --> [Duplicate location detection]
    +-- enables --> [Cache migration tool]
    +-- enables --> [Geocoding cost tracking (accurate counts)]

[DaisyUI consistency across all 4 pages]
    +-- enables --> [Theme switcher (light/dark)]
    +-- enables --> [Loading/empty states with DaisyUI skeletons]
    +-- enables --> [Color-coded status badges]
    +-- enables --> [Capacity utilization bars]

[Next-stop hero card (PWA)]
    +-- requires --> [Stop status tracking (ALREADY EXISTS)]
    +-- enhances --> [Focus mode (next-stop-only view)]
    +-- enhances --> [Auto-advance after confirmation]

[Visual progress indicator (PWA)]
    +-- requires --> [Stop status tracking (ALREADY EXISTS)]
    +-- enhances --> [Next-stop hero card]

[Geocoding cost tracking]
    +-- requires --> [Counter addition in upload endpoint]
    +-- requires --> [New fields in OptimizationSummary response model]
    +-- enables --> [Cost indicator display in ImportSummary UI]
    +-- enables --> [Cache statistics endpoint]

[Offline sync indicator (PWA)]
    +-- requires --> [Offline queue in localStorage (ALREADY EXISTS)]
    +-- enhances --> [Pull-to-refresh mechanism]

[Cache migration tool]
    +-- requires --> [Unified normalization function finalized]
    +-- requires --> [File cache deprecation decided]

[Driver-verified coordinate promotion]
    +-- requires --> [Status update GPS capture (ALREADY EXISTS)]
    +-- requires --> [Telemetry endpoint wiring to save_geocode_cache]
    +-- enhances --> [Duplicate location detection accuracy over time]
```

### Dependency Notes

- **Unified normalization MUST happen before cache migration.** The normalization algorithm must be settled before migrating historical file-cache data, otherwise migration would need to be re-run.
- **Deprecating file cache MUST happen alongside normalization.** Cannot have consistent cache behavior with two caches using different key strategies. GoogleGeocoder's internal `_cache` dict and `_save_cache()` should be removed or made inert.
- **DaisyUI consistency MUST come before theme switcher.** Cannot toggle themes until all pages use DaisyUI. Partially-themed pages would have some elements respond to theme change and others ignore it.
- **Next-stop hero card is independent of geocoding fixes.** These two domains (PWA refresh + geocoding) can be worked in parallel by different developers or phases.
- **Cost tracking requires both backend (counters) and frontend (display).** Backend change is prerequisite. Frontend display is a small addition to the existing ImportSummary component.

---

## MVP Definition

### Must Ship in v1.1 (P1)

These directly address the milestone goals stated in PROJECT.md:

- [ ] **Unified cache normalization** -- fix the root cause of duplicate map locations (geocoding data integrity)
- [ ] **Deprecate file-based geocode cache** -- single source of truth through DB cache only
- [ ] **Duplicate location detection** -- flag orders resolving to same GPS coordinates
- [ ] **Geocoding cost tracking** -- cache hit vs API call indicator per upload
- [ ] **DaisyUI consistency across all 4 dashboard pages** -- professional logistics SaaS look
- [ ] **SVG icons replacing emoji nav items** -- professional sidebar appearance
- [ ] **Loading and empty states** -- no more blank pages when data is absent
- [ ] **Next-stop hero card in driver PWA** -- simplified driver workflow
- [ ] **Visual progress indicator in PWA** -- delivery progress visibility
- [ ] **Pull-to-refresh in driver PWA** -- route data freshness control
- [ ] **Touch target audit (60px+)** -- verify all primary actions meet outdoor-use size requirements
- [ ] **High-contrast text audit** -- verify WCAG AAA (7:1) on all color combinations

### Should Have (P2 -- add during v1.1 if time permits)

- [ ] **Color-coded status badges** on route cards -- quick visual scanning
- [ ] **Per-vehicle capacity utilization bar** -- load balance visibility
- [ ] **Daily summary card** -- at-a-glance operational overview
- [ ] **Cache migration tool** -- preserve historical geocoding investment (run once at deploy)
- [ ] **Theme switcher (light/dark)** -- add after DaisyUI consistency is proven
- [ ] **Auto-advance after delivery confirmation** -- smoother driver workflow
- [ ] **Haptic feedback on delivery confirmation** -- tactile confirmation for outdoor use
- [ ] **Geocoding cost indicator in dashboard** -- surface cost tracking in ImportSummary UI
- [ ] **Responsive sidebar improvements** -- DaisyUI drawer for mobile breakpoint

### Future Consideration (v1.2+)

- [ ] **Focus mode (next-stop-only view)** in PWA -- after hero card validates the pattern
- [ ] **Offline sync queue indicator** -- after validating offline queue reliability
- [ ] **Cache statistics endpoint** -- when office staff request ongoing cost visibility
- [ ] **Driver-verified coordinate promotion** -- wire GPS delivery data to cache
- [ ] **Address similarity matching (fuzzy)** -- HIGH complexity, safety risk, defer until cache miss rate is measured
- [ ] **Keyboard shortcuts** -- after core UI is stable and user feedback gathered
- [ ] **At-a-glance daily summary with trend** -- requires storing historical run metrics for comparison

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Unified cache normalization | HIGH | MEDIUM | P1 |
| Deprecate file-based cache | HIGH | MEDIUM | P1 |
| Duplicate location detection | HIGH | MEDIUM | P1 |
| Geocoding cost tracking (backend) | MEDIUM | LOW | P1 |
| DaisyUI consistency all pages | HIGH | MEDIUM | P1 |
| SVG icons replacing emojis | MEDIUM | LOW | P1 |
| Loading/empty states | MEDIUM | LOW | P1 |
| Next-stop hero card (PWA) | HIGH | MEDIUM | P1 |
| Progress indicator (PWA) | MEDIUM | LOW | P1 |
| Pull-to-refresh (PWA) | MEDIUM | LOW | P1 |
| Touch target audit | HIGH | LOW | P1 |
| Contrast audit | HIGH | LOW | P1 |
| Status badges on route cards | MEDIUM | LOW | P2 |
| Capacity utilization bars | MEDIUM | LOW | P2 |
| Daily summary card | MEDIUM | MEDIUM | P2 |
| Cache migration tool | MEDIUM | LOW | P2 |
| Theme switcher | LOW | LOW | P2 |
| Auto-advance (PWA) | MEDIUM | LOW | P2 |
| Haptic feedback (PWA) | LOW | LOW | P2 |
| Cost indicator in UI | MEDIUM | LOW | P2 |
| Focus mode (PWA) | MEDIUM | MEDIUM | P3 |
| Offline sync indicator | MEDIUM | MEDIUM | P3 |
| Cache statistics endpoint | LOW | LOW | P3 |
| Driver-verified promotion | MEDIUM | LOW | P3 |
| Fuzzy address matching | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must have for v1.1 milestone completion
- P2: Should have, add during v1.1 if time permits or as immediate follow-up
- P3: Nice to have, defer to v1.2+ milestone

---

## Competitor Feature Analysis

| Feature | Route4Me | Routific | DispatchTrack | Our v1.1 Approach |
|---------|----------|----------|---------------|-------------------|
| Dashboard design | Complex, feature-heavy, dated UI | Clean minimal, modern | Enterprise-heavy, many panels | Clean minimal with DaisyUI -- closest to Routific aesthetic but simpler for single-depot use case |
| Driver app platform | Native Android/iOS | Native apps | Native with full offline | PWA (no app store, zero install friction for 13 drivers). Trade-off: less native feel but appropriate for small fleet |
| Next-stop prominence | Dedicated screen | Top card with large address | Large card with navigate button | Hero card at top of stop list. Optional focus mode later. |
| Outdoor readability | Standard contrast | Standard contrast | Configurable themes | WCAG AAA (7:1) dark-first design. Exceeds all competitors. Kerala-specific requirement. |
| Geocoding transparency | Hidden behind the scenes | Hidden behind the scenes | Hidden behind the scenes | **Unique:** Transparent cost tracking shown to office staff after each upload |
| Offline support | Limited | Limited | Full offline with sync | Full offline via service worker + localStorage queue. Comparable to DispatchTrack. |
| Duplicate detection | Manual review | Address validation warnings | Pre-route validation | Coordinate-proximity detection flagged automatically in import summary |
| Cache management | Not user-visible | Not user-visible | Not user-visible | **Unique:** Cache hit rate, API call count, estimated cost visible to operators |

---

## Sources

- [DispatchTrack Mobile App UX Refresh](https://www.dispatchtrack.com/blog/mobile-app-ui-ux/) -- driver app redesign patterns, outdoor readability improvements
- [Last-Mile Delivery Driver App UX Optimization](https://www.zigpoll.com/content/how-can-our-ux-designers-optimize-the-mobile-app-interface-to-reduce-delivery-time-errors-and-improve-driver-efficiency-for-lastmile-logistics) -- next-stop workflow, one-handed operation, progressive disclosure, bottom thumb zone placement
- [Redesigning a Delivery Driver App (Medium)](https://amillionadventures.medium.com/redesigning-orderins-delivery-driver-app-part-1-research-1ba39ee70b1a) -- research-based driver app redesign with outdoor contrast findings
- [AddressHub: Caching Geocoding Results](https://address-hub.com/address-intelligence/caching/) -- cache normalization, TTL strategy, cost reduction metrics (10-20ms cache vs 100-300ms API)
- [Radar: Complete Guide to Geocoding APIs](https://radar.com/blog/geocoding-apis) -- caching best practices, normalize before provider calls, deduplication
- [Deduplicate Location Records (Towards Data Science)](https://towardsdatascience.com/deduplicate-and-clean-up-millions-of-location-records-abcffb308ebf/) -- geospatial clustering for duplicate detection
- [DaisyUI Themes Documentation](https://daisyui.com/docs/themes/) -- built-in 35 themes, light/dark mode, theme generator
- [Logistics KPIs That Matter in 2026 (Locus)](https://blog.locus.sh/logistics-kpi/) -- delivery dashboard metrics: on-time rate, cost per delivery, fleet utilization
- [PWA Offline-First Strategies (MagicBell)](https://www.magicbell.com/blog/offline-first-pwas-service-worker-caching-strategies) -- service worker caching patterns: cache-first, network-first, stale-while-revalidate
- [Logistics Dashboard Design Trends 2026 (Muzli)](https://muz.li/blog/best-dashboard-design-examples-inspirations-for-2026/) -- information hierarchy, visual weight, key metrics at top
- Codebase analysis: `.planning/codebase/CONCERNS.md` (dual-cache normalization bug), `ARCHITECTURE.md` (data flow), `STACK.md` (tech decisions)

---
*Feature research for: Kerala LPG Delivery Route Optimizer v1.1 -- Dashboard UI Overhaul, Driver PWA Refresh, Geocoding Cache Fixes*
*Researched: 2026-03-01*
