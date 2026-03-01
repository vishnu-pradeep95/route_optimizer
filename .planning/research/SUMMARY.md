# Project Research Summary

**Project:** Kerala LPG Delivery Route Optimizer — UI/UX Polish, Security Hardening, Test Improvement Milestone
**Domain:** Logistics SaaS — Single-operator delivery route optimization dashboard + offline-capable driver PWA
**Researched:** 2026-03-01
**Confidence:** HIGH (stack versions verified on PyPI/npm; architecture grounded in codebase inspection; pitfalls confirmed against official docs)

## Executive Summary

This is a hardening and polish milestone on a working logistics system, not a greenfield build. The core route optimization stack (FastAPI 0.129, React 19 + Vite 7, PostgreSQL/PostGIS, OSRM, VROOM) is already in production and must not change. The milestone has three parallel concerns: making the UI look and behave like a professional logistics product, fixing a critical data integrity bug where geocoding failures are silently swallowed, and adding the security headers and dependency hygiene required for any production web application. Research confirms all three are achievable with low-to-medium complexity additions — no architectural rewrites are needed.

The most important finding across all four research areas is a strict build order dependency. Tailwind + DaisyUI scaffolding must be installed and verified collision-free before any component work begins. Backend error propagation (the `geocoding_failures` structured response) must be shipped before the frontend import summary UI. Security middleware must be validated against the existing test suite before declaring hardening complete. Getting this sequence wrong is the most common failure mode for milestones like this — the research consistently flags that refactoring, behavior changes, and styling migrations should never be mixed in the same commit.

The single highest-risk item is the Tailwind v4 CSS variable namespace collision. Tailwind v4 emits `--color-*` CSS custom properties onto `:root` that will directly conflict with the existing dashboard design tokens (`--color-accent`, `--color-surface`, `--color-success`, etc.). The fix is a one-line change (`@import "tailwindcss" prefix(tw)`) at the very start of installation — but if this is missed, colors break silently and the resulting debugging cost is high. Every phase plan must treat this as a pre-condition checkpoint, not an afterthought.

## Key Findings

### Recommended Stack

The additive libraries for this milestone are well-established and version-pinned. For the UI layer: Tailwind CSS 4.2.1 + DaisyUI 5.5.19 are the confirmed current stable versions (npm-verified 2026-03-01), and DaisyUI v5 is Tailwind v4-native with zero runtime dependencies. Leaflet must stay at 1.9.4 — the 2.0.0 alpha breaks the existing plugin ecosystem including markercluster. For security: PyJWT 2.11.0 replaces abandoned python-jose (FastAPI team explicitly deprecated python-jose in 2025), and pwdlib 0.3.0 replaces abandoned passlib (passlib breaks on Python 3.13). For testing: hypothesis 6.151.9, factory_boy 3.3.3, pytest-cov 7.0.0, and respx 0.22.0 are all current stable, PyPI-verified.

The driver PWA presents a specific constraint: it has no build step. The correct solution is the Tailwind standalone CLI binary, which pre-compiles a static `tailwind.css` artifact at author time. This file is committed and cached by the service worker. The Tailwind Play CDN (`@tailwindcss/browser@4`) is explicitly documented as "not for production" by Tailwind Labs and is incompatible with the PWA's offline requirements.

**Core technologies:**
- Tailwind CSS 4.2.1 + DaisyUI 5.5.19: utility-first CSS with semantic components — covers all dashboard and PWA UI needs with a 34 kB CSS footprint
- PyJWT 2.11.0: JWT auth, replacing abandoned python-jose per FastAPI team recommendation
- pwdlib 0.3.0: password hashing, replacing abandoned passlib; Python 3.13-safe
- Secweb 1.11.0: one-call HTTP security header middleware for Starlette/FastAPI (MEDIUM confidence on version freshness)
- hypothesis 6.151.9 + factory_boy 3.3.3 + respx 0.22.0: property-based testing, fixture factories, and HTTP mock library for edge case coverage
- Leaflet.markercluster 1.5.3: cluster 300+ delivery pins without breaking map readability

### Expected Features

The gap between the current system and a professional logistics tool is primarily about visibility and feedback, not new functionality. The most critical missing feature is geocoding failure reporting: orders that fail geocoding silently disappear from the map. Dispatchers upload 47 orders and see 41 pins with no explanation. This is the core data integrity bug that blocks professional use. Every UI improvement layers on top of fixing this first.

**Must have (table stakes — P1):**
- Geocoding failure reporting (backend) — silent drops must become visible structured failures with address + reason
- Import summary screen — rows processed/geocoded/failed/unassigned shown after every upload
- HTTP security headers — X-Frame-Options, X-Content-Type-Options, CSP, Referrer-Policy, Permissions-Policy
- Actionable error messages — replace generic "Upload failed" strings with specific, row-level guidance
- Consistent design system — Tailwind + DaisyUI applied uniformly; no mixed CSS approaches

**Should have (competitive — P2):**
- Row-level import report table (Row | Address | Status | Reason) with export to CSV
- CORS origin whitelist restricted to known production origins
- Toast notification system for all user actions (non-blocking, auto-dismissing)
- Empty states for all pages (not blank screens)
- Unassigned order detail — which specific orders weren't routed and why
- API docs gating — disable /docs and /redoc in production
- Environment variable validation at startup — fail loudly with helpful messages
- One-command Docker setup with Kerala OSM data preprocessing documented

**Defer to future (P3):**
- Geocoding confidence display per stop
- Capacity utilization bars on route cards
- ETA display in driver stop list
- Driver PWA high-contrast mode for bright outdoor use
- Dependency security scan in CI (pip-audit, npm audit)

### Architecture Approach

The architecture for this milestone is additive, not disruptive. The FastAPI middleware stack gets security headers inserted at the outermost layer. The `OptimizationSummary` Pydantic model gains a `geocoding_failures: list[GeocodingFailure]` field that surfaces what the geocoder already knows but currently drops. The React dashboard gets `@tailwindcss/vite` added to `vite.config.ts` and a `useToast` hook with a `ToastContainer` component. The driver PWA gets a pre-compiled static CSS file. All existing components, routes, and integrations remain in place throughout.

**Major components and their changes:**
1. `api/main.py` middleware stack — add Secweb security headers as outermost middleware; validate CORS origin whitelist; confirm CORS middleware is registered first so error responses (429, 401) include CORS headers
2. `core/geocoding/google_adapter.py` — collect failures into a structured list instead of logging and dropping; return `GeocodingFailure` objects with order_id, address_raw, and classified reason code
3. `dashboard/src/` — install Tailwind via `@tailwindcss/vite` plugin; add DaisyUI; implement `useToast` hook; migrate components one at a time with component CSS files deleted only after visual verification
4. `driver_app/index.html` — pre-compile Tailwind CSS via standalone CLI; bump `sw.js` CACHE_VERSION; avoid DaisyUI interactive variant components (CDN excludes them)
5. `tests/` — replace Kochi depot coordinates with Vatakara coordinates; add behavior-asserting tests for geocoding failures and VROOM timeout; reset rate limiter state between tests

### Critical Pitfalls

1. **Tailwind v4 CSS variable collision** — use `@import "tailwindcss" prefix(tw)` immediately at install time. Tailwind v4 emits `--color-*` variables that override the dashboard's existing `--color-accent`, `--color-surface` etc. Silent breakage. Fix: one-line prefix at install; verify in DevTools before writing any utility classes. (See: tailwindlabs/tailwindcss#15754)

2. **CORS headers missing on error responses (429/401)** — CORS middleware must be registered first (`app.add_middleware(CORSMiddleware, ...)` before all other middleware). If registered after rate limiting or auth middleware, error responses escape without `Access-Control-Allow-Origin` and the browser reports a misleading CORS error instead of the actual 429 or 401.

3. **Rate limiting breaks the existing 351-test suite** — slowapi's in-memory limiter persists state across TestClient calls. After adding `@limiter.limit()` decorators, E2E pipeline tests and parametrized upload tests will fail with 429. Fix: add an `autouse=True` conftest fixture that resets limiter state between tests.

4. **Removing "dead code" that is actually defense-in-depth** — `main.py` is 1760 lines of AI-generated code with overlapping security guards. Removing what looks redundant (duplicate escape calls, multiple null checks) destroys layered protection. Rule: trace every code path before removing a guard; run the full test suite after each individual file cleanup.

5. **E2E tests use Kochi coordinates instead of Vatakara** — existing test fixtures define `KOCHI_DEPOT` at latitude ~9.97° (Kochi) while production uses Vatakara at 11.52°N. Tests pass because VROOM doesn't validate geography, but geographic bounds tests are meaningless against the wrong location. Fix first, before writing any new tests.

## Implications for Roadmap

Based on research, the build order is dictated by hard dependencies, not preference. The architecture research provides an explicit 8-step sequence that should translate directly into phase structure.

### Phase 1: Foundation Setup
**Rationale:** Nothing else can proceed safely without this. Tailwind installation must be verified collision-free before component work. Backend structured error model must exist before frontend can parse it. These are blockers, not features.
**Delivers:** Tailwind + DaisyUI integrated into Vite build and verified against existing CSS tokens; `GeocodingFailure` Pydantic model and structured `OptimizationSummary` response shape defined; `useToast` React hook and `ToastContainer` component built; Vatakara depot coordinates corrected in all test fixtures.
**Addresses:** Consistent design system foundation (P1), geocoding failure reporting backend (P1)
**Avoids:** CSS variable collision (Pitfall 1), wrong test geography causing false-green tests (Pitfall 6)

### Phase 2: Security Hardening
**Rationale:** Security middleware is independent of UI work and can proceed in parallel with Phase 1 but should be verified and merged before UI components are built on top. Middleware order must be confirmed before any endpoint changes.
**Delivers:** Secweb security headers middleware added; CORS origin whitelist restricted to production origins; API docs gating in production mode; environment variable validation at startup; rate limiter reset fixture in conftest.
**Uses:** Secweb 1.11.0, PyJWT 2.11.0, pwdlib 0.3.0
**Avoids:** CORS headers missing on error responses (Pitfall 3), rate limiting breaking test suite (Pitfall 4), dev mode unusable after hardening (Pitfall 9)

### Phase 3: Geocoding Failure Visibility
**Rationale:** The core data integrity bug. Must ship before UI improvements because the import summary screen has nothing meaningful to display until the backend returns structured failure data.
**Delivers:** `GoogleGeocoder.batch()` accumulates per-order failures; `POST /api/upload-orders` returns `geocoding_failures[]` with classified reason codes; import summary screen shows processed/geocoded/failed counts; toast warning for partial geocoding with expandable failure list.
**Addresses:** Geocoding failure reporting (P1 blocker), import summary screen (P1), actionable error messages (P1)
**Avoids:** Silent drop anti-pattern (Architecture Anti-Pattern 3)

### Phase 4: UI Polish and Component Migration
**Rationale:** With foundation verified and error data available from the backend, component-by-component Tailwind migration can proceed. Progressive migration (one component per PR, CSS file deleted only after visual verification) prevents big-bang regression.
**Delivers:** All dashboard pages migrated to Tailwind + DaisyUI classes; empty states for all pages; toast system wired to all user actions; per-component CSS files deleted; row-level import report table with CSV export; unassigned order detail view.
**Addresses:** Consistent design system (P1), empty states (P2), row-level import report (P2), unassigned order detail (P2), failed row download (P2)
**Avoids:** One giant CSS cleanup commit (Architecture Anti-Pattern 4), DaisyUI theme variable bypass (Architecture Anti-Pattern 2)

### Phase 5: Driver PWA Update
**Rationale:** The driver PWA update is independent of the dashboard migration but must not proceed until the Tailwind standalone CLI pre-compilation workflow is established in Phase 1. Service worker cache versioning is a hard requirement for every change.
**Delivers:** Pre-compiled `tailwind.css` generated by Tailwind standalone CLI; inline styles replaced with DaisyUI utility classes; `sw.js` CACHE_VERSION bumped; interactive states (modals, stop list) managed via vanilla JS `classList.toggle()` not DaisyUI variant classes.
**Addresses:** Driver PWA design consistency
**Avoids:** Play CDN in production (Architecture Anti-Pattern 1), DaisyUI CDN missing interactive states (Pitfall 2), service worker cache staleness (Pitfall 8)

### Phase 6: Test Quality and Code Cleanup
**Rationale:** Code cleanup must come last — never mixed with behavior changes. Test improvements can identify gaps left by earlier phases and lock in correct behavior as a regression net. Cleanup requires a fully green test suite as a pre-condition.
**Delivers:** hypothesis property-based tests for geocoding coordinate validators and weight calculations; factory_boy fixtures replacing hard-coded dicts; respx mocks for Google Geocoding API and OSRM calls; pytest-cov coverage gate in CI; ruff + vulture cleanup of unused imports and dead code; `main.py` slop removal (inline imports, phase-comment noise, redundant try/except); one-command Docker setup documented.
**Uses:** hypothesis 6.151.9, factory_boy 3.3.3, respx 0.22.0, pytest-cov 7.0.0
**Avoids:** Removing defense-in-depth code (Pitfall 5), behavior vs. mock-verification tests (Pitfall 11), OSRM documentation gap (Pitfall 10), refactoring mixed with feature work (Architecture Anti-Pattern 5)

### Phase Ordering Rationale

- **Foundation first** because both CSS variable collision and test fixture geography errors will corrupt everything built on top of them if not fixed before other phases begin.
- **Security before UI polish** because middleware order affects every endpoint, and it is far easier to verify CORS headers on clean endpoints than after component migration has touched `main.py`.
- **Backend error propagation before frontend summary UI** because the frontend import summary is meaningless without structured data from the API — a strict data dependency confirmed by the feature dependency graph in FEATURES.md.
- **Driver PWA after dashboard** because the Tailwind standalone CLI workflow established for the dashboard informs the PWA pre-compilation approach; doing PWA first would require discovering this in isolation.
- **Cleanup last** because the architecture research explicitly states: never mix refactoring with behavior changes. The 351-test suite is the safety net; it must be green throughout every cleanup step.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Geocoding Failure Visibility):** The `_classify_geocode_failure()` helper and the Google Geocoding API status code taxonomy need validation against the actual API response format in the codebase before implementation. Architecture research provides a pattern but codebase-specific details matter.
- **Phase 5 (Driver PWA):** The Tailwind standalone CLI download URL and exact binary invocation for the project's Docker build environment (Linux x64 on WSL2) should be verified at planning time. The service worker cache size for offline map tile pre-caching is flagged as ~50MB in PITFALLS.md — confirm this is acceptable before committing to it.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation Setup):** Tailwind + DaisyUI installation is well-documented with official step-by-step guides verified against current versions.
- **Phase 2 (Security Hardening):** HTTP security headers and CORS configuration are OWASP-documented patterns; Secweb middleware reduces this to a one-call integration.
- **Phase 6 (Cleanup):** ruff, vulture, and pytest-cov tooling are mature with established usage patterns; no novel integration work required.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified directly on PyPI/npm as of 2026-03-01. Version compatibility matrix confirmed (Tailwind 4 + DaisyUI 5, PyJWT + FastAPI 0.129, respx + httpx 0.28.1). One exception: Secweb 1.11.0 is MEDIUM — release date not pinned, monitor GitHub for freshness. |
| Features | MEDIUM-HIGH | P1 features are directly grounded in codebase gaps (geocoding failures confirmed by code inspection). P2/P3 priority ordering uses competitor analysis from Onfleet and Routific, which are MEDIUM-confidence marketing sources. Core must-haves are HIGH confidence. |
| Architecture | HIGH | Build order sequence is derived from actual codebase structure (1760-line `main.py` inspected, `OptimizationSummary` model traced, Vite config reviewed). Structured error response pattern follows FastAPI official docs. PWA offline constraint is grounded in existing `sw.js` inspection. |
| Pitfalls | HIGH | Six critical pitfalls are grounded in either official GitHub issues (tailwindlabs/tailwindcss#15754), official docs (FastAPI middleware ordering, DaisyUI CDN limitations), or direct codebase inspection (Kochi vs. Vatakara coordinates, rate limiter test isolation). |

**Overall confidence:** HIGH

### Gaps to Address

- **Secweb CSP header tuning:** The CSP must allow Leaflet tile URLs (unpkg.com, OSM tile servers) and the existing Google Geocoding API calls. The exact CSP policy string needs to be drafted and tested against the running application — a misconfigured CSP silently breaks map tiles. Address during Phase 2 planning.
- **Geocoding API response shape:** The `_classify_geocode_failure()` helper in ARCHITECTURE.md assumes specific status codes from Google Geocoding API. Verify these against actual API responses in the codebase (`core/geocoding/google_adapter.py`) before implementing. Address during Phase 3 planning.
- **Rate limiter multi-worker behavior:** PITFALLS.md flags that slowapi's in-memory limiter produces inconsistent behavior when uvicorn runs with `--workers N > 1`. If the deployment uses multiple workers, a Redis backend for slowapi is required. Confirm deployment topology during Phase 2 planning.
- **Offline map tile pre-caching scope:** Caching OSM tiles for a 30km radius around Vatakara at zoom 10–16 is estimated at ~50MB. Confirm whether this is within acceptable PWA install size for the target Android devices before committing to the approach in Phase 5.

## Sources

### Primary (HIGH confidence)
- [DaisyUI npm](https://www.npmjs.com/package/daisyui) — v5.5.19 version verified 2026-03-01
- [Tailwind CSS npm](https://www.npmjs.com/package/tailwindcss) — v4.2.1 version verified 2026-03-01
- [Tailwind CSS v4 official blog](https://tailwindcss.com/blog/tailwindcss-v4) — CSS-variable architecture, no tailwind.config.js
- [Tailwind Play CDN docs](https://tailwindcss.com/docs/installation/play-cdn) — "not for production" confirmed
- [Leaflet 2.0 alpha blog](https://leafletjs.com/2025/05/18/leaflet-2.0.0-alpha.html) — alpha status, breaking plugin API
- [PyJWT PyPI](https://pypi.org/project/PyJWT/) — v2.11.0 released Jan 30, 2026
- [FastAPI discussion #11345](https://github.com/fastapi/fastapi/discussions/11345) — python-jose abandonment, PyJWT recommendation
- [pwdlib PyPI](https://pypi.org/project/pwdlib/) — v0.3.0, bcrypt+argon2 backends, Python 3.13 safe
- [FastAPI discussion #11773](https://github.com/fastapi/fastapi/discussions/11773) — passlib abandonment, pwdlib recommendation
- [OWASP HTTP Headers Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html) — required security headers
- [FastAPI middleware ordering docs](https://fastapi.tiangolo.com/advanced/middleware/) — CORS must be outermost
- [FastAPI error handling docs](https://fastapi.tiangolo.com/tutorial/handling-errors/) — structured detail dict pattern
- [DaisyUI CDN limitations](https://daisyui.com/docs/cdn/) — interactive variant classes excluded
- [tailwindlabs/tailwindcss#15754](https://github.com/tailwindlabs/tailwindcss/issues/15754) — CSS variable namespace collision
- Codebase inspection: `apps/kerala_delivery/api/main.py`, `apps/kerala_delivery/dashboard/src/index.css`, `tests/test_e2e_pipeline.py`, `.planning/codebase/CONCERNS.md`

### Secondary (MEDIUM confidence)
- [hypothesis PyPI](https://pypi.org/project/hypothesis/) — v6.151.9 released Feb 2026
- [factory-boy PyPI](https://pypi.org/project/factory-boy/) — v3.3.3
- [respx PyPI](https://pypi.org/project/respx/) — v0.22.0, httpx>=0.25 required
- [pytest-cov PyPI](https://pypi.org/project/pytest-cov/) — v7.0.0
- [Secweb libraries.io](https://libraries.io/pypi/Secweb) — v1.11.0 (release date not fully pinned)
- [Onfleet Driver Status Docs](https://support.onfleet.com/hc/en-us/articles/10228905705876-Driver-Status) — driver status color conventions
- [Dromo CSV Import Best Practices](https://dromo.io/blog/ultimate-guide-to-csv-imports) — row-level error reporting UX
- [slowapi documentation](https://slowapi.readthedocs.io/) — rate limiter test isolation patterns
- [Simon Willison — Tips for coding agents to write good Python tests (2026)](https://simonwillison.net/2026/Jan/26/tests/) — behavior-first test principle

### Tertiary (LOW confidence — needs validation)
- [FastAPI OWASP hardening guide](https://oneuptime.com/blog/post/2025-01-06-fastapi-owasp-security/view) — single source, 2025; verify CSP header values against actual tile CDN URLs used
- Offline map tile caching size estimate (~50MB for Vatakara 30km radius, zoom 10–16) — derived from general OSM tile density estimates; needs measurement

---
*Research completed: 2026-03-01*
*Ready for roadmap: yes*
