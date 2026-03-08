/**
 * License Validation E2E Tests (TEST-04)
 *
 * Verifies that the API returns 503 responses in production mode with an
 * invalid license key, while still allowing /health for diagnostics.
 *
 * These tests run against a separate API container on port 8001 that is
 * started in production mode with an invalid license key via
 * docker-compose.license-test.yml.
 */

import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';

const LICENSE_TEST_BASE = 'http://localhost:8001';

/** Retry polling a URL until it responds (any status). */
async function waitForContainer(
  request: ReturnType<typeof test.extend>,
  url: string,
  timeoutMs: number = 60_000,
): Promise<void> {
  const startTime = Date.now();
  let delay = 1000;

  while (Date.now() - startTime < timeoutMs) {
    try {
      // Use a plain fetch since the request fixture uses baseURL on port 8000.
      // /health always responds even with invalid license.
      const response = await (globalThis as any).fetch(url);
      if (response.status === 200) return;
    } catch {
      // Container not ready yet
    }
    await new Promise((resolve) => setTimeout(resolve, delay));
    delay = Math.min(delay * 1.5, 5000);
  }
  throw new Error(`Container at ${url} did not become ready within ${timeoutMs}ms`);
}

test.describe('License Validation (Production Mode)', () => {
  // Container startup is slow -- generous timeout for beforeAll
  test.setTimeout(90_000);

  test.beforeAll(async () => {
    // Start the license-test container in production mode with invalid license
    try {
      execSync(
        'docker compose -f docker-compose.yml -f docker-compose.license-test.yml up -d api-license-test',
        { cwd: process.cwd(), timeout: 60_000, stdio: 'pipe' },
      );
    } catch (e) {
      throw new Error(
        `Failed to start license-test container. ` +
        `Error: ${(e as Error).message}`
      );
    }

    // Wait for the container to be ready (poll /health)
    const startTime = Date.now();
    let ready = false;
    let delay = 1000;

    while (Date.now() - startTime < 60_000) {
      try {
        const response = await fetch(`${LICENSE_TEST_BASE}/health`);
        if (response.ok || response.status === 200) {
          ready = true;
          break;
        }
      } catch {
        // Container not ready yet
      }
      await new Promise((resolve) => setTimeout(resolve, delay));
      delay = Math.min(delay * 1.5, 5000);
    }

    if (!ready) {
      throw new Error(
        'License-test container did not become ready within 60s. ' +
        'Check: docker compose -f docker-compose.yml -f docker-compose.license-test.yml logs api-license-test'
      );
    }
  });

  test.afterAll(async () => {
    // Stop and remove the license-test container
    try {
      execSync(
        'docker compose -f docker-compose.yml -f docker-compose.license-test.yml stop api-license-test',
        { cwd: process.cwd(), timeout: 30_000, stdio: 'pipe' },
      );
      execSync(
        'docker compose -f docker-compose.yml -f docker-compose.license-test.yml rm -f api-license-test',
        { cwd: process.cwd(), timeout: 15_000, stdio: 'pipe' },
      );
    } catch {
      // Best-effort cleanup -- don't fail tests if container stop fails
    }
  });

  test('health endpoint responds with license status header', async () => {
    const response = await fetch(`${LICENSE_TEST_BASE}/health`);
    expect(response.status).toBe(200);

    // Health is always allowed, but gets X-License-Status header when invalid
    const licenseStatus = response.headers.get('X-License-Status');
    expect(licenseStatus).toBe('invalid');

    // Body should have a status field
    const body = await response.json();
    expect(body).toHaveProperty('status');
  });

  test('API routes endpoint returns 503 with invalid license', async () => {
    const response = await fetch(`${LICENSE_TEST_BASE}/api/routes`);
    expect(response.status).toBe(503);

    // Exact response body match per user decision
    const body = await response.json();
    expect(body).toEqual({
      detail: 'License expired or invalid. Contact support.',
      license_status: 'invalid',
    });
  });

  test('API config endpoint returns 503', async () => {
    const response = await fetch(`${LICENSE_TEST_BASE}/api/config`);
    expect(response.status).toBe(503);

    const body = await response.json();
    expect(body).toEqual({
      detail: 'License expired or invalid. Contact support.',
      license_status: 'invalid',
    });
  });

  test('API vehicles endpoint returns 503', async () => {
    const apiKey = process.env.API_KEY || '';
    const response = await fetch(`${LICENSE_TEST_BASE}/api/vehicles`, {
      headers: { 'X-API-Key': apiKey },
    });
    expect(response.status).toBe(503);
  });
});
