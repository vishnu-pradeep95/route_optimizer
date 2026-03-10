# Architecture Research: v2.1 Licensing & Distribution Security

**Domain:** Software licensing enforcement, code protection, integrity checking for a Python/Docker application
**Researched:** 2026-03-10
**Confidence:** HIGH (existing codebase thoroughly analyzed, Cython docs verified, integration points mapped)

## Existing System Overview

```
CURRENT LICENSING ARCHITECTURE
==============================

Developer Machine                    Customer Machine (WSL2 + Docker)
==================                   ================================

scripts/generate_license.py          docker-compose.yml
  |                                    |
  | encode_license_key()               | api container (:8000)
  |                                    |   |
  v                                    |   v
LPG-XXXX-XXXX key string              |  main.py lifespan (L162-203)
  |                                    |   |-- validate_license()
  | (sent to customer)                 |   |-- env == "development"? -> override to VALID  <-- LOOPHOLE #1
  |                                    |   |-- app.state.license_info = result
  v                                    |   |
LICENSE_KEY env var                     |  main.py middleware (L381-427)          <-- LOOPHOLE #2
  or license.key file                  |   |-- check app.state.license_info
                                       |   |-- INVALID -> 503
                                       |   |-- GRACE -> X-License-Warning header
                                       |   |-- VALID -> pass through
                                       |
                                       |  core/licensing/license_manager.py      <-- LOOPHOLE #4 (.pyc only)
                                       |   |-- get_machine_fingerprint()         <-- LOOPHOLE #3
                                       |   |   |-- platform.node()
                                       |   |   |-- uuid.getnode() (MAC)
                                       |   |   |-- _get_docker_container_id()    <-- ephemeral, changes on recreate
                                       |   |-- decode_license_key()
                                       |   |-- validate_license()
                                       |
                                       |  Startup-only check                     <-- LOOPHOLE #5
                                       |  No file integrity checking             <-- LOOPHOLE #6
                                       |
scripts/get_machine_id.py             scripts/get_machine_id.py (customer runs)
  (standalone copy)                     |-- same fingerprint logic as license_manager.py

BUILD PIPELINE:
scripts/build-dist.sh
  1. rsync project (exclude .git, tests, .planning, generate_license.py)
  2. compileall -b core/licensing/  -> .pyc (legacy placement)
  3. rm core/licensing/*.py (source removed)
  4. PYTHONPATH test import validation
  5. tar czf dist/kerala-delivery-vX.X.tar.gz
```

---

## Target Architecture (v2.1)

```
TARGET LICENSING ARCHITECTURE
==============================

Developer Machine                     Customer Machine (WSL2 + Docker)
==================                    ================================

scripts/generate_license.py           docker-compose.yml
  |-- encode_license_key()              |-- NEW: /etc/machine-id bind-mount (read-only)
  |-- NEW: --renew flag                 |
  v                                     | api container (:8000)
LPG-XXXX-XXXX key string               |   |
                                        |   v
                                        |  main.py (STRIPPED: no dev-mode block)
                                        |   |-- from core.licensing.enforcement import enforce
                                        |   |-- enforce(app)  <-- single call, everything else compiled
                                        |   |
                                        |  core/licensing/enforcement.so  (Cython-compiled)
                                        |   |-- enforce(app):
                                        |   |   |-- startup_validate()
                                        |   |   |-- register_middleware(app)
                                        |   |   |-- check_file_integrity()
                                        |   |
                                        |   |-- _INTEGRITY_MANIFEST = { ... }  (embedded SHA256 hashes)
                                        |   |-- _REQUEST_COUNTER (internal state)
                                        |   |-- _REVALIDATION_INTERVAL = 500
                                        |   |
                                        |   |-- middleware:
                                        |   |   |-- increment _REQUEST_COUNTER
                                        |   |   |-- if counter % N == 0: re-validate + re-check integrity
                                        |   |   |-- INVALID -> 503
                                        |   |   |-- GRACE -> X-License-Warning
                                        |   |
                                        |  core/licensing/license_manager.so  (Cython-compiled)
                                        |   |-- get_machine_fingerprint()  (STRENGTHENED)
                                        |   |   |-- platform.node()
                                        |   |   |-- uuid.getnode() (MAC)
                                        |   |   |-- /etc/machine-id (bind-mounted)
                                        |   |   |-- /proc/cpuinfo model name
                                        |   |   |-- NO container_id (dropped -- too ephemeral)
                                        |   |
                                        |   |-- validate_license()
                                        |   |-- decode_license_key()
                                        |   |-- encode_license_key()  <-- still here for renewal
                                        |   |
                                        |  core/licensing/__init__.so  (Cython-compiled)

BUILD PIPELINE (updated):
scripts/build-dist.sh
  1. rsync project (same exclusions + e2e/, docker-compose.license-test.yml)
  2. NEW: Strip dev-mode block from main.py (sed/awk removal)
  3. NEW: Generate SHA256 manifest of protected files
  4. NEW: Inject manifest into enforcement.py source
  5. NEW: Cython compile core/licensing/*.py -> .so (replaces compileall)
  6. rm core/licensing/*.py, core/licensing/*.c (source + intermediate removed)
  7. PYTHONPATH test import validation (.so loading)
  8. tar czf dist/kerala-delivery-vX.X.tar.gz
```

---

## New Components

### 1. `core/licensing/enforcement.py` (NEW file, compiled to .so)

**Responsibility:** Single entry point for all license enforcement. Absorbs the middleware logic currently in main.py and adds periodic re-validation + integrity checking.

**Why a new file instead of adding to license_manager.py:**
- `license_manager.py` has a clean single responsibility: key encoding/decoding/validation
- Enforcement (middleware registration, request counting, integrity checking) is a separate concern
- Splitting allows `generate_license.py` to import only `license_manager` without pulling in FastAPI dependencies
- Keeps the Cython compilation units focused

**Public API:**
```python
def enforce(app: FastAPI) -> None:
    """Register license enforcement on the app.

    Called once from main.py. Does:
    1. Validate license at startup
    2. Check file integrity against embedded manifest
    3. Register middleware for ongoing enforcement + periodic re-validation
    """
```

**Internal state (inside compiled .so, not on app.state):**
```python
_request_counter: int = 0
_license_info: LicenseInfo = None
_REVALIDATION_INTERVAL: int = 500  # re-validate every Nth request
_INTEGRITY_MANIFEST: dict[str, str] = {}  # populated at build time
```

**Why move state off app.state:**
Currently `app.state.license_info` is trivially patchable -- anyone can set it to VALID from a Python shell or by editing main.py. Moving the license state inside the compiled .so makes it inaccessible from outside the module (no `app.state.license_info = fake_valid`). The middleware closure captures the module-level variable directly.

### 2. `core/licensing/integrity.py` (NEW file, compiled to .so)

**Responsibility:** SHA256 file hashing and manifest verification.

**Why separate from enforcement.py:**
- Testability: integrity checking can be unit-tested independently
- The manifest constant will be injected by build-dist.sh before Cython compilation
- Clean separation: enforcement orchestrates, integrity checks files

**Public API:**
```python
def check_integrity(base_path: str = "/app") -> tuple[bool, list[str]]:
    """Verify protected files against embedded SHA256 manifest.

    Returns:
        (all_ok, list_of_failures)
        Failures are strings like "main.py: expected abc123, got def456"
    """
```

**Protected files (embedded in manifest):**
- `apps/kerala_delivery/api/main.py` -- the entrypoint that calls enforce()
- `docker-compose.yml` -- prevents adding ENVIRONMENT=development
- Any other critical files identified during implementation

### 3. Updated `core/licensing/license_manager.py` (MODIFIED, compiled to .so)

**Changes:**
- `get_machine_fingerprint()`: Add `/etc/machine-id` and `/proc/cpuinfo` signals, drop container_id
- Add `renew_license()` function for license renewal without new fingerprint

### 4. Updated `scripts/get_machine_id.py` (MODIFIED, shipped to customer)

**Changes:**
- Add `/etc/machine-id` reading
- Add `/proc/cpuinfo` model name extraction
- Drop `_get_docker_container_id()` function
- Note: This file is NOT compiled -- customer runs it as plain Python

### 5. Updated `scripts/generate_license.py` (MODIFIED, stays on developer machine)

**Changes:**
- Add `--renew` flag that takes an existing key and extends expiry without requiring a new fingerprint

### 6. Updated `scripts/build-dist.sh` (MODIFIED)

**Changes:**
- Replace `compileall` with Cython compilation
- Add dev-mode stripping step
- Add manifest generation and injection
- Update import validation for .so files

### 7. Updated `docker-compose.yml` (MODIFIED)

**Changes:**
- Add `/etc/machine-id` read-only bind mount to api service

### 8. Updated `infra/Dockerfile` (MODIFIED)

**Changes:**
- Builder stage: Add Cython + python3-dev as build dependencies
- Note: Cython compilation happens in build-dist.sh (on developer machine), NOT in the Docker build. The Dockerfile change is only needed if we want to support building inside Docker for CI/testing.

---

## Component Boundaries

### New Components

| Component | Responsibility | Communicates With | Status |
|-----------|---------------|-------------------|--------|
| `core/licensing/enforcement.py` | Middleware registration, periodic re-validation, integrity orchestration | `license_manager`, `integrity`, FastAPI app | **NEW** |
| `core/licensing/integrity.py` | SHA256 manifest verification | Filesystem (protected files) | **NEW** |

### Modified Components

| Component | What Changes | Why |
|-----------|--------------|-----|
| `core/licensing/license_manager.py` | Stronger fingerprint (machine-id, cpuinfo, drop container_id), renewal function | Loopholes #3, renewal feature |
| `core/licensing/__init__.py` | Re-export enforcement.enforce for clean import | Single import path |
| `scripts/build-dist.sh` | Cython compilation, dev-mode stripping, manifest generation | Loopholes #1, #2, #4, #6 |
| `scripts/get_machine_id.py` | New fingerprint signals, drop container_id | Must match license_manager changes |
| `scripts/generate_license.py` | Add --renew flag | License renewal feature |
| `scripts/verify-dist.sh` | Validate .so loading instead of .pyc | Must match build changes |
| `docker-compose.yml` | Add /etc/machine-id bind mount to api service | Fingerprint needs host machine-id |
| `docker-compose.license-test.yml` | Add /etc/machine-id bind mount, add test scenarios | Must match production setup |
| `infra/Dockerfile` | Add Cython + python3-dev to builder stage (if needed for CI) | Cython build support |
| `apps/kerala_delivery/api/main.py` | Replace inline middleware + dev-mode block with single enforce(app) call | Loopholes #1, #2 |
| `e2e/license.spec.ts` | Add tests for integrity failure, periodic re-validation, renewal | Test coverage for new features |
| `tests/core/licensing/test_license_manager.py` | Add tests for new fingerprint signals, renewal | Unit test coverage |

### Untouched Components

| Component | Why No Change |
|-----------|--------------|
| `apps/kerala_delivery/dashboard/` | Dashboard is not part of licensing |
| `apps/kerala_delivery/driver_app/` | Driver PWA is not part of licensing |
| `core/database/` | Database layer unchanged |
| `core/geocoding/` | Geocoding unrelated |
| `core/optimizer/` | Optimizer unrelated |
| PostgreSQL, OSRM, VROOM services | Infrastructure unchanged (except machine-id mount on api) |

---

## Data Flow Changes

### Current: Startup-only validation

```
Container start
  -> main.py lifespan
    -> validate_license()
    -> if dev mode: override to VALID    <-- stripped in v2.1
    -> app.state.license_info = result   <-- moved into enforcement.so
  -> middleware reads app.state          <-- replaced by closure in enforcement.so
  -> (runs forever, never re-checks)    <-- fixed by periodic re-validation
```

### Target: Continuous enforcement with integrity checking

```
Container start
  -> main.py lifespan
    -> enforce(app)                      <-- single call
      -> validate_license()              <-- inside enforcement.so
      -> check_integrity("/app")         <-- verify main.py, docker-compose.yml
      -> register middleware             <-- closure captures module-level state
  -> middleware (inside enforcement.so)
    -> every request: check cached license status
    -> every 500th request:
      -> validate_license()              <-- re-validate (expiry, fingerprint)
      -> check_integrity("/app")         <-- re-verify file hashes
      -> update cached status
    -> INVALID: return 503
    -> GRACE: add X-License-Warning header
    -> VALID: pass through
```

### Fingerprint Data Flow Change

```
CURRENT:  hostname | MAC | container_id  -> SHA256
TARGET:   hostname | MAC | /etc/machine-id | cpuinfo_model  -> SHA256

WSL2-specific:
  /etc/machine-id is the WSL instance's machine-id (persistent across reboots)
  /proc/cpuinfo model name is the host CPU (consistent across container recreates)
  container_id DROPPED (changes on every docker compose down/up)
```

### Build Pipeline Data Flow Change

```
CURRENT:
  rsync -> compileall (pyc) -> rm .py -> tar

TARGET:
  rsync
    -> strip dev-mode from main.py (sed removes lines 184-203)
    -> sha256sum protected files -> generate manifest dict
    -> inject manifest into enforcement.py source
    -> cythonize core/licensing/*.py -> .so files
    -> rm core/licensing/*.py core/licensing/*.c
    -> validate .so import
    -> tar
```

### License Renewal Data Flow

```
CURRENT:
  Customer sends fingerprint -> developer generates new key -> customer replaces key

TARGET (renewal):
  Customer's license approaching expiry
    -> developer runs: generate_license.py --renew --key <existing_key> --months 12
    -> generates new key with same fingerprint, new expiry
    -> customer replaces LICENSE_KEY or license.key file
    -> next periodic re-validation picks up new key automatically (no restart)
```

---

## Cython Compilation Architecture

### Why Cython Compiles Existing .py Files Directly

Cython supports "pure Python mode" -- it can compile regular `.py` files to `.so` without renaming to `.pyx`. The existing `license_manager.py` uses only stdlib imports (`hashlib`, `hmac`, `struct`, `base64`, `os`, `platform`, `uuid`) and standard Python constructs (`dataclass`, `Enum`). These all compile cleanly with Cython 3.x on Python 3.12.

### Build-time Setup

```python
# scripts/cython_build.py (NEW, used by build-dist.sh)
from setuptools import setup, Extension
from Cython.Build import cythonize

extensions = [
    Extension("core.licensing.license_manager",
              ["core/licensing/license_manager.py"]),
    Extension("core.licensing.enforcement",
              ["core/licensing/enforcement.py"]),
    Extension("core.licensing.integrity",
              ["core/licensing/integrity.py"]),
    Extension("core.licensing.__init__",
              ["core/licensing/__init__.py"]),
]

setup(
    ext_modules=cythonize(extensions, compiler_directives={
        "language_level": "3",
    }),
)
```

**Build command (inside build-dist.sh):**
```bash
cd "$STAGE"
PYTHONPATH="$STAGE" python3 scripts/cython_build.py build_ext --inplace
rm -f core/licensing/*.py core/licensing/*.c  # Remove source + C intermediate
rm -rf build/  # Remove setuptools build artifacts
```

### Output Files

```
core/licensing/
  __init__.cpython-312-x86_64-linux-gnu.so
  license_manager.cpython-312-x86_64-linux-gnu.so
  enforcement.cpython-312-x86_64-linux-gnu.so
  integrity.cpython-312-x86_64-linux-gnu.so
```

### Cython Build Dependencies

**Build-time only (developer machine):**
- `cython>=3.0` (pip install, NOT in requirements.txt)
- `python3-dev` (system package, provides Python.h headers)
- `gcc` (C compiler)

**Runtime (customer machine):**
- None -- .so files are self-contained native code
- Must match Python version (3.12) and platform (x86_64 Linux)

### Platform Lock-in Consideration

Cython .so files are platform-specific. The current deployment target is WSL2 on x86_64, which matches the developer's build machine. If deployment targets change (ARM, different Python version), the build must be done on a matching platform. This is acceptable for the current single-customer deployment model.

---

## File Integrity Manifest Architecture

### Manifest Generation (build-time)

```bash
# Inside build-dist.sh, AFTER stripping dev-mode, BEFORE Cython compilation:

MANIFEST=$(python3 -c "
import hashlib, json, os
files = {
    'apps/kerala_delivery/api/main.py': None,
    'docker-compose.yml': None,
}
for path in files:
    full = os.path.join('$STAGE', path)
    with open(full, 'rb') as f:
        files[path] = hashlib.sha256(f.read()).hexdigest()
print(json.dumps(files))
")

# Inject into enforcement.py before Cython compilation
sed -i "s|_INTEGRITY_MANIFEST = {}|_INTEGRITY_MANIFEST = $MANIFEST|" \
    "$STAGE/core/licensing/enforcement.py"
```

### Manifest Verification (runtime)

```python
# Inside enforcement.so (compiled)
def check_integrity(base_path: str = "/app") -> tuple[bool, list[str]]:
    failures = []
    for rel_path, expected_hash in _INTEGRITY_MANIFEST.items():
        full_path = os.path.join(base_path, rel_path)
        try:
            with open(full_path, "rb") as f:
                actual = hashlib.sha256(f.read()).hexdigest()
            if actual != expected_hash:
                failures.append(f"{rel_path}: modified")
        except FileNotFoundError:
            failures.append(f"{rel_path}: missing")
    return (len(failures) == 0, failures)
```

### What the Manifest Protects

| File | Why Protected | What Tampering Catches |
|------|--------------|----------------------|
| `apps/kerala_delivery/api/main.py` | Contains the `enforce(app)` call | Removing or bypassing the enforce() call |
| `docker-compose.yml` | Contains ENVIRONMENT variable | Adding ENVIRONMENT=development (irrelevant after dev-mode strip, but defense-in-depth) |

---

## Dev-Mode Stripping Architecture

### What Gets Stripped

In `main.py` lines 184-203, the current code has:

```python
else:
    # INVALID -- but only enforce in production. In dev, just warn.
    if env == "production":
        logger.error(...)
    else:
        logger.info("License not configured (dev mode)...")
        # In dev mode, override to VALID so the middleware doesn't block
        license_info = LicenseInfo(
            customer_id="dev-mode",
            fingerprint="",
            expires_at=...,
            status=LicenseStatus.VALID,
            days_remaining=999,
            message="Development mode -- no license required",
        )
        app.state.license_info = license_info
```

### Stripping Strategy

**Option A: Marker-based removal (recommended)**

Add comment markers in the source:

```python
    # DIST-STRIP-BEGIN
    else:
        logger.info("License not configured (dev mode)...")
        license_info = LicenseInfo(...)
        app.state.license_info = license_info
    # DIST-STRIP-END
```

Build-dist.sh uses sed to remove everything between markers:

```bash
sed -i '/# DIST-STRIP-BEGIN/,/# DIST-STRIP-END/d' "$STAGE/apps/kerala_delivery/api/main.py"
```

**Why markers instead of line numbers:** Line numbers are fragile -- any edit to main.py shifts them. Markers are self-documenting and resilient to code changes above/below.

### Post-Strip: main.py Changes

After stripping, the entire lifespan license block becomes:

```python
# main.py in distribution
from core.licensing.enforcement import enforce

# Inside lifespan:
enforce(app)  # All license logic is inside compiled .so
```

The full middleware (lines 381-427) is also removed from main.py, since `enforce()` registers its own middleware internally.

---

## Docker Compose Changes

### /etc/machine-id Bind Mount

```yaml
# docker-compose.yml (modified api service)
api:
  build:
    context: .
    dockerfile: infra/Dockerfile
  volumes:
    - ./data:/app/data
    - dashboard_assets:/srv/dashboard:ro
    - /etc/machine-id:/etc/machine-id:ro    # NEW: for fingerprinting
```

**WSL2 behavior:** `/etc/machine-id` in WSL2 is the instance's systemd machine-id. It is persistent across reboots on standard Ubuntu WSL (stored on the ext4 virtual disk). The NixOS-WSL tmpfs issue does not apply to standard Ubuntu/Debian WSL distros used in this project.

**Read-only mount:** `:ro` prevents the container from modifying the host's machine-id.

### docker-compose.license-test.yml Update

```yaml
# Must mirror the production mount
api-license-test:
  volumes:
    - /etc/machine-id:/etc/machine-id:ro    # NEW: match production
```

---

## Periodic Re-validation Architecture

### Why Request-Based (Not Timer-Based)

A background timer (`asyncio.create_task` with `asyncio.sleep`) has problems:
- Runs even when the app is idle (wasted cycles)
- Requires careful lifecycle management (cancel on shutdown)
- Interacts poorly with uvicorn worker forking (timer per worker)

Request-based re-validation is simpler: the middleware increments a counter on every request and re-validates every Nth request. If the app is idle, no re-validation happens (which is fine -- an idle app is not being exploited).

### Recommended N Value: 500

**Rationale:**
- At peak load (office uploads + 13 drivers checking routes), the system sees maybe 50-100 requests per hour
- N=500 means re-validation approximately every 5-10 hours of active use
- Low enough to catch mid-day license expiry
- High enough to have zero performance impact (one extra SHA256 + HMAC per 500 requests)

### Counter Implementation

```python
# Inside enforcement.so (compiled)
_request_counter: int = 0
_cached_license_status: LicenseStatus = LicenseStatus.INVALID

async def _enforcement_middleware(request: Request, call_next):
    global _request_counter, _cached_license_status

    # Always allow health checks
    if request.url.path == "/health":
        response = await call_next(request)
        if _cached_license_status != LicenseStatus.VALID:
            response.headers["X-License-Status"] = _cached_license_status.value
        return response

    # Periodic re-validation
    _request_counter += 1
    if _request_counter % _REVALIDATION_INTERVAL == 0:
        _cached_license_status = _do_full_validation()
        integrity_ok, failures = check_integrity()
        if not integrity_ok:
            _cached_license_status = LicenseStatus.INVALID
            logger.error("File integrity check failed: %s", failures)

    # Enforcement
    if _cached_license_status == LicenseStatus.INVALID:
        return JSONResponse(status_code=503, content={
            "detail": "License expired or invalid. Contact support.",
            "license_status": "invalid",
        })

    response = await call_next(request)

    if _cached_license_status == LicenseStatus.GRACE:
        response.headers["X-License-Warning"] = "License in grace period"

    return response
```

---

## License Renewal Architecture

### Protocol

1. Customer contacts developer saying "license expiring"
2. Developer runs: `python scripts/generate_license.py --renew --key <current_key> --months 12`
3. Script decodes existing key to extract customer_id and fingerprint
4. Script generates new key with same customer_id and fingerprint, new expiry
5. Developer sends new key to customer
6. Customer updates LICENSE_KEY env var or license.key file
7. On next periodic re-validation (every 500th request), new key is picked up automatically -- no restart needed

### Why No Restart Required

The periodic re-validation in enforcement.so re-reads the license key from the environment/file on every Nth request. If the key has been updated, the new expiry is picked up automatically. This is a significant UX improvement over requiring a Docker restart.

### generate_license.py --renew Implementation

```python
# Pseudocode for the --renew path
if args.renew:
    old_info = decode_license_key(args.key)
    if old_info is None:
        error("Cannot decode existing key")
        sys.exit(1)
    # Reuse customer_id and fingerprint from old key
    # We only have the fingerprint PREFIX (16 hex chars) in the key,
    # so we pad it to 64 chars for encode_license_key compatibility
    fingerprint_padded = old_info.fingerprint + "0" * 48
    new_key = encode_license_key(
        customer_id=old_info.customer_id,
        fingerprint=fingerprint_padded,
        expires_at=new_expiry,
    )
```

**Note:** Since the key only stores the first 8 bytes (16 hex chars) of the fingerprint, and `validate_license()` only compares those first 16 chars, padding the rest with zeros is safe -- the comparison still passes because only the prefix matters.

---

## Testing Architecture

### Unit Tests (tests/core/licensing/)

| Test Area | New Tests Needed |
|-----------|-----------------|
| Fingerprint | Test with /etc/machine-id present/absent, /proc/cpuinfo present/absent |
| Fingerprint | Test that container_id no longer affects fingerprint |
| Integrity | Test check_integrity() with correct manifest -> pass |
| Integrity | Test check_integrity() with modified file -> fail |
| Integrity | Test check_integrity() with missing file -> fail |
| Enforcement | Test enforce() registers middleware on FastAPI app |
| Enforcement | Test request counter increments and triggers re-validation at N |
| Renewal | Test --renew flag generates valid key with same fingerprint |

### E2E Tests (e2e/license.spec.ts)

| Test Scenario | How to Test |
|--------------|-------------|
| Existing: 503 with invalid license | Already covered |
| Existing: /health allowed with invalid license | Already covered |
| NEW: Integrity check failure | Modify main.py in container, restart, verify 503 |
| NEW: Periodic re-validation catches expiry | Start with valid license, mock time forward, send 500+ requests |
| NEW: Renewal picks up new key without restart | Start with expiring license, update license.key, verify re-validation |

### docker-compose.license-test.yml

Needs new test scenarios. The existing setup (single container on port 8001 with invalid key) should be extended with:
- A valid-license container for testing periodic re-validation
- A tampered-file container for testing integrity checking

---

## Suggested Build Order

Based on dependencies between components:

### Phase 1: Stronger Fingerprinting (no dependencies on other phases)

**Files:** `core/licensing/license_manager.py`, `scripts/get_machine_id.py`, `docker-compose.yml`, `docker-compose.license-test.yml`
**Tests:** `tests/core/licensing/test_license_manager.py` (new fingerprint tests)
**Rationale:** Self-contained change. The fingerprint function is used by both validation and key generation. Changing it first means all subsequent phases use the new fingerprint.

### Phase 2: Dev-Mode Stripping + Enforcement Module (depends on understanding Phase 1)

**Files:** `core/licensing/enforcement.py` (NEW), `core/licensing/integrity.py` (NEW), `core/licensing/__init__.py`, `apps/kerala_delivery/api/main.py`
**Tests:** `tests/core/licensing/test_enforcement.py` (NEW), `tests/core/licensing/test_integrity.py` (NEW)
**Rationale:** Creates the enforcement module that absorbs middleware from main.py. The dev-mode block in main.py is replaced by a single `enforce(app)` call. This is the largest architectural change and should be done before Cython compilation so the code can be tested as plain Python first.

### Phase 3: Cython Compilation (depends on Phase 2 being stable)

**Files:** `scripts/cython_build.py` (NEW), `scripts/build-dist.sh` (major rewrite), `scripts/verify-dist.sh`
**Tests:** Manual build + import validation, verify-dist.sh execution
**Rationale:** Replace compileall with Cython. This is a build-system change, not a runtime change. All logic should already work as plain Python from Phase 2. Cython compilation is purely a protection layer.

### Phase 4: File Integrity Checking (depends on Phase 3 for manifest injection)

**Files:** Manifest generation in `build-dist.sh`, manifest injection into `enforcement.py`
**Tests:** `tests/core/licensing/test_integrity.py` (manifest tests), `e2e/license.spec.ts` (integrity E2E)
**Rationale:** Integrity checking requires the build pipeline to generate and inject manifests. This must come after the Cython build pipeline is working.

### Phase 5: Periodic Re-validation (depends on Phase 2 enforcement module)

**Files:** Counter logic in `core/licensing/enforcement.py`
**Tests:** `tests/core/licensing/test_enforcement.py` (counter tests), `e2e/license.spec.ts` (re-validation E2E)
**Rationale:** Adds request counting to the enforcement middleware created in Phase 2.

### Phase 6: License Renewal (independent, can be done anytime after Phase 1)

**Files:** `scripts/generate_license.py`
**Tests:** Unit tests for --renew flag
**Rationale:** Developer-side tool change. Independent of all runtime changes.

### Build Order Rationale

- **Fingerprinting first** because it changes the identity function used everywhere
- **Enforcement module before Cython** because debugging plain Python is easier than debugging compiled .so
- **Cython before integrity** because integrity manifests need to be injected before compilation
- **Periodic re-validation late** because it builds on the enforcement module
- **Renewal is independent** and can slot in anywhere

---

## Sources

- [Cython Build Documentation](https://cython.readthedocs.io/en/latest/src/quickstart/build.html) -- setup.py patterns, build_ext --inplace
- [Cython Pure Python Mode](https://cython.readthedocs.io/en/latest/src/tutorial/pure.html) -- compiling .py files directly
- [Cython Source Files and Compilation](https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html) -- Extension objects, compiler directives
- [Cython Docker Multi-stage Build Gist](https://gist.github.com/operatorequals/a1264ad67b3b9a08651c9736bbfe26b0) -- Builder stage pattern for .so compilation
- [Protecting Python with Cython and Docker](https://shawinnes.com/protecting-python/) -- Practical guide to Cython code protection
- [WSL2 /etc/machine-id Persistence](https://github.com/nix-community/NixOS-WSL/issues/574) -- NixOS-WSL tmpfs issue (does not affect standard Ubuntu WSL)
- [Docker /etc/machine-id Feature Request](https://forums.docker.com/t/host-machine-id-visible-from-containers/100533) -- Bind-mounting host machine-id into containers
- [freedesktop.org machine-id spec](https://www.freedesktop.org/software/systemd/man/machine-id.html) -- Official machine-id documentation
- [Python hashlib File Hashing](https://docs.python.org/3/library/hashlib.html#hashlib.file_digest) -- SHA256 file integrity
- [FastAPI Advanced Middleware](https://fastapi.tiangolo.com/advanced/middleware/) -- Middleware registration patterns
- Existing codebase: `core/licensing/license_manager.py`, `apps/kerala_delivery/api/main.py`, `scripts/build-dist.sh`, `docker-compose.yml`, `infra/Dockerfile`

---
*Architecture research for: v2.1 Licensing & Distribution Security*
*Researched: 2026-03-10*
