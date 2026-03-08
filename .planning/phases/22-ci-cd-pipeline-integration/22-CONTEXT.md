# Phase 22: CI/CD Pipeline Integration - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

E2E tests run automatically on every push to main via GitHub Actions, with clear failure diagnostics and visible project health status. Fix all existing CI failures so the pipeline passes green. Add Playwright E2E job, failure artifacts, and CI badge to README.

</domain>

<decisions>
## Implementation Decisions

### CI secrets & environment
- API_KEY stored as a GitHub Actions secret (repo is private, no fork concerns)
- Google Maps API key omitted entirely — tests use pre-geocoded CSV, no geocoding calls needed
- License tests included in CI — spin up license-test container via docker-compose.license-test.yml alongside main stack
- ENVIRONMENT=development for the main API container in CI

### Failure artifacts
- Upload full `playwright-report/` directory (HTML report + embedded traces + screenshots) as a single artifact
- Also capture Docker container logs (`docker compose logs`) as a separate artifact on failure — critical for diagnosing API-side vs test-side issues
- Upload only on failure (`if: failure()`)
- 7-day artifact retention period

### Existing CI job fixes
- Fix all 64 pre-existing pytest failures (SQLAlchemy async/greenlet issues, DB-dependent tests) — do not use xfail markers or skip
- Update CI YAML comments to reflect actual test counts (was "211+", now 420+)
- CI badge placed at top of README.md, immediately after the title

### Test project scope
- All 4 Playwright projects run in CI: api, driver-pwa, dashboard, license
- Docker Compose stack without OSRM/VROOM (per success criteria)
- `--workers=1` (already in playwright.config.ts)
- Chromium-only (Playwright default)

### Claude's Discretion
- Docker Compose service subset configuration for CI (which services to include/exclude)
- Health check wait strategy before running tests
- How to fix the 64 pytest failures (mock strategy, async fixes, etc.)
- CI job ordering and dependency chain
- Whether E2E job runs on PRs or only push to main

</decisions>

<specifics>
## Specific Ideas

- Success criteria specifies "without OSRM/VROOM" — API must handle missing route optimization services gracefully in CI
- Sequential story pattern means test order matters — `workers: 1` and `fullyParallel: false` already configured
- License tests need the separate docker-compose.license-test.yml override container on port 8001

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.github/workflows/ci.yml` — existing 3-job CI (Python Tests, Dashboard Build, Docker Build)
- `playwright.config.ts` — fully configured with 4 projects, CI-aware settings (forbidOnly, retries)
- `docker-compose.yml` — main stack definition
- `docker-compose.license-test.yml` — production-mode API on port 8001 for license tests
- `e2e/` directory with 38 passing tests across 4 spec files

### Established Patterns
- CI uses `actions/checkout@v4`, `actions/setup-python@v5`, `actions/setup-node@v4`
- Concurrency group with cancel-in-progress for same-branch runs
- Docker build job only runs on push (not PRs)
- pytest runs with `RATE_LIMIT_ENABLED=false` and dummy `DATABASE_URL`

### Integration Points
- `.github/workflows/ci.yml` — add E2E job, fix pytest job
- `README.md` — add CI badge after title
- `playwright.config.ts` — already CI-aware (forbidOnly in CI, retries in CI)
- `package.json` — has Playwright dependency at project root
- Docker Compose stack needs to start in CI for E2E tests

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 22-ci-cd-pipeline-integration*
*Context gathered: 2026-03-08*
