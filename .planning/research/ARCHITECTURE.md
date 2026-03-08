# Architecture Research: v1.4 Ship-Ready QA

**Domain:** E2E Testing Infrastructure, CI/CD Integration, Operational Scripts for Docker Compose app
**Researched:** 2026-03-08
**Confidence:** HIGH

## Existing System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Interfaces                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌───────────────────┐   │
│  │   Dashboard      │  │   Driver PWA    │  │   API Docs        │   │
│  │ React/TS/Vite    │  │ Vanilla JS/HTML │  │   /docs (Swagger) │   │
│  │ :8000/dashboard/ │  │ :8000/driver/   │  │   :8000/docs      │   │
│  └────────┬─────────┘  └────────┬────────┘  └────────┬──────────┘   │
│           │                     │                    │              │
├───────────┴─────────────────────┴────────────────────┴──────────────┤
│                      FastAPI Backend (:8000)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐    │
│  │ Upload   │  │ Optimize │  │ Geocode  │  │ Serve Static     │    │
│  │ /api/*   │  │ VROOM    │  │ Google   │  │ /driver/ /dash/  │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────────────┘    │
│       │              │              │                               │
├───────┴──────────────┴──────────────┴───────────────────────────────┤
│                      Infrastructure Layer                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                          │
│  │ PostGIS  │  │   OSRM   │  │  VROOM   │                          │
│  │ :5432    │  │  :5000   │  │  :3000   │                          │
│  └──────────┘  └──────────┘  └──────────┘                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Current Test Infrastructure

| Layer | What Exists | How It Runs |
|-------|-------------|-------------|
| Python unit tests | `tests/core/`, `tests/apps/`, `tests/scripts/` (211+ tests) | `pytest` in CI, mocks for OSRM/VROOM/Google/PostgreSQL |
| E2E pipeline tests | `tests/test_e2e_pipeline.py` -- full CSV-to-QR flow | `pytest` with FastAPI TestClient, all services mocked |
| Dashboard build check | `npm run build` in CI | Validates TypeScript compiles, React builds |
| Docker smoke test | `docker build` + `docker run` in CI | Verifies API image boots (push to main only) |
| Deploy test | `tests/deploy/Dockerfile.fresh-deploy` | Docker-in-Docker manual test, not in CI |
| **Browser E2E** | **MISSING** | **No Playwright tests exist yet** |

### Current CI Pipeline (`.github/workflows/ci.yml`)

```
Push/PR to main
    ├── Job 1: Python Tests (pytest, 211+ tests, ~30s)
    ├── Job 2: Dashboard Build (npm ci + npm run build, ~45s)
    └── Job 3: Docker Build (push to main only, ~2min)
         ├── Build API image
         ├── Build Dashboard image
         └── Smoke test: API container boots
```

---

## New Components to Add

### 1. Playwright E2E Test Infrastructure

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Playwright E2E Test Layer                         │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  playwright.config.ts                                        │   │
│  │  - baseURL: http://localhost:8000                            │   │
│  │  - projects: chromium only (drivers use Chrome on Android)   │   │
│  │  - retries: 2 in CI, 0 locally                              │   │
│  │  - workers: 1 (tests share Docker state)                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │  Page Objects    │  │  Test Specs     │  │  Fixtures       │    │
│  │  DriverPWAPage  │  │  driver.spec.ts │  │  csv-data.ts    │    │
│  │  DashboardPage  │  │  upload.spec.ts │  │  test base.ts   │    │
│  │  UploadPage     │  │  api.spec.ts    │  │                 │    │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘    │
│           │                    │                     │             │
│           └────────────────────┴─────────────────────┘             │
│                         │                                          │
│                    Playwright Test Runner                           │
│                         │                                          │
│               ┌─────────┴─────────┐                                │
│               │ Docker Compose    │                                 │
│               │ (services on      │                                 │
│               │  localhost:8000)  │                                 │
│               └───────────────────┘                                │
└─────────────────────────────────────────────────────────────────────┘
```

### 2. Stop/GC Script

```
scripts/stop.sh [--gc] [--force]
    │
    ├── Phase 1: Graceful Stop
    │   └── docker compose stop (SIGTERM, 10s grace period)
    │
    ├── Phase 2: Container Cleanup
    │   └── docker compose down --remove-orphans
    │
    ├── Phase 3: Garbage Collection (only with --gc flag)
    │   ├── Remove dangling images: docker image prune -f
    │   ├── Remove build cache: docker builder prune -f
    │   ├── Remove unused networks: docker network prune -f
    │   └── NEVER remove named volumes (pgdata, dashboard_assets)
    │
    └── Phase 4: Report
        └── Print freed space summary
```

---

## Recommended Project Structure

### New Files and Directories

```
routing_opt/
├── playwright.config.ts           # NEW -- Playwright test runner configuration
├── e2e/                           # NEW -- Playwright test directory
│   ├── fixtures/                  # NEW -- Custom test fixtures
│   │   ├── base.ts                #   Extended test object with page objects
│   │   └── test-data.ts           #   CSV file generators, expected data
│   ├── pages/                     # NEW -- Page Object Models
│   │   ├── driver-pwa.page.ts     #   Driver PWA interactions
│   │   ├── upload.page.ts         #   Upload flow interactions
│   │   └── dashboard.page.ts      #   Dashboard interactions (future)
│   ├── upload-flow.spec.ts        # NEW -- CSV upload to route display
│   ├── driver-pwa.spec.ts         # NEW -- Driver PWA full lifecycle
│   ├── api-health.spec.ts         # NEW -- API endpoint smoke tests
│   └── helpers/                   # NEW -- Shared utilities
│       └── docker-health.ts       #   Wait-for-healthy helper
├── scripts/
│   └── stop.sh                    # NEW -- Graceful stop + GC
├── .github/workflows/
│   └── ci.yml                     # MODIFIED -- Add Playwright E2E job
├── package.json                   # MODIFIED -- Add test:e2e scripts
└── tests/                         # EXISTING -- Python tests (untouched)
```

### Structure Rationale

- **`e2e/` at project root, NOT inside `tests/`:** The `tests/` directory is exclusively Python/pytest. Playwright tests use TypeScript, a different runner, and a different config. Mixing them causes test discovery confusion (pytest would try to scan `.ts` files). The `e2e/` name is the Playwright community convention and immediately signals "browser tests."

- **`e2e/pages/` for Page Object Models:** The Driver PWA and Dashboard have distinct interaction patterns. POMs encapsulate selectors and actions so that when the UI changes (as it did in v1.1 and v1.2), test specs remain stable and only the POM updates. This is the Playwright-recommended pattern.

- **`e2e/fixtures/` for shared setup:** Custom fixtures extend Playwright's `test` object with pre-configured page objects and test data generators. This avoids repeating `const driverPage = new DriverPWAPage(page)` in every test file.

- **`playwright.config.ts` at root:** Playwright requires this at the project root (or specified via `--config`). It sits alongside `package.json` where `@playwright/test` is installed. This is non-negotiable.

- **`scripts/stop.sh` in existing `scripts/` directory:** Follows the established pattern of `start.sh`, `install.sh`, `deploy.sh`, `reset.sh`. Uses the same color helpers and error formatting conventions.

---

## Architectural Patterns

### Pattern 1: Docker Compose as External Backend (Not webServer)

**What:** Playwright's `webServer` config is designed to start a single dev server process. This project needs 4+ Docker containers orchestrated by Docker Compose with dependency health checks. Use explicit Docker Compose management instead of `webServer`.

**Why not webServer:** `docker compose up -d` returns immediately (detached). Playwright would poll the URL but cannot verify that all service dependencies (DB healthy, migrations applied, OSRM loaded, VROOM connected) are actually ready. The existing `start.sh` health polling pattern is superior.

**Implementation:**

```typescript
// playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,  // Sequential -- tests share Docker state
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,  // Single worker -- one Docker Compose stack
  reporter: process.env.CI
    ? [['github'], ['html', { open: 'never' }]]
    : [['html', { open: 'on-failure' }]],
  use: {
    baseURL: 'http://localhost:8000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],
  // No webServer -- Docker Compose managed externally.
  // Locally: run start.sh first. In CI: workflow starts Docker Compose.
});
```

**Trade-offs:**
- Pro: Full control over Docker lifecycle, health checking, teardown
- Pro: CI can cache Docker images and volumes across runs
- Con: Requires explicit `docker compose up` before running tests locally
- Con: More custom setup (but matches existing `start.sh` pattern)

### Pattern 2: Page Object Model for Driver PWA

**What:** Encapsulate all Driver PWA selectors and actions into a `DriverPWAPage` class. Tests call high-level methods like `uploadCSV()`, `markStopDone()`, `markStopFailed()` rather than raw selectors.

**When to use:** Always for UI tests that interact with complex pages.

**Example:**

```typescript
// e2e/pages/driver-pwa.page.ts
import { type Page, type Locator, expect } from '@playwright/test';

export class DriverPWAPage {
  readonly page: Page;
  readonly uploadButton: Locator;
  readonly fileInput: Locator;
  readonly deliveryListTab: Locator;
  readonly mapViewTab: Locator;
  readonly doneButton: Locator;
  readonly failButton: Locator;
  readonly navigateButton: Locator;
  readonly progressBar: Locator;

  constructor(page: Page) {
    this.page = page;
    this.uploadButton = page.getByRole('button', { name: /upload/i });
    this.fileInput = page.locator('input[type="file"]');
    this.deliveryListTab = page.getByRole('tab', { name: /delivery list/i });
    this.mapViewTab = page.getByRole('tab', { name: /map/i });
    this.doneButton = page.getByRole('button', { name: /done/i });
    this.failButton = page.getByRole('button', { name: /fail/i });
    this.navigateButton = page.getByRole('link', { name: /navigate/i });
    this.progressBar = page.locator('[role="progressbar"]');
  }

  async goto() {
    await this.page.goto('/driver/');
  }

  async uploadCSV(csvContent: Buffer) {
    await this.fileInput.setInputFiles({
      name: 'orders.csv',
      mimeType: 'text/csv',
      buffer: csvContent,
    });
  }

  async selectVehicle(vehicleId: string) {
    await this.page.getByText(vehicleId).click();
  }

  async markStopDone() {
    await this.doneButton.click();
    await expect(this.page.getByText(/delivered/i)).toBeVisible();
  }

  async markStopFailed(reason: string) {
    await this.failButton.click();
    const dialog = this.page.locator('dialog[open]');
    await expect(dialog).toBeVisible();
    await dialog.getByRole('combobox').selectOption(reason);
    await dialog.getByRole('button', { name: /yes, failed/i }).click();
  }
}
```

### Pattern 3: CI Pipeline with Docker Compose Services

**What:** Add a fourth CI job that starts Docker Compose services, waits for health, runs Playwright, and uploads artifacts. Gate it behind Python tests and Dashboard build passing first.

**Implementation:**

```yaml
# New job in .github/workflows/ci.yml
e2e:
  name: E2E Tests
  runs-on: ubuntu-latest
  needs: [test, dashboard]  # Only run after unit tests + build pass
  steps:
    - uses: actions/checkout@v4

    - name: Set up Node.js 22
      uses: actions/setup-node@v4
      with:
        node-version: '22'
        cache: 'npm'

    - name: Install dependencies
      run: npm ci

    - name: Install Playwright browsers
      run: npx playwright install --with-deps chromium

    - name: Start services
      run: |
        docker compose up -d --build db db-init dashboard-build api
        for i in $(seq 1 40); do
          if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            echo "Services healthy after $((i * 3))s"
            break
          fi
          [ "$i" -eq 40 ] && { docker compose logs; exit 1; }
          sleep 3
        done
      env:
        ENVIRONMENT: development
        RATE_LIMIT_ENABLED: 'false'

    - name: Run Playwright tests
      run: npx playwright test
      env:
        CI: 'true'

    - name: Upload test results
      uses: actions/upload-artifact@v4
      if: ${{ !cancelled() }}
      with:
        name: playwright-report
        path: playwright-report/
        retention-days: 7

    - name: Teardown
      if: always()
      run: docker compose down -v
```

**Trade-offs:**
- Pro: Real integration tests against actual services (not mocks)
- Pro: `needs: [test, dashboard]` avoids wasting CI minutes on broken code
- Con: Slower (~3-5 min for Docker build + startup + tests)
- Con: OSRM data download required for full optimization flow (see OSRM strategy below)

### Pattern 4: Global Setup for Docker Health Verification

**What:** Use Playwright's `globalSetup` to verify Docker Compose is healthy before any tests run. Fail fast with an actionable error message if services are down.

**Example:**

```typescript
// e2e/helpers/docker-health.ts
export async function assertServicesHealthy(baseURL: string): Promise<void> {
  const maxAttempts = 20;
  const interval = 3000;

  for (let i = 0; i < maxAttempts; i++) {
    try {
      const response = await fetch(`${baseURL}/health`);
      if (response.ok) return;
    } catch {
      // Service not ready yet
    }
    await new Promise(r => setTimeout(r, interval));
  }

  throw new Error(
    `Docker Compose services not healthy after ${(maxAttempts * interval) / 1000}s.\n` +
    `Run: docker compose up -d && ./scripts/start.sh`
  );
}
```

---

## Data Flow: E2E Test Execution

### Local Development Flow

```
Developer runs: npx playwright test
    │
    ├── Prerequisite: docker compose up -d (already running via start.sh)
    │
    ├── globalSetup
    │   └── assertServicesHealthy(http://localhost:8000)
    │       ├── OK -> proceed to tests
    │       └── FAIL -> "Run docker compose up -d"
    │
    ├── Test: api-health.spec.ts
    │   ├── GET /health -> 200
    │   ├── GET /driver/ -> serves HTML
    │   ├── GET /api/vehicles -> returns list
    │   └── POST /api/upload-orders with bad file -> 400
    │
    ├── Test: upload-flow.spec.ts
    │   ├── Navigate to /driver/
    │   ├── Upload test CSV via file input
    │   ├── Select vehicle from list
    │   └── Verify route view renders
    │
    ├── Test: driver-pwa.spec.ts
    │   ├── Navigate to /driver/
    │   ├── Verify initial upload screen renders
    │   ├── Upload CSV -> vehicle selection -> route view
    │   ├── Mark stop Done -> verify toast + auto-advance
    │   ├── Mark stop Failed -> verify dialog modal
    │   └── Complete all stops -> verify "Route complete!" banner
    │
    └── Report: playwright-report/index.html (opens on failure)
```

### CI Flow

```
GitHub Actions: Push/PR to main
    │
    ├── Job 1: Python Tests (parallel, ~30s)
    ├── Job 2: Dashboard Build (parallel, ~45s)
    │
    └── Job 3: E2E Tests (needs: [test, dashboard], ~3-5min)
        ├── Checkout code
        ├── Setup Node.js 22
        ├── npm ci
        ├── npx playwright install --with-deps chromium
        ├── docker compose up -d --build db db-init dashboard-build api
        ├── Poll http://localhost:8000/health (max 120s)
        ├── npx playwright test
        ├── Upload playwright-report/ as artifact
        └── docker compose down -v (always, even on failure)
```

### OSRM Data Challenge in CI

The OSRM init container downloads ~150 MB of Kerala OSM data and preprocesses it (~1.5 GB total). This is too slow and too large for every CI run.

**Recommended approach for v1.4: Skip OSRM/VROOM in CI.**

Start only `db`, `db-init`, `dashboard-build`, and `api` in CI. The API will start but optimization requests that need OSRM/VROOM will fail. E2E tests should focus on:

1. Page loads and renders correctly (upload screen, tabs, icons)
2. File upload UI works (selecting file, showing status)
3. API returns appropriate responses/errors
4. Driver PWA navigation, tab switching, and UI interactions
5. Stop status updates (Done/Failed) against pre-seeded or mock data

The full upload-to-optimization flow is already tested by `tests/test_e2e_pipeline.py` with mocked VROOM responses at the Python level. Browser E2E tests add coverage for UI rendering and user interactions, not for the optimization engine.

**Future option:** Cache OSRM data in CI (GitHub Actions cache for `data/osrm/`) to enable full-stack E2E. First run would be ~5min, subsequent runs skip OSRM init.

---

## Component Boundaries

### New Components

| Component | Responsibility | Communicates With | Status |
|-----------|---------------|-------------------|--------|
| `playwright.config.ts` | Test runner configuration | `e2e/` directory, `package.json` | **NEW** |
| `e2e/pages/*.page.ts` | UI interaction encapsulation | Playwright Page API | **NEW** |
| `e2e/*.spec.ts` | Test scenarios | Page objects, fixtures, API endpoints | **NEW** |
| `e2e/fixtures/base.ts` | Extended test object | Page objects, test data generators | **NEW** |
| `e2e/helpers/docker-health.ts` | Health check before tests | Docker Compose services | **NEW** |
| `scripts/stop.sh` | Graceful shutdown + GC | Docker Compose CLI, Docker CLI | **NEW** |

### Modified Components

| Component | Current State | What Changes | Why |
|-----------|--------------|--------------|-----|
| `.github/workflows/ci.yml` | 3 jobs (test, dashboard, docker) | Add 4th job: `e2e` | Browser test coverage in CI |
| `package.json` | Only `@playwright/test` devDep, `test` script echoes error | Add `test:e2e`, `test:e2e:ui`, `test:e2e:report` scripts | Developer convenience |

### Untouched Components

| Component | Why No Change Needed |
|-----------|---------------------|
| `tests/` (all Python tests) | Separate test ecosystem; pytest and Playwright do not interact |
| `tests/conftest.py` | Python fixtures, irrelevant to browser tests |
| `docker-compose.yml` | Services already have health checks; E2E tests target existing ports |
| `docker-compose.prod.yml` | Production config, not used in testing |
| `apps/kerala_delivery/api/main.py` | API is the test target, not modified for testing |
| `apps/kerala_delivery/driver_app/` | Driver PWA is the test target, not modified |
| `infra/Dockerfile` | API Docker image unchanged |
| `scripts/start.sh` | Works as-is for local E2E (services already up) |
| `scripts/install.sh` | Installation flow unrelated to testing |
| `scripts/reset.sh` | Destructive cleanup, separate from stop.sh |

---

## Stop Script Architecture

### Design: `scripts/stop.sh`

Follows established conventions from `start.sh`, `install.sh`, `reset.sh`:

```
scripts/stop.sh [--gc] [--force] [--dry-run]
    │
    ├── Same color helpers (info, success, warn, error, header)
    ├── Same SCRIPT_DIR / PROJECT_ROOT pattern
    │
    ├── stop_services()
    │   ├── docker compose stop (SIGTERM, 10s grace period)
    │   └── docker compose down --remove-orphans
    │
    ├── garbage_collect() (only with --gc flag)
    │   ├── docker container prune -f (remove stopped containers)
    │   ├── docker image prune -f (remove dangling images)
    │   ├── docker builder prune -f (remove build cache)
    │   ├── docker network prune -f (remove unused networks)
    │   └── Report freed space
    │   INVARIANT: NEVER removes named volumes (pgdata, dashboard_assets)
    │
    └── report()
        ├── Verify no project containers running
        └── Print disk usage summary
```

**Key design decisions:**

- **`--gc` is opt-in, NOT default.** Office staff running `stop.sh` should not accidentally delete Docker images they need for the next `start.sh`. Without `--gc`, stop.sh just stops containers.
- **Named volumes are NEVER touched.** `pgdata` (database) and `dashboard_assets` (built dashboard) persist. Volume cleanup is exclusively handled by `reset.sh` which has explicit confirmation prompts.
- **`stop.sh` is the counterpart to `start.sh`.** Simple, safe, fast. `start.sh` brings up, `stop.sh` brings down.
- **`--force` uses `docker compose kill`** for containers that do not respond to SIGTERM within the grace period.
- **`--dry-run` shows what would be cleaned** without actually doing it (matches `reset.sh --dry-run` convention).

### Integration with Existing Scripts

```
┌─────────────────────────────────────────────────────┐
│                 Script Lifecycle                     │
│                                                     │
│  bootstrap.sh -> install.sh -> start.sh             │
│  (first time)   (build)       (daily start)         │
│                                                     │
│  stop.sh     <- NEW counterpart to start.sh         │
│  (end of day / before restart)                      │
│                                                     │
│  reset.sh    (nuclear option: removes everything)   │
│  deploy.sh   (production deployment)                │
│  backup_db.sh (database snapshots)                  │
└─────────────────────────────────────────────────────┘
```

---

## Updated CI Pipeline Architecture

### Target Pipeline

```
Push/PR to main
    │
    ├── Job 1: Python Tests ──────── ~30s
    │   └── pytest tests/ -q --tb=short
    │
    ├── Job 2: Dashboard Build ───── ~45s
    │   └── npm ci && npm run build
    │
    ├── Job 3: Docker Build ──────── ~2min (push to main only)
    │   ├── docker build API image
    │   ├── docker build Dashboard image
    │   └── Smoke test API boots
    │
    └── Job 4: E2E Tests ─────────── ~3-5min (NEW)
        │   needs: [test, dashboard]
        │
        ├── npm ci + playwright install chromium
        ├── docker compose up -d --build db db-init dashboard-build api
        ├── Wait for /health (120s timeout)
        ├── npx playwright test
        ├── Upload playwright-report/ artifact
        └── docker compose down -v
```

### CI Duration Budget

| Job | Current | After v1.4 | Notes |
|-----|---------|------------|-------|
| Python Tests | ~30s | ~30s | No change |
| Dashboard Build | ~45s | ~45s | No change |
| Docker Build | ~2min | ~2min | No change, push only |
| E2E Tests | N/A | ~3-5min | New, gated by test+dashboard |
| **Total (PR)** | **~1.5min** | **~5-6min** | E2E is the new bottleneck |
| **Total (push)** | **~3min** | **~7min** | Docker + E2E in parallel |

Acceptable: 5-6 minutes for PRs is well within GitHub Actions free tier and developer patience thresholds. The `needs` dependency means E2E never runs on code that fails unit tests.

### CI Services Strategy

Start a minimal service set in CI to avoid the OSRM download:

```yaml
docker compose up -d --build db db-init dashboard-build api
```

This starts PostgreSQL, runs migrations, builds the dashboard, and starts the API. OSRM and VROOM are not started, so optimization requests will fail. E2E tests focus on UI rendering, navigation, and API contract validation.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Running Playwright Inside a Docker Container

**What people do:** Build a Docker image with Playwright + browsers, run tests inside a container against other containers on the Docker network.
**Why it's wrong:** Adds ~2 GB image size (Chromium), complex container-to-container networking, difficult debugging (no local browser UI), and slow builds. The official Playwright Docker image exists for CI runners lacking browser system dependencies, not for orchestrating tests against Docker Compose stacks.
**Do this instead:** Install Playwright browsers on the host (CI runner or dev machine) and test against `localhost:8000` where Docker Compose exposes ports.

### Anti-Pattern 2: Using webServer to Start Docker Compose

**What people do:** `webServer: { command: 'docker compose up -d', url: 'http://localhost:8000' }`
**Why it's wrong:** `docker compose up -d` returns immediately (detached mode). Playwright polls the URL, but a 200 from the API does not guarantee that DB migrations finished, OSRM loaded its data, or VROOM connected to OSRM. Intermittent test failures result.
**Do this instead:** Use `globalSetup` or a CI script that explicitly waits for `/health` to return 200. The existing `start.sh` health polling pattern is the right model.

### Anti-Pattern 3: Mixing pytest and Playwright in tests/

**What people do:** Put `.spec.ts` files inside the `tests/` directory alongside `.py` files.
**Why it's wrong:** pytest scans `tests/` and may choke on `.ts` files or `node_modules`. Playwright would need a custom `testDir` anyway. Configuration for `conftest.py` and `playwright.config.ts` living in the same tree is confusing.
**Do this instead:** `tests/` for Python, `e2e/` for Playwright. Each has its own runner, config, and CI job.

### Anti-Pattern 4: Testing All Browsers in CI

**What people do:** Configure Playwright with Chromium, Firefox, and WebKit projects.
**Why it's wrong for this project:** Drivers use Android phones (Chrome). The office employee uses a Windows laptop (Chrome/Edge). Testing Firefox and WebKit triples CI time for zero value.
**Do this instead:** Chromium only. Add other browsers if the user base diversifies.

### Anti-Pattern 5: Stop Script That Removes Volumes

**What people do:** Include `docker volume prune` in a stop/cleanup script.
**Why it's wrong:** This destroys `pgdata` (PostgreSQL database) and `dashboard_assets` (built dashboard). The next `start.sh` would require a full database migration and dashboard rebuild. For an office employee, this is catastrophic data loss.
**Do this instead:** `stop.sh --gc` prunes containers, images, and build cache only. Volume cleanup is exclusively in `reset.sh` which has explicit confirmation prompts.

---

## Integration Points

### E2E Tests <-> Docker Compose Services

| E2E Test Area | Services Required | Notes |
|---------------|-------------------|-------|
| Page load + render | `api` (serves static files) | Dashboard assets from shared volume |
| File upload UI | `api`, `db` | API validates file, stores in DB |
| Route display | `api`, `db` | Pre-seeded route data or data from upload |
| Driver interactions | `api`, `db` | PATCH stop status, real DB writes |
| Full optimization | `api`, `db`, `osrm`, `vroom` | Skip in CI; covered by Python E2E tests |

### E2E Tests <-> Existing Python Tests (Overlap Analysis)

| Python Test | Playwright E2E Equivalent | Overlap |
|-------------|---------------------------|---------|
| `test_e2e_pipeline.py` (API response shape) | `upload-flow.spec.ts` (UI renders response) | Complementary, not redundant |
| `test_api.py` (detailed API behavior) | `api-health.spec.ts` (basic HTTP contract) | Minimal overlap |
| `test_models.py`, `test_vroom_adapter.py` | None | No overlap (pure unit tests) |

### stop.sh <-> Existing Scripts

| Script | Relationship to stop.sh |
|--------|------------------------|
| `start.sh` | Inverse: start brings up, stop brings down |
| `reset.sh` | stop.sh is safe (preserves data); reset.sh is destructive |
| `install.sh` | install.sh builds images; stop.sh --gc cleans old images |
| `deploy.sh` | deploy.sh is for production; stop.sh is for development |
| `backup_db.sh` | Run backup_db.sh BEFORE stop.sh if you want a snapshot |

---

## Suggested Build Order

Based on dependencies between new components:

### Phase 1: Foundation (no dependencies)

1. **`playwright.config.ts`** -- Configuration must exist before any test runs
2. **`scripts/stop.sh`** -- Independent of testing infrastructure; useful immediately
3. **`package.json` updates** -- Add `test:e2e`, `test:e2e:ui`, `test:e2e:report` scripts

### Phase 2: Page Objects (depends on Phase 1)

4. **`e2e/pages/driver-pwa.page.ts`** -- Core POM for the most important test surface
5. **`e2e/pages/upload.page.ts`** -- Upload flow POM
6. **`e2e/fixtures/base.ts`** -- Extended test fixture integrating POMs + test data

### Phase 3: Test Specs (depends on Phase 2)

7. **`e2e/api-health.spec.ts`** -- Simplest test; validates infrastructure works
8. **`e2e/upload-flow.spec.ts`** -- Upload CSV, verify vehicle list and route response
9. **`e2e/driver-pwa.spec.ts`** -- Full driver lifecycle (upload, Done, Failed, all-done)

### Phase 4: CI Integration (depends on Phase 3)

10. **`.github/workflows/ci.yml` update** -- Add E2E job after all tests pass locally

### Build Order Rationale

- **Config before tests:** Playwright will not run without `playwright.config.ts`
- **POMs before specs:** Tests using raw selectors are brittle and will break on UI changes. Build the abstraction layer first.
- **`api-health.spec.ts` first:** The simplest possible test validates that Docker Compose + Playwright integration works before writing complex UI tests.
- **CI last:** Get tests passing locally on a running Docker Compose stack before adding CI complexity. Debugging CI-only failures is expensive.
- **`stop.sh` early:** It is independent of all other components and provides immediate operational value.

---

## Sources

- [Playwright CI Documentation](https://playwright.dev/docs/ci) -- GitHub Actions workflow examples, artifact uploads, sharding strategies
- [Playwright Docker Documentation](https://playwright.dev/docs/docker) -- Official Docker image (`mcr.microsoft.com/playwright:v1.58.2-noble`), `--ipc=host` requirement
- [Playwright Test Configuration](https://playwright.dev/docs/test-configuration) -- `defineConfig`, `webServer`, `projects`, `reporter` options
- [Playwright webServer Documentation](https://playwright.dev/docs/test-webserver) -- `command`, `url`, `reuseExistingServer`, `timeout`, `gracefulShutdown`
- [Playwright Page Object Models](https://playwright.dev/docs/pom) -- Official POM pattern guidance
- [Playwright Fixtures](https://playwright.dev/docs/test-fixtures) -- Custom fixture patterns for test setup/teardown
- [Docker Compose Stop](https://docs.docker.com/reference/cli/docker/compose/stop/) -- Graceful shutdown, SIGTERM behavior, `stop_grace_period`
- [Playwright in CI with GitHub Actions and Docker](https://www.roybakker.dev/blog/playwright-in-ci-with-github-actions-and-docker-endtoend-guide) -- End-to-end CI setup patterns
- [Dockerized E2E Tests with GitHub Actions](https://lachiejames.com/elevate-your-ci-cd-dockerized-e2e-tests-with-github-actions/) -- Docker Compose + Playwright CI integration
- [Organizing Playwright Tests Effectively](https://dev.to/playwright/organizing-playwright-tests-effectively-2hi0) -- Directory layout and test organization
- Existing codebase: `ci.yml`, `docker-compose.yml`, `docker-compose.prod.yml`, `tests/conftest.py`, `tests/test_e2e_pipeline.py`, `scripts/start.sh`, `scripts/reset.sh`, `package.json`

---
*Architecture research for: v1.4 Ship-Ready QA -- Playwright E2E tests, CI integration, stop/GC scripts*
*Researched: 2026-03-08*
