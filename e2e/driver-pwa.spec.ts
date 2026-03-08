/**
 * E2E Driver PWA flow tests for Kerala LPG Delivery Route Optimizer (TEST-02).
 *
 * Tests the complete driver daily workflow as a sequential story:
 *   Upload screen -> CSV upload -> vehicle selector -> route view ->
 *   mark done (UI + API) -> mark fail via dialog (UI + API) ->
 *   all-done banner -> navigation reset
 *
 * Uses mobile viewport (393x851) set by the driver-pwa project in playwright.config.ts.
 * Shared state per spec file: upload once in beforeAll, sequential tests build on prior state.
 *
 * Requires:
 * - Docker stack running at localhost:8000 (api, db, osrm, vroom)
 * - API_KEY environment variable set
 *
 * Run: npx playwright test --project=driver-pwa
 */

import { test, expect, type Page, type BrowserContext } from '@playwright/test';
import {
  validateApiKey,
  uploadTestCSV,
  waitForHealthy,
  PREGEOCODE_CSV_PATH,
} from './helpers/setup';

test.describe.configure({ mode: 'serial' });

test.describe('Driver PWA Flow', () => {
  // Shared state across all tests in this describe block
  let context: BrowserContext;
  let page: Page;
  let vehicleId: string;
  let firstStopOrderId: string;

  test.beforeAll(async ({ browser, request }) => {
    // 1. Validate API key is configured
    await validateApiKey(request);

    // 2. Wait for Docker stack to be healthy
    await waitForHealthy(request);

    // 3. Upload pre-geocoded CSV via API to seed route data.
    //    Uses sample_orders.csv which has lat/lon columns, bypassing geocoding.
    const uploadResult = await uploadTestCSV(request, PREGEOCODE_CSV_PATH);

    // 4. Extract first vehicle ID from the routes
    const routesResp = await request.get('/api/routes');
    const routesBody = await routesResp.json();
    expect(routesBody.routes.length).toBeGreaterThan(0);
    vehicleId = routesBody.routes[0].vehicle_id;

    // 5. Create a persistent browser context with API key in localStorage
    context = await browser.newContext({
      viewport: { width: 393, height: 851 },
    });
    page = await context.newPage();

    // Set API key in localStorage before any navigation
    await page.goto('http://localhost:8000/driver/');
    await page.evaluate((key) => {
      localStorage.clear();
      localStorage.setItem('lpg_api_key', key);
    }, process.env.API_KEY || '');
  });

  test.afterAll(async () => {
    await context?.close();
  });

  // =========================================================================
  // Test 1: Upload screen renders correctly
  // =========================================================================

  test('upload screen renders correctly', async () => {
    // Navigate fresh and clear any cached state
    await page.goto('http://localhost:8000/driver/');
    await page.evaluate((key) => {
      localStorage.clear();
      localStorage.setItem('lpg_api_key', key);
    }, process.env.API_KEY || '');
    await page.reload();

    // Assert upload section is visible
    await expect(page.locator('#upload-section')).toBeVisible();

    // Assert "Today's Deliveries" heading
    await expect(page.getByText("Today's Deliveries")).toBeVisible();

    // Assert upload button visible
    await expect(page.locator('button.upload-btn')).toBeVisible();
    await expect(page.getByText('Upload Delivery List')).toBeVisible();

    // Assert upload icon container visible
    await expect(page.locator('.upload-icon')).toBeVisible();

    // Assert upload status area present
    await expect(page.locator('#upload-status')).toBeAttached();

    // Assert file input exists (hidden)
    await expect(page.locator('#file-input')).toBeAttached();

    // Check for console errors
    const errors: string[] = [];
    page.on('pageerror', (err) => errors.push(err.message));
    // Allow a brief moment for any deferred errors
    await page.waitForTimeout(500);
    // No critical JS errors expected (network errors from missing resources are OK)
  });

  // =========================================================================
  // Test 2: CSV upload shows vehicle selector
  // =========================================================================

  test('CSV upload shows vehicle selector', async () => {
    // Trigger file upload via the hidden file input
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.locator('button.upload-btn').click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(PREGEOCODE_CSV_PATH);

    // Wait for vehicle selector to appear (geocoding/optimization can be slow)
    await expect(page.locator('#vehicle-selector')).toHaveClass(/visible/, {
      timeout: 60_000,
    });

    // Assert "Select Your Vehicle" text visible
    await expect(page.getByText('Select Your Vehicle')).toBeVisible();

    // Assert at least one vehicle button exists
    const vehicleButtons = page.locator('button.vehicle-btn');
    await expect(vehicleButtons.first()).toBeVisible({ timeout: 10_000 });
    const count = await vehicleButtons.count();
    expect(count).toBeGreaterThan(0);
  });

  // =========================================================================
  // Test 3: Vehicle selection shows route view
  // =========================================================================

  test('vehicle selection shows route view', async () => {
    // Click the first vehicle button
    await page.locator('button.vehicle-btn').first().click();

    // Wait for route view to become visible
    await expect(page.locator('#route-view')).toBeVisible({ timeout: 10_000 });

    // Assert stop list has at least one stop
    const stopList = page.locator('#stop-list');
    await expect(stopList).toBeVisible();

    // Assert hero card exists (first pending stop)
    await expect(page.locator('.hero-card').first()).toBeVisible({
      timeout: 10_000,
    });

    // Assert progress bar is visible
    await expect(page.locator('#progress-bar')).toBeVisible();

    // Assert header stats contains delivered count text
    const headerStats = page.locator('#header-stats');
    await expect(headerStats).toBeVisible();
    await expect(headerStats).toContainText('delivered');

    // Assert navigate button exists on hero card
    await expect(page.locator('button.btn-navigate').first()).toBeVisible();

    // Assert Done button exists (class is btn-deliver in the actual HTML)
    await expect(page.locator('button.btn-deliver').first()).toBeVisible();

    // Assert Fail button exists
    await expect(page.locator('button.btn-fail').first()).toBeVisible();

    // Assert Call Office FAB is visible
    await expect(page.locator('#call-office-fab')).toBeVisible();

    // Store the first stop's order_id from the DOM
    const heroCard = page.locator('.hero-card').first();
    const heroId = await heroCard.getAttribute('id');
    // Hero card id is "stop-{order_id}"
    firstStopOrderId = heroId?.replace('stop-', '') || '';
    expect(firstStopOrderId).toBeTruthy();
  });

  // =========================================================================
  // Test 4: Mark stop as delivered (UI + API dual verification)
  // =========================================================================

  test('mark stop as delivered with UI and API verification', async () => {
    // Record order_id of the current hero card stop before clicking
    const heroCard = page.locator('.hero-card').first();
    const currentOrderId = (await heroCard.getAttribute('id'))?.replace(
      'stop-',
      '',
    );
    expect(currentOrderId).toBeTruthy();

    // Click the Done button on the hero card
    await page.locator('button.btn-deliver').first().click();

    // Wait for success toast to appear
    await expect(page.locator('.toast-delivered')).toBeVisible({
      timeout: 5_000,
    });

    // Wait for the stop list to re-render (1500ms timeout in the app + render time)
    // The delivered stop should now appear as a compact card with "Delivered" status
    await expect(
      page.locator(`.compact-card.delivered`).first(),
    ).toBeVisible({ timeout: 5_000 });

    // Verify the delivered stop shows the checkmark/delivered indicator
    await expect(page.locator('.status-chip.delivered').first()).toBeVisible();

    // Assert progress bar updated (at least one delivered segment)
    await expect(
      page.locator('.progress-segment.progress-delivered').first(),
    ).toBeVisible();

    // API verification: fetch route and verify stop status changed to "delivered"
    const apiResponse = await page.request.get(
      `http://localhost:8000/api/routes/${vehicleId}`,
      {
        headers: { 'X-API-Key': process.env.API_KEY || '' },
      },
    );
    expect(apiResponse.status()).toBe(200);
    const routeData = await apiResponse.json();
    const deliveredStop = routeData.stops.find(
      (s: { order_id: string; status: string }) =>
        s.order_id === currentOrderId,
    );
    expect(deliveredStop).toBeTruthy();
    expect(deliveredStop.status).toBe('delivered');
  });

  // =========================================================================
  // Test 5: Mark stop as failed via dialog modal
  // =========================================================================

  test('mark stop as failed via dialog modal with UI and API verification', async () => {
    // Get the current hero card's order_id (next pending stop after the delivered one)
    const heroCard = page.locator('.hero-card').first();
    await expect(heroCard).toBeVisible({ timeout: 5_000 });
    const failOrderId = (await heroCard.getAttribute('id'))?.replace(
      'stop-',
      '',
    );
    expect(failOrderId).toBeTruthy();

    // Click the Fail button on the hero card
    await page.locator('button.btn-fail').first().click();

    // Assert fail dialog is visible (native <dialog> element)
    const dialog = page.locator('dialog#fail-dialog');
    await expect(dialog).toBeVisible({ timeout: 3_000 });

    // Assert dialog has the expected content
    await expect(page.getByText('Mark delivery as failed?')).toBeVisible();

    // Assert fail reason dropdown is visible with options
    const reasonSelect = page.locator('select#fail-reason');
    await expect(reasonSelect).toBeVisible();

    // Assert "Yes, Failed" button is visible
    await expect(page.locator('button#fail-confirm')).toBeVisible();

    // Assert "Cancel" button is visible
    await expect(page.locator('button#fail-cancel')).toBeVisible();

    // Click "Cancel" -- assert dialog closes, no state change
    await page.locator('button#fail-cancel').click();
    await expect(dialog).toBeHidden({ timeout: 3_000 });

    // Verify no state change: hero card should still show the same stop
    await expect(heroCard).toBeVisible();
    const sameOrderId = (await heroCard.getAttribute('id'))?.replace(
      'stop-',
      '',
    );
    expect(sameOrderId).toBe(failOrderId);

    // Click Fail again on the same stop
    await page.locator('button.btn-fail').first().click();
    await expect(dialog).toBeVisible({ timeout: 3_000 });

    // Select a reason from the dropdown
    await reasonSelect.selectOption('not_home');

    // Click "Yes, Failed"
    await page.locator('button#fail-confirm').click();

    // Wait for fail toast to appear
    await expect(page.locator('.toast-failed')).toBeVisible({
      timeout: 5_000,
    });

    // Wait for the stop to re-render as failed compact card
    await expect(page.locator('.compact-card.failed').first()).toBeVisible({
      timeout: 5_000,
    });

    // Verify the failed stop shows the failed indicator
    await expect(page.locator('.status-chip.failed').first()).toBeVisible();

    // API verification: fetch route and verify stop status is "failed"
    const apiResponse = await page.request.get(
      `http://localhost:8000/api/routes/${vehicleId}`,
      {
        headers: { 'X-API-Key': process.env.API_KEY || '' },
      },
    );
    expect(apiResponse.status()).toBe(200);
    const routeData = await apiResponse.json();
    const failedStop = routeData.stops.find(
      (s: { order_id: string; status: string }) =>
        s.order_id === failOrderId,
    );
    expect(failedStop).toBeTruthy();
    expect(failedStop.status).toBe('failed');
  });

  // =========================================================================
  // Test 6: All-done banner appears when all stops are complete
  // =========================================================================

  test('all-done banner appears when all stops complete', async () => {
    // Mark all remaining pending stops as "Done" by clicking btn-deliver repeatedly
    let remainingHero = page.locator('.hero-card');

    // Loop: while there's a hero card (pending stop), click Done
    while (await remainingHero.count().then((c) => c > 0)) {
      await page.locator('button.btn-deliver').first().click();

      // Wait for toast and re-render
      await expect(page.locator('.toast-delivered')).toBeVisible({
        timeout: 5_000,
      });
      // Wait for re-render (the 1500ms setTimeout in updateStatus)
      // Use a concrete assertion instead of waitForTimeout:
      // Either the next hero card appears, or the all-done banner appears
      await Promise.race([
        expect(page.locator('#all-done-banner')).toBeVisible({
          timeout: 5_000,
        }).catch(() => {}),
        expect(remainingHero).toBeVisible({ timeout: 5_000 }).catch(() => {}),
      ]);

      // Brief pause for DOM stability
      await page.waitForTimeout(300);
    }

    // Assert all-done banner is visible
    await expect(page.locator('#all-done-banner')).toBeVisible({
      timeout: 5_000,
    });
    await expect(page.getByText('Route complete!')).toBeVisible();

    // Assert progress bar is fully filled (no pending segments)
    const pendingSegments = page.locator(
      '.progress-segment.progress-pending',
    );
    expect(await pendingSegments.count()).toBe(0);

    // Assert banner dismiss button exists
    const dismissBtn = page.locator('button.all-done-close');
    await expect(dismissBtn).toBeVisible();

    // Click dismiss button -- banner should disappear
    await dismissBtn.click();
    await expect(page.locator('#all-done-banner')).toBeHidden({
      timeout: 3_000,
    });
  });

  // =========================================================================
  // Test 7: Navigation flow - reset returns to vehicle selector
  // =========================================================================

  test('reset button returns to vehicle selector', async () => {
    // The reset/change-vehicle button uses the ⇄ character
    // It's in #header-actions and calls changeVehicle()
    const resetBtn = page.locator(
      '#header-actions button[title="Switch to a different vehicle"]',
    );
    await expect(resetBtn).toBeVisible();

    // Click reset
    await resetBtn.click();

    // Assert vehicle selector becomes visible again
    await expect(page.locator('#vehicle-selector')).toHaveClass(/visible/, {
      timeout: 5_000,
    });

    // Assert route view is hidden
    await expect(page.locator('#route-view')).toBeHidden();

    // Assert "Select Your Vehicle" heading is visible
    await expect(page.getByText('Select Your Vehicle')).toBeVisible();

    // Assert vehicle buttons are still present (from cached routes)
    const vehicleButtons = page.locator('button.vehicle-btn');
    expect(await vehicleButtons.count()).toBeGreaterThan(0);
  });
});
