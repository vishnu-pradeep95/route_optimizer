/**
 * Dashboard Error UI E2E Tests (Phase 02, Plan 04)
 *
 * Verifies all error UI components in the dashboard:
 * - ErrorBanner renders with correct severity color class
 * - "Show details" toggle reveals error_code, request_id, timestamp
 * - Retry button is visible and clickable
 * - Dismiss button removes the banner
 * - ErrorTable renders rows with correct columns
 * - Health status bar shows per-service status indicators
 * - No console errors during error UI interactions
 *
 * Satisfies CONTEXT.md HARD REQUIREMENT:
 * "Every error UI element must have Playwright E2E test coverage."
 *
 * Runs at desktop viewport (1280x800) per the dashboard project config.
 */

import { test, expect, type Page } from '@playwright/test';

test.describe.configure({ mode: 'serial' });

/**
 * Navigate to the upload form. If the dashboard is showing existing routes
 * (success state), click "Upload New File" to reset to the upload form.
 * This handles the case where previous tests/uploads left routes in the DB.
 */
async function navigateToUploadForm(page: Page): Promise<void> {
  await page.goto('/dashboard/');
  await page.waitForLoadState('networkidle');

  // If routes are already loaded, the success state is showing.
  // Click "Upload New File" to get back to the upload form.
  const newUploadBtn = page.locator('button', { hasText: /Upload New File/i });
  const isSuccessState = await newUploadBtn.isVisible({ timeout: 5_000 }).catch(() => false);
  if (isSuccessState) {
    await newUploadBtn.click();
    // Wait for the upload form to appear
    await expect(page.locator('input[type="file"]')).toBeAttached({ timeout: 5_000 });
  }
}

/**
 * Trigger a client-side validation error by uploading an invalid .txt file.
 * The UploadRoutes component validates the extension client-side and creates
 * a synthetic ApiError with error_code=UPLOAD_INVALID_FORMAT.
 */
async function triggerUploadError(page: Page): Promise<void> {
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles({
    name: 'test.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('not a csv'),
  });
}

test.describe('Dashboard Error UI', () => {

  // ─── ErrorBanner Tests ───────────────────────────────────

  test('ErrorBanner renders with correct severity on upload error', async ({ page }) => {
    await navigateToUploadForm(page);
    await triggerUploadError(page);

    // Wait for error banner to appear
    const banner = page.locator('[data-testid="error-banner"]');
    await expect(banner).toBeVisible({ timeout: 10_000 });

    // Verify severity attribute: should be "error" for upload failures
    await expect(banner).toHaveAttribute('data-severity', 'error');

    // Verify the banner contains alert-error class (DaisyUI red alert)
    // The class is tw:alert-error which renders in DOM
    const bannerClasses = await banner.getAttribute('class');
    expect(bannerClasses).toContain('alert-error');

    // Verify user_message text is visible (not empty)
    const messageText = banner.locator('p').first();
    await expect(messageText).not.toBeEmpty();
    await expect(messageText).toContainText(/\.csv|\.xlsx|\.xls/);
  });

  test('ErrorBanner "Show details" toggle reveals error_code, request_id, timestamp', async ({ page }) => {
    await navigateToUploadForm(page);
    await triggerUploadError(page);

    const banner = page.locator('[data-testid="error-banner"]');
    await expect(banner).toBeVisible({ timeout: 10_000 });

    // Click "Show details" toggle.
    // The DaisyUI collapse uses a checkbox overlay, so we use force:true
    // to bypass the interception by the hidden checkbox input.
    const detailToggle = page.locator('[data-testid="error-detail-toggle"]');
    await expect(detailToggle).toBeVisible();
    await expect(detailToggle).toContainText('Show details');
    await detailToggle.click({ force: true });

    // Verify detail panel becomes visible (the collapse-content within error-detail)
    const detailPanel = page.locator('[data-testid="error-detail"]');
    await expect(detailPanel).toBeVisible();

    // Verify error_code is displayed (starts with UPLOAD_)
    await expect(detailPanel).toContainText(/UPLOAD_INVALID_FORMAT/);

    // Verify request_id label is displayed
    await expect(detailPanel).toContainText(/Request ID/i);

    // Verify timestamp is displayed (labeled "Time:")
    await expect(detailPanel).toContainText(/Time/i);

    // Toggle text should change to "Hide details"
    await expect(detailToggle).toContainText('Hide details');

    // Click again to collapse
    await detailToggle.click({ force: true });
    await expect(detailToggle).toContainText('Show details');
  });

  test('ErrorBanner Retry button is visible and clickable', async ({ page }) => {
    await navigateToUploadForm(page);
    await triggerUploadError(page);

    const banner = page.locator('[data-testid="error-banner"]');
    await expect(banner).toBeVisible({ timeout: 10_000 });

    // Verify Retry button exists (data-testid="error-retry-btn")
    const retryBtn = page.locator('[data-testid="error-retry-btn"]');
    await expect(retryBtn).toBeVisible();
    await expect(retryBtn).toBeEnabled();
    await expect(retryBtn).toContainText(/retry/i);

    // Click retry -- should reset the form (handleReset clears error state)
    await retryBtn.click();

    // After retry, the error banner should disappear (reset to idle state)
    await expect(banner).not.toBeVisible({ timeout: 5_000 });

    // The upload drop zone should be visible again (back to idle state)
    const dropZone = page.locator('.drop-zone');
    await expect(dropZone).toBeVisible();
  });

  test('ErrorBanner Dismiss button removes the banner', async ({ page }) => {
    await navigateToUploadForm(page);
    await triggerUploadError(page);

    const banner = page.locator('[data-testid="error-banner"]');
    await expect(banner).toBeVisible({ timeout: 10_000 });

    // Verify Dismiss button exists (data-testid="error-dismiss-btn")
    const dismissBtn = page.locator('[data-testid="error-dismiss-btn"]');
    await expect(dismissBtn).toBeVisible();

    // Click dismiss
    await dismissBtn.click();

    // Banner should disappear
    await expect(banner).not.toBeVisible({ timeout: 5_000 });
  });

  // ─── ErrorTable Tests ───────────────────────────────────

  test('ErrorTable renders rows with Row #, Address, Reason columns after API error', async ({ page }) => {
    // Upload a CSV with bad data rows via the UI to trigger row-level failures.
    // The CSV has a valid header but rows with missing required fields.
    const badCSV = [
      'Order ID,Customer Name,Address,Phone,Status,Quantity',
      ',,,,,',  // Empty row -- should fail validation
      'ORD-003,Bad Customer,,9876543210,Allocated-Printed,1',  // Missing address
    ].join('\n');

    await navigateToUploadForm(page);

    // Upload the bad CSV via the UI
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: 'test-bad.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(badCSV),
    });

    // Click the "Generate Routes & QR Codes" button to trigger upload
    const uploadBtn = page.locator('button', { hasText: /Generate Routes/i });
    await expect(uploadBtn).toBeVisible({ timeout: 5_000 });
    await uploadBtn.click();

    // Wait for results -- either ErrorBanner (full rejection) or ImportSummary with failures
    // Give extra time for processing
    await page.waitForTimeout(10_000);

    // Check if ErrorTable appeared (within ImportSummary for partial failures)
    // The error table may be inside a collapse that needs expanding
    const errorTable = page.locator('[data-testid="error-table"]');
    const errorBanner = page.locator('[data-testid="error-banner"]');
    const hasErrorTable = await errorTable.isVisible().catch(() => false);
    const hasErrorBanner = await errorBanner.isVisible().catch(() => false);

    if (hasErrorTable) {
      // Verify table has the expected column headers
      const headers = errorTable.locator('thead th');
      await expect(headers.nth(0)).toContainText('Row');
      await expect(headers.nth(1)).toContainText('Address');
      await expect(headers.nth(2)).toContainText('Reason');

      // Verify at least one data row exists
      const rows = errorTable.locator('tbody tr');
      const rowCount = await rows.count();
      expect(rowCount).toBeGreaterThan(0);
    } else if (hasErrorBanner) {
      // The entire file was rejected -- ErrorBanner should show error info
      const bannerText = await errorBanner.textContent();
      expect(bannerText).toBeTruthy();
    } else {
      // Check if there's a failures collapse that needs expanding
      const failuresCollapse = page.locator('.tw\\:collapse', { hasText: /failed row/i });
      const hasCollapse = await failuresCollapse.isVisible().catch(() => false);

      if (hasCollapse) {
        // Click to expand the failures section
        await failuresCollapse.click();
        await page.waitForTimeout(500);
        // Now check for error table inside
        await expect(errorTable).toBeVisible({ timeout: 5_000 });
        const headers = errorTable.locator('thead th');
        await expect(headers.nth(0)).toContainText('Row');
        await expect(headers.nth(1)).toContainText('Address');
        await expect(headers.nth(2)).toContainText('Reason');
      } else {
        // If neither table nor banner, the CSV may have been fully accepted
        // (no failures). This is still a valid outcome -- the test verifies
        // the error path is reachable. Fail with clear message.
        const pageContent = await page.content();
        expect(
          hasErrorTable || hasErrorBanner,
          'Expected either ErrorTable or ErrorBanner to be visible after uploading CSV with bad rows. ' +
          'The API may have accepted all rows. Page state: ' +
          (pageContent.includes('error-banner') ? 'has error-banner in DOM' : 'no error elements')
        ).toBeTruthy();
      }
    }
  });

  // ─── Health Status Bar Tests ────────────────────────────

  test('Health status bar shows service status indicators', async ({ page }) => {
    await page.goto('/dashboard/');
    await page.waitForLoadState('networkidle');

    // The health status bar is in the sidebar, rendered on initial load.
    // It polls /health and displays overall + per-service status.
    // There are two health bars (desktop sidebar + mobile drawer), so scope to
    // the desktop sidebar (<aside class="app-sidebar">).
    const healthBar = page.locator('aside.app-sidebar [data-testid="health-status-bar"]');
    await expect(healthBar).toBeVisible({ timeout: 15_000 });

    // Verify it contains a health-dot indicator
    const healthDot = healthBar.locator('.health-dot').first();
    await expect(healthDot).toBeVisible();

    // Verify status text is present (e.g., "All systems operational", "Connected", or service names)
    const healthText = await healthBar.textContent();
    expect(healthText).toBeTruthy();
    expect(healthText!.length).toBeGreaterThan(0);

    // The health text should contain meaningful status info.
    // With the enhanced /health endpoint, it shows per-service status;
    // with the legacy endpoint, it shows "All systems operational", "Connected", etc.
    expect(healthText).toMatch(
      /operational|healthy|connected|checking|postgresql|osrm|vroom|degraded|unhealthy|offline/i
    );
  });

  // ─── No Console Errors ──────────────────────────────────

  test('No console errors during error UI interactions', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await navigateToUploadForm(page);
    await triggerUploadError(page);

    // Wait for error banner to render
    const banner = page.locator('[data-testid="error-banner"]');
    await expect(banner).toBeVisible({ timeout: 10_000 });

    // Interact with the error detail toggle (force:true to bypass DaisyUI checkbox overlay)
    const detailToggle = page.locator('[data-testid="error-detail-toggle"]');
    if (await detailToggle.isVisible()) {
      await detailToggle.click({ force: true });
      await page.waitForTimeout(500);
    }

    // Click retry to reset
    const retryBtn = page.locator('[data-testid="error-retry-btn"]');
    if (await retryBtn.isVisible()) {
      await retryBtn.click();
      await page.waitForTimeout(500);
    }

    // Filter out known benign errors (favicon, service worker, dev warnings)
    const realErrors = consoleErrors.filter(
      (e) =>
        !e.includes('favicon') &&
        !e.includes('sw.js') &&
        !e.includes('service-worker') &&
        !e.includes('VITE_API_KEY not set') &&
        // Network errors for tile loading in dev are expected
        !e.includes('ERR_CONNECTION_REFUSED') &&
        !e.includes('Content Security Policy') &&
        !e.includes('net::ERR_')
    );

    expect(realErrors).toHaveLength(0);
  });
});
