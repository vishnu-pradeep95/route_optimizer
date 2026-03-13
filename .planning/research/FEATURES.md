# Feature Landscape

**Domain:** Driver-centric delivery management -- driver management, per-driver TSP optimization, route validation, geocode cache management, upload history, settings
**Researched:** 2026-03-12
**Milestone:** v3.0 (Driver-Centric Model)
**Overall Confidence:** MEDIUM-HIGH

## Context

This research covers features for the v3.0 milestone which transforms the system from a vehicle-fleet CVRP model to a driver-centric TSP model. The CDCMS CSV already contains a "DeliveryMan" column that pre-assigns orders to drivers. The optimizer's job shifts from "assign orders to vehicles" (CVRP) to "find optimal stop sequence for each driver's pre-assigned orders" (TSP per driver).

Existing infrastructure leveraged:
- VROOM solver (already supports single-vehicle TSP when given one vehicle)
- PostgreSQL `drivers` table (exists but unused)
- `optimization_runs` table with `source_filename` (partial upload history)
- `geocode_cache` table with `hit_count`, `last_used_at`, `confidence`, `source`
- Google Maps route URL generation (QR codes, navigation links)
- Dashboard with DaisyUI/Tailwind v4, sidebar navigation, skeleton loading
- Driver PWA with offline support, hero card architecture

---

## Table Stakes

Features users expect from any driver-centric delivery management system. Missing any of these makes the v3.0 transition feel broken or incomplete.

### 1. Vehicle-to-Driver Conceptual Rename

| Aspect | Detail |
|--------|--------|
| **Why Expected** | The system currently says "Vehicle VEH-01" everywhere but the office staff thinks in terms of drivers ("Rajan's route"). CDCMS data uses "DeliveryMan" -- the system should match the mental model. |
| **Complexity** | LOW-MEDIUM |
| **What Changes** | DB: `routes.vehicle_id` -> `routes.driver_id` (or add driver_id alongside). API: response fields use "driver" terminology. Dashboard: "Fleet Management" -> "Drivers" page. TypeScript types: `Vehicle` interface adapted or replaced with `Driver`. |
| **Dependencies** | None -- pure renaming/aliasing. Can be done incrementally with backward-compatible aliases. |
| **Risk** | Breaking change to API consumers if not aliased. Driver PWA fetches by `vehicle_id` -- must be updated or route API must accept either. |
| **Existing code affected** | `VehicleDB` model, `FleetManagement.tsx`, `types.ts` (`Vehicle`, `RouteSummary.vehicle_id`), API endpoints (`/api/vehicles`, `/api/routes/{vehicle_id}`), Driver PWA route fetching. |

### 2. Driver Auto-Creation from CSV

| Aspect | Detail |
|--------|--------|
| **Why Expected** | Office staff upload a CDCMS export that already has a "DeliveryMan" column. Requiring them to manually create each driver before uploading is wasted effort. The system should learn driver names from the data it ingests. |
| **Complexity** | LOW |
| **What Changes** | During CSV upload, extract unique DeliveryMan values, check against `drivers` table, auto-create new entries with `is_active=true`. Return creation count in upload response. |
| **Dependencies** | Depends on CDCMS preprocessor detecting the DeliveryMan column. |
| **Risk** | Name normalization -- "RAJAN K" vs "Rajan K" vs "RAJAN.K" must resolve to the same driver. Use `normalize_driver_name()` with case-insensitive matching + whitespace/punctuation normalization. |
| **Industry pattern** | Standard in logistics software -- Detrack, Onfleet, and Route4Me all auto-detect drivers from import files. First-seen names create records; subsequent uploads match against existing records. |

### 3. Manual Driver Add/Edit/Deactivate

| Aspect | Detail |
|--------|--------|
| **Why Expected** | Auto-creation handles the common case but office staff need to correct typos (CSV had "RAJN K" instead of "RAJAN K"), add phone numbers for the Call Office button, and deactivate drivers who left. |
| **Complexity** | LOW (existing `FleetManagement.tsx` pattern can be adapted) |
| **What Changes** | Rename/adapt FleetManagement page to "Drivers" page. Replace vehicle-specific fields (max_weight_kg, depot_location, speed_limit) with driver-specific fields (name, phone, assigned vehicle, status). Keep inline edit pattern (already proven UX). |
| **Dependencies** | Driver table schema must support all needed fields. Existing `DriverDB` model already has `name`, `phone`, `vehicle_id`, `is_active`. |
| **Existing code reused** | 80%+ of `FleetManagement.tsx` logic (CRUD operations, inline editing, error handling, form validation). `EmptyState`, `ErrorBanner` components unchanged. |

### 4. Per-Driver TSP Optimization

| Aspect | Detail |
|--------|--------|
| **Why Expected** | With CDCMS pre-assigning orders to drivers, the optimizer should find the best stop sequence for each driver -- not reassign orders across the fleet. This is TSP (one driver, optimal sequence) not CVRP (many vehicles, assignment + sequencing). |
| **Complexity** | MEDIUM |
| **What Changes** | After CSV parsing, group orders by DeliveryMan. For each driver, create a VROOM request with exactly one vehicle and that driver's orders. VROOM naturally solves TSP when given one vehicle. Collect results into a unified `RouteAssignment`. |
| **Dependencies** | Driver auto-creation (need driver records to map DeliveryMan column values). Vehicle capacity constraints still apply (each driver has an assigned vehicle). |
| **Technical detail** | VROOM handles TSP as a special case of VRP with one vehicle. No solver change needed -- just change how we partition the input. Send N requests (one per driver) instead of one request with all orders and vehicles. Each request is tiny (10-30 jobs, 1 vehicle) so VROOM solves in <10ms each. Total wall time similar to current single CVRP solve. |
| **Risk** | If CDCMS data has an unrecognized DeliveryMan value or missing column, the system needs a fallback. Options: (a) error out clearly, (b) assign unmatched orders to a "default" driver, (c) fall back to fleet-wide CVRP. Option (a) is safest for data integrity. |
| **Industry context** | Per-driver TSP is standard when assignment is pre-determined. Route4Me, OptimoRoute, and RoadWarrior all support "optimize sequence only" mode alongside full fleet dispatch. |

### 5. Improved CSV Upload Flow

| Aspect | Detail |
|--------|--------|
| **Why Expected** | Current upload immediately triggers optimization for the entire fleet. With the driver-centric model, the office employee should see which drivers were detected, how many orders each has, and confirm before optimizing. |
| **Complexity** | MEDIUM |
| **What Changes** | Two-step upload: (1) parse + validate + show driver summary, (2) confirm to optimize. The summary screen shows detected drivers, order counts, any new drivers that will be created, and validation warnings. |
| **Dependencies** | CDCMS preprocessor must extract DeliveryMan column. Driver auto-creation logic must be ready. |
| **Risk** | Adding a confirmation step slows the workflow. Mitigate by making confirmation fast (single button click, no additional form fields). The parsing step should be <2 seconds. |

### 6. Upload History / Audit Trail

| Aspect | Detail |
|--------|--------|
| **Why Expected** | The existing `optimization_runs` table already stores `source_filename`, `created_at`, `total_orders`, `status`. The `RunHistory.tsx` page already displays this. But office staff want to see "what file did I upload yesterday?" and re-run optimization on past data. This is table stakes for any business tool that processes file uploads. |
| **Complexity** | LOW (mostly already exists) |
| **What Changes** | Enhance `RunHistory` page: show source filename prominently, add filter by date range, add driver breakdown per run. The API already returns this data via `GET /api/runs`. Minor API enhancement: add `drivers_in_run` count to run response. |
| **Dependencies** | None -- builds on existing `optimization_runs` table and `RunHistory.tsx`. |
| **Existing code reused** | `RunHistory.tsx` page structure, `fetchRuns()` API call, expandable row pattern, skeleton loading. |
| **What NOT to build** | Re-upload/re-process from history -- this requires storing the original CSV file (storage cost, privacy concerns with PII like addresses). Instead, the employee re-uploads a fresh file. Show history for audit/reference, not replay. |

### 7. Dashboard Settings Page

| Aspect | Detail |
|--------|--------|
| **Why Expected** | Google Maps API key is currently set via environment variable. Office staff cannot change it without SSH access. A settings page lets them manage the API key, see system configuration, and access cache stats -- all standard admin features. |
| **Complexity** | LOW-MEDIUM |
| **What Changes** | New dashboard page with sections: (a) Google Maps API key input (masked, test button), (b) system info (depot location, safety multiplier -- read-only from `/api/config`), (c) geocode cache stats. |
| **Dependencies** | API endpoint for updating/testing API key. API endpoint for cache stats. |
| **Risk** | API key security -- must be stored encrypted or in environment variable, never in localStorage. The API key should be settable via dashboard but stored server-side. Send to API via authenticated POST, mask in GET response (show last 4 chars). |
| **Industry pattern** | Every SaaS settings page follows the same pattern: section header, form fields, save button, success toast. Stripe, Datadog, and MoEngage all manage API keys through Settings > API Keys. |

---

## Differentiators

Features that set this system apart. Not universally expected, but high-value for this specific deployment context.

### 8. Google Maps Route Validation / Confidence Comparison

| Aspect | Detail |
|--------|--------|
| **Value Proposition** | Compare OSRM-calculated route distance/duration against Google Maps Routes API for the same waypoints. Large discrepancies (>30% difference) suggest geocoding errors or road network issues. This is a "trust but verify" signal that catches subtle problems OSRM's OSM data might miss (e.g., a road closed for construction that Google knows about). |
| **Complexity** | MEDIUM |
| **What Changes** | After VROOM optimization, call Google Maps Routes API (`computeRoutes`) with the same waypoints. Compare total distance and duration. Store discrepancy as a route-level confidence metric. Surface in dashboard as a green/amber/red indicator per route. |
| **Dependencies** | Google Maps API key must be configured. Requires Google Maps Routes API to be enabled (separate from Geocoding API). |
| **Cost** | Routes API: $0.005/route for basic, $0.01/route with traffic. At 13 routes/day: $0.065-$0.13/day (~$2-4/month). Acceptable for validation. |
| **Risk** | Different routing engines use different road networks and speed profiles. OSRM uses OSM data (community-maintained); Google uses proprietary data with real-time traffic. Some discrepancy is expected and normal. The threshold (>30%) needs calibration with real data. |
| **Industry context** | Onfleet and LogiNext both offer "route confidence" scores but implement them differently. Most compare planned vs actual (post-delivery), not planned vs alternative engine. Pre-delivery comparison using Google is uncommon and genuinely differentiating. |

### 9. Geocode Cache Management Dashboard

| Aspect | Detail |
|--------|--------|
| **Value Proposition** | The geocode cache is the system's most valuable asset -- over time it builds a verified address database for the delivery zone. Giving office staff visibility into cache health (total entries, hit rate, source breakdown, stale entries) builds trust and enables proactive maintenance. |
| **Complexity** | LOW-MEDIUM |
| **What Changes** | New section in Settings or dedicated page. API endpoints: `GET /api/cache/stats` (total entries, hits, misses, source breakdown, staleness distribution), `DELETE /api/cache/{id}` (purge single entry with API key auth). Dashboard shows stats cards and optionally a searchable table of cached addresses. |
| **Dependencies** | Existing `geocode_cache` table has all needed fields (`hit_count`, `last_used_at`, `source`, `confidence`). |
| **Risk** | Cache purge must be authenticated (API key required). Accidental bulk delete could force expensive re-geocoding. Add confirmation dialog. Do NOT expose bulk delete initially -- single-entry purge only. |
| **Google ToS note** | Google's Terms of Service restrict caching geocoding results to 30 days. However, the system's cache stores driver-verified coordinates (`source='driver_verified'`) and manually corrected coordinates (`source='manual'`) which are not subject to Google's restriction -- they are first-party data. Only `source='google'` entries are subject to the 30-day limit. A cache management UI could flag stale Google entries (>30 days since `created_at`). |

### 10. Multi-Format CSV Support

| Aspect | Detail |
|--------|--------|
| **Value Proposition** | CDCMS exports can be .csv or .xlsx. The current system accepts both but the CDCMS preprocessor has fragile column detection. Better format handling (auto-detect delimiter, handle BOM, detect .xlsx masquerading as .csv) reduces upload failures. |
| **Complexity** | LOW |
| **What Changes** | Improve `CsvImporter` and `cdcms_preprocessor.py`: add BOM stripping, try multiple delimiters (comma, semicolon, tab), validate .xlsx magic bytes vs extension, better error messages for format mismatches. |
| **Dependencies** | None -- enhancement to existing code. |

### 11. CDCMS Preprocessing Fixes

| Aspect | Detail |
|--------|--------|
| **Value Proposition** | Known issues: address garbling in certain CDCMS exports, .xlsx files with wrong extension not detected, inconsistent column naming between CDCMS versions. Fixing these reduces the "upload failed" rate that frustrates office staff. |
| **Complexity** | LOW |
| **What Changes** | Harden `preprocess_cdcms()`: handle more column name variants, improve error messages for unrecognized columns, add `.xlsx` content-type sniffing. |
| **Dependencies** | None. |

---

## Anti-Features

Features that seem useful but would cause harm for this specific system and use case.

| Anti-Feature | Why Commonly Requested | Why Avoid | What to Do Instead |
|--------------|----------------------|-----------|-------------------|
| **Drag-and-drop route reordering** | Operators want to manually adjust stop sequences. Every competitor offers it. | Undermines the VROOM optimizer. Manual overrides create suboptimal routes and make the system feel unreliable ("if I have to fix it myself, why use an optimizer?"). Already in PROJECT.md Out of Scope. | Trust the optimizer. If stop sequence is wrong, the root cause is bad geocoding (fix the address), not bad optimization. |
| **Driver assignment UI (drag drivers to orders)** | "Let me choose which driver gets which stop." Feels like control. | CDCMS already assigns drivers in the CSV. Manual reassignment contradicts the source-of-truth data. If the office wants different assignments, they should change the CDCMS export, not override in the optimizer. | Auto-detect from CSV. Provide clear error messages when DeliveryMan column is missing or has issues. |
| **Real-time route recalculation** | "A stop was cancelled mid-route, re-optimize the remaining stops." | Requires the driver to have connectivity (Kerala has spotty mobile networks in rural areas). Re-routing mid-delivery confuses drivers who memorized the sequence. The 10-30 stop routes are short enough that skipping one stop doesn't materially change efficiency. | Driver marks stop as "Failed" and moves to next stop. The PWA already handles this with auto-advance. |
| **Driver shift scheduling** | "Manage driver availability, working hours, break times." | Over-engineers the workflow. This is a single-depot, single-shift operation. All 13 drivers work the same hours. Shift management adds complexity with zero benefit for this deployment. | Single implicit shift. If multi-shift is ever needed, it is a future milestone. |
| **Driver performance dashboards** | "Show delivery speed, on-time percentage, stops per hour." | Introduces surveillance dynamics that damage driver trust. Kerala labor relations are sensitive to monitoring. The system should help drivers, not evaluate them. Also, accuracy requires GPS telemetry analysis that is out of scope for v3.0. | Track delivery completion (already done via status updates). Performance analytics is a separate future concern if ever needed. |
| **Editable API key in localStorage** | "Let me type the API key in the browser settings." | API keys in browser storage are vulnerable to XSS attacks. Any script on the page can read localStorage. | Server-side API key storage. Dashboard sends key to authenticated API endpoint. Response shows masked key (last 4 chars). Key never stored client-side. |
| **Geocode cache auto-purge** | "Automatically delete cache entries older than 30 days." | Driver-verified entries (source='driver_verified') are first-party data exempt from Google's 30-day restriction. Auto-purging would destroy the most valuable data in the system. | Manual purge of individual entries. Flag Google-sourced entries >30 days old but do not auto-delete. Let the operator decide. |
| **Bulk cache operations** | "Select all and delete" in the cache management UI. | Accidental bulk delete forces expensive re-geocoding of the entire address database. One misclick destroys months of accumulated cache value. | Single-entry delete only, with confirmation dialog. If bulk cleanup is needed, provide a server-side script for IT staff with double-confirmation. |

---

## Feature Dependencies

```
[CDCMS DeliveryMan column detection]
    |
    +--enables--> [Driver auto-creation from CSV]
    |                 |
    |                 +--enables--> [Per-driver TSP optimization]
    |                 |                 |
    |                 |                 +--feeds--> [Route validation vs Google Maps]
    |                 |
    |                 +--populates--> [Driver management page]
    |
    +--enables--> [Improved upload flow with driver summary]
                      |
                      +--links to--> [Upload history (enhanced RunHistory)]

[Dashboard Settings page]  (independent)
    |
    +--contains--> [API key management]
    |                  |
    |                  +--required by--> [Route validation] (needs Routes API enabled)
    |
    +--contains--> [Geocode cache stats + management]

[Vehicle-to-Driver rename]  (can be incremental, partially independent)
    |
    +--affects--> [Dashboard pages, API responses, TypeScript types]
    +--affects--> [Driver PWA route fetching]

[CDCMS preprocessing fixes]  (independent)
[Multi-format CSV support]  (independent)
```

### Critical Path

The critical dependency chain is:

1. DeliveryMan column detection in CDCMS preprocessor
2. Driver auto-creation from detected names
3. Per-driver grouping and TSP optimization
4. Dashboard showing per-driver results

Everything else (settings, cache management, route validation, upload history) can be built in parallel or after the critical path.

### Independence Notes

- **Settings page** is fully independent -- no dependency on driver model changes. Can be built in any phase.
- **Upload history enhancements** build on existing `RunHistory.tsx` and `optimization_runs` table. Independent of driver model.
- **Cache management** is independent -- only depends on existing `geocode_cache` table.
- **Route validation** depends on Google Maps API key being configured (Settings page helps here) and routes being generated (optimization pipeline).
- **Vehicle-to-Driver rename** is a cross-cutting concern that touches many files but has no functional dependency on other features. Can be done gradually with backward-compatible aliases.

---

## MVP Recommendation

### Phase 1: Driver Model Foundation (Critical Path)

These features must ship together to make the v3.0 transition functional.

1. **CDCMS DeliveryMan column detection** -- parse the column, extract driver names
2. **Driver auto-creation** -- create driver records from CSV data
3. **Per-driver TSP optimization** -- group orders by driver, VROOM TSP per group
4. **Vehicle-to-Driver rename** (at least in UI terminology) -- dashboard and API say "driver" not "vehicle"
5. **Driver management page** -- adapted from FleetManagement.tsx
6. **Improved upload flow** -- show driver summary before optimizing

### Phase 2: Operational Polish

Add after core driver model works:

7. **Upload history enhancements** -- date filter, driver breakdown, filename display
8. **Dashboard Settings page** -- API key management, system info, cache overview
9. **CDCMS preprocessing fixes** -- hardening for edge cases
10. **Multi-format CSV support** -- .xlsx detection, delimiter handling

### Phase 3: Validation and Confidence

Add after baseline routes are flowing correctly:

11. **Google Maps route validation** -- compare OSRM vs Google distances
12. **Geocode cache management** -- stats dashboard, single-entry purge
13. **Geocode validation tightening** -- 20km radius (from current 30km)

### Defer

- Driver performance dashboards -- explicitly avoid
- Driver shift scheduling -- single shift, no complexity needed
- Drag-and-drop route reordering -- undermines optimizer

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority | Phase |
|---------|------------|---------------------|----------|-------|
| CDCMS DeliveryMan detection | HIGH | LOW | P0 | 1 |
| Driver auto-creation from CSV | HIGH | LOW | P0 | 1 |
| Per-driver TSP optimization | HIGH | MEDIUM | P0 | 1 |
| Vehicle-to-Driver rename (UI) | HIGH | MEDIUM | P0 | 1 |
| Driver management page | HIGH | LOW | P0 | 1 |
| Improved upload flow | MEDIUM | MEDIUM | P1 | 1 |
| CDCMS preprocessing fixes | MEDIUM | LOW | P1 | 2 |
| Multi-format CSV support | MEDIUM | LOW | P1 | 2 |
| Upload history enhancements | MEDIUM | LOW | P1 | 2 |
| Dashboard Settings page | MEDIUM | MEDIUM | P1 | 2 |
| API key management | MEDIUM | LOW | P1 | 2 |
| Google Maps route validation | MEDIUM | MEDIUM | P2 | 3 |
| Geocode cache stats/management | LOW-MEDIUM | LOW-MEDIUM | P2 | 3 |
| Geocode validation tightening | LOW | LOW | P2 | 3 |

**Priority key:**
- P0: Must have for v3.0 to be functional (driver-centric model works end-to-end)
- P1: Should have for v3.0 to feel polished (operational quality of life)
- P2: Nice to have, improves confidence and maintainability

---

## Existing Infrastructure Leveraged

| Existing Component | How v3.0 Features Use It |
|--------------------|--------------------------|
| `DriverDB` model (table exists, unused) | Driver auto-creation populates this table. Driver management page reads/writes it. |
| `VroomAdapter.optimize()` | Per-driver TSP calls this with a single vehicle -- VROOM handles TSP as VRP with 1 vehicle. No solver change needed. |
| `optimization_runs` table | Upload history already stored. Enhance with driver_count, display in RunHistory. |
| `geocode_cache` table | Cache management reads `hit_count`, `last_used_at`, `source`, `confidence`. All fields already exist. |
| `FleetManagement.tsx` | Driver management page reuses 80%+ of this code: CRUD pattern, inline editing, form validation, error handling. |
| `RunHistory.tsx` | Upload history page reuses expandable row pattern, skeleton loading, date formatting. |
| `UploadRoutes.tsx` | Upload flow enhanced with driver summary step. Existing drop zone, progress feedback, error display all reused. |
| `/api/config` endpoint | Settings page reads depot location, safety multiplier from this existing endpoint. |
| `cdcms_preprocessor.py` | DeliveryMan column detection adds to existing preprocessing. `CDCMS_COL_*` constants pattern followed. |
| DaisyUI component library | Settings page uses existing `tw:stat`, `tw:input`, `tw:alert` classes. No new dependencies. |
| `ErrorBanner`, `EmptyState`, `StatusBadge` components | Reused across all new pages without modification. |
| Google Maps API key in env var | Settings page provides UI for what is currently an env var. Backward compatible -- env var remains as fallback. |

---

## Competitor Feature Analysis

| Feature | Route4Me | OptimoRoute | Onfleet | This System (v3.0) |
|---------|----------|-------------|---------|---------------------|
| Driver auto-detect from CSV | Yes, column mapping | Yes, import wizard | No (API-only) | Auto-detect DeliveryMan column, fuzzy name matching |
| Per-driver optimization | "Optimize sequence only" mode | TSP mode toggle | Per-driver dispatch | VROOM TSP per driver group |
| Route validation | Distance vs ETA comparison | Google Maps overlay | Post-delivery comparison | OSRM vs Google Maps pre-delivery comparison |
| Cache management | Not exposed | Not exposed | Not exposed | Stats dashboard with per-entry purge |
| Upload history | Import log with status | Batch import history | API audit log | Enhanced RunHistory with driver breakdown |
| Settings page | Full admin panel | Settings > Integrations | Dashboard > Settings | API key + cache stats + system info |
| Driver management | Full driver profiles | Driver + vehicle pairing | Team management | Auto-create + manual CRUD, inline editing |

---

## Sources

- [VROOM Project GitHub](https://github.com/VROOM-Project/vroom) -- VROOM handles TSP as VRP with 1 vehicle (HIGH confidence)
- [Nextmv: TSP vs CVRP](https://www.nextmv.io/blog/tsp-pdtsp-cvrp-cvrptw-oh-my-the-alphabet-soup-of-route-optimization) -- when to use TSP vs CVRP (MEDIUM confidence)
- [Google Maps Routes API: Compute Routes](https://developers.google.com/maps/documentation/routes/compute_route_directions) -- route distance/duration comparison (HIGH confidence)
- [Google Maps Route Optimization API](https://developers.google.com/maps/documentation/route-optimization/overview) -- Google's fleet optimization offering (HIGH confidence)
- [Google Maps Geocoding Policies](https://developers.google.com/maps/documentation/geocoding/policies) -- 30-day cache restriction, Place ID exemption (HIGH confidence)
- [Google Cloud Maps Service Terms](https://cloud.google.com/maps-platform/terms/maps-service-terms) -- caching restrictions on geocoding results (HIGH confidence)
- [OSRM vs Google comparison tool](https://github.com/yklyahin/osrm-google-comparison) -- open-source distance comparison methodology (MEDIUM confidence)
- [LogisticsOS: Comparing Matrix Routing Services](https://www.logisticsos.com/blog/distance-matrix) -- OSRM vs Google accuracy analysis (MEDIUM confidence)
- [Coaxsoft: Driver Management Software Guide](https://coaxsoft.com/blog/guide-to-driver-management-software) -- industry feature expectations (MEDIUM confidence)
- [Detrack: Delivery Management](https://www.detrack.com/) -- competitor feature reference (LOW confidence, marketing material)
- [Route4Me](https://www.route4me.com/) -- competitor feature reference for sequence-only optimization (LOW confidence)
- [Stripe API Key Management](https://docs.stripe.com/keys) -- settings page UX pattern reference (HIGH confidence)
- [Opsgenie API Key Management](https://support.atlassian.com/opsgenie/docs/api-key-management/) -- settings page pattern (MEDIUM confidence)
- [Mapscaping: Geocoding API Pricing Guide](https://mapscaping.com/guide-to-geocoding-api-pricing/) -- Google Maps API cost reference (MEDIUM confidence)

---
*Feature research for: Driver-centric delivery management (v3.0)*
*Researched: 2026-03-12*
