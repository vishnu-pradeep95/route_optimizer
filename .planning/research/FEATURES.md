# Feature Landscape

**Domain:** Ship-Ready QA for Docker Compose Delivery App (v1.4)
**Researched:** 2026-03-08
**Confidence:** HIGH (based on existing codebase analysis + current Playwright/Docker docs)

---

## Context: What Already Exists (v1.3 Complete)

This is the v1.4 milestone on a working, deployed system. These artifacts are ALREADY SHIPPED:

- **420 pytest unit tests** with mocked services (OSRM, VROOM, Google, PostgreSQL)
- **GitHub Actions CI** — 3 jobs: pytest, dashboard TypeScript build, Docker image smoke test
- **`test-fresh-deploy.sh`** — Docker-in-Docker simulation of a new employee following DEPLOY.md (tests git repo, not dist tarball)
- **`build-dist.sh`** — creates versioned tarball with .pyc-compiled licensing module, import validation
- **Operational scripts**: `bootstrap.sh`, `install.sh`, `start.sh`, `deploy.sh`, `backup_db.sh`, `reset.sh`
- **User docs**: DEPLOY.md (office guide), CSV_FORMAT.md, LICENSING.md, README.md, SETUP.md
- **License system**: hardware-bound HMAC keys, 7-day grace period, generate/activate/validate lifecycle

**The gap for v1.4:** No automated browser-level testing exists. The CLAUDE.md E2E checklist (8 categories, 30+ checks) is performed manually via Playwright MCP during development but never encoded as repeatable tests. CI does not exercise the running application. The dist tarball is built but never verified as installable. No stop/cleanup script exists for daily end-of-shift use. License lifecycle and distribution workflow docs are scattered.

---

## Table Stakes

Features that a ship-ready QA milestone must have. Missing any of these means the product is not verifiably ready for customer delivery.

| Feature | Why Expected | Complexity | Dependencies |
|---------|-------------|------------|--------------|
| **Playwright E2E: API endpoint smoke tests** | Every API endpoint (`/health`, `/api/config`, `/api/routes`, `/api/vehicles`, etc.) needs automated verification beyond the pytest mocked tests. These test the actual running Docker stack. | Low | Docker Compose running, `@playwright/test` (already in root devDeps) |
| **Playwright E2E: Driver PWA upload-to-delivery flow** | The critical user path: CSV upload, vehicle selection, route view rendering, mark stop done/fail, all-done banner. This is the CLAUDE.md checklist (Sections 1-7) automated. If this breaks, drivers get no routes. | Med | API running, test CSV fixtures, browser automation |
| **Playwright E2E: Dashboard route display** | Office staff's primary interface. Must verify route cards render, QR sheet generates, map view loads after upload. | Med | Dashboard build, API running |
| **CI/CD pipeline fix + Playwright integration** | Existing CI runs pytest + dashboard build + Docker smoke. E2E tests must also run in CI or the test suite is decorative -- tests that do not run in CI rot within weeks. | Med-High | GitHub Actions, Playwright container image, Docker Compose service startup in CI |
| **Stop script with garbage collection** | `docker compose down` is the current end-of-day instruction (DEPLOY.md Section 3). No cleanup for dangling images, build cache, or container logs. Over months, customer laptops fill up. This is different from `reset.sh` (nuclear option) -- it is for daily use. | Low | Existing `reset.sh` as pattern reference |
| **Clean install verification from tarball** | `build-dist.sh` creates a tarball. `test-fresh-deploy.sh` exists but tests the git repo checkout, not the actual distribution tarball that customers receive. The tarball is the product -- it must be tested. | Med | `build-dist.sh`, Docker-in-Docker or clean container |
| **Production vs development environment docs** | LICENSING.md has a partial comparison table (lines 161-251). Needs consolidation into a clear section a non-developer can use to verify they are running the right configuration. Currently split across LICENSING.md and scattered DEPLOY.md references. | Low | Existing docs to consolidate |
| **Google API key troubleshooting guide** | The single most common customer support issue. Geocoding fails with `REQUEST_DENIED` or `ZERO_RESULTS`. Current error message says "contact IT" with no actionable steps. Google Cloud Console requires: project created, Geocoding API enabled, billing enabled, key unrestricted or correctly restricted. | Low | Google Cloud Console knowledge |

---

## Differentiators

Features that go beyond table stakes and make the product notably more professional or reliable. Not expected by every customer, but signal quality and reduce support burden.

| Feature | Value Proposition | Complexity | Dependencies |
|---------|-------------------|------------|--------------|
| **Playwright visual regression tests** | Catch CSS regressions in dashboard and driver PWA. Tailwind v4 prefix (`tw:`) has broken before (the v1.0 `tw-` to `tw:` migration affected 13 files). Screenshot comparison prevents silent UI degradation between releases. | Med | Playwright screenshots, baseline images, Docker for consistent rendering environment |
| **Distribution documentation (build-dist workflow)** | Developer-facing doc explaining the full build-to-deliver pipeline: build tarball, generate license, transfer to customer, verify install. Currently scattered across LICENSING.md "Building a distribution" section and build-dist.sh comments. | Low | Existing docs to consolidate |
| **License lifecycle documentation** | End-to-end journey: generate key on dev machine, deliver to customer (WhatsApp/email), customer activates, monitor grace period warnings, renew before expiry. Currently split between LICENSING.md (developer steps) and DEPLOY.md Section 6.1 (customer steps). | Low | Existing docs to consolidate |
| **CI badge on README** | Visual signal that CI is passing. Standard for any project claiming ship-readiness. Adds credibility when sharing the repo with potential customers or collaborators. | Trivial | GitHub Actions workflow name |
| **Playwright test report as CI artifact** | Upload HTML report on test failure for debugging. Playwright generates detailed HTML reports with screenshots and traces by default. Saves hours of "works on my machine" debugging. | Low | GitHub Actions artifact upload step |
| **E2E test for license validation flow** | Verify that expired/missing/invalid license keys return 503 correctly. Critical path for the revenue model -- if licensing breaks silently, the product is given away for free. | Low-Med | License generation script, test fixtures |
| **Stop script with log rotation** | Beyond garbage collection: Docker's default JSON-file logging has no size limit. On a customer laptop running for months, container logs accumulate indefinitely. Truncating or rotating logs prevents disk exhaustion. | Low | Docker log config or manual truncation |
| **Offline PWA E2E test** | Driver PWA claims offline support (service worker caches route data). Verify this actually works by intercepting network in Playwright. High-value for Kerala's spotty mobile networks. | Med-High | Playwright network mocking, service worker testing |

---

## Anti-Features

Features to explicitly NOT build in this milestone. Including them would delay ship-readiness or add complexity without proportional value.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Performance/load testing** | This is a single-laptop, 13-vehicle system processing ~50 orders/day. Load testing adds no value at this scale. The optimization runs in <15 seconds for 50 orders. | Monitor response times in E2E tests as sanity checks (assert < 30s). |
| **Multi-browser E2E testing** | Drivers use Chrome on Android. Dashboard users use Chrome on Windows. Safari/Firefox coverage adds CI time (3x) without matching real-world usage. | Run Playwright in Chromium only. Add webkit project later if a customer reports Safari issues. |
| **Automated accessibility testing (axe-core)** | WCAG AAA contrast is already validated by design (v1.1). axe-core integration is valuable but is a maintenance-phase activity, not a ship-ready gate. | Keep WCAG AAA contrast ratios in the design tokens. Accessibility audit in a future milestone. |
| **Docker image size optimization** | Multi-stage builds, Alpine base images, etc. The customer laptop has 256+ GB SSD. Current images work. Image size is not a deployment blocker. | Keep the current Debian-based images. Optimize only if a customer reports disk pressure. |
| **Automated dependency updates (Dependabot/Renovate)** | Adds PR noise to a solo-dev project. Dependencies are pinned for stability (OSRM v5.27.1, VROOM v1.14.0-rc.2). Automated updates risk breaking the stack. | Manual quarterly dependency review. |
| **Test coverage metrics (codecov/coveralls)** | 420 pytest tests exist. Chasing coverage percentages does not find bugs -- E2E tests that exercise real user flows do. Coverage tooling adds CI time and configuration overhead. | Focus on E2E flow coverage (critical paths tested), not line coverage. |
| **Canary/blue-green deployment** | Single-laptop deployment. There is no staging environment and no traffic to canary. The deployment model is "stop, update, start." | The `test-fresh-deploy.sh` IS the pre-deployment verification. Clean install verification from tarball extends this. |
| **Automated rollback on deploy failure** | `deploy.sh` already creates a pre-deploy database backup. Automated rollback for a single-laptop system adds complexity for a failure mode that has never occurred. | Keep manual rollback instructions in deploy.sh comments. |

---

## Feature Dependencies

```
Playwright config (playwright.config.ts) [prerequisite for all E2E]
  |
  +-> Playwright E2E: API smoke tests [no browser needed, fastest]
  |     |
  |     +-> Playwright E2E: Driver PWA flow [needs API, needs browser]
  |     |
  |     +-> Playwright E2E: Dashboard flow [needs API, needs browser]
  |
  +-> CI/CD pipeline fix [needs working CI before adding E2E jobs]
        |
        +-> Playwright in CI [needs CI fix, then add E2E job]
              |
              +-> Playwright report artifact [upload on E2E failure]

build-dist.sh (exists)
  |
  +-> Clean install verification from tarball [tests the dist output]
  |
  +-> Distribution documentation [documents the build-to-deliver workflow]

License generation (exists) + LICENSING.md (exists) + DEPLOY.md 6.1 (exists)
  |
  +-> License lifecycle docs [consolidates scattered info]

Google API key troubleshooting [standalone, no dependencies]

Stop script with GC [standalone, references docker compose commands]

Prod vs dev docs [standalone, references existing LICENSING.md]
```

---

## MVP Recommendation

### Phase 1: Test Infrastructure (do first -- gates everything else)

| # | Feature | Effort | Rationale |
|---|---------|--------|-----------|
| 1 | **Playwright config + API smoke tests** | 2-3h | Create `playwright.config.ts`, write 5-8 API test cases using Playwright's `request` API (no browser). Validates test infrastructure works before investing in browser tests. |
| 2 | **Playwright E2E: Driver PWA upload-to-delivery flow** | 4-6h | Highest-value user path. Upload CSV, select vehicle, verify route view, mark stop done, verify all-done banner. This is the CLAUDE.md E2E checklist (Sections 1-7) automated. |
| 3 | **Playwright E2E: Dashboard route display** | 3-4h | Second user path. Upload, verify route cards, QR sheet generation, map view. Simpler interactions than PWA. |
| 4 | **CI/CD pipeline fix + Playwright in CI** | 3-4h | Add 4th CI job: start Docker Compose on runner, install Playwright browsers, run E2E tests, upload report artifact on failure. Without this, E2E tests rot. |

### Phase 2: Distribution Verification (do second)

| # | Feature | Effort | Rationale |
|---|---------|--------|-----------|
| 5 | **Clean install verification from tarball** | 2-3h | Extend or create script to: `build-dist.sh v1.4` -> extract tarball in clean container -> run install.sh -> health check -> verify API + PWA + dashboard serve. Tests the product customers receive. |
| 6 | **Stop script with garbage collection** | 1-2h | Simple script: `docker compose down` (keep volumes), prune dangling images, truncate logs, print disk space freed. High customer value, low effort. |

### Phase 3: Documentation (do third)

| # | Feature | Effort | Rationale |
|---|---------|--------|-----------|
| 7 | **Google API key troubleshooting guide** | 1-2h | Standalone. High customer support value. Covers: create project, enable Geocoding API, enable billing, check key restrictions, test with curl. Decision tree format. |
| 8 | **Distribution documentation** | 1-2h | Developer-facing. Consolidates build-dist.sh workflow, tarball contents, what is excluded and why, customer delivery checklist. |
| 9 | **License lifecycle documentation** | 1-2h | End-to-end journey consolidation. Currently split across LICENSING.md and DEPLOY.md 6.1. Single coherent narrative: generate -> deliver -> activate -> monitor -> renew -> troubleshoot. |
| 10 | **Prod vs dev environment docs** | 0.5-1h | Extend LICENSING.md "Dev vs Production" table or create standalone section. Focus: how a non-developer verifies they are in the right environment. |

### Defer to v1.5+

- **Visual regression tests** -- valuable but requires baseline image management infrastructure. Better after core E2E suite is stable and proven.
- **Offline PWA E2E test** -- complex (service worker testing in Playwright requires network interception patterns). Better after core E2E suite covers the happy path.
- **License validation E2E test** -- nice to have, but license logic is covered by pytest unit tests. Add after core E2E flows are solid.
- **CI badge on README** -- trivial, can be added anytime.

---

## Key Technical Decisions for Features

### Playwright Test Architecture

The project already has `@playwright/test ^1.58.2` in root `package.json` devDependencies. No `playwright.config.ts` exists yet.

**Recommended test structure:**
```
tests/e2e/
  playwright.config.ts     # Config: baseURL, webServer or reuseExistingServer
  api.spec.ts              # API endpoint smoke tests (Playwright request API, no browser)
  driver-pwa.spec.ts       # Full driver flow (browser automation)
  dashboard.spec.ts        # Dashboard route display (browser automation)
  fixtures/
    test-orders.csv        # Known-good CSV with 5 orders for upload tests
```

**Service startup approach:** Two options exist:
- **Option A (webServer):** Playwright launches `docker compose up -d` before tests, polls `/health`, runs tests, then `docker compose down`. Simpler config but Playwright manages Docker lifecycle.
- **Option B (external services):** Expect services already running. Set `reuseExistingServer: true` locally. In CI, a separate step starts Docker Compose.

**Recommendation: Option B.** Start services in a separate CI step (or manually for local dev). Playwright tests just connect to `http://localhost:8000`. This matches the existing `test-fresh-deploy.sh` pattern, avoids Playwright managing Docker lifecycle, and is simpler to debug when services fail to start (CI logs show Docker Compose output separately from test output).

### CI/CD Architecture for E2E

Current CI has 3 jobs. Adding Playwright E2E as a 4th job.

**Key constraint:** Playwright E2E needs Docker Compose services running. Two approaches:
- **Docker-in-Docker:** Complex, slow, fragile. Not recommended.
- **Direct on runner:** GitHub Actions ubuntu-latest has Docker pre-installed. Run `docker compose up -d` directly, wait for health, run Playwright. Simple and proven.

**Recommendation:** Direct on runner.
```yaml
e2e:
  name: E2E Tests
  runs-on: ubuntu-latest
  steps:
    - checkout
    - docker compose up -d
    - wait for health (curl loop)
    - setup Node + npm ci
    - npx playwright install --with-deps chromium
    - npx playwright test
    - upload playwright-report/ as artifact (always, for debugging)
    - docker compose down
```

**CI cost consideration:** The existing 3 jobs run in ~2-3 minutes. E2E with Docker Compose startup adds ~5-8 minutes. Total ~8-11 minutes, well within GitHub Actions free tier (2,000 min/month for private repos).

### Stop Script vs Reset Script

`reset.sh` exists with comprehensive cleanup (6 steps, interactive/all/dry-run modes). The stop script is fundamentally different:

| Aspect | `stop.sh` (new) | `reset.sh` (existing) |
|--------|-----------------|----------------------|
| Purpose | End-of-shift shutdown | Nuclear reset for troubleshooting |
| Frequency | Daily | Rarely (troubleshooting only) |
| Database | Preserved | Optionally destroyed |
| OSRM data | Preserved | Optionally destroyed |
| Docker images | Dangling pruned | All removed |
| Container logs | Truncated | N/A |
| User prompt | None (safe by default) | Interactive or `--all` confirmation |

### Clean Install Verification Scope

`test-fresh-deploy.sh` tests: git repo -> install.sh -> health check -> endpoint verification.
The new tarball verification tests: build-dist.sh -> extract tarball -> install.sh -> health check -> endpoint verification.

**Key difference:** The tarball has no `.git/`, no `tests/`, no `generate_license.py`, and licensing is `.pyc`-only. The test must verify that the tarball works without these files.

---

## Complexity Estimates Summary

| Feature | Estimated Effort | Risk |
|---------|-----------------|------|
| Playwright config + API smoke tests | 2-3 hours | Low -- well-documented, no browser needed |
| Driver PWA E2E flow | 4-6 hours | Medium -- file upload automation, multi-step flow, modal interaction |
| Dashboard E2E flow | 3-4 hours | Medium -- route card rendering depends on upload completing first |
| CI/CD pipeline fix + Playwright | 3-4 hours | Medium -- Docker Compose in CI has startup timing concerns |
| Clean install verification | 2-3 hours | Medium -- Docker-in-Docker or clean container approach |
| Stop script with GC | 1-2 hours | Low -- straightforward shell script |
| Google API key troubleshooting | 1-2 hours | Low -- documentation only |
| Distribution documentation | 1-2 hours | Low -- consolidating existing info |
| License lifecycle docs | 1-2 hours | Low -- consolidating existing info |
| Prod vs dev docs | 0.5-1 hour | Low -- extending existing table |

**Total estimated effort:** 20-30 hours (3-5 focused days)

---

## Customer Delivery Checklist (informing distribution docs)

Based on the existing build-dist.sh workflow and LICENSING.md, the full customer delivery pipeline is:

1. **Build:** `./scripts/build-dist.sh v1.4` -- creates `dist/kerala-delivery-v1.4.tar.gz`
2. **Verify build:** Run clean install verification script on the tarball
3. **Generate license:** Get customer's machine fingerprint, run `generate_license.py`
4. **Package delivery:** tarball + license key string + DEPLOY.md quick reference card
5. **Customer installs:** Extract tarball, run `bootstrap.sh`, enter Google API key when prompted
6. **Customer activates license:** Run `get_machine_id.py`, send fingerprint, receive and save key
7. **Verify installation:** Customer runs `start.sh`, opens dashboard, uploads test CSV
8. **Go live:** Customer uploads real CDCMS export, prints QR codes for drivers

This checklist should be the backbone of the distribution documentation.

---

## Sources

- [Playwright CI Documentation](https://playwright.dev/docs/ci) -- HIGH confidence
- [Playwright webServer Configuration](https://playwright.dev/docs/test-webserver) -- HIGH confidence
- [Playwright Docker Documentation](https://playwright.dev/docs/docker) -- HIGH confidence
- [BrowserStack: E2E Testing with Playwright and Docker](https://www.browserstack.com/guide/playwright-docker) -- MEDIUM confidence
- [BrowserStack: 15 Playwright Best Practices 2026](https://www.browserstack.com/guide/playwright-best-practices) -- MEDIUM confidence
- [Docker Compose stop docs](https://docs.docker.com/reference/cli/docker/compose/stop/) -- HIGH confidence
- [Docker stop_grace_period](https://oneuptime.com/blog/post/2026-02-08-how-to-use-docker-compose-stopgraceperiod-setting/view) -- MEDIUM confidence
- [Google Maps API Error Messages](https://developers.google.com/maps/documentation/maps-static/error-messages) -- HIGH confidence
- [Google Maps API Troubleshooting](https://developers.google.com/maps/documentation/javascript/troubleshooting) -- HIGH confidence
- [Scalable Integration Testing with Playwright, Docker, and GitHub Actions](https://arthiyadevi.medium.com/scalable-integration-testing-with-playwright-docker-and-github-actions-3712b5c12eee) -- MEDIUM confidence
- [Elevate Your CI/CD: Dockerized E2E Tests with GitHub Actions](https://lachiejames.com/elevate-your-ci-cd-dockerized-e2e-tests-with-github-actions/) -- MEDIUM confidence
- Existing codebase: `.github/workflows/ci.yml`, `tests/deploy/test-fresh-deploy.sh`, `scripts/build-dist.sh`, `scripts/reset.sh`, `scripts/start.sh`, `DEPLOY.md`, `LICENSING.md` -- HIGH confidence (primary source)

---

*Feature research for: Kerala LPG Delivery Route Optimizer v1.4 -- Ship-Ready QA*
*Researched: 2026-03-08*
