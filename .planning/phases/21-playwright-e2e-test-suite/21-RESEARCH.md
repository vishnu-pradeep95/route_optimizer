# Phase 21: Playwright E2E Test Suite - Research

**Researched:** 2026-03-08
**Domain:** End-to-end browser testing with Playwright against a live Docker stack
**Confidence:** HIGH

## Summary

This phase adds automated Playwright E2E tests covering four feature areas: API endpoints, Driver PWA flow, Dashboard route display, and license validation. The project already has `@playwright/test@1.58.2` installed with Chromium browsers cached, and a running Docker stack at `localhost:8000`. No `playwright.config.ts` or `e2e/` directory exists yet -- both need to be created from scratch.

The main technical challenges are: (1) the test CSV must produce routes via the full geocoding + VROOM optimization pipeline, which requires a working Google Maps API key passed via environment variable; (2) the license validation test requires restarting the API container with `ENVIRONMENT=production` and no valid license key to trigger 503 responses; (3) the Driver PWA uses vanilla JS with vanilla HTML elements (not React), so locators target raw DOM elements like `<dialog>`, `<select>`, and elements identified by `id` attributes; (4) the Dashboard is a React SPA served from a Docker volume at `/dashboard/`, requiring the dashboard-build container to have completed successfully.

**Primary recommendation:** Create four spec files (`api.spec.ts`, `driver-pwa.spec.ts`, `dashboard.spec.ts`, `license.spec.ts`) in `e2e/` with a shared `playwright.config.ts` at project root, sequential test ordering within files, and a shared test CSV fixture using real Vatakara addresses.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Google Maps API key provided and working -- tests use real geocoding against real Vatakara addresses
- API key passed via environment variable (never hardcoded in test files or config)
- Tests must detect and clearly report missing/invalid API key at startup -- not cryptic failures
- DOM presence + key text content for visual features (headings, button labels, status messages, data values)
- UI state change AND separate API verification for action flows (mark done/fail) -- verify both UI update and DB persistence
- Full JSON schema validation for API endpoint tests -- verify status codes and complete response structure
- Full response validation for license tests -- verify 503 status, error message text, and additional fields (expiry, grace period)
- Shared state per spec file -- upload CSV once in beforeAll, all tests in file run against same data
- Sequential story within spec files -- tests run in order, each building on the previous state
- fullyParallel: false within spec files
- One spec file per feature area: `api.spec.ts`, `driver-pwa.spec.ts`, `dashboard.spec.ts`, `license.spec.ts`
- Directory: `e2e/` at project root
- Shared test CSV in `e2e/fixtures/test-orders.csv` with real Vatakara addresses
- Shared utilities in `e2e/helpers/setup.ts`

### Claude's Discretion
- Cross-file parallelism configuration
- DB cleanup strategy (globalSetup vs fresh stack assumption)
- Timeout values and retry configuration
- Viewport settings per spec file (mobile for driver PWA, desktop for dashboard)
- Failure artifact capture (screenshots, HTML reports)
- Whether VROOM/OSRM are required for all tests or only route-dependent ones
- Graceful handling when API key is missing (skip vs fail)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TEST-01 | Playwright E2E tests verify all API endpoints return expected status codes against running Docker stack | `api.spec.ts` uses `request.get()`/`request.post()` with JSON schema validation against all 12+ endpoints |
| TEST-02 | Playwright E2E tests cover full Driver PWA flow: upload CSV -> vehicle select -> route view -> mark done/fail -> all-done banner | `driver-pwa.spec.ts` uses mobile viewport (393x851), sequential story pattern with fileChooser for CSV upload, DOM assertions for each state transition |
| TEST-03 | Playwright E2E tests verify Dashboard: route cards render, QR sheet generates, map loads after upload | `dashboard.spec.ts` uses desktop viewport, uploads via API in beforeAll, then navigates dashboard to verify route cards, QR sheet link, and Leaflet map container |
| TEST-04 | Playwright E2E tests verify license validation: expired/missing/invalid keys return 503 | `license.spec.ts` uses `request.get()` against a production-mode API container with invalid/missing license, verifying 503 status and response body fields |
| TEST-05 | All existing 420 pytest unit tests pass in CI | No E2E infrastructure changes should modify Python source code; pytest tests run independently via `pytest tests/ -x` |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @playwright/test | 1.58.2 | E2E test framework | Already in devDependencies, browsers installed, industry standard for web E2E |
| TypeScript | Built into Playwright | Type-safe test files | Playwright has first-class TS support, no separate tsconfig needed for tests |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Node.js fs/path | Built-in | File fixture loading | Reading test CSV for upload, resolving fixture paths |
| Playwright APIRequestContext | Built into @playwright/test | API-level testing | Direct HTTP assertions without browser overhead (api.spec.ts, license.spec.ts) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Playwright APIRequestContext | Supertest/axios | Playwright's built-in API testing shares auth context with browser tests, no extra dependency |
| Separate test runner | Jest + Playwright | Playwright's own test runner has better parallel/retry/reporter support than Jest + pw library |

**Installation:**
Already installed. Browser install may need:
```bash
npx playwright install chromium
```

## Architecture Patterns

### Recommended Project Structure
```
e2e/
├── fixtures/
│   └── test-orders.csv          # Real Vatakara addresses in CDCMS format
├── helpers/
│   └── setup.ts                 # Upload helper, cleanup, API key validation
├── api.spec.ts                  # TEST-01: All API endpoints
├── driver-pwa.spec.ts           # TEST-02: Full driver PWA flow
├── dashboard.spec.ts            # TEST-03: Dashboard route display
└── license.spec.ts              # TEST-04: License validation 503
playwright.config.ts             # At project root (alongside package.json)
```

### Pattern 1: Sequential Story Pattern (for spec files)
**What:** Tests within a spec file run in order, sharing state from a `beforeAll` upload. Each test builds on the previous state (upload -> view -> interact -> verify completion).
**When to use:** Driver PWA and Dashboard specs where the user flow is inherently sequential.
**Example:**
```typescript
// Source: Playwright docs + CONTEXT.md decision
import { test, expect } from '@playwright/test';

test.describe.configure({ mode: 'serial' });

test.describe('Driver PWA Flow', () => {
  test.beforeAll(async ({ browser }) => {
    // Upload CSV once, share context across tests
  });

  test('uploads CSV and shows vehicle selector', async ({ page }) => {
    // First step in the story
  });

  test('selects vehicle and shows route view', async ({ page }) => {
    // Builds on previous state
  });

  test('marks stop as delivered', async ({ page }) => {
    // Builds on previous state
  });
});
```

### Pattern 2: API-Level Testing (for api.spec.ts and license.spec.ts)
**What:** Use Playwright's `request` fixture (APIRequestContext) for direct HTTP calls without browser overhead.
**When to use:** API endpoint validation, license enforcement testing.
**Example:**
```typescript
// Source: Playwright APIRequestContext docs
import { test, expect } from '@playwright/test';

test('GET /health returns 200 with status ok', async ({ request }) => {
  const response = await request.get('/health');
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body).toMatchObject({
    status: 'ok',
    service: 'kerala-lpg-optimizer',
    version: expect.any(String),
  });
});
```

### Pattern 3: File Upload via FileChooser (for browser-based upload tests)
**What:** Use Playwright's `page.waitForEvent('filechooser')` to handle file input elements that are triggered by button clicks.
**When to use:** Driver PWA upload (button triggers hidden `<input type="file">`), Dashboard drag-and-drop zone.
**Example:**
```typescript
// Source: Playwright FileChooser docs
import path from 'path';

const fileChooserPromise = page.waitForEvent('filechooser');
await page.getByRole('button', { name: 'Upload Delivery List' }).click();
const fileChooser = await fileChooserPromise;
await fileChooser.setFiles(path.join(__dirname, 'fixtures', 'test-orders.csv'));
```

### Pattern 4: API Upload via Multipart Request (for beforeAll setup)
**What:** Upload CSV via API directly (bypassing UI) to set up test data in beforeAll hooks.
**When to use:** Dashboard spec and API spec where you need routes to exist but don't need to test the upload UI.
**Example:**
```typescript
// Source: Playwright APIRequestContext docs
import fs from 'fs';
import path from 'path';

const csvBuffer = fs.readFileSync(path.join(__dirname, 'fixtures', 'test-orders.csv'));
const response = await request.post('/api/upload-orders', {
  headers: { 'X-API-Key': process.env.API_KEY || '' },
  multipart: {
    file: {
      name: 'test-orders.csv',
      mimeType: 'text/csv',
      buffer: csvBuffer,
    },
  },
});
expect(response.status()).toBe(200);
```

### Anti-Patterns to Avoid
- **Hard-coded waits (`page.waitForTimeout`):** Use web-first assertions (`expect(locator).toBeVisible()`) which auto-retry. Hard-coded waits are flaky and slow.
- **CSS class selectors for assertions:** The project uses `tw:` prefixed Tailwind classes that are styling-only. Use `getByRole`, `getByText`, `getByTestId`, or element IDs instead.
- **Testing third-party maps rendering:** Leaflet map tiles load from external CDN. Assert the map container exists, not that tiles rendered correctly.
- **Sharing browser context across spec files:** Each spec file should get its own browser context to maintain isolation. Share state WITHIN a file via `test.describe.configure({ mode: 'serial' })`.
- **Not clearing localStorage between PWA tests:** The Driver PWA caches route data in localStorage. Clear it in `beforeAll` or `beforeEach` to prevent stale state from previous test runs.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| File upload in tests | Custom fetch() with FormData | Playwright's `fileChooser.setFiles()` or `request.post({ multipart })` | Handles content-type boundaries, file encoding automatically |
| Waiting for UI updates | `setTimeout` / `sleep` loops | `expect(locator).toBeVisible()` / `expect(locator).toHaveText()` | Auto-retries with configurable timeout, no flaky timing |
| JSON schema validation | Manual field-by-field checks | `expect(body).toMatchObject({...})` with `expect.any()` matchers | Readable, handles nested objects, gives clear diff on failure |
| Test data cleanup | Custom SQL scripts | Truncate via API or Docker restart between test suites | Avoids DB connection complexity in test code |
| Screenshot on failure | Manual `page.screenshot()` calls | `playwright.config.ts` `use: { screenshot: 'only-on-failure' }` | Automatic, captures at exact failure point, saved in test-results |
| HTML test report | Custom reporter | `reporter: 'html'` in config | Built-in, includes traces, retries, screenshots |

**Key insight:** Playwright's built-in features cover test artifacts, retries, parallelism, and reporting. Custom infrastructure is rarely needed.

## Common Pitfalls

### Pitfall 1: API Key Not Set for Upload Endpoints
**What goes wrong:** Upload endpoint returns 401 because `X-API-Key` header is missing. Tests fail cryptically with "Upload failed" errors.
**Why it happens:** The API requires `X-API-Key` header on all POST endpoints when `API_KEY` env var is set (which it is -- `8qZSN7Ln8...` in `.env`).
**How to avoid:** Read `API_KEY` from environment in test setup. Pass it as header in all POST requests. Validate at startup with a clear error message.
**Warning signs:** 401 responses on any POST endpoint.

### Pitfall 2: Driver PWA localStorage Caching
**What goes wrong:** Tests find stale route data from a previous run because the PWA caches `vehicle_id`, `route_data`, and `routes_list` in localStorage.
**Why it happens:** The PWA's `DOMContentLoaded` handler restores cached state, bypassing the upload screen entirely.
**How to avoid:** Clear localStorage in `beforeAll` before starting the upload flow: `await page.evaluate(() => localStorage.clear())`.
**Warning signs:** Upload screen is skipped, tests see route data from a previous session.

### Pitfall 3: License Test Requires Production Mode
**What goes wrong:** License tests pass even with invalid/missing keys because the API runs in `ENVIRONMENT=development` by default, which overrides invalid licenses to VALID.
**Why it happens:** The API lifespan handler (main.py line 173-192) explicitly skips license enforcement in dev mode.
**How to avoid:** License tests must either: (a) use `request.get()` against a separately-started API container with `ENVIRONMENT=production`, or (b) mock the license state. Option (a) is more realistic. The test can use Docker exec or a dedicated docker-compose override.
**Warning signs:** License tests always pass regardless of license state.

### Pitfall 4: Dashboard Served from Docker Volume
**What goes wrong:** Navigating to `http://localhost:8000/dashboard/` returns 404 or empty page.
**Why it happens:** The Dashboard is a React SPA built by the `dashboard-build` container into a shared Docker volume (`dashboard_assets`). If dashboard-build failed or hasn't run, the volume is empty.
**How to avoid:** Verify dashboard-build container completed successfully before running dashboard tests. Can check with `docker compose ps dashboard-build` or probe `http://localhost:8000/dashboard/` in a health check.
**Warning signs:** 404 at `/dashboard/`, empty HTML response.

### Pitfall 5: Geocoding Failures Due to Invalid Google Maps API Key
**What goes wrong:** CSV upload returns 200 but with `orders_assigned: 0` because all addresses failed geocoding.
**Why it happens:** `GOOGLE_MAPS_API_KEY` in `.env` is set to `your-key-here` (placeholder) or the key has been invalidated (STATE.md notes "REQUEST_DENIED" issue).
**How to avoid:** Validate the Google Maps API key at test startup by checking the upload response for `failed_geocoding > 0` or `orders_assigned == 0` and providing a clear error message.
**Warning signs:** `orders_assigned: 0`, `failed_geocoding: N` where N = total rows, `ZERO_RESULTS` or `REQUEST_DENIED` in failure reasons.

### Pitfall 6: Sequential Tests Breaking on Timing
**What goes wrong:** The Driver PWA uses `setTimeout` for toast animations (1500ms) and auto-advance after marking done/failed. Tests that click too quickly miss state transitions.
**Why it happens:** `updateStatus()` calls `setTimeout(() => renderStopList(), 1500)` for toast visibility before re-rendering.
**How to avoid:** After clicking "Done" or "Yes, Failed", wait for the toast to appear AND disappear, then assert on the new state. Use `expect(locator).toBeVisible()` followed by `expect(locator).toBeHidden()` or just wait for the next expected state.
**Warning signs:** Tests pass locally but fail in CI due to timing differences.

### Pitfall 7: VROOM/OSRM Dependency for Route Generation
**What goes wrong:** Upload succeeds but returns zero vehicles used or empty routes because VROOM/OSRM services are not running.
**Why it happens:** Route optimization requires OSRM (travel time matrix) and VROOM (solver). Without them, the optimizer has no distance data.
**How to avoid:** Docker compose health checks should verify OSRM and VROOM are running before tests start. The Docker stack has healthchecks configured but tests should verify.
**Warning signs:** `vehicles_used: 0` in upload response, optimizer timeout errors in API logs.

## Code Examples

### playwright.config.ts (Recommended Configuration)
```typescript
// Source: Playwright docs + project-specific decisions
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false, // Sequential within files (CONTEXT.md decision)
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1, // Sequential across files — shared DB state
  reporter: [
    ['html', { open: 'never' }],
    ['list'],
  ],
  timeout: 60_000, // 60s per test — geocoding can be slow
  use: {
    baseURL: 'http://localhost:8000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    extraHTTPHeaders: {
      'X-API-Key': process.env.API_KEY || '',
    },
  },
  projects: [
    {
      name: 'api',
      testMatch: 'api.spec.ts',
    },
    {
      name: 'driver-pwa',
      testMatch: 'driver-pwa.spec.ts',
      use: {
        viewport: { width: 393, height: 851 }, // Mobile viewport
      },
    },
    {
      name: 'dashboard',
      testMatch: 'dashboard.spec.ts',
      use: {
        viewport: { width: 1280, height: 800 }, // Desktop viewport
      },
    },
    {
      name: 'license',
      testMatch: 'license.spec.ts',
    },
  ],
});
```

### Test CSV Fixture Format (CDCMS Tab-Separated)
```
# Based on data/sample_cdcms_export.csv — real CDCMS export format
# Tab-separated, specific column names (OrderNo, ConsumerAddress, etc.)
# Use 3-5 orders for fast test execution while covering multi-stop routes
# Addresses must be real Vatakara region locations for geocoding to succeed
```

### API Key Validation in Setup Helper
```typescript
// e2e/helpers/setup.ts
import { expect } from '@playwright/test';
import type { APIRequestContext } from '@playwright/test';

export async function validateApiKey(request: APIRequestContext): Promise<void> {
  const apiKey = process.env.API_KEY;
  if (!apiKey) {
    throw new Error(
      'API_KEY environment variable is not set. ' +
      'E2E tests require it for authenticated endpoints. ' +
      'Set it in .env or export API_KEY=...'
    );
  }
}

export async function uploadTestCSV(
  request: APIRequestContext,
  csvPath: string,
): Promise<Record<string, unknown>> {
  const fs = await import('fs');
  const csvBuffer = fs.readFileSync(csvPath);
  const response = await request.post('/api/upload-orders', {
    multipart: {
      file: {
        name: 'test-orders.csv',
        mimeType: 'text/csv',
        buffer: csvBuffer,
      },
    },
  });
  expect(response.status()).toBe(200);
  const body = await response.json();

  // Detect geocoding failures early with clear message
  if (body.orders_assigned === 0) {
    const reasons = (body.failures || [])
      .map((f: { reason: string }) => f.reason)
      .join(', ');
    throw new Error(
      `Upload succeeded but 0 orders were assigned. ` +
      `Likely cause: invalid GOOGLE_MAPS_API_KEY. ` +
      `Failure reasons: ${reasons || 'unknown'}`
    );
  }

  return body;
}
```

### Driver PWA File Upload via FileChooser
```typescript
// Source: Playwright FileChooser API
test('uploads CSV and shows vehicle selector', async ({ page }) => {
  await page.goto('/driver/');
  await page.evaluate(() => localStorage.clear());
  await page.reload();

  // Wait for upload section to be visible
  await expect(page.locator('#upload-section')).toBeVisible();
  await expect(page.getByText('Today\'s Deliveries')).toBeVisible();

  // Trigger file upload via hidden input
  const fileChooserPromise = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: 'Upload Delivery List' }).click();
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles(path.join(__dirname, 'fixtures', 'test-orders.csv'));

  // Wait for upload to complete and vehicle selector to appear
  await expect(page.locator('#vehicle-selector')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('Select Your Vehicle')).toBeVisible();
});
```

### License 503 Verification
```typescript
// Source: main.py license enforcement middleware (lines 337-383)
// License enforcement only works in ENVIRONMENT=production
// The API returns 503 with { detail, license_status } on invalid license
test('returns 503 with invalid license in production mode', async ({ request }) => {
  // This test assumes the API has been restarted with:
  //   ENVIRONMENT=production LICENSE_KEY=invalid-key
  const response = await request.get('/api/routes');
  expect(response.status()).toBe(503);
  const body = await response.json();
  expect(body).toMatchObject({
    detail: expect.stringContaining('License expired or invalid'),
    license_status: 'invalid',
  });
});
```

### Dashboard Route Card Assertions
```typescript
// Source: UploadRoutes.tsx (lines 654-684)
test('shows route cards with vehicle data', async ({ page }) => {
  await page.goto('/dashboard/');
  // Route cards should appear (loaded from existing routes on mount)
  await expect(page.locator('.route-cards')).toBeVisible({ timeout: 15_000 });

  // Each route card has vehicle ID badge and driver name
  const firstCard = page.locator('.route-cards .tw\\:card').first();
  await expect(firstCard).toBeVisible();
  // Vehicle ID displayed as badge
  await expect(firstCard.locator('.tw\\:badge')).toBeVisible();
  // Stats: stops, km, min, kg
  await expect(firstCard.getByText('stops')).toBeVisible();
  await expect(firstCard.getByText('km')).toBeVisible();
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `page.waitForSelector()` + manual assertions | Web-first assertions (`expect(locator).toBeVisible()`) | Playwright 1.20+ | Auto-retry, less flaky, cleaner syntax |
| `page.$eval()` for DOM queries | Role-based locators (`getByRole`, `getByText`) | Playwright 1.27+ | More resilient to DOM changes |
| Separate test runner (Jest/Mocha) | Built-in `@playwright/test` runner | Standard since 1.0 | Better parallel support, fixtures, reporters |
| Manual multipart encoding | `request.post({ multipart })` | Playwright 1.18+ | No need for FormData construction in Node |
| `page.waitForTimeout(ms)` | `expect(locator).toBeVisible({ timeout })` | Best practice since 1.0 | Eliminates hard-coded waits |

**Deprecated/outdated:**
- `page.waitForSelector()`: Still works but `expect(locator)` assertions are preferred
- `page.$(selector)`: Use `page.locator(selector)` instead (no await needed until action)
- `expect(await locator.isVisible()).toBe(true)`: Use `await expect(locator).toBeVisible()` (auto-retry)

## Critical Implementation Details

### License Test Strategy
The license middleware (main.py lines 337-383) only enforces license validation in `ENVIRONMENT=production`. In dev mode, invalid licenses are overridden to VALID. The license test must:

1. **Option A (Recommended):** Use Docker to restart the API container with production environment:
   ```bash
   docker compose exec api sh -c "ENVIRONMENT=production LICENSE_KEY=bogus uvicorn ..."
   ```
   This is complex because the container needs to be restarted.

2. **Option B (Simpler):** Use `docker compose exec` to modify the `app.state.license_info` at runtime via a test-only endpoint, or directly test the API middleware by sending requests after manipulating Docker environment.

3. **Option C (Most practical):** Create a separate `docker-compose.license-test.yml` override that sets `ENVIRONMENT=production` and removes the license key, then use `docker compose -f ... up` to start a temporary production-mode API container on a different port (e.g., 8001) for license tests only.

The 503 response body is:
```json
{
  "detail": "License expired or invalid. Contact support.",
  "license_status": "invalid"
}
```

Health endpoint (`/health`) is always allowed even with invalid license, but gets an `X-License-Status` response header.

### API Key Authentication
All POST endpoints and sensitive GET endpoints (`/api/vehicles`, `/api/telemetry/*`) require `X-API-Key` header matching the `API_KEY` env var (`8qZSN7Ln8HFcPNDuZC7PZZ4hu0n8F37u` in .env). Tests must:
- Read `API_KEY` from process.env or .env file
- Include it in `extraHTTPHeaders` in playwright.config.ts
- The Driver PWA reads the key from `localStorage('lpg_api_key')` -- tests must set this before performing POST actions

### Driver PWA DOM Structure (Key Selectors)
| Element | Selector | Notes |
|---------|----------|-------|
| Upload section | `#upload-section` | Contains upload button, hidden file input |
| Upload button | `button.upload-btn` or `getByRole('button', { name: 'Upload Delivery List' })` | Triggers hidden `#file-input` |
| File input | `#file-input` | Hidden, accepts `.csv,.xlsx,.xls` |
| Upload status | `#upload-status` | Shows progress/result text |
| Vehicle selector | `#vehicle-selector` | Has `.visible` class when shown |
| Vehicle buttons | `button.vehicle-btn` | One per vehicle, shows driver name + stats |
| Route view | `#route-view` | Main delivery screen |
| Stop list | `#stop-list` | Contains stop cards |
| Progress bar | `#progress-bar` | Colored segments |
| Header stats | `#header-stats` | "X of Y delivered" text |
| Done button | `button.btn-done` | Per-stop, calls `markDelivered()` |
| Fail button | `button.btn-fail` | Per-stop, calls `markFailed()` |
| Fail dialog | `dialog#fail-dialog` | Native `<dialog>`, opened via `.showModal()` |
| Fail reason select | `select#fail-reason` | Dropdown with 5 options |
| Fail confirm | `button#fail-confirm` | "Yes, Failed" button |
| Fail cancel | `button#fail-cancel` | "Cancel" button |
| All-done banner | `#all-done-banner` | Injected dynamically, has `.all-done-banner` class |
| Banner close | `button.all-done-close` | X button to dismiss |
| Call office FAB | `#call-office-fab` | Fixed bottom-right, phone icon |
| Navigate button | `button.btn-navigate` or link with Google Maps URL | Opens Google Maps |

### Dashboard DOM Structure (Key Selectors)
| Element | Selector | Notes |
|---------|----------|-------|
| Upload section | `.upload-section` | Drag-and-drop zone |
| Drop zone | `.drop-zone` | File drop area |
| Route cards container | `.route-cards` | Contains vehicle cards |
| Vehicle card | `.tw\:card` inside `.route-cards` | DaisyUI card component |
| Vehicle ID badge | `.tw\:badge.tw\:badge-neutral` | Shows VEH-XX |
| Stats (stops/km/min/kg) | `.numeric` spans | Inside each card |
| Print QR Sheet link | `a.print-sheet-btn` | Opens `/api/qr-sheet` in new tab |
| QR section | `.qr-section` | Visible when card expanded |
| Map container | Leaflet `.leaflet-container` | On LiveMap page |

### Test CSV Requirements
The test CSV must be in CDCMS tab-separated format (matching `data/sample_cdcms_export.csv`):
- Tab-separated (not comma-separated)
- Must have columns: `OrderNo`, `ConsumerAddress`, plus other CDCMS columns
- Addresses must be real Vatakara region addresses that Google Maps can geocode
- Use 3-5 orders minimum (enough for multi-vehicle routing, fast enough for tests)
- Use the same structure as `data/sample_cdcms_export.csv` (19 columns)

### Timeout Recommendations
| Operation | Recommended Timeout | Rationale |
|-----------|-------------------|-----------|
| CSV upload + geocoding + optimization | 60,000ms | Google Maps geocoding for 3-5 addresses can take 5-15 seconds |
| Vehicle selector appearance | 30,000ms | Depends on upload completion |
| Route view rendering | 10,000ms | Local data, should be fast |
| Toast appearance | 3,000ms | CSS animation: 200ms in + 1200ms visible + 300ms out |
| All-done banner | 5,000ms | Appears after re-render triggered by setTimeout(1500) |
| Dashboard route card load | 15,000ms | Fetches routes + details + QR codes in parallel |
| API endpoint response | 10,000ms | Most are fast, but first request may be slow (cold start) |
| QR sheet generation | 15,000ms | Server-side QR + HTML rendering |

## Open Questions

1. **Google Maps API Key Validity**
   - What we know: STATE.md notes the key was previously showing REQUEST_DENIED. CONTEXT.md says "Google Maps API key provided and working."
   - What's unclear: Whether the key has been fixed since the STATE.md entry.
   - Recommendation: Test setup helper should validate the key by checking upload response. If geocoding fails, provide a clear error message pointing to the API key.

2. **License Test Container Strategy**
   - What we know: License enforcement requires `ENVIRONMENT=production`. The running stack uses `ENVIRONMENT=development`.
   - What's unclear: Best approach to test 503 behavior without disrupting the running stack.
   - Recommendation: Use a docker-compose override file to start a second API container on port 8001 with `ENVIRONMENT=production` and no valid license. The license spec targets this separate container. Alternatively, use `docker compose exec` to restart the API process with modified env vars.

3. **Database State Between Spec Files**
   - What we know: Upload creates routes in PostgreSQL. Multiple spec files may conflict if they all upload.
   - What's unclear: Whether the DB needs truncation between spec files.
   - Recommendation: Run spec files sequentially (workers: 1). API spec uploads first and validates responses. Dashboard spec can reuse existing routes (loaded on mount). Driver PWA spec uploads its own CSV. License spec doesn't need routes.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | @playwright/test 1.58.2 |
| Config file | `playwright.config.ts` (Wave 0 -- needs creation) |
| Quick run command | `npx playwright test --project=api` |
| Full suite command | `npx playwright test` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TEST-01 | All API endpoints return expected status codes | E2E (API) | `npx playwright test e2e/api.spec.ts` | Wave 0 |
| TEST-02 | Driver PWA upload-to-delivery flow | E2E (browser) | `npx playwright test e2e/driver-pwa.spec.ts` | Wave 0 |
| TEST-03 | Dashboard route cards, QR sheet, map | E2E (browser) | `npx playwright test e2e/dashboard.spec.ts` | Wave 0 |
| TEST-04 | License validation returns 503 | E2E (API) | `npx playwright test e2e/license.spec.ts` | Wave 0 |
| TEST-05 | 420+ pytest tests pass | unit (Python) | `pytest tests/ -x --tb=short` | Existing (420+ tests) |

### Sampling Rate
- **Per task commit:** `npx playwright test --project=api` (fastest, API-only)
- **Per wave merge:** `npx playwright test` (full suite)
- **Phase gate:** Full suite green + `pytest tests/ -x --tb=short` before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `playwright.config.ts` -- Playwright configuration at project root
- [ ] `e2e/fixtures/test-orders.csv` -- Test data in CDCMS format with real Vatakara addresses
- [ ] `e2e/helpers/setup.ts` -- Shared upload helper, API key validation, cleanup utilities
- [ ] `e2e/api.spec.ts` -- API endpoint tests (TEST-01)
- [ ] `e2e/driver-pwa.spec.ts` -- Driver PWA flow tests (TEST-02)
- [ ] `e2e/dashboard.spec.ts` -- Dashboard display tests (TEST-03)
- [ ] `e2e/license.spec.ts` -- License validation tests (TEST-04)
- [ ] `package.json` update -- Add `"test:e2e"` script

## Sources

### Primary (HIGH confidence)
- Playwright official docs: [Configuration](https://playwright.dev/docs/test-configuration) -- config options, defaults
- Playwright official docs: [Best Practices](https://playwright.dev/docs/best-practices) -- locator strategies, assertions
- Playwright official docs: [APIRequestContext](https://playwright.dev/docs/api/class-apirequestcontext) -- multipart upload, HTTP testing
- Playwright official docs: [FileChooser](https://playwright.dev/docs/api/class-filechooser) -- file upload in browser tests
- Project source: `apps/kerala_delivery/api/main.py` -- all API endpoints, license middleware, auth
- Project source: `apps/kerala_delivery/driver_app/index.html` -- DOM structure, JS functions
- Project source: `apps/kerala_delivery/dashboard/src/pages/UploadRoutes.tsx` -- Dashboard upload + route cards
- Project source: `core/licensing/license_manager.py` -- license validation logic
- Project source: `data/sample_cdcms_export.csv` -- CDCMS format reference

### Secondary (MEDIUM confidence)
- Installed package: `@playwright/test@1.58.2` verified in `node_modules`
- Chromium browser cached at `/home/vishnu/.cache/ms-playwright/chromium-1208`
- Docker stack running: all 4 services healthy (lpg-api, lpg-db, osrm-kerala, vroom-solver)

### Tertiary (LOW confidence)
- Google Maps API key status: CONTEXT.md says "working" but STATE.md has a blocker about REQUEST_DENIED. Needs runtime validation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- Playwright already installed, version verified, browsers cached
- Architecture: HIGH -- Based on direct source code analysis and Playwright official docs
- Pitfalls: HIGH -- Identified from actual code paths (license dev mode bypass, localStorage caching, API key auth)
- DOM selectors: HIGH -- Extracted directly from source HTML/TSX files
- License test strategy: MEDIUM -- Multiple approaches possible, recommendation needs validation

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (stable -- Playwright API unlikely to change in 30 days)
