# Pitfalls Research

**Domain:** Licensing & Distribution Security -- Cython compilation, file integrity checking, machine fingerprinting, periodic re-validation, dev-mode stripping, and license renewal for an existing FastAPI/Docker application on WSL2
**Researched:** 2026-03-10
**Confidence:** HIGH for Cython/.so pitfalls (verified against Cython docs, FastAPI issue tracker, CPython naming conventions); HIGH for WSL2 fingerprinting instability (verified against WSL GitHub issue tracker); MEDIUM for integrity manifest bypass patterns (general security principles, not project-specific verification); HIGH for async middleware counter pitfalls (verified against FastAPI concurrency docs)

---

## Critical Pitfalls

### Pitfall 1: Cython .so Files Are Python-Version-AND-Platform-Locked

**What goes wrong:**
Cython compiles `.py` files into native `.so` shared libraries with names like `license_manager.cpython-312-x86_64-linux-gnu.so`. This name encodes the exact Python minor version (3.12) and platform (x86_64 Linux). If the build machine uses Python 3.12 but the Docker image upgrades to Python 3.13 (even a minor bump like `python:3.12-slim` -> `python:3.13-slim`), the `.so` file will not import. Python's import machinery looks for the platform-tagged name first and silently skips files that don't match.

This is worse than the current `.pyc` approach. `.pyc` files have a magic number check that produces a clear error message. `.so` files simply aren't found by the import system -- you get `ModuleNotFoundError: No module named 'core.licensing.license_manager'` with zero indication that the problem is a version mismatch.

**Why it happens:**
The current Dockerfile uses `python:3.12-slim` and the build script uses the host's Python. Developers assume "Python 3" is enough. But Cython's `cythonize()` and `setuptools.build_ext` produce ABI-tagged `.so` files that are pinned to the exact CPython version and ABI flags. Even a rebuild on the same machine with a different Python patch version (3.12.3 vs 3.12.5) is fine (same ABI tag), but 3.12 vs 3.13 is not.

**How to avoid:**
1. **Compile inside the same Docker image** used for runtime. Add a build stage to the Dockerfile or use a separate build script that runs `python setup.py build_ext --inplace` inside a `python:3.12-slim` container. Never compile on the host and copy into Docker.
2. **Pin the exact Python minor version** in both Dockerfile (`FROM python:3.12-slim`) and build script. Add a version check at the top of `build-dist.sh`: `python3 -c "import sys; assert sys.version_info[:2] == (3, 12), f'Need Python 3.12, got {sys.version_info}'"`.
3. **Test the import inside the Docker container** as part of the build pipeline, not just on the host. The existing import validation step (`PYTHONPATH="$STAGE" python3 -c "import core.licensing..."`) must run inside the target Docker image.

**Warning signs:**
- `ModuleNotFoundError` for `core.licensing` in the container but works on the host
- `.so` filename in the staging directory doesn't match the Python version in the Docker image
- `build-dist.sh` runs on a host with a different Python version than the Dockerfile's base image

**Phase to address:**
Phase 1 (Cython compilation pipeline) -- this must be validated before any other feature is built on top of the compiled module.

---

### Pitfall 2: WSL2 MAC Address Changes on Every Reboot, Breaking Fingerprints

**What goes wrong:**
The current `get_machine_fingerprint()` uses `uuid.getnode()` (MAC address) as a primary fingerprint signal. In WSL2, the virtual network adapter's MAC address changes on every WSL restart or Windows reboot. This is a known, long-standing WSL2 issue (microsoft/WSL#5352, microsoft/WSL#5291). The fingerprint computed at license-generation time will not match the fingerprint computed after a reboot, causing the license to fail validation with "License key is not valid for this machine."

Compounding the problem: Python's `uuid.getnode()` may not even return the real MAC address when built with `libuuid` -- it can return a random number that is cached per-process but not persistent across restarts (cpython/cpython#132710).

**Why it happens:**
WSL2 runs as a lightweight VM with a virtual Hyper-V network adapter. Microsoft intentionally randomizes the MAC address on each start for network isolation. This was a design choice, not a bug, and there is no official fix. Setting a static MAC address manually breaks internet connectivity in WSL2.

**How to avoid:**
1. **Drop MAC address from the fingerprint entirely** for WSL2 deployments. The v2.1 plan already calls for this (replacing container_id with /etc/machine-id + /proc/cpuinfo), but the MAC address must also be removed, not just supplemented.
2. **Use `/etc/machine-id` as the primary stable signal.** WSL2's `/etc/machine-id` is generated once during distro installation and persists across reboots. Bind-mount it read-only into the Docker container.
3. **Use CPU model string from `/proc/cpuinfo`** (e.g., `model name : Intel(R) Core(TM) i7-10750H`) as a secondary signal. This is stable across reboots and reflects the actual hardware. Do NOT use clock speed (`cpu MHz`) which fluctuates with power management.
4. **Use hostname as a tertiary signal**, but document that changing the WSL hostname invalidates the license (acceptable -- customers rarely change hostnames).

**Warning signs:**
- License works after fresh generation but fails after Windows reboot
- `get_machine_id.py` produces different output each time it runs
- Customer reports "license stopped working" with no code changes

**Phase to address:**
Phase 2 (Fingerprinting hardening) -- must be implemented before shipping any builds to customers, and before license renewal is implemented (otherwise renewal keys will also be unstable).

---

### Pitfall 3: Cython Cannot Compile FastAPI Async Route Handlers

**What goes wrong:**
If you accidentally try to compile `main.py` or any module containing `async def` route handlers with Cython, the compiled code will silently break. Cython-compiled async functions don't pass `asyncio.iscoroutinefunction()` checks, which FastAPI uses internally to determine whether to `await` a handler's return value. The result: handlers return raw coroutine objects instead of awaited responses, producing `TypeError("'coroutine' object is not iterable")` or `TypeError('vars() argument must have __dict__ attribute')` at runtime.

This has been a documented issue since FastAPI#1921 (2020) and remains unfixed in FastAPI itself. Cython 3.0+ partially addresses it, but the `iscoroutinefunction` mismatch persists in some introspection paths.

**Why it happens:**
The v2.1 scope is to compile only `core/licensing/` -- which contains synchronous functions only. But during implementation, there's a temptation to also compile the enforcement middleware in `main.py` (which is `async def`) or to move enforcement logic into an async function inside the licensing module. Any async code in the compiled module will hit this bug.

**How to avoid:**
1. **Strict scope: compile ONLY `core/licensing/` and nothing else.** The licensing module (`license_manager.py`, `__init__.py`) contains zero async code -- it's all synchronous (hashlib, hmac, struct, file I/O). Keep it that way.
2. **Never add `async def` to any file that will be Cython-compiled.** The enforcement middleware must stay in `main.py` as plain Python. The compiled module should expose synchronous validation functions that the middleware calls.
3. **Add a lint check in `build-dist.sh`** that greps for `async def` in files targeted for Cython compilation and fails the build if found: `grep -r "async def" core/licensing/ && { echo "ERROR: async code in licensing module will break Cython"; exit 1; }`.

**Warning signs:**
- `TypeError: 'coroutine' object is not iterable` in production logs
- License validation works in unit tests (pure Python) but fails in Docker (compiled)
- Endpoints return empty 500 errors with no clear traceback

**Phase to address:**
Phase 1 (Cython compilation pipeline) -- enforce with a build-time check so this can never slip in during later phases.

---

### Pitfall 4: Dev-Mode Code Stripping Leaves Syntactically Invalid Python

**What goes wrong:**
The plan calls for `build-dist.sh` to remove the `if env == "development"` block from `main.py` before packaging. Naive text-based stripping (using `sed` or similar) can leave syntactically broken Python if the if/else structure is not perfectly handled. For example, removing the `else:` branch of `if env == "production":` / `else:` leaves an orphaned `if` with no body, or removing the wrong lines breaks indentation. The tarball ships, the Docker container starts, and `main.py` fails to parse -- the entire API is down with `SyntaxError`.

This is especially dangerous because the current dev-mode block (main.py lines 184-203) creates a replacement `LicenseInfo` object inside the `else:` branch. Simply deleting those lines leaves the `if license_info.status == LicenseStatus.INVALID:` branch's `else:` clause empty.

**Why it happens:**
Text-based code manipulation is fragile. The developer writes a `sed` command that works for the current code, but any reformatting, added comments, or minor refactoring breaks the regex. There's no feedback loop -- the build script "succeeds" but produces invalid Python.

**How to avoid:**
1. **Use AST-based transformation, not text manipulation.** Write a small Python script that uses the `ast` module to parse `main.py`, identify and remove the dev-mode branch, and write valid Python back. This is robust against formatting changes.
2. **Alternatively, restructure `main.py` before v2.1** so the dev-mode code is isolated behind a clear sentinel marker (e.g., `# BEGIN_DEV_ONLY` / `# END_DEV_ONLY`) that can be reliably stripped with a simple line-range delete.
3. **Validate the stripped `main.py` parses correctly** in `build-dist.sh`: `python3 -c "import ast; ast.parse(open('$STAGE/apps/kerala_delivery/api/main.py').read())"`. This catches syntax errors immediately.
4. **Run the existing unit test suite against the staged directory** before packaging. If `main.py` is broken, tests will fail.

**Warning signs:**
- `SyntaxError` when the API container starts (check Docker logs)
- Build script succeeds but `python3 -c "import ..."` against the staged directory fails
- Customer reports "API won't start after update"

**Phase to address:**
Phase 1 (Dev-mode stripping) -- implement and validate before the Cython compilation phase, because the stripped `main.py` is what gets integrity-checked.

---

### Pitfall 5: Integrity Manifest Becomes Stale After Docker Compose Edits

**What goes wrong:**
The SHA256 integrity manifest is generated at build time and baked into the compiled `.so`. It covers `main.py`, `middleware.py`, and `docker-compose.yml`. But the customer might legitimately edit `docker-compose.yml` to change environment variables (e.g., `POSTGRES_PASSWORD`, `GOOGLE_MAPS_API_KEY`, port mappings). Any edit to a manifest-covered file triggers an integrity failure, and the license stops working. The customer sees "License expired or invalid" with no indication that a config file edit caused it.

**Why it happens:**
The manifest design treats all file modifications as tampering. But `docker-compose.yml` contains both infrastructure config (which customers must customize) and security-critical config (which should not be modified). There's no way to distinguish between the two after the manifest is generated.

**How to avoid:**
1. **Exclude `docker-compose.yml` from the integrity manifest.** It's not a code file -- it's a config file that customers must edit. Protecting it adds friction without security benefit (the real enforcement is in the compiled `.so`).
2. **Only manifest files that contain enforcement logic:** `main.py`, any middleware files that import from `core.licensing`, and the `core/licensing/__init__.py` stub (if one exists after compilation). These are the files where someone would try to bypass licensing.
3. **Provide clear, specific error messages** when integrity check fails: "File X has been modified (expected hash: abc..., actual: def...). If you need to customize configuration, edit .env instead of docker-compose.yml." This prevents customer confusion.
4. **Consider using `.env` for all customer-configurable values** and making `docker-compose.yml` read-only in the distribution. The existing `.env.example` pattern already supports this.

**Warning signs:**
- Customer reports license failure after changing database password
- Integrity check fails on first boot because the customer followed setup instructions that involve editing docker-compose.yml
- Support tickets spike after distribution updates

**Phase to address:**
Phase 3 (Integrity manifest) -- the manifest file list must be carefully chosen during design, not as an afterthought.

---

### Pitfall 6: Request-Counter Re-Validation Blocks the Event Loop on Synchronous License Check

**What goes wrong:**
The periodic re-validation plan calls for the compiled middleware to re-run license validation every N requests. The current `validate_license()` function performs synchronous file I/O (reading `license.key`) and hashing operations. If called directly from an `async def` middleware handler, it blocks the asyncio event loop for the duration of the validation (10-50ms for SHA256 hashing of manifest files + file reads). During that time, ALL concurrent requests are stalled -- not just the one that triggered re-validation.

With 2 uvicorn workers and ~100 concurrent requests during peak delivery hours, a 50ms block means 100 requests wait 50ms extra. At every-100th-request validation, this happens once per second at 100 req/s. The cumulative effect is noticeable latency spikes in the driver PWA.

**Why it happens:**
FastAPI's `async def` middleware runs on the main event loop thread. Unlike `def` endpoints (which run in a threadpool), middleware has no automatic threadpool offloading. Developers assume "it's just a hash check, it's fast" -- but file I/O + SHA256 of multiple files adds up, especially on Docker's overlayfs.

**How to avoid:**
1. **Run the re-validation in a threadpool** using `asyncio.get_event_loop().run_in_executor(None, validate_and_check_integrity)`. This offloads the synchronous work to a thread, keeping the event loop responsive.
2. **Cache the validation result** with a timestamp. Instead of re-running full validation on every Nth request, check "has it been M seconds since last validation?" and only re-validate if both the request count AND time threshold are met. This bounds the worst-case frequency.
3. **Keep the counter as a simple integer in the compiled module.** In CPython, integer increment (`counter += 1`) is atomic due to the GIL, even with multiple uvicorn workers (each worker is a separate process with its own counter, which is fine -- each process validates independently).
4. **Set N to a reasonable value** like 500-1000 requests, not 10 or 50. At 100 req/s peak, N=500 means re-validation every 5 seconds -- more than sufficient to catch a mid-runtime license change.

**Warning signs:**
- Latency spikes every N requests in driver PWA network tab
- Uvicorn logs show "WARNING: ... took longer than expected" for middleware
- `asyncio` debug mode reports "Executing ... took 0.050 seconds"

**Phase to address:**
Phase 4 (Periodic re-validation) -- must use threadpool executor from the start, not retrofitted after performance complaints.

---

### Pitfall 7: Cython Build Produces Architecture-Mismatched .so for Docker

**What goes wrong:**
If `build-dist.sh` runs on an ARM Mac (Apple Silicon) or any non-x86_64 host, the compiled `.so` will be for the wrong architecture. The Docker container runs `python:3.12-slim` which is x86_64 Linux (or matches the Docker host platform). A `.so` compiled natively on macOS/ARM will produce `license_manager.cpython-312-aarch64-linux-gnu.so` or `license_manager.cpython-312-darwin.so`, which the x86_64 container cannot load.

This is not currently a problem (deployment is WSL2 on x86_64), but it will bite if the developer works on a Mac or if the build pipeline moves to GitHub Actions (which uses x86_64 Linux runners by default but may switch to ARM).

**Why it happens:**
Cython compiles to native code, unlike `.pyc` which is platform-independent bytecode. The current `.pyc` approach works everywhere because CPython's bytecode is architecture-agnostic. Switching to `.so` breaks this portability.

**How to avoid:**
1. **Always compile inside the target Docker container**, not on the host. Use a Docker-based build step: `docker run --rm -v $(pwd):/app -w /app python:3.12-slim pip install cython && python setup.py build_ext --inplace`. This guarantees the `.so` matches the runtime environment.
2. **Add an architecture check in `build-dist.sh`** that verifies the `.so` file's ELF header matches the target: `file "$STAGE/core/licensing/license_manager*.so" | grep -q "x86-64" || { echo "ERROR: .so is not x86_64"; exit 1; }`.
3. **Document the build requirement**: "Must build on x86_64 Linux or inside Docker."

**Warning signs:**
- `ImportError: ... wrong ELF class` or `invalid ELF header` in container logs
- `.so` filename contains `darwin` or `aarch64` instead of `x86_64-linux-gnu`
- Build works on developer's machine but fails in Docker

**Phase to address:**
Phase 1 (Cython compilation pipeline) -- the build must be containerized from day one.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Compiling `.so` on host instead of in Docker | Faster build iteration | Breaks on any platform mismatch; silent import failures | Never for distribution builds; OK for local testing only |
| Text-based sed stripping of dev-mode code | Simple, no Python dependency in build | Breaks on any reformatting; no syntax validation | Never -- use AST-based or sentinel-based approach |
| Including docker-compose.yml in integrity manifest | More files "protected" | Customer edits break license; support burden | Never -- protect code files only |
| Hardcoding N=100 for re-validation counter | Simple implementation | Too frequent at high load; performance cost | Only if combined with time-based debounce |
| Using `uuid.getnode()` for MAC in WSL2 | No code change needed | Fingerprint changes on reboot; license breaks | Never on WSL2 -- remove MAC entirely |
| Monolithic `validate_license()` doing fingerprint + integrity + expiry | Single function, simple | Cannot test components independently; re-validation is all-or-nothing | Only in v1.x; refactor for v2.1 to separate concerns |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Cython + Docker multi-stage build | Installing Cython in runtime stage (bloats image, exposes build tools) | Install Cython only in the builder stage; copy only the compiled `.so` to runtime stage; never ship Cython itself |
| `/etc/machine-id` bind mount | Mounting without `:ro` flag; container could theoretically write to host's machine-id | Always use `- /etc/machine-id:/etc/machine-id:ro` in docker-compose.yml; add comment explaining why |
| `/proc/cpuinfo` in Docker | Reading `cpu MHz` (fluctuates with power management) or `processor` count (varies with `--cpus` flag) | Read only `model name` and `vendor_id` -- these are hardware constants that don't change with Docker resource limits |
| Cython + existing test suite | Tests import from `core.licensing.license_manager` which no longer exists as `.py` | Tests must run against source `.py` (not compiled `.so`); keep `.py` in the repository; only remove in `build-dist.sh` staging |
| License renewal + fingerprint change | Generating renewal key with old fingerprint signals (MAC), which no longer match after the fingerprinting upgrade | Generate renewal keys using the NEW fingerprint format; provide a migration path for existing customers (re-run `get_machine_id.py` with updated script) |
| `build-dist.sh` + Cython setup.py | Running `setup.py build_ext` in the project root, polluting source tree with `.so` files and `build/` directory | Use `--build-lib` to output to the staging directory; or run inside an isolated temp directory; clean up `build/` and `*.c` intermediates |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Synchronous integrity check in async middleware | All concurrent requests block during file hashing; latency spikes every N requests | Use `run_in_executor()` for file I/O and hashing; cache result with TTL | At ~50 concurrent requests; noticeable at 100+ |
| Re-hashing all manifest files on every check | Disk I/O on overlayfs is slow; each file read + SHA256 = 5-20ms | Hash once at startup; re-hash only on re-validation trigger (every Nth request) | At any concurrency level -- overlayfs is slow |
| Full `validate_license()` on every re-validation | Reads license.key from disk, computes fingerprint, decodes key, checks expiry | Cache decoded license info; only re-read file if mtime changed; only recompute fingerprint on first call (it doesn't change mid-runtime) | Immediately measurable; 10-50ms per validation call |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Embedding HMAC secret in compiled `.so` without changing the derivation seed | Determined attacker extracts the seed from the old `.pyc` (trivial) and it still works with the new `.so` | Rotate the `_DERIVATION_SEED` value when switching from `.pyc` to `.so`; existing license keys must be re-generated |
| Integrity manifest stored as a separate file (not embedded in `.so`) | Attacker replaces both the manifest file and the code files; manifest check passes with attacker's hashes | Embed manifest directly in the Cython source before compilation; it becomes part of the native binary |
| Request counter stored in `app.state` (Python object) | Attacker patches `main.py` to reset counter to 0 on each request, preventing re-validation | Store counter inside the compiled `.so` module as a module-level variable; inaccessible without reverse-engineering the binary |
| `/etc/machine-id` readable by any process in the container | Not a real risk for licensing, but principle of least privilege | Mount read-only; run container as non-root (already done); this is defense in depth |
| Logging fingerprint details in plaintext | Customer sends logs to support; logs contain all fingerprint signals; attacker on same network intercepts | Log only the final SHA256 hash, never the component signals (hostname, machine-id, CPU info); current code already follows this pattern |
| Not changing the HMAC key derivation when format changes | License keys from v1.x (with MAC + container_id fingerprint) could be replayed against v2.1 (with machine-id + cpuinfo fingerprint) if the HMAC key is unchanged | The fingerprint is embedded IN the key, so old keys won't match new fingerprints; BUT if the attacker generates their own key, the same HMAC key means the generation script still works. Rotate the seed. |

## "Looks Done But Isn't" Checklist

- [ ] **Cython compilation:** Often missing the `__init__.py` compilation -- both `__init__.py` AND `license_manager.py` must be compiled to `.so`. If `__init__.py` is left as `.py`, it creates an import inconsistency. If it's deleted without compilation, `import core.licensing` fails entirely.
- [ ] **Dev-mode stripping:** Often strips the code but forgets to remove the `ENVIRONMENT` variable from `docker-compose.yml` -- customer sets `ENVIRONMENT=development` in `.env` and bypasses everything.
- [ ] **Fingerprint migration:** Often updates `license_manager.py` fingerprinting but forgets to update `scripts/get_machine_id.py` -- customer runs old script, sends old fingerprint, gets a key that doesn't match new validation.
- [ ] **Docker volume mount:** Often adds `/etc/machine-id` mount to `docker-compose.yml` but forgets `docker-compose.license-test.yml` and `docker-compose.prod.yml` -- E2E license tests fail or production deploys fail.
- [ ] **build-dist.sh exclusions:** Often adds Cython build artifacts (`.c` files, `build/` directory, `*.egg-info`) but forgets to add them to the rsync `--exclude` list -- tarball ships with intermediate C files and build metadata.
- [ ] **License renewal E2E test:** Often tests renewal happy path but forgets to test renewal-after-fingerprint-change scenario -- renewal works in dev but fails for customers who rebooted between initial license and renewal.
- [ ] **Verify-dist.sh updates:** Often updates `build-dist.sh` for Cython but forgets to update `verify-dist.sh` which still checks for `.pyc` files instead of `.so` files.
- [ ] **ENVIRONMENT variable removal:** Strips dev-mode code from `main.py` but leaves `ENVIRONMENT=${ENVIRONMENT:-development}` in docker-compose.yml; the variable is unused but confusing, and a determined attacker might try to re-add the dev-mode code path.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| .so version mismatch (wrong Python version) | LOW | Rebuild with correct Python version inside Docker; re-package tarball; no customer data lost |
| Fingerprint changes after WSL reboot | MEDIUM | Customer re-runs `get_machine_id.py`, sends new fingerprint; we generate new key or renewal key; customer replaces `license.key` and restarts. Requires support interaction. |
| Dev-mode stripping produces broken main.py | HIGH | Customer's API is completely down. Emergency: ship a corrected tarball. Prevention is much cheaper than recovery. |
| Integrity manifest blocks legitimate edits | LOW | Customer restores original file from backup or re-extracts from tarball; OR we ship a new build with corrected manifest. Support must identify which file was modified. |
| Event loop blocked by sync re-validation | LOW | Deploy a patched version with `run_in_executor()`. No data loss, just performance degradation until patched. |
| HMAC seed not rotated, old keys still work | MEDIUM | Generate new keys with new seed for all customers; coordinate key replacement. Old keys stop working immediately when new `.so` is deployed. Must time the rollout carefully. |
| Architecture-mismatched .so in tarball | LOW | Rebuild inside Docker on correct platform; re-package; no data loss. But the customer's system is down until the new tarball arrives. |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| .so Python version lock | Phase 1: Cython Pipeline | `python3 -c "import core.licensing"` runs inside Docker container after build; `.so` filename contains `cpython-312` |
| WSL2 MAC address instability | Phase 2: Fingerprint Hardening | `get_machine_id.py` produces same output before and after WSL restart; no `uuid.getnode()` calls remain |
| Async code in compiled module | Phase 1: Cython Pipeline | `grep -r "async def" core/licensing/` returns nothing; build-time check enforced |
| Dev-mode stripping syntax errors | Phase 1: Dev-Mode Stripping | `python3 -c "ast.parse(...)"` against stripped `main.py`; pytest runs against staged directory |
| Integrity manifest over-coverage | Phase 3: Integrity Manifest | Manifest file list documented; `docker-compose.yml` explicitly excluded; customer can edit `.env` without triggering integrity failure |
| Event loop blocking on re-validation | Phase 4: Periodic Re-Validation | Load test with 50 concurrent requests; no request takes >200ms during re-validation window |
| Architecture mismatch | Phase 1: Cython Pipeline | `file *.so` shows `x86-64` and `ELF`; build runs inside Docker |
| HMAC seed not rotated | Phase 1: Cython Pipeline | Old license keys fail validation with new `.so`; generate_license.py updated with new seed |
| `get_machine_id.py` out of sync | Phase 2: Fingerprint Hardening | `get_machine_id.py` and `license_manager.py` produce identical fingerprints on same machine |
| Docker volume mounts missing | Phase 2: Fingerprint Hardening | All docker-compose*.yml files mount `/etc/machine-id:ro`; E2E license tests pass |
| verify-dist.sh still checks .pyc | Phase 1: Cython Pipeline | `verify-dist.sh` checks for `.so` files and validates they import correctly |
| ENVIRONMENT variable in docker-compose.yml | Phase 1: Dev-Mode Stripping | Distributed `docker-compose.yml` does not reference `ENVIRONMENT` variable at all |

## Sources

- [Cython FastAPI coroutine issue: FastAPI#1921](https://github.com/fastapi/fastapi/issues/1921)
- [Cython .so naming convention: Cython documentation](https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html)
- [WSL2 MAC address instability: microsoft/WSL#5352](https://github.com/microsoft/WSL/issues/5352)
- [WSL2 fixed MAC address request: microsoft/WSL#5291](https://github.com/microsoft/WSL/issues/5291)
- [Python uuid.getnode() not tied to MAC with libuuid: cpython#132710](https://github.com/python/cpython/issues/132710)
- [Cython async iscoroutinefunction issue: cython/cython#2273](https://github.com/cython/cython/issues/2273)
- [FastAPI concurrency model: FastAPI docs](https://fastapi.tiangolo.com/async/)
- [Docker /proc/cpuinfo inconsistencies: docker/for-mac#6111](https://github.com/docker/for-mac/issues/6111)
- [Cython glibc version compatibility](https://snorfalorpagus.net/blog/2016/07/17/compiling-python-extensions-for-old-glibc-versions/)
- [Protecting Python code with Cython and Docker](https://shawinnes.com/protecting-python/)
- [Cython Pure Python Mode](https://cython.readthedocs.io/en/latest/src/tutorial/pure.html)
- [Docker bind mount security: Docker docs](https://docs.docker.com/engine/storage/bind-mounts/)
- [FastAPI thread safety discussion: fastapi#876](https://github.com/fastapi/fastapi/issues/876)

---
*Pitfalls research for: v2.1 Licensing & Distribution Security*
*Researched: 2026-03-10*
