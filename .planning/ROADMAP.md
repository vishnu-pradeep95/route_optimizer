# Roadmap: Kerala LPG Delivery Route Optimizer

## Overview

This is a hardening and polish milestone on a working logistics system. The route optimization pipeline (VROOM/OSRM, FastAPI, React dashboard, driver PWA) already works — the goal is to make it production-grade: fix the critical geocoding failure bug that silently drops delivery orders, harden security, overhaul the UI to a professional logistics SaaS aesthetic, and clean up the codebase so the next person (human or AI) can work in it without pain. Phases follow a strict dependency chain: foundation first, security next, data integrity before UI, driver PWA after dashboard, cleanup last.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Foundation** - Install Tailwind 4 + DaisyUI 5 collision-safe; establish test baseline (Vatakara coordinates, asyncio config)
- [ ] **Phase 2: Security Hardening** - HTTP security headers, CORS hardening, API doc gating, input validation, dependency replacement
- [ ] **Phase 3: Data Integrity** - Fix silent geocoding drops; surface row-level failures with structured import summary
- [ ] **Phase 4: Dashboard UI Migration** - Migrate all dashboard pages to Tailwind/DaisyUI; add empty states and toast notifications
- [ ] **Phase 5: Driver PWA Update** - Pre-compiled Tailwind CSS; professional mobile layout; updated service worker cache
- [ ] **Phase 6: Quality and Documentation** - Property-based tests, factory fixtures, external API mocks, coverage gate, dead code removal, main.py refactor, README + docs

## Phase Details

### Phase 1: Foundation
**Goal**: Design system and test infrastructure are verified and stable before any component work begins
**Depends on**: Nothing (first phase)
**Requirements**: DASH-01, DASH-02, PWA-01, TEST-01, TEST-06
**Success Criteria** (what must be TRUE):
  1. Tailwind 4 + DaisyUI 5 are installed in the Vite pipeline with `prefix(tw)` — existing dashboard CSS variables (`--color-accent`, `--color-surface`) are verified unchanged in browser DevTools after install
  2. A utility class from Tailwind and a component from DaisyUI render correctly on the dashboard without breaking any existing styles
  3. The Tailwind standalone CLI binary is present and can generate a static `tailwind.css` for the PWA from the command line
  4. All E2E tests that previously referenced Kochi coordinates (9.97°N) now use Vatakara (11.52°N) and the full test suite still passes
  5. `asyncio_mode=auto` is configured in pytest.ini and async tests run without warnings
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md — Install Tailwind 4 + DaisyUI 5 in Vite pipeline with collision-safe prefix
- [ ] 01-02-PLAN.md — Define logistics SaaS design tokens and verify collision-free in DevTools
- [ ] 01-03-PLAN.md — Set up Tailwind standalone CLI for PWA; fix Vatakara coordinates in tests; configure asyncio_mode

### Phase 2: Security Hardening
**Goal**: All API endpoints emit correct security headers, CORS is locked to production origins, and deprecated auth libraries are replaced
**Depends on**: Phase 1
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06
**Success Criteria** (what must be TRUE):
  1. A browser security header scan (e.g., securityheaders.com) shows A-grade headers: CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and Permissions-Policy present on all responses
  2. A request from an unlisted origin is rejected by CORS — only origins in the whitelist env var receive `Access-Control-Allow-Origin`
  3. Visiting `/docs` or `/redoc` in an environment with `ENV=production` returns 404 — in development it still works
  4. Uploading a file with wrong MIME type or size over the limit is rejected with a clear error message before any processing occurs
  5. The full 351-test suite passes with no 429 cross-test bleed after rate limiter state is isolated between tests
**Plans**: TBD

Plans:
- [ ] 02-01: Add Secweb security headers middleware; harden CORS to env-var whitelist; gate API docs
- [ ] 02-02: Audit file upload input validation; replace python-jose with PyJWT and passlib with pwdlib; isolate rate limiter in tests

### Phase 3: Data Integrity
**Goal**: Every geocoding failure is visible to the office user with a per-row reason — no order silently disappears from the map
**Depends on**: Phase 2
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05
**Success Criteria** (what must be TRUE):
  1. After uploading a CSV where some rows have bad addresses, the upload response includes a count of succeeded, failed, and unassigned orders — not just "No valid orders"
  2. A user can see which specific rows failed geocoding and why (e.g., "Row 12: ADDRESS_NOT_FOUND — 'Near old temple, Vatakara'") in the UI
  3. Uploading a CSV where 3 of 10 rows fail geocoding still produces an optimized route for the 7 successful orders
  4. The system uses only Vatakara depot coordinates (11.52°N) throughout the pipeline — no Kozhikode coordinates appear in geocoded results, route origins, or test fixtures
  5. CSV rows with missing required fields or malformed data show a validation error per row before geocoding is attempted
**Plans**: TBD

Plans:
- [ ] 03-01: Backend — structured geocoding failure model; `batch()` accumulates failures; audit depot coordinate propagation
- [ ] 03-02: Backend — CSV row-level pre-validation before geocoding; partial-batch optimization support
- [ ] 03-03: Frontend — import summary screen with counts; expandable failure list; toast warning for partial geocoding

### Phase 4: Dashboard UI Migration
**Goal**: Every dashboard page looks like a professional logistics SaaS product (Onfleet/Routific style) with consistent Tailwind/DaisyUI styling
**Depends on**: Phase 3
**Requirements**: DASH-03, DASH-04, DASH-05, DASH-06, DASH-07, DASH-08
**Success Criteria** (what must be TRUE):
  1. The Upload/Routes page uses Tailwind/DaisyUI components — drag-and-drop upload area, progress indicator, and results table all styled consistently with the design system
  2. The Live Map page has a clean map container with a styled vehicle sidebar showing driver info and status indicators
  3. The Fleet Management page shows vehicle cards with capacity indicators and driver info pulled from config or database (not hardcoded placeholder names)
  4. The Run History page has a sortable run table with expandable route details — no unstyled or legacy CSS visible
  5. Every page has a designed empty state (not a blank screen) for when there are no routes, no vehicles, or no history
  6. User actions (upload, route, error) trigger non-blocking toast notifications that auto-dismiss
**Plans**: TBD

Plans:
- [ ] 04-01: Migrate Upload/Routes page to Tailwind/DaisyUI; wire import summary and failure list from Phase 3
- [ ] 04-02: Migrate Live Map page and Fleet Management page to Tailwind/DaisyUI
- [ ] 04-03: Migrate Run History page to Tailwind/DaisyUI; implement toast notification system; add empty states for all pages

### Phase 5: Driver PWA Update
**Goal**: The driver PWA looks professional on a phone screen, works offline, and is styled with pre-compiled Tailwind CSS (no CDN dependency)
**Depends on**: Phase 4
**Requirements**: PWA-02, PWA-03, PWA-04
**Success Criteria** (what must be TRUE):
  1. The driver PWA loads and displays the route list and map correctly with no CDN requests — all CSS is served from the pre-compiled static file cached by the service worker
  2. The mobile layout shows a clean stop list, delivery cards, and Leaflet map that are readable outdoors (adequate contrast, large touch targets)
  3. Uninstalling and reinstalling the PWA picks up the new CSS — the service worker cache version has been bumped and old assets are evicted
  4. Delivery status updates trigger a toast/alert on mobile that confirms the action without blocking the screen
**Plans**: TBD

Plans:
- [ ] 05-01: Pre-compile Tailwind CSS via standalone CLI; commit static artifact; update service worker cache version
- [ ] 05-02: Redesign PWA mobile layout with DaisyUI utility classes; add mobile toast/alert system

### Phase 6: Quality and Documentation
**Goal**: The codebase is clean, tests cover edge cases with proper isolation, and a new developer can set up and understand the project from the README alone
**Depends on**: Phase 5
**Requirements**: QUAL-01, QUAL-02, QUAL-03, QUAL-04, TEST-02, TEST-03, TEST-04, TEST-05, DOCS-01, DOCS-02, DOCS-03, DOCS-04
**Success Criteria** (what must be TRUE):
  1. `ruff` and `vulture` report zero unused imports and zero dead code — `main.py` is split into focused modules under 500 lines each
  2. Property-based tests with `hypothesis` cover CSV parsing edge cases and geocoding coordinate boundary conditions
  3. External API calls (Google Geocoding, VROOM, OSRM) are mocked with `respx` in tests — no real network calls during `pytest`
  4. `pytest --cov` reports a baseline coverage percentage that is enforced as a CI gate — a PR that drops coverage fails the check
  5. `docker compose up` brings up the full stack (API, OSRM, VROOM, PostgreSQL) with one command, documented in the README with screenshots
**Plans**: TBD

Plans:
- [ ] 06-01: Add hypothesis property-based tests; add factory_boy Order/Vehicle/Route factories; add respx mocks for external APIs
- [ ] 06-02: Configure pytest-cov and establish coverage gate; fix asyncio singleton thread-safety
- [ ] 06-03: Dead code removal with ruff + vulture; refactor main.py into focused modules; remove hardcoded placeholder driver names
- [ ] 06-04: Rewrite README with one-command Docker setup and screenshots; write env var guide, troubleshooting section, and developer guide

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/3 | Not started | - |
| 2. Security Hardening | 0/2 | Not started | - |
| 3. Data Integrity | 0/3 | Not started | - |
| 4. Dashboard UI Migration | 0/3 | Not started | - |
| 5. Driver PWA Update | 0/2 | Not started | - |
| 6. Quality and Documentation | 0/4 | Not started | - |
