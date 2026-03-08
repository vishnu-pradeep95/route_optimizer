# Stack Research

**Domain:** E2E testing, CI/CD pipeline, operational scripts, distribution verification
**Researched:** 2026-03-08
**Confidence:** HIGH
**Scope:** v1.4 milestone only — "Ship-Ready QA". Existing Python/FastAPI/React/Docker/Playwright stack is locked. This document covers ONLY what is new: Playwright E2E test configuration for CI, test reporters, stop/GC scripts, and clean-install verification tooling.

---

## Context: What Is Already in Place (Locked — Do Not Change)

| Component | Status |
|-----------|--------|
| `@playwright/test` v1.58.2 | Installed in root `package.json` as devDependency. Lock file exists. |
| Playwright browsers | Installed locally at `~/.cache/ms-playwright/` (chromium-1208, firefox-1509, webkit-2248). |
| `.playwright-mcp/` | MCP console logs from manual testing sessions. Not automated test infrastructure. |
| `package.json` (root) | Exists with `@playwright/test` only. No scripts, no config file yet. |
| `package-lock.json` (root) | Exists. Tracks `@playwright/test` + transitive deps. |
| `.github/workflows/ci.yml` | 3 jobs: Python Tests, Dashboard Build, Docker Build. No Playwright job. |
| `scripts/start.sh` | Daily startup script. Health poll, Docker start, diagnosis. |
| `scripts/install.sh` | First-time install. Builds images, waits for health. |
| `scripts/build-dist.sh` | Distribution tarball builder. rsync + .pyc compile + tar. |
| `tests/` (Python) | 420+ pytest unit/integration tests. Fully mocked (no Docker needed). |
| No `playwright.config.ts` | Does not exist yet. Must be created. |
| No `tests/e2e/` directory | No Playwright test files exist yet. |

---

## Recommended Stack

### Playwright E2E Testing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `@playwright/test` | 1.58.2 (already installed) | E2E test framework | Already in `package.json`. Pin to exact version — Playwright Docker images must match this version exactly or browser executables will not be found. |
| `playwright.config.ts` | N/A | Test configuration | Must be created at project root. Configures `baseURL`, `webServer`, reporters, browser selection. |
| Chromium only (in CI) | Bundled with Playwright 1.58.2 | Browser for E2E tests | Use `projects: [{ name: 'chromium' }]` in CI. Chromium-only cuts CI time by 60%+ vs running all three browsers. Cross-browser testing is irrelevant for this app — it targets Chrome on Android (driver PWA) and Chrome on Windows (dashboard). |

### CI/CD Additions

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `mcr.microsoft.com/playwright:v1.58.2-noble` | v1.58.2 | Docker image for CI runner | Official Playwright Docker image with all browsers + system deps pre-installed. Eliminates `npx playwright install --with-deps` step (~30s savings). Version MUST match `@playwright/test` in `package.json`. Noble = Ubuntu 24.04 LTS base. |
| GitHub Actions `actions/upload-artifact@v4` | v4 | Upload test reports | Already used pattern in CI. Upload HTML report + trace files on failure for debugging. 30-day retention is sufficient. |
| Built-in `github` reporter | Bundled | Failure annotations in PR | Playwright's built-in GitHub Actions reporter adds inline failure annotations to PRs. Zero install — just add `['github']` to reporter array. |
| Built-in `html` reporter | Bundled | Detailed test report | Self-contained HTML report uploaded as CI artifact. Open locally to debug failures with traces, screenshots, DOM snapshots. Configure `open: 'never'` for CI. |

### Operational Scripts

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Bash 5.x | Pre-installed | Stop/GC script, verify script | Matches existing script conventions (`set -euo pipefail`, color helpers, `header()`/`info()`/`success()`/`error()` functions). All scripts in `scripts/` use this pattern. |
| `docker system prune` | Docker CLI | Container/image garbage collection | Built-in Docker command. `--filter until=24h` for time-based cleanup. Safer than manual `rm`. |
| `docker compose down --remove-orphans` | Docker Compose CLI | Graceful stop | Stops all project containers and removes orphans from previous compose file versions. Already available. |
| ShellCheck | Pre-installed on ubuntu-latest | Shell script linting in CI | ShellCheck is pre-installed on GitHub Actions `ubuntu-latest` runners. Add a lint step for all `scripts/*.sh` files. Catches quoting bugs, unbound variables, POSIX compatibility issues. |

### Distribution Verification

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Bash + Docker | Already available | Clean-install verification | A script that extracts the tarball to a temp directory, runs `install.sh` inside a fresh Docker container (or validates structure/imports without full Docker orchestration). No new tools needed. |
| `tar -tzf` | coreutils | Tarball content validation | List tarball contents without extracting. Verify expected files are present and no dev artifacts leaked. Already available everywhere. |
| `sha256sum` | coreutils | Tarball integrity check | Generate `.sha256` alongside tarball in `build-dist.sh`. Customer can verify integrity. Already available. |

---

## Playwright Configuration Design

### `playwright.config.ts` — Recommended Structure

The config must handle two modes:
1. **Local development**: Reuse a running `docker compose up` stack at `localhost:8000`
2. **CI**: Start Docker Compose, wait for health, run tests, tear down

Key decisions:

| Decision | Choice | Why |
|----------|--------|-----|
| `webServer.command` | `docker compose up -d && scripts/wait-for-health.sh` | Playwright's `webServer` option can launch Docker Compose. The `url` check waits for the health endpoint. `reuseExistingServer: !process.env.CI` means local dev skips startup if stack is already running. |
| `baseURL` | `http://localhost:8000` | API serves both dashboard (`/dashboard/`) and driver PWA (`/driver/`). Single origin, no CORS issues in tests. |
| `workers` | `1` in CI, default locally | CI stability. This is a small test suite (not hundreds of tests). Single worker avoids Docker Compose resource contention. |
| `retries` | `2` in CI, `0` locally | CI retries catch transient Docker startup race conditions. Locally, retries hide real bugs. |
| `timeout` | `30000` (30s) | Default. Docker Compose services are pre-warmed by `webServer.url` health check. Individual test actions should complete in seconds. |
| `trace` | `'on-first-retry'` | Captures Playwright trace (DOM snapshots, network, console) only when a test is retried. Saves disk space while still providing debugging data for flaky tests. |
| `screenshot` | `'only-on-failure'` | Captures screenshot on failure for CI artifact debugging. |
| Test directory | `tests/e2e/` | Separates Playwright tests from existing `tests/` Python pytest directory. Clear boundary. |
| `testMatch` | `**/*.spec.ts` | Standard Playwright convention. |

### Reporter Configuration for CI

```typescript
reporter: process.env.CI
  ? [['github'], ['html', { open: 'never' }]]
  : [['list']],
```

- **CI**: `github` reporter for PR annotations + `html` for detailed artifact report
- **Local**: `list` reporter for readable terminal output

Do NOT use `@estruyf/github-actions-reporter`. It is a third-party package (last updated over a year ago) that adds a summary table to GitHub Actions. The built-in `github` reporter already provides inline failure annotations, which is more useful for a small test suite. Avoid unnecessary dependencies.

---

## CI Pipeline Design

### New Job: `e2e`

Add a fourth job to `.github/workflows/ci.yml`. This job:
1. Runs on `ubuntu-latest`
2. Uses the Playwright Docker image (`mcr.microsoft.com/playwright:v1.58.2-noble`) as the container
3. Needs Docker Compose for the application stack (Docker-in-Docker or service containers)

**Critical constraint**: The application requires Docker Compose to run (API + DB + OSRM + VROOM). Running E2E tests in CI means either:

- **Option A: Docker-in-Docker** — Run tests inside the Playwright Docker image with Docker Compose available. Complex, fragile.
- **Option B: Direct install on runner** — Install Playwright browsers on the ubuntu-latest runner with `npx playwright install --with-deps chromium`. Docker Compose is available natively on GitHub Actions runners. This is simpler and more reliable.

**Recommendation: Option B (direct install on runner)**. Because this app needs Docker Compose for its own services (db, osrm, vroom, api), running tests on the bare `ubuntu-latest` runner where Docker is natively available is far simpler than Docker-in-Docker. The Playwright Docker image is designed for apps that run outside Docker — not for apps that ARE Docker Compose stacks.

### CI Job Structure

```yaml
e2e:
  name: E2E Tests
  runs-on: ubuntu-latest
  timeout-minutes: 15
  # Only run on push to main (not PRs — too slow, needs Docker builds)
  if: github.event_name == 'push'
  needs: [test, dashboard]  # Run after unit tests pass

  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: '22'
        cache: 'npm'
    - run: npm ci
    - run: npx playwright install --with-deps chromium
    - name: Build and start application
      run: docker compose up -d --build
      env:
        GOOGLE_MAPS_API_KEY: ""  # No geocoding in E2E tests
        API_KEY: "test-api-key"
        ENVIRONMENT: "development"
    - name: Wait for health
      run: |
        timeout 120 bash -c 'until curl -sf http://localhost:8000/health; do sleep 3; done'
    - run: npx playwright test
    - uses: actions/upload-artifact@v4
      if: ${{ !cancelled() }}
      with:
        name: playwright-report
        path: playwright-report/
        retention-days: 30
```

**Why `if: github.event_name == 'push'` only**: E2E tests require building Docker images (~2 min) + starting the full stack (~1-2 min). This is too slow for every PR commit. Unit tests and dashboard build catch most regressions. E2E runs on merge to main as a safety net.

### ShellCheck Job

Add a lightweight lint job for shell scripts:

```yaml
shellcheck:
  name: Shell Lint
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Run ShellCheck
      run: shellcheck scripts/*.sh
```

ShellCheck is pre-installed on ubuntu-latest. No action or install step needed.

---

## Stop/GC Script Design

### No New Tools Needed

The stop and GC script uses only Docker CLI commands that are already available:

| Command | Purpose |
|---------|---------|
| `docker compose down --remove-orphans` | Stop all project containers, remove orphans |
| `docker compose down -v` | Additionally remove named volumes (pgdata, dashboard_assets) — destructive, needs confirmation |
| `docker image prune -f --filter "label=com.docker.compose.project"` | Remove dangling images from this project |
| `docker builder prune -f` | Clear build cache |
| `docker system df` | Show disk usage before/after GC |
| `truncate -s 0` on log files | Clear container logs without removing files |

Pattern: The script should default to a safe stop (no volume deletion) and offer a `--deep` flag for full cleanup including volumes and build cache.

---

## Clean-Install Verification Design

### No New Tools Needed

Verification is a bash script that validates the tarball's contents without requiring a full Docker orchestration:

1. **Structure check**: Extract to temp dir, verify critical files exist (`docker-compose.yml`, `scripts/install.sh`, `scripts/bootstrap.sh`, `infra/Dockerfile`, `.env.example`)
2. **No dev artifacts check**: Verify `.git/`, `tests/`, `.planning/`, `.claude/`, `node_modules/` are NOT in the tarball
3. **License module check**: Verify `core/licensing/__init__.pyc` and `core/licensing/license_manager.pyc` exist, and `.py` source does NOT exist
4. **Import check**: `PYTHONPATH=<extracted> python3 -c "import core.licensing; import core.licensing.license_manager"` (already done in build-dist.sh, but verify after tarball extraction too)
5. **Compose syntax check**: `docker compose -f <extracted>/docker-compose.yml config --quiet` validates the compose file parses

These are all shell commands using existing tools.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| CI Playwright runner | `npx playwright install --with-deps chromium` on ubuntu-latest | `mcr.microsoft.com/playwright:v1.58.2-noble` Docker image | App itself needs Docker Compose. Docker-in-Docker is fragile. Direct install on runner where Docker is native is simpler. |
| CI reporter | Built-in `github` + `html` | `@estruyf/github-actions-reporter` | Third-party dep, last updated 1+ year ago. Built-in `github` reporter provides PR annotations. HTML report covers detailed debugging. No benefit to adding a third-party package. |
| Test browsers | Chromium only | Chromium + Firefox + WebKit | Target users are Chrome on Android (drivers) and Chrome on Windows (office). Cross-browser testing adds CI time for zero coverage gain. |
| Shell linting | ShellCheck (pre-installed) | `shfmt` (formatter) | ShellCheck catches bugs. shfmt enforces style. For 9 scripts, manual style consistency is fine. Add shfmt later if the script count grows. |
| Tarball verification | Bash script with `tar -tzf` | Container-based clean install test | Full Docker orchestration in CI for tarball verification is overkill for v1.4. Structure + import checks catch 95% of distribution bugs. |
| E2E test runner trigger | Push to main only | Every PR | Docker build + stack startup adds 3-5 min to CI. Unit tests + dashboard build on PRs, E2E on merge is the right balance for a solo/small team. |

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Cypress | Playwright is already installed and configured. Cypress adds a second E2E framework with different API, different config, different CI setup. | Playwright (already in package.json) |
| `@playwright/experimental-ct-react` | Component testing framework. Dashboard components are straightforward React + DaisyUI. E2E covers the integration. Unit tests cover logic. Component testing is a third layer with minimal marginal value. | E2E tests for integration, pytest for logic |
| Playwright Test for Visual Regression | `toHaveScreenshot()` requires baseline images checked into git, platform-specific rendering differences, and careful threshold tuning. Overkill for this app. | Manual visual checks for subjective UX |
| `docker-compose-wait` or `wait-for-it.sh` | Third-party wait scripts. A simple `timeout + curl` loop does the same thing in 2 lines of bash. Already proven in `scripts/start.sh`. | `timeout 120 bash -c 'until curl -sf ...; do sleep 3; done'` |
| Testcontainers for Node.js | Programmatic Docker management for tests. Adds complexity — Playwright's `webServer` config handles starting Docker Compose before tests. | Playwright `webServer` config |
| `act` (run GitHub Actions locally) | Local CI simulation tool. Useful for complex workflows, but this CI is simple (4 jobs, no matrix). Run Playwright locally with `npx playwright test` against a running stack. | `npx playwright test` locally |
| New npm packages for reporting | `allure-playwright`, `playwright-html-reporter`, etc. Built-in reporters are sufficient. Adding packages means version management, security updates, and dependency sprawl for marginal formatting improvements. | Built-in `github` + `html` reporters |
| Separate `docker-compose.test.yml` | A test-specific compose override. The existing `docker-compose.yml` works for E2E with environment variable overrides. Adding a second compose file means keeping two files in sync. | Environment variables in CI (`GOOGLE_MAPS_API_KEY=""`, `API_KEY="test-api-key"`) |

---

## Installation

### Root package.json Changes

```bash
# Already installed — no new packages needed for Playwright
npm ls @playwright/test  # Should show 1.58.2

# Install Playwright browsers (if not already cached)
npx playwright install chromium
```

### New npm Scripts to Add

```json
{
  "scripts": {
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui",
    "test:e2e:headed": "playwright test --headed"
  }
}
```

### CI Browser Installation

```bash
# In GitHub Actions (no Docker image needed)
npx playwright install --with-deps chromium
```

The `--with-deps` flag installs system-level dependencies (libgbm, libasound, etc.) that Chromium needs on a fresh Ubuntu runner. The `chromium` argument installs only Chromium (not Firefox + WebKit), saving ~200MB download and ~30s.

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `@playwright/test` 1.58.2 | Node.js 18, 20, 22 | Node 22 is used in CI (matches dashboard job). |
| Playwright browsers (chromium-1208) | `@playwright/test` 1.58.2 only | Browser version is tied to Playwright version. Upgrading Playwright requires `npx playwright install` to get new browsers. |
| `mcr.microsoft.com/playwright:v1.58.2-noble` | Ubuntu 24.04 LTS | Not used in CI (see rationale above), but available if Docker-in-Docker is ever needed. |
| ShellCheck | Pre-installed on ubuntu-latest | Version varies with runner image. No version pinning needed — ShellCheck is backward-compatible for standard checks. |
| `docker compose` | v2.x on ubuntu-latest | GitHub Actions runners include Docker Compose v2. Same as local development. |

---

## Sources

- [Playwright CI documentation](https://playwright.dev/docs/ci) — GitHub Actions setup, Docker image recommendations, caching guidance. HIGH confidence.
- [Playwright CI intro](https://playwright.dev/docs/ci-intro) — Recommended GitHub Actions YAML, `--with-deps` flag, artifact upload. HIGH confidence.
- [Playwright Docker documentation](https://playwright.dev/docs/docker) — Official Docker images, version pinning, `--ipc=host` flag. HIGH confidence.
- [Playwright test reporters documentation](https://playwright.dev/docs/test-reporters) — Built-in reporters (github, html, blob, list, dot), configuration syntax. HIGH confidence.
- [Playwright webServer documentation](https://playwright.dev/docs/test-webserver) — `command`, `url`, `reuseExistingServer`, `timeout` options. HIGH confidence.
- [Microsoft Artifact Registry](https://mcr.microsoft.com/en-us/artifact/mar/playwright) — Docker image tags for v1.58.2-noble. HIGH confidence.
- [@estruyf/github-actions-reporter on npm](https://www.npmjs.com/package/@estruyf/github-actions-reporter) — Third-party reporter, last published 1+ year ago. MEDIUM confidence (not recommended).
- [ShellCheck GitHub Wiki](https://www.shellcheck.net/wiki/GitHub-Actions) — Pre-installed on ubuntu-latest, direct usage. HIGH confidence.
- Existing `ci.yml`, `package.json`, `docker-compose.yml`, `scripts/` in this repo — reviewed directly. HIGH confidence (source of truth).

---

*Stack research for: Kerala LPG Delivery Route Optimizer v1.4 — Ship-Ready QA*
*Researched: 2026-03-08*
