# Project Research Summary

**Project:** Kerala LPG Delivery Route Optimizer -- v2.1 Licensing & Distribution Security
**Domain:** Software licensing enforcement, code protection, and integrity checking for a Python/FastAPI/Docker application deployed on WSL2
**Researched:** 2026-03-10
**Confidence:** HIGH

## Executive Summary

v2.1 is a security-hardening milestone that closes six identified loopholes in an already-working licensing system. The existing system (v2.0) provides HMAC-SHA256 license keys with machine fingerprinting, but uses `.pyc` bytecode (trivially decompilable), startup-only validation (no mid-runtime checks), an exploitable dev-mode bypass, and an unstable fingerprint that relies on Docker container IDs and WSL2 MAC addresses -- both of which change on routine operations. The goal is to move from "Tier 1" (license key at startup) to "Tier 2" (compiled enforcement with integrity checks) without changing the existing offline, single-customer deployment model.

The recommended approach is Cython 3.2.4 compilation of the licensing module to native `.so` shared libraries, combined with SHA256 file integrity manifests embedded in the compiled binary, stronger machine fingerprinting using `/etc/machine-id` and `/proc/cpuinfo`, periodic request-count-based re-validation, dev-mode code stripping from distribution builds, and a license renewal mechanism. The entire stack addition is one build-time dependency (Cython) with zero new runtime dependencies on the customer machine. All technologies are stdlib-based or build-time-only. This is a well-scoped, dependency-light enhancement.

The primary risks are: (1) Cython `.so` files are platform-and-version-locked -- building on the wrong Python version or architecture produces silent import failures, so compilation must happen inside the target Docker container; (2) WSL2 MAC addresses change on every reboot, so MAC must be dropped entirely from the fingerprint (not just supplemented); (3) the fingerprint formula change is a **breaking change** that invalidates all existing customer licenses, requiring a coordinated migration; and (4) dev-mode code stripping with naive `sed` can produce syntactically broken Python that takes down the customer's API -- AST-based validation or marker-based removal with syntax checks is mandatory.

## Key Findings

### Recommended Stack

The existing Python 3.12 / FastAPI / Docker Compose stack is locked and unchanged. v2.1 adds exactly one build-time dependency: **Cython 3.2.4**. No new runtime dependencies are introduced on the customer machine. All other changes use Python stdlib (`hashlib`, `hmac`, `struct`) and Linux system files (`/etc/machine-id`, `/proc/cpuinfo`). See `.planning/research/STACK.md` for full details.

**Core technologies:**
- **Cython 3.2.4** (build-time only): Compiles `core/licensing/*.py` to native `.so` shared libraries. Replaces `.pyc` (decompilable in seconds) with real machine code (requires disassembly). Supports pure Python mode -- no `.pyx` rewrite of existing code needed. Zero customer-side dependencies.
- **`hashlib.file_digest()`** (stdlib, Python 3.11+): SHA256 hashing of protected files for the integrity manifest. Already available in our Python 3.12 runtime.
- **`/etc/machine-id`** (Linux system file): Stable 128-bit machine identifier that survives reboots and container recreation. Bind-mounted read-only into Docker. Replaces the unstable Docker container ID.
- **`/proc/cpuinfo` model name** (Linux procfs): Hardware-intrinsic CPU identifier. Accessible inside Docker containers without special mounting. Cannot change without swapping physical CPU.

**Critical version requirement:** The `.so` files are tagged `cpython-312-x86_64-linux-gnu`. Build and runtime must use the same Python minor version (3.12) and architecture (x86_64). Pin both in the Dockerfile and build script.

### Expected Features

See `.planning/research/FEATURES.md` for full details including dependency graph and expected behavior specifications.

**Must have (table stakes -- close the six identified loopholes):**
- **Dev-mode stripping** -- Remove `ENVIRONMENT=development` bypass from distributed builds. Currently the easiest exploit: one env var disables all enforcement.
- **Cython compilation to `.so`** -- Replace decompilable `.pyc` with native machine code. Prerequisite for three other features.
- **Enforcement logic in compiled module** -- Move middleware from plain-text `main.py` into the compiled `.so`. Expose a single `enforce(app)` entry point.
- **Stronger machine fingerprinting** -- Replace Docker container ID and MAC address with `/etc/machine-id` + CPU model + hostname. Stable across container recreation and reboots.
- **SHA256 file integrity manifest** -- Embed hashes of protected files (main.py) in the compiled binary. Detect tampering at startup and periodically.
- **Periodic re-validation** -- Re-check license + integrity every Nth request (N=500). Catches mid-runtime expiry or file modifications.
- **License renewal mechanism** -- `--renew` flag on `generate_license.py` to extend expiry without requiring new fingerprint exchange.

**Should have (differentiators -- professional polish):**
- Compilation with `-O2` and `embedsignature=False` optimization flags
- Build-time `.so` import validation
- Expiry warning in API response headers (`X-License-Expires-In`)
- License status in `/health` endpoint body for monitoring
- Renewal notification logging (WARNING at 30 days, ERROR in grace period)

**Defer (v2+):**
- Fingerprint similarity scoring (fuzzy match on partial signal changes)
- Call-home license verification (offline requirement is a hard constraint)
- Hardware dongle support
- Centralized license server (makes sense at 50+ customers, not 1)

### Architecture Approach

See `.planning/research/ARCHITECTURE.md` for full component diagrams, data flow changes, and code-level specifications.

The architecture introduces two new compiled modules (`enforcement.py`, `integrity.py`) alongside the existing `license_manager.py`, all compiled to `.so` files via Cython. The key architectural shift is moving enforcement state (license info, request counter) from `app.state` (editable Python object) into module-level variables inside the compiled binary (inaccessible without reverse engineering). `main.py` reduces from ~50 lines of inline licensing logic to a single `enforce(app)` call. The build pipeline gains three new ordered steps: dev-mode stripping, manifest generation, and Cython compilation (order is critical -- manifest must be generated AFTER stripping but BEFORE compilation).

**Major components:**
1. **`core/licensing/enforcement.py` (NEW, compiled to .so)** -- Single entry point for all enforcement. Registers middleware, performs startup validation, orchestrates periodic re-validation and integrity checking. Holds internal state (counter, cached license status) in compiled binary.
2. **`core/licensing/integrity.py` (NEW, compiled to .so)** -- SHA256 manifest verification. Checks protected files against build-time-embedded hashes. Separated from enforcement for testability.
3. **`core/licensing/license_manager.py` (MODIFIED, compiled to .so)** -- Updated fingerprint function (machine-id + cpuinfo + MAC, dropped container_id). Added renewal function.
4. **`scripts/build-dist.sh` (MODIFIED)** -- Rewritten build pipeline: rsync -> strip dev-mode -> generate manifest -> inject manifest -> Cython compile -> remove source -> validate -> tar.

### Critical Pitfalls

See `.planning/research/PITFALLS.md` for all seven critical pitfalls plus integration gotchas, technical debt patterns, and recovery strategies.

1. **Cython `.so` platform lock** -- The `.so` is pinned to `cpython-312-x86_64-linux-gnu`. Building on wrong Python version or architecture produces silent `ModuleNotFoundError`. **Avoid by:** compiling inside the target Docker container, adding version assertion in build script, testing import inside Docker.

2. **WSL2 MAC address instability** -- `uuid.getnode()` returns different values after every WSL2 reboot (microsoft/WSL#5352). This breaks fingerprints. **Avoid by:** dropping MAC address entirely from the fingerprint formula for WSL2 deployments, using `/etc/machine-id` as primary stable signal.

3. **Cython cannot compile async code safely** -- `async def` functions compiled with Cython fail `asyncio.iscoroutinefunction()` checks, causing silent runtime failures in FastAPI (FastAPI#1921). **Avoid by:** strict scope -- compile ONLY synchronous `core/licensing/` code. Add build-time `grep` check for `async def` in compilation targets.

4. **Dev-mode stripping can produce broken Python** -- Naive `sed` removal of if/else blocks leaves syntactically invalid code. Customer's API goes down completely. **Avoid by:** marker-based removal (`# DIST-STRIP-BEGIN` / `# DIST-STRIP-END`) with mandatory `ast.parse()` validation of the stripped file.

5. **Integrity manifest blocks legitimate config edits** -- If `docker-compose.yml` is in the manifest, customer's password change breaks the license. **Avoid by:** excluding `docker-compose.yml` from the manifest. Only protect code files that contain enforcement logic (`main.py`).

## Implications for Roadmap

Based on research, the suggested phase structure follows the dependency chain identified across all four research files. The critical path is: dev-mode stripping -> Cython pipeline -> enforcement module -> integrity manifest -> periodic re-validation. Fingerprinting and renewal are parallel tracks.

### Phase 1: Foundation -- Fingerprinting and Dev-Mode Markers
**Rationale:** Fingerprinting is independent of Cython and changes the identity function used everywhere. Do it first so all subsequent phases use the new formula. Dev-mode markers are zero-risk annotations that prepare for Phase 2 stripping.
**Delivers:** Updated `get_machine_fingerprint()` with machine-id + cpuinfo, Docker Compose machine-id bind mount, updated `get_machine_id.py`, DIST-STRIP markers added to `main.py`.
**Addresses:** Stronger fingerprinting (table stakes), prep for dev-mode stripping.
**Avoids:** WSL2 MAC instability pitfall (drop MAC or make it optional). Fingerprint migration pitfall (update both `license_manager.py` and `get_machine_id.py` simultaneously).
**Key action:** Regenerate the customer's license key with the new fingerprint. This is a breaking change -- coordinate with customer.

### Phase 2: Build Pipeline -- Dev-Mode Stripping and Cython Compilation
**Rationale:** These are the two highest-severity loopholes (#1 and #4). They share a common artifact: `build-dist.sh`. The stripped `main.py` must exist before Cython compiles, and the Cython pipeline must work before enforcement can move into the `.so`. Group them because they are both build-system changes with the same validation pattern.
**Delivers:** Marker-based dev-mode stripping with AST validation, Cython compilation of `core/licensing/*.py` to `.so`, updated build-dist.sh with correct ordering, import validation inside Docker.
**Addresses:** Dev-mode stripping (table stakes), Cython compilation (table stakes).
**Avoids:** Platform lock pitfall (compile inside Docker), syntax error pitfall (AST validation), async compilation pitfall (build-time grep check), architecture mismatch pitfall (ELF header check).
**Key action:** Rotate the HMAC derivation seed since the `.pyc` version is already in the wild and trivially decompilable.

### Phase 3: Enforcement Refactor -- Move Middleware Into Compiled Module
**Rationale:** Must come after Cython pipeline is working. This is the largest architectural change: creating `enforcement.py` and `integrity.py`, moving middleware from `main.py` into compiled code, reducing `main.py` to a single `enforce(app)` call. Test as plain Python first, then compile.
**Delivers:** `core/licensing/enforcement.py` (new), `core/licensing/integrity.py` (new), refactored `main.py` with single enforcement call, internal license state (not on `app.state`).
**Addresses:** Enforcement in compiled module (table stakes), file integrity manifest (table stakes).
**Avoids:** Integrity manifest over-coverage pitfall (protect only `main.py`, not `docker-compose.yml`). Build order pitfall (manifest generated AFTER strip, BEFORE compile).

### Phase 4: Periodic Re-Validation and Polish
**Rationale:** Depends on enforcement module from Phase 3. Adds request counting and re-validation to the middleware. Also a good time for the differentiator features (optimization flags, expiry headers, health endpoint enhancement).
**Delivers:** Request-count-based re-validation (every 500 requests), `run_in_executor` for async-safe re-validation, compilation optimization flags (`-O2`, `embedsignature=False`), expiry warning headers.
**Addresses:** Periodic re-validation (table stakes), compilation optimization (differentiator), expiry warnings (differentiator).
**Avoids:** Event loop blocking pitfall (use threadpool executor). Counter stored in compiled module (not `app.state`).

### Phase 5: License Renewal and Migration
**Rationale:** Independent of the compilation pipeline. Requires fingerprinting to be stable (Phase 1). Best done last because the renewal mechanism should work with the final fingerprint formula and compiled enforcement.
**Delivers:** `--renew` flag on `generate_license.py`, renewal key workflow without new fingerprint exchange, automatic pickup on next periodic re-validation (no restart needed).
**Addresses:** License renewal (table stakes).
**Avoids:** Renewal-after-fingerprint-change pitfall (fingerprint is stable by this phase).

### Phase 6: End-to-End Validation and Customer Migration
**Rationale:** All features are implemented. This phase is about building the distribution tarball, running full E2E license tests, validating the complete build pipeline, and coordinating the customer migration (new fingerprint, new license key, new tarball).
**Delivers:** Complete distribution tarball with all v2.1 security features, E2E test coverage for integrity failure / re-validation / renewal scenarios, updated `docker-compose.license-test.yml`, customer migration documentation.
**Addresses:** All "Looks Done But Isn't" checklist items from PITFALLS.md.

### Phase Ordering Rationale

- **Fingerprinting first** because it changes the identity function consumed by key generation and validation. Every subsequent phase operates on the new fingerprint formula.
- **Build pipeline (strip + Cython) before enforcement refactor** because debugging plain Python is vastly easier than debugging compiled `.so`. Get the compilation working with existing code before introducing new modules.
- **Enforcement refactor before re-validation** because re-validation is an extension of the enforcement middleware. The middleware must exist before it can count requests.
- **Renewal last** because it is developer-side tooling that does not affect the security posture. It is a customer experience improvement, not a loophole fix.
- **End-to-end validation as a final phase** because it exercises the complete pipeline. Partial E2E testing happens in each phase, but the full integration (build tarball -> deploy -> validate license -> test integrity -> test re-validation -> test renewal) must be done holistically.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Cython compilation):** The interaction between Cython, setuptools, and the Docker build environment has edge cases around `build_ext --inplace` directory handling, intermediate `.c` file cleanup, and `__init__.py` compilation. Warrants a `/gsd:research-phase` spike focused on the exact build commands and their output.
- **Phase 3 (Enforcement refactor):** Moving middleware registration into a compiled module while keeping FastAPI's middleware decorator patterns working requires careful testing. The `enforce(app)` function signature and its interaction with FastAPI's startup lifecycle should be prototyped before committing to the architecture.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Fingerprinting):** Well-documented. Reading `/etc/machine-id` and `/proc/cpuinfo` is straightforward file I/O. Docker bind mounts are a standard pattern.
- **Phase 4 (Re-validation):** Standard request-counting middleware with `run_in_executor`. No novel patterns.
- **Phase 5 (Renewal):** Standard HMAC key generation with a `--renew` flag. Reuses existing `encode_license_key()` / `decode_license_key()`.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Only one new dependency (Cython 3.2.4). Version confirmed on PyPI. All other tools are stdlib or already in the project. Verified on target WSL2 system. |
| Features | HIGH | Features scoped directly from six identified loopholes in CONTEXT.md. No ambiguity about what needs to be built. Dependency chain is clear. |
| Architecture | HIGH | Existing codebase thoroughly analyzed with line-number precision. Component boundaries are clean. New modules follow existing patterns. |
| Pitfalls | HIGH | Cython and WSL2 pitfalls verified against GitHub issue trackers and official docs. FastAPI async/Cython incompatibility confirmed via FastAPI#1921. Recovery strategies documented. |

**Overall confidence:** HIGH

### Gaps to Address

- **WSL2 MAC address behavior:** Research strongly recommends dropping MAC from the fingerprint entirely, but STACK.md still includes it as a signal. The PITFALLS.md research is more recent and specific -- **follow the pitfalls recommendation: drop MAC or make it the lowest-weight optional signal.** Validate by running `get_machine_id.py` before and after a WSL restart.
- **Cython compilation inside Docker vs. on host:** STACK.md recommends `cythonize -i` on the developer machine. PITFALLS.md warns this produces architecture-mismatched `.so` if the host ever changes. **Recommendation: compile inside Docker from the start.** The extra build time (seconds) is trivial compared to the debugging cost of a silent import failure.
- **HMAC seed rotation:** PITFALLS.md identifies that the current HMAC derivation seed is recoverable from the existing `.pyc` files. Rotating it means all existing license keys become invalid (in addition to the fingerprint change). This is acceptable since fingerprinting already forces re-keying, but it must be documented and coordinated. **Do both changes (fingerprint + seed) in the same customer migration.**
- **`docker-compose.yml` in integrity manifest:** FEATURES.md includes it as a protected file. PITFALLS.md explicitly warns against it (customers must edit it for passwords, ports). **Follow the pitfalls recommendation: exclude `docker-compose.yml` from the manifest. Protect only `main.py`.**
- **Re-validation interval (N):** FEATURES.md suggests N=250, ARCHITECTURE.md suggests N=500, PITFALLS.md warns against N=100. **Use N=500 as the starting value.** It can be tuned later since it is a compiled constant.
- **Cython async limitation:** The enforcement middleware is `async def` and cannot be compiled by Cython (FastAPI#1921). The current ARCHITECTURE.md design places the middleware inside `enforcement.py` which is compiled. **Resolution: the middleware closure must be defined as a regular `def` or the async wrapper must remain in uncompiled `main.py` while calling synchronous compiled functions.** This needs resolution during Phase 3 design.

## Sources

### Primary (HIGH confidence)
- [Cython 3.2.4 on PyPI](https://pypi.org/project/Cython/) -- version confirmation, pure Python mode support
- [Cython Source Files and Compilation](https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html) -- Extension objects, build patterns, `.so` naming
- [Cython Pure Python Mode](https://cython.readthedocs.io/en/latest/src/tutorial/pure.html) -- confirmation that `.py` compiles directly
- [machine-id(5) manpage](https://man7.org/linux/man-pages/man5/machine-id.5.html) -- 32-char hex, persistence guarantees
- [Python hashlib docs](https://docs.python.org/3/library/hashlib.html) -- `file_digest()` in 3.11+
- [FastAPI Advanced Middleware](https://fastapi.tiangolo.com/advanced/middleware/) -- middleware registration patterns
- [Docker Bind Mounts](https://docs.docker.com/engine/storage/bind-mounts/) -- read-only mount syntax
- Local verification on target WSL2 system: `/etc/machine-id` populated, `/proc/cpuinfo` accessible, Docker bind mount tested

### Secondary (MEDIUM confidence)
- [WSL2 MAC address instability: microsoft/WSL#5352](https://github.com/microsoft/WSL/issues/5352) -- confirmed WSL2 MAC randomization
- [Cython async issue: FastAPI#1921](https://github.com/fastapi/fastapi/issues/1921) -- async def incompatibility with Cython compilation
- [Python uuid.getnode() instability: cpython#132710](https://github.com/python/cpython/issues/132710) -- MAC not guaranteed stable with libuuid
- [Cython reverse engineering difficulty](https://groups.google.com/g/cython-users/c/Zd7HZ9UW_ew) -- community consensus that `.so` is significantly harder than `.pyc`
- [Cisco: Securing Python with Cython](https://blogs.cisco.com/developer/securingpythoncodewithcython01) -- practical guide
- [WSL2 machine-id persistence: microsoft/WSL#6347](https://github.com/microsoft/WSL/issues/6347) -- WSL2 machine-id edge cases

### Tertiary (LOW confidence)
- [NixOS-WSL /etc/machine-id persistence issue](https://github.com/nix-community/NixOS-WSL/issues/574) -- NixOS-specific, does not apply to standard Ubuntu WSL but worth monitoring

---
*Research completed: 2026-03-10*
*Ready for roadmap: yes*
