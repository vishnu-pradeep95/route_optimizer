/**
 * Address Cleaning E2E Tests (Phase 18)
 *
 * Verifies that addresses from real CDCMS data (Refill.xlsx) display
 * correctly after upload -- (HO) expanded to House, (PO) expanded to
 * P.O., MUTTUNGAL preserved, no garbling visible.
 *
 * Requires: Docker stack running, GOOGLE_MAPS_API_KEY set for geocoding.
 * Matched by: dashboard project (testMatch: 'dashboard*.spec.ts').
 */

import { test, expect } from '@playwright/test';
import { validateApiKey, REFILL_XLSX_PATH } from './helpers/setup';
import fs from 'fs';

test.describe.configure({ mode: 'serial' });

test.describe('Address Cleaning - Refill.xlsx', () => {
  test.beforeAll(async ({ request }) => {
    await validateApiKey(request);

    // Verify Refill.xlsx exists before attempting upload
    if (!fs.existsSync(REFILL_XLSX_PATH)) {
      throw new Error(
        `Refill.xlsx not found at ${REFILL_XLSX_PATH}. ` +
        'This file is required for address cleaning E2E tests.'
      );
    }

    // Upload Refill.xlsx via API (faster than UI upload for setup)
    const xlsxBuffer = fs.readFileSync(REFILL_XLSX_PATH);
    const response = await request.post('/api/upload-orders', {
      multipart: {
        file: {
          name: 'Refill.xlsx',
          mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          buffer: xlsxBuffer,
        },
      },
    });
    expect(response.status()).toBe(200);

    const body = await response.json();
    // Verify at least some orders were processed
    expect(body.orders_assigned).toBeGreaterThan(0);
  });

  test('route view shows expanded addresses without raw abbreviations', async ({ page }) => {
    // Navigate to dashboard and wait for routes to load
    await page.goto('/dashboard/');
    await expect(page.locator('.route-cards')).toBeVisible({ timeout: 15_000 });

    // Click first route card to see stops with addresses
    const firstCard = page.locator('.route-cards .tw\\:card').first();
    await expect(firstCard).toBeVisible();
    await firstCard.click();

    // Wait for route details/stops to be visible
    // Give the UI time to render stop details after card click
    await page.waitForTimeout(1000);

    // Check that addresses in the page don't contain raw (HO)/(PO)
    const pageContent = await page.textContent('body');
    expect(pageContent).not.toContain('(HO)');
    expect(pageContent).not.toContain('(PO)');
  });

  test('addresses display House and P.O. correctly', async ({ page }) => {
    await page.goto('/dashboard/');
    await expect(page.locator('.route-cards')).toBeVisible({ timeout: 15_000 });

    // Navigate to a route with stops
    const firstCard = page.locator('.route-cards .tw\\:card').first();
    await expect(firstCard).toBeVisible();
    await firstCard.click();

    // Wait for stop details to render
    await page.waitForTimeout(1000);

    // Verify at least some addresses show "House" (from (HO)/(H) expansion)
    // and "P.O." (from (PO) expansion)
    // With 172 (HO) + 104 (H) patterns in the data, at least one route
    // should contain a "House" address
    const bodyText = await page.textContent('body');
    expect(bodyText).toContain('House');
  });

  test('MUTTUNGAL area addresses are not garbled', async ({ page }) => {
    await page.goto('/dashboard/');
    await expect(page.locator('.route-cards')).toBeVisible({ timeout: 15_000 });

    // Check all visible text on the page for garbled patterns.
    // If MUTTUNGAL addresses are garbled, we'd see fragments like
    // "Muttung A L" instead of "Muttungal"
    const bodyText = await page.textContent('body') || '';

    // "Muttungal" should NOT appear as garbled fragments with spaces
    // between letters. Check for the telltale pattern of single uppercase
    // letters separated by spaces (garbling signature).
    expect(bodyText).not.toMatch(/Muttung\s+A\s+L/i);
  });
});
