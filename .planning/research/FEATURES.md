# Feature Landscape

**Domain:** Licensing & Distribution Security Hardening (v2.1)
**Researched:** 2026-03-10
**Confidence:** HIGH (features scoped by CONTEXT.md decisions, verified against existing codebase + Cython/system docs)

---

## Context: What Already Exists (v2.0 Complete)

This is a security-hardening milestone on a working licensing system. These licensing artifacts are ALREADY SHIPPED:

- **License key format**: `LPG-XXXX-XXXX-...` base32-encoded payload with HMAC-SHA256 signature (truncated to 8 bytes)
- **Machine fingerprinting**: hostname + MAC address + Docker container ID, combined with SHA256
- **License validation**: startup-only check in `main.py` lifespan function (lines 162-203)
- **Enforcement middleware**: FastAPI middleware blocks all endpoints with 503 when invalid (lines 381-427)
- **Grace period**: 7 days post-expiry with `X-License-Warning` header
- **HMAC key derivation**: PBKDF2 with 100k iterations from a seed constant
- **Dev mode bypass**: `ENVIRONMENT=development` overrides INVALID to VALID (lines 184-203 of main.py)
- **Distribution build**: `build-dist.sh` uses `compileall` to create .pyc files, removes .py source from `core/licensing/`
- **Key generation**: `scripts/generate_license.py` (not shipped) + `scripts/get_machine_id.py` (shipped)
- **Test coverage**: 15 unit tests in `test_license_manager.py`, 4 E2E tests in `license.spec.ts`
- **Docker setup**: API runs as non-root user (UID 1001) in python:3.12-slim container

**The gap for v2.1:** Six specific loopholes identified in CONTEXT.md. The current system is Tier 1 (license-key-at-startup). A moderately determined user can: (1) set `ENVIRONMENT=development` to bypass enforcement, (2) read enforcement logic in plain-text main.py, (3) spoof Docker fingerprint by recreating containers, (4) decompile .pyc files trivially with `uncompyle6`/`decompyle3`, (5) modify the license check to always return VALID since it only runs at startup, (6) edit shipped files without detection. The goal is Tier 2: compiled enforcement + integrity checks.

---

## Table Stakes

Features that close the identified loopholes. Missing any of these means the licensing system has a known, exploitable bypass.

| Feature | Why Expected | Complexity | Dependencies |
|---------|-------------|------------|--------------|
| **Dev-mode stripping from distributed builds** | CRITICAL loophole. Anyone who sets `ENVIRONMENT=development` in `.env` bypasses all license enforcement. The shipped code must have NO concept of dev mode -- the `if env == "production"` / `else` block in main.py (lines 184-203) and the `_env_name` docs-toggle logic (lines 239-242) must be physically absent from the tarball. | Low | `build-dist.sh` modification. Sed/AST removal of the dev-mode code block before packaging. |
| **Cython compilation of licensing module to .so** | CRITICAL loophole. Current .pyc files are trivially decompilable with `uncompyle6` or `decompyle3`, exposing the HMAC seed, PBKDF2 parameters, and full validation logic. Cython compiles Python to C, then to a native `.so` shared library. Reverse engineering requires disassembling machine code -- orders of magnitude harder than reading bytecode. | Med | Cython as build-time dependency. `setup.py` or inline `cythonize` call. C compiler in Docker build stage (gcc already present in builder stage). Python 3.12 + Linux x86_64 target. |
| **Enforcement logic moved into compiled module** | CRITICAL loophole. Currently, main.py contains the enforcement middleware in plain text (lines 381-427). Anyone can edit main.py to comment out the middleware or make it always pass. Moving enforcement INTO the compiled .so means editing main.py to skip the call is detectable by integrity checking. | Med | Cython compilation (above). Refactor: `core/licensing/` exports an `enforce(app)` function that registers middleware. main.py calls `licensing.enforce(app)` -- a one-liner. |
| **Stronger machine fingerprinting** | MEDIUM loophole. Current fingerprint uses container_id which changes on every `docker compose down/up` cycle, forcing license re-generation. Replacing with `/etc/machine-id` (stable 128-bit UUID, persistent across reboots) + `/proc/cpuinfo` stable fields (vendor_id, model name, cpu family) + MAC address gives a fingerprint that survives container recreation but changes when software is copied to a different physical machine. | Med | Volume mount `/etc/machine-id:/etc/machine-id:ro` in docker-compose.yml. Read `/proc/cpuinfo` model name inside container. Update `get_machine_fingerprint()` and `get_machine_id.py`. Update `generate_license.py` to accept new fingerprint format. Existing license keys become invalid (migration consideration). |
| **File integrity verification (SHA256 manifest)** | LOW-MEDIUM loophole. Nothing prevents editing main.py, docker-compose.yml, or any shipped file after delivery. An embedded SHA256 manifest inside the compiled .so checks critical files at startup and periodically. If any protected file is modified, the license validation fails. Build-time: `build-dist.sh` hashes critical files and injects the manifest as a Python dict/constant into the Cython source before compilation. | Med-High | Cython compilation (above). Build pipeline generates manifest. Protected files: main.py, docker-compose.yml, any middleware files. Manifest embedded as constant in `.so` -- cannot be edited without recompiling. |
| **Periodic license re-validation (Nth-request)** | LOW-MEDIUM loophole. Current validation runs once at startup. If a license expires mid-session (unlikely but possible) or if files are modified after startup, the system keeps running until next restart. Re-validating on every Nth request catches mid-runtime issues. The request counter and re-validation logic live inside the compiled .so module. | Med | Cython compilation (above). Enforcement middleware counts requests internally. Suggested N: every 100-500 requests (configurable as compiled constant). Re-runs `validate_license()` + integrity check. Updates `app.state.license_info` if status changes. |
| **License renewal mechanism** | Missing workflow. Currently, renewing requires generating an entirely new license key, which means the customer must re-run `get_machine_id.py`, send the fingerprint, wait for a new key, and update their `.env`. A renewal flow should allow extending an existing license with a simpler exchange -- e.g., a renewal code that extends the expiry date when applied. | Med | New `scripts/renew_license.py` (on our side). New API endpoint or CLI command on customer side to apply renewal. Renewal code format that encodes new expiry + is HMAC-signed. Backward-compatible with existing license key format. |

---

## Differentiators

Features that go beyond closing the six loopholes. Not required for Tier 2 security, but add professional polish or reduce future support burden.

| Feature | Value Proposition | Complexity | Dependencies |
|---------|-------------------|------------|--------------|
| **Fingerprint similarity scoring (fuzzy match)** | Instead of exact fingerprint match, allow a threshold-based match. If 2 of 3 signals match (e.g., machine-id + CPU match but MAC changed due to network adapter swap), accept with a warning instead of hard-failing. Reduces false negatives from minor hardware changes. | Low-Med | Modified `validate_license()` in compiled module. Separate fingerprint components instead of single hash. Threshold constant (e.g., 2/3 signals must match). |
| **Expiry warning in API response headers** | Currently, grace period adds `X-License-Warning`. Extend this to add `X-License-Expires-In: 14d` header when license is valid but approaching expiry (e.g., within 30 days). Gives the dashboard a chance to show a renewal reminder banner. | Low | Middleware change in compiled module. New header `X-License-Expires-In`. Dashboard could read this header (future feature). |
| **License status in /health endpoint body** | Add license expiry date and days remaining to the /health JSON response. Currently /health only gets an `X-License-Status` header when invalid. Adding it to the body lets monitoring tools (curl + jq in cron) alert on approaching expiry. | Low | Modify /health handler. Already partially exists (header-based). |
| **Compilation with optimization flags** | Strip debug symbols and optimize the .so with `-O2` and `-s` (strip). Makes the binary smaller and marginally harder to reverse engineer. Also set Cython `embedsignature=False` to avoid leaking Python function signatures into the binary. | Low | `extra_compile_args=['-O2', '-s']` in setup.py Extension. `compiler_directives={'embedsignature': False}`. |
| **Build-time validation of .so import** | After Cython compilation, automatically verify the .so loads and the `enforce()` function is callable. Catches compilation errors before packaging. Extends the existing .pyc import validation pattern in build-dist.sh. | Low | Already has .pyc validation pattern. Update to test .so loading + function presence. |
| **Renewal notification logging** | Log a WARNING-level message on every startup when license expires within 30 days. Log an ERROR-level message when in grace period. These messages appear in `docker compose logs api` which is the primary diagnostic tool for the customer. | Low | Extend existing startup logging in lifespan function. Already partially exists for GRACE status. |

---

## Anti-Features

Features to explicitly NOT build. Each was considered and rejected for the stated reason.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Call-home license verification** | Deployment is on a WSL laptop in a Kerala office. Internet connectivity is unreliable (monsoon outages). A call-home requirement would lock out the customer when they need the system most. Also adds server infrastructure we must maintain. | Offline-only validation. All checks happen locally with cryptographic verification. |
| **PyArmor or commercial obfuscation** | Adds a runtime dependency the customer must install. License terms of PyArmor are complex. Cython compilation achieves the same goal (compiled binary) without any runtime overhead or licensing entanglement. | Cython compilation to native .so. |
| **Encrypted Python source with runtime decryption** | The decryption key must exist somewhere accessible to the Python runtime, so it is just obfuscation with extra steps. Cython eliminates the source entirely -- there is no Python source to decrypt. | Cython compilation to native .so. |
| **Hardware dongle (USB key)** | Overkill for a single-customer delivery logistics app. Adds hardware cost, shipping logistics, and failure mode (dongle breaks/lost). | Software fingerprinting with /etc/machine-id + CPU + MAC. |
| **Background timer thread for re-validation** | Adds threading complexity to an async FastAPI app. A background thread checking license validity could race with request handling. Request-count-based re-validation is simpler, deterministic, and naturally tied to system usage. | Re-validate on every Nth request in the middleware. |
| **Obfuscation of variable/function names** | Cython compilation already produces machine code. Obfuscating Python-level names before compilation adds build complexity for negligible security gain -- the names are compiled away regardless. | Compile with `embedsignature=False` to strip signatures from .so. |
| **Network-based fingerprinting (IP address, DNS)** | IP addresses change. DNS resolution depends on network config. Neither is stable enough for hardware binding. Would cause false license failures when the network changes. | Hardware-based signals: /etc/machine-id, CPU info, MAC address. |
| **Self-modifying code or anti-debugging** | Anti-debugging tricks (ptrace detection, timing checks) are fragile, OS-dependent, and create false positives in legitimate debugging scenarios. "Reasonable deterrent" threat model does not warrant this complexity. | Compiled .so + integrity checks are sufficient for the threat model. |
| **License server (centralized)** | Same connectivity concerns as call-home. Additionally requires us to run infrastructure. The customer base is small (single customer currently). A license server makes sense at 50+ customers, not 1. | Offline license keys with renewal codes. |

---

## Feature Dependencies

```
Dev-mode stripping ──────────────────────────────────────→ (independent, earliest)
                                                           |
Cython compilation of licensing module ──────────────────→ (prerequisite for 3 features below)
    |                                                      |
    ├── Enforcement logic in compiled module ─────────────→ (requires .so to exist)
    |                                                      |
    ├── File integrity manifest embedded in .so ─────────→ (requires Cython build pipeline)
    |       |                                              |
    |       └── Periodic re-validation (uses integrity) ─→ (requires integrity + enforcement in .so)
    |                                                      |
    └── Compilation optimization flags ──────────────────→ (applied during Cython build)

Stronger fingerprinting ─────────────────────────────────→ (independent of Cython, but changes
    |                                                       license key format → migration needed)
    └── Fingerprint similarity scoring ──────────────────→ (optional, extends fingerprinting)

License renewal mechanism ───────────────────────────────→ (independent, can be done anytime
                                                            after fingerprinting is stable)
```

**Critical path:** Dev-mode stripping (no deps) -> Cython build pipeline -> enforcement in .so -> integrity manifest -> periodic re-validation. This is the longest dependency chain and should drive phase ordering.

**Parallel track:** Stronger fingerprinting and license renewal are independent of the Cython pipeline and can be developed in parallel or in separate phases.

---

## Feature Details: Expected Behavior

### 1. Dev-Mode Stripping

**What it does:** The `build-dist.sh` script physically removes dev-mode code from main.py before packaging. The shipped main.py has no `if env == "production"` conditional -- license is always enforced.

**Expected behavior:**
- In the tarball, main.py lines 184-203 (the `else` block that overrides INVALID to VALID in dev mode) do not exist
- In the tarball, `ENVIRONMENT` variable is not checked for license decisions
- Setting `ENVIRONMENT=development` in the customer's `.env` has zero effect on license enforcement
- The dev-mode code continues to exist in the source repository for developer convenience
- `build-dist.sh` uses sed or a marker-based approach (e.g., `# BEGIN_DEV_ONLY` / `# END_DEV_ONLY` markers) to cleanly excise the block
- Also strip the Swagger/OpenAPI docs toggle (lines 239-242) since production should never have /docs

**Complexity:** Low. Sed-based text removal with marker comments. No compilation, no new dependencies. The existing `build-dist.sh` already has the rsync + staging pattern -- this adds one more transformation step.

### 2. Cython Compilation

**What it does:** Replaces `compileall` (Python bytecode) with Cython (native machine code) for the `core/licensing/` module. Produces `license_manager.cpython-312-x86_64-linux-gnu.so` instead of `license_manager.pyc`.

**Expected behavior:**
- `build-dist.sh` invokes Cython to compile `core/licensing/*.py` to `.so` files
- The `.so` files are platform-specific (Linux x86_64, Python 3.12) -- matches the Docker image target
- Cython is a BUILD-TIME dependency only -- not shipped, not installed in customer Docker image
- The Docker builder stage already has gcc; may need python3-dev headers added
- `__init__.py` for the package also needs compilation or a minimal stub
- Import validation in `build-dist.sh` tests `.so` loading (not `.pyc`)
- The `.so` is compiled inside Docker (matching the target platform) or cross-compiled

**Build pipeline:**
```
core/licensing/license_manager.py
    |
    v  (Cython: .py -> .c)
license_manager.c
    |
    v  (gcc: .c -> .so)
license_manager.cpython-312-x86_64-linux-gnu.so
    |
    v  (copy to staging, remove .py source)
Tarball ships with .so only
```

**Key technical detail:** Cython can compile pure `.py` files directly (no `.pyx` needed). The existing license_manager.py uses only stdlib (hashlib, hmac, struct, etc.), which Cython handles without modification. No Cython-specific annotations needed.

### 3. Enforcement Logic in Compiled Module

**What it does:** Moves the FastAPI middleware (currently main.py lines 381-427) into `core/licensing/`. The compiled .so exports an `enforce(app)` function that main.py calls.

**Expected behavior:**
- `core/licensing/` exports: `enforce(app: FastAPI) -> None`
- `enforce()` registers the middleware on the FastAPI app
- `enforce()` stores license state internally (not in `app.state` which is editable)
- main.py becomes a single call: `from core.licensing.license_manager import enforce; enforce(app)`
- If someone comments out the `enforce(app)` call in main.py, the integrity check (feature 5) detects the modification to main.py
- The middleware logic, status enum, grace period constants -- all live inside the .so
- `/health` endpoint exclusion logic also lives in the .so

### 4. Stronger Fingerprinting

**What it does:** Replaces the current fingerprint signals (hostname + MAC + container_id) with more stable, harder-to-spoof signals.

**New signals:**
| Signal | Source | Stability | Spoof Difficulty |
|--------|--------|-----------|-----------------|
| /etc/machine-id | Bind-mount read-only into container | Persistent across reboots, unique per OS install | Requires root on host to modify |
| CPU model string | `/proc/cpuinfo` model name field | Hardware-intrinsic, never changes | Requires CPU swap (physical hardware change) |
| MAC address | `uuid.getnode()` | Stable for physical NICs | Spoofable but requires deliberate action |

**Dropped signals:**
| Signal | Why Dropped |
|--------|-------------|
| Docker container_id | Changes on every `docker compose down/up`. Forces license regeneration on routine operations. |
| hostname | User-changeable with a single command. Weak signal. |

**Expected behavior:**
- docker-compose.yml adds: `volumes: ["/etc/machine-id:/etc/machine-id:ro"]` to the api service
- `get_machine_fingerprint()` reads `/etc/machine-id`, `/proc/cpuinfo` model name, and MAC address
- Fingerprint format: SHA256 of `machine_id|cpu_model|mac_address`
- `get_machine_id.py` updated to show new signal sources and produce new-format fingerprint
- `generate_license.py` updated to accept new fingerprint format
- **BREAKING CHANGE**: Existing license keys are invalid after this change. Must regenerate for the customer.
- WSL-specific: `/etc/machine-id` in WSL2 is the WSL instance's machine-id, which is stable across WSL restarts but would change if the WSL distro is reset/reinstalled. This is acceptable -- a distro reset is equivalent to a new machine.

### 5. File Integrity Verification

**What it does:** At build time, SHA256 hashes of critical files are computed and embedded as constants in the Cython source. At runtime, the compiled module re-hashes those files and compares. Any modification = license invalid.

**Protected files:**
| File | Why Protected |
|------|--------------|
| main.py | Contains the `enforce(app)` call. Removing it disables enforcement. |
| docker-compose.yml | Contains volume mounts (machine-id) and environment config. |

**Expected behavior:**
- `build-dist.sh` computes SHA256 of protected files AFTER dev-mode stripping
- Hashes injected into Cython source as a Python dict constant: `_INTEGRITY_MANIFEST = {"main.py": "abc123...", ...}`
- After Cython compilation, the manifest is embedded in machine code -- cannot be edited without recompiling
- On startup: compiled module hashes each protected file, compares against manifest
- On every Nth request: same integrity check runs again
- If mismatch: `LicenseStatus.INVALID` with message "File integrity check failed. Contact support."
- File paths are relative to the application root (`/app/` in Docker)
- Graceful handling if a file is missing: treat as integrity failure (prevents deletion attack)

### 6. Periodic Re-Validation

**What it does:** The enforcement middleware counts requests and re-runs full validation (license key + fingerprint + integrity check) on every Nth request.

**Expected behavior:**
- Request counter is a module-level variable inside the compiled .so (not `app.state`)
- Suggested N: 250 requests (roughly every few minutes under normal usage)
- On Nth request: run `validate_license()` + integrity check
- If validation status changes (e.g., VALID -> GRACE or VALID -> INVALID), update enforcement behavior
- Counter is not reset on validation -- it keeps incrementing
- Validation runs synchronously in the request path (it is fast -- file hashing + HMAC check, no I/O beyond file reads)
- Performance impact: negligible. SHA256 of 2-3 small files + HMAC verify takes < 1ms

### 7. License Renewal

**What it does:** Provides a mechanism to extend a license without regenerating the full key.

**Recommended approach: Renewal Code**

A renewal code is a shorter, HMAC-signed token that encodes:
- Customer ID (must match existing license)
- New expiry date
- HMAC signature

**Expected behavior:**
- We run `scripts/renew_license.py --customer vatakara-lpg-01 --extend 365` on our machine
- Produces a renewal code: `RNW-XXXX-XXXX-XXXX`
- Customer places the renewal code in `renewal.key` file or `RENEWAL_CODE` env var
- On startup, if renewal code is present and valid:
  1. Verify HMAC signature
  2. Verify customer ID matches current license
  3. Update expiry date to the new date
  4. Write updated license key to `license.key` (atomic write)
  5. Delete the `renewal.key` file
  6. Log: "License renewed -- new expiry: YYYY-MM-DD"
- The renewed license key has the same fingerprint binding (no need for `get_machine_id.py` again)
- Renewal codes are one-time-use (consumed on application)
- If renewal code is invalid: log warning, continue with existing license

---

## MVP Recommendation

Prioritize in this order (driven by dependency chain and severity):

1. **Dev-mode stripping** -- CRITICAL, no dependencies, lowest complexity. Closes the easiest bypass.
2. **Cython build pipeline** -- CRITICAL, prerequisite for 3 other features. Get the compilation working first.
3. **Enforcement in compiled module** -- CRITICAL, requires Cython. Moves the attack surface into compiled code.
4. **Stronger fingerprinting** -- MEDIUM severity, independent track. Can be parallel with Cython work.
5. **File integrity manifest** -- Requires Cython pipeline + enforcement refactor complete.
6. **Periodic re-validation** -- Requires integrity manifest. Last in the chain.
7. **License renewal** -- Independent, lowest urgency. Nice-to-have for customer experience but not a security fix.

**Defer:** Fingerprint similarity scoring (differentiator, not a loophole fix), expiry warning headers (polish), /health license body enhancement (polish).

---

## Sources

- [Cython Official Docs: Source Files and Compilation](https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html) -- HIGH confidence, authoritative
- [Cython Pure Python Mode](https://cython.readthedocs.io/en/latest/src/tutorial/pure.html) -- HIGH confidence, confirms .py direct compilation
- [Cython Basic Tutorial](https://cython.readthedocs.io/en/latest/src/tutorial/cython_tutorial.html) -- HIGH confidence
- [machine-id(5) manpage](https://manpages.ubuntu.com/manpages/bionic//man5/machine-id.5.html) -- HIGH confidence, system documentation
- [freedesktop machine-id spec](https://www.freedesktop.org/software/systemd/man/machine-id.html) -- HIGH confidence
- [NixOS-WSL /etc/machine-id persistence issue](https://github.com/nix-community/NixOS-WSL/issues/574) -- MEDIUM confidence, WSL-specific edge case
- [Cisco: Securing Python Code with Cython](https://blogs.cisco.com/developer/securingpythoncodewithcython01) -- MEDIUM confidence
- [Protecting Python Sources with Cython](https://medium.com/@xpl/protecting-python-sources-using-cython-dcd940bb188e) -- MEDIUM confidence
- [Cython Reverse Engineering difficulty](https://groups.google.com/g/cython-users/c/Zd7HZ9UW_ew) -- MEDIUM confidence, community discussion
- [setuptools: Building Extension Modules](https://setuptools.pypa.io/en/latest/userguide/ext_modules.html) -- HIGH confidence
- [Keygen: Timed Licensing Model](https://keygen.sh/docs/choosing-a-licensing-model/timed-licenses/) -- MEDIUM confidence, renewal patterns
- [NetLicensing: Machine Fingerprint FAQ](https://netlicensing.io/wiki/faq-how-to-generate-machine-fingerprint/) -- MEDIUM confidence, fingerprinting patterns
- [LicenseSpring: Python Hardware IDs](https://docs.licensespring.com/sdks/python/hardware-id) -- MEDIUM confidence
- Existing codebase analysis: `core/licensing/license_manager.py`, `scripts/build-dist.sh`, `main.py`, `docker-compose.yml`, `infra/Dockerfile` -- HIGH confidence, primary source
