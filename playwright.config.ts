import { defineConfig } from '@playwright/test';

/**
 * Playwright E2E test configuration for Kerala LPG Delivery Route Optimizer.
 *
 * Assumes the Docker stack is running at localhost:8000 (api, db, osrm, vroom).
 * API_KEY env var must be set for authenticated endpoints.
 *
 * Usage:
 *   npx playwright test                    # Run all tests
 *   npx playwright test --project=api      # Run API tests only
 *   npx playwright test --project=driver-pwa  # Run driver PWA tests only
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [
    ['html', { open: 'never' }],
    ['list'],
  ],
  timeout: 60_000,
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
        viewport: { width: 393, height: 851 },
      },
    },
    {
      name: 'dashboard',
      testMatch: 'dashboard*.spec.ts',
      use: {
        viewport: { width: 1280, height: 800 },
      },
    },
    {
      name: 'license',
      testMatch: 'license.spec.ts',
    },
    {
      name: 'security-pipeline',
      testMatch: 'security-pipeline.spec.ts',
    },
  ],
});
