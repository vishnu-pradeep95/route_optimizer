# Phase 22: CI/CD Pipeline Integration - Research

**Researched:** 2026-03-08
**Domain:** GitHub Actions CI, Docker Compose in CI, Playwright E2E in CI, pytest async fixes
**Confidence:** HIGH

## Summary

Phase 22 requires four deliverables: (1) fix all existing CI failures (64 pytest failures), (2) add a Playwright E2E job to GitHub Actions, (3) upload Playwright HTML reports as artifacts on failure, and (4) add a CI status badge to README.md. The project already has a well-structured CI workflow (`.github/workflows/ci.yml`) with three jobs (Python Tests, Dashboard Build, Docker Build) and a complete Playwright test suite (38 tests across 4 projects) that passes locally.

The most significant technical challenge is the constraint conflict between the success criteria ("without OSRM/VROOM") and the E2E tests' requirement for OSRM+VROOM. All four Playwright projects (api, driver-pwa, dashboard, license) call `uploadTestCSV()` in their `beforeAll` hooks, which triggers the full upload-optimize pipeline including VROOM HTTP calls to `http://localhost:3000`. Without VROOM (which requires OSRM), these tests will fail with connection errors. The OSRM init container downloads ~150 MB of Kerala map data -- impractical for CI. This constraint must be resolved: either include OSRM+VROOM in CI (accepting the download overhead or caching the data), or modify tests to not require optimization.

The pytest fixes involve 64 pre-existing failures related to SQLAlchemy async/greenlet issues and DB-dependent tests that run without a real PostgreSQL connection. The fix strategy is to properly mock async sessions and repository functions, or use `pytest-asyncio` correctly where async test patterns are broken.

**Primary recommendation:** Include OSRM+VROOM in the CI Docker Compose stack (cache OSRM data as a GitHub Actions cache artifact to avoid re-downloading on every run), fix the 64 pytest failures with proper async mocking, and add the E2E job as a fourth CI job that depends on the Docker Build job.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- API_KEY stored as a GitHub Actions secret (repo is private, no fork concerns)
- Google Maps API key omitted entirely -- tests use pre-geocoded CSV, no geocoding calls needed
- License tests included in CI -- spin up license-test container via docker-compose.license-test.yml alongside main stack
- ENVIRONMENT=development for the main API container in CI
- Upload full `playwright-report/` directory (HTML report + embedded traces + screenshots) as a single artifact
- Also capture Docker container logs (`docker compose logs`) as a separate artifact on failure
- Upload only on failure (`if: failure()`)
- 7-day artifact retention period
- Fix all 64 pre-existing pytest failures (SQLAlchemy async/greenlet issues, DB-dependent tests) -- do not use xfail markers or skip
- Update CI YAML comments to reflect actual test counts (was "211+", now 420+)
- CI badge placed at top of README.md, immediately after the title
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

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CICD-01 | GitHub Actions pipeline passes (fix any failing jobs) | Pytest fix strategy (Section: Fixing 64 Pytest Failures), CI YAML updates |
| CICD-02 | Playwright E2E job added to CI (Chromium-only, runs on push to main) | E2E job architecture, Docker Compose CI strategy, Playwright install pattern |
| CICD-03 | Playwright HTML report uploaded as CI artifact on failure | Artifact upload pattern with `actions/upload-artifact@v4`, failure condition |
| CICD-04 | CI status badge added to README.md | Badge markdown format for GitHub Actions |
</phase_requirements>

## Standard Stack

### Core (Already in Project)
| Library/Tool | Version | Purpose | Why Standard |
|--------------|---------|---------|--------------|
| GitHub Actions | ubuntu-latest | CI runner | Pre-installed Docker Engine v29.1 + Compose v2.40 |
| Playwright | ^1.58.2 | E2E tests | Already configured in `package.json` and `playwright.config.ts` |
| pytest | 9.0.2 | Python unit tests | Already in `requirements.txt` |
| Docker Compose | v2.40+ (pre-installed) | Stack orchestration in CI | Built-in `--wait` flag for health check readiness |

### GitHub Actions (Existing in CI)
| Action | Version | Purpose |
|--------|---------|---------|
| `actions/checkout` | v4 | Repository checkout (existing pattern) |
| `actions/setup-python` | v5 | Python 3.12 setup with pip cache |
| `actions/setup-node` | v4 | Node.js 22 setup with npm cache |
| `actions/upload-artifact` | v4 | Playwright report + Docker logs upload |

### Why Keep Existing Action Versions
The CI already uses `actions/checkout@v4`, `actions/setup-python@v5`, `actions/setup-node@v4`. While v5/v6 of checkout and upload-artifact exist, upgrading adds no value for this phase and risks introducing subtle runner compatibility issues. Stay with existing versions for the new E2E job.

## Architecture Patterns

### Recommended CI Job Structure

```
┌──────────────────┐  ┌────────────────────┐  ┌──────────────────┐
│  Python Tests    │  │  Dashboard Build    │  │  Docker Build     │
│  (fix 64 fails)  │  │  (existing)         │  │  (push-only)      │
└──────────────────┘  └────────────────────┘  └──────────────────┘
                                                       │
                                               ┌───────▼──────────┐
                                               │  E2E Tests        │
                                               │  (push-only)      │
                                               │  needs: docker    │
                                               └──────────────────┘
```

**Recommendation:** E2E job runs only on push to main (not PRs). Rationale:
- E2E requires Docker Compose stack build (~3-5 min) + OSRM data download (first run only)
- PR testing already has pytest + dashboard build for fast feedback
- E2E on every PR commit would consume CI minutes rapidly
- The Docker Build job already restricts to push-only; E2E depends on it

### CI Docker Compose Service Subset

For CI, the stack needs these services:
- **db** (PostgreSQL + PostGIS) -- required for all API operations
- **db-init** (Alembic migrations) -- required for schema setup
- **dashboard-build** (React build to shared volume) -- required for dashboard E2E tests
- **api** (FastAPI) -- required for all tests, depends on db-init + dashboard-build

**Critical constraint issue with OSRM/VROOM:**

The success criteria says "without OSRM/VROOM" but all 4 Playwright test projects call `uploadTestCSV()` which triggers the upload-optimize pipeline. The `VroomAdapter.optimize()` method makes HTTP POST to `http://localhost:3000` (VROOM). Without VROOM, this call fails with `httpx.ConnectError`.

**Options to resolve:**

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| **A. Include OSRM+VROOM** | Add osrm-init, osrm, vroom to CI stack | Tests run unmodified, full coverage | OSRM data download ~150 MB first run (cacheable) |
| **B. Cache OSRM data** | GitHub Actions cache for `data/osrm/` | Download only once, ~30s restore | Cache key management, 10 GB cache limit |
| **C. Remove upload from 3 projects** | Only api project uploads; others use pre-seeded DB | Fewer dependencies | Major test refactor, tests diverge from local behavior |

**Recommendation: Option A + B (include OSRM+VROOM, cache OSRM data).** The GitHub Actions cache can store the preprocessed OSRM data (~1.5 GB after preprocessing, but can be reduced). However, 1.5 GB may exceed cache efficiency. A simpler approach: accept the ~2-3 minute OSRM startup overhead on CI since the osrm-init downloads and preprocesses only on first run, and subsequent runs benefit from Docker layer caching.

**Simplest viable approach:** Use `docker compose up --wait` with `--scale osrm-init=0` if OSRM data is pre-cached, or let the full stack start including osrm-init. The `--wait` flag blocks until all services with healthchecks pass, eliminating the need for custom polling scripts.

### Health Check Wait Strategy

Docker Compose v2.1+ supports `docker compose up --wait` which blocks until all services with healthchecks report healthy. The existing `docker-compose.yml` already has healthchecks on:
- **db**: `pg_isready -U routing -d routing_opt` (interval: 10s, retries: 5)
- **osrm**: TCP check on port 5000 (interval: 30s, retries: 3, start_period: 10s)
- **api**: `curl -f http://localhost:8000/health` (interval: 30s, retries: 3)

The `--wait` flag handles all of this automatically. No third-party actions or custom scripts needed.

```yaml
- name: Start Docker Compose stack
  run: docker compose up -d --wait --wait-timeout 120
  env:
    API_KEY: ${{ secrets.API_KEY }}
    ENVIRONMENT: development
```

**For license tests**, the `api-license-test` container starts on demand inside the test spec via `execSync('docker compose -f docker-compose.yml -f docker-compose.license-test.yml up -d api-license-test')`. This works in CI because the license spec handles its own container lifecycle.

### Playwright Install Pattern for CI

```yaml
- name: Install Playwright Chromium
  run: npx playwright install chromium --with-deps
```

The `--with-deps` flag installs OS-level dependencies (libgbm, libasound, etc.) that Chromium needs on ubuntu-latest. Installing only `chromium` (not all browsers) saves ~1 minute.

### Artifact Upload Pattern

```yaml
- name: Upload Playwright report
  if: failure()
  uses: actions/upload-artifact@v4
  with:
    name: playwright-report
    path: playwright-report/
    retention-days: 7

- name: Upload Docker logs
  if: failure()
  uses: actions/upload-artifact@v4
  with:
    name: docker-logs
    path: docker-logs.txt
    retention-days: 7
```

**Important:** Use `if: failure()` (not `if: ${{ !cancelled() }}`). The user decision explicitly says "Upload only on failure." The Docker logs capture step should run `docker compose logs > docker-logs.txt` before the upload.

### CI Badge Format

For the repo `vishnu-pradeep95/route_optimizer` with workflow file `ci.yml`:

```markdown
![CI](https://github.com/vishnu-pradeep95/route_optimizer/actions/workflows/ci.yml/badge.svg)
```

Place immediately after the title in README.md:

```markdown
# Routing Optimization Platform

![CI](https://github.com/vishnu-pradeep95/route_optimizer/actions/workflows/ci.yml/badge.svg)

A modular delivery-route optimization system...
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Service readiness polling | Custom bash script with sleep/retry | `docker compose up --wait` | Built-in, handles all healthchecks automatically |
| Browser dependency install | Manual apt-get for Chromium deps | `npx playwright install chromium --with-deps` | Playwright knows exact deps for each OS |
| Artifact upload | Custom S3/storage scripts | `actions/upload-artifact@v4` | Native GHA integration, downloadable from PR/run UI |
| CI badge | Custom badge service | GitHub's native workflow badge URL | Always accurate, no external dependency |

## Common Pitfalls

### Pitfall 1: Docker Compose Startup Without Wait
**What goes wrong:** Tests start before API/DB are ready, causing connection refused errors and flaky CI.
**Why it happens:** `docker compose up -d` returns immediately; containers may not be healthy yet.
**How to avoid:** Use `docker compose up -d --wait --wait-timeout 120`. The `--wait` flag blocks until all services with healthchecks are healthy.
**Warning signs:** Intermittent test failures, "connection refused" errors in CI logs.

### Pitfall 2: Missing API_KEY Secret in GitHub Actions
**What goes wrong:** E2E tests fail with "API_KEY environment variable is not set" error from `validateApiKey()` in `e2e/helpers/setup.ts`.
**Why it happens:** GitHub Actions secrets must be explicitly passed to steps via `env:` block.
**How to avoid:** Add `API_KEY: ${{ secrets.API_KEY }}` to the environment of the Playwright test step. Verify the secret exists in repo Settings > Secrets and variables > Actions.
**Warning signs:** First test fails immediately in beforeAll.

### Pitfall 3: Playwright Install Without --with-deps
**What goes wrong:** Chromium crashes with missing shared library errors (libgbm.so, libasound.so).
**Why it happens:** ubuntu-latest doesn't have all Chromium dependencies pre-installed.
**How to avoid:** Always use `npx playwright install chromium --with-deps`.
**Warning signs:** "Failed to launch chromium" or "error while loading shared libraries" in CI logs.

### Pitfall 4: OSRM Data Not Available in CI
**What goes wrong:** VROOM returns 500 errors because OSRM has no routing data; all E2E tests fail.
**Why it happens:** osrm-init downloads 150 MB of Kerala map data and preprocesses it (~1.5 GB output). First CI run takes extra time.
**How to avoid:** Let osrm-init run in CI (it's idempotent). The Docker volume persists within a single CI run. Use `--wait-timeout 120` to give OSRM time to start.
**Warning signs:** VROOM HTTP 500 errors, "no matching road found" in logs.

### Pitfall 5: Playwright forbidOnly Failing in CI
**What goes wrong:** CI fails with "test.only is not allowed in CI" error.
**Why it happens:** `playwright.config.ts` has `forbidOnly: !!process.env.CI` -- if someone commits a `.only`, CI catches it.
**How to avoid:** This is a feature, not a bug. Remove `.only` from tests before pushing.
**Warning signs:** Immediate failure with clear forbidOnly message.

### Pitfall 6: Artifact Upload Step Skipped on Failure
**What goes wrong:** Playwright report is not uploaded despite test failures.
**Why it happens:** By default, subsequent steps don't run when a prior step fails.
**How to avoid:** Use `if: failure()` on the upload step (not `if: always()` which would upload on success too, wasting storage).
**Warning signs:** No artifacts visible in the GitHub Actions run.

### Pitfall 7: Docker Image Build Context in CI
**What goes wrong:** Docker build fails because CI checkout doesn't include all needed files.
**Why it happens:** `.dockerignore` or sparse checkout may exclude files needed by Dockerfile.
**How to avoid:** Use standard `actions/checkout@v4` with no path filters. Verify the Dockerfiles reference paths that exist in the checkout.
**Warning signs:** "COPY failed: file not found" in Docker build logs.

### Pitfall 8: pytest-asyncio Version Mismatch
**What goes wrong:** 64 pytest failures with greenlet/async errors persist after mock fixes.
**Why it happens:** `pytest-asyncio==1.3.0` is very old (current is 0.24+). The 1.3.0 version has different async mode defaults.
**How to avoid:** Check if upgrading `pytest-asyncio` resolves the greenlet issues. If not, ensure proper mock patterns for `AsyncSession`.
**Warning signs:** `MissingGreenlet` errors in pytest output.

## Fixing 64 Pytest Failures

### Root Cause Analysis

The CONTEXT.md from Phase 21 notes: "362/426 pytest tests pass (64 pre-existing failures, 0 regressions)." The failures are described as "SQLAlchemy async/greenlet issues, DB-dependent tests."

**Likely failure categories:**

1. **AsyncSession mocking issues:** Tests that import from `core.database.connection` trigger `create_async_engine()` at module import time. If `DATABASE_URL` points to a non-existent database, this doesn't fail immediately (engines are lazy), but session operations can fail.

2. **Greenlet errors:** When async SQLAlchemy operations are accessed synchronously (e.g., lazy-loading a relationship in a sync context), SQLAlchemy raises `MissingGreenlet`. Tests using `FastAPI.TestClient` run in a sync context but mock async sessions.

3. **DB-dependent tests without proper mocking:** Some tests may attempt real database operations (execute, commit) against the mock session without proper return values configured.

**Fix strategies (Claude's discretion):**

| Strategy | When to Use | Confidence |
|----------|-------------|------------|
| Improve AsyncMock configuration | Tests that call session.execute() without configured return | HIGH |
| Patch module-level imports | Tests that fail on import of database modules | HIGH |
| Add proper repository mocking | Tests that call repo functions without mocking them | HIGH |
| Fix pytest-asyncio configuration | If async test markers are misconfigured | MEDIUM |

**Key pattern for fixing:** The existing `test_api.py` has a working pattern:
```python
@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session

@pytest.fixture
def client(mock_session):
    async def override_get_session():
        yield mock_session
    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()
```

The 64 failures are likely in test files that don't follow this pattern or have insufficient mocking. The fix is to audit each failing test and ensure proper mocking.

**Important:** The user decision says "do not use xfail markers or skip." All 64 must actually pass.

## Code Examples

### Complete E2E Job YAML

```yaml
# Source: Playwright CI docs + project-specific configuration
e2e:
  name: E2E Tests
  runs-on: ubuntu-latest
  if: github.event_name == 'push'
  needs: [docker]  # Reuse validated Docker images

  steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Node.js 22
      uses: actions/setup-node@v4
      with:
        node-version: "22"
        cache: "npm"
        cache-dependency-path: package-lock.json

    - name: Install dependencies
      run: npm ci

    - name: Install Playwright Chromium
      run: npx playwright install chromium --with-deps

    - name: Start Docker Compose stack
      run: docker compose up -d --wait --wait-timeout 180
      env:
        API_KEY: ${{ secrets.API_KEY }}
        ENVIRONMENT: development

    - name: Run Playwright E2E tests
      run: npx playwright test --workers=1
      env:
        API_KEY: ${{ secrets.API_KEY }}
        CI: true

    - name: Capture Docker logs
      if: failure()
      run: docker compose logs --no-color > docker-logs.txt 2>&1

    - name: Upload Playwright report
      if: failure()
      uses: actions/upload-artifact@v4
      with:
        name: playwright-report
        path: playwright-report/
        retention-days: 7

    - name: Upload Docker logs
      if: failure()
      uses: actions/upload-artifact@v4
      with:
        name: docker-logs
        path: docker-logs.txt
        retention-days: 7

    - name: Tear down Docker Compose
      if: always()
      run: docker compose down -v
```

### CI Badge Markdown

```markdown
![CI](https://github.com/vishnu-pradeep95/route_optimizer/actions/workflows/ci.yml/badge.svg)
```

### Docker Compose Partial Start (Exclude OSRM+VROOM)

If the decision is to truly exclude OSRM/VROOM, the stack would be:
```bash
docker compose up -d --wait db db-init dashboard-build api
```

But this will cause E2E test failures on upload. See Open Questions section.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `docker-compose` (hyphenated) | `docker compose` (space) | Compose v2 (2022) | CI already uses correct form |
| Custom health polling scripts | `docker compose up --wait` | Compose v2.1+ | Eliminates bash polling hacks |
| `actions/upload-artifact@v3` | `actions/upload-artifact@v4` | Apr 2024 deprecation | v3 deprecated, v4 required |
| `npx playwright install` (all) | `npx playwright install chromium --with-deps` | Stable | Saves ~1 min in CI, installs only what's needed |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Playwright 1.58.2 (E2E) + pytest 9.0.2 (unit) |
| Config file | `playwright.config.ts` (E2E), `pytest` uses defaults (unit) |
| Quick run command | `npx playwright test --project=api` |
| Full suite command | `npx playwright test` (E2E) / `python -m pytest tests/ -q --tb=short` (unit) |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CICD-01 | All pytest tests pass in CI | unit | `python -m pytest tests/ -q --tb=short` | Yes (tests/) |
| CICD-02 | Playwright E2E job passes in CI | e2e | `npx playwright test --workers=1` | Yes (e2e/) |
| CICD-03 | HTML report uploaded on failure | manual-only | Verify artifact exists in GHA UI after induced failure | N/A |
| CICD-04 | CI badge visible in README | manual-only | Visual check of README.md on GitHub | N/A |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -q --tb=short` (for pytest fixes)
- **Per wave merge:** Push to main, verify full CI pipeline passes
- **Phase gate:** All 4 CI jobs green, badge visible, artifact upload verified

### Wave 0 Gaps
None -- existing test infrastructure covers all phase requirements. The E2E tests and pytest suite already exist; this phase integrates them into CI.

## Open Questions

1. **OSRM/VROOM in CI: Include or Exclude?**
   - What we know: Success criteria says "without OSRM/VROOM" but E2E tests require VROOM for upload-optimize flow. All 4 Playwright projects call `uploadTestCSV()` which triggers `VroomAdapter.optimize()` over HTTP.
   - What's unclear: Whether the user intended to literally exclude OSRM/VROOM (accepting that upload tests fail) or whether this was a simplification assumption that doesn't hold.
   - Recommendation: **Include OSRM+VROOM in CI.** The osrm-init container handles data download automatically. First CI run takes ~3-5 extra minutes; Docker layer caching makes subsequent runs faster. Without OSRM+VROOM, 30+ of 38 E2E tests will fail. The success criteria "all jobs including the new E2E job" cannot be met without VROOM.

2. **pytest-asyncio Version**
   - What we know: `pytest-asyncio==1.3.0` is in requirements.txt. Current stable is `0.24+` (confusingly, the 1.x branch was an older fork).
   - What's unclear: Whether the 64 failures are caused by the pytest-asyncio version or by incomplete mocking.
   - Recommendation: Investigate failures locally first. Fix mocking where possible. Consider upgrading pytest-asyncio only if mocking fixes don't resolve all 64.

3. **E2E Job Dependency Chain**
   - What we know: The Docker Build job validates image builds. E2E needs running containers.
   - What's unclear: Whether `needs: [docker]` provides value (E2E rebuilds images via `docker compose up`) or just adds ordering.
   - Recommendation: E2E job should NOT depend on the Docker Build job. The Docker Build job builds standalone images and smoke-tests them. The E2E job runs `docker compose up` which builds images from docker-compose.yml. They're independent. If we add a dependency, E2E won't run when Docker Build is skipped (PRs). Since E2E is push-only anyway, add `needs: [test, dashboard]` so E2E only runs if basic validations pass first.

## Sources

### Primary (HIGH confidence)
- Existing CI workflow: `.github/workflows/ci.yml` -- current 3-job structure
- Playwright config: `playwright.config.ts` -- CI-aware settings (forbidOnly, retries, workers)
- Docker Compose: `docker-compose.yml` -- service definitions, healthchecks
- E2E test files: `e2e/*.spec.ts` -- dependency on VROOM verified via code inspection

### Secondary (MEDIUM confidence)
- [Playwright CI documentation](https://playwright.dev/docs/ci) -- GitHub Actions workflow pattern, `--with-deps` flag
- [GitHub Docs: Workflow status badge](https://docs.github.com/en/actions/monitoring-and-troubleshooting-workflows/monitoring-workflows/adding-a-workflow-status-badge) -- badge URL format
- [Docker Compose `--wait` flag](https://github.com/docker/compose/issues/8351) -- built-in health check wait
- [GitHub Changelog: Docker/Compose upgrades](https://github.blog/changelog/2026-01-30-docker-and-docker-compose-version-upgrades-on-hosted-runners/) -- Compose v2.40 pre-installed on ubuntu-latest

### Tertiary (LOW confidence)
- pytest-asyncio version analysis -- needs local verification of actual error messages

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all tools already in project, well-documented
- Architecture: HIGH -- CI pattern well-established, Docker Compose healthchecks verified
- Pitfalls: HIGH -- verified through code inspection (VROOM dependency, artifact patterns)
- Pytest fixes: MEDIUM -- strategy identified but actual failures need local investigation

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (stable CI tooling, no fast-moving dependencies)
