# Pitfalls Research

**Domain:** Ship-Ready QA -- Playwright E2E tests, CI/CD browser integration, stop/GC scripts, distribution verification, license lifecycle docs for Docker Compose route optimization app
**Researched:** 2026-03-08
**Confidence:** HIGH (Playwright CI patterns verified against official docs; Docker signal handling verified against Docker docs; .pyc compatibility verified against CPython PEP 3147 and issue trackers; stop script patterns verified against Docker Compose documentation)

---

## Critical Pitfalls

### Pitfall 1: Playwright Tests Start Before Docker Compose Services Are Actually Ready

**What goes wrong:**
Playwright's `webServer` config detects when a port opens and immediately starts running tests. But Docker Compose opens the mapped port on the host as soon as the container starts -- before the application process inside the container is actually listening. This creates a race condition: Playwright detects port 8000 is open, sends its first request, and gets `ECONNREFUSED` because uvicorn has not finished booting inside the container. The test fails with a timeout error that looks like a test bug, not a startup timing issue.

This is worse in this project because the API depends on `db-init` (Alembic migrations) and `dashboard-build` completing first. The full startup chain is: db healthy -> db-init migrations -> osrm-init -> osrm started -> vroom started -> dashboard-build done -> API boots. This takes 10-60 seconds depending on cold/warm state, with OSRM init potentially taking 15+ minutes on first run.

**Why it happens:**
Docker's port forwarding operates at the network level, not the application level. The port-open signal is not equivalent to "service is ready." Developers test locally where services are already warm, so they never hit the cold-start race.

**How to avoid:**
Do NOT use Playwright's `webServer` config to start Docker Compose. Instead:
1. Use a `globalSetup` script that runs `docker compose up -d` and then polls the `/health` endpoint with curl/fetch until it returns 200, with a configurable timeout (90 seconds for warm, 300 seconds for cold with OSRM init).
2. In `playwright.config.ts`, set `baseURL: 'http://localhost:8000'` and rely on the `globalSetup` having already verified the service is healthy.
3. Add a `globalTeardown` that optionally runs `docker compose down` (controlled by an env var like `KEEP_SERVICES=true` for development).

Example `globalSetup`:
```typescript
async function globalSetup() {
  execSync('docker compose up -d', { stdio: 'inherit' });
  const maxWait = 90_000;
  const start = Date.now();
  while (Date.now() - start < maxWait) {
    try {
      const res = await fetch('http://localhost:8000/health');
      if (res.ok) return;
    } catch { /* not ready */ }
    await new Promise(r => setTimeout(r, 2000));
  }
  throw new Error('Services did not become healthy');
}
```

**Warning signs:**
- Tests pass locally (services already running) but fail in CI (cold start)
- Intermittent `ECONNREFUSED` or `net::ERR_CONNECTION_REFUSED` in first test
- Tests pass when re-run immediately after failure (services warmed up from first attempt)

**Phase to address:** Playwright E2E setup phase -- must be the first thing configured before writing any tests.

---

### Pitfall 2: Playwright Tests Flaky in GitHub Actions Due to CI Resource Constraints

**What goes wrong:**
Tests pass reliably on the developer's machine but fail intermittently in GitHub Actions. The symptoms are: timeouts on `page.waitForSelector`, elements not found after navigation, screenshots showing half-rendered pages, and `TimeoutError: locator.click: Timeout 30000ms exceeded`. This happens because GitHub Actions shared runners have 2 vCPUs and 7 GB RAM, which must run 4 Docker containers (API, DB, OSRM, VROOM) AND a Chromium browser simultaneously. The containers consume 2-4 GB RAM, leaving Chromium resource-starved.

**Why it happens:**
Developer machines typically have 8-16 GB RAM and 4+ cores, giving ample headroom. CI runners are shared, throttled, and have variable I/O performance. Animations that complete in 50ms locally take 200ms+ in CI. Database queries that return in 5ms locally take 50ms in CI under load.

**How to avoid:**
1. Run Playwright in CI with `--workers=1` to avoid concurrent browser contexts competing with Docker containers for limited CPU/RAM.
2. Use `expect(locator).toBeVisible({ timeout: 15000 })` instead of default timeouts -- CI needs 2-3x longer than local.
3. Set `retries: 2` in `playwright.config.ts` for CI only: `retries: process.env.CI ? 2 : 0`.
4. Enable traces on first retry: `trace: 'on-first-retry'` -- this captures screenshots, DOM snapshots, and network logs for debugging.
5. Upload trace artifacts in the GitHub Actions workflow so failures can be debugged post-run.
6. Use `mcr.microsoft.com/playwright:v{version}-noble` Docker image in CI to avoid browser installation time (saves 1-2 minutes and 400MB download).
7. Do NOT run E2E tests alongside the Docker Build CI job -- they need separate runners or sequential execution.

**Warning signs:**
- Tests pass locally 100% but fail 20-40% of the time in CI
- Failures always involve timeouts, never assertion mismatches
- Adding `await page.waitForTimeout(1000)` "fixes" it (this is a band-aid, not a fix)

**Phase to address:** CI/CD pipeline integration phase -- configure Playwright CI with proper timeouts and artifact upload before merging E2E tests.

---

### Pitfall 3: .pyc Distribution Breaks When Build Machine and Docker Image Use Different Python Minor Versions

**What goes wrong:**
`build-dist.sh` compiles `core/licensing/*.py` to `.pyc` using the developer's local Python. The resulting `.pyc` files embed a "magic number" that identifies the exact Python version (e.g., 3.12.3). The Docker image uses `python:3.12-slim` which resolves to the latest 3.12.x patch. If the developer's local Python is 3.12.3 but the Docker image pulls 3.12.7, the magic numbers differ. Python refuses to import the `.pyc` with `ImportError: bad magic number`.

This is especially dangerous because:
- The build appears to succeed (import validation in `build-dist.sh` runs on the same local Python that compiled it).
- The failure only manifests when the customer extracts the tarball and runs `docker compose up`.
- The error message ("bad magic number") is incomprehensible to office staff.
- Python 3.12 has had multiple magic number changes across patch releases.

**Why it happens:**
CPython .pyc magic numbers change with each minor release AND can change with patch releases when bytecode format changes. `python:3.12-slim` without a pinned patch version is a moving target. The developer's local Python and the Docker image's Python are independently updated.

**How to avoid:**
1. Pin the Docker image to a specific patch version: `python:3.12.3-slim` (not just `3.12-slim`).
2. OR (better): compile .pyc inside the Docker build, not on the developer's machine. Add a step to `build-dist.sh` that uses Docker to compile:
   ```bash
   docker run --rm -v "$STAGE:/app" python:3.12-slim \
     python -m compileall -b -f -q /app/core/licensing/
   ```
3. Add a version check to `build-dist.sh` that verifies the local Python version matches the Dockerfile's base image version.
4. The import validation step in `build-dist.sh` already tests against local Python -- but add a Docker-based validation too: run the import inside the same Docker image.

**Warning signs:**
- `build-dist.sh` runs `python3 -m compileall` without checking the Python version
- Dockerfile uses `python:3.12-slim` (unpinned patch version)
- Import validation only runs locally, not inside the target Docker image
- Customer reports "the system worked until we ran a Docker update"

**Phase to address:** Distribution verification phase -- fix .pyc compilation strategy before building any customer tarballs.

---

### Pitfall 4: Stop Script Uses `docker compose down -v` and Destroys Production Database

**What goes wrong:**
A stop/GC script intended for cleanup uses `docker compose down -v` (the `-v` flag removes named volumes). The `pgdata` volume contains the PostgreSQL database with all order history, geocode cache, delivery records, and route data. One accidental run of the stop script -- or a developer habit from using it in testing -- destroys all production data with no recovery path. The `-v` flag is a single character that causes irreversible data loss.

The existing `reset.sh` script already has this footgun: it offers `docker compose down -v` as an option. If a stop/GC script reuses this pattern without safeguards, the same risk applies.

**Why it happens:**
Developers use `docker compose down -v` routinely in development to get a clean slate. It becomes muscle memory. Stop scripts often start as copies of reset scripts. The `-v` flag is easy to include by accident or by habit. Docker provides no confirmation prompt for volume removal.

**How to avoid:**
1. The stop script must use `docker compose stop` (not `down`) for graceful shutdown. `stop` halts containers but preserves everything.
2. If garbage collection of containers is needed, use `docker compose down` WITHOUT `-v`. This removes containers and networks but preserves volumes.
3. Never include `-v` in any script except the explicit reset/nuke script, which must require confirmation (the existing `reset.sh` already has this, which is good).
4. Name the scripts clearly: `stop.sh` (daily shutdown), `reset.sh` (nuclear option with confirmation). Never have a script that ambiguously does both.
5. Add a safety check: if the `pgdata` volume has data, refuse to remove it without explicit confirmation:
   ```bash
   if docker volume inspect routing_opt_pgdata &>/dev/null; then
     error "Database volume exists. Use reset.sh --all to remove data."
     exit 1
   fi
   ```

**Warning signs:**
- Stop script contains `docker compose down -v` or `docker compose down --volumes`
- Stop and reset functionality combined in one script
- No confirmation before volume removal
- Script tested only on dev machine where data loss is inconsequential

**Phase to address:** Stop/GC script phase -- design stop.sh as a safe shutdown from the start, completely separate from reset.sh.

---

### Pitfall 5: Clean Install Verification Tests the Developer's Cached State, Not a Fresh Machine

**What goes wrong:**
The developer runs "clean install verification" by: (1) extracting the tarball, (2) running `install.sh`, (3) seeing it work. But the machine already has: Docker images cached (no download), OSRM data in `data/osrm/` (no 15-minute preprocessing), `.env` from a previous install (no prompts), Python 3.12 installed, and the Google Maps API key set. The "clean install" test misses every first-run problem because nothing is actually first-run.

**Why it happens:**
Testing clean install on the same machine you develop on is the default behavior. Creating a truly fresh environment requires a separate VM/WSL instance, which adds friction. Developers unconsciously avoid this because they know the fresh install takes 15-20 minutes (OSRM download + preprocessing).

**How to avoid:**
1. Test in a fresh WSL instance: `wsl --install -d Ubuntu-24.04 --name test-clean-install` (creates a separate WSL instance with no Docker, no Python, no project files).
2. Create a verification checklist that must be run on the fresh instance:
   - [ ] Extract tarball to `~/routing_opt`
   - [ ] Run `./scripts/bootstrap.sh` (not from the repo -- from the tarball)
   - [ ] Verify OSRM downloads and preprocesses (15+ min)
   - [ ] Verify API starts and `/health` returns 200
   - [ ] Upload a CSV and verify routes generate
   - [ ] Open driver PWA and verify map loads
3. Automate what can be automated: a CI job that extracts the tarball into a fresh Docker container (not the project's containers) and runs the install script.
4. Test without the Google Maps API key to verify graceful degradation.

**Warning signs:**
- "Clean install verified" but OSRM data directory already existed
- Verification done on the same machine as development
- Install script never tested non-interactively (piped stdin)
- No verification of the tarball contents against expected file list

**Phase to address:** Clean install verification phase -- must create a separate test environment before declaring the tarball verified.

---

### Pitfall 6: Playwright E2E Tests Require Google Maps API Key That Does Not Exist in CI

**What goes wrong:**
The E2E test for the upload flow requires: upload CSV -> geocode addresses -> optimize routes -> display on map. Geocoding calls the Google Maps API, which requires a valid API key. In CI (GitHub Actions), there is no API key configured. The upload flow fails at geocoding with `REQUEST_DENIED`, and the test fails -- not because the UI is broken, but because an external dependency is missing.

This is compounded by the existing problem noted in the milestone context: the Google Maps API key is currently broken with `REQUEST_DENIED`. E2E tests will fail even locally if the key is not working.

**Why it happens:**
E2E tests by nature exercise the full stack, including external API dependencies. Developers either hardcode their API key locally or forget that CI has no access to it. Storing the API key in GitHub Secrets and passing it to the test environment seems like the fix, but it incurs real costs (each CI run geocodes addresses) and creates a dependency on Google's uptime for CI reliability.

**How to avoid:**
1. E2E tests must use a mock geocoding backend, not the real Google API. Options:
   - Seed the database with pre-geocoded addresses before running tests (skip the geocoding step entirely).
   - Use an API test fixture that overrides the geocoding endpoint to return canned responses.
   - Pre-populate the geocode cache in the test database so geocoding hits the cache, not Google.
2. Have exactly ONE integration test that verifies Google Geocoding API connectivity -- run it locally with a real key, skip it in CI (`test.skip(process.env.CI)`).
3. Store the Google Maps API key as a GitHub Secret only for the geocoding integration test, not for all E2E tests.
4. Add a `/health` response field that shows geocoding status (e.g., `"geocoding": "configured"` vs `"geocoding": "not configured"`) so tests can assert on it.

**Warning signs:**
- E2E tests pass locally (API key in `.env`) but fail in CI (no key)
- CI workflow does not set `GOOGLE_MAPS_API_KEY` secret
- Tests rely on real geocoding results instead of seeded/cached data
- CI costs increase as more tests trigger geocoding API calls

**Phase to address:** Playwright E2E setup phase -- establish the mocking/seeding strategy before writing any test that touches the upload flow.

---

### Pitfall 7: License Lifecycle Documentation Assumes Technical Reader for Non-Technical Customer

**What goes wrong:**
License lifecycle documentation (generate -> deliver -> activate -> renew -> troubleshoot) is written with developer terminology: "HMAC validation," "hardware-bound key," "magic bytes." The first customer is a Vatakara HPCL office with non-technical staff. They receive a `license.key` file and instructions to "place it in the project root." They do not know what a "project root" is, or how to place a file in a WSL Linux directory from Windows.

Worse, when the license expires or the hardware changes (new laptop), the error message says something like "License validation failed" with no instructions on what to do. The customer calls support, and there is no documented procedure for the support person to follow.

**Why it happens:**
License systems are built by developers for developers. The documentation describes the mechanism (HMAC, hardware binding) rather than the user workflow (what to do when you see an error). First-customer documentation is always the hardest because there is no feedback loop yet.

**How to avoid:**
1. Write TWO documents: one for the developer (how the licensing system works internally) and one for the customer (what to do when X happens).
2. Customer-facing license doc must cover:
   - "Your license expires on [date]. You will see a yellow warning 30 days before." (if applicable)
   - "If you see 'License expired,' contact [phone/email] with your license ID."
   - "If you moved to a new computer, your license key needs to be re-issued. Contact [phone/email]."
   - "Where is my license file?" -> `C:\Users\[name]` in WSL becomes `~/routing_opt/license.key` -- show the Windows path equivalent.
3. Add a license status indicator to the dashboard UI (green = valid, yellow = expiring soon, red = expired/invalid) with a plain-English message.
4. The license troubleshooting guide must include the exact error messages and their meanings, not generic descriptions.

**Warning signs:**
- License docs mention HMAC, hardware fingerprinting, or bytecode
- No mapping from error messages to customer actions
- License file delivery instructions assume Linux terminal familiarity
- No "contact support" procedure documented for license issues

**Phase to address:** License lifecycle documentation phase -- write the customer-facing document first, then the developer reference.

---

### Pitfall 8: Tarball Missing Critical Files Due to rsync Exclusion Overshoot

**What goes wrong:**
`build-dist.sh` uses `rsync --exclude` to strip developer artifacts. Adding a new exclude pattern (e.g., `--exclude='*.test.*'` to remove test files) accidentally catches production files that match the pattern. Or a new directory added to the project is not explicitly included and gets silently excluded by a broad pattern. The tarball builds successfully, the import validation passes (it only checks `core/licensing`), but the API fails at runtime because a template file, migration script, or configuration file is missing.

Specific risks for this project:
- `--exclude='data/'` removes the empty `data/` directory, but the API expects `data/` to exist at `/app/data` for uploads.
- `--exclude='scripts/generate_license.py'` correctly excludes the license generator, but if other scripts are added in `scripts/`, they might need to be explicitly included.
- `.env.example` is included but not verified to have correct placeholder values.
- Alembic migration files (`infra/alembic/`) must be included or the `db-init` container fails.

**Why it happens:**
Exclusion-based packaging (exclude what you do not want) is fragile because new files are included by default until someone adds an exclusion. Inclusion-based packaging (include only what you want) is safer but requires updating the include list when new files are added. `build-dist.sh` uses exclusion. There is no post-build verification that the tarball contains everything needed.

**How to avoid:**
1. Add a manifest verification step to `build-dist.sh` that checks for required files after staging:
   ```bash
   REQUIRED_FILES=(
     "docker-compose.yml"
     "infra/Dockerfile"
     "infra/Dockerfile.dashboard"
     "alembic.ini"
     "infra/alembic/env.py"
     "scripts/install.sh"
     "scripts/start.sh"
     "scripts/bootstrap.sh"
     "apps/kerala_delivery/api/main.py"
     "apps/kerala_delivery/driver_app/index.html"
     "core/licensing/__init__.pyc"
     "core/licensing/license_manager.pyc"
     ".env.example"
   )
   for f in "${REQUIRED_FILES[@]}"; do
     [ -f "$STAGE/$f" ] || { error "Missing required file: $f"; exit 1; }
   done
   ```
2. Add a tarball-contents smoke test: extract to a temp directory and verify the file tree matches expectations.
3. If adding new rsync excludes, always test by running `build-dist.sh` and then extracting the tarball and diffing against expected contents.

**Warning signs:**
- `build-dist.sh` has more than 15 `--exclude` patterns (complexity increases error risk)
- No post-staging file verification step
- Tarball tested by "it builds" not "it contains everything"
- New files added to the project without updating `build-dist.sh` verification

**Phase to address:** Distribution verification phase -- add manifest check to `build-dist.sh` before building the v1.4 tarball.

---

### Pitfall 9: Stop Script Sends SIGKILL to PostgreSQL Before Dirty Pages Are Flushed

**What goes wrong:**
Docker's default grace period is 10 seconds. `docker compose stop` sends SIGTERM, waits 10 seconds, then sends SIGKILL. PostgreSQL needs time to flush dirty pages, complete in-flight transactions, and write checkpoint records. If PostgreSQL is mid-write when SIGKILL arrives, the database may need recovery on next startup (adding 30-60 seconds to boot time) or, in worst cases, suffer minor data corruption.

For this project, PostgreSQL holds delivery records, geocode cache, and route history. Data loss or corruption here means re-importing and re-geocoding all addresses (which costs real money via Google API calls).

**Why it happens:**
The default `stop_grace_period` of 10 seconds is designed for stateless web services. Databases need more time. Developers test stop/start with small datasets where PostgreSQL flushes instantly, so they never hit the timeout.

**How to avoid:**
1. Set `stop_grace_period: 30s` for the `db` service in `docker-compose.yml`:
   ```yaml
   db:
     stop_grace_period: 30s
   ```
2. The stop script should stop services in dependency-reverse order: API first (stops accepting requests), then VROOM/OSRM (stateless, can be killed), then PostgreSQL last (needs graceful shutdown time).
3. Use `docker compose stop` (not `down`) in the stop script. `stop` sends SIGTERM and respects grace period. `down` also removes containers, which is unnecessary for daily shutdown.
4. Verify PostgreSQL receives SIGTERM correctly: the `postgis/postgis:16-3.5` image should handle this natively, but confirm with `docker compose stop db && docker compose logs db --tail=5` -- look for "received fast shutdown request."

**Warning signs:**
- `docker compose logs db` shows "redo" or "recovery" messages on startup (indicates unclean previous shutdown)
- Stop script uses `docker compose down` instead of `docker compose stop`
- No `stop_grace_period` configured for the db service
- PostgreSQL startup takes 30+ seconds (recovery in progress)

**Phase to address:** Stop/GC script phase -- configure grace period when writing the stop script.

---

### Pitfall 10: E2E Tests Leak State Between Test Runs, Causing Order-Dependent Failures

**What goes wrong:**
An E2E test uploads a CSV file and creates routes. The next test expects a clean state but finds leftover data from the previous test. Results: test 2 sees unexpected orders in the route list, vehicle selection shows vehicles already assigned, or the "no deliveries" empty state never appears because the database has stale data. Tests pass when run individually but fail when run as a suite.

**Why it happens:**
E2E tests against a real database accumulate state. Unlike unit tests (which mock the database), E2E tests write real data through the API. Without explicit cleanup, each test inherits the previous test's data. This is the #1 source of flaky E2E test suites.

**How to avoid:**
1. Reset database state before each test file (not each individual test -- too slow). Use a `beforeAll` hook that calls a test-only API endpoint to truncate tables, or run an SQL script via `docker compose exec db psql -c "TRUNCATE orders, routes, route_assignments, route_stops CASCADE"`.
2. Alternatively, use database transactions: start a transaction before each test and roll it back after. This is faster but harder to implement with E2E tests because the API runs in a separate process.
3. Add a test-only `/api/test/reset` endpoint (guarded by `ENVIRONMENT=test`) that truncates all tables. This is the pragmatic approach for a project with one test database.
4. Never depend on test execution order. Each test must set up its own preconditions.

**Warning signs:**
- Tests pass in isolation (`npx playwright test upload.spec.ts`) but fail as a suite
- Test failures mention unexpected data counts ("expected 0 routes, got 3")
- Adding `--workers=1` "fixes" failures (sequential execution reduces but does not eliminate state leakage)
- Rerunning the same failing test immediately after failure passes (state was cleaned up by the failed test's side effects)

**Phase to address:** Playwright E2E setup phase -- establish the state management strategy before writing any test that modifies data.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Compiling .pyc on developer machine instead of in Docker | Faster build-dist.sh, no Docker dependency for build | .pyc magic number mismatch when Docker image Python version drifts | Never for customer distribution -- always compile in Docker |
| `docker compose down` in stop script | Clean container state | Removes containers unnecessarily; adds 5-10s to next startup (containers must be recreated) | Only in reset script, never in daily stop |
| Hardcoding `localhost:8000` in Playwright tests | Quick setup | Tests cannot run against a different host/port; breaks if port changes | Acceptable if `baseURL` is set in config, not per-test |
| Skipping E2E tests in CI to speed up pipeline | CI runs 2 minutes faster | Silent regressions in UI flows; defeats the purpose of E2E tests | Never once E2E tests are added; use parallelism instead |
| No database reset between E2E test files | Tests run faster | Order-dependent failures, flaky suite, developer distrust of tests | Never -- test isolation is non-negotiable |
| Using `page.waitForTimeout(2000)` instead of proper waits | Fixes flaky test immediately | Creates slow, fragile tests; masks real timing bugs | Only as temporary debugging aid, never in committed code |

---

## Integration Gotchas

Common mistakes when connecting these v1.4 features to the existing system.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Playwright + Docker Compose | Using `webServer` config to start Docker Compose (race condition on port open vs service ready) | Use `globalSetup` with health endpoint polling; start Docker Compose independently |
| Playwright + GitHub Actions | Running E2E tests on same runner as Docker containers without increasing timeouts | Use `--workers=1`, increase timeouts 2-3x for CI, upload trace artifacts |
| E2E tests + Google Maps API | Tests depend on real geocoding API (costs money, fails in CI, flaky) | Seed database with pre-geocoded addresses; mock geocoding for E2E |
| Stop script + PostgreSQL | Using `docker compose down` which removes containers, or not setting grace period for DB | Use `docker compose stop` with `stop_grace_period: 30s` on db service |
| build-dist.sh + Docker Python version | Compiling .pyc with local Python that differs from Docker image Python | Compile .pyc inside Docker, or pin Docker image to exact patch version |
| Tarball + file permissions | Tarball preserves developer's UID/GID which differs from Docker's appuser (1001) | Verify tarball contents work with the Docker non-root user; test extraction + build |
| CI Playwright + browser cache | Downloading 400MB browsers on every CI run | Cache browsers with `actions/cache` keyed on Playwright version, or use Playwright Docker image |
| License docs + customer deployment | Documenting license.key placement as a Linux path (`~/routing_opt/license.key`) | Show the Windows Explorer path and explain how to access WSL filesystem from Windows |
| E2E tests + existing 420 unit tests | Running Playwright E2E in same CI job as pytest, exceeding runner time limits | Separate CI jobs: `test` (pytest, 2 min), `e2e` (Playwright, 5-10 min), `docker` (build verify, 2 min) |

---

## Performance Traps

Patterns that work at small scale but fail as the CI pipeline or test suite grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Downloading Playwright browsers on every CI run | CI takes 3+ minutes before first test; 400MB bandwidth per run | Cache with `actions/cache` on `~/.cache/ms-playwright`, keyed on Playwright version in package.json | Immediately on first CI run; gets worse with more frequent pushes |
| Running all E2E tests serially on one CI runner | CI pipeline takes 15+ minutes as E2E suite grows | Shard tests across multiple runners with `--shard=1/3` when suite exceeds 5 minutes | At ~20 E2E test files or 10 minutes total |
| Rebuilding Docker images on every E2E CI run | Adds 2-3 minutes per run; Docker layer cache cold in CI | Use `docker compose build` with `DOCKER_BUILDKIT=1` and GitHub Actions Docker layer cache | Immediately; mitigate with `type=gha` cache in `docker/build-push-action` |
| Not pruning Docker artifacts in stop/GC script | Disk fills on customer machine after weeks of daily use (old images, build cache, logs) | Stop script includes periodic pruning: `docker image prune -f`, `docker builder prune -f` | After 2-4 weeks of daily Docker rebuilds; faster if dashboard has frequent updates |

---

## Security Mistakes

Domain-specific security issues for v1.4 features.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Google Maps API key stored in GitHub Actions as a plain env var (not a Secret) | Key visible in CI logs, accessible to anyone with repo read access | Always use `secrets.GOOGLE_MAPS_API_KEY`, never `env` in workflow YAML; ideally skip real key in CI entirely |
| Test-only `/api/test/reset` endpoint accessible in production | Anyone can truncate the production database | Guard with `if os.environ.get('ENVIRONMENT') == 'test'` AND check for a test-only header/token; better: only register the route when `ENVIRONMENT=test` |
| License key included in distribution tarball | Customer A's license key works on any machine if tarball is shared | License key must NOT be in the tarball; deliver it separately via secure channel (encrypted email, in-person USB) |
| Trace artifacts from E2E tests uploaded as public CI artifacts | Traces contain screenshots of the app, potentially with test data that mirrors real delivery addresses | Set artifact retention to 7 days (not 30); ensure test data is synthetic, not derived from real customer data |

---

## UX Pitfalls

Common user experience mistakes specific to v1.4 features.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| License error shows "HMAC validation failed" | Office employee has no idea what this means; system unusable until developer interprets | Show "License problem -- please contact [support phone]. Error code: L-001" with a code the developer can look up |
| Stop script has no feedback during shutdown | User runs `./stop.sh`, sees nothing for 10-30 seconds, thinks it is broken | Show per-service status during shutdown: "Stopping API... done. Stopping OSRM... done. Stopping database... done." |
| Google API troubleshooting doc lists 8 possible causes | Office employee cannot diagnose which applies; gives up after step 2 | Decision tree: "Does the dashboard show addresses on the map? YES -> key is working. NO -> Is there a red error banner? YES -> read the banner text and go to Step X." |
| License renewal requires CLI commands | Customer cannot renew without developer/IT assistance | Document the renewal as a file replacement: "Delete old license.key, copy new license.key to same location, restart the system" |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Playwright E2E tests:** Pass locally but no `globalSetup` health check -- will fail in CI cold start
- [ ] **Playwright E2E tests:** No database reset between test files -- will produce order-dependent failures as suite grows
- [ ] **Playwright E2E tests:** Use real Google Geocoding API -- will fail in CI where no API key exists
- [ ] **Playwright config:** Default timeouts work locally but are too short for CI runners
- [ ] **CI workflow:** Installs Playwright browsers on every run instead of caching -- adds 2+ minutes per run
- [ ] **CI workflow:** E2E job does not upload trace artifacts -- failures are un-debuggable
- [ ] **CI workflow:** E2E and pytest run in same job -- exceeds runner time limit as test count grows
- [ ] **build-dist.sh:** .pyc compiled with local Python, not Docker image Python -- magic number mismatch risk
- [ ] **build-dist.sh:** No manifest verification of required files after staging -- missing files not caught until customer install
- [ ] **build-dist.sh:** tarball tested by "it builds" not "it extracts and boots in a fresh environment"
- [ ] **Stop script:** Uses `docker compose down` instead of `docker compose stop` -- unnecessarily removes containers
- [ ] **Stop script:** No `stop_grace_period` for PostgreSQL -- risk of unclean shutdown on slow machines
- [ ] **Stop script:** No per-service progress feedback -- user thinks script is broken during 10-30s shutdown
- [ ] **License lifecycle doc:** Written for developers, not for office staff -- mentions HMAC, hardware binding, magic bytes
- [ ] **License lifecycle doc:** No mapping from error messages to customer actions
- [ ] **License lifecycle doc:** No "contact support" procedure with phone number / email
- [ ] **Google API troubleshooting:** Lists technical causes without a user-facing decision tree
- [ ] **Clean install verification:** Tested on developer machine with cached Docker images and OSRM data, not fresh WSL instance
- [ ] **Prod vs dev docs:** Do not explain which docker-compose file to use when, or how to switch between them

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| .pyc magic number mismatch in customer tarball | MEDIUM | Rebuild tarball using Docker-based compilation; re-deliver to customer; no data loss |
| Stop script accidentally removed database volume | HIGH | Restore from most recent `backups/*.sql.gz` (if backup script was configured); if no backup, all data is lost -- must re-import all CSVs and re-geocode (costs Google API credits) |
| E2E tests flaky in CI | LOW | Add `retries: 2`, increase timeouts, use `--workers=1`; investigate root cause from trace artifacts |
| Playwright tests fail because Google API key missing in CI | LOW | Switch to seeded/cached geocode data for E2E tests; add key as GitHub Secret only for the geocoding integration test |
| Tarball missing required file | LOW | Add file to rsync include or remove from exclude list; add to manifest check array; rebuild and re-deliver |
| License expired at customer site | MEDIUM | Generate new license key; deliver to customer; they replace `license.key` file and restart. Recovery depends on how fast you can reach the customer. |
| Clean install fails on customer machine | HIGH | Remote diagnosis required; could be OSRM OOM, Python version mismatch, Docker not installed, or missing .env values. Each diagnosis takes 30-60 minutes remotely. Prevention via thorough clean install testing is far cheaper. |
| E2E test state leakage causing false failures | LOW | Add database reset to `beforeAll` hooks; rerun tests to verify; fix is mechanical once identified |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Service startup race condition | Playwright E2E setup | Tests pass on cold start: `docker compose down && npx playwright test` |
| CI flakiness (timeouts, resources) | CI/CD pipeline integration | 10 consecutive CI runs with zero flaky failures |
| .pyc version mismatch | Distribution verification | Build tarball, extract in fresh Docker container, run `python -c "import core.licensing"` |
| Stop script data loss | Stop/GC script | Run stop script 10 times; verify `docker volume ls` still shows pgdata after each |
| Clean install from tarball | Clean install verification | Extract tarball on fresh WSL instance with no Docker cache; full workflow completes |
| Google API key missing in E2E | Playwright E2E setup | CI E2E tests pass with no `GOOGLE_MAPS_API_KEY` set |
| License docs for non-technical user | License lifecycle docs | Hand document to non-technical person; they can identify their license status and know who to contact |
| Tarball missing files | Distribution verification | Manifest check in `build-dist.sh` passes; tarball extract matches expected file list |
| Database state leakage in E2E | Playwright E2E setup | Run full test suite 3 times consecutively; all pass with identical results |
| PostgreSQL unclean shutdown | Stop/GC script | After stop + start, `docker compose logs db` shows no "recovery" messages |
| Playwright browser caching in CI | CI/CD pipeline integration | Second CI run uses cached browsers (check `actions/cache` hit in logs) |
| License error messages for office staff | License lifecycle docs | Every license error code has a plain-English explanation and "contact support" instruction |

---

## Sources

- [Playwright Official: Setting up CI](https://playwright.dev/docs/ci-intro) -- recommended CI configuration, artifact upload, trace collection
- [Playwright Official: Docker](https://playwright.dev/docs/docker) -- Docker image names (`mcr.microsoft.com/playwright`), `--ipc=host` requirement, `--init` flag
- [Playwright Official: Timeouts](https://playwright.dev/docs/test-timeouts) -- timeout configuration hierarchy
- [Playwright webServer race condition with Docker Compose](https://github.com/sillsdev/web-languageforge/issues/1402) -- port-open != service-ready
- [Avoiding Flaky Tests in Playwright (Better Stack)](https://betterstack.com/community/guides/testing/avoid-flaky-playwright-tests/) -- explicit waits, stable selectors, retry strategies
- [Why Playwright Tests Fail in CI but Pass Locally (JavaScript in Plain English)](https://javascript.plainenglish.io/why-your-playwright-tests-fail-in-ci-but-pass-locally-and-how-to-fix-it-54fa19836737) -- CI resource constraints, timeout adjustment
- [Docker Compose stop documentation](https://docs.docker.com/reference/cli/docker/compose/stop/) -- SIGTERM, grace period, SIGKILL behavior
- [Docker Compose down documentation](https://docs.docker.com/reference/cli/docker/compose/down/) -- `-v` removes volumes, default behavior
- [Why You Need to Wait When Stopping Docker Compose Services (vsupalov.com)](https://vsupalov.com/docker-compose-stop-slow/) -- signal propagation, grace period configuration
- [Docker Graceful Shutdown and Signal Handling](https://oneuptime.com/blog/post/2026-01-16-docker-graceful-shutdown-signals/view) -- SIGTERM handling in containers
- [PEP 3147 -- PYC Repository Directories](https://peps.python.org/pep-3147/) -- .pyc magic numbers, version-specific caching, `-b` flag for legacy placement
- [Python .pyc Bytecode Compatibility (CPython Bug Tracker)](https://bugs.python.org/issue41650) -- .pyc not portable across Python versions
- [The Benefits and Limitations of PYC-only Distribution (Nick Coghlan)](https://www.curiousefficiency.org/posts/2011/04/benefits-and-limitations-of-pyc-only/) -- .pyc-only distribution constraints
- [Google Maps Error Messages (Official)](https://developers.google.com/maps/documentation/javascript/error-messages) -- REQUEST_DENIED causes, billing requirements
- [Google Maps Troubleshooting (Official)](https://developers.google.com/maps/documentation/javascript/troubleshooting) -- API key verification steps
- [How to Fix Google Maps API Billing Error (Storepoint)](https://storepoint.co/help/articles/how-to-fix-a-google-maps-api-billing-error) -- billing setup, expired credit card causes
- Codebase inspection: `build-dist.sh` (rsync excludes, .pyc compilation with `-b` flag, import validation), `docker-compose.yml` (service dependency chain, healthchecks, no `stop_grace_period`), `.github/workflows/ci.yml` (3 jobs, no Playwright, no E2E), `scripts/start.sh` (health polling pattern), `scripts/reset.sh` (interactive volume removal), `infra/Dockerfile` (Python 3.12-slim unpinned), `core/licensing/` (2 .py files compiled to .pyc)

---
*Pitfalls research for: Kerala LPG Delivery Route Optimizer -- v1.4 Ship-Ready QA*
*Researched: 2026-03-08*
