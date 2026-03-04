# Roadmap: Kerala LPG Delivery Route Optimizer

## Milestones

- ✅ **v1.0 Infrastructure** — Phases 1-3 (shipped 2026-03-01)
- ✅ **v1.1 Polish & Reliability** — Phases 4-7 (shipped 2026-03-03)
- 🚧 **v1.2 Tech Debt & Cleanup** — Phases 8-12 (in progress)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

<details>
<summary>✅ v1.0 Infrastructure (Phases 1-3) — SHIPPED 2026-03-01</summary>

- [x] Phase 1: Foundation (3/3 plans) — completed 2026-03-01
- [x] Phase 2: Security Hardening (2/2 plans) — completed 2026-03-01
- [x] Phase 3: Data Integrity (3/3 plans) — completed 2026-03-01

</details>

<details>
<summary>✅ v1.1 Polish & Reliability (Phases 4-7) — SHIPPED 2026-03-03</summary>

- [x] Phase 4: Geocoding Cache Normalization (2/2 plans) — completed 2026-03-01
- [x] Phase 5: Geocoding Enhancements (2/2 plans) — completed 2026-03-02
- [x] Phase 6: Dashboard UI Overhaul (9/9 plans) — completed 2026-03-02
- [x] Phase 7: Driver PWA Refresh (3/3 plans) — completed 2026-03-03

</details>

### 🚧 v1.2 Tech Debt & Cleanup (In Progress)

**Milestone Goal:** Eliminate all known tech debt, dead code, and consistency issues across the API, dashboard, and driver PWA. No new features -- strictly cleanup and fixes.

- [ ] **Phase 8: API Dead Code & Hygiene** - Remove dead functions, unused imports, fix import ordering, correct stale docstrings, extract PostGIS helper
- [ ] **Phase 9: Config Consolidation** - Single API config endpoint serves depot coords, safety multiplier, and office phone number; QR sheet magic number aligned
- [x] **Phase 10: Driver PWA Hardening** - Safety fixes (GPS leak, alert replacement), consume config endpoint for phone number, proper PWA icons, SW cache gap, debug logging (completed 2026-03-04)
- [ ] **Phase 11: Dashboard Cleanup** - Dead CSS removal, design token consistency, TypeScript type gaps, N+1 fetch elimination
- [ ] **Phase 12: Data Wiring & Validation** - Wire save_driver_verified into status endpoint, validate duplicate detection thresholds against production data

## Phase Details

### Phase 8: API Dead Code & Hygiene
**Goal**: API codebase has zero dead code, clean imports, correct documentation, and type-safe PostGIS operations
**Depends on**: Nothing (independent backend cleanup)
**Requirements**: API-01, API-02, API-03, API-04, API-05, API-06
**Success Criteria** (what must be TRUE):
  1. `_build_fleet()` function no longer exists in the codebase and no remaining references to it
  2. Running `ruff check` (or equivalent linter) on `main.py` reports zero unused imports
  3. All imports in `main.py` are consolidated at file top -- no mid-file imports
  4. `config.py` has no `OSRM_URL` variable and existing OSRM references use correct config path
  5. PostGIS geometry operations use a typed helper function with zero `type: ignore` suppressions for geometry columns
**Plans**: 2 plans (Wave 1 -> Wave 2, sequential due to shared main.py)

Plans:
- [ ] 08-01: Dead code removal, import consolidation, OSRM_URL cleanup, docstring corrections (API-01, API-02, API-03, API-04, API-05)
- [ ] 08-02: PostGIS geometry helper extraction (API-06)

### Phase 9: Config Consolidation
**Goal**: Frontend applications read depot coordinates, safety multiplier, and office phone number from a single API config endpoint instead of hardcoded values
**Depends on**: Nothing (creates the endpoint others consume)
**Requirements**: CFG-01, CFG-02, CFG-03
**Success Criteria** (what must be TRUE):
  1. `GET /api/config` (or similar) returns JSON containing depot lat/lng, safety multiplier, and office phone number sourced from `config.py`
  2. QR sheet duration buffer is computed from the safety multiplier constant, not a separate magic number
  3. Changing depot coordinates or safety multiplier in `config.py` propagates to all consumers without touching frontend code
**Plans**: TBD

Plans:
- [ ] 09-01: TBD

### Phase 10: Driver PWA Hardening
**Goal**: Driver PWA has no safety bugs, proper installability assets, complete offline support, and clean production logging
**Depends on**: Phase 9 (config endpoint for phone number and depot coords)
**Requirements**: PWA-01, PWA-02, PWA-03, PWA-04, PWA-05, PWA-06
**Success Criteria** (what must be TRUE):
  1. Call Office FAB dials the real office phone number fetched from the API config endpoint -- no hardcoded placeholder visible in source
  2. Navigating away from route view or resetting route clears the GPS watch (no `watchPosition` leak in DevTools Sensors panel)
  3. Offline error notification uses a styled `<dialog>` element -- browser `alert()` is not called anywhere in the PWA source
  4. PWA "Add to Home Screen" prompt shows a proper PNG icon (192px and 512px), not a data-URI SVG emoji
  5. After installing the PWA and going offline, `tailwind.css` loads from service worker cache (no unstyled flash)
**Plans**: 2 plans (Wave 1 -> Wave 2, sequential due to shared index.html)

Plans:
- [ ] 10-01-PLAN.md — Safety fixes: config endpoint phone fetch, GPS watch leak fix, offline dialog replacement (PWA-01, PWA-02, PWA-03)
- [ ] 10-02-PLAN.md — PWA quality: PNG icons, SW tailwind.css cache, debug logging gate (PWA-04, PWA-05, PWA-06)

### Phase 11: Dashboard Cleanup
**Goal**: Dashboard CSS is minimal and token-driven, TypeScript types are complete and safe, and map rendering uses efficient batched data loading
**Depends on**: Nothing (independent frontend cleanup)
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05
**Success Criteria** (what must be TRUE):
  1. `index.css` contains no dead CSS variable aliases -- every declared `--variable` is referenced in at least one rule or component
  2. `.text-muted-30` class uses a design token (CSS variable) instead of a hardcoded hex color value
  3. `RouteDetail` TypeScript interface includes `total_weight_kg` and `total_items` fields, and components accessing these fields have no `as any` or `as unknown` casts
  4. `RunHistory.tsx` status handling uses proper TypeScript type narrowing (discriminated union, type guard, or exhaustive switch) with no unsafe casts
  5. LiveMap page makes one batch API call for all routes instead of N sequential calls -- network tab shows single request for route data
**Plans**: 2 plans (Wave 1 -> Wave 2, Plan 02 depends on Plan 01 for RouteDetail type)

Plans:
- [ ] 11-01-PLAN.md — CSS token cleanup, RouteDetail type fix, RunHistory cast removal (DASH-01, DASH-02, DASH-03, DASH-04)
- [ ] 11-02-PLAN.md — Batch routes endpoint and LiveMap N+1 elimination (DASH-05)

### Phase 12: Data Wiring & Validation
**Goal**: Driver-verified delivery data is persisted to the database, and duplicate detection thresholds are validated against actual production geocoding data
**Depends on**: Nothing (independent data-layer work)
**Requirements**: API-07, DATA-01
**Success Criteria** (what must be TRUE):
  1. When a driver marks a stop as delivered or failed via the PWA, `save_driver_verified()` is called and the verification record is persisted in the database
  2. Duplicate detection distance thresholds (10m/25m/100m) are validated against actual `geocode_cache` table `location_type` distribution, with documented evidence of appropriate threshold selection
**Plans**: TBD

Plans:
- [ ] 12-01: TBD

## Progress

**Execution Order:**
Phases 8, 9, 11, 12 are independent. Phase 10 depends on Phase 9.
Recommended order: 8 -> 9 -> 10 -> 11 -> 12

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.0 | 3/3 | Complete | 2026-03-01 |
| 2. Security Hardening | v1.0 | 2/2 | Complete | 2026-03-01 |
| 3. Data Integrity | v1.0 | 3/3 | Complete | 2026-03-01 |
| 4. Geocoding Cache Normalization | v1.1 | 2/2 | Complete | 2026-03-01 |
| 5. Geocoding Enhancements | v1.1 | 2/2 | Complete | 2026-03-02 |
| 6. Dashboard UI Overhaul | v1.1 | 9/9 | Complete | 2026-03-02 |
| 7. Driver PWA Refresh | v1.1 | 3/3 | Complete | 2026-03-03 |
| 8. API Dead Code & Hygiene | v1.2 | 0/? | Not started | - |
| 9. Config Consolidation | v1.2 | 0/? | Not started | - |
| 10. Driver PWA Hardening | 2/2 | Complete    | 2026-03-04 | - |
| 11. Dashboard Cleanup | v1.2 | 0/2 | Planned | - |
| 12. Data Wiring & Validation | v1.2 | 0/? | Not started | - |

---
*Full phase details for v1.0 and v1.1 archived in `.planning/milestones/`*
