# Pitfalls Research

**Domain:** Logistics delivery route optimizer — milestone improvement (UI overhaul, security hardening, code cleanup, test improvement, documentation)
**Researched:** 2026-03-01
**Confidence:** HIGH (project-specific, grounded in actual codebase inspection + official docs)

---

## Critical Pitfalls

### Pitfall 1: Tailwind v4 CSS Variable Namespace Collision

**What goes wrong:**
Tailwind CSS v4 auto-generates CSS custom properties on `:root` using the `--color-*` prefix (e.g., `--color-red-500`, `--color-gray-200`). The dashboard's `index.css` already defines an extensive set of custom properties using the same prefix pattern: `--color-surface`, `--color-accent`, `--color-text-primary`, `--color-border`, `--color-success`, etc. When Tailwind is added, its generated variables silently override or are overridden by the project's existing ones. The result is broken colors in components that mix Tailwind utilities with the existing CSS variable system — some elements turn the wrong color, others lose their color entirely.

**Why it happens:**
Tailwind v4 changed from `tailwind.config.js` to a CSS-first configuration, and all theme tokens now emit as CSS variables on `:root`. This is a well-documented conflict tracked in [tailwindlabs/tailwindcss#15754](https://github.com/tailwindlabs/tailwindcss/issues/15754). Developers installing Tailwind into an existing project assume the utility classes are additive, not realizing the `:root` variable injection is a global side effect.

**How to avoid:**
Add `@import "tailwindcss" prefix(tw)` in the CSS entry point. This namespaces all Tailwind-generated variables as `--tw-color-red-500`, `--tw-font-display`, etc., preventing any collision with the existing `--color-*` design token system. The existing CSS variables in `index.css` and `App.css` remain untouched. Verify after installation by checking `:root` in DevTools — you should see both `--color-accent` (project) and `--tw-color-amber-600` (Tailwind) without collision.

**Warning signs:**
- Header or sidebar colors shift immediately after adding Tailwind — even before writing any utility classes
- DevTools shows `--color-surface` overriding or overridden by Tailwind's palette
- DM Sans font stops rendering correctly (Tailwind's `--font-sans` conflicts with `--font-body`)
- `tailwind.config.js` present alongside `@import "tailwindcss"` in CSS (double-processing)

**Phase to address:** UI overhaul phase — install Tailwind with prefix before writing any utility classes.

---

### Pitfall 2: DaisyUI CDN Missing Interactive Component States in the Driver PWA

**What goes wrong:**
The driver PWA (`driver_app/index.html`) is a standalone HTML/JS app with no build step. To add DaisyUI styling, the natural choice is the CDN file. However, DaisyUI's interactive component variant classes (`is-drawer-open`, `is-drawer-close`, modal open/close states) are explicitly excluded from the CDN bundle to keep file size manageable. Any DaisyUI component that relies on toggling a variant class will appear broken — the drawer will not animate open/closed, modals may be permanently visible or invisible.

**Why it happens:**
The CDN file ships only the CSS for static component appearances. Variant-class-driven state changes require the full npm build output. Developers discover this hours into integration when components that look correct in static demos fail in the interactive PWA.

**How to avoid:**
For the driver PWA, do not use DaisyUI interactive components that rely on variant classes. Instead: (1) use DaisyUI purely for static visual styling — buttons, badges, typography, cards; (2) manage interactive states (e.g., stop list expand/collapse, confirmation dialogs) using JavaScript `classList.toggle()` with plain CSS transitions already in the PWA. The PWA's existing dark-first CSS (`background: #0B0B0F`, saffron `#FF9410` accent) is well-suited to adopt DaisyUI's data-theme attribute for theming without relying on variant class state management.

**Warning signs:**
- Modal dismissal button does nothing visually when using `modal-open` class pattern
- Drawer components stay permanently open or closed
- No animation on DaisyUI collapse components
- Browser console shows no errors (this is a silent CSS-only failure)

**Phase to address:** UI overhaul phase, specifically the driver PWA sub-task.

---

### Pitfall 3: FastAPI Middleware Order Breaking CORS on Security Errors

**What goes wrong:**
When activating slowapi rate limiting decorators on endpoints, requests that exceed the limit return HTTP 429. If CORS middleware is not the outermost middleware in the stack, the 429 response will be sent without `Access-Control-Allow-Origin` headers. The browser receives a 429 with no CORS headers and reports a CORS error instead of a rate-limit error — making the actual problem invisible to the frontend and extremely confusing to debug.

**Why it happens:**
FastAPI (Starlette) applies middleware in the order added: last added = outermost. CORS middleware must be the first added (which makes it the outermost) so it runs on every response including error responses. If security middleware (authentication dependency, rate limit handler) is added before CORS middleware in the registration order, error responses escape without CORS headers.

**How to avoid:**
In `main.py`, ensure `app.add_middleware(CORSMiddleware, ...)` is called first — before any other `add_middleware` call. The slowapi rate limit exception handler is registered separately (`app.add_exception_handler(RateLimitExceeded, ...)`) and does not affect middleware order, but verify it generates responses that include correct status codes. Test explicitly by triggering a 429 from a browser (not curl) and confirming the response has `Access-Control-Allow-Origin`.

**Warning signs:**
- Browser console shows "CORS policy" error on what should be a 429 or 401
- curl shows the correct error (401/429) but the React dashboard shows a generic network error
- After adding rate limits, upload functionality appears to break intermittently

**Phase to address:** Security hardening phase — test CORS headers on every error code path before declaring security hardening complete.

---

### Pitfall 4: Activating Rate Limiting Breaks Existing Tests

**What goes wrong:**
The existing test suite uses `fastapi.testclient.TestClient` which shares the same in-memory limiter state across tests. When rate limit decorators are added to endpoints, tests that call the same endpoint multiple times (e.g., parametrized CSV upload tests, E2E pipeline tests that run several upload cycles) start failing with HTTP 429 after the first few calls. Because the limiter is initialized once per process, limits do not reset between test functions.

**Why it happens:**
slowapi uses an in-memory backend by default. TestClient reuses the same app instance across all tests in a session. A test suite with 10 upload tests each calling `POST /api/upload-orders` will hit the "2/minute" limit after 2 calls and the remaining 8 tests fail with 429, not the assertion error they were designed to test.

**How to avoid:**
Add a `@pytest.fixture(autouse=True)` that resets the limiter between tests: `app.state.limiter.reset()` or use slowapi's `storage_uri` to point to a fresh in-memory store per test. Alternatively, inject an environment variable that disables rate limiting during test runs (`DISABLE_RATE_LIMIT=true` checked in the limiter key function). Document which tests require this override in `conftest.py`.

**Warning signs:**
- Tests that passed individually start failing when the full suite runs
- Upload-related tests fail with 429 status instead of their expected assertion error
- Test failures disappear when tests run in isolation but appear in CI

**Phase to address:** Security hardening phase — must validate test suite still passes immediately after adding rate limit decorators.

---

### Pitfall 5: Removing "Dead Code" That Is Actually Defense-in-Depth

**What goes wrong:**
`main.py` is 1760 lines. During AI-code cleanup, code that appears redundant — duplicate null checks, overly cautious bounds validation, `if not api_key` branches that also check hmac — is removed as "defensive programming gone too far." The resulting code is cleaner but loses protection against a class of inputs. For example: removing the secondary `html_module.escape()` call on address fields because "Pydantic already validates them" creates an XSS vector if the CSV importer ever accepts a different code path. The bug is invisible until a driver sees injected HTML in a QR sheet.

**Why it happens:**
AI-generated code that was written cautiously tends to have multiple overlapping guards. A human reviewer pattern-matches this as "redundant" without tracing whether each layer guards a different code path. The 1760-line `main.py` has security-critical code interleaved with business logic throughout — it is not structured with clear security boundaries.

**How to avoid:**
Before removing any validation, null check, or escape call: trace all code paths that reach that line. Ask "what input triggers this branch?" not "is this branch reachable in the happy path?" Pay specific attention to: `html_module.escape()` calls (each one blocks a distinct XSS vector), `hmac.compare_digest` usage (not replaceable with `==`), and the `_get_geocoder()` initialization lock pattern. Run the full test suite after each individual removal, not after a batch of removals. If a removed guard had no test, write one before removing it.

**Warning signs:**
- Cleanup PR removes more than 50 lines at once without corresponding test additions
- The word "redundant" appears in a PR description next to a security-related change
- `main.py` drops by more than 200 lines in a single cleanup pass
- A removed `if not X` guard was checking a value that comes from user input (even if Pydantic-validated)

**Phase to address:** Code quality cleanup phase — requires pre-cleanup test coverage audit.

---

### Pitfall 6: E2E Tests Use Kochi Coordinates Instead of Vatakara

**What goes wrong:**
The E2E pipeline test (`tests/test_e2e_pipeline.py` line 43) defines `KOCHI_DEPOT = Location(latitude=9.9716, longitude=76.2846, address_text="Depot")` — Kochi, not Vatakara. The production `config.py` uses Vatakara depot coordinates. Tests pass because the optimizer does not validate geographic plausibility — VROOM accepts any valid lat/lon pair. But the test suite validates the wrong geography: coordinate bounds checks tuned for Vatakara (roughly 11.5°N, 75.6°E) do not trigger, monsoon-area safety multiplier tests against the wrong base location, and any future bounds validation logic will not be exercised by tests that run against Kochi.

**Why it happens:**
Initial test fixtures were written before the depot location was finalized. Kochi is the obvious "Kerala city" and a reasonable placeholder. It was never updated when the requirement clarified to Vatakara.

**How to avoid:**
Replace all test depot fixtures with Vatakara coordinates (`latitude=11.5167, longitude=75.5931`) immediately during the test improvement phase. Add a `conftest.py` constant `VATAKARA_DEPOT` and assert its coordinates match `config.DEPOT_LATITUDE` / `config.DEPOT_LONGITUDE` — this turns the test suite into a guard against future depot coordinate changes. Delivery location fixtures should use addresses within 30km of Vatakara (not Kochi, 200km away).

**Warning signs:**
- Any fixture with latitude ~9.9° (Kochi latitude) in a test about Vatakara delivery
- Tests pass when `VATAKARA_DEPOT` is swapped in without any assertion changes
- Bounds-checking tests do not fail when Kochi coordinates are out of the Vatakara service area

**Phase to address:** Test improvement phase — fix before any other test improvements so all new tests start from the correct geography.

---

## Moderate Pitfalls

### Pitfall 7: Tailwind Preflight Resets Breaking Existing Component Styles

**What goes wrong:**
Tailwind's Preflight (based on modern-normalize) adds `border-style: solid` to all elements, sets `line-height: inherit`, removes default margins/padding, and changes `<button>` appearance. The dashboard's existing CSS relies on browser defaults for some of these properties (particularly `button` font inheritance, `table` border-collapse behavior, `h1-h6` margin). After Tailwind is installed, existing components that relied on browser defaults shift layout slightly or lose styling.

**How to avoid:**
The dashboard's `index.css` already explicitly resets most of these (box-sizing, button font-family, h* margin, table border-collapse). Verify these explicit resets override Preflight. After installing Tailwind, visual-diff every page before writing any utility classes — any change is a Preflight regression, not a Tailwind utility bug. If Preflight creates conflicts that cannot be easily overridden, disable it with `@layer base { * { all: revert; } }` — though this is a last resort.

**Phase to address:** UI overhaul phase — first step after installing Tailwind.

---

### Pitfall 8: Service Worker Cache Staleness After CSS/JS Updates

**What goes wrong:**
The driver PWA has a service worker (`sw.js`) that caches static assets. After adding or updating CSS (Tailwind CDN URL, new stylesheet versions), deployed drivers see the old cached UI until the service worker updates — which only happens when `sw.js` itself changes. A CSS update that is not accompanied by a `sw.js` cache version bump is invisible to installed PWA users. If the new CSS has a critical layout fix for outdoor readability (the PWA's primary concern), drivers continue with the broken layout.

**How to avoid:**
Every CSS/JS change to the driver PWA must be accompanied by a cache version bump in `sw.js` (typically a `CACHE_VERSION` or `CACHE_NAME` constant). Add a checklist item to the driver PWA update process. For Tailwind/DaisyUI CDN: pin the CDN URL to a specific version (not `@latest`) so the cache key is stable and intentional upgrades are explicit.

**Phase to address:** UI overhaul phase, driver PWA sub-task.

---

### Pitfall 9: Security Hardening Making Dev Mode Unusable

**What goes wrong:**
The current codebase has a "dev mode" where `API_KEY` unset means no auth required (correct). Hardening efforts sometimes add validation that requires `API_KEY` to be set even in development (e.g., "require all env vars at startup"), or tighten CORS to disallow `localhost:5173`. Developers then need to configure secrets just to run locally, making the development loop painful and incentivizing people to hardcode secrets in `.env` files that get committed.

**How to avoid:**
Maintain the existing `ENVIRONMENT != "development"` guard for auth enforcement. For CORS, `localhost:5173` must remain in the allowed origins list when `ENVIRONMENT=development`. Separate the `CORS_ALLOWED_ORIGINS` variable into dev defaults and production requirements. Startup validation should warn in dev, not error. The principle: hardening must not change the local development experience.

**Phase to address:** Security hardening phase — validate that `ENVIRONMENT=development` still works without any API key or production secrets.

---

### Pitfall 10: Documentation Omitting Docker Compose Startup Order

**What goes wrong:**
A rewritten README documents `docker-compose up` but omits the dependency chain: OSRM requires the Kerala OSM data to be loaded before it can respond to routing requests (this is a multi-hour preprocessing step on first run). New contributors run `docker-compose up`, all containers start, but OSRM returns 400 for every routing request until the data is pre-processed. The OSRM data-loading step is a one-time operation that requires a separate `docker-compose run` command with specific volume mounts.

**How to avoid:**
Document the two-phase startup explicitly: (1) data preprocessing (one-time), (2) service startup (ongoing). Include the exact commands with copy-paste safety — no placeholders. Add a verification step: `curl http://localhost:5000/route/v1/driving/75.59,11.52;75.60,11.53` should return a valid route response. If it returns `{"message":"Incorrect coordinates"}` the data is loaded but coordinates are wrong; if it returns connection refused, OSRM is still starting. This distinction saves 2-3 hours of debugging for every new setup.

**Phase to address:** Documentation phase — treat the OSRM data-loading requirement as the most critical setup step.

---

### Pitfall 11: Test "Improvement" Converting Behavior Tests Into Mock-Verification Tests

**What goes wrong:**
When improving test coverage, the temptation is to add tests that verify how code is called (mock call counts, argument inspection) rather than what the system does (correct output for valid inputs, correct errors for invalid inputs). For this codebase, this looks like: asserting `geocoder.geocode.call_count == len(orders)` instead of asserting that the returned route has all orders assigned. The mock-verification test passes even when the geocoding logic has a bug that returns wrong coordinates — because it only checks that the mock was called.

**How to avoid:**
For every new test, ask: "if the function under test returned garbage output, would this test fail?" If no — the test is testing the mock, not the behavior. Prefer output assertions (`assert route.total_stops == 5`) over call assertions (`assert mock.call_count == 5`). The existing E2E tests that check full pipeline output are good models. Add coverage for: (1) geocoding failure → validation report includes failed rows, (2) VROOM timeout → 503 response with helpful message, (3) CSV with midnight-crossing windows → either valid route or explicit error, not silent drop.

**Phase to address:** Test improvement phase — enforce behavior-first rule in the PR checklist.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Using Tailwind utility classes directly in JSX without abstraction | Fast styling during overhaul | Hundreds of utility strings scattered through 4 pages — hard to maintain a consistent look | Only acceptable for one-off styles; create component CSS classes for repeated patterns |
| Adding DaisyUI themes via `data-theme` attribute at `<html>` level | Quick dark/light toggle | Theme applies globally including to Leaflet map tiles and popups, causing map readability issues | Never for this project — scope theme to the app container, not `<html>` |
| Skipping rate limit testing by mocking the limiter | Tests run faster | Rate limit logic is never actually tested; production behavior is unverified | Never — test the limiter with real calls to verify 429 responses |
| Hardcoding new lint rules during code cleanup | Code gets cleaner | If lint rules are stricter than what existing code passes, the pipeline breaks for everyone immediately | Add lint rules incrementally; fix existing violations before adding new rules |
| Using `# type: ignore` during cleanup to suppress TypeScript/mypy warnings | Cleanup PR is smaller | Suppressed errors resurface in production and are harder to debug | Only temporarily during active migration, must resolve before merging |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Google Geocoding API | Assuming cached addresses are always correct — cache hit means "address was geocoded once", not "coordinates are still valid" | Add cache TTL (e.g., 90 days) and flag addresses where geocoding confidence was LOW for periodic re-validation |
| VROOM optimizer | Not checking the VROOM container health before submitting optimization — if VROOM exits, the 60-second timeout blocks the upload endpoint | Add a startup health check that verifies VROOM responds before accepting orders; return 503 with explanation if VROOM is unavailable |
| OSRM routing | Passing coordinates in (lat, lon) order — OSRM expects (lon, lat) | Verify coordinate order in `osrm_adapter.py`; add a unit test that asserts OSRM receives coordinates in (lon, lat) order |
| Leaflet in Driver PWA | Importing Leaflet from CDN and then adding DaisyUI from CDN — both add global CSS that may conflict with `.leaflet-container` styles | Load Leaflet CSS first, DaisyUI second; check that `.leaflet-popup-content` text color is not overridden by DaisyUI's base styles |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| N+1 route detail fetches in LiveMap | Dashboard hangs for 5+ seconds on page load as fleet grows | Create `GET /api/routes?include_stops=true` batch endpoint; see CONCERNS.md | At 30+ vehicles in a single batch |
| Tailwind JIT scanning entire codebase | Vite dev server gets slow when Tailwind scans `node_modules` | Explicitly configure `content` in Tailwind config to only scan `src/**/*.{tsx,ts}` — not `node_modules`, not `dist` | Not a scale issue but a DX issue immediately on large projects |
| Geocoding 250+ addresses synchronously | Import of large CDCMS batches times out in 30s; user sees error with no partial result | Queue geocoding as background task; return partial result immediately | First time a large CDCMS export is imported |
| Rate limiter in-memory state in multi-worker uvicorn | Rate limits appear inconsistent (different workers have different counts) | Use Redis backend for slowapi (`storage_uri="redis://localhost:6379"`) when running multiple workers | When uvicorn is started with `--workers N` where N > 1 |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Committing `.env` with `API_KEY` during documentation phase | API key exposed in git history; full access to all endpoints permanently compromised | Add `.env` to `.gitignore` before creating it; verify `.env.example` contains only placeholders (`API_KEY=your-key-here`), never real values |
| QR code URLs expose raw GPS coordinates | Driver routes become public if QR codes are photographed — GPS coordinates of all delivery stops exposed | Current mitigation (HTTPS + short-lived tokens) is sufficient for this use case; do not embed coordinates in QR URLs in any future endpoint that returns public QR codes |
| DaisyUI theme `data-theme="dark"` leaking driver names into page title | Not directly a security issue but `document.title` set from route data could expose driver assignment | Ensure page title is generic ("LPG Delivery Route") not "{driver_name}'s Route" |
| Unvalidated `vehicle_id` in telemetry endpoint | Attacker enumerates vehicle IDs to scrape GPS history for all vehicles | Current API key protects this, but if key is shared with drivers, any driver can query all vehicles; add vehicle-scoped keys in future |
| Rate limit bypass via X-Forwarded-For header spoofing | Attacker sets custom `X-Forwarded-For: 1.2.3.4` to use a different IP for each request, bypassing per-IP limits | Configure slowapi to trust proxy headers only when behind a known reverse proxy; use `get_remote_address` (default) which reads real socket IP when no proxy is involved |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing a loading spinner without timeout on VROOM optimization | Dispatcher waits indefinitely when VROOM is slow; cannot tell if system is working or broken | Set a client-side timeout (65s) that shows "Optimization is taking longer than usual — check server logs" |
| CSV validation errors shown only as a toast notification | Notification disappears; dispatcher cannot see which rows failed | Persist validation report as a collapsible section below the upload form; allow export of failed-row list to CSV |
| Driver PWA requiring internet to load map tiles | Drivers in low-connectivity areas (common in rural Kerala) see a blank map | Cache map tiles for the Vatakara delivery area in the service worker; tiles for 30km radius around Vatakara at zoom levels 10-16 are ~50MB and cacheable |
| Outdoor readability on dark theme not verified | Drivers in direct sunlight on Piaggio Ape cannot see route details | Test PWA UI on a physical Android device in bright light; the existing 7:1 WCAG AAA contrast ratio is correct but needs field validation |
| Countdown timers in driver PWA | MVD compliance violation under Kerala Motor Vehicles Department rules | Never add countdown timers to the driver PWA — existing design correctly omits them; security hardening phase must not add "session expiry countdown" UI |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Tailwind installation:** Verify no CSS variable collisions with existing `--color-*` tokens in DevTools `:root` inspector before writing any utility classes
- [ ] **DaisyUI in driver PWA:** Verify interactive component states (open/close) work via JavaScript after confirming CDN lacks variant classes
- [ ] **Rate limiting:** Verify 429 responses include CORS headers by triggering a rate limit from the browser (not curl)
- [ ] **Rate limiting tests:** Verify existing test suite still passes after adding `@limiter.limit()` decorators — specifically E2E pipeline and CSV upload tests
- [ ] **Code cleanup:** Run full test suite after each individual file cleanup, not once after all cleanups
- [ ] **Test fixtures:** Verify all depot/location fixtures use Vatakara coordinates, not Kochi
- [ ] **OSRM documentation:** Verify README includes the one-time Kerala OSM data preprocessing step with exact commands
- [ ] **Service worker cache:** Verify `sw.js` cache version was bumped after any CSS/JS asset change
- [ ] **Security env vars:** Verify `ENVIRONMENT=development` still runs without API_KEY configured after security hardening

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| CSS variable collision discovered after writing 200 lines of Tailwind utilities | HIGH | Add Tailwind prefix (`@import "tailwindcss" prefix(tw)`), then do a find-replace to prefix all Tailwind utility classes in JSX — this is mechanical but tedious; use `npx @tailwindcss/upgrade` first to automate what it can |
| Rate limiting breaks test suite after security hardening merge | MEDIUM | Add `autouse=True` fixture in conftest.py that resets limiter state between tests; no test logic changes needed |
| Removed "redundant" code caused a regression found in production | HIGH | Revert the cleanup PR (git revert); write a test that reproduces the regression before re-attempting cleanup; add the test to CI so the regression cannot reoccur |
| OSRM documentation gap causes 3-hour setup failure for new contributor | LOW | Add the OSRM preprocessing step to README immediately; add a `make setup` or `docker-compose run osrm-preprocess` command that encapsulates the one-time step |
| Service worker not updating after CSS change | LOW | Bump `CACHE_VERSION` constant in `sw.js` and redeploy; drivers must manually clear PWA cache or reinstall if service worker update is not picked up within 24 hours |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Tailwind v4 CSS variable collision | UI overhaul — Tailwind installation | DevTools `:root` shows no `--color-*` naming collisions; all existing pages still render correctly before any utility classes are written |
| DaisyUI CDN missing interactive states | UI overhaul — driver PWA | All interactive components tested manually on mobile viewport; no silent CSS-only failures |
| CORS headers missing on rate limit 429 | Security hardening | Trigger 429 from browser dev console; confirm `Access-Control-Allow-Origin` present in response headers |
| Rate limiting breaks existing tests | Security hardening | Full test suite passes in CI after adding all `@limiter.limit()` decorators |
| Removing defense-in-depth code | Code quality cleanup | Test suite passes after each individual file; security-sensitive lines have documented justification |
| Wrong depot coordinates in E2E tests | Test improvement | `assert fixture_depot.latitude == config.DEPOT_LATITUDE` added to conftest |
| Behavior vs. mock-verification tests | Test improvement | PR checklist: "Does this test fail if the function returns garbage output?" |
| Preflight CSS resets breaking layout | UI overhaul — Tailwind installation | Visual diff all 4 pages before and after adding Tailwind (before any utility classes) |
| Service worker cache staleness | UI overhaul — driver PWA | After each asset change, verify `CACHE_VERSION` bumped; install PWA on test device and confirm update received |
| Documentation missing OSRM preprocessing | Documentation | Fresh Docker setup following README alone completes successfully including routing responses |
| Dev mode unusable after security hardening | Security hardening | `ENVIRONMENT=development docker-compose up` works without `API_KEY` and `CORS_ALLOWED_ORIGINS` set |

---

## Sources

- [Tailwind CSS v4 CSS variable naming collision — tailwindlabs/tailwindcss#15754](https://github.com/tailwindlabs/tailwindcss/issues/15754)
- [Tailwind CSS v4 upgrade guide — official](https://tailwindcss.com/docs/upgrade-guide)
- [DaisyUI CDN limitations — official docs](https://daisyui.com/docs/cdn/)
- [DaisyUI v5 release notes — variant classes excluded from CDN](https://daisyui.com/docs/v5/)
- [FastAPI middleware ordering — CORS must be outermost](https://fastapi.tiangolo.com/advanced/middleware/)
- [slowapi rate limiter documentation](https://slowapi.readthedocs.io/)
- [Simon Willison — Tips for getting coding agents to write good Python tests (2026)](https://simonwillison.net/2026/Jan/26/tests/)
- [Tailwind v4 mixing v3/v4 production pitfalls](https://dev.to/wishot_cipher/the-hidden-pitfall-mixing-tailwind-css-v3-and-v4-in-production-3m4i)
- [FastAPI middleware ordering — CORS dilemma](https://medium.com/@saurabhbatham17/navigating-middleware-ordering-in-fastapi-a-cors-dilemma-8be88ab2ee7b)
- Codebase inspection: `.planning/codebase/CONCERNS.md`, `apps/kerala_delivery/dashboard/src/index.css`, `apps/kerala_delivery/dashboard/src/App.css`, `apps/kerala_delivery/api/main.py`, `tests/test_e2e_pipeline.py`

---
*Pitfalls research for: Kerala LPG delivery route optimizer — milestone improvement*
*Researched: 2026-03-01*
