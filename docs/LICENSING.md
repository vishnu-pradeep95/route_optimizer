# Licensing Guide (v2.1)

> **Audience:** Developer + Customer

This document covers the v2.1 licensing system: how license keys work, how to
generate and activate them, how to renew, and how to monitor and troubleshoot.

---

## Overview

The software uses **hardware-bound license keys** that tie each installation to
a specific machine. Without a valid license key, the API returns `503 Service
Unavailable` on all endpoints (except `/health`, which always responds for
monitoring purposes).

```
Customer machine                      Developer machine
-----------------                     ------------------
get_machine_id.py                     generate_license.py
       |                                     |
       v                                     v
  Fingerprint hash  ---- (send) ---->  License key string
  (SHA256 of                           (LPG-XXXX-XXXX-...)
   machine-id +                               |
   CPU model)        <-- (send back) ---------+
                            |
                            v
                    .env or license.key
                            |
                            v
                    API validates on startup
                            |
                            v
               +-----------+-----------+
               |           |           |
            VALID        GRACE      INVALID
          (API runs)  (API runs +  (503 on all
                       warning     endpoints)
                       header)
```

### What the license key encodes

Each key is a signed token containing:

- **Customer ID** (e.g., `vatakara-lpg-01`)
- **Expiry timestamp** (UTC)
- **Machine fingerprint prefix** (first 8 bytes of the SHA256 hash)
- **HMAC-SHA256 signature** (truncated to 8 bytes)

The key is base32-encoded and formatted as `LPG-XXXX-XXXX-XXXX-...`.
Tampering with any component invalidates the signature.

---

## For Developers: Generating a License Key

### Step 1: Get the customer's machine fingerprint

The customer runs this on **their** machine (inside the Docker API container in
production, or directly on the host):

```bash
# If running in Docker (production):
docker compose -f docker-compose.prod.yml --env-file .env.production \
  run --rm api python scripts/get_machine_id.py

# If running locally (development):
python scripts/get_machine_id.py
```

This outputs a 64-character hex string -- the SHA256 hash of two stable
machine identifiers:

| Component | Source | Why stable |
|-----------|--------|------------|
| `/etc/machine-id` | Systemd machine identifier | Unique per OS installation, persists across reboots. Must be bind-mounted into Docker containers. |
| CPU model name | `/proc/cpuinfo` | Hardware identifier, shared automatically between host and containers via the Linux kernel. |

The customer sends this fingerprint to the developer.

> **Why these two signals?** The v1.x formula used identifiers that differed
> between host and container (e.g., container names change on recreation, virtual
> network adapters get random addresses in WSL2). The v2.1 formula uses signals
> that are identical in both environments, so one license key works everywhere.

### Step 2: Generate the license key

On **your** (developer) machine:

```bash
source .venv/bin/activate

# Generate a 12-month license
python scripts/generate_license.py \
  --customer "vatakara-lpg-01" \
  --fingerprint "abc123def456789..." \
  --months 12 \
  --verify

# Generate for your own machine (testing):
python scripts/generate_license.py \
  --customer "dev-local" \
  --months 12 \
  --this-machine \
  --verify
```

**Options:**

| Flag | Description |
|------|-------------|
| `--customer` | Customer identifier (e.g., `vatakara-lpg-01`) -- required |
| `--fingerprint` | 64-char hex from `get_machine_id.py` |
| `--this-machine` | Use your own machine's fingerprint (for testing) |
| `--months` | License duration in months (default: 6) |
| `--verify` | Verify the generated key decodes correctly |
| `--renew` | Generate a renewal key (saved as `renewal.key` by customer) |

### Step 3: Send the key to the customer

The output looks like:

```
============================================================
  LICENSE KEY GENERATED
============================================================

  Customer:    vatakara-lpg-01
  Machine:     abc123def456789...
  Expires:     2027-03-07 12:00 UTC
  Duration:    12 months

  Key: LPG-ABCD-EFGH-IJKL-MNOP-QRST-UVWX

  To activate: set LICENSE_KEY environment variable or
  save the key to a file called 'license.key' in the project root.
```

Send the `LPG-XXXX-...` key to the customer via a secure channel.

---

## For Customers: Activating a License

You received a license key string (starts with `LPG-`). Two ways to activate:

### Option A: Environment variable (recommended)

Add to your `.env.production` file:

```bash
LICENSE_KEY=LPG-ABCD-EFGH-IJKL-MNOP-QRST-UVWX
```

Then restart:

```bash
./scripts/deploy.sh
```

### Option B: License key file

Save the key to a file called `license.key` in the project root:

```bash
echo "LPG-ABCD-EFGH-IJKL-MNOP-QRST-UVWX" > license.key
```

The API reads this file on startup. In Docker, the project root is `/app`.

### Verifying activation

After restarting, check the license status:

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

Expected output when the license is valid:

```json
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

Also check response headers:

```bash
curl -I http://localhost:8000/health
```

You should see:

```
X-License-Expires-In: 365d
```

If `license.status` is `"valid"` and `fingerprint_match` is `true`, the license
is working correctly.

---

## License Renewal

### Simple file drop renewal (recommended)

When a license is approaching expiry, use the file drop method -- no new
fingerprint exchange needed (the machine hasn't changed).

**Developer generates a renewal key:**

```bash
python scripts/generate_license.py \
  --customer "vatakara-lpg-01" \
  --fingerprint "same-fingerprint-as-before" \
  --months 12 \
  --renew \
  --verify
```

The `--renew` flag labels the output as a renewal key.

**Customer activates the renewal:**

1. Save the key as `renewal.key` in the project root (alongside `license.key`).
2. Restart the API:
   ```bash
   docker compose restart api
   ```

On startup, the API:
- Detects `renewal.key` and validates it
- If valid, replaces `license.key` with the new key content
- Deletes `renewal.key` (best-effort -- logged but non-fatal if read-only)
- Continues with the new expiry date

**Why file drop?** The renewal check runs *before* the one-way state guard
(`INVALID -> VALID` upgrades are normally blocked). By checking `renewal.key`
first, the system can transition directly to a valid state on restart.

### Full re-key renewal

If the machine fingerprint has changed (e.g., hardware swap, OS reinstall), the
customer must provide a new fingerprint:

1. Customer runs `python scripts/get_machine_id.py` and sends the new fingerprint
2. Developer generates a new key with `generate_license.py` using the new fingerprint
3. Customer updates `LICENSE_KEY` env var or `license.key` file
4. Restart the API

---

## Monitoring and Diagnostics

### Response headers

The API adds license-related headers to every response:

| Header | When | Example |
|--------|------|---------|
| `X-License-Expires-In` | Always (when license state exists) | `X-License-Expires-In: 45d` |
| `X-License-Warning` | During grace period only | `X-License-Warning: License in grace period` |
| `X-License-Status` | When license is invalid | `X-License-Status: invalid` |

### /health endpoint

The `/health` endpoint includes a `license` section in its response body:

```json
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

| Field | Description |
|-------|-------------|
| `status` | `"valid"`, `"grace"`, or `"invalid"` |
| `expires_at` | License expiry date (ISO 8601) |
| `days_remaining` | Days until expiry (negative = days past expiry) |
| `fingerprint_match` | Whether the license matches this machine |

> **Note:** The license section is purely informational in `/health`. An invalid
> license does not degrade the overall `/health` status -- this allows monitoring
> tools to detect that the server is running even when the license has expired.

### Quick diagnostic commands

```bash
# Check license status
curl -s http://localhost:8000/health | python3 -m json.tool

# Check expiry header on any endpoint
curl -I http://localhost:8000/api/routes

# Check if license warning is present (grace period)
curl -sI http://localhost:8000/api/routes | grep -i license
```

---

## Grace Period

When a license expires, the system enters a **7-day grace period** before
blocking API access. This gives customers time to renew without downtime.

### Status transitions

```
         expires           +7 days past expiry
  VALID ---------> GRACE -----------------> INVALID
   |                 |                         |
   | API works       | API works + warning     | 503 on all endpoints
   | normally        | header on all responses | (except /health)
```

| Status | Behavior | Duration |
|--------|----------|----------|
| `VALID` | API works normally, `X-License-Expires-In` header present | Until expiry date |
| `GRACE` | API works but adds `X-License-Warning` header to all responses | 7 days after expiry |
| `INVALID` | API returns 503 on all endpoints (except `/health`) | Until renewed |

### Detecting grace period

```bash
curl -I http://localhost:8000/api/routes
```

During grace period, you will see:

```
X-License-Warning: License in grace period
X-License-Expires-In: -3d
```

### One-way state guard

License status can only degrade during runtime: `VALID -> GRACE -> INVALID`.
Upgrades (e.g., `INVALID -> VALID`) require a restart. This prevents race
conditions during periodic re-validation and ensures state transitions are
predictable. The `renewal.key` mechanism works around this by running renewal
checks before the initial state is set.

---

## Dev vs Production

### Development environment

- **Source code:** Full `.py` source including tests, planning docs, AI agent configs
- **License:** Not enforced -- set `ENVIRONMENT=development` explicitly to skip
  license checks. **Note:** `ENVIRONMENT=development` must be explicitly set;
  production is the default.
- **Files present:** `tests/`, `.planning/`, `.github/`, `scripts/generate_license.py`

```bash
# Start dev environment
docker compose up -d
```

### Production / distribution (customer deployment)

- **Source code:** Licensing module compiled to native `.so` via Cython.
  The `.so` binary is significantly harder to decompile or inspect than
  interpreted formats.
- **License:** Required -- API returns 503 without a valid key
- **Scripts excluded:** `generate_license.py` is NOT included in the distribution

### Build pipeline

The `build-dist.sh` script creates a distribution tarball:

```bash
./scripts/build-dist.sh v2.1
```

Pipeline steps:

1. **Stage** -- Copy project tree, exclude dev-only files (`.git`, `tests/`, `.planning/`, `generate_license.py`)
2. **Strip dev-mode** -- Replace `ENVIRONMENT` checks with hardcoded `False` in staged `main.py`
3. **Validate** -- Zero `ENVIRONMENT` references in staged Python files
4. **Hash** -- Compute SHA256 of protected files (`main.py`, `enforcement.py`, `__init__.py`)
5. **Inject manifest** -- Embed SHA256 hashes into `license_manager.py` (replacing empty `_INTEGRITY_MANIFEST`)
6. **Compile** -- Cython compilation to `.so` via Docker (`python:3.12-slim` + Cython)
7. **Validate imports** -- `.so` loads correctly inside Docker
8. **Clean** -- Remove `.py` source from licensing module (keep `__init__.py` stub and `enforcement.py` async wrapper)
9. **Package** -- Create versioned tarball (`dist/kerala-delivery-v2.1.tar.gz`)

> **Why keep `enforcement.py` as `.py`?** Cython cannot compile `async def`
> functions (FastAPI middleware). `enforcement.py` is a thin async wrapper that
> calls synchronous functions in the compiled `.so`.

---

## Security Architecture

### Integrity checking

Protected files are verified against a SHA256 manifest at two points:

1. **At startup:** `enforce()` calls `verify_integrity()` -- if any protected
   file has been modified, the API exits with `SystemExit`.
2. **Every 500 requests:** `maybe_revalidate()` re-checks the manifest during
   runtime -- if tampering is detected, the API shuts down with `SystemExit`.

The manifest is an empty dict (`{}`) in development (no files to check). In
production builds, `build-dist.sh` computes SHA256 hashes and injects them into
`license_manager.py` before Cython compilation. The hashes are embedded in the
compiled `.so` and cannot be trivially modified.

**Protected files:**
- `apps/kerala_delivery/api/main.py`
- `core/licensing/enforcement.py`
- `core/licensing/__init__.py`

### Periodic re-validation

License status and file integrity are re-checked every 500 requests (offline,
no network calls):

1. Increment request counter on every request
2. At counter % 500 == 0, run:
   - SHA256 integrity check against embedded manifest
   - License expiry re-check (detect `VALID -> GRACE -> INVALID` transitions)
3. Reset counter to 0

This catches:
- Files modified after startup (tamper detection)
- License transitioning from valid to grace or invalid during long-running sessions

> **Dev mode:** Skipped when `_INTEGRITY_MANIFEST` is empty (development environment).

### Enforcement module

Single entry point: `enforce(app)` in `core/licensing/enforcement.py`. Called
once from `main.py` lifespan. Does:

1. Check for `renewal.key` (before normal validation -- bypasses state guard)
2. Validate license (from env var or file)
3. Verify file integrity (production only)
4. Register HTTP middleware for ongoing enforcement

`main.py` has no inline enforcement logic -- all enforcement flows through the
compiled module.

### HMAC signing

- **Key derivation:** PBKDF2 with SHA-256, 200,000 iterations
- **Seed:** Stored as `bytes.fromhex()` -- not human-readable, not greppable as
  a string in source code
- **Salt:** 16-byte random value, also stored as `bytes.fromhex()`
- **Signature:** HMAC-SHA256, truncated to 8 bytes for shorter key strings

The HMAC key, seed, and salt are all embedded in `license_manager.py`, which is
compiled to `.so` in distribution builds. The `.so` format raises the bar
significantly against casual extraction.

---

## License Lifecycle

```
Developer                              Customer
---------                              --------

1. GENERATE                            2. DELIVER
   generate_license.py  --- key ------>  Receive LPG-XXXX key
   (on dev machine)                       (via secure channel)
                                              |
                                              v
                                       3. ACTIVATE
                                          Set LICENSE_KEY in .env
                                          or create license.key file
                                              |
                                              v
                                       4. MONITOR
                                          API runs normally
                                          Watch X-License-Expires-In header
                                          Check /health license section
                                              |
                                         +----+----+
                                         |         |
                                         v         v
                                    5a. RENEW   5b. TROUBLESHOOT
                                    (file drop)    (if 503)
                                         |
                                    +----|----+
                                    |         |
                                    v         v
                              Simple      Full re-key
                              renewal     (new fingerprint)
                              (renewal.key  (get_machine_id.py
                               file drop)    + new key)
```

**Stage details:**

| Stage | What happens | Reference |
|-------|-------------|-----------|
| Generate | Developer creates a key bound to the customer's fingerprint | [Generating a License Key](#for-developers-generating-a-license-key) |
| Deliver | Key is sent to the customer alongside the distribution tarball | [DISTRIBUTION.md](DISTRIBUTION.md#step-3-deliver-to-customer) |
| Activate | Customer sets the key in `.env` or `license.key` and restarts | [Activating a License](#for-customers-activating-a-license) |
| Monitor | Check `/health` license section and response headers | [Monitoring and Diagnostics](#monitoring-and-diagnostics) |
| Renew (simple) | Developer generates renewal key, customer drops `renewal.key` file | [Simple file drop renewal](#simple-file-drop-renewal-recommended) |
| Renew (full) | New fingerprint + new key if machine changed | [Full re-key renewal](#full-re-key-renewal) |
| Troubleshoot | Diagnose 503 errors | [Troubleshooting](#troubleshooting) below |

---

## Troubleshooting

### 503 "License expired or invalid. Contact support."

**Cause:** License has expired beyond the 7-day grace period, or no license key
is configured.

**Diagnosis:**

```bash
# Check license status
curl -s http://localhost:8000/health | python3 -m json.tool
# Look at license.status and license.days_remaining

# Check if a license key is set
grep LICENSE_KEY .env.production
# or
cat license.key
```

**Fix:**
1. If no key is set, follow the [Activation](#for-customers-activating-a-license) steps.
2. If key is set but expired, follow the [Renewal](#license-renewal) steps.

---

### 503 "License key is not valid for this machine"

**Cause:** The machine fingerprint has changed since the license was generated.
The v2.1 fingerprint uses `/etc/machine-id` + CPU model name, which is stable
across Docker container recreation and reboots. Fingerprint changes only if:

- The OS was reinstalled (new `/etc/machine-id`)
- Hardware was swapped (different CPU model)
- `/etc/machine-id` is not bind-mounted into the Docker container

**Diagnosis:**

```bash
# Get current fingerprint
python scripts/get_machine_id.py
# or in Docker:
docker compose exec api python scripts/get_machine_id.py
```

**Fix:**
1. If using Docker, ensure `/etc/machine-id` is bind-mounted read-only:
   ```yaml
   volumes:
     - /etc/machine-id:/etc/machine-id:ro
   ```
2. Send the new fingerprint to the developer for a new license key.

---

### "File integrity check failed. Protected files have been modified."

**Cause:** One or more protected files (`main.py`, `enforcement.py`, `__init__.py`)
have been modified after the distribution was built. The SHA256 hash no longer
matches the manifest embedded in the compiled `.so`.

**Fix:**
1. Do not modify protected files in a production deployment.
2. Reinstall from the original distribution tarball:
   ```bash
   docker compose down
   tar xzf kerala-delivery-v2.1.tar.gz
   docker compose up -d
   ```

---

### "Runtime integrity check failed. Protected files modified."

**Cause:** Same as above, but detected during runtime (periodic re-validation
every 500 requests) rather than at startup. A protected file was modified while
the API was running.

**Fix:** Same as above -- reinstall from the distribution tarball.

---

### "Invalid license key format or tampered key."

**Cause:** The license key string is corrupted, has extra whitespace, or was not
copied correctly.

**Diagnosis:**

```bash
# Check the key value
grep LICENSE_KEY .env.production
# or
cat -A license.key
# Should show the key followed by a single $ (newline), nothing else
```

**Fix:**
1. Verify the key starts with `LPG-` and contains no trailing whitespace.
2. If the key appears corrupted, request a new key from the developer.

---

### "Only /api/upload-orders fails, other endpoints work fine"

**Cause:** This is NOT a license issue. When the license is invalid, ALL
endpoints return 503. If only the upload endpoint fails, the issue is with the
Google Maps Geocoding API.

**Fix:** See [GOOGLE-MAPS.md](GOOGLE-MAPS.md) for troubleshooting geocoding errors.

---

## Security Notes

- `generate_license.py` must **never** be shipped to customers. It contains the
  HMAC signing logic that creates valid license keys. The `build-dist.sh` script
  explicitly excludes it from the distribution.
- The compiled `.so` raises the bar against casual inspection. Native Cython
  compilation is significantly harder to reverse-engineer than interpreted
  formats. This is acceptable for the threat model (preventing casual copying,
  not determined piracy).
- The HMAC seed is stored as `bytes.fromhex()` -- not human-readable and not
  extractable by simple text search.
- License keys encode customer ID + expiry + fingerprint prefix + HMAC signature.
  Tampering with any component invalidates the signature.

---

## Source Code Reference

| Component | File | Purpose |
|-----------|------|---------|
| Fingerprinting | `core/licensing/license_manager.py` | `get_machine_fingerprint()` -- SHA256 of machine-id + CPU model |
| Key encoding/decoding | `core/licensing/license_manager.py` | `encode_license_key()`, `decode_license_key()` |
| Full validation | `core/licensing/license_manager.py` | `validate_license()` -- decode + fingerprint check + expiry |
| Integrity verification | `core/licensing/license_manager.py` | `verify_integrity()`, `maybe_revalidate()` |
| Enforcement entry point | `core/licensing/enforcement.py` | `enforce(app)` -- startup + middleware registration |
| Renewal handling | `core/licensing/enforcement.py` | `_try_load_renewal_key()`, `_handle_post_renewal()` |
| Expiry header | `core/licensing/enforcement.py` | `_compute_expires_header()` |
| Customer fingerprint tool | `scripts/get_machine_id.py` | Run on customer machine, outputs fingerprint |
| Developer key generator | `scripts/generate_license.py` | Run on developer machine, creates license keys |
| Distribution builder | `scripts/build-dist.sh` | Strips dev code, hashes files, compiles to .so, packages tarball |
