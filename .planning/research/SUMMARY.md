# Project Research Summary

**Project:** Kerala LPG Delivery Route Optimizer -- v1.4 Ship-Ready QA
**Domain:** E2E testing infrastructure, CI/CD integration, distribution verification, operational scripts for Docker Compose delivery app
**Researched:** 2026-03-08
**Confidence:** HIGH

## Executive Summary

v1.4 is a QA and distribution-readiness milestone on a mature, working product (v1.3 shipped with 420+ pytest tests, Docker Compose orchestration, and full deployment scripts). The core gap is that no automated browser-level testing exists -- the 30+ item CLAUDE.md E2E checklist is performed manually via Playwright MCP but never encoded as repeatable tests. CI does not exercise the running application. The distribution tarball is built but never verified as installable on a fresh machine. No graceful stop script exists for daily end-of-shift use. All four research streams converge on a clear conclusion: the existing stack (Playwright already installed, Docker Compose already working, bash script conventions already established) needs configuration and test authoring, not new technology adoption.

The recommended approach is a four-phase build: (1) Playwright test infrastructure and first tests against the running Docker stack, (2) CI integration with the E2E job, (3) distribution verification and the stop/GC script, (4) documentation consolidation. This ordering is driven by dependency analysis -- Playwright config gates all E2E work, local test stability gates CI integration, and distribution verification gates customer delivery. The total estimated effort is 20-30 hours across all phases.

The top risks are: Docker Compose service startup race conditions causing flaky tests in CI (solved by explicit health polling, not Playwright webServer); .pyc magic number mismatch between the developer's Python and the Docker image's Python (solved by compiling inside Docker); and the stop script accidentally destroying the production database volume (solved by using `docker compose stop` not `down -v`, and keeping volume cleanup exclusively in the existing `reset.sh`). All three risks have straightforward prevention strategies identified in the pitfalls research.

## Key Findings

### Recommended Stack

No new technologies are required. Playwright `@playwright/test` v1.58.2 is already installed as a devDependency. The stack additions are configuration files and scripts using existing tools. See `.planning/research/STACK.md` for full details.

**Core technologies:**
- **Playwright 1.58.2 (already installed):** E2E test framework -- `playwright.config.ts` must be created at project root, Chromium-only in CI (drivers and office staff both use Chrome)
- **GitHub Actions `ubuntu-latest` runner:** CI host for E2E -- install Playwright browsers directly on runner (not Docker-in-Docker) because the app itself IS a Docker Compose stack
- **Built-in `github` + `html` reporters:** CI test reporting -- PR failure annotations + HTML artifact for debugging, no third-party reporter packages
- **Bash 5.x (existing conventions):** Stop/GC script and verification scripts -- matches `set -euo pipefail`, color helpers, `header()`/`info()`/`success()`/`error()` function pattern from existing scripts
- **ShellCheck (pre-installed on CI runners):** Shell script linting -- catches quoting bugs and unbound variables in all `scripts/*.sh` files

**What NOT to add:** Cypress, Testcontainers, `@estruyf/github-actions-reporter`, `docker-compose-wait`, visual regression baselines, multi-browser testing. All were evaluated and rejected -- see STACK.md "What NOT to Add" section.

### Expected Features

See `.planning/research/FEATURES.md` for full analysis including effort estimates and dependency graph.

**Must have (table stakes):**
- Playwright E2E: API endpoint smoke tests (5-8 tests, no browser needed)
- Playwright E2E: Driver PWA upload-to-delivery flow (the critical user path)
- Playwright E2E: Dashboard route display and QR sheet generation
- CI/CD pipeline with Playwright job (without this, E2E tests rot within weeks)
- Stop script with garbage collection (daily end-of-shift use, separate from `reset.sh`)
- Clean install verification from tarball (tests the product customers actually receive)
- Google API key troubleshooting guide (single most common support issue)
- Production vs development environment documentation

**Should have (differentiators):**
- Playwright test report as CI artifact (saves hours of "works on my machine" debugging)
- Distribution documentation (build-to-deliver pipeline consolidated)
- License lifecycle documentation (generate, deliver, activate, renew, troubleshoot)
- CI badge on README
- Stop script with log rotation/truncation

**Defer (v1.5+):**
- Visual regression tests (requires baseline image management)
- Offline PWA E2E test (complex service worker testing)
- License validation E2E test (covered by existing pytest unit tests)
- Performance/load testing (irrelevant at 50 orders/day scale)
- Multi-browser testing (irrelevant -- all users on Chrome)

### Architecture Approach

The architecture adds a Playwright test layer on top of the existing Docker Compose stack with no modifications to existing components. Tests run against `http://localhost:8000` where Docker Compose exposes ports. A Page Object Model pattern encapsulates UI selectors so tests remain stable when the UI changes (as it did in v1.1, v1.2). The stop script is the safe counterpart to `start.sh` -- it halts containers but preserves all data volumes. See `.planning/research/ARCHITECTURE.md` for full component diagrams and data flow.

**Major components:**
1. **`playwright.config.ts`** -- Test runner configuration (baseURL, Chromium-only, CI-aware retries/reporters)
2. **`e2e/` directory** -- Test specs, Page Object Models, fixtures, and helpers (separated from Python `tests/` to avoid pytest/Playwright discovery conflicts)
3. **`e2e/pages/*.page.ts`** -- Page Object Models for Driver PWA, Upload flow, and Dashboard (encapsulate selectors, expose high-level actions like `uploadCSV()`, `markStopDone()`)
4. **CI `e2e` job** -- 4th GitHub Actions job: start Docker Compose on runner, install Chromium, run tests, upload artifacts, teardown
5. **`scripts/stop.sh`** -- Graceful shutdown (`docker compose stop`) with optional `--gc` flag for image/cache pruning; NEVER touches named volumes

**Key architectural decisions:**
- Docker Compose managed externally (not via Playwright `webServer`) -- avoids port-open-before-service-ready race condition
- OSRM/VROOM skipped in CI -- too slow to download/preprocess; UI rendering and API contract tests do not need the optimization engine
- Database state reset via `beforeAll` hooks or test-only reset endpoint -- prevents order-dependent test failures
- E2E tests use pre-geocoded/seeded data -- avoids dependency on Google Maps API key in CI

### Critical Pitfalls

See `.planning/research/PITFALLS.md` for all 10 pitfalls with detailed prevention strategies.

1. **Service startup race condition** -- Docker opens ports before the app is ready; Playwright detects the port and starts tests prematurely. Prevention: use `globalSetup` with `/health` endpoint polling (not `webServer` config). Verification: tests pass on cold start `docker compose down && npx playwright test`.

2. **CI resource constraints causing flaky tests** -- GitHub Actions shared runners have 2 vCPUs / 7 GB RAM running 4 Docker containers + Chromium simultaneously. Prevention: `--workers=1`, `retries: 2` in CI, `trace: 'on-first-retry'`, upload artifacts for debugging.

3. **.pyc magic number mismatch in distribution tarball** -- `build-dist.sh` compiles `.pyc` with local Python; Docker image may use a different patch version. Prevention: compile .pyc inside Docker (`docker run --rm -v ... python:3.12-slim python -m compileall`), or pin Docker image to exact patch version.

4. **Stop script destroys production database** -- `docker compose down -v` removes named volumes including `pgdata`. Prevention: use `docker compose stop` (not `down -v`); keep volume cleanup exclusively in `reset.sh` with confirmation prompts.

5. **E2E tests leak state between runs** -- Tests upload CSVs and create routes; next test finds stale data. Prevention: database reset in `beforeAll` hooks or test-only `/api/test/reset` endpoint (guarded by `ENVIRONMENT=test`).

6. **Google Maps API key missing in CI** -- Upload flow requires geocoding which fails without API key. Prevention: seed database with pre-geocoded addresses; E2E tests must pass with no `GOOGLE_MAPS_API_KEY` set.

7. **Tarball missing critical files** -- `rsync --exclude` overshoot silently drops required files. Prevention: manifest verification step in `build-dist.sh` that checks for 15+ required files after staging.

## Implications for Roadmap

Based on combined research, the suggested structure is 4 phases with a clear dependency chain.

### Phase 1: Playwright Test Infrastructure + First Tests
**Rationale:** Everything else depends on this. Playwright config must exist before any test runs. The API smoke tests validate that the test infrastructure works before investing in browser tests. The Driver PWA flow is the highest-value user path and the most complex to automate.
**Delivers:** `playwright.config.ts`, `e2e/` directory structure, Page Object Models, API smoke tests (5-8 tests), Driver PWA E2E flow, Dashboard E2E flow
**Addresses:** Table stakes features -- Playwright E2E (API, Driver PWA, Dashboard)
**Avoids:** Pitfall 1 (startup race -- configure globalSetup with health polling from day one), Pitfall 6 (Google API key -- establish seeding/mocking strategy before writing upload tests), Pitfall 10 (state leakage -- build database reset into fixture setup from the start)
**Estimated effort:** 10-14 hours
**Build order within phase:** config + API smoke tests first (validate infrastructure), then Page Object Models, then Driver PWA spec, then Dashboard spec

### Phase 2: CI/CD Pipeline Integration
**Rationale:** Tests that do not run in CI rot within weeks. This phase takes locally-passing tests and makes them reliable in GitHub Actions. Must come after Phase 1 (need passing tests before adding CI complexity).
**Delivers:** 4th CI job (`e2e`), ShellCheck lint job, Playwright browser caching, artifact upload on failure, `package.json` script updates
**Addresses:** Table stakes feature -- CI/CD pipeline fix and Playwright integration
**Avoids:** Pitfall 2 (CI flakiness -- configure `--workers=1`, increased timeouts, trace artifacts), Pitfall 6 (no API key in CI -- tests already use seeded data from Phase 1)
**Estimated effort:** 3-4 hours
**Key constraint:** OSRM/VROOM not started in CI. Only `db`, `db-init`, `dashboard-build`, `api` services. Tests focus on UI rendering and API contracts.

### Phase 3: Distribution Verification + Operational Scripts
**Rationale:** Before declaring the product ship-ready, verify that the actual customer deliverable (tarball) works on a fresh machine. The stop script is operationally independent but belongs in this phase because it rounds out the deployment lifecycle (bootstrap -> install -> start -> stop). The .pyc compilation fix must land before building any customer tarballs.
**Delivers:** Tarball manifest verification in `build-dist.sh`, clean install verification script, `scripts/stop.sh` with `--gc` flag, `stop_grace_period: 30s` for PostgreSQL in `docker-compose.yml`
**Addresses:** Table stakes features -- clean install verification, stop script with GC
**Avoids:** Pitfall 3 (.pyc mismatch -- fix compilation to use Docker), Pitfall 4 (stop script data loss -- use `docker compose stop`, never `-v`), Pitfall 5 (cached state masking fresh-install problems -- test on fresh WSL instance), Pitfall 8 (tarball missing files -- add manifest verification), Pitfall 9 (PostgreSQL unclean shutdown -- set grace period)
**Estimated effort:** 4-6 hours

### Phase 4: Documentation Consolidation
**Rationale:** Documentation has no technical dependencies and can proceed in parallel with other work, but is listed last because it benefits from having the verified tooling (E2E tests, CI, stop script, tarball verification) in place -- docs can reference actual commands and workflows. Write customer-facing docs first, developer docs second.
**Delivers:** Google API key troubleshooting guide (decision tree format), distribution documentation (build-to-deliver pipeline), license lifecycle documentation (customer-facing + developer reference), production vs development environment docs
**Addresses:** Table stakes features -- Google API troubleshooting, prod vs dev docs; differentiator features -- distribution docs, license lifecycle docs
**Avoids:** Pitfall 7 (technical docs for non-technical readers -- write customer-facing version first with plain-English error explanations and "contact support" procedures)
**Estimated effort:** 4-6 hours

### Phase Ordering Rationale

- **Dependency chain:** Config -> tests -> CI -> distribution -> docs. Each phase builds on the previous one. You cannot add tests to CI before they pass locally. You cannot verify distribution before fixing .pyc compilation.
- **Risk-first:** Phase 1 addresses the three highest-complexity pitfalls (startup race, state leakage, API key mocking). Getting these right early prevents cascading failures in later phases.
- **Value delivery:** Phase 1 alone delivers the highest-value outcome (automated E2E tests for the critical user paths). If the milestone is time-constrained, Phase 1 is the minimum viable delivery.
- **Architecture grouping:** Phases group naturally by component boundary -- Phase 1 is all Playwright, Phase 2 is all CI YAML, Phase 3 is all bash scripts, Phase 4 is all markdown.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1:** The database state reset strategy (test-only API endpoint vs SQL truncation vs transaction rollback) needs a concrete decision during phase planning. The seeded-data approach for bypassing Google Geocoding also needs the specific seed data defined.
- **Phase 2:** OSRM data caching in CI (GitHub Actions cache for `data/osrm/`) is a future optimization that may need research if full-stack E2E is desired later.

Phases with standard patterns (skip research-phase):
- **Phase 3:** Stop script and tarball verification are straightforward bash scripting following established project conventions. All Docker commands are documented. No research needed.
- **Phase 4:** Documentation consolidation is reorganizing existing content. No research needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All tools already installed or pre-available. Playwright 1.58.2 is pinned. No new dependencies. Verified against official Playwright CI docs, Docker docs. |
| Features | HIGH | Feature list derived from existing CLAUDE.md E2E checklist and codebase analysis. Effort estimates based on comparable Playwright projects. Clear table stakes vs differentiator separation. |
| Architecture | HIGH | Architecture adds a test layer on top of an existing, stable system. Page Object Model and CI patterns are well-documented Playwright conventions. No novel architectural decisions. |
| Pitfalls | HIGH | All 10 pitfalls verified against official documentation (Playwright CI docs, Docker signal handling docs, CPython .pyc specs). Race condition and .pyc mismatch pitfalls confirmed by GitHub issue trackers and community reports. |

**Overall confidence:** HIGH

This is a well-scoped QA milestone on a mature codebase with no technology unknowns. The existing Playwright installation, Docker Compose stack, and bash script conventions provide a solid foundation. Every recommendation uses tools already available in the project.

### Gaps to Address

- **Database state reset strategy:** Research identifies three options (test-only API endpoint, SQL truncation in beforeAll, transaction rollback) but does not prescribe which one. Decision needed during Phase 1 planning based on API framework capabilities.
- **Seeded test data for geocoding bypass:** The specific CSV fixture and pre-geocoded database records need to be defined. Should use addresses from the existing test fixtures or synthetic Kerala addresses that are already in the geocode cache.
- **OSRM in CI (future):** If full optimization-flow E2E tests are ever desired in CI, the OSRM data download (~150 MB) and preprocessing need a caching strategy. Not needed for v1.4 but flagged for future milestones.
- **Physical Android device testing:** Listed as tech debt in PROJECT.md. E2E tests run in desktop Chromium, not on a real Android phone. Outdoor contrast and touch target sizes cannot be verified by Playwright. This remains a manual verification gap.

## Sources

### Primary (HIGH confidence)
- [Playwright CI documentation](https://playwright.dev/docs/ci) -- GitHub Actions setup, Docker image recommendations, caching
- [Playwright CI intro](https://playwright.dev/docs/ci-intro) -- Recommended YAML, `--with-deps` flag, artifact upload
- [Playwright Docker documentation](https://playwright.dev/docs/docker) -- Official images, version pinning, `--ipc=host`
- [Playwright test configuration](https://playwright.dev/docs/test-configuration) -- `defineConfig`, `webServer`, `projects`, `reporter`
- [Playwright webServer documentation](https://playwright.dev/docs/test-webserver) -- `command`, `url`, `reuseExistingServer`
- [Playwright Page Object Models](https://playwright.dev/docs/pom) -- Official POM pattern
- [Playwright test reporters](https://playwright.dev/docs/test-reporters) -- Built-in reporters
- [Docker Compose stop documentation](https://docs.docker.com/reference/cli/docker/compose/stop/) -- SIGTERM, grace period, SIGKILL
- [Docker Compose down documentation](https://docs.docker.com/reference/cli/docker/compose/down/) -- `-v` flag behavior
- [PEP 3147](https://peps.python.org/pep-3147/) -- .pyc magic numbers, version-specific caching
- [Google Maps Error Messages](https://developers.google.com/maps/documentation/javascript/error-messages) -- REQUEST_DENIED causes
- Existing codebase: `ci.yml`, `docker-compose.yml`, `package.json`, `scripts/`, `tests/`, `build-dist.sh`, `DEPLOY.md`, `LICENSING.md`

### Secondary (MEDIUM confidence)
- [BrowserStack: Playwright Best Practices 2026](https://www.browserstack.com/guide/playwright-best-practices)
- [Better Stack: Avoid Flaky Playwright Tests](https://betterstack.com/community/guides/testing/avoid-flaky-playwright-tests/)
- [Dockerized E2E Tests with GitHub Actions](https://lachiejames.com/elevate-your-ci-cd-dockerized-e2e-tests-with-github-actions/)
- [Playwright webServer race condition with Docker Compose](https://github.com/sillsdev/web-languageforge/issues/1402)
- [Docker Graceful Shutdown Signals](https://oneuptime.com/blog/post/2026-01-16-docker-graceful-shutdown-signals/view)

---
*Research completed: 2026-03-08*
*Ready for roadmap: yes*
