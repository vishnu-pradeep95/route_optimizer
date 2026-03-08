/**
 * Shared E2E test utilities for Kerala LPG Delivery Route Optimizer.
 *
 * Provides:
 * - API key validation (fail fast with clear error)
 * - Test CSV upload helper (multipart POST with geocoding error detection)
 * - Health check polling (wait for Docker stack readiness)
 * - Common path constants
 */

import { expect } from '@playwright/test';
import type { APIRequestContext } from '@playwright/test';
import fs from 'fs';
import path from 'path';

/** Path to the test CSV fixture (CDCMS tab-separated format, 5 Vatakara orders). */
export const TEST_CSV_PATH = path.join(__dirname, '..', 'fixtures', 'test-orders.csv');

/**
 * Path to the pre-geocoded sample orders CSV (has lat/lon columns).
 * Used when GOOGLE_MAPS_API_KEY is not available for geocoding.
 * These orders already have coordinates so they bypass the geocoding step.
 */
export const PREGEOCODE_CSV_PATH = path.join(__dirname, '..', '..', 'data', 'sample_orders.csv');

/**
 * Validate that the API_KEY environment variable is set.
 *
 * E2E tests require an API key for authenticated endpoints (POST, PUT, DELETE,
 * and sensitive GET endpoints like /api/vehicles and /api/telemetry/*).
 * Fails fast with a descriptive error instead of cryptic 401s during tests.
 */
export async function validateApiKey(request: APIRequestContext): Promise<void> {
  const apiKey = process.env.API_KEY;
  if (!apiKey) {
    throw new Error(
      'API_KEY environment variable is not set. ' +
      'E2E tests require it for authenticated endpoints. ' +
      'Set it in .env or export API_KEY=your-key-here before running tests.'
    );
  }
}

/**
 * Upload a test CSV file via the /api/upload-orders endpoint.
 *
 * Performs a multipart POST, validates the response, and checks that
 * at least some orders were assigned to routes. Provides clear error
 * messages when geocoding fails (common cause: invalid GOOGLE_MAPS_API_KEY).
 *
 * @param request - Playwright APIRequestContext (includes API key from config)
 * @param csvPath - Absolute path to the CSV file to upload
 * @returns The parsed JSON response body (OptimizationSummary)
 */
export async function uploadTestCSV(
  request: APIRequestContext,
  csvPath: string,
): Promise<Record<string, unknown>> {
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
      `Likely cause: invalid GOOGLE_MAPS_API_KEY or VROOM/OSRM not running. ` +
      `Failure reasons: ${reasons || 'unknown'}`
    );
  }

  return body;
}

/**
 * Wait for the API server to respond to health checks.
 *
 * Polls GET /health until it returns 200, with exponential backoff.
 * Used to verify the Docker stack is running before tests start.
 *
 * @param request - Playwright APIRequestContext
 * @param timeoutMs - Maximum time to wait (default: 30 seconds)
 */
export async function waitForHealthy(
  request: APIRequestContext,
  timeoutMs: number = 30_000,
): Promise<void> {
  const startTime = Date.now();
  let lastError: Error | null = null;
  let delay = 500;

  while (Date.now() - startTime < timeoutMs) {
    try {
      const response = await request.get('/health');
      if (response.status() === 200) {
        return;
      }
      lastError = new Error(`Health check returned status ${response.status()}`);
    } catch (err) {
      lastError = err as Error;
    }

    await new Promise(resolve => setTimeout(resolve, delay));
    delay = Math.min(delay * 2, 5000);
  }

  throw new Error(
    `API server did not become healthy within ${timeoutMs}ms. ` +
    `Is the Docker stack running? (docker compose up -d) ` +
    `Last error: ${lastError?.message || 'unknown'}`
  );
}
