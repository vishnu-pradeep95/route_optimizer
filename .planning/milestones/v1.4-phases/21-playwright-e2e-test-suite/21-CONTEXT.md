# Phase 21: Playwright E2E Test Suite - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Automated Playwright tests covering all critical user paths against the running Docker stack at localhost:8000: API endpoint verification, Driver PWA upload-to-delivery flow, Dashboard route display and QR generation, and license validation. All 420+ existing pytest unit tests must continue to pass. No visual regression testing, offline PWA testing, or performance budgets (deferred to future requirements).

</domain>

<decisions>
## Implementation Decisions

### Test data strategy
- Google Maps API key provided and working — tests use real geocoding against real Vatakara addresses
- API key passed via environment variable (never hardcoded in test files or config)
- Tests must detect and clearly report missing/invalid API key at startup — not cryptic failures
- Claude's discretion on additional handling (graceful skip of geocoding-dependent tests vs fail fast)

### Assertion depth
- DOM presence + key text content for visual features (headings, button labels, status messages, data values)
- UI state change AND separate API verification for action flows (mark done/fail) — verify both UI update and DB persistence
- Full JSON schema validation for API endpoint tests — verify status codes and complete response structure
- Full response validation for license tests — verify 503 status, error message text, and additional fields (expiry, grace period)

### Test isolation
- Shared state per spec file — upload CSV once in beforeAll, all tests in the file run against same data
- Sequential story within spec files — tests run in order, each building on the previous state (upload → view → mark done → mark fail → all-done)
- fullyParallel: false within spec files
- Claude's discretion on cross-file parallelism and DB cleanup strategy (globalSetup truncation vs assume fresh stack)

### Test organization
- One spec file per feature area, mapping to requirements:
  - `api.spec.ts` — TEST-01: all API endpoints with full schema validation
  - `driver-pwa.spec.ts` — TEST-02: upload → vehicle select → route → done/fail → all-done
  - `dashboard.spec.ts` — TEST-03: route cards, QR sheet, map
  - `license.spec.ts` — TEST-04: expired/missing/invalid key → 503
- Directory: `e2e/` at project root (alongside package.json and playwright.config.ts)
- Shared test CSV in `e2e/fixtures/test-orders.csv` with real Vatakara addresses matching CDCMS export format
- Shared utilities in `e2e/helpers/setup.ts` (upload, cleanup, common assertions)

### Claude's Discretion
- Cross-file parallelism configuration
- DB cleanup strategy (globalSetup vs fresh stack assumption)
- Timeout values and retry configuration
- Viewport settings per spec file (mobile for driver PWA, desktop for dashboard)
- Failure artifact capture (screenshots, HTML reports)
- Whether VROOM/OSRM are required for all tests or only route-dependent ones
- Graceful handling when API key is missing (skip vs fail)

</decisions>

<specifics>
## Specific Ideas

- Test CSV should use real Vatakara region addresses matching CDCMS export format — validates the actual production geocoding pipeline
- Sequential story pattern for driver PWA tests mirrors a real user session: upload → view → deliver → complete
- Success criteria requires `npx playwright test` from project root with zero manual setup beyond `docker compose up`

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `@playwright/test` already in devDependencies (package.json) — just needs config and test files
- `data/sample_cdcms_export.csv` and `data/sample_orders.csv` — reference for test CSV format
- 420+ pytest tests in `tests/` — established patterns for descriptive names, fixtures, docstrings

### Established Patterns
- Driver PWA: vanilla JS served at `/driver/` from API (StaticFiles mount)
- Dashboard: React/Vite build served at `/dashboard/` from `/srv/dashboard` Docker volume
- API: FastAPI at localhost:8000 with `/api/` prefix for all endpoints
- License validation: returns HTTP 503 for expired/missing/invalid keys
- Python tests use pytest with class-based grouping, fixtures in conftest.py

### Integration Points
- `playwright.config.ts` at project root — new file
- `e2e/` directory at project root — new directory
- `package.json` — may need test script update
- Docker stack must be running at localhost:8000 (API, OSRM, VROOM, PostgreSQL)
- Dashboard requires dashboard-build container to populate /srv/dashboard volume

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 21-playwright-e2e-test-suite*
*Context gathered: 2026-03-08*
