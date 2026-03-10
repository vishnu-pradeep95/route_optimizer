# Stack Research

**Domain:** Licensing & distribution security hardening for Python/FastAPI application
**Researched:** 2026-03-10
**Confidence:** HIGH
**Scope:** v2.1 milestone only -- "Licensing & Distribution Security". Existing Python 3.12 / FastAPI / Docker Compose stack is locked. This document covers ONLY what is new: Cython compilation, SHA256 file integrity, stronger machine fingerprinting, periodic re-validation, dev-mode stripping, and license renewal.

---

## Context: What Is Already in Place (Locked -- Do Not Change)

| Component | Status |
|-----------|--------|
| Python 3.12 / FastAPI 0.129.1 | Runtime, locked in `requirements.txt` and `python:3.12-slim` Docker image |
| `core/licensing/license_manager.py` | Full license validation pipeline (fingerprint, encode, decode, validate). Will be refactored and Cython-compiled to `.so`. |
| `core/licensing/__init__.py` | Module docstring only. Will be compiled alongside `license_manager.py`. |
| `scripts/build-dist.sh` | Distribution builder. Currently uses `compileall` for `.pyc`. Will be rewritten for Cython `.so` output. |
| `scripts/generate_license.py` | License key generator. Stays on developer machine. Needs update for new fingerprint formula. |
| `scripts/get_machine_id.py` | Customer fingerprint reporter. Needs update for new fingerprint signals. |
| `apps/kerala_delivery/api/main.py` | Lifespan (lines 162-203) validates license at startup. Middleware (lines 381-427) enforces on every request. Dev-mode bypass at lines 184-203 must be stripped in distribution. |
| `docker-compose.yml` | API service has no `/etc/machine-id` mount yet. Needs adding. |
| `docker-compose.license-test.yml` | Isolated production-mode container on port 8001. Needs same mount + new test scenarios. |
| `hashlib`, `hmac`, `struct`, `uuid`, `platform` | All already imported in `license_manager.py`. No new stdlib imports needed. |
| 38 E2E tests (Playwright), 426 unit tests (pytest) | Existing test infrastructure. Extend, do not replace. |

---

## Recommended Stack

### Core: Cython Compilation (Loopholes #2, #4)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Cython | 3.2.4 | Compile `core/licensing/*.py` to native `.so` shared libraries | Latest stable (Jan 2026). Compiles pure Python `.py` files directly -- no `.pyx` rewrite needed. Existing `dataclass`, `Enum`, `hashlib`, `hmac` usage all works in Cython's pure Python mode. Produces native x86_64 machine code that requires disassembly to reverse (vs `.pyc` which decompiles to near-original source with `uncompyle6`). Build-time dependency only -- never shipped to customer. |

**Compilation approach:** Use `cythonize -i core/licensing/*.py` directly in `build-dist.sh`. This is simpler than maintaining a `setup.py` and sufficient for compiling 2 files in one package. Produces files like `license_manager.cpython-312-x86_64-linux-gnu.so` that Python imports automatically.

**Build-time dependencies:**

| Dependency | Type | Purpose | Notes |
|------------|------|---------|-------|
| `Cython==3.2.4` | pip (build machine only) | Python-to-C transpiler | `pip install Cython==3.2.4` on developer machine. NOT in `requirements.txt` (not shipped). |
| `gcc` / `build-essential` | apt (build machine only) | C compiler for `.c` to `.so` | Already installed on developer WSL2 system. Already in Dockerfile builder stage. |
| `python3-dev` | apt (build machine only) | Python headers (`Python.h`) | Provides `Python.h` needed to compile Cython's C output into `.so`. Install on developer machine: `sudo apt-get install python3-dev`. |

**Customer impact:** Zero. The `.so` is self-contained and runs on `python:3.12-slim` without Cython or gcc installed.

### Core: File Integrity Manifest (Loophole #6)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `hashlib.file_digest()` | Python 3.11+ stdlib | SHA256 hashing of protected files | Added in Python 3.11, available in our Python 3.12 runtime. Cleaner than manual chunk-based reading. Crypto-grade collision resistance. Zero dependencies. |

**Protected files:** `main.py`, `docker-compose.yml`, and any other files where tampering would bypass enforcement.

**Pattern:**
1. At build time (`build-dist.sh`): hash protected files after dev-mode stripping, generate a Python dict literal manifest
2. Inject manifest as a constant into `core/licensing/` source code BEFORE Cython compilation
3. At runtime: re-hash files and compare against embedded manifest
4. On mismatch: license validation fails with integrity error

**No new dependencies.** `hashlib` is already imported in `license_manager.py`.

### Core: Stronger Machine Fingerprinting (Loophole #3)

All signals use Python stdlib. No new libraries.

| Signal | Source | Stability | Notes |
|--------|--------|-----------|-------|
| `/etc/machine-id` | `open("/etc/machine-id").read().strip()` | HIGH -- survives reboots, stable across container recreates | 32-char hex. Verified present and populated on target WSL2 system (`9ea32533cbc847218443c7139d7ce34b`). Bind-mounted read-only into Docker container. |
| `/proc/cpuinfo` model name | `open("/proc/cpuinfo")` + filter `model name` | HIGH -- tied to physical hardware | Verified accessible in WSL2 (`AMD Ryzen 9 9955HX3D 16-Core Processor`). Docker containers see host CPU through `/proc`. Cannot change without swapping CPU. |
| MAC address | `uuid.getnode()` | MEDIUM -- stable across reboots, spoofable | Already used. Keep as existing signal. |
| hostname | `platform.node()` | LOW -- easily user-changeable | Already used. Keep but consider lowest weight. Dropping it would break backward compatibility unnecessarily. |

**Drop:** `_get_docker_container_id()`. Container ID changes on every `docker compose down && docker compose up`, making the fingerprint unstable. This was identified as Loophole #3.

**Docker Compose change:** Add `/etc/machine-id` as read-only bind mount to `api` service:

```yaml
# In docker-compose.yml, under api.volumes:
volumes:
  - ./data:/app/data
  - dashboard_assets:/srv/dashboard:ro
  - /etc/machine-id:/etc/machine-id:ro  # NEW: stable machine fingerprint
```

Same mount needed in `docker-compose.license-test.yml` for `api-license-test` service.

### Core: Periodic Re-Validation (Loophole #5)

No new dependencies. Implementation uses module-level counter inside compiled `.so`.

| Component | Approach | Why |
|-----------|----------|-----|
| Request counter | Module-level integer in `license_manager.py` (compiled to `.so`) | Lives inside native code, harder to patch than `app.state`. Cannot be easily zeroed by editing Python source. |
| Re-validation trigger | Every N=100 requests, re-run `validate_license()` | Balance between security (catch expired/tampered mid-runtime) and performance (validation is fast but not free). 100 requests is ~10-15 minutes of typical usage. |
| Integrity re-check | Same N=100 interval, re-hash protected files | Catches file modifications made while the server is running. |
| State update | Update `app.state.license_info` in middleware if status changes | Existing middleware pattern reads `app.state.license_info`. Re-validation updates it. |

### Core: Dev-Mode Stripping (Loophole #1)

No new dependencies. Build-time `sed` or Python string manipulation in `build-dist.sh`.

| Approach | Tool | Notes |
|----------|------|-------|
| Remove dev-mode `if/else` block from `main.py` | `sed` in `build-dist.sh` | Strips lines 184-203 (the `else` branch that overrides INVALID to VALID in dev mode). Shipped `main.py` always enforces licensing. |
| Move enforcement into compiled module | Refactor in Python | `main.py` calls `licensing.enforce(app)` which registers middleware. All enforcement logic lives in compiled `.so`. Even if customer edits `main.py` to skip the call, integrity check catches it. |

### Core: License Renewal

No new dependencies. Enhancement to `scripts/generate_license.py` (developer-side tool).

| Change | Implementation | Notes |
|--------|----------------|-------|
| `--renew` flag | New argument in `generate_license.py` | Takes existing customer_id + fingerprint (or reads from existing key), generates new key with extended expiry. |
| Customer workflow | Replace `license.key` file, restart API | Same as initial activation. No protocol changes. Offline operation preserved. |
| Renewal validation | Decode old key to extract customer_id + fingerprint, encode new key with new expiry | Reuses existing `encode_license_key()` and `decode_license_key()`. |

---

## Installation

### Developer machine (build-time)

```bash
# Cython -- build-time only, NOT added to requirements.txt
pip install Cython==3.2.4

# System packages (if not already present)
sudo apt-get install -y build-essential python3-dev
```

### Docker changes

```yaml
# docker-compose.yml -- add to api service volumes
- /etc/machine-id:/etc/machine-id:ro

# docker-compose.license-test.yml -- add to api-license-test service volumes
- /etc/machine-id:/etc/machine-id:ro
```

### Customer machine

**No changes.** No new pip packages, no new apt packages. The `.so` file runs on existing `python:3.12-slim` Docker image.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not Alternative |
|----------|-------------|-------------|---------------------|
| Code protection | Cython 3.2.4 (`.so`) | PyArmor obfuscation | Runtime dependency, license cost ($300+/yr), known generic bypass tools, security-through-obfuscation. Cython produces real machine code. |
| Code protection | Cython 3.2.4 (`.so`) | Nuitka full-app compile | Compiles entire app to standalone binary -- breaks Docker workflow, massive build complexity, 10+ minute builds. We only need 2 files compiled. |
| Code protection | Cython 3.2.4 (`.so`) | `compileall` (`.pyc`) | Current approach. Trivially decompilable. `uncompyle6 license_manager.pyc` recovers near-original source in seconds. Not a real barrier. |
| Build method | `cythonize -i` CLI | `setup.py build_ext` | `setup.py` adds a file to maintain for no benefit. We compile 2 files in one package. `cythonize -i` is a one-liner. |
| File hashing | `hashlib.file_digest()` (stdlib) | `xxhash` (fast non-crypto hash) | Integrity checking needs collision resistance. SHA256 is crypto-grade. Speed irrelevant -- we hash 3 files. |
| CPU info | `open("/proc/cpuinfo")` (5 lines) | `py-cpuinfo` library | External dependency for trivial file parsing. We need one field (`model name`). |
| Machine ID | `/etc/machine-id` (file read) | `dbus-uuidgen` / `dmidecode` | Additional tools that may not be installed. `/etc/machine-id` is universally present on systemd Linux and verified on target WSL2. |
| Re-validation | Request-counting (every Nth) | Background timer (`asyncio.create_task`) | Timer can be killed, paused by debugger, or blocked by event loop. Request counting is deterministic and lives in compiled code. |
| License server | Offline HMAC validation | Call-home license server | Kerala has patchy internet. Offline validation is a hard requirement from PROJECT.md constraints. |
| Signing library | `hmac` + `hashlib` (stdlib) | `cryptography` / `PyNaCl` | Already using stdlib HMAC-SHA256 with PBKDF2 key derivation. `cryptography` adds OpenSSL dependency for zero practical gain at our threat level. |

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| PyArmor / PyInstaller / py2exe | Obfuscation theater. Known bypass tools exist for all of them. Adds runtime overhead and dependencies to shipped code. | Cython `.so` (real machine code, no runtime dependency) |
| `py-cpuinfo` library | External dependency for 5 lines of file reading. We only need the `model name` field from `/proc/cpuinfo`. | `open("/proc/cpuinfo")` with line filtering |
| `cryptography` / `PyNaCl` | Heavy dependencies (OpenSSL binding) for signing. Already have HMAC-SHA256 via stdlib which is sufficient for offline license validation at our threat level. | `hmac` + `hashlib` (stdlib, already used) |
| Docker container ID in fingerprint | Ephemeral -- changes on every `docker compose down && up`. Causes fingerprint instability, making licenses appear invalid after routine restarts. This IS the bug we are fixing. | `/etc/machine-id` (stable, survives container lifecycle) |
| Background validation timer | Async task that can be killed, paused, or starved. Harder to reason about than synchronous check. Requires graceful shutdown handling. | Request-counting re-validation in middleware (deterministic, compiled) |
| Any call-home / phone-home mechanism | Hard requirement: offline operation (Kerala internet constraints). Adds server infrastructure. | Offline HMAC validation with embedded integrity manifest |
| `Cython` in `requirements.txt` | Cython is a build-time tool. Including it in requirements.txt would install it on the customer's machine, wasting space and leaking build tooling. | Install separately on developer machine only |
| Separate `requirements-build.txt` | Over-engineering for one build dependency. `pip install Cython==3.2.4` in `build-dist.sh` is clear and self-documenting. | Inline `pip install` in build script |

---

## Build Pipeline Changes (build-dist.sh)

The build script needs these ordered steps. Order is critical because manifest generation must happen AFTER code stripping but BEFORE Cython compilation.

```
1. Copy project tree to staging (existing)
2. NEW: Strip dev-mode bypass block from staged main.py
3. NEW: Generate SHA256 manifest of protected files (main.py, docker-compose.yml)
4. NEW: Inject manifest into licensing source code as constant
5. CHANGED: Compile core/licensing/*.py with Cython (replaces compileall)
6. Remove .py source from licensing module (existing pattern)
7. NEW: Validate .so imports (replaces .pyc import validation)
8. Create tarball (existing)
```

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| Cython 3.2.4 | Python 3.8-3.14 | Full Python 3.12 support confirmed. Must compile on same Python minor version as runtime. |
| Cython `.so` output | `python:3.12-slim` Docker image | Filename includes Python version and platform: `license_manager.cpython-312-x86_64-linux-gnu.so`. Must match exactly. |
| Cython `.so` output | Developer WSL2 (x86_64) to Docker `python:3.12-slim` (x86_64) | Same architecture (x86_64), same Python (3.12). Compatible. If developer machine ever changes to ARM, must cross-compile or compile inside Docker. |
| `/etc/machine-id` | WSL2 Ubuntu, bare metal Linux, Debian, Fedora | Universally present on systemd-based Linux. May be empty on WSL1 (not our target). Verified populated on target system. |
| `/proc/cpuinfo` | All Linux environments including WSL2, Docker | Docker containers see host `/proc/cpuinfo`. No special mounting needed -- it is always accessible. |
| `hashlib.file_digest()` | Python 3.11+ | Added in Python 3.11. Our runtime is Python 3.12. Safe to use. |
| New fingerprint formula | Existing license keys | BREAKING CHANGE. New formula (machine_id + cpu_model + mac + hostname replacing container_id) produces different fingerprints. All existing customer licenses must be regenerated. |

---

## Critical Integration Notes

### BREAKING CHANGE: Fingerprint Migration

Changing the fingerprint formula invalidates all existing licenses. Both `get_machine_id.py` (customer side) and `generate_license.py` (developer side) must be updated simultaneously. All customer licenses must be regenerated with the new fingerprint. Plan a coordinated rollout.

### Build Order Dependency

The SHA256 manifest must be generated AFTER dev-mode stripping (so the hash reflects the shipped `main.py`, not the source `main.py`) but BEFORE Cython compilation (so the manifest is embedded in the `.so`). Getting this order wrong means either: (a) integrity check passes on tampered files (manifest reflects wrong version), or (b) manifest is not in the compiled module.

### Platform Lock

The `.so` is compiled for `cpython-312-x86_64-linux-gnu`. If the developer machine or Docker base image changes Python version (3.13) or architecture (ARM), the `.so` must be recompiled. Consider adding a platform assertion in `build-dist.sh`:
```bash
python3 -c "import sys; assert sys.version_info[:2] == (3, 12), f'Need Python 3.12, got {sys.version}'"
```

### Cython and `__init__.py`

Cython compiles `__init__.py` to `__init__.cpython-312-x86_64-linux-gnu.so`. Python's import system finds this automatically when the `.py` is removed. The existing import validation command (`python3 -c "import core.licensing"`) works unchanged -- it just loads the `.so` instead of `.pyc`.

### Request Counter Persistence

The Nth-request counter is a module-level variable in the compiled `.so`. It resets to zero on every server restart. This is acceptable -- the primary threat is license expiry or file tampering during long-running sessions, not across restarts (startup validation catches those).

---

## Sources

- [Cython 3.2.4 on PyPI](https://pypi.org/project/Cython/) -- Latest stable version confirmed (HIGH confidence)
- [Cython Building Docs](https://cython.readthedocs.io/en/latest/src/quickstart/build.html) -- `cythonize -i` workflow for `.py` files (HIGH confidence)
- [Cython Source Files and Compilation](https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html) -- Pure Python compilation, glob patterns, parallel builds (HIGH confidence)
- [Cython Pure Python Mode](https://cython.readthedocs.io/en/latest/src/tutorial/pure.html) -- Standard Python features (dataclass, enum, hashlib) work without `.pyx` (HIGH confidence)
- [machine-id(5) man page](https://man7.org/linux/man-pages/man5/machine-id.5.html) -- 32-char hex, stable identifier (HIGH confidence)
- [WSL /etc/machine-id issue #6347](https://github.com/microsoft/WSL/issues/6347) -- WSL2 machine-id may be empty on some configurations (MEDIUM confidence; verified populated on OUR target system)
- [Docker Bind Mounts Docs](https://docs.docker.com/engine/storage/bind-mounts/) -- Read-only mount syntax `:ro` (HIGH confidence)
- [Python hashlib docs](https://docs.python.org/3/library/hashlib.html) -- `file_digest()` available in 3.11+ (HIGH confidence)
- [Cython reverse engineering discussion](https://groups.google.com/g/cython-users/c/Zd7HZ9UW_ew) -- `.so` significantly harder to reverse than `.pyc` (MEDIUM confidence, community consensus)
- [Cython multi-stage Docker gist](https://gist.github.com/operatorequals/a1264ad67b3b9a08651c9736bbfe26b0) -- Pattern for Cython in Docker builds (MEDIUM confidence)
- Local verification on target WSL2 system: `/etc/machine-id` populated, `/proc/cpuinfo` accessible, Docker bind mount of machine-id tested successfully, `pip index versions Cython` confirmed 3.2.4 (HIGH confidence)

---
*Stack research for: Kerala LPG Delivery Route Optimizer v2.1 -- Licensing & Distribution Security*
*Researched: 2026-03-10*
