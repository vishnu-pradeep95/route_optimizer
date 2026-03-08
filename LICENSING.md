# Licensing Guide

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
- **Files present:** `tests/`, `plan/`, `.planning/`, `.github/`, `GUIDE.md`,
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
- **Files excluded:** `tests/`, `plan/`, `.planning/`, `.github/`, `GUIDE.md`,
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
| `plan/`, `.planning/` | Design docs and session journals |
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
| `README.md`, `DEPLOY.md`, `CSV_FORMAT.md`, `SETUP.md` | User documentation |
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
