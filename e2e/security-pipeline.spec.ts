/**
 * Security Pipeline E2E Tests (DOC-01)
 *
 * Validates the complete v2.1 security pipeline end-to-end using
 * production-mode Docker containers:
 *
 * 1. Fingerprint Mismatch Rejection -- license bound to wrong machine
 * 2. Periodic Re-Validation Triggering -- counter-based revalidation cycle
 * 3. Integrity Tamper Detection -- file modification caught at re-validation
 * 4. License Renewal via File Drop -- expired -> drop renewal.key -> valid
 *
 * Each scenario uses isolated Docker containers started via
 * docker-compose.license-test.yml override. Containers run in production
 * mode (ENVIRONMENT=production) with real license keys generated at test time.
 *
 * Prerequisites:
 *   - Docker Compose stack with db service running and healthy
 *   - Python 3.12+ with project dependencies (for license key generation)
 *   - /etc/machine-id present on host (bind-mounted into containers)
 */

import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';
import { writeFileSync, unlinkSync, existsSync } from 'fs';

const COMPOSE_CMD = 'docker compose -f docker-compose.yml -f docker-compose.license-test.yml';
const CWD = process.cwd();
const EXEC_OPTS = { cwd: CWD, timeout: 60_000, stdio: 'pipe' as const };

const SECURITY_TEST_BASE = 'http://localhost:8002';
const FINGERPRINT_TEST_BASE = 'http://localhost:8003';

// ─── Helpers ───────────────────────────────────────────────────────────────

/** Poll a URL until it responds with any status code. */
async function waitForContainer(
  url: string,
  timeoutMs: number = 60_000,
): Promise<void> {
  const startTime = Date.now();
  let delay = 1000;

  while (Date.now() - startTime < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.status > 0) return;
    } catch {
      // Container not ready yet -- connection refused
    }
    await new Promise((resolve) => setTimeout(resolve, delay));
    delay = Math.min(delay * 1.5, 5000);
  }
  throw new Error(`Container at ${url} did not respond within ${timeoutMs}ms`);
}

/** Generate a valid license key for this machine using generate_license.py. */
function generateValidKey(customer: string): string {
  const output = execSync(
    `python3 scripts/generate_license.py --customer "${customer}" --this-machine --months 1 --verify`,
    { ...EXEC_OPTS, timeout: 30_000 },
  ).toString();

  // Parse the key from the "Key: LPG-XXXX-..." line
  const match = output.match(/Key:\s+(LPG-[\w-]+)/);
  if (!match) {
    throw new Error(`Could not parse license key from output:\n${output}`);
  }
  return match[1];
}

/** Generate a license key bound to a fake fingerprint (all zeros). */
function generateMismatchedKey(customer: string): string {
  const script = `
from core.licensing.license_manager import encode_license_key
from datetime import datetime, timedelta, timezone
key = encode_license_key(
    customer_id="${customer}",
    fingerprint="0" * 64,
    expires_at=datetime.now(timezone.utc) + timedelta(days=30),
)
print(key)
`.trim();

  const output = execSync(`python3 -c '${script}'`, {
    ...EXEC_OPTS,
    timeout: 15_000,
  }).toString().trim();

  if (!output.startsWith('LPG-')) {
    throw new Error(`Unexpected mismatched key output: ${output}`);
  }
  return output;
}

/** Generate an expired license key (10 days past expiry, beyond grace period). */
function generateExpiredKey(customer: string): string {
  const script = `
from core.licensing.license_manager import encode_license_key, get_machine_fingerprint
from datetime import datetime, timedelta, timezone
key = encode_license_key(
    customer_id="${customer}",
    fingerprint=get_machine_fingerprint(),
    expires_at=datetime.now(timezone.utc) - timedelta(days=10),
)
print(key)
`.trim();

  const output = execSync(`python3 -c '${script}'`, {
    ...EXEC_OPTS,
    timeout: 15_000,
  }).toString().trim();

  if (!output.startsWith('LPG-')) {
    throw new Error(`Unexpected expired key output: ${output}`);
  }
  return output;
}

/** Stop and remove a compose service (best-effort). */
function stopService(service: string): void {
  try {
    execSync(`${COMPOSE_CMD} stop ${service}`, { ...EXEC_OPTS, timeout: 30_000 });
    execSync(`${COMPOSE_CMD} rm -f ${service}`, { ...EXEC_OPTS, timeout: 15_000 });
  } catch {
    // Best-effort cleanup
  }
}

/** Get container state via docker inspect. */
function getContainerState(service: string): string {
  try {
    const output = execSync(
      `docker inspect --format='{{.State.Status}}' $(${COMPOSE_CMD} ps -q ${service})`,
      { ...EXEC_OPTS, timeout: 10_000 },
    ).toString().trim();
    return output;
  } catch {
    return 'not-found';
  }
}

// =============================================================================
// Scenario 1: Fingerprint Mismatch Rejection
// =============================================================================

test.describe.serial('Fingerprint Mismatch Rejection', () => {
  test.setTimeout(120_000);

  test.beforeAll(async () => {
    // Generate a key bound to a fake fingerprint that will not match
    const mismatchedKey = generateMismatchedKey('fingerprint-e2e');
    process.env.FINGERPRINT_TEST_LICENSE_KEY = mismatchedKey;

    // Start the fingerprint-test container
    execSync(
      `${COMPOSE_CMD} up -d api-fingerprint-test`,
      EXEC_OPTS,
    );

    // Wait for container to become ready (/health always responds)
    await waitForContainer(`${FINGERPRINT_TEST_BASE}/health`, 60_000);
  });

  test.afterAll(async () => {
    stopService('api-fingerprint-test');
  });

  test('API routes returns 503 with fingerprint-mismatched license', async () => {
    const response = await fetch(`${FINGERPRINT_TEST_BASE}/api/routes`);
    expect(response.status).toBe(503);
  });

  test('health endpoint returns 200 with X-License-Status: invalid', async () => {
    const response = await fetch(`${FINGERPRINT_TEST_BASE}/health`);
    expect(response.status).toBe(200);

    const licenseStatus = response.headers.get('X-License-Status');
    expect(licenseStatus).toBe('invalid');
  });
});

// =============================================================================
// Scenario 2: Periodic Re-Validation Triggering
// =============================================================================

test.describe.serial('Periodic Re-Validation Triggering', () => {
  test.setTimeout(120_000);

  test.beforeAll(async () => {
    // Generate a valid key for this machine
    const validKey = generateValidKey('revalidation-e2e');
    process.env.SECURITY_TEST_LICENSE_KEY = validKey;

    // Start security-test container with REVALIDATION_INTERVAL=10
    execSync(
      `${COMPOSE_CMD} up -d api-security-test`,
      EXEC_OPTS,
    );

    // Wait for container readiness
    await waitForContainer(`${SECURITY_TEST_BASE}/health`, 60_000);
  });

  test.afterAll(async () => {
    stopService('api-security-test');
  });

  test('API is working with valid license', async () => {
    const response = await fetch(`${SECURITY_TEST_BASE}/health`);
    expect(response.status).toBe(200);

    // Should NOT have invalid license status
    const licenseStatus = response.headers.get('X-License-Status');
    expect(licenseStatus).not.toBe('invalid');
  });

  test('re-validation cycle completes without error after 10+ requests', async () => {
    // REVALIDATION_INTERVAL=10, so after 10 requests the counter triggers
    // re-validation. With a valid license and dev-mode manifest (empty),
    // re-validation should pass silently.
    const results: number[] = [];

    for (let i = 0; i < 15; i++) {
      const response = await fetch(`${SECURITY_TEST_BASE}/health`);
      results.push(response.status);
    }

    // All requests should succeed (200) -- re-validation with valid license
    // should not degrade the API
    const allOk = results.every((s) => s === 200);
    expect(allOk).toBe(true);
  });
});

// =============================================================================
// Scenario 3: Integrity Tamper Detection
// =============================================================================

test.describe.serial('Integrity Tamper Detection', () => {
  test.setTimeout(120_000);

  // NOTE: Integrity tamper detection requires a production build with a
  // populated _INTEGRITY_MANIFEST (non-empty dict). In development builds,
  // the manifest is empty and integrity checks are skipped. This test
  // verifies the mechanism works when the manifest is populated.
  //
  // If running against a dev-mode container, the tamper will not be detected
  // because verify_integrity() returns (True, []) when _INTEGRITY_MANIFEST
  // is empty. The test checks for this condition and skips gracefully.

  let isProductionBuild = false;

  test.beforeAll(async () => {
    // Generate a valid key
    const validKey = generateValidKey('integrity-e2e');
    process.env.SECURITY_TEST_LICENSE_KEY = validKey;

    // Start security-test container
    execSync(
      `${COMPOSE_CMD} up -d api-security-test`,
      EXEC_OPTS,
    );

    await waitForContainer(`${SECURITY_TEST_BASE}/health`, 60_000);

    // Check if this is a production build with populated manifest.
    // In dev mode, _INTEGRITY_MANIFEST is {} and integrity checks are skipped.
    // We detect this by checking if the license_manager module has .so files.
    try {
      const output = execSync(
        `${COMPOSE_CMD} exec -T api-security-test sh -c "ls /app/core/licensing/license_manager*.so 2>/dev/null && echo HAS_SO || echo NO_SO"`,
        { ...EXEC_OPTS, timeout: 10_000 },
      ).toString().trim();
      isProductionBuild = output.includes('HAS_SO');
    } catch {
      isProductionBuild = false;
    }
  });

  test.afterAll(async () => {
    stopService('api-security-test');
  });

  test('API is working before tamper', async () => {
    const response = await fetch(`${SECURITY_TEST_BASE}/health`);
    expect(response.status).toBe(200);
  });

  test('integrity tamper detected on re-validation', async () => {
    test.skip(
      !isProductionBuild,
      'Requires production build (build-dist.sh) -- _INTEGRITY_MANIFEST is empty in dev mode, integrity checks are skipped',
    );

    // Modify a protected file inside the running container
    execSync(
      `${COMPOSE_CMD} exec --user root -T api-security-test sh -c "echo tampered >> /app/apps/kerala_delivery/api/main.py"`,
      { ...EXEC_OPTS, timeout: 15_000 },
    );

    // Small delay to ensure filesystem write completes
    await new Promise((resolve) => setTimeout(resolve, 1000));

    // Send 10+ requests to trigger re-validation (REVALIDATION_INTERVAL=10).
    // The container should detect integrity violation and exit (SystemExit).
    for (let i = 0; i < 15; i++) {
      try {
        await fetch(`${SECURITY_TEST_BASE}/health`);
      } catch {
        // Connection refused = container has exited, which is expected
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 200));
    }

    // Verify container has stopped (SystemExit from integrity failure)
    // Give a moment for the container to fully stop
    await new Promise((resolve) => setTimeout(resolve, 3000));

    const state = getContainerState('api-security-test');
    expect(['exited', 'not-found']).toContain(state);
  });
});

// =============================================================================
// Scenario 4: License Renewal via File Drop
// =============================================================================

test.describe.serial('License Renewal via File Drop', () => {
  test.setTimeout(180_000);

  const renewalKeyPath = '/tmp/security-e2e-renewal.key';

  test.beforeAll(async () => {
    // Generate an expired license key (10 days past expiry, beyond grace)
    const expiredKey = generateExpiredKey('renewal-e2e');
    process.env.SECURITY_TEST_LICENSE_KEY = expiredKey;

    // Generate a valid renewal key
    const renewalKey = generateValidKey('renewal-e2e');
    writeFileSync(renewalKeyPath, renewalKey);

    // Start container with expired license
    execSync(
      `${COMPOSE_CMD} up -d api-security-test`,
      EXEC_OPTS,
    );

    await waitForContainer(`${SECURITY_TEST_BASE}/health`, 60_000);
  });

  test.afterAll(async () => {
    stopService('api-security-test');
    // Clean up temp key file
    try {
      if (existsSync(renewalKeyPath)) unlinkSync(renewalKeyPath);
    } catch {
      // Best-effort cleanup
    }
  });

  test('API returns 503 with expired license', async () => {
    const response = await fetch(`${SECURITY_TEST_BASE}/api/routes`);
    expect(response.status).toBe(503);

    // Health should still respond but show invalid status
    const healthResp = await fetch(`${SECURITY_TEST_BASE}/health`);
    expect(healthResp.status).toBe(200);
    const licenseStatus = healthResp.headers.get('X-License-Status');
    expect(licenseStatus).toBe('invalid');
  });

  test('renewal via file drop restores valid license', async () => {
    // Get the container ID for docker cp
    const containerId = execSync(
      `${COMPOSE_CMD} ps -q api-security-test`,
      { ...EXEC_OPTS, timeout: 10_000 },
    ).toString().trim();

    // Copy renewal key into the container
    execSync(
      `docker cp ${renewalKeyPath} ${containerId}:/app/renewal.key`,
      { ...EXEC_OPTS, timeout: 10_000 },
    );

    // Restart the container so enforce() picks up the renewal.key
    execSync(
      `${COMPOSE_CMD} restart api-security-test`,
      { ...EXEC_OPTS, timeout: 60_000 },
    );

    // Wait for container to come back up
    await waitForContainer(`${SECURITY_TEST_BASE}/health`, 60_000);

    // Verify license is now valid
    const healthResp = await fetch(`${SECURITY_TEST_BASE}/health`);
    expect(healthResp.status).toBe(200);

    const body = await healthResp.json();

    // The /health body should have a license section showing valid status
    if (body.license) {
      expect(body.license.status).toBe('valid');
    }

    // X-License-Status header should NOT be 'invalid' after renewal
    const licenseStatus = healthResp.headers.get('X-License-Status');
    expect(licenseStatus).not.toBe('invalid');

    // API routes should work now
    const routesResp = await fetch(`${SECURITY_TEST_BASE}/api/routes`);
    // 200 or 401 (if API key required) -- but NOT 503
    expect(routesResp.status).not.toBe(503);
  });
});
