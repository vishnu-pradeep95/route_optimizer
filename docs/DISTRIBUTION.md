# Distribution Workflow

> **Audience:** Developer

> **Who this is for:** A developer who needs to build, deliver, and verify a customer distribution.

---

## Overview

A customer distribution is a self-contained tarball (`kerala-delivery-vX.Y.tar.gz`) containing the application, Docker configs, and setup scripts. The licensing module is compiled to `.pyc` bytecode so the HMAC signing logic is not exposed as source.

The end-to-end workflow:

```
Build tarball  ->  Generate license  ->  Deliver to customer  ->  Customer installs  ->  Verify
```

---

## Prerequisites

| Requirement | Why |
|-------------|-----|
| Python 3.12 | Must match the Docker image version -- `.pyc` files are version-specific and will not import on a different Python version |
| rsync | Used by `build-dist.sh` for selective file copying with exclusions |
| Virtual environment activated | `generate_license.py` requires project dependencies (`source .venv/bin/activate`) |
| Project root as working directory | All scripts use relative paths from the project root |

---

## Step 1: Build the Tarball

Run the build script with a version tag:

```bash
./scripts/build-dist.sh v1.4
```

The `v1.4` argument sets the version in the output filename. Use semantic versioning.

### What it does (6-step process)

1. **Copies the project tree** to a temporary staging directory using `rsync` with exclusions
2. **Strips developer-only artifacts** (tests, planning docs, AI agent configs, etc.)
3. **Compiles `core/licensing/`** to `.pyc` bytecode using `python3 -m compileall -b -f -q` (the `-b` flag is critical -- it places `.pyc` files in the same directory instead of `__pycache__/`, which is required for imports after `.py` removal)
4. **Removes `.py` source** from the licensing module only (`__init__.py` and `license_manager.py`)
5. **Validates `.pyc` imports** by running `import core.licensing; import core.licensing.license_manager` against the staged directory
6. **Creates the tarball** at `dist/kerala-delivery-v1.4.tar.gz`

### What's excluded from the distribution

| Excluded | Reason |
|----------|--------|
| `.git/` | Version control history |
| `.github/`, `.claude/`, `.vscode/`, `.playwright-mcp/`, `.agents/` | CI configs, AI agent configs, editor settings, test tooling |
| `tests/`, `.pytest_cache/` | Developer test suite and cache |
| `.planning/` | Design docs and planning artifacts |
| `.venv/`, `node_modules/`, `__pycache__/` | Environment-specific, rebuilt on install |
| `scripts/generate_license.py` | License signing tool -- must never reach customers |
| `docs/GUIDE.md`, `CLAUDE.md`, `pytest.ini`, `.gitignore` | Developer-only documentation and config |
| `.env`, `.env.production`, `.env.production.example` | Secrets and internal templates |
| `docker-compose.prod.yml` | Included separately or pre-configured for the customer |
| `dist/`, `backups/`, `data/` | Build artifacts, backups, runtime data |
| `gsd-template/`, `tools/` | Development tooling |

### What's included in the distribution

| Included | Purpose |
|----------|---------|
| `core/` (with `.pyc` licensing) | Application logic |
| `apps/` | Kerala delivery app (API, dashboard, driver PWA) |
| `infra/` | Dockerfiles, migrations, Caddy config |
| `scripts/` (minus `generate_license.py`) | Bootstrap, start, backup, machine ID scripts |
| `docker-compose.yml` | Service stack definition |
| `README.md` | Project overview and quick start |
| `docs/DEPLOY.md`, `docs/CSV_FORMAT.md`, `docs/SETUP.md` | User-facing documentation |
| `docs/DISTRIBUTION.md` | This document |
| `docs/LICENSING.md` | License activation and lifecycle guide |
| `docs/ATTRIBUTION.md` | Third-party license attributions |
| `.env.example` | Environment variable template |
| `license.key` (if present) | Pre-generated license key file |

### Output

```
dist/kerala-delivery-v1.4.tar.gz
```

---

## Step 2: Generate a License Key

The customer's machine must be fingerprinted before a key can be generated. If the customer hasn't installed yet, they'll need to come back to this step after Step 4.

### Get the customer's machine fingerprint

The customer runs this on **their** machine (inside the Docker API container):

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production \
  run --rm api python scripts/get_machine_id.py
```

This outputs a 64-character hex string (SHA256 of hostname + MAC + container ID). The customer sends this fingerprint to you.

### Generate the key

On **your** (developer) machine:

```bash
source .venv/bin/activate

python scripts/generate_license.py \
  --customer "vatakara-lpg-01" \
  --fingerprint "abc123def456789..." \
  --months 12 \
  --verify
```

| Flag | Description |
|------|-------------|
| `--customer` | Customer identifier (e.g., `vatakara-lpg-01`) -- required |
| `--fingerprint` | 64-char hex string from `get_machine_id.py` |
| `--this-machine` | Use your own fingerprint instead (for testing) |
| `--months` | License duration in months (default: 6) |
| `--verify` | Decode the generated key to confirm it's valid |

The output includes the `LPG-XXXX-XXXX-...` key string. Send this to the customer.

For full details on license generation options and key format, see [LICENSING.md](LICENSING.md#for-developers-generating-a-license-key).

---

## Step 3: Deliver to Customer

Transfer two items to the customer:

1. **The tarball:** `dist/kerala-delivery-v1.4.tar.gz`
2. **The license key:** The `LPG-XXXX-...` string (via secure channel -- email, encrypted message, etc.)

The tarball is self-contained -- it includes all Docker configs, setup scripts, and documentation. The customer does not need internet access to install (Docker images are built locally from the included Dockerfiles).

Alternatively, pre-load the license key into the tarball before delivery:

```bash
# Place the key file in the project root before building
echo "LPG-ABCD-EFGH-IJKL-MNOP-QRST-UVWX" > license.key
./scripts/build-dist.sh v1.4
# The tarball now includes license.key
```

---

## Step 4: Customer Installation

What the customer does after receiving the tarball and license key:

### Extract and enter the directory

```bash
tar xzf kerala-delivery-v1.4.tar.gz
cd kerala-delivery/
```

### Run the bootstrap script

```bash
./scripts/bootstrap.sh
```

This installs Docker (if not present), generates a `.env` file from `.env.example`, and prepares the environment. The script prompts for required values like database password and API key.

### Activate the license

**Option A -- Environment variable** (recommended):

```bash
# Edit .env.production and add:
LICENSE_KEY=LPG-ABCD-EFGH-IJKL-MNOP-QRST-UVWX
```

**Option B -- License key file:**

```bash
echo "LPG-ABCD-EFGH-IJKL-MNOP-QRST-UVWX" > license.key
```

### Start the application

```bash
./scripts/start.sh
```

### Verify it works

```bash
curl http://localhost:8000/health
```

A `200 OK` response with JSON status means the system is running. If it returns `503`, the license is not activated -- see [LICENSING.md](LICENSING.md#troubleshooting-license-503) for troubleshooting.

---

## Step 5: Verify the Distribution

Before delivering to a customer, verify the tarball works end-to-end using the verification script:

```bash
./scripts/verify-dist.sh dist/kerala-delivery-v1.4.tar.gz
```

### What it checks

1. **Extracts** the tarball to a temporary directory
2. **Generates** a dummy `.env` with random credentials (no prompts)
3. **Creates** an isolated Docker Compose file on port 8002 (avoids conflicts with any running stack on 8000)
4. **Builds and starts** essential services (db, db-init, dashboard-build, api -- skips OSRM/VROOM to avoid 300+ MB map data download)
5. **Verifies endpoints:**
   - `GET /health` -- returns 200
   - `GET /driver/` -- returns HTML
   - `GET /dashboard/` -- returns HTML
6. **Cleans up** all containers, volumes, and temp files on exit

### Reading the output

```
✓ Distribution verified! All 3 checks passed.

  Tarball: kerala-delivery-v1.4.tar.gz
  Checks:  /health (200), /driver/ (HTML), /dashboard/ (HTML)
```

If any check fails, the script prints diagnostic logs from the Docker containers.

For license-specific verification after the customer installs, see [LICENSING.md](LICENSING.md#verifying-activation).

---

## Troubleshooting

### ".pyc import failed" during build

**Cause:** Python version mismatch. The `.pyc` bytecode was compiled with a different Python version than the one running the import test.

**Fix:** Ensure you're running Python 3.12, which matches the Docker image version:

```bash
python3 --version
# Must show Python 3.12.x
```

### "Missing .env" during verification or startup

**Cause:** The bootstrap script was not run, or `.env.example` was not copied to `.env`.

**Fix:** Run `./scripts/bootstrap.sh` or manually copy:

```bash
cp .env.example .env
# Edit .env and set required values (POSTGRES_PASSWORD, API_KEY)
```

### "API returns 503 on all endpoints"

**Cause:** License key is not activated or has expired.

**Fix:** Follow the license activation steps in Step 4 above, or see [LICENSING.md](LICENSING.md#troubleshooting-license-503) for detailed 503 troubleshooting.

### "Verification script fails to build Docker images"

**Cause:** Docker is not running, or there's insufficient disk space.

**Fix:** Start Docker and check available space:

```bash
# Start Docker
sudo service docker start  # WSL
sudo systemctl start docker  # Linux

# Check disk space (need ~5 GB free)
df -h .
```
