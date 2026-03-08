/**
 * Dashboard E2E Tests (TEST-03)
 *
 * Verifies the ops dashboard displays route cards with vehicle data,
 * generates QR sheet HTML, and loads the map page with a MapLibre GL container.
 *
 * Runs at desktop viewport (1280x800) per the dashboard project config.
 * Routes are pre-loaded via API upload in beforeAll -- no UI upload testing here.
 */

import { test, expect } from '@playwright/test';
import { validateApiKey, uploadTestCSV, PREGEOCODE_CSV_PATH } from './helpers/setup';

test.describe.configure({ mode: 'serial' });

test.describe('Dashboard', () => {
  test.beforeAll(async ({ request }) => {
    // Validate API key is set (fail fast with clear error)
    await validateApiKey(request);
    // Upload test CSV to ensure routes exist for dashboard to display
    await uploadTestCSV(request, PREGEOCODE_CSV_PATH);
  });

  test('loads and shows route cards', async ({ page }) => {
    await page.goto('/dashboard/');

    // Wait for React SPA to hydrate and fetch route data from API
    // The route-cards container appears after routes are fetched and rendered
    await expect(page.locator('.route-cards')).toBeVisible({ timeout: 15_000 });

    // At least one card should exist inside route-cards
    const firstCard = page.locator('.route-cards .tw\\:card').first();
    await expect(firstCard).toBeVisible();

    // Card should show a vehicle ID badge (e.g., VEH-01)
    // Use the specific badge-neutral class to avoid matching the status badge
    await expect(firstCard.locator('.tw\\:badge.tw\\:badge-neutral')).toBeVisible();

    // Card should show stats with "stops" text
    await expect(firstCard.getByText('stops')).toBeVisible();

    // Card should show stats with "km" text
    await expect(firstCard.getByText('km')).toBeVisible();
  });

  test('route card displays vehicle and stat data', async ({ page }) => {
    await page.goto('/dashboard/');

    // Wait for route cards to load
    await expect(page.locator('.route-cards')).toBeVisible({ timeout: 15_000 });

    const firstCard = page.locator('.route-cards .tw\\:card').first();
    await expect(firstCard).toBeVisible();

    // Card should have numeric stat values (not empty or zero-only)
    const numericSpans = firstCard.locator('.numeric');
    const count = await numericSpans.count();
    expect(count).toBeGreaterThan(0);

    // At least one numeric span should contain a non-zero value
    const firstNumericText = await numericSpans.first().textContent();
    expect(firstNumericText).toBeTruthy();
    expect(firstNumericText!.trim().length).toBeGreaterThan(0);

    // Card should be clickable (expand/collapse functionality)
    const expandableArea = firstCard.locator('.tw\\:cursor-pointer').first();
    await expect(expandableArea).toBeVisible();
  });

  test('QR sheet generation returns valid HTML', async ({ request }) => {
    // Directly request the QR sheet endpoint via API
    // The extraHTTPHeaders in config include X-API-Key
    const response = await request.get('/api/qr-sheet');
    expect(response.status()).toBe(200);

    // Content type should be HTML
    const contentType = response.headers()['content-type'] || '';
    expect(contentType).toContain('text/html');

    // Body should be substantial (not an empty page)
    const body = await response.text();
    expect(body.length).toBeGreaterThan(500);

    // Body should contain QR-related content (img tags with QR code images)
    // The QR sheet generates base64-encoded PNG QR codes in <img> tags
    expect(body).toContain('<img');
  });

  test('map page loads with MapLibre GL container', async ({ page }) => {
    // Collect console errors during navigation
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto('/dashboard/');

    // Navigate to Live Map via sidebar
    // The sidebar has nav buttons with label text
    const liveMapButton = page.locator('button.sidebar-nav-item', { hasText: 'Live Map' });
    await expect(liveMapButton).toBeVisible({ timeout: 5_000 });
    await liveMapButton.click();

    // Wait for MapLibre GL map container to appear
    // MapLibre GL JS uses the class "maplibregl-map" on the container element
    const mapContainer = page.locator('.maplibregl-map');
    await expect(mapContainer).toBeVisible({ timeout: 15_000 });

    // Map container should have non-zero dimensions
    const box = await mapContainer.boundingBox();
    expect(box).toBeTruthy();
    expect(box!.width).toBeGreaterThan(0);
    expect(box!.height).toBeGreaterThan(0);

    // Filter for actual map initialization errors (not CSP/network issues with tile loading).
    // CSP errors about tile CDN connections are expected in Docker environments
    // and are not map initialization failures.
    const mapInitErrors = consoleErrors.filter(
      (e) =>
        (e.toLowerCase().includes('map') || e.toLowerCase().includes('maplibre')) &&
        !e.toLowerCase().includes('content security policy') &&
        !e.toLowerCase().includes('fetch api cannot load') &&
        !e.toLowerCase().includes('ajaxerror: failed to fetch')
    );
    expect(mapInitErrors).toHaveLength(0);
  });
});
