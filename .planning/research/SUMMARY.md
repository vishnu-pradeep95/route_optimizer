# Project Research Summary

**Project:** Kerala LPG Delivery Route Optimizer -- v3.0 Driver-Centric Model
**Domain:** Driver-centric delivery route optimization (CVRP-to-TSP transition, dashboard admin features)
**Researched:** 2026-03-12
**Confidence:** HIGH

## Executive Summary

The v3.0 milestone transforms the Kerala LPG delivery optimizer from a vehicle-fleet CVRP model to a driver-centric TSP model. The core insight is that the CDCMS CSV already pre-assigns orders to drivers via its `DeliveryMan` column, but the current system ignores this assignment and re-assigns all orders across 13 vehicles. The fix is conceptually simple: group orders by driver, run VROOM TSP (1 vehicle, N jobs) per driver, and surface driver names instead of vehicle IDs throughout the UI. This is an architectural and data-model change, not a technology change. Zero new Python packages, zero new npm packages, and zero new Docker services are required.

The recommended approach follows a strict dependency chain: first promote the existing `DriverDB` model to a working entity with auto-creation from CSV, then rewire the optimization pipeline from fleet-wide CVRP to per-driver TSP, then update the dashboard and Driver PWA to speak in "driver" terms instead of "vehicle" terms. Parallel workstreams (settings page, cache management, Google Maps route validation) can proceed independently once the driver foundation is laid. VROOM already handles TSP as a special case of VRP with one vehicle, so no solver change is needed -- only the orchestration layer changes.

The primary risks are: (1) the vehicle-to-driver rename is a semantic split, not a simple find-and-replace, with 371 "vehicle" references in the dashboard, 67 in the Driver PWA, and 129 in tests -- a naive rename would break everything; (2) driver name normalization from CDCMS free-text creates duplicate driver records over time; and (3) Alembic auto-generated migrations could silently drop data if not hand-reviewed. All three are preventable with the phased approach outlined below, which adds new columns alongside old ones rather than renaming, uses fuzzy name matching for driver lookup, and mandates hand-written migrations.

## Key Findings

### Recommended Stack

The v3.0 milestone requires zero new dependencies. Every capability is built with existing packages: SQLAlchemy 2.0 for the extended driver model and settings table, Alembic for schema migrations, httpx for Google Routes API calls (same pattern as geocoding and OSRM), VROOM for per-driver TSP (1 vehicle = TSP automatically), React 19 + DaisyUI 5 for the settings and driver management pages.

See `.planning/research/STACK.md` for full dependency analysis, pricing impact assessment, and alternatives considered.

**Core technologies (all existing):**
- **VROOM (Docker, existing):** Per-driver TSP optimization -- submit 1 vehicle + N jobs, VROOM solves TSP. No adapter code changes needed.
- **Google Routes API v2 (new API, existing httpx client):** Route validation comparing OSRM vs Google distances. Use `computeRoutes` POST endpoint, NOT the deprecated Directions API. Essentials tier at $5/1000 requests, well within free tier at 13 routes/day ($0/month incremental cost).
- **SQLAlchemy 2.0 + Alembic (existing):** Extend `DriverDB` model with `name_normalized`, `source`, `last_seen_at` columns. New `settings` key-value table. All hand-written migrations.
- **PostgreSQL + PostGIS (existing):** New `settings` table, extended driver queries, geocode cache export. Zero new services.

**Critical version note:** Use Google Routes API v2 (`computeRoutes`), NOT the legacy Directions API deprecated March 2025. Do NOT install the `googlemaps` pip package (wraps legacy API). Use raw httpx POST, matching the existing codebase pattern.

### Expected Features

See `.planning/research/FEATURES.md` for full details, dependency graph, competitor analysis, and anti-feature rationale.

**Must have (table stakes -- v3.0 is broken without these):**
- CDCMS DeliveryMan column detection and driver auto-creation from CSV
- Per-driver TSP optimization (group by driver, VROOM TSP per group)
- Vehicle-to-Driver UI terminology rename (labels only, not API field names)
- Driver management page (adapted from existing FleetManagement.tsx, 80% code reuse)
- Improved upload flow with driver summary/confirmation step before optimization
- Upload history enhancements (date filter, driver breakdown in RunHistory.tsx)
- Dashboard settings page (API key management, system info, cache overview)

**Should have (differentiators):**
- Google Maps route validation / confidence comparison (OSRM vs Google, green/amber/red badge)
- Geocode cache management dashboard (stats, single-entry purge, Google ToS compliance flags)
- Multi-format CSV support (.xlsx detection, BOM stripping, delimiter auto-detection)
- CDCMS preprocessing hardening (column name variants, address garbling fixes)

**Defer (explicitly avoid):**
- Drag-and-drop route reordering -- undermines the VROOM optimizer
- Driver assignment UI -- CDCMS is the source of truth for assignments
- Real-time route recalculation -- spotty mobile networks, short routes make this pointless
- Driver performance dashboards -- surveillance dynamics damage driver trust
- Driver shift scheduling -- single depot, single shift, zero benefit
- Geocode cache auto-purge -- would destroy valuable driver-verified entries
- Bulk cache delete -- one misclick destroys months of accumulated cache value

### Architecture Approach

The system remains a monolith with 4 Docker services. The key architectural change is in the upload-to-route pipeline: after CSV parsing, build a `driver_orders_map` from the DeliveryMan column, auto-create drivers via `get_or_create_driver()`, then call VROOM N times (once per driver) instead of once for the whole fleet. All N driver routes are stored under a single `optimization_run` to preserve fleet-wide visibility. The existing `VroomAdapter.optimize()` protocol handles TSP without modification when given 1 vehicle.

See `.planning/research/ARCHITECTURE.md` for full data flow diagrams (before/after), component interfaces, database schema changes, API endpoint inventory, and the complete dependency graph with build order.

**Major components (new or modified):**
1. **Driver Management (repository.py extension):** `get_or_create_driver()`, `get_active_drivers()`, `update_driver()` -- CRUD with case-insensitive fuzzy name matching for auto-creation from CSV
2. **Per-Driver TSP Wrapper (main.py):** ~50-line orchestration function that groups orders by driver, calls VROOM per group, combines results into a single `RouteAssignment`
3. **Google Maps Route Validator (new: core/routing/gmaps_validator.py):** Calls Google Routes API `computeRoutes`, compares distance/duration with OSRM, returns confidence level (high <15% delta, medium <30%, low >=30%)
4. **Dashboard Settings Page (new: Settings.tsx):** API key config (masked display, server-side storage, test button), geocode cache stats, system info
5. **Driver Management Page (adapted FleetManagement.tsx):** List, create, edit, deactivate drivers. Inline edit pattern reused from existing fleet management.

**Unchanged components:** VroomAdapter internals, OSRM adapter, geocoding pipeline, Order/Vehicle/Route/RouteStop models, core protocols, Driver PWA (backward-compatible -- accepts both vehicle_id and driver_name).

### Critical Pitfalls

See `.planning/research/PITFALLS.md` for all 15 pitfalls with severity ratings, code-level analysis, and prevention strategies.

1. **Vehicle-to-Driver rename is a semantic split, not find-and-replace.** 647+ references across codebase. Prevention: add new columns alongside old ones, change UI labels only, keep `vehicle_id` in API field names and URLs. Never rename the column.

2. **CVRP-to-TSP transition must preserve capacity constraints and fleet metrics.** Store all N driver routes under ONE `optimization_run`. Never create separate runs per driver (breaks `get_latest_run()`). Keep vehicle capacity in per-driver VROOM calls.

3. **CDCMS .xlsx files break auto-detection.** `_is_cdcms_format()` opens files as text, fails on binary .xlsx. Fix: check file extension first, use `pd.read_excel()` for .xlsx header inspection.

4. **Google Maps validation can cause cost spikes.** Must be user-triggered only (button click), never automatic. Cache results per route hash. Set Google Cloud billing alerts.

5. **Driver auto-creation creates ghost drivers from name variations.** Prevention: `name_normalized` column (lowercase, stripped), unique constraint, fuzzy matching on lookup. Log all auto-created drivers for review.

## Implications for Roadmap

Based on the dependency analysis across all four research files, the v3.0 milestone should be structured in 5 phases with a clear critical path.

### Phase 1: Driver DB Foundation

**Rationale:** Everything depends on the driver entity existing and being populated. The `DriverDB` model already exists in `core/database/models.py` but is unused. This phase promotes it to a working entity.
**Delivers:** Alembic migration adding `name_normalized`, `source`, `last_seen_at` to `drivers` table. New `settings` key-value table. Repository functions for driver CRUD with fuzzy name matching. API endpoints for driver management (`GET/POST/PUT/DELETE /api/drivers`). Adapted driver management dashboard page (from FleetManagement.tsx).
**Addresses:** CDCMS DeliveryMan detection, driver auto-creation, manual driver CRUD, driver management page (Features 1-3).
**Avoids:** Pitfall 1 (semantic minefield) by adding columns alongside existing ones, never renaming. Pitfall 5 (Alembic drops data) by hand-writing all migrations. Pitfall 9 (ghost drivers) by implementing `name_normalized` with unique constraint and fuzzy matching from the start. Pitfall 13 (settings persistence) by creating `settings` table in this first migration.

### Phase 2: Per-Driver TSP Optimization

**Rationale:** Depends on Phase 1 (needs resolved driver entities with vehicle assignments). This is the core functional change -- switching from fleet CVRP to per-driver TSP.
**Delivers:** `driver_orders_map` construction from CDCMS DeliveryMan column. Driver-to-vehicle assignment logic (round-robin default, manual override). Per-driver TSP wrapper calling VroomAdapter with 1 vehicle per driver. Fallback to fleet-wide CVRP for non-CDCMS uploads. Updated `save_optimization_run()` storing all driver routes under single run. Improved upload flow with driver summary/confirmation step.
**Addresses:** Per-driver TSP optimization, improved upload flow (Features 4-5).
**Avoids:** Pitfall 2 (optimizer interface breakage) by wrapping per-driver calls and combining into single RouteAssignment. Pitfall 6 (fleet metrics loss) by aggregating all driver results into one optimization_run record.

### Phase 3: Dashboard and PWA Driver Integration

**Rationale:** Depends on Phases 1+2 (needs working driver API and per-driver routes to display). This phase updates the UI layer to show driver names instead of vehicle IDs.
**Delivers:** Route cards with driver names. Driver selection step in UploadRoutes.tsx. TypeScript types for Driver, RouteValidation, GeocodeCacheStats. Route lookup accepting both vehicle_id and driver name. Driver PWA backward-compatible display updates. Service worker cache version bump.
**Addresses:** Vehicle-to-Driver UI rename (Feature 1 UI portion).
**Avoids:** Pitfall 10 (PWA route fetching breakage) by keeping `/api/routes/{vehicle_id}` endpoint path and accepting both identifiers. Pitfall 15 (cached old PWA) by bumping service worker cache version and including both identifiers in API responses.

### Phase 4: Operational Polish

**Rationale:** Independent of the critical path. Can run in parallel with Phase 3. Improves quality-of-life for office staff.
**Delivers:** Dashboard settings page (API key management with masked display, system info, cache overview). Upload history enhancements (date filter, driver breakdown, filename display). CDCMS preprocessing hardening (.xlsx detection fix, column name variants, address garbling fixes). Multi-format CSV support (BOM stripping, delimiter auto-detection). Geocode cache export/import API endpoints.
**Addresses:** Settings page, upload history, CDCMS fixes, multi-format CSV, cache export (Features 6-7, 10-11).
**Avoids:** Pitfall 3 (.xlsx detection) by fixing `_is_cdcms_format()` to handle binary files. Pitfall 7 (API key exposure) by storing keys server-side with masked display only. Pitfall 8 (cache invalidation from preprocessing changes) by building cache export/import before changing preprocessing logic. Pitfall 14 (PostGIS serialization) by exporting as lat/lng JSON.

### Phase 5: Validation and Confidence

**Rationale:** Depends on Phase 2 (needs working optimized routes to validate against Google). This is the "trust but verify" layer that adds confidence without changing routing decisions.
**Delivers:** `GoogleMapsRouteValidator` in `core/routing/gmaps_validator.py`. `GET /api/routes/{id}/validate` endpoint. Dashboard validation badge (green/amber/red) on route cards. Geocode cache management dashboard (stats, single-entry purge, Google ToS compliance flags for entries >30 days). Geocode validation radius tightening (30km to 20km).
**Addresses:** Google Maps route validation, geocode cache management (Features 8-9).
**Avoids:** Pitfall 4 (cost explosion) by making validation user-triggered only with result caching and billing alerts. Pitfall 12 (25-waypoint limit) by reusing existing `split_route_into_segments()` logic from qr_helpers.py.

### Phase Ordering Rationale

- **Phase 1 before everything** because the driver entity is the foundation. Auto-creation from CSV and name normalization must be rock-solid before optimization changes.
- **Phase 2 after Phase 1** because per-driver TSP requires resolved driver entities with vehicle assignments to pass to VROOM.
- **Phase 3 after Phase 2** because the dashboard cannot show per-driver routes until they exist. But Phase 3 is UI-only, so development could overlap with late Phase 2.
- **Phase 4 is parallel-safe** because settings, upload history, CSV hardening, and cache management have no dependency on the driver model critical path. Build concurrently with Phases 2-3.
- **Phase 5 last** because validation is a confidence layer on top of working routes. It adds value only after the core pipeline is flowing correctly.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Per-Driver TSP):** The VROOM single-vehicle behavior is verified, but the orchestration of N VROOM calls and result merging needs careful design around error handling (what if one driver's optimization fails?), the `optimization_run` record structure (single run with multiple routes), and the upload flow UX (driver summary confirmation step).
- **Phase 5 (Google Maps Validation):** The Routes API v2 endpoint, pricing, and field masking are documented, but threshold calibration (what delta % means "low confidence"?) needs real-world data from production routes. Also: routes with >25 stops require segment splitting and distance reassembly.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Driver DB Foundation):** Well-established CRUD pattern. The repository already has the exact pattern for vehicles. Copy and adapt. Migration is straightforward column addition.
- **Phase 3 (Dashboard Integration):** Standard React component work with existing DaisyUI patterns. FleetManagement.tsx provides 80% of the driver management code.
- **Phase 4 (Operational Polish):** Settings pages and upload history are thoroughly documented industry patterns (Stripe, Datadog). No novel integration.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new dependencies. Every technology is already in the codebase and proven. Google Routes API v2 pricing verified against official docs. Incremental cost: $0/month. |
| Features | MEDIUM-HIGH | Table stakes features are clear and well-bounded. Route validation threshold calibration (15% vs 30% delta) needs real-world data. Driver name normalization edge cases may surface in production. |
| Architecture | HIGH | All integration points traced through source code with line-number precision. VroomAdapter, DriverDB, repository patterns all verified. Per-driver TSP is a ~50-line wrapper. |
| Pitfalls | HIGH | 15 pitfalls identified with specific code references (line numbers, column counts, reference counts across files). Migration and rename pitfalls verified against existing schema and 6 Alembic migrations. |

**Overall confidence:** HIGH

### Gaps to Address

- **Driver name normalization edge cases:** CDCMS free-text names have unknown variation patterns. The `name_normalized` approach handles case and whitespace, but abbreviations ("K" vs "KUMAR") and transliteration differences may need a fuzzy matching layer or alias tracking. Monitor after first 2-3 weeks of production uploads.

- **Route validation threshold calibration:** The 15%/30% delta thresholds for high/medium/low confidence are educated guesses. Need to run validation against 50+ real production routes to establish appropriate thresholds for Kerala road conditions (OSRM uses OSM data which may diverge from Google's proprietary data).

- **Vehicle-to-driver assignment for new drivers:** When a new driver appears in CSV with no vehicle assignment, the round-robin default may assign vehicles suboptimally. May need a "default vehicle" concept or manual assignment step in the upload flow.

- **Google ToS compliance for geocode cache:** Google's 30-day caching restriction applies to `source='google'` entries. The cache management UI should flag stale Google entries, but the enforcement mechanism (auto-purge vs manual review) is not yet decided. Research recommends manual review to protect valuable data.

- **Per-driver TSP error handling:** If VROOM fails for one driver's optimization (e.g., all stops are ungeocoded), the behavior for the remaining drivers is undefined. Need a clear strategy: skip failed driver and proceed, or fail the entire batch.

## Sources

### Primary (HIGH confidence)
- [Google Maps Routes API Usage and Billing](https://developers.google.com/maps/documentation/routes/usage-and-billing) -- pricing tiers, free tier limits, SKU breakdown
- [Google Maps Routes API Compute Routes](https://developers.google.com/maps/documentation/routes/compute_route_directions) -- POST endpoint, request/response format, field masking
- [Google Maps Directions API Migration Guide](https://developers.google.com/maps/documentation/routes/migrate-routes) -- legacy API deprecation details
- [VROOM Project GitHub](https://github.com/VROOM-Project/vroom) -- TSP as VRP with 1 vehicle, confirmed in docs
- [VROOM API Documentation](https://github.com/VROOM-Project/vroom/blob/master/docs/API.md) -- request format, vehicles/jobs arrays, step-level output
- [Alembic Autogenerate Documentation](https://alembic.sqlalchemy.org/en/latest/autogenerate.html) -- column rename limitations, manual review requirement
- [Google Maps Geocoding Policies](https://developers.google.com/maps/documentation/geocoding/policies) -- 30-day cache restriction, Place ID exemption
- [Google Maps Platform Security Best Practices](https://developers.google.com/maps/api-security-best-practices) -- server-side key storage
- Codebase analysis: `core/database/models.py`, `core/optimizer/vroom_adapter.py`, `core/database/repository.py`, `apps/kerala_delivery/api/main.py`, `core/data_import/cdcms_preprocessor.py`, `apps/kerala_delivery/dashboard/src/` (16 files, 371 vehicle references)

### Secondary (MEDIUM confidence)
- [Nextmv: TSP vs CVRP](https://www.nextmv.io/blog/tsp-pdtsp-cvrp-cvrptw-oh-my-the-alphabet-soup-of-route-optimization) -- when to use TSP vs CVRP
- [LogisticsOS: Comparing Matrix Routing Services](https://www.logisticsos.com/blog/distance-matrix) -- OSRM vs Google accuracy analysis
- [Google Maps API pricing restructure March 2025](https://masterconcept.ai/news/google-maps-api-changes-2025-migration-guide-for-directions-api-distance-matrix-api/) -- new billing tiers
- [Coaxsoft: Driver Management Software Guide](https://coaxsoft.com/blog/guide-to-driver-management-software) -- industry feature expectations
- [OSRM vs Google comparison tool](https://github.com/yklyahin/osrm-google-comparison) -- distance comparison methodology

### Tertiary (LOW confidence)
- [Detrack](https://www.detrack.com/), [Route4Me](https://www.route4me.com/), [Onfleet](https://onfleet.com/) -- competitor feature references (marketing material)
- [Stripe API Key Management](https://docs.stripe.com/keys) -- settings page UX pattern reference

---
*Research completed: 2026-03-12*
*Ready for roadmap: yes*
