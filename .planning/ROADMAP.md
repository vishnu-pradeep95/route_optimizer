# Roadmap: Kerala LPG Delivery Route Optimizer

## Milestones

- [x] **v1.0 Infrastructure** - Phases 1-3 (shipped 2026-03-01)
- [ ] **v1.1 Polish & Reliability** - Phases 4-7 (in progress)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

<details>
<summary>v1.0 Infrastructure (Phases 1-3) - SHIPPED 2026-03-01</summary>

- [x] **Phase 1: Foundation** - Install Tailwind 4 + DaisyUI 5 collision-safe; establish test baseline (Vatakara coordinates, asyncio config)
- [x] **Phase 2: Security Hardening** - HTTP security headers, CORS hardening, API doc gating, input validation, dependency replacement
- [x] **Phase 3: Data Integrity** - Fix silent geocoding drops; surface row-level failures with structured import summary

</details>

### v1.1 Polish & Reliability

- [x] **Phase 4: Geocoding Cache Normalization** - Unify address normalization across all cache layers; deprecate file-based cache (completed 2026-03-01)
- [x] **Phase 5: Geocoding Enhancements** - Duplicate location detection and cost tracking in the optimization pipeline (completed 2026-03-02)
- [ ] **Phase 6: Dashboard UI Overhaul** - Migrate all 4 dashboard pages to consistent DaisyUI component vocabulary with professional logistics SaaS aesthetic
- [ ] **Phase 7: Driver PWA Refresh** - Next-stop hero card, delivery progress, outdoor readability, and offline reliability

## Phase Details

<details>
<summary>v1.0 Infrastructure (Phases 1-3) - SHIPPED 2026-03-01</summary>

### Phase 1: Foundation
**Goal**: Design system and test infrastructure are verified and stable before any component work begins
**Depends on**: Nothing (first phase)
**Requirements**: DASH-01, DASH-02, PWA-01, TEST-01, TEST-06
**Success Criteria** (what must be TRUE):
  1. Tailwind 4 + DaisyUI 5 are installed in the Vite pipeline with `prefix(tw)` -- existing dashboard CSS variables preserved
  2. A utility class from Tailwind and a component from DaisyUI render correctly without breaking existing styles
  3. The Tailwind standalone CLI binary can generate a static `tailwind.css` for the PWA
  4. All E2E tests use Vatakara (11.52N) coordinates and the full test suite passes
  5. `asyncio_mode=auto` is configured in pytest.ini and async tests run without warnings
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md -- Install Tailwind 4 + DaisyUI 5 in Vite pipeline with collision-safe prefix
- [x] 01-02-PLAN.md -- Define logistics SaaS design tokens and verify collision-free in DevTools
- [x] 01-03-PLAN.md -- Set up Tailwind standalone CLI for PWA; fix Vatakara coordinates in tests; configure asyncio_mode

### Phase 2: Security Hardening
**Goal**: All API endpoints emit correct security headers, CORS is locked to production origins, and deprecated auth libraries are replaced
**Depends on**: Phase 1
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06
**Success Criteria** (what must be TRUE):
  1. Browser security header scan shows A-grade headers on all responses
  2. Requests from unlisted origins are rejected by CORS
  3. `/docs` and `/redoc` return 404 in production environment
  4. Files with wrong MIME type or oversized are rejected with clear error before processing
  5. Full test suite passes with no 429 cross-test bleed
**Plans**: 2 plans

Plans:
- [x] 02-01-PLAN.md -- Add security headers middleware, harden CORS, fix /redoc gating
- [x] 02-02-PLAN.md -- Enhance file upload validation, isolate rate limiter state in tests

### Phase 3: Data Integrity
**Goal**: Every geocoding failure is visible to the office user with a per-row reason -- no order silently disappears from the map
**Depends on**: Phase 2
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05
**Success Criteria** (what must be TRUE):
  1. Upload response includes counts of succeeded, failed, and unassigned orders
  2. User can see which specific rows failed geocoding and why
  3. Partial geocoding failures still produce optimized routes for successful orders
  4. System uses only Vatakara depot coordinates throughout the pipeline
  5. CSV rows with missing required fields show validation errors per row before geocoding
**Plans**: 3 plans

Plans:
- [x] 03-01-PLAN.md -- Add ImportResult model and row-level validation; audit depot coordinates
- [x] 03-02-PLAN.md -- Enrich OptimizationSummary with failure data; collect geocoding errors
- [x] 03-03-PLAN.md -- Import summary UI with counts, expandable failure table, three visual states

</details>

### Phase 4: Geocoding Cache Normalization
**Goal**: All geocoding lookups use a single normalization function so the same address always resolves to the same cached coordinates -- no duplicate map pins from cache key mismatch
**Depends on**: Phase 3 (v1.0 complete)
**Requirements**: GEO-01, GEO-02
**Success Criteria** (what must be TRUE):
  1. Uploading the same address with different whitespace, casing, or Unicode forms always returns the same cached GPS coordinates (no duplicate map pins)
  2. All geocoding cache reads and writes go through the PostgreSQL/PostGIS database -- no file-based JSON cache is consulted or written to
  3. Existing cached addresses in the database are re-normalized via Alembic migration so historical data is consistent with new lookups
**Plans**: TBD

### Phase 5: Geocoding Enhancements
**Goal**: Office staff can see which addresses cost money (API calls vs cache hits) and get warned when multiple orders resolve to suspiciously close GPS coordinates
**Depends on**: Phase 4
**Requirements**: GEO-03, GEO-04
**Success Criteria** (what must be TRUE):
  1. After uploading a CSV, the response shows how many addresses were cache hits (free) versus Google API calls, with an estimated cost figure
  2. When two or more orders in an upload resolve to GPS coordinates within 15m of each other, a visible warning identifies the affected orders
  3. Duplicate location warnings use confidence-weighted thresholds (tighter for ROOFTOP results, wider for GEOMETRIC_CENTER) to minimize false positives in dense Vatakara streets
**Plans**: 2 plans

Plans:
- [x] 05-01-PLAN.md — Backend: duplicate detector module, config thresholds, cost stats + duplicate wiring into upload endpoint
- [x] 05-02-PLAN.md — Frontend: TypeScript types, CostSummary stats display, DuplicateWarnings UI components

### Phase 6: Dashboard UI Overhaul
**Goal**: Every dashboard page looks and behaves like a professional logistics SaaS product -- consistent component vocabulary, proper loading states, and responsive layout
**Depends on**: Phase 5
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06, DASH-07
**Success Criteria** (what must be TRUE):
  1. All 4 dashboard pages (Upload, Live Map, Run History, Fleet Management) use DaisyUI components consistently -- no mixed raw CSS and DaisyUI on the same page
  2. Sidebar navigation uses SVG icons (lucide-react) instead of emoji, collapses to icon-only below 1280px, and uses a DaisyUI drawer on mobile
  3. Every page displays a skeleton loading state while data loads and a meaningful empty state when no data exists
  4. Route cards show color-coded status badges (green/amber/red) and numeric values use tabular-number font variant for column alignment
  5. QR sheet prints cleanly with large QR codes, vehicle name, and driver name via @media print styles
**Plans**: TBD

### Phase 7: Driver PWA Refresh
**Goal**: Drivers see their next delivery prominently, track progress visually, and can work reliably in outdoor conditions with spotty network
**Depends on**: Phase 4 (shares no code with Phase 6; only needs stable geocoding from Phase 4)
**Requirements**: PWA-01, PWA-02, PWA-03, PWA-04, PWA-05, PWA-06
**Success Criteria** (what must be TRUE):
  1. The next undelivered stop is displayed as a prominent hero card at the top of the stop list with large address text, distance, and a Navigate button -- no scrolling required
  2. Header shows delivery progress as "X of Y delivered" with a visual progress bar that updates as stops are marked complete
  3. Driver can tap a visible Refresh button to reload route data, and a "Last updated" timestamp confirms when data was last fetched
  4. All primary action buttons (Delivered, Failed, Navigate, Call Office) are at least 60px touch targets usable with gloves or in motion
  5. All text and background color combinations meet WCAG AAA contrast ratio (7:1 for body text, 4.5:1 for large text) for outdoor readability in direct sunlight
  6. Route data persists offline -- loading the app, viewing stops, and marking deliveries all work without network connectivity
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 4 -> 5 -> 6 -> 7

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.0 | 3/3 | Complete | 2026-03-01 |
| 2. Security Hardening | v1.0 | 2/2 | Complete | 2026-03-01 |
| 3. Data Integrity | v1.0 | 3/3 | Complete | 2026-03-01 |
| 4. Geocoding Cache Normalization | v1.1 | Complete    | 2026-03-01 | - |
| 5. Geocoding Enhancements | v1.1 | 2/2 | Complete | 2026-03-02 |
| 6. Dashboard UI Overhaul | v1.1 | 0/? | Not started | - |
| 7. Driver PWA Refresh | v1.1 | 0/? | Not started | - |
