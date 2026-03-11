# Phase 10: End-to-End Validation - Research

**Researched:** 2026-03-11
**Domain:** E2E testing (Playwright + Docker), technical documentation (Markdown)
**Confidence:** HIGH

## Summary

Phase 10 is the final phase of the v2.1 milestone. It has three deliverables: (1) Playwright E2E tests for four security pipeline scenarios, (2) full rewrite of LICENSING.md plus updates to SETUP.md and ERROR-MAP.md, and (3) an updated customer migration document. All implementation code is complete (Phases 5-9 done) -- this phase validates and documents everything.

The E2E tests must exercise real Docker containers in production mode. The existing `e2e/license.spec.ts` and `docker-compose.license-test.yml` provide a proven pattern: override compose file starts a separate API on port 8001 with controlled environment variables. Two of the four test scenarios (integrity tamper, renewal lifecycle) require more sophisticated Docker orchestration than the current tests -- specifically `docker exec` for file modification inside a running container and container restart with file drop. The re-validation test requires a new `REVALIDATION_INTERVAL` env var in `license_manager.py` (currently hardcoded to 500).

**Primary recommendation:** Extend the existing license E2E test infrastructure. Add a `REVALIDATION_INTERVAL` env var to `license_manager.py` for test-time override. Create a new spec file for v2.1 security scenarios to keep them separate from the existing basic license tests. Rewrite LICENSING.md from scratch using current codebase as source of truth.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Claude decides the right balance of Docker integration vs pytest unit tests per scenario
- Claude decides whether to extend existing `e2e/license.spec.ts` or create a new spec file
- Lower re-validation threshold for tests: add a test-only env var (e.g., `REVALIDATION_INTERVAL=10`) so re-validation tests only need ~10 requests instead of 500
- Fingerprint mismatch test: generate a license with a different fingerprint than the container's, verify 503 rejection at startup
- Integrity tamper test: use `docker exec` to modify a protected file inside a running container, then verify next re-validation cycle catches it
- Renewal test: full lifecycle -- start with expired license, verify 503/GRACE, drop renewal.key via Docker, restart container, verify VALID status restored
- LICENSING.md: full rewrite -- current content significantly outdated
- ERROR-MAP.md: audit and add -- grep codebase for all new error messages from Phases 5-9
- SETUP.md: config changes + monitoring -- add v2.1 configuration and monitoring section
- Docker exec approach for integrity tamper tests
- Full container lifecycle for renewal test
- Security pipeline tests run as a separate CI step (not part of regular Playwright suite)
- Reuse existing docker-compose.license-test.yml pattern for container management

### Claude's Discretion
- Test file organization (extend license.spec.ts vs new spec file)
- LICENSING.md audience structure (developer-only vs dev+customer split)
- Migration doc scope (breaking changes only vs full changelog)
- Exact Docker compose configuration for renewal and tamper test scenarios
- Which error messages from Phases 5-9 need ERROR-MAP.md entries (grep-based audit)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DOC-01 | E2E tests for integrity failure, periodic re-validation, license renewal, fingerprint mismatch scenarios | Playwright test infrastructure exists (`e2e/license.spec.ts`, `docker-compose.license-test.yml`); need `REVALIDATION_INTERVAL` env var, Docker exec patterns, container lifecycle management |
| DOC-02 | docs/LICENSING.md, SETUP.md, ERROR-MAP.md updated for all v2.1 changes | Current LICENSING.md is outdated (references old fingerprint formula, .pyc, no renewal/integrity); ERROR-MAP.md needs v2.1 error messages; SETUP.md needs machine-id mount, renewal.key, env vars |
| DOC-03 | Customer migration procedure documented (fingerprint formula change + HMAC seed rotation) | MIGRATION.md exists from Phase 6 with correct structure; needs v2.1-specific verification steps (/health license.status, fingerprint_match, X-License-Expires-In header) |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @playwright/test | ^1.58.2 | E2E browser and API testing | Already installed, proven Docker lifecycle pattern in license.spec.ts |
| child_process (Node built-in) | N/A | Execute docker compose, docker exec from tests | Used in existing license.spec.ts for container management |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| docker compose | (system) | Container orchestration for test environments | All 4 E2E test scenarios need isolated containers |
| docker exec | (system) | Modify files inside running containers | Integrity tamper test: modify a protected file mid-run |
| docker cp | (system) | Copy files into containers | Renewal test: drop renewal.key into container |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| New spec file | Extend license.spec.ts | New file recommended: existing tests are basic 503 checks; v2.1 scenarios are complex lifecycle tests with different container configs |
| Playwright API testing | pytest + httpx | pytest runs in Python (closer to codebase) but loses the established Playwright Docker pattern and CI integration |

## Architecture Patterns

### Recommended Test File Structure
```
e2e/
  license.spec.ts              # Existing: basic invalid-license 503 tests (keep as-is)
  security-pipeline.spec.ts    # NEW: v2.1 integrity, revalidation, renewal, fingerprint tests
docker-compose.license-test.yml  # Existing: extend with new service configs
```

### Pattern 1: Docker Compose Override for Test Scenarios
**What:** Use `docker-compose.license-test.yml` override to define multiple test containers with different configurations (mismatched fingerprint, expired license, low revalidation interval).
**When to use:** Each E2E test scenario needs a differently-configured container.
**Example:**
```yaml
# docker-compose.license-test.yml additions
services:
  api-security-test:
    build:
      context: .
      dockerfile: infra/Dockerfile
    ports:
      - "8002:8000"
    environment:
      - ENVIRONMENT=production
      - LICENSE_KEY=${VALID_LICENSE_KEY}
      - REVALIDATION_INTERVAL=10
      - DATABASE_URL=postgresql+asyncpg://routing:${POSTGRES_PASSWORD:-routing_dev_pass}@db:5432/routing_opt
    volumes:
      - /etc/machine-id:/etc/machine-id:ro
    depends_on:
      db:
        condition: service_healthy
```

### Pattern 2: Sequential Test Story with Container Lifecycle
**What:** Tests run in declared order within a `test.describe.serial()` block, sharing a container that may be restarted between tests.
**When to use:** Renewal lifecycle test (start expired -> drop key -> restart -> verify valid).
**Example:**
```typescript
test.describe.serial('License Renewal Lifecycle', () => {
  test.beforeAll(async () => {
    // Start container with expired license
    execSync('docker compose -f ... up -d api-renewal-test');
    await waitForContainer(LICENSE_TEST_URL);
  });

  test('Step 1: verify 503 with expired license', async () => {
    const resp = await fetch(`${URL}/api/routes`);
    expect(resp.status).toBe(503);
  });

  test('Step 2: drop renewal.key into container', async () => {
    execSync('docker cp renewal.key container:/app/renewal.key');
    execSync('docker compose restart api-renewal-test');
    await waitForContainer(URL);
  });

  test('Step 3: verify VALID after renewal', async () => {
    const resp = await fetch(`${URL}/health`);
    const body = await resp.json();
    expect(body.license.status).toBe('valid');
  });
});
```

### Pattern 3: Docker Exec for In-Container File Modification
**What:** Use `docker exec` to modify protected files inside a running container to trigger integrity check failures.
**When to use:** Integrity tamper detection test.
**Example:**
```typescript
test('integrity tamper detected on re-validation', async () => {
  // Container running with valid license and REVALIDATION_INTERVAL=10
  // Modify a protected file inside the running container
  execSync(
    'docker exec api-security-test sh -c "echo tampered >> /app/apps/kerala_delivery/api/main.py"'
  );

  // Send 10 requests to trigger re-validation
  for (let i = 0; i < 10; i++) {
    await fetch(`${URL}/api/routes`);
  }

  // Container should have exited (SystemExit from integrity failure)
  // Verify container is stopped or next request fails
});
```

### Pattern 4: REVALIDATION_INTERVAL Env Var Override
**What:** Add env var override to `license_manager.py` so tests can use a low threshold (10) instead of the production default (500).
**When to use:** Re-validation E2E tests -- avoids sending 500 requests per cycle.
**Implementation:**
```python
# In license_manager.py, replace hardcoded 500:
_REVALIDATION_INTERVAL = int(os.environ.get("REVALIDATION_INTERVAL", "500"))

# In maybe_revalidate():
if _request_counter % _REVALIDATION_INTERVAL != 0:
    return
```

### Anti-Patterns to Avoid
- **Running security E2E tests in the main Playwright suite:** These tests start/stop Docker containers and take 30-60s each. They must be a separate CI step or Playwright project, gated to main branch pushes.
- **Using the dev-mode Docker compose for security tests:** Dev mode (`ENVIRONMENT=development`) skips all enforcement. Tests must use production mode with real license keys.
- **Hardcoding license keys in test files:** Generate valid keys dynamically during `beforeAll` using the local machine's fingerprint to ensure tests work on any machine.
- **Modifying `_INTEGRITY_MANIFEST` for tests:** The manifest is empty in dev mode (no file checking). Tests must run in production-mode containers where the manifest is populated by `build-dist.sh`. For tamper tests, the approach is simpler: start a production container with a valid manifest, then modify a file via `docker exec`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Container readiness polling | Custom HTTP retry loop | Existing `waitForContainer()` from license.spec.ts | Handles exponential backoff, timeout, error reporting |
| License key generation for tests | Manual key string construction | `generate_license.py --this-machine` via exec | Ensures proper HMAC signing, fingerprint matching |
| Markdown documentation templates | Custom doc format | Existing LICENSING.md structure (overview, dev guide, customer guide, lifecycle, troubleshooting) | Proven information architecture |
| Error message discovery | Manual code reading | `grep -rn "logger\.\(error\|warning\)" core/licensing/` + grep for user-facing messages | Systematic, complete, auditable |

## Common Pitfalls

### Pitfall 1: Docker Container User Permissions
**What goes wrong:** `docker exec` commands fail because the container runs as non-root user (appuser, UID 1001). Writing/modifying files in the container may fail with permission errors.
**Why it happens:** The Dockerfile uses `USER appuser` for security. The appuser cannot modify files owned by root (like the application code copied during build).
**How to avoid:** Use `docker exec --user root` when modifying files for tamper tests. The container runs as appuser, but test-time exec can override.
**Warning signs:** "Permission denied" errors in docker exec output.

### Pitfall 2: Container Not Restarting After SystemExit
**What goes wrong:** After integrity failure triggers `SystemExit`, the container stops and Docker Compose may or may not restart it depending on the restart policy.
**Why it happens:** The default Dockerfile has no `restart: always` policy. `SystemExit` causes a graceful shutdown.
**How to avoid:** For tamper detection tests, verify the container state after sending the triggering requests. Use `docker inspect --format='{{.State.Status}}'` to check if the container exited. The test asserts the container stopped (or that subsequent requests fail), not that it restarted.
**Warning signs:** Tests expecting the container to restart automatically when it stays stopped.

### Pitfall 3: REVALIDATION_INTERVAL Not Visible in .so
**What goes wrong:** The `REVALIDATION_INTERVAL` env var is added to `license_manager.py`, but in production builds this file is compiled to `.so`. The env var read happens at module import time, so it works the same in both formats.
**Why it happens:** Python reads `os.environ.get()` at module load time regardless of whether the code is in `.py` or `.so`.
**How to avoid:** Use module-level constant `_REVALIDATION_INTERVAL = int(os.environ.get("REVALIDATION_INTERVAL", "500"))`. This is evaluated at import time, before any requests are processed.
**Warning signs:** None expected -- this works identically in .py and .so.

### Pitfall 4: License Key Fingerprint Mismatch in CI
**What goes wrong:** E2E tests generate a license key using the host machine's fingerprint, but the Docker container has a different fingerprint because `/etc/machine-id` is not mounted.
**Why it happens:** The license test compose override must explicitly mount `/etc/machine-id:ro` for the container fingerprint to match the host's fingerprint.
**How to avoid:** All test compose services must include `- /etc/machine-id:/etc/machine-id:ro` in volumes. For the fingerprint mismatch test, deliberately omit this mount OR generate a key with a fake fingerprint.
**Warning signs:** "License key is not valid for this machine" on tests that should pass.

### Pitfall 5: Outdated LICENSING.md Content Surviving Rewrite
**What goes wrong:** Copy-paste from old LICENSING.md introduces stale information (old fingerprint formula, .pyc references, no renewal.key, no integrity checking).
**Why it happens:** The current LICENSING.md references `hostname + MAC + container_id` fingerprint (Phase 5 changed to `machine-id + CPU model`), `.pyc` (Phase 6 changed to `.so`), and lacks sections for renewal.key (Phase 9), integrity checking (Phase 7), and periodic re-validation (Phase 8).
**How to avoid:** Write LICENSING.md from scratch using the actual codebase as source of truth. Cross-reference `license_manager.py`, `enforcement.py`, `get_machine_id.py`, `build-dist.sh` for current behavior.
**Warning signs:** Any reference to: hostname, MAC, container_id, .pyc, "compile to bytecode".

### Pitfall 6: Race Condition in Tamper + Revalidation Test
**What goes wrong:** File modification via `docker exec` and request sending happen concurrently; the revalidation check may fire before or after the file modification.
**Why it happens:** `docker exec` modifies the file system, but the Python process inside the container checks files only on every Nth request. If requests are already in-flight, timing matters.
**How to avoid:** Modify the file first, then send the batch of requests that triggers revalidation. Use `REVALIDATION_INTERVAL=10` and send exactly 10 requests after the modification. Add a small delay after `docker exec` to ensure the filesystem write completes.
**Warning signs:** Test passes intermittently -- sometimes the integrity check fires before the file is modified.

## Code Examples

### Generating a Valid License Key for Tests
```bash
# Source: scripts/generate_license.py
# Generate key that matches the current host machine's fingerprint
python scripts/generate_license.py \
  --customer "e2e-test" \
  --this-machine \
  --months 1 \
  --verify
```

### Generating an Expired License Key for Renewal Tests
```python
# Source: core/licensing/license_manager.py encode_license_key()
# Generate a key expired 10 days ago (past grace period)
from core.licensing.license_manager import encode_license_key, get_machine_fingerprint
from datetime import datetime, timedelta, timezone

expired_key = encode_license_key(
    customer_id="renewal-test",
    fingerprint=get_machine_fingerprint(),
    expires_at=datetime.now(timezone.utc) - timedelta(days=10),
)
```

### Generating a Fingerprint-Mismatched Key
```python
# Generate a key bound to a fake fingerprint (all zeros)
from core.licensing.license_manager import encode_license_key
from datetime import datetime, timedelta, timezone

mismatched_key = encode_license_key(
    customer_id="mismatch-test",
    fingerprint="0" * 64,  # Will not match any real machine
    expires_at=datetime.now(timezone.utc) + timedelta(days=30),
)
```

### Health Endpoint License Section (v2.1)
```json
// Source: apps/kerala_delivery/api/main.py:721-730
{
  "status": "healthy",
  "license": {
    "status": "valid",
    "expires_at": "2027-03-11",
    "days_remaining": 365,
    "fingerprint_match": true
  }
}
```

### X-License-Expires-In Header
```
// Source: core/licensing/enforcement.py:92-99
X-License-Expires-In: 365d
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| hostname + MAC + container_id fingerprint | /etc/machine-id + CPU model | Phase 5 | Breaking change -- all keys invalidated |
| .pyc bytecode compilation | .so native compilation (Cython) | Phase 6 | Much harder to decompile |
| Human-readable HMAC seed | bytes.fromhex() HMAC seed | Phase 6 | Breaking change -- old keys unverifiable |
| License checked only at startup | Every 500 requests re-validation | Phase 8 | Ongoing runtime protection |
| No file integrity checking | SHA256 manifest in compiled .so | Phase 7 | Tamper detection at startup and runtime |
| Full re-keying for renewal | Drop renewal.key file | Phase 9 | Simpler customer renewal workflow |
| No expiry visibility | X-License-Expires-In header | Phase 9 | Monitoring-friendly |
| No license in /health | License section in /health body | Phase 9 | Diagnostic-friendly |

**Outdated content in current LICENSING.md (must be rewritten):**
- References `hostname + MAC + container_id` fingerprint formula (line 52-53, 269)
- References `.pyc` compilation (line 189, 235)
- No mention of `renewal.key` file drop renewal
- No mention of integrity checking or `_INTEGRITY_MANIFEST`
- No mention of periodic re-validation (every 500 requests)
- No mention of `X-License-Expires-In` header
- No mention of `/health` license section
- Security notes reference old "HMAC key derived via PBKDF2 from a seed" but don't mention rotation
- Build pipeline section references `.pyc` compilation, not Cython `.so`

## Error Messages Audit (Phases 5-9)

Error messages to add to ERROR-MAP.md, based on codebase grep:

| Message | Source | Phase |
|---------|--------|-------|
| "No license key found. Set LICENSE_KEY env var or place license.key file." | `core/licensing/license_manager.py:411` | Pre-existing |
| "Invalid license key format or tampered key." | `core/licensing/license_manager.py:419` | Pre-existing |
| "License key is not valid for this machine. Run scripts/get_machine_id.py and send the output to support." | `core/licensing/license_manager.py:436-438` | Phase 5 (updated message) |
| "License expired beyond grace period. Contact support." | `core/licensing/license_manager.py:347` | Pre-existing |
| "License expired or invalid. Contact support." | `core/licensing/enforcement.py:203` | Phase 7 (503 body) |
| "File integrity check failed. Protected files have been modified." | `core/licensing/enforcement.py:171` | Phase 7 (SystemExit) |
| "Runtime integrity check failed. Protected files modified." | `core/licensing/license_manager.py:566` | Phase 8 (SystemExit) |

**Response headers to document:**
| Header | Source | Phase |
|--------|--------|-------|
| `X-License-Status: invalid` | `core/licensing/enforcement.py:193` | Phase 7 |
| `X-License-Warning: License in grace period` | `core/licensing/enforcement.py:215` | Phase 7 |
| `X-License-Expires-In: {N}d` | `core/licensing/enforcement.py:219` | Phase 9 |

## Open Questions

1. **Build-dist.sh for E2E tests?**
   - What we know: Integrity tamper tests need a populated `_INTEGRITY_MANIFEST` (non-empty dict), which only happens when `build-dist.sh` runs during distribution build. In development, the manifest is empty and integrity checks are skipped.
   - What's unclear: How to create a container with a populated manifest for E2E tests without running the full build pipeline.
   - Recommendation: For integrity tamper tests, the test can run `build-dist.sh` to create a tarball, build a Docker image from it, and run that container. Alternatively, use `docker exec` to inject a manifest directly into the running container's `license_manager.py` (or `.so`). The simpler approach may be a dedicated test Dockerfile that injects a manifest at build time. The planner should decide the exact approach. **Key insight:** the test compose override could set `REVALIDATION_INTERVAL=10` and use a custom Dockerfile stage that populates the manifest.

2. **CI step configuration**
   - What we know: Security tests should be a separate CI step, gated to main branch. Current ci.yml has 4 jobs (test, dashboard, docker, e2e).
   - What's unclear: Whether to add as a 5th Playwright project in the existing e2e job or a completely separate job.
   - Recommendation: Separate job `e2e-security` that runs after `docker` job, only on push to main. Uses its own compose override. This keeps the existing e2e job unchanged and prevents security test failures from blocking regular E2E tests.

3. **Renewal test license key generation**
   - What we know: The renewal test needs an expired license key AND a valid renewal.key, both bound to the same machine fingerprint.
   - What's unclear: Whether to generate these keys inline in the test (requires Python call from Node) or pre-generate them in a test setup script.
   - Recommendation: Use `execSync('python scripts/generate_license.py ...')` in the test `beforeAll` to generate both keys. The `--this-machine` flag ensures fingerprint matches. Use `--months -1` or direct Python for the expired key (the CLI may not support negative months).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Playwright ^1.58.2 |
| Config file | `playwright.config.ts` |
| Quick run command | `npx playwright test --project=license` |
| Full suite command | `npx playwright test` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DOC-01a | Integrity tamper detection | E2E (Docker) | `npx playwright test e2e/security-pipeline.spec.ts -g "integrity tamper"` | No -- Wave 0 |
| DOC-01b | Periodic re-validation triggering | E2E (Docker) | `npx playwright test e2e/security-pipeline.spec.ts -g "re-validation"` | No -- Wave 0 |
| DOC-01c | License renewal via file drop | E2E (Docker) | `npx playwright test e2e/security-pipeline.spec.ts -g "renewal"` | No -- Wave 0 |
| DOC-01d | Fingerprint mismatch rejection | E2E (Docker) | `npx playwright test e2e/security-pipeline.spec.ts -g "fingerprint"` | No -- Wave 0 |
| DOC-02 | Documentation updated | manual-only | Visual review of LICENSING.md, SETUP.md, ERROR-MAP.md | N/A |
| DOC-03 | Migration document updated | manual-only | Visual review of MIGRATION.md | N/A |

### Sampling Rate
- **Per task commit:** `npx playwright test e2e/security-pipeline.spec.ts --workers=1`
- **Per wave merge:** `npx playwright test --workers=1`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `e2e/security-pipeline.spec.ts` -- covers DOC-01a through DOC-01d
- [ ] `docker-compose.license-test.yml` updates -- new service configs for security tests
- [ ] `REVALIDATION_INTERVAL` env var in `core/licensing/license_manager.py` -- makes re-validation testable
- [ ] Test key generation helper (expired key, mismatched fingerprint key, valid renewal key)

## Sources

### Primary (HIGH confidence)
- `e2e/license.spec.ts` -- existing Docker-based E2E test patterns (container lifecycle, waitForContainer, execSync)
- `core/licensing/license_manager.py` -- complete licensing module source (fingerprint, encode/decode, validate, integrity, revalidation)
- `core/licensing/enforcement.py` -- middleware, renewal, headers, enforce() entry point
- `docker-compose.license-test.yml` -- existing test container override pattern
- `playwright.config.ts` -- 4-project config structure
- `docs/LICENSING.md` -- current content (confirmed outdated for v2.1)
- `docs/MIGRATION.md` -- Phase 6 migration document (needs v2.1 verification steps)
- `docs/ERROR-MAP.md` -- current error traceability format (25 entries, needs v2.1 additions)
- `docs/SETUP.md` -- current setup guide (needs machine-id, renewal.key, monitoring)
- `scripts/build-dist.sh` -- distribution pipeline (manifest injection, Cython compilation)
- `.github/workflows/ci.yml` -- current CI structure (4 jobs)

### Secondary (MEDIUM confidence)
- Playwright documentation for `test.describe.serial()` and container management patterns

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all tools already in use, no new dependencies needed
- Architecture: HIGH -- extending proven Docker test patterns from existing license.spec.ts
- Pitfalls: HIGH -- all pitfalls derived from direct codebase analysis (Dockerfile USER, compose volumes, hardcoded 500, etc.)
- Documentation gaps: HIGH -- line-by-line comparison of current docs vs actual codebase

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (stable -- no external dependencies changing)
