# Licensing Guide

> **Audience:** Developer

This document covers how the software licensing system works, how to generate
license keys (developer), and how to activate them (customer/employee).

---

## Overview

The software uses **hardware-bound license keys** that tie each installation to
a specific machine. Without a valid license key, the API returns `503 Service
Unavailable` on all endpoints (except `/health`).

```
Customer machine                      Developer machine
─────────────────                     ──────────────────
get_machine_id.py                     generate_license.py
       │                                     │
       ▼                                     ▼
  Fingerprint hash  ──── (send) ────▶  License key string
  (64-char hex)                       (LPG-XXXX-XXXX-...)
                                             │
                     ◀── (send back) ────────┘
                            │
                            ▼
                    .env or license.key
                            │
                            ▼
                    API validates on startup
```

---

## For Developers: Generating a License Key

### Step 1: Get the customer's machine fingerprint

The customer runs this on **their** machine (inside the Docker API container in
production):

```bash
# If running in Docker (production):
docker compose -f docker-compose.prod.yml --env-file .env.production \
  run --rm api python scripts/get_machine_id.py

# If running locally (development):
python scripts/get_machine_id.py
```

This outputs a 64-character hex string (SHA256 hash of hostname + MAC + container ID).
The customer sends this fingerprint to you.

### Step 2: Generate the license key

On **your** (developer) machine:

```bash
# Activate the virtual environment
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
| `--customer` | Customer identifier (e.g., `vatakara-lpg-01`) — required |
| `--fingerprint` | 64-char hex from `get_machine_id.py` |
| `--this-machine` | Use your own machine's fingerprint (for testing) |
| `--months` | License duration in months (default: 6) |
| `--verify` | Verify the generated key decodes correctly |

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

Send the `LPG-XXXX-...` key to the customer.

---

## For Customers/Employees: Activating a License

You received a license key string (starts with `LPG-`). Two ways to activate:

### Option A: Environment variable (recommended for production)

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

The API reads this file on startup. In Docker, it's mounted read-only into the
container automatically.

### Verifying activation

After restarting, check:

```bash
curl http://localhost:8000/health
```

If the license is valid, the API responds normally. If invalid or expired, all
endpoints (except `/health`) return `503`.

### License expiry and renewal

- **Valid:** API works normally.
- **Grace period:** License expired within the last 7 days. API still works but
  adds an `X-License-Warning` header to all responses. Contact the software
  provider to renew.
- **Expired:** License expired more than 7 days ago. API returns 503 on all
  endpoints. Get a new license key.

To renew: run `get_machine_id.py` again (the fingerprint may have changed if the
Docker container was recreated), send the fingerprint to the developer, and
receive a new key.

---

## Dev vs Production: What's Different

### Development environment (for developers)

- **Source code:** Full source including tests, planning docs, AI agent configs
- **License:** Not enforced — set `ENVIRONMENT=development` (default) to skip
  license checks, or generate a dev license with `--this-machine`
- **Docker Compose:** `docker-compose.yml` — ports exposed for debugging
- **Scripts included:** `generate_license.py` (the signing tool)
- **Files present:** `tests/`, `.planning/`, `.github/`, `docs/GUIDE.md`,
  `CLAUDE.md`, `pytest.ini`

```bash
# Start dev environment
docker compose up -d
# Dashboard dev server with hot reload
cd apps/kerala_delivery/dashboard && npm run dev
```

### Production / employee software (distributed to customers)

- **Source code:** Licensing module compiled to `.pyc` (bytecode only)
- **License:** **Required** — API will not serve requests without a valid key
- **Docker Compose:** `docker-compose.prod.yml` — only ports 80/443 exposed
  through Caddy reverse proxy with auto-TLS
- **Scripts excluded:** `generate_license.py` is NOT included
- **Files excluded:** `tests/`, `.planning/`, `.github/`, `docs/GUIDE.md`,
  `CLAUDE.md`, `pytest.ini`, `.env.production.example`

```bash
# Build distribution tarball
./scripts/build-dist.sh v1.3

# Output: dist/kerala-delivery-v1.3.tar.gz
```

### Building a distribution for customers

The `build-dist.sh` script creates a clean tarball:

```bash
./scripts/build-dist.sh v1.3
```

What it does:
1. Copies the project tree (excluding dev-only files)
2. Compiles `core/licensing/` to `.pyc` bytecode (hides HMAC signing logic)
3. Removes `.py` source from the licensing module only
4. Validates that `.pyc` imports work correctly
5. Creates `dist/kerala-delivery-v1.3.tar.gz`

**What's stripped from the distribution:**

| Excluded | Reason |
|----------|--------|
| `.git/` | Version control history |
| `tests/` | Developer test suite |
| `.planning/` | Design docs and planning artifacts |
| `.github/`, `.claude/` | AI agent configs |
| `scripts/generate_license.py` | License signing tool (developer-only) |
| `GUIDE.md`, `CLAUDE.md` | Developer-only documentation |
| `.env.production.example` | Template with comments about internals |
| `docker-compose.prod.yml` | Included separately or pre-configured |

**What's included in the distribution:**

| Included | Purpose |
|----------|---------|
| `core/` (with `.pyc` licensing) | Application logic |
| `apps/` | Kerala delivery app |
| `infra/` | Docker configs, migrations |
| `scripts/` (minus generate_license) | Setup, start, backup, machine ID |
| `docker-compose.yml` | Service stack |
| `README.md`, `docs/DEPLOY.md`, `docs/CSV_FORMAT.md`, `docs/SETUP.md` | User documentation |
| `ATTRIBUTION.md` | Third-party license obligations |
| `.env.example` | Environment template |

### How to tell if you're running dev or production

| Check | Development | Production |
|-------|-------------|------------|
| `core/licensing/license_manager.py` exists | Yes (`.py` source) | No (`.pyc` only) |
| `scripts/generate_license.py` exists | Yes | No |
| `tests/` directory exists | Yes | No |
| `ENVIRONMENT` env var | `development` (or unset) | `production` |
| Docker Compose file | `docker-compose.yml` | `docker-compose.prod.yml` |
| Exposed ports | 8000, 5432, 5000, 3000 | 80, 443 only (via Caddy) |
| API docs at `/docs` | Available | Disabled |

---

## Security Notes

- `generate_license.py` must **never** be shipped to customers. It contains the
  HMAC signing logic that creates valid license keys.
- The HMAC key is derived via PBKDF2 from a seed embedded in the licensing module.
  The `.pyc` compilation raises the bar against casual inspection but is not
  unbreakable — this is acceptable for the threat model (preventing casual
  copying, not determined piracy).
- License keys encode: customer ID + expiry timestamp + machine fingerprint prefix
  + HMAC signature. Tampering with any component invalidates the signature.
- The machine fingerprint combines hostname + MAC address + Docker container ID.
  Copying the software to a different machine invalidates the license.

---

## License Lifecycle

The full license lifecycle from generation to renewal:

```
Developer                              Customer
─────────                              ────────

1. GENERATE                            2. DELIVER
   generate_license.py  ─── key ──────▶  Receive LPG-XXXX key
   (on dev machine)                       (via email / secure channel)
                                              │
                                              ▼
                                       3. ACTIVATE
                                          Set LICENSE_KEY in .env
                                          or create license.key file
                                              │
                                              ▼
                                       4. MONITOR
                                          API runs normally
                                          Watch for X-License-Warning header
                                              │
                                         ┌────┴────┐
                                         │         │
                                         ▼         ▼
                                    5. RENEW    TROUBLESHOOT
                                    (if expiring)  (if 503)
```

**Stage details:**

| Stage | What happens | Reference |
|-------|-------------|-----------|
| Generate | Developer creates a key bound to the customer's machine fingerprint | [Generating a License Key](#for-developers-generating-a-license-key) |
| Deliver | Key is sent to the customer alongside the distribution tarball | [DISTRIBUTION.md](DISTRIBUTION.md#step-3-deliver-to-customer) |
| Activate | Customer sets the key in `.env` or `license.key` and restarts | [Activating a License](#for-customersemployees-activating-a-license) |
| Monitor | Check for `X-License-Warning` header during grace period | [Grace Period Monitoring](#grace-period-monitoring) below |
| Renew | Get new fingerprint, generate new key, update and restart | [Renewal Process](#renewal-process) below |
| Troubleshoot | Diagnose 503 errors -- license vs other causes | [Troubleshooting License 503](#troubleshooting-license-503) below |

---

## Grace Period Monitoring

When a license expires, the system enters a **7-day grace period** before shutting down API access. During this grace period, the API continues to work normally but adds a warning header to every response.

### How it works

From `core/licensing/license_manager.py`:

- `GRACE_PERIOD_DAYS = 7` -- the window after expiry where the API still works
- License status transitions: `VALID` -> `GRACE` -> `INVALID`

| Status | Behavior |
|--------|----------|
| `VALID` | API works normally, no warnings |
| `GRACE` | API works but adds `X-License-Warning` header to all responses |
| `INVALID` | API returns `503 Service Unavailable` on all endpoints (except `/health`) |

### Detecting grace period

Check for the `X-License-Warning` header on any API response:

```bash
curl -I http://localhost:8000/api/routes
```

During grace period, you'll see a header like:

```
X-License-Warning: License expired 3 days ago. Grace period: 4 days left. Contact support to renew.
```

If **no** `X-License-Warning` header is present, the license is either valid (not expired) or already past the grace period (returning 503).

### What the warning contains

The `X-License-Warning` header includes:
- How many days ago the license expired
- How many grace period days remain
- A prompt to contact support for renewal

### What happens when the grace period ends

After 7 days past expiry:
- All API endpoints return `503 Service Unavailable`
- The `/health` endpoint still responds (for monitoring tools to detect the server is running)
- The system requires a new license key to resume operation

---

## Renewal Process

When a license is approaching expiry or has entered the grace period, follow these steps to renew.

### Step 1: Get the current machine fingerprint

The fingerprint may have changed since the original license was generated (e.g., if the Docker container was recreated, or the hostname changed). Always get a fresh fingerprint:

```bash
# On the customer's machine (production):
docker compose -f docker-compose.prod.yml --env-file .env.production \
  run --rm api python scripts/get_machine_id.py
```

This outputs a 64-character hex string. The customer sends this to the developer.

### Step 2: Developer generates a new key

On the developer's machine:

```bash
source .venv/bin/activate

python scripts/generate_license.py \
  --customer "vatakara-lpg-01" \
  --fingerprint "abc123def456789..." \
  --months 12 \
  --verify
```

Use the **new** fingerprint from Step 1. The `--verify` flag confirms the key decodes correctly before sending it.

### Step 3: Customer updates the license key

**Option A -- Environment variable:**

```bash
# Edit .env.production and update:
LICENSE_KEY=LPG-NEW-KEY-HERE
```

**Option B -- License key file:**

```bash
echo "LPG-NEW-KEY-HERE" > license.key
```

### Step 4: Restart the application

```bash
# Production:
./scripts/deploy.sh

# Development:
docker compose restart api
```

### Step 5: Verify renewal

```bash
curl -I http://localhost:8000/health
```

The API should respond normally with no `X-License-Warning` header. If the header is still present or you get a 503, double-check the key value and restart again.

---

## Troubleshooting License 503

### "All endpoints return 503 Service Unavailable"

**Cause:** License has expired beyond the 7-day grace period, or no license key is configured.

**Fix:**

1. Check if a license key is set:
   ```bash
   grep LICENSE_KEY .env.production
   # or
   cat license.key
   ```

2. If no key is set, follow the [Activation](#for-customersemployees-activating-a-license) steps.

3. If a key is set but expired, follow the [Renewal Process](#renewal-process) above.

### "503 with 'License not valid for this machine'"

**Cause:** The machine fingerprint has changed since the license was generated. This happens when:
- The Docker container was recreated (container ID is part of the fingerprint)
- The server hostname was changed
- The software was copied to a different machine

**Fix:**

1. Get the current fingerprint:
   ```bash
   docker compose -f docker-compose.prod.yml --env-file .env.production \
     run --rm api python scripts/get_machine_id.py
   ```

2. Send the new fingerprint to the developer for a new key.

3. Update the key and restart (see [Renewal Process](#renewal-process)).

### "503 with 'Invalid license key format'"

**Cause:** The license key is corrupted, has extra whitespace, or was not copied correctly.

**Fix:**

1. Check the key value in `.env.production`:
   ```bash
   grep LICENSE_KEY .env.production
   ```

2. Verify the key starts with `LPG-` and contains no trailing newlines or spaces.

3. If using `license.key` file, ensure no extra whitespace:
   ```bash
   cat -A license.key
   # Should show the key followed by a single $ (newline), nothing else
   ```

4. If the key appears corrupted, request a new key from the developer.

### "Only /api/upload-orders fails, other endpoints work fine"

**Cause:** This is **not** a license issue. When the license is invalid, **all** endpoints return 503. If only the upload endpoint fails while other endpoints work normally, the issue is with the Google Maps Geocoding API.

**Fix:** See [GOOGLE-MAPS.md](GOOGLE-MAPS.md) for troubleshooting Google Maps API errors (REQUEST_DENIED, OVER_QUERY_LIMIT, etc.).
